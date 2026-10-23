"""Checks the bridge without API keys. Run: python test_server.py"""
import json

import numpy as np
import pandas as pd

import server

assert server.validate({"policy": "We are a cancer charity."}) is None
assert server.validate({"policy": "   "})
assert server.validate({"policy": 5})
assert server.validate({})
assert server.validate([])
assert server.validate({"policy": "x" * (server.MAX_POLICY_CHARS + 1)})


def fake(news_checked):
    return {"memo": "m", "policy": {}, "split": {}, "rate_note": None, "expected_return": np.float64(0.08),
            "rf": 0.04, "companies_scanned": 100,
            "portfolio": pd.DataFrame([{"ticker": "MSFT", "dollars": np.float64(7000), "flagged": np.bool_(False),
                                        "sharpe": np.nan}]),
            "screen": pd.DataFrame([{"ticker": "PM", "status": "excluded", "stage": "industry screen", "url": np.nan},
                                    {"ticker": "MSFT", "status": "included", "stage": "AI news screen",
                                     "news_checked": news_checked}])}


# A pipeline result with NaN and numpy types must become valid JSON (NaN -> null).
out = json.loads(json.dumps(server.to_json(fake(10)),
                            default=lambda o: o.item() if hasattr(o, "item") else str(o), allow_nan=False))
assert out["portfolio"][0]["sharpe"] is None and out["portfolio"][0]["flagged"] is False
assert out["screen"][0]["url"] is None
assert not any("news" in n for n in out["notes"])
assert any("FINNHUB" in n for n in server.to_json(fake(0))["notes"]), "missing news must be reported"
print("ok")
