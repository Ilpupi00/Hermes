"""Submit a CSV to a running Hermes Control Room for a manual smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one CSV job to the Hermes Control Room."
    )
    parser.add_argument("csv", type=Path, help="Path to a UTF-8 CSV file.")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Control Room base URL (default: %(default)s).",
    )
    parser.add_argument(
        "--model-id",
        type=int,
        default=1,
        help="Database ID of the model to use (default: %(default)s).",
    )
    parser.add_argument(
        "--prompt",
        default="Analizza il contenuto della riga.",
        help="Prompt submitted with the job.",
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--chunk-size", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = args.csv.expanduser().resolve()

    if not csv_path.is_file():
        raise SystemExit(f"CSV non trovato: {csv_path}")
    if csv_path.suffix.lower() != ".csv":
        raise SystemExit(f"Il file deve avere estensione .csv: {csv_path}")

    endpoint = f"{args.base_url.rstrip('/')}/api/upload"
    form_data = {
        "id_modello": str(args.model_id),
        "prompt": args.prompt,
        "temperatura": str(args.temperature),
        "max_tokens": str(args.max_tokens),
        "chunk_size": str(args.chunk_size),
    }

    with csv_path.open("rb") as csv_file:
        response = requests.post(
            endpoint,
            data=form_data,
            files={"file": (csv_path.name, csv_file, "text/csv")},
            timeout=30,
        )

    print(f"HTTP {response.status_code}")
    try:
        print(response.json())
    except requests.JSONDecodeError:
        print(response.text)

    response.raise_for_status()


if __name__ == "__main__":
    main()
