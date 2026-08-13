"""
Load the generated CSVs into a BigQuery `raw` dataset.

Usage:
    python scripts/load_to_bigquery.py --project YOUR_GCP_PROJECT --dataset raw --data ./data

Auth: GOOGLE_APPLICATION_CREDENTIALS, DBT_GCP_KEYFILE, or
`gcloud auth application-default login`.
"""
from __future__ import annotations

import argparse
import os

from google.cloud import bigquery

TABLES = ["accounts", "subscriptions", "usage_events", "tickets"]


def _client(project: str) -> bigquery.Client:
    keyfile = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("DBT_GCP_KEYFILE")
    if keyfile:
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", keyfile)
    return bigquery.Client(project=project)


def ensure_dataset(client: bigquery.Client, project: str, dataset: str, location: str) -> None:
    ref = bigquery.Dataset(f"{project}.{dataset}")
    ref.location = location
    client.create_dataset(ref, exists_ok=True)
    print(f"dataset ready: {project}.{dataset}")


def load_table(client: bigquery.Client, project: str, dataset: str, data_dir: str, table: str) -> None:
    path = os.path.join(data_dir, f"{table}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing {path} — run scripts/generate_data.py first")
    table_id = f"{project}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
    )
    with open(path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)
    job.result()
    n = client.get_table(table_id).num_rows
    print(f"loaded {table_id}: {n:,} rows")


def main() -> None:
    p = argparse.ArgumentParser(description="Load RevenueGrain CSVs into BigQuery.")
    p.add_argument("--project", default=os.environ.get("DBT_GCP_PROJECT"), required=False)
    p.add_argument("--dataset", default="raw")
    p.add_argument("--data", default="./data")
    p.add_argument("--location", default="US")
    args = p.parse_args()

    if not args.project:
        raise SystemExit("--project is required (or set DBT_GCP_PROJECT)")

    client = _client(args.project)
    ensure_dataset(client, args.project, args.dataset, args.location)
    for t in TABLES:
        load_table(client, args.project, args.dataset, args.data, t)
    print("all tables loaded.")


if __name__ == "__main__":
    main()
