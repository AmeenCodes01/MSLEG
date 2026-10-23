"""Runs pipeline.run() end to end with fake data and no network or LLM. Run: python test_pipeline.py"""
import numpy as np
import pandas as pd

import pipeline as p

N = 100
TICKERS = [f"T{i:02d}" for i in range(N)]
INDUSTRY = {"T00": "Tobacco", "T01": "Aerospace & Defense"}
SECTORS = ["Healthcare", "Industrials", "Technology"]
SHORT_HISTORY = {"T02"}

rng = np.random.default_rng(0)
dates = pd.bdate_range(end="2026-10-01", periods=756)
prices = pd.DataFrame({t: 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01 + i / 5000, len(dates))))
                       for i, t in enumerate(TICKERS + list(p.FUNDS))}, index=dates)
prices.loc[prices.index[:-100], list(SHORT_HISTORY)] = np.nan

p.cached = lambda name, fn: fn()
p.parse_policy = lambda text: {"mission": "cancer research", "exclude_tags": ["tobacco", "weapons"],
                               "inferred_exclusions": [], "risk": "moderate", "max_position": 0.08, "horizon_years": 3,
                               "values_summary": text}
p.get_universe = lambda: [{"ticker": t, "name": t} for t in TICKERS]
p.get_profiles = lambda tickers, progress=None: {
    t: {"industry": INDUSTRY.get(t, f"Industry {i % 10}"), "sector": SECTORS[i % 3], "name": f"Company {t}",
        "category": None}
    for i, t in enumerate(tickers)}
p.ai_industry_screen = lambda industries, policy: {}
p.get_risk_free = lambda: 0.04
p.get_prices = lambda tickers, years=5: prices[tickers]
p.get_news = lambda t: [{"headline": f"{t} headline", "source": "x", "url": "http://x", "date": "2026-10-01"}]
p.judge_news = lambda t, name, news, policy: (
    {"verdict": "exclude", "reason": "Scandal.", "evidence": news[0]["headline"]} if t == shortlist_first[0]
    else {"verdict": "pass", "reason": "No conflict.", "evidence": None})
p.explain = lambda *a: "memo"


class FakeMacro:
    def analyze(self):
        return {"status": "available", "score": 0.8, "regime": "Strong", "stale": False, "confidence": "high"}


p.WorldBankMacroAnalyzer = FakeMacro

ranked = p.compute_metrics(prices[[t for t in TICKERS if t not in ("T00", "T01")]], 0.04, 3)
shortlist_first = list(ranked.sort_values("sharpe", ascending=False).index[:1])

out = p.run("We are a cancer charity.")
scr, port = out["screen"], out["portfolio"]
companies = scr[~scr.ticker.isin(p.FUNDS)]

assert sorted(companies.ticker) == TICKERS, "every company gets exactly one row"
assert companies.reason.notna().all()
assert set(scr[scr.ticker.isin(["T00", "T01"])].status) == {"excluded"}
assert scr.set_index("ticker").at["T02", "stage"] == "price history"
assert "3-year horizon" in scr.set_index("ticker").at["T02", "reason"]
assert scr.set_index("ticker").at[shortlist_first[0], "status"] == "excluded"
held = set(port.ticker) - set(p.FUNDS)
assert len(held) == p.MAX_STOCKS
assert set(companies[companies.ticker.isin(held)].status) <= {"included", "flagged"}
assert (companies.status == "included").sum() == p.MAX_STOCKS, "included means held"
assert out["macro_context"]["score"] == 0.8
held_rows = companies[companies.ticker.isin(held)]
assert held_rows.selection_rank.notna().all()
news_checked = companies[companies.stage == "AI news screen"]
assert len(news_checked) == p.SHORTLIST
assert port.dollars.sum() == p.BUDGET
print(companies.status.value_counts().to_dict())
print("ok")
