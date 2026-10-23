import unittest
from datetime import date

import pandas as pd

from macro import WorldBankDataError, WorldBankMacroAnalyzer, rank_candidates


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class WorldBankMacroTests(unittest.TestCase):
    def make_analyzer(self, gdp=2.0, inflation=2.0, unemployment=3.0, year=2025):
        values = {
            "NY.GDP.MKTP.KD.ZG": [(year, gdp), (year - 1, gdp - 0.5 if gdp is not None else None)],
            "FP.CPI.TOTL.ZG": [(year, inflation), (year - 1, inflation - 0.5 if inflation is not None else None)],
            "SL.UEM.TOTL.ZS": [(year, unemployment), (year - 1, unemployment + 0.2 if unemployment is not None else None)],
        }

        def get(url, params, timeout):
            code = url.rsplit("/", 1)[-1]
            observations = [
                {"date": str(observation_year), "value": value}
                for observation_year, value in values[code]
            ]
            observations.extend([
                {"date": str(year - 2), "value": None},
                {"date": "not-a-year", "value": 2},
                {"date": str(year + 10), "value": 500},
            ])
            return FakeResponse([{"pages": 1}, observations])

        return WorldBankMacroAnalyzer(get=get, today=lambda: date(2026, 10, 23))

    def test_score_is_bounded_and_strong_for_favorable_inputs(self):
        result = self.make_analyzer(gdp=6, inflation=2, unemployment=3).analyze()
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["regime"], "Strong")
        self.assertEqual(result["confidence"], "high")

    def test_score_is_bounded_and_weak_for_unfavorable_inputs(self):
        result = self.make_analyzer(gdp=-3, inflation=10, unemployment=12).analyze()
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["regime"], "Weak")
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 1)

    def test_cleans_invalid_and_future_observations(self):
        result = self.make_analyzer(gdp=2).analyze()
        self.assertEqual(result["indicators"]["gdp_growth"]["latest"]["year"], 2025)
        self.assertEqual(result["indicators"]["gdp_growth"]["latest"]["value"], 2)

    def test_missing_secondary_indicators_are_not_imputed(self):
        result = self.make_analyzer(inflation=None, unemployment=None).analyze()
        self.assertEqual(result["confidence"], "limited")
        self.assertEqual(result["score"], round((2 + 3) / 9, 4))
        self.assertEqual(set(result["components"]), {"gdp_growth"})

    def test_stale_gdp_data_returns_neutral_score(self):
        result = self.make_analyzer(gdp=-2, year=2020).analyze()
        self.assertTrue(result["stale"])
        self.assertEqual(result["score"], 0.5)
        self.assertEqual(result["regime"], "stale")

    def test_missing_gdp_is_explicit_error(self):
        def get(url, params, timeout):
            if "NY.GDP.MKTP.KD.ZG" in url:
                return FakeResponse([{"pages": 0}, []])
            return FakeResponse([{"pages": 0}, []])

        analyzer = WorldBankMacroAnalyzer(get=get, today=lambda: date(2026, 10, 23))
        with self.assertRaises(WorldBankDataError):
            analyzer.analyze()

    def test_economic_score_changes_sector_fit_in_opposite_directions(self):
        metrics = pd.DataFrame({"volatility": [0.2, 0.2]}, index=["HEALTH", "CYCLICAL"])
        profiles = {
            "HEALTH": {"sector": "Healthcare", "industry": "Drug Manufacturers"},
            "CYCLICAL": {"sector": "Industrials", "industry": "Specialty Industrial"},
        }
        candidates = [{"ticker": ticker} for ticker in metrics.index]
        weak = rank_candidates(
            candidates, metrics, profiles,
            {"status": "available", "score": 0.1, "stale": False},
        )
        strong = rank_candidates(
            candidates, metrics, profiles,
            {"status": "available", "score": 0.9, "stale": False},
        )
        self.assertEqual(weak[0]["ticker"], "HEALTH")
        self.assertEqual(strong[0]["ticker"], "CYCLICAL")
        self.assertEqual(strong[0]["macro_score"], 0.9)

    def test_stale_or_unavailable_macro_is_neutral_for_sector_ranking(self):
        metrics = pd.DataFrame({"volatility": [0.2, 0.2]}, index=["HEALTH", "CYCLICAL"])
        profiles = {
            "HEALTH": {"sector": "Healthcare", "industry": "Health"},
            "CYCLICAL": {"sector": "Industrials", "industry": "Industrials"},
        }
        candidates = [{"ticker": ticker} for ticker in metrics.index]
        for context in (
            {"status": "available", "score": 0.1, "stale": True},
            {"status": "unavailable", "score": 0.5, "stale": True},
            None,
        ):
            with self.subTest(context=context):
                ranked = rank_candidates(candidates, metrics, profiles, context)
                self.assertEqual({item["macro_fit_score"] for item in ranked}, {0.5})
                self.assertEqual({item["macro_score"] for item in ranked}, {0.5})

    def test_ranking_skips_candidates_without_valid_volatility(self):
        metrics = pd.DataFrame({"volatility": [float("nan")]}, index=["BAD"])
        ranking = rank_candidates(
            [{"ticker": "BAD"}],
            metrics,
            {"BAD": {"sector": "Healthcare"}},
            {"status": "available", "score": 0.5, "stale": False},
        )
        self.assertEqual(ranking, [])


if __name__ == "__main__":
    unittest.main()
