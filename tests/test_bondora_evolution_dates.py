import unittest
from datetime import datetime, timedelta

from parser_2026 import compute_bondo_evo_target_dates


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


if __name__ == "__main__":
    unittest.main()

