"""Tests for src.statistics."""

import pandas as pd
import pytest

from src.statistics import (
    StatisticsError,
    by_category,
    by_month,
    full_report,
    monthly_averages,
    overall_summary,
    top_expenses,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """A realistic multi-month, multi-category DataFrame."""
    data = {
        "date": pd.to_datetime(
            [
                "2024-01-05",
                "2024-01-10",
                "2024-01-15",
                "2024-02-03",
                "2024-02-20",
                "2024-03-01",
            ]
        ),
        "amount": [1500.00, -200.00, -50.00, 1500.00, -300.00, -100.00],
        "description": ["Salary", "Rent", "Groceries", "Salary", "Utilities", "Groceries"],
        "category": ["income", "housing", "food", "income", "utilities", "food"],
    }
    return pd.DataFrame(data)


@pytest.fixture()
def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "amount"])


# ──────────────────────────────────────────────────────────────────────────────
# overall_summary
# ──────────────────────────────────────────────────────────────────────────────

class TestOverallSummary:
    def test_basic_values(self, sample_df):
        s = overall_summary(sample_df)
        assert s["total_income"] == pytest.approx(3000.00)
        assert s["total_expenses"] == pytest.approx(-650.00)
        assert s["net_balance"] == pytest.approx(2350.00)
        assert s["transaction_count"] == 6

    def test_date_range(self, sample_df):
        s = overall_summary(sample_df)
        assert s["date_from"] == pd.Timestamp("2024-01-05")
        assert s["date_to"] == pd.Timestamp("2024-03-01")

    def test_empty_dataframe(self, empty_df):
        s = overall_summary(empty_df)
        assert s["total_income"] == 0.0
        assert s["total_expenses"] == 0.0
        assert s["net_balance"] == 0.0
        assert s["transaction_count"] == 0
        assert s["date_from"] is None

    def test_missing_column_raises(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"])})
        with pytest.raises(StatisticsError):
            overall_summary(df)

    def test_all_income(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "amount": [100.0, 200.0],
            }
        )
        s = overall_summary(df)
        assert s["total_expenses"] == 0.0
        assert s["net_balance"] == pytest.approx(300.0)

    def test_all_expenses(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "amount": [-500.0],
            }
        )
        s = overall_summary(df)
        assert s["total_income"] == 0.0
        assert s["net_balance"] == pytest.approx(-500.0)


# ──────────────────────────────────────────────────────────────────────────────
# by_category
# ──────────────────────────────────────────────────────────────────────────────

class TestByCategory:
    def test_groups_correctly(self, sample_df):
        result = by_category(sample_df)
        assert "income" in result.index
        assert "housing" in result.index
        assert "food" in result.index

    def test_income_category_values(self, sample_df):
        result = by_category(sample_df)
        assert result.loc["income", "income"] == pytest.approx(3000.00)
        assert result.loc["income", "expenses"] == pytest.approx(0.00)

    def test_food_category_values(self, sample_df):
        result = by_category(sample_df)
        assert result.loc["food", "expenses"] == pytest.approx(-150.00)

    def test_sorted_by_net_balance(self, sample_df):
        result = by_category(sample_df)
        net_values = result["net_balance"].tolist()
        assert net_values == sorted(net_values)

    def test_fallback_when_no_category_column(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "amount": [-50.0],
            }
        )
        result = by_category(df)
        assert "(uncategorised)" in result.index

    def test_null_category_becomes_uncategorised(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "amount": [-50.0],
                "category": [None],
            }
        )
        result = by_category(df)
        assert "(uncategorised)" in result.index


# ──────────────────────────────────────────────────────────────────────────────
# by_month
# ──────────────────────────────────────────────────────────────────────────────

class TestByMonth:
    def test_correct_number_of_months(self, sample_df):
        result = by_month(sample_df)
        assert len(result) == 3  # Jan, Feb, Mar

    def test_january_totals(self, sample_df):
        result = by_month(sample_df)
        jan = result.loc["2024-01"]
        assert jan["income"] == pytest.approx(1500.00)
        assert jan["expenses"] == pytest.approx(-250.00)
        assert jan["net_balance"] == pytest.approx(1250.00)

    def test_sorted_chronologically(self, sample_df):
        result = by_month(sample_df)
        periods = [str(p) for p in result.index]
        assert periods == sorted(periods)

    def test_empty_dataframe(self, empty_df):
        result = by_month(empty_df)
        assert result.empty


# ──────────────────────────────────────────────────────────────────────────────
# monthly_averages
# ──────────────────────────────────────────────────────────────────────────────

class TestMonthlyAverages:
    def test_averages(self, sample_df):
        avgs = monthly_averages(sample_df)
        # Income: 1500 Jan + 1500 Feb + 0 Mar  → avg = 1000
        assert avgs["avg_monthly_income"] == pytest.approx(1000.00)
        # Expenses: -250 Jan + -300 Feb + -100 Mar → avg ≈ -216.67
        assert avgs["avg_monthly_expenses"] == pytest.approx(-216.67, abs=0.01)

    def test_empty_dataframe(self, empty_df):
        avgs = monthly_averages(empty_df)
        assert avgs["avg_monthly_income"] == 0.0
        assert avgs["avg_monthly_expenses"] == 0.0
        assert avgs["avg_monthly_net"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# top_expenses
# ──────────────────────────────────────────────────────────────────────────────

class TestTopExpenses:
    def test_returns_only_negative(self, sample_df):
        result = top_expenses(sample_df)
        assert (result["amount"] < 0).all()

    def test_sorted_largest_outflow_first(self, sample_df):
        result = top_expenses(sample_df)
        amounts = result["amount"].tolist()
        assert amounts == sorted(amounts)

    def test_n_parameter(self, sample_df):
        result = top_expenses(sample_df, n=2)
        assert len(result) <= 2

    def test_no_expenses(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "amount": [100.0],
            }
        )
        result = top_expenses(df)
        assert result.empty


# ──────────────────────────────────────────────────────────────────────────────
# full_report
# ──────────────────────────────────────────────────────────────────────────────

class TestFullReport:
    def test_keys(self, sample_df):
        report = full_report(sample_df)
        assert set(report.keys()) == {
            "summary",
            "by_category",
            "by_month",
            "monthly_averages",
            "top_expenses",
        }

    def test_consistent_with_individual_functions(self, sample_df):
        report = full_report(sample_df)
        assert report["summary"]["net_balance"] == pytest.approx(
            overall_summary(sample_df)["net_balance"]
        )
