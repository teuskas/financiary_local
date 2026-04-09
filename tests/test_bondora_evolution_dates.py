import unittest
from datetime import datetime, timedelta

from parser_2026 import (
    compute_bondo_evo_target_dates,
    get_bondo_evo_selectable_targets,
    get_progressive_amount_targets,
)


class BondoraEvolutionDatesTest(unittest.TestCase):
    def test_compute_target_dates_from_today_for_each_unreached(self):
        base_dt = datetime(2026, 3, 12, 0, 0, 0)
        data = {
            0.40: {"mtns": -10.0, "mdtns": None},
            0.41: {"mtns": 45.0, "mdtns": 113.77},
            0.42: {"mtns": 108.0, "mdtns": 262.58},
            0.43: {"mtns": 170.0, "mdtns": 10.0},
        }

        enriched = compute_bondo_evo_target_dates(data, base_datetime=base_dt)

        self.assertTrue(enriched[0.40]["is_reached"])
        self.assertIsNone(enriched[0.40]["target_date"])

        # Ogni data è sempre base_dt + mdtns del singolo obiettivo
        self.assertEqual(enriched[0.41]["target_date"], (base_dt + timedelta(days=113.77)).date())
        self.assertEqual(enriched[0.42]["target_date"], (base_dt + timedelta(days=262.58)).date())
        self.assertEqual(enriched[0.43]["target_date"], (base_dt + timedelta(days=10.0)).date())

    def test_skip_date_when_unreached_but_missing_mdtns(self):
        base_dt = datetime(2026, 3, 12, 0, 0, 0)
        data = {
            0.50: {"mtns": 100.0, "mdtns": None},
            0.51: {"mtns": 120.0, "mdtns": 20.0},
        }

        enriched = compute_bondo_evo_target_dates(data, base_datetime=base_dt)

        self.assertFalse(enriched[0.50]["is_reached"])
        self.assertIsNone(enriched[0.50]["target_date"])
        self.assertEqual(enriched[0.51]["target_date"], (base_dt + timedelta(days=20)).date())

    def test_selectable_targets_include_only_max_reached_and_unreached(self):
        data = {
            0.40: {"is_reached": True},
            0.41: {"is_reached": True},
            0.42: {"is_reached": False},
            0.43: {"is_reached": False},
        }

        selectable = get_bondo_evo_selectable_targets(data)

        self.assertEqual(selectable, [0.41, 0.42, 0.43])

    def test_selectable_targets_fallback_when_no_reached_or_all_reached(self):
        none_reached = {
            0.50: {"is_reached": False},
            0.51: {"is_reached": False},
        }
        all_reached = {
            0.60: {"is_reached": True},
            0.61: {"is_reached": True},
        }

        self.assertEqual(get_bondo_evo_selectable_targets(none_reached), [0.50, 0.51])
        self.assertEqual(get_bondo_evo_selectable_targets(all_reached), [0.61])

    def test_progressive_amount_targets_examples(self):
        self.assertEqual(get_progressive_amount_targets(2782.0, 10.0), [2790.0, 2800.0, 2810.0, 2820.0, 2830.0])
        self.assertEqual(get_progressive_amount_targets(2782.0, 50.0), [2800.0, 2850.0, 2900.0, 2950.0, 3000.0])
        self.assertEqual(get_progressive_amount_targets(2782.0, 100.0), [2800.0, 2900.0, 3000.0, 3100.0, 3200.0])
        self.assertEqual(get_progressive_amount_targets(2782.0, 1000.0), [3000.0, 4000.0, 5000.0, 6000.0, 7000.0])

    def test_progressive_amount_targets_from_exact_multiple(self):
        self.assertEqual(get_progressive_amount_targets(2800.0, 100.0, count=4), [2900.0, 3000.0, 3100.0, 3200.0])


if __name__ == "__main__":
    unittest.main()

