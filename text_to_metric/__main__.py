"""Allow `python -m text_to_metric "What was NRR last quarter?"`."""
from __future__ import annotations

import sys

from .query_builder import QueryBuilder


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What was net revenue retention by month in 2025?"
    print(QueryBuilder().build(question))


if __name__ == "__main__":
    main()
