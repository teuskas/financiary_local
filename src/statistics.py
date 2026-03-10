"""Financial statistics: compute summaries from a normalised DataFrame."""

from __future__ import annotations

import pandas as pd


class StatisticsError(Exception):
    """Raised when statistics cannot be computed."""


def _require_columns(df: pd.DataFrame, *columns: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise StatisticsError(f"DataFrame is missing required columns: {missing}")


# ---------------------------------------------------------------------------
# High-level summary
# ---------------------------------------------------------------------------

def overall_summary(df: pd.DataFrame) -> dict:
    """Return a dict with total income, expenses and net balance.

    Positive *amount* values are treated as income; negative values as
    expenses.

    Parameters
    ----------
    df:
        Normalised DataFrame produced by :mod:`src.data_reader`.

    Returns
    -------
    dict
        Keys: ``total_income``, ``total_expenses``, ``net_balance``,
        ``transaction_count``, ``date_from``, ``date_to``.
    """
    _require_columns(df, "amount", "date")
    if df.empty:
        return {
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_balance": 0.0,
            "transaction_count": 0,
            "date_from": None,
            "date_to": None,
        }

    income = df.loc[df["amount"] > 0, "amount"].sum()
    expenses = df.loc[df["amount"] < 0, "amount"].sum()
    return {
        "total_income": round(float(income), 2),
        "total_expenses": round(float(expenses), 2),
        "net_balance": round(float(income + expenses), 2),
        "transaction_count": len(df),
        "date_from": df["date"].min(),
        "date_to": df["date"].max(),
    }


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------

def by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Return income, expenses and net balance grouped by category.

    If the ``category`` column is absent, all transactions are assigned to the
    ``"(uncategorised)"`` bucket.

    Returns
    -------
    pd.DataFrame
        Indexed by category with columns ``income``, ``expenses``,
        ``net_balance``, ``count``.  Sorted by ``net_balance`` ascending
        (largest outflow first).
    """
    _require_columns(df, "amount")

    work = df.copy()
    if "category" not in work.columns:
        work["category"] = "(uncategorised)"
    else:
        work["category"] = work["category"].fillna("(uncategorised)")

    groups = work.groupby("category")["amount"]

    result = pd.DataFrame(
        {
            "income": groups.apply(lambda s: s[s > 0].sum()),
            "expenses": groups.apply(lambda s: s[s < 0].sum()),
            "count": groups.count(),
        }
    )
    result["net_balance"] = result["income"] + result["expenses"]
    result = result.sort_values("net_balance")
    result[["income", "expenses", "net_balance"]] = result[
        ["income", "expenses", "net_balance"]
    ].round(2)
    return result


# ---------------------------------------------------------------------------
# Monthly breakdown
# ---------------------------------------------------------------------------

def by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Return income, expenses and net balance grouped by calendar month.

    Returns
    -------
    pd.DataFrame
        Indexed by ``period`` (``YYYY-MM``) with columns ``income``,
        ``expenses``, ``net_balance``, ``count``.  Sorted chronologically.
    """
    _require_columns(df, "amount", "date")

    if df.empty:
        return pd.DataFrame(columns=["income", "expenses", "net_balance", "count"])

    work = df.copy()
    work["period"] = work["date"].dt.to_period("M")

    groups = work.groupby("period")["amount"]
    result = pd.DataFrame(
        {
            "income": groups.apply(lambda s: s[s > 0].sum()),
            "expenses": groups.apply(lambda s: s[s < 0].sum()),
            "count": groups.count(),
        }
    )
    result["net_balance"] = result["income"] + result["expenses"]
    result = result.sort_index()
    result[["income", "expenses", "net_balance"]] = result[
        ["income", "expenses", "net_balance"]
    ].round(2)
    return result


# ---------------------------------------------------------------------------
# Monthly averages
# ---------------------------------------------------------------------------

def monthly_averages(df: pd.DataFrame) -> dict:
    """Return average monthly income, expenses and net balance.

    Returns
    -------
    dict
        Keys: ``avg_monthly_income``, ``avg_monthly_expenses``,
        ``avg_monthly_net``.
    """
    monthly = by_month(df)
    if monthly.empty:
        return {
            "avg_monthly_income": 0.0,
            "avg_monthly_expenses": 0.0,
            "avg_monthly_net": 0.0,
        }
    return {
        "avg_monthly_income": round(float(monthly["income"].mean()), 2),
        "avg_monthly_expenses": round(float(monthly["expenses"].mean()), 2),
        "avg_monthly_net": round(float(monthly["net_balance"].mean()), 2),
    }


# ---------------------------------------------------------------------------
# Top expenses
# ---------------------------------------------------------------------------

def top_expenses(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Return the *n* largest individual expenses.

    Returns
    -------
    pd.DataFrame
        Subset of *df* with only negative-amount rows, sorted by amount
        ascending (largest outflow first), limited to *n* rows.
    """
    _require_columns(df, "amount")
    expenses_df = df.loc[df["amount"] < 0].copy()
    return expenses_df.sort_values("amount").head(n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

def full_report(df: pd.DataFrame) -> dict:
    """Compute all statistics and return them in a single dict.

    Keys
    ----
    ``summary``
        Output of :func:`overall_summary`.
    ``by_category``
        Output of :func:`by_category`.
    ``by_month``
        Output of :func:`by_month`.
    ``monthly_averages``
        Output of :func:`monthly_averages`.
    ``top_expenses``
        Output of :func:`top_expenses`.
    """
    return {
        "summary": overall_summary(df),
        "by_category": by_category(df),
        "by_month": by_month(df),
        "monthly_averages": monthly_averages(df),
        "top_expenses": top_expenses(df),
    }
