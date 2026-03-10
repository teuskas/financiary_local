"""CLI entry point for financiary_local.

Usage
-----
    python -m src.main [--folder /dropbox/path] [--top N]

Environment variables (can also be placed in a .env file):
    DROPBOX_ACCESS_TOKEN  – required
    DROPBOX_FOLDER_PATH   – optional, default "/"
    CSV_DATE_COLUMN       – optional, default "date"
    CSV_AMOUNT_COLUMN     – optional, default "amount"
    CSV_DESCRIPTION_COLUMN– optional, default "description"
    CSV_CATEGORY_COLUMN   – optional, default "category"
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from src.data_reader import DataReaderError, load_dataframes
from src.dropbox_client import DropboxClientError, build_client_from_env
from src.statistics import full_report


# ──────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_currency(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.2f}"


def _print_summary(summary: dict) -> None:
    date_from = summary["date_from"]
    date_to = summary["date_to"]
    period = (
        f"{date_from.strftime('%Y-%m-%d')} → {date_to.strftime('%Y-%m-%d')}"
        if date_from is not None
        else "n/a"
    )
    print("\n╔══════════════════════════════════════╗")
    print("║        FINANCIAL SUMMARY             ║")
    print("╚══════════════════════════════════════╝")
    print(f"  Period            : {period}")
    print(f"  Transactions      : {summary['transaction_count']}")
    print(f"  Total income      :  {_fmt_currency(summary['total_income'])}")
    print(f"  Total expenses    :  {_fmt_currency(summary['total_expenses'])}")
    print(f"  Net balance       :  {_fmt_currency(summary['net_balance'])}")


def _print_by_category(by_cat) -> None:
    if by_cat.empty:
        return
    print("\n── By Category ──────────────────────────")
    print(f"  {'Category':<25} {'Income':>12} {'Expenses':>12} {'Net':>12} {'Txn':>6}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")
    for cat, row in by_cat.iterrows():
        print(
            f"  {str(cat):<25} {_fmt_currency(row['income']):>12} "
            f"{_fmt_currency(row['expenses']):>12} "
            f"{_fmt_currency(row['net_balance']):>12} {int(row['count']):>6}"
        )


def _print_by_month(by_month) -> None:
    if by_month.empty:
        return
    print("\n── Monthly Breakdown ────────────────────")
    print(f"  {'Month':<10} {'Income':>12} {'Expenses':>12} {'Net':>12} {'Txn':>6}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")
    for period, row in by_month.iterrows():
        print(
            f"  {str(period):<10} {_fmt_currency(row['income']):>12} "
            f"{_fmt_currency(row['expenses']):>12} "
            f"{_fmt_currency(row['net_balance']):>12} {int(row['count']):>6}"
        )


def _print_monthly_averages(avgs: dict) -> None:
    print("\n── Monthly Averages ─────────────────────")
    print(f"  Avg income    : {_fmt_currency(avgs['avg_monthly_income'])}")
    print(f"  Avg expenses  : {_fmt_currency(avgs['avg_monthly_expenses'])}")
    print(f"  Avg net       : {_fmt_currency(avgs['avg_monthly_net'])}")


def _print_top_expenses(top, n: int) -> None:
    if top.empty:
        return
    print(f"\n── Top {n} Expenses ──────────────────────")
    cols = ["date", "amount", "description", "category"]
    visible = [c for c in cols if c in top.columns]
    header = (
        f"  {'Date':<12} {'Amount':>12}"
        + (f"  {'Description':<30}" if "description" in visible else "")
        + (f"  {'Category':<20}" if "category" in visible else "")
    )
    print(header)
    separator = f"  {'-'*12} {'-'*12}"
    if "description" in visible:
        separator += f"  {'-'*30}"
    if "category" in visible:
        separator += f"  {'-'*20}"
    print(separator)
    for _, row in top.iterrows():
        line = f"  {str(row['date'].date()):<12} {_fmt_currency(row['amount']):>12}"
        if "description" in visible:
            desc = str(row.get("description", ""))[:29]
            line += f"  {desc:<30}"
        if "category" in visible:
            cat = str(row.get("category", ""))[:19]
            line += f"  {cat:<20}"
        print(line)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Compute financial statistics from CSV files stored in Dropbox."
    )
    parser.add_argument(
        "--folder",
        default=os.environ.get("DROPBOX_FOLDER_PATH", "/"),
        help="Dropbox folder to scan for CSV files (default: %(default)s).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of top expenses to display (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    try:
        print(f"Connecting to Dropbox …")
        client = build_client_from_env()

        print(f"Scanning '{args.folder}' for CSV files …")
        csv_items = list(client.iter_csv_contents(args.folder))
        if not csv_items:
            print("No CSV files found. Nothing to do.", file=sys.stderr)
            return 1

        print(f"Found {len(csv_items)} CSV file(s). Loading data …")
        df = load_dataframes(csv_items)

        if df.empty:
            print("No valid financial records found.", file=sys.stderr)
            return 1

        print(f"Loaded {len(df)} transactions. Computing statistics …")
        report = full_report(df)

    except (DropboxClientError, DataReaderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_summary(report["summary"])
    _print_by_category(report["by_category"])
    _print_by_month(report["by_month"])
    _print_monthly_averages(report["monthly_averages"])
    _print_top_expenses(report["top_expenses"], args.top)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
