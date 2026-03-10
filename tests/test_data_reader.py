"""Tests for src.data_reader."""

import warnings

import pandas as pd
import pytest

from src.data_reader import DataReaderError, load_dataframes, parse_csv


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _csv(content: str) -> bytes:
    return content.strip().encode("utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# parse_csv
# ──────────────────────────────────────────────────────────────────────────────

class TestParseCsv:
    def test_basic_parse(self):
        raw = _csv("""
date,amount,description,category
2024-01-05,100.00,Salary,income
2024-01-10,-20.50,Groceries,food
""")
        df = parse_csv(raw)
        assert len(df) == 2
        assert list(df.columns) >= ["date", "amount", "description", "category"]
        assert df["amount"].iloc[0] == pytest.approx(100.00)
        assert df["amount"].iloc[1] == pytest.approx(-20.50)

    def test_date_parsing(self):
        raw = _csv("""
date,amount
2024-03-15,50.00
""")
        df = parse_csv(raw)
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert df["date"].iloc[0].year == 2024
        assert df["date"].iloc[0].month == 3

    def test_sorted_by_date(self):
        raw = _csv("""
date,amount
2024-03-01,10.00
2024-01-01,20.00
2024-02-01,-5.00
""")
        df = parse_csv(raw)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_missing_required_column_raises(self):
        raw = _csv("""
description,category
Salary,income
""")
        with pytest.raises(DataReaderError, match="missing required columns"):
            parse_csv(raw)

    def test_unparseable_amount_dropped_with_warning(self):
        raw = _csv("""
date,amount
2024-01-01,not_a_number
2024-01-02,50.00
""")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df = parse_csv(raw)
        assert len(df) == 1
        assert df["amount"].iloc[0] == pytest.approx(50.00)
        assert any("dropped" in str(warning.message).lower() for warning in w)

    def test_empty_csv_raises(self):
        with pytest.raises(DataReaderError):
            parse_csv(_csv(""))

    def test_whitespace_column_names_normalised(self):
        raw = _csv("""
 Date , Amount , Description
2024-06-01,200.00,Test
""")
        df = parse_csv(raw)
        assert "date" in df.columns
        assert "amount" in df.columns

    def test_no_optional_columns(self):
        raw = _csv("""
date,amount
2024-06-01,300.00
""")
        df = parse_csv(raw)
        assert "date" in df.columns
        assert "amount" in df.columns

    def test_dayfirst_date_format(self):
        raw = _csv("""
date,amount
05/01/2024,42.00
""")
        df = parse_csv(raw)
        assert df["date"].iloc[0].year == 2024


# ──────────────────────────────────────────────────────────────────────────────
# load_dataframes
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadDataframes:
    def test_combines_multiple_files(self):
        csv1 = _csv("""
date,amount
2024-01-01,100.00
""")
        csv2 = _csv("""
date,amount
2024-02-01,-30.00
""")
        df = load_dataframes([("file1.csv", csv1), ("file2.csv", csv2)])
        assert len(df) == 2

    def test_sorted_across_files(self):
        csv1 = _csv("""
date,amount
2024-03-01,10.00
""")
        csv2 = _csv("""
date,amount
2024-01-01,20.00
""")
        df = load_dataframes([("a.csv", csv1), ("b.csv", csv2)])
        assert df["date"].iloc[0].month == 1

    def test_invalid_file_skipped_with_warning(self):
        valid = _csv("""
date,amount
2024-01-01,50.00
""")
        invalid = b"this is not a valid csv at all\x00\x01"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df = load_dataframes([("good.csv", valid), ("bad.csv", invalid)])
        assert len(df) == 1

    def test_empty_iterable_returns_empty_dataframe(self):
        df = load_dataframes([])
        assert df.empty
        assert "date" in df.columns
        assert "amount" in df.columns
