"""
Web API so the front end can call the AI analyst.
Run:  uvicorn api:app --port 8001 --reload
Docs: http://localhost:8001/docs  (try the endpoint in the browser)
"""
import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import run

app = FastAPI(title="Ethical Charity AI Analyst API")

# Let the front end (served from another port, e.g. localhost:8000) call this API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AnalyseRequest(BaseModel):
    policy: str


def _clean(records):
    """Turn NaN into null so the response is valid JSON."""
    return [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
            for r in records]


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyse")
def analyse(req: AnalyseRequest):
    if not req.policy.strip():
        raise HTTPException(400, "policy text is empty")
    try:
        res = run(req.policy)
    except Exception as e:  # surface a readable error to the front end
        raise HTTPException(500, f"{type(e).__name__}: {e}")

    port, scr = res["portfolio"], res["screen"]
    news = scr[scr.stage == "AI news screen"]
    return {
        "policy": res["policy"],                       # mission, exclusions (stated + inferred), risk, cap
        "summary": {
            "budget": 100000,
            "companies_scanned": res["companies_scanned"],
            "excluded_count": int((scr.status == "excluded").sum()),
            "risk_free_rate": res["rf"],
            "horizon_years": res["policy"].get("horizon_years", 5),
            "historical_return_estimate": res["expected_return"],
            "rate_note": res["rate_note"],
        },
        "allocation_by_class": {k: round(v, 4) for k, v in res["split"].items()},
        "holdings": _clean(port[["ticker", "name", "industry", "asset_class", "dollars", "weight",
                                 "annual_return", "volatility", "max_drawdown", "flagged"]]
                           .round(4).to_dict("records")),
        "exclusions": _clean(scr[scr.status.isin(["excluded", "flagged"])]
                             [["ticker", "name", "industry", "status", "stage", "reason", "evidence", "url"]]
                             .to_dict("records")),
        "news_check": _clean(news.reindex(columns=["ticker", "name", "industry", "headlines", "status",
                                                   "reason", "evidence", "url"]).to_dict("records")),
        "memo_markdown": res["memo"],
    }
