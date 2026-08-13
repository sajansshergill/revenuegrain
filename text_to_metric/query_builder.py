"""
Turn a natural-language question into BigQuery SQL, constrained to the
governed metrics defined in semantic_layer.yml.
"""
from __future__ import annotations

import os
import re

import yaml

try:
    from .llm_client import LLMClient
except ImportError:
    from llm_client import LLMClient

HERE = os.path.dirname(os.path.abspath(__file__))

SYSTEM_TEMPLATE = """You are a careful analytics engineer. Translate the user's
question into a single BigQuery SQL query, using ONLY the metrics and dimensions
defined below. Do not invent columns or tables. Prefer the pre-defined metric
expressions. Join core.dim_accounts when a segment or current_status filter is
needed, using account_id. Return ONLY SQL — no prose, no markdown fences.

SEMANTIC LAYER:
{semantic}
"""

_METRIC_ALIASES = (
    ("net_revenue_retention", ("nrr", "net revenue retention", "net retention")),
    ("gross_revenue_retention", ("grr", "gross revenue retention", "gross retention")),
    ("account_health", ("health", "health score", "account health")),
    ("feature_adoption", ("feature", "adoption", "usage")),
    ("mrr", ("mrr", "monthly recurring", "revenue")),
)


def load_semantic_layer(path: str | None = None) -> dict:
    path = path or os.path.join(HERE, "semantic_layer.yml")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data or "metrics" not in data:
        raise ValueError(f"semantic layer at {path} is missing metrics")
    return data


def _strip_fences(sql: str) -> str:
    cleaned = re.sub(r"^```(?:sql)?\s*", "", sql.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    return cleaned.strip().rstrip(";") + ";"


def _match_metric(question: str, semantic: dict) -> dict:
    q = question.lower()
    by_name = {m["name"]: m for m in semantic["metrics"]}
    for name, aliases in _METRIC_ALIASES:
        if any(alias in q for alias in aliases) and name in by_name:
            return by_name[name]
    return semantic["metrics"][0]


def _year_filter(question: str, time_column: str | None) -> str:
    if not time_column:
        return ""
    match = re.search(r"\b(20\d{2})\b", question)
    if not match:
        return ""
    year = match.group(1)
    return f"\nwhere extract(year from {time_column}) = {year}"


def compile_sql(question: str, semantic: dict) -> str:
    metric = _match_metric(question, semantic)
    model = metric["model"]
    expression = metric["expression"]
    time_column = metric.get("time_column")
    q = question.lower()

    select_parts = [f"{expression} as {metric['name']}"]
    group_parts: list[str] = []
    joins = ""

    wants_time = bool(time_column) and (
        any(word in q for word in ("month", "by month", "trend", "over time"))
        or bool(re.search(r"20\d{2}", q))
    )
    if wants_time:
        select_parts.insert(0, time_column)
        group_parts.append(time_column)

    dim_src = semantic.get("dimensions_source") or {}
    if "segment" in q and "segment" in dim_src:
        dim = dim_src["segment"]
        joins = (
            f"\nleft join {dim['model']} d"
            f"\n  on m.{dim['join_key']} = d.{dim['join_key']}"
        )
        select_parts.insert(0, f"d.{dim['column']}")
        group_parts.insert(0, f"d.{dim['column']}")

    where = _year_filter(question, time_column)
    select_sql = ",\n    ".join(select_parts)
    group_sql = f"\ngroup by {', '.join(group_parts)}" if group_parts else ""
    order_sql = f"\norder by {group_parts[0]}" if group_parts else ""

    sql = (
        f"select\n    {select_sql}\n"
        f"from {model} m"
        f"{joins}"
        f"{where}"
        f"{group_sql}"
        f"{order_sql}"
    )
    return _strip_fences(sql)


class QueryBuilder:
    def __init__(self, client: LLMClient | None = None, semantic: dict | None = None):
        self.semantic = semantic or load_semantic_layer()
        self.client = client
        self.used_llm = False

    def _llm(self) -> LLMClient | None:
        if self.client is not None:
            return self.client
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        self.client = LLMClient()
        return self.client

    def allowed_models(self) -> set[str]:
        models = {m["model"] for m in self.semantic.get("metrics", [])}
        for dim in self.semantic.get("dimensions_source", {}).values():
            models.add(dim["model"])
        return models

    def build(self, question: str) -> str:
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        client = self._llm()
        if client is None:
            self.used_llm = False
            return compile_sql(question.strip(), self.semantic)
        self.used_llm = True
        system = SYSTEM_TEMPLATE.format(semantic=yaml.dump(self.semantic, sort_keys=False))
        raw = client.complete(system=system, user=question.strip())
        return _strip_fences(raw)


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "What was net revenue retention by month in 2025?"
    print(QueryBuilder().build(q))
