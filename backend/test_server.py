"""Checks the bridge without API keys. Run: python test_server.py"""
import json

import numpy as np
import pandas as pd

import server

brief = {"mission": "cancer research", "exclusions": ["Tobacco"], "flags": ["Workers’ rights"],
         "min_esg": 60, "risk": "Balanced", "notes": ""}
text = server.brief_to_policy(brief)
assert "We will not invest in: Tobacco." in text and "risk tolerance is moderate" in text, text

assert server.validate(brief) is None
assert server.validate({"min_esg": 500, "mission": "x"})
assert server.validate({"exclusions": "Tobacco"})
assert server.validate({})

# A pipeline result with NaN and numpy types must become valid JSON (NaN -> null).
fake = {"memo": "m", "policy": {}, "split": {}, "rate_note": None, "expected_return": np.float64(0.08),
        "rf": 0.04, "companies_scanned": 100,
        "portfolio": pd.DataFrame([{"ticker": "MSFT", "dollars": np.float64(7000), "flagged": np.bool_(False),
                                    "sharpe": np.nan}]),
        "screen": pd.DataFrame([{"ticker": "PM", "status": "excluded", "evidence": None, "url": np.nan}])}
out = json.loads(json.dumps(server.to_json(fake, brief),
                            default=lambda o: o.item() if hasattr(o, "item") else str(o), allow_nan=False))
assert out["portfolio"][0]["sharpe"] is None and out["portfolio"][0]["flagged"] is False
assert out["screen"][0]["url"] is None
assert out["notes"] and "ESG" in out["notes"][0]
print("ok")
