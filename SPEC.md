# Ethos: how the frontend and backend connect

The chat page (`index.html`, `app.js`) collects a charity's brief. When the user ticks the approval box and presses **Confirm & run analysis**, the page sends the brief to `POST /api/run`. `backend/server.py` turns it into a plain-English policy, calls `pipeline.run()`, and returns JSON that the chat renders as a holdings table, an excluded/flagged list and the trustees' memo.

```
index.html + app.js  --POST /api/run {brief}-->  backend/server.py  -->  backend/pipeline.py
        ^                                                |
        '------------------ JSON result -----------------'
```

## Run it

```sh
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env     # fill in the hackathon Azure key (and Finnhub for news)
python3 backend/server.py                # serves the page and the API on http://localhost:8000
```

- **Sample mode:** open <http://localhost:8000/?sample=1>. Confirm returns `backend/sample_data/sample_response.json` instantly, with no API keys or packages needed. Use this for frontend work.
- **Live mode:** open <http://localhost:8000>. A first run takes a few minutes (it looks up 100 company profiles); later runs reuse `backend/cache/`. Set `USE_CACHE=1` in `.env` for the demo so bad wifi can't break it.
- **Checks:** `cd backend && python test_server.py` tests the bridge without keys.

The server only serves `index.html`, `app.js` and `styles.css`; every other path, including `.env`, returns 404.

## Request: what the page sends

`POST /api/run` (add `?sample=1` for the canned response)

```json
{
  "mission": "We are a cancer research charity...",
  "exclusions": ["Tobacco", "Weapons & defence"],
  "flags": ["Workers’ rights"],
  "min_esg": 60,
  "risk": "Balanced",
  "notes": ""
}
```

| Field | Type | Used for |
| --- | --- | --- |
| `mission` | string | The pipeline infers extra exclusions from it (cancer → tobacco) and judges news against it |
| `exclusions` | list of frontend labels (`exclusionOptions` in `app.js`) | Industries to drop; the LLM maps labels to the pipeline's tags |
| `flags` | list of frontend labels (`flagOptions` in `app.js`) | Controversy themes the news check looks for |
| `min_esg` | number 0–100 or `null` | **Not applied yet**: the backend has no ESG data, and the response says so in `notes` |
| `risk` | `Conservative`, `Balanced`, `Growth-oriented` or `null` | Mapped to `low`, `moderate` or `high`, which sets the stocks/bonds/cash split |
| `notes` | string | Text of attached `.txt`/`.csv` files; PDF and DOC attachments are not read yet |

The exclusion list alone isn't enough: the pipeline also needs `mission` (for inferred exclusions and judging news) and `risk` (for the split). `flags` and `notes` are optional.

The server turns the brief into policy text (`brief_to_policy` in `server.py`), so `pipeline.run(policy_text)` is unchanged. A bad brief gets `400 {"error": "..."}`; a pipeline failure gets `500 {"error": "..."}`, which the chat shows.

## Response: what the backend returns

```json
{
  "sample": false,
  "memo": "markdown memo for trustees",
  "policy": {"mission": "...", "exclude_tags": ["tobacco"], "inferred_exclusions": [], "risk": "moderate", "max_position": 0.08, "values_summary": "..."},
  "portfolio": [{"ticker": "MSFT", "name": "...", "industry": "...", "asset_class": "equity", "weight": 0.07, "dollars": 7000, "flagged": false, "annual_return": 0.16, "volatility": 0.23, "max_drawdown": -0.21, "sharpe": 0.52}],
  "screen": [{"ticker": "PM", "name": "...", "industry": "Tobacco", "status": "excluded", "stage": "industry screen (no data used)", "reason": "...", "evidence": null, "url": null}],
  "split": {"equity": 0.5, "bond": 0.35, "cash": 0.15},
  "rate_note": "string or null",
  "expected_return": 0.081,
  "risk_free_rate": 0.042,
  "companies_scanned": 100,
  "notes": ["Minimum ESG score 60 was not applied: the backend has no ESG data source yet."]
}
```

- `portfolio`: one row per holding; `dollars` sums to 100,000. `flagged` holdings are held at half weight.
- `screen`: every company the pipeline judged. `status` is `included`, `excluded` or `flagged`; `evidence` is the headline the AI relied on.
- Missing numbers are `null`, never `NaN`.

## Who owns what

| File | Owner | Notes |
| --- | --- | --- |
| `index.html`, `app.js`, `styles.css` | Norbert | `buildBrief()`, `runAnalysis()` and `resultMarkdown()` in `app.js` are the bridge |
| `backend/pipeline.py`, `backend/app.py` | Purna | `app.py` is a separate Streamlit test page |
| `backend/server.py`, `backend/sample_data/`, `backend/test_server.py` | Ameen | the bridge |

Change the request or response shape only by updating this file in the same PR.

## Known gaps

1. **ESG** is collected but not applied: there is no ESG data source.
2. **Data** comes from Yahoo Finance, Finnhub and FRED, not LSEG. `get_universe`, `get_profiles` and `get_prices` in `pipeline.py` are the functions to swap if LSEG access arrives.
3. **No follow-up chat.** After a run, messages go back to the keyword matcher. The next step is an agent with a `run_portfolio` tool that answers "why not X?" and re-runs with changed rules.
4. **Attachments:** only `.txt` and `.csv` contents are sent.
