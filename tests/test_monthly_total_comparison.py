import io
import unittest
from types import SimpleNamespace

import pandas as pd

from parser_2026 import (
    FILE_PATH,
    get_monthly_comparison_chart_points,
    get_monthly_comparison_total,
    get_total_monthly_comparison_data,
    get_yearly_main_tables_data,
    invalidate_cache,
)


ARCHIVE_PATH = "/me/ARCHIVIO INV/ARCHIVIO INV.xlsx"


class _FakeDropbox:
    def __init__(self, files_map: dict[str, bytes]):
        self.files_map = files_map

    def files_download(self, path: str):
        if path not in self.files_map:
            raise FileNotFoundError(path)
        return None, SimpleNamespace(content=self.files_map[path])

    def files_get_metadata(self, path: str):
        if path not in self.files_map:
            raise FileNotFoundError(path)
        return SimpleNamespace(path_display=path)

    def files_list_folder(self, _path: str):
        return SimpleNamespace(entries=[])


def _build_guadagni_sheet(platform_values: dict[str, list[float]]) -> pd.DataFrame:
    cols = 14  # col0 piattaforma + 12 mesi + totale
    df = pd.DataFrame([[None] * cols for _ in range(6)])

    months = [
        "GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO",
        "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE",
    ]

    df.iloc[0, 0] = "GUADAGNI PER PIATTAFORMA"
    for idx, month in enumerate(months, start=1):
        df.iloc[0, idx] = month
    df.iloc[0, 13] = "TOTALE"

    for row_idx, (platform, values) in enumerate(platform_values.items(), start=1):
        df.iloc[row_idx, 0] = platform
        for col_idx, value in enumerate(values, start=1):
            df.iloc[row_idx, col_idx] = value
        df.iloc[row_idx, 13] = sum(values)

    return df


def _build_full_main_sheet(guadagni_values: dict[str, list[float]]) -> pd.DataFrame:
    cols = 14  # col0 piattaforma + 12 mesi + totale
    rows = 20
    df = pd.DataFrame([[None] * cols for _ in range(rows)])
    months = [
        "GENNAIO", "FEBBRAIO", "MARZO", "APRILE", "MAGGIO", "GIUGNO",
        "LUGLIO", "AGOSTO", "SETTEMBRE", "OTTOBRE", "NOVEMBRE", "DICEMBRE",
    ]

    def write_table(start_row: int, title: str, values: dict[str, list[float]]):
        df.iloc[start_row, 0] = title
        for idx, month in enumerate(months, start=1):
            df.iloc[start_row, idx] = month
        df.iloc[start_row, 13] = "TOTALE"

        row_idx = start_row + 1
        for platform, vals in values.items():
            df.iloc[row_idx, 0] = platform
            for col_idx, value in enumerate(vals, start=1):
                df.iloc[row_idx, col_idx] = value
            df.iloc[row_idx, 13] = sum(vals)
            row_idx += 1

    invest_values = {
        "Bondora": [100.0] * 12,
        "Mintos": [50.0] * 12,
        "ReLender": [20.0] * 12,
        "SOMMA": [170.0] * 12,
    }
    inv_guad_values = {
        "Bondora": [120.0] * 12,
        "Mintos": [60.0] * 12,
        "ReLender": [25.0] * 12,
        "SOMMA": [205.0] * 12,
    }

    write_table(0, "INVESTIMENTI PER PIATTAFORMA", invest_values)
    write_table(6, "GUADAGNI PER PIATTAFORMA", guadagni_values)
    write_table(12, "INV+GUAD PER PIATTAFORMA", inv_guad_values)
    return df


def _build_workbook_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False, header=False)
    return buf.getvalue()


