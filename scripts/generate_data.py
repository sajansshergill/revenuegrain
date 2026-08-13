"""
Synthetic SaaS operational data generator for RevenueGrain.

Produces four raw CSVs (accounts, subscriptions, usage_events, tickets) that
match the source definitions in models/staging/_staging__sources.yml.

The data is deliberately seeded with duplicates, nulls, and late-arriving
rows so the dbt staging layer and test suite have real defects to clean.

Usage:
    python scripts/generate_data.py
    python scripts/generate_data.py --accounts 80 --out ./data --seed 42
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml
from faker import Faker

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "seed_config.yml")

SEGMENTS = ["smb", "mid-market", "enterprise"]
SEGMENT_WEIGHTS = [0.5, 0.35, 0.15]
INDUSTRIES = ["software", "retail", "healthcare", "finance", "manufacturing", "education"]
COUNTRIES = ["US", "CA", "GB", "DE", "IN", "AU"]
BILLING = ["monthly", "annual"]
FEATURES = ["dashboards", "api_access", "sso", "alerts", "exports", "audit_log", "workflows"]
TICKET_PRIORITY = ["low", "medium", "high", "urgent"]
TICKET_CATEGORY = ["billing", "bug", "how-to", "feature-request", "outage"]

# plan_id -> monthly price in cents (mirrors seeds/seed_plan_tiers.csv)
PLAN_PRICES = {1: 4900, 2: 19900, 3: 49900, 4: 149900, 5: 299900}
SEGMENT_PLANS = {
    "smb": [1, 2],
    "mid-market": [2, 3],
    "enterprise": [4, 5],
}


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _rng(seed: int) -> Faker:
    np.random.seed(seed)
    fake = Faker()
    Faker.seed(seed)
    return fake


def generate_accounts(fake: Faker, n: int, start: datetime, end: datetime, null_industry_fraction: float) -> pd.DataFrame:
    rows = []
    span_days = max((end - start).days, 1)
    for _ in range(n):
        signup = start + timedelta(days=int(np.random.randint(0, span_days)))
        segment = np.random.choice(SEGMENTS, p=SEGMENT_WEIGHTS)
        industry = np.random.choice(INDUSTRIES)
        if np.random.random() < null_industry_fraction:
            industry = None
        rows.append(
            {
                "account_id": str(uuid4()),
                "account_name": fake.company(),
                "segment": segment,
                "industry": industry,
                "country": np.random.choice(COUNTRIES),
                "signup_date": signup.date().isoformat(),
                "created_at": (signup + timedelta(hours=int(np.random.randint(0, 12)))).isoformat(),
            }
        )
    return pd.DataFrame(rows)


def generate_subscriptions(accounts: pd.DataFrame, end: datetime, churn_rate: float) -> pd.DataFrame:
    rows = []
    for _, acc in accounts.iterrows():
        signup = datetime.fromisoformat(acc["signup_date"])
        plan = int(np.random.choice(SEGMENT_PLANS[acc["segment"]]))
        base_price = PLAN_PRICES[plan]
        churned = np.random.random() < churn_rate
        started = signup
        ended = None
        status = "active"
        if churned:
            months = int(np.random.randint(2, 24))
            ended = started + timedelta(days=30 * months)
            if ended > end:
                ended, status, churned = None, "active", False
            else:
                status = "churned"

        rows.append(
            {
                "subscription_id": str(uuid4()),
                "account_id": acc["account_id"],
                "plan_id": plan,
                "status": status,
                "mrr_cents": base_price,
                "started_at": started.isoformat(),
                "ended_at": ended.isoformat() if ended else None,
                "billing_interval": np.random.choice(BILLING, p=[0.7, 0.3]),
            }
        )

        if not churned and np.random.random() < 0.20:
            higher = min(plan + 1, 5)
            upgrade_start = started + timedelta(days=30 * int(np.random.randint(3, 12)))
            if upgrade_start < end:
                rows[-1]["status"] = "churned"
                rows[-1]["ended_at"] = upgrade_start.isoformat()
                rows.append(
                    {
                        "subscription_id": str(uuid4()),
                        "account_id": acc["account_id"],
                        "plan_id": higher,
                        "status": "active",
                        "mrr_cents": PLAN_PRICES[higher],
                        "started_at": upgrade_start.isoformat(),
                        "ended_at": None,
                        "billing_interval": np.random.choice(BILLING, p=[0.7, 0.3]),
                    }
                )
    return pd.DataFrame(rows)


def generate_usage_events(subscriptions: pd.DataFrame, end: datetime, intensity_scale: float) -> pd.DataFrame:
    rows = []
    for _, sub in subscriptions.iterrows():
        s = datetime.fromisoformat(str(sub["started_at"]))
        e = datetime.fromisoformat(str(sub["ended_at"])) if pd.notna(sub["ended_at"]) else end
        active_days = max((e - s).days, 1)
        intensity = intensity_scale + 0.08 * int(sub["plan_id"])
        n_events = max(int(active_days * intensity), 1)
        for _ in range(n_events):
            ts = s + timedelta(
                days=int(np.random.randint(0, active_days)),
                hours=int(np.random.randint(0, 24)),
            )
            if ts > end:
                continue
            rows.append(
                {
                    "event_id": str(uuid4()),
                    "account_id": sub["account_id"],
                    "feature_key": np.random.choice(FEATURES),
                    "event_ts": ts.isoformat(),
                    "event_count": int(np.random.randint(1, 6)),
                }
            )
    return pd.DataFrame(rows)


def generate_tickets(accounts: pd.DataFrame, end: datetime) -> pd.DataFrame:
    rows = []
    for _, acc in accounts.iterrows():
        n_tickets = int(np.random.poisson(2))
        signup = datetime.fromisoformat(acc["signup_date"])
        window = max((end - signup).days, 1)
        for _ in range(n_tickets):
            created = signup + timedelta(days=int(np.random.randint(0, window)))
            status = np.random.choice(["open", "resolved", "closed"], p=[0.1, 0.5, 0.4])
            resolved = None
            if status != "open":
                resolved = created + timedelta(hours=int(np.random.randint(1, 120)))
            rows.append(
                {
                    "ticket_id": str(uuid4()),
                    "account_id": acc["account_id"],
                    "created_at": created.isoformat(),
                    "resolved_at": resolved.isoformat() if resolved else None,
                    "priority": np.random.choice(TICKET_PRIORITY, p=[0.4, 0.35, 0.2, 0.05]),
                    "status": status,
                    "category": np.random.choice(TICKET_CATEGORY),
                }
            )
    return pd.DataFrame(rows)


def inject_messiness(accounts: pd.DataFrame, events: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    dup_n = int(len(accounts) * cfg.get("duplicate_account_fraction", 0))
    if dup_n:
        dups = accounts.sample(dup_n, random_state=1).copy()
        dups["created_at"] = (
            pd.to_datetime(dups["created_at"]) + pd.Timedelta(days=1)
        ).dt.strftime("%Y-%m-%dT%H:%M:%S")
        accounts = pd.concat([accounts, dups], ignore_index=True)

    if len(events):
        dup_e = int(len(events) * cfg.get("duplicate_event_fraction", 0))
        if dup_e:
            events = pd.concat(
                [events, events.sample(dup_e, random_state=2)], ignore_index=True
            )

        late_e = int(len(events) * cfg.get("late_arriving_event_fraction", 0))
        if late_e:
            idx = events.sample(late_e, random_state=3).index
            events.loc[idx, "event_ts"] = (
                pd.to_datetime(events.loc[idx, "event_ts"]) - pd.Timedelta(days=400)
            ).dt.strftime("%Y-%m-%dT%H:%M:%S")

    return accounts, events


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic SaaS CSVs for RevenueGrain.")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Path to seed_config.yml")
    p.add_argument("--accounts", type=int, default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--out", default="./data")
    args = p.parse_args()

    cfg = load_config(args.config) if os.path.exists(args.config) else {}
    mess = cfg.get("messiness") or {}

    n_accounts = args.accounts if args.accounts is not None else int(cfg.get("n_accounts", 400))
    start = datetime.fromisoformat(args.start or cfg.get("start_date", "2023-01-01"))
    end = datetime.fromisoformat(args.end or cfg.get("end_date", "2026-08-01"))
    seed = args.seed if args.seed is not None else int(cfg.get("seed", 42))
    churn_rate = float(cfg.get("churn_rate", 0.28))
    intensity_scale = float(cfg.get("usage_intensity_scale", 0.15))

    fake = _rng(seed)

    print("generating accounts...")
    accounts = generate_accounts(
        fake, n_accounts, start, end, float(mess.get("null_industry_fraction", 0.05))
    )
    print("generating subscriptions...")
    subs = generate_subscriptions(accounts, end, churn_rate=churn_rate)
    print("generating usage events...")
    events = generate_usage_events(subs, end, intensity_scale=intensity_scale)
    print("generating tickets...")
    tickets = generate_tickets(accounts, end)

    print("injecting messiness...")
    accounts, events = inject_messiness(accounts, events, mess)

    os.makedirs(args.out, exist_ok=True)
    accounts.to_csv(os.path.join(args.out, "accounts.csv"), index=False)
    subs.to_csv(os.path.join(args.out, "subscriptions.csv"), index=False)
    events.to_csv(os.path.join(args.out, "usage_events.csv"), index=False)
    tickets.to_csv(os.path.join(args.out, "tickets.csv"), index=False)

    print(
        f"done -> {args.out}\n"
        f"  accounts:      {len(accounts):>7,}\n"
        f"  subscriptions: {len(subs):>7,}\n"
        f"  usage_events:  {len(events):>7,}\n"
        f"  tickets:       {len(tickets):>7,}"
    )


if __name__ == "__main__":
    main()
