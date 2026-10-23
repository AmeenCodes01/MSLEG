# Backend API (for the front end)

## Run the backend

```sh
cd backend
source .venv/bin/activate        # or create it: python3 -m venv .venv && pip install -r requirements.txt
uvicorn api:app --port 8001 --reload
```

Needs a `backend/.env` with the keys (ask Satish; never commit it).
Interactive docs to try it in the browser: <http://localhost:8001/docs>

## Endpoint

`POST http://localhost:8001/api/analyse`

Request:

```json
{ "policy": "We are a cancer research charity... no weapons... moderate risk... max 8% per company." }
```

The first call can take 2–5 minutes (it scans 100 companies and reads news). Show a loading state.
Set `USE_CACHE=1` in `.env` after one good run to make repeat calls fast and Wi-Fi-proof.

Response (shape):

```json
{
  "policy": {
    "mission": "Cancer research and early detection",
    "exclude_tags": ["alcohol", "tobacco", "weapons"],
    "inferred_exclusions": [{ "theme": "tobacco", "reason": "Tobacco causes cancer..." }],
    "risk": "moderate", "max_position": 0.08, "values_summary": "..."
  },
  "summary": {
    "budget": 100000, "companies_scanned": 100, "excluded_count": 4,
    "risk_free_rate": 0.042, "historical_return_estimate": 0.33, "rate_note": "...",
    "news_review_candidate_cap": 20, "economic_strength_score": 0.61
  },
  "macro_context": {
    "status": "available", "source": "World Bank Open Data API",
    "country_code": "USA", "score": 0.61, "confidence": "high",
    "regime": "Mixed", "stale": false,
    "indicators": {
      "gdp_growth": { "latest": { "year": 2025, "value": 2.1 } },
      "inflation": { "latest": { "year": 2025, "value": 3.0 } },
      "unemployment": { "latest": { "year": 2025, "value": 4.2 } }
    },
    "methodology": "...", "source_urls": { "gdp_growth": "https://api.worldbank.org/..." }
  },
  "candidate_ranking": [
    {
      "selection_rank": 1, "ticker": "EXAMPLE", "macro_score": 0.61,
      "macro_fit_score": 0.61, "volatility_score": 0.80,
      "ranking_score": 0.705, "selected": true,
      "macro_fit_reason": "Cyclical sector proxy; ..."
    }
  ],
  "allocation_by_class": { "equity": 0.5, "bond": 0.35, "cash": 0.15 },
  "holdings": [
    { "ticker": "SUSB", "name": "...", "industry": "Short-Term Bond", "asset_class": "bond",
      "dollars": 18692, "weight": 0.1869, "annual_return": 0.04, "volatility": 0.024,
      "max_drawdown": -0.016, "flagged": false }
  ],
  "exclusions": [
    { "ticker": "PM", "name": "Philip Morris", "industry": "Tobacco", "status": "excluded",
      "stage": "industry screen (no data used)", "reason": "...", "evidence": null, "url": null }
  ],
  "news_check": [
    { "ticker": "RY", "name": "Royal Bank of Canada", "industry": "Banks - Diversified",
      "headlines": 15, "status": "included", "reason": "Routine business news...",
      "evidence": null, "url": null }
  ],
  "memo_markdown": "## 1) Recommendation\n..."
}
```

Screening statuses include `included`, `flagged`, `excluded`, and `not selected` (ethics-cleared but outside the final portfolio shortlist). `memo_markdown` is Markdown (the chat already renders Markdown).

The macro `score` is a descriptive 0–1 heuristic from annual US GDP growth (50%), inflation (25%), and unemployment (25%). Missing indicators are omitted and remaining weights renormalized; stale GDP data (>4 years) yields a neutral score of 0.5. On the candidate pool that has passed industry and news screening, the ranking combines normalized lower volatility (50%) and broad sector/macro fit (50%). Cyclical sector fit follows the macro score; defensive sector fit follows its inverse; unclassified sectors receive 0.5. This is not a probability, forecast, company revenue exposure, or validated recommendation. The news-review budget is limited to 20 companies, preselected by historical Sharpe, before the final ranking.

## Example call from `app.js`

```js
async function analyse(policyText) {
  const res = await fetch("http://localhost:8001/api/analyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy: policyText }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}
```

Errors come back as HTTP 400/500 with `{ "detail": "message" }`.
Health check: `GET http://localhost:8001/api/health` → `{ "ok": true }`.