class MonthlyTotalComparisonTest(unittest.TestCase):
    def setUp(self):
        invalidate_cache()

    def tearDown(self):
        invalidate_cache()

    def test_merge_archive_and_current_year_with_override(self):
        archive_2025 = _build_guadagni_sheet(
            {
                "Bondora": [10.0] * 12,
                "Mintos": [5.0] * 12,
                "ReLender": [2.0] * 12,
                "SOMMA": [17.0] * 12,
            }
        )
        archive_2026 = _build_guadagni_sheet(
            {
                "Bondora": [1.0] * 12,
                "Mintos": [1.0] * 12,
                "ReLender": [1.0] * 12,
                "SOMMA": [3.0] * 12,
            }
        )
        current_2026 = _build_guadagni_sheet(
            {
                "Bondora": [20.0] * 12,
                "Mintos": [7.0] * 12,
                "ReLender": [3.0] * 12,
                "SOMMA": [30.0] * 12,
            }
        )

        dbx = _FakeDropbox(
            {
                ARCHIVE_PATH: _build_workbook_bytes({"2025": archive_2025, "2026": archive_2026}),
                FILE_PATH: _build_workbook_bytes({"2026": current_2026}),
            }
        )

        data = get_total_monthly_comparison_data(dbx)

        self.assertEqual(data["current_year"], "2026")
        self.assertEqual(data["years"], ["2025", "2026"])

        rows_by_year = {row["year"]: row for row in data["rows"]}

        jan_2025 = rows_by_year["2025"]["monthly_totals"]["GENNAIO"]
        self.assertEqual(jan_2025, 17.0)

        # Verifica override del 2026 dal file corrente (20+7+3), non dall'archivio (1+1+1)
        jan_2026 = rows_by_year["2026"]["monthly_totals"]["GENNAIO"]
        self.assertEqual(jan_2026, 30.0)

        jan_details = rows_by_year["2026"]["details"]["GENNAIO"]
        self.assertEqual(jan_details["Bondora"], 20.0)
        self.assertEqual(jan_details["Mintos"], 7.0)
        self.assertEqual(jan_details["ReLender"], 3.0)

    def test_monthly_comparison_total_supports_bondora_mintos_scope(self):
        month_details = {"Bondora": 20.0, "Mintos": 7.0, "ReLender": 3.0}

        self.assertEqual(get_monthly_comparison_total(month_details, "Totale"), 30.0)
        self.assertEqual(get_monthly_comparison_total(month_details, "Bondora + Mintos"), 27.0)
        self.assertEqual(get_monthly_comparison_total(month_details, "Qualsiasi altra vista"), 30.0)

    def test_monthly_comparison_chart_points_include_only_positive_months_in_chronological_order(self):
        comparison_data = {
            "months": ["GENNAIO", "FEBBRAIO", "MARZO"],
            "rows": [
                {
                    "year": "2025",
                    "details": {
                        "GENNAIO": {"Bondora": 0.0, "Mintos": 0.0, "ReLender": 1.0},
                        "FEBBRAIO": {"Bondora": 1.5, "Mintos": 2.5, "ReLender": 0.0},
                        "MARZO": {"Bondora": -1.0, "Mintos": 0.5, "ReLender": 0.0},
                    },
                },
                {
                    "year": "2026",
                    "details": {
                        "GENNAIO": {"Bondora": 2.0, "Mintos": 3.0, "ReLender": 0.0},
                        "FEBBRAIO": {"Bondora": 0.0, "Mintos": 0.0, "ReLender": 0.0},
                        "MARZO": {"Bondora": 4.0, "Mintos": 1.0, "ReLender": 0.0},
                    },
                },
            ],
        }

        points = get_monthly_comparison_chart_points(comparison_data, scope="Bondora + Mintos", positive_only=True)

        self.assertEqual([point["label"] for point in points], ["Feb 2025", "Gen 2026", "Mar 2026"])
        self.assertEqual([point["value"] for point in points], [4.0, 5.0, 5.0])

    def test_monthly_comparison_chart_points_can_be_filtered_by_year(self):
        comparison_data = {
            "months": ["GENNAIO", "FEBBRAIO", "MARZO"],
            "rows": [
                {
                    "year": "2025",
                    "details": {
                        "GENNAIO": {"Bondora": 1.0, "Mintos": 1.0, "ReLender": 0.0},
                        "FEBBRAIO": {"Bondora": 0.0, "Mintos": 0.0, "ReLender": 0.0},
                        "MARZO": {"Bondora": 3.0, "Mintos": 2.0, "ReLender": 0.0},
                    },
                },
                {
                    "year": "2026",
                    "details": {
                        "GENNAIO": {"Bondora": 10.0, "Mintos": 1.0, "ReLender": 0.0},
                        "FEBBRAIO": {"Bondora": 5.0, "Mintos": 2.0, "ReLender": 0.0},
                        "MARZO": {"Bondora": 0.0, "Mintos": 0.0, "ReLender": 0.0},
                    },
                },
            ],
        }

        points = get_monthly_comparison_chart_points(
            comparison_data,
            scope="Bondora + Mintos",
            year_filter="2026",
            positive_only=True,
        )

        self.assertEqual([point["label"] for point in points], ["Gen 2026", "Feb 2026"])
        self.assertEqual([point["value"] for point in points], [11.0, 7.0])

    def test_yearly_main_tables_include_only_years_with_core_platform_gains(self):
        archive_2024 = _build_full_main_sheet(
            {
                "Bondora": [0.0] * 12,
                "Mintos": [0.0] * 12,
                "ReLender": [0.0] * 12,
                "SOMMA": [0.0] * 12,
            }
        )
        archive_2025 = _build_full_main_sheet(
            {
                "Bondora": [5.0] * 12,
                "Mintos": [1.0] * 12,
                "ReLender": [0.0] * 12,
                "SOMMA": [6.0] * 12,
            }
        )
        current_2026 = _build_full_main_sheet(
            {
                "Bondora": [7.0] * 12,
                "Mintos": [2.0] * 12,
                "ReLender": [1.0] * 12,
                "SOMMA": [10.0] * 12,
            }
        )

        dbx = _FakeDropbox(
            {
                ARCHIVE_PATH: _build_workbook_bytes({"2024": archive_2024, "2025": archive_2025, "2026": archive_2025}),
                FILE_PATH: _build_workbook_bytes({"2026": current_2026}),
            }
        )

        payload = get_yearly_main_tables_data(dbx, current_year_sheet="2026")

        self.assertEqual(payload["years"], ["2025", "2026"])
        self.assertEqual(payload["default_year"], "2026")
        self.assertIn("investimenti", payload["tables_by_year"]["2026"])
        self.assertIn("guadagni", payload["tables_by_year"]["2026"])
        self.assertIn("inv_guad", payload["tables_by_year"]["2026"])

        # 2026 deve arrivare dal file corrente (override archivio)
        guadagni_2026 = payload["tables_by_year"]["2026"]["guadagni"]
        bondora_gen = float(
            guadagni_2026[guadagni_2026["Piattaforma"] == "Bondora"].iloc[0]["GENNAIO"]
        )
        self.assertEqual(bondora_gen, 7.0)


if __name__ == "__main__":
    unittest.main()

