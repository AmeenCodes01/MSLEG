"""Clean World Bank macro data and derive an experimental 0..1 context score."""
from datetime import date
import math

import requests


WORLD_BANK_URL = "https://api.worldbank.org/v2/country/USA/indicator/{indicator}"
INDICATORS = {
    "gdp_growth": {
        "code": "NY.GDP.MKTP.KD.ZG",
        "label": "Real GDP growth",
        "unit": "% annual",
        "weight": 0.50,
    },
    "inflation": {
        "code": "FP.CPI.TOTL.ZG",
        "label": "Inflation",
        "unit": "% annual",
        "weight": 0.25,
    },
    "unemployment": {
        "code": "SL.UEM.TOTL.ZS",
        "label": "Unemployment",
        "unit": "% of labor force",
        "weight": 0.25,
    },
}
MAX_MACRO_AGE_YEARS = 4
SECTOR_GROUPS = {
    "defensive": {"consumer defensive", "healthcare", "utilities"},
    "cyclical": {
        "basic materials",
        "consumer cyclical",
        "financial services",
        "industrials",
        "real estate",
    },
}
VOLATILITY_WEIGHT = 0.50
MACRO_FIT_WEIGHT = 0.50


class WorldBankDataError(Exception):
    """Raised when the World Bank response is missing or invalid."""


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


class WorldBankMacroAnalyzer:
    """Fetch, clean, and score the latest available US annual macro indicators."""

    def __init__(self, get=requests.get, today=date.today):
        self.get = get
        self.today = today

    def analyze(self):
        indicators = {
            key: self._fetch_indicator(indicator)
            for key, indicator in INDICATORS.items()
        }
        gdp = indicators["gdp_growth"]["latest"]
        if gdp is None:
            raise WorldBankDataError("World Bank has no valid US real GDP growth observations.")

        age = self.today().year - gdp["year"]
        components = self._score_components(indicators)
        stale = age > MAX_MACRO_AGE_YEARS
        if stale:
            score = 0.5
            confidence = "low"
            regime = "stale"
            description = (
                f"The latest US GDP growth observation is from {gdp['year']} "
                f"({age} years old); macro score is neutral because the data is stale."
            )
        else:
            available_weight = sum(item["weight"] for item in components.values())
            if not available_weight:
                raise WorldBankDataError("No valid World Bank observations were available to score.")
            score = sum(item["score"] * item["weight"] for item in components.values()) / available_weight
            confidence = "high" if len(components) == len(INDICATORS) else "limited"
            regime = self._label(score)
            description = (
                f"Experimental US economic-strength score is {score:.2f}/1.00 "
                f"({regime.lower()}), based on latest available annual observations."
            )

        return {
            "status": "available",
            "source": "World Bank Open Data API",
            "country_code": "USA",
            "fetched_at": self.today().isoformat(),
            "indicators": indicators,
            "components": components,
            "score": round(_clamp(score), 4),
            "confidence": confidence,
            "regime": regime,
            "description": description,
            "gdp_observation_age_years": age,
            "stale": stale,
            "methodology": (
                "Score x is a transparent descriptive heuristic, not a probability or forecast. "
                "GDP component = clamp((real GDP growth + 3) / 9); inflation component = "
                "clamp(1 - abs(inflation - 2) / 8); unemployment component = "
                "clamp((12 - unemployment) / 9). Weighted mean: GDP 50%, inflation 25%, "
                "unemployment 25%, renormalized over available indicators. Missing indicator "
                "values are excluded, not imputed. GDP observations older than four years "
                "produce neutral x=0.5. Thresholds and weights are illustrative and unvalidated."
            ),
            "source_urls": {key: value["url"] for key, value in indicators.items()},
        }

    def _fetch_indicator(self, indicator):
        url = WORLD_BANK_URL.format(indicator=indicator["code"])
        try:
            response = self.get(
                url,
                params={"format": "json", "per_page": 20},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise WorldBankDataError(
                f"Could not fetch {indicator['label']} from the World Bank: {error}"
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise WorldBankDataError(
                f"World Bank returned invalid JSON for {indicator['label']}."
            ) from error

        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            message = None
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                messages = payload[0].get("message", [])
                if messages and isinstance(messages[0], dict):
                    message = messages[0].get("value")
            raise WorldBankDataError(
                message or f"World Bank returned an unexpected response for {indicator['label']}."
            )

        observations = []
        for record in payload[1]:
            try:
                year = int(record["date"])
                value = float(record["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if 1900 <= year <= self.today().year and math.isfinite(value):
                observations.append({"year": year, "value": value})
        observations.sort(key=lambda observation: observation["year"], reverse=True)
        return {
            **indicator,
            "latest": observations[0] if observations else None,
            "previous": observations[1] if len(observations) > 1 else None,
            "url": url,
        }

    @staticmethod
    def _label(score):
        if score >= 0.67:
            return "Strong"
        if score <= 0.33:
            return "Weak"
        return "Mixed"

    @staticmethod
    def _score_components(indicators):
        components = {}
        observations = {
            key: indicator["latest"] for key, indicator in indicators.items()
        }
        gdp = observations["gdp_growth"]
        inflation = observations["inflation"]
        unemployment = observations["unemployment"]

        if gdp is not None:
            components["gdp_growth"] = {
                "score": _clamp((gdp["value"] + 3.0) / 9.0),
                "weight": INDICATORS["gdp_growth"]["weight"],
                "observation_year": gdp["year"],
                "raw_value": gdp["value"],
            }
        if inflation is not None:
            components["inflation"] = {
                "score": _clamp(1.0 - abs(inflation["value"] - 2.0) / 8.0),
                "weight": INDICATORS["inflation"]["weight"],
                "observation_year": inflation["year"],
                "raw_value": inflation["value"],
            }
        if unemployment is not None:
            components["unemployment"] = {
                "score": _clamp((12.0 - unemployment["value"]) / 9.0),
                "weight": INDICATORS["unemployment"]["weight"],
                "observation_year": unemployment["year"],
                "raw_value": unemployment["value"],
            }
        return components


def macro_fit_for_sector(sector, macro_score, stale=False):
    """Map macro strength to a broad cyclical/defensive sector fit proxy."""
    if stale:
        return 0.5, "Neutral: macro observations are stale."

    normalized = (sector or "").strip().casefold()
    if normalized in SECTOR_GROUPS["cyclical"]:
        return round(_clamp(macro_score), 4), (
            "Cyclical sector proxy; higher macro score raises this context factor."
        )
    if normalized in SECTOR_GROUPS["defensive"]:
        return round(_clamp(1.0 - macro_score), 4), (
            "Defensive sector proxy; lower macro score raises this context factor."
        )
    return 0.5, "Neutral sector proxy; sensitivity is not classified."


def rank_candidates(candidates, metrics, profiles, macro_context):
    """Rank eligible candidates by relative volatility and sector/macro context."""
    usable_macro = (
        macro_context
        and macro_context.get("status") == "available"
        and not macro_context.get("stale")
        and isinstance(macro_context.get("score"), (int, float))
        and math.isfinite(macro_context["score"])
    )
    macro_score = _clamp(macro_context["score"]) if usable_macro else 0.5
    scored = []

    for candidate in candidates:
        ticker = candidate["ticker"]
        if ticker not in metrics.index:
            continue
        volatility = float(metrics.at[ticker, "volatility"])
        if not math.isfinite(volatility) or volatility < 0:
            continue
        profile = profiles.get(ticker, {})
        sector = profile.get("sector") or "Unknown"
        macro_fit, macro_reason = macro_fit_for_sector(
            sector, macro_score, stale=not usable_macro
        )
        scored.append({
            **candidate,
            "name": profile.get("name") or ticker,
            "sector": sector,
            "industry": profile.get("industry") or "Unknown",
            "volatility": volatility,
            "macro_score": round(macro_score, 4),
            "macro_fit_score": macro_fit,
            "macro_fit_reason": macro_reason,
        })

    if not scored:
        return []

    volatilities = [candidate["volatility"] for candidate in scored]
    minimum = min(volatilities)
    maximum = max(volatilities)
    for candidate in scored:
        if maximum == minimum:
            candidate["volatility_score"] = 0.5
        else:
            candidate["volatility_score"] = (
                maximum - candidate["volatility"]
            ) / (maximum - minimum)
        candidate["ranking_score"] = (
            VOLATILITY_WEIGHT * candidate["volatility_score"]
            + MACRO_FIT_WEIGHT * candidate["macro_fit_score"]
        )

    return sorted(
        scored,
        key=lambda candidate: (
            -candidate["ranking_score"],
            candidate["volatility"],
            candidate["ticker"],
        ),
    )
