# Ethos: how the frontend and backend connect

The user pastes their charity's investment policy into the chat (or clicks an example). The page sends that text to `POST /api/run`. `backend/server.py` passes it to `pipeline.run()`, where the LLM turns it into structured JSON rules and the pipeline screens, checks news, allocates and explains. The result comes back as JSON, and the chat shows it with a reason for every company. There is no separate confirm step: the chat shows how the AI read the policy as part of the result, and the right-hand panel fills in from it.

```
chat text --POST /api/run {"policy": "..."}--> backend/server.py --> pipeline.run(policy)
                                                                       |  parse_policy: LLM -> JSON rules
                                                                       |  industry screen -> prices -> rank
                                                                       |  news check (LLM, JSON) -> allocate
                                                                       |  memo (LLM, markdown)
chat <------------------------------- JSON result ---------------------'
```

## Run it

```sh
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env     # fill in the hackathon Azure key, and Finnhub for news
python3 backend/server.py                # serves the page and the API on http://localhost:8000
```

- **Sample mode:** open <http://localhost:8000/?sample=1>. Any policy returns `backend/sample_data/sample_response.json` instantly, with no keys or packages. Use this for frontend work.
- **Live mode:** open <http://localhost:8000>. A first run takes a few minutes; later runs reuse `backend/cache/`. Set `USE_CACHE=1` in `.env` for the demo so bad wifi can't break it.
- **Checks (no keys needed):** `cd backend && python test_server.py && python test_pipeline.py`.

The server only serves `index.html`, `app.js` and `styles.css`; every other path, including `.env`, returns 404.

Purna's `backend/api.py` (FastAPI, `POST /api/analyse` on port 8001, see `backend/API.md`) takes the same request but returns a different response shape. **The chat uses `server.py`.**

## Request

`POST /api/run` (add `?sample=1` for the canned response)

```json
{ "policy": "We are a cancer research charity... We will not invest in weapons... moderate risk... no more than 8% in one company." }
```

`policy` must be a non-empty string under 20,000 characters. Documents are not read: paste the text.

## What the LLM returns from the policy

`parse_policy` in `pipeline.py` uses JSON mode, and code then cleans the result:

```json
{
  "mission": "cancer research",
  "exclude_tags": ["tobacco", "weapons"],
  "inferred_exclusions": [{"theme": "tobacco", "reason": "Tobacco causes cancer..."}],
  "risk": "low | moderate | high",
  "max_position": 0.08,
  "values_summary": "one sentence used to judge industries and news"
}
```

`risk` falls back to `moderate` if it's invalid, and `max_position` is clamped to 2–25%.

## Response

```json
{
  "sample": false,
  "memo": "markdown memo for trustees",
  "policy": { "...": "as above" },
  "portfolio": [{"ticker": "MSFT", "name": "...", "industry": "...", "asset_class": "equity", "weight": 0.07, "dollars": 7000, "flagged": false, "annual_return": 0.16, "volatility": 0.23, "max_drawdown": -0.21, "sharpe": 0.52}],
  "screen": [{"ticker": "PM", "name": "...", "industry": "Tobacco", "status": "excluded", "stage": "industry screen (no data used)", "reason": "...", "evidence": null, "url": null}],
  "split": {"equity": 0.5, "bond": 0.35, "cash": 0.15},
  "rate_note": "string or null",
  "expected_return": 0.081,
  "risk_free_rate": 0.042,
  "companies_scanned": 100,
  "notes": ["No ESG scores were used: the backend has no ESG data source yet."]
}
```

- `portfolio`: one row per holding; `dollars` sums to 100,000. Flagged holdings are held at half weight.
- `screen`: **exactly one row per scanned company, each with a `reason`**, plus one row per fund (`stage: "fund"`). `status` is:
    - `included`: held in the portfolio
    - `flagged`: held at half weight because of a news concern
    - `excluded`: dropped by the industry screen or the news check
    - `not_selected`: allowed, but not picked (`stage` says why: `price history`, `risk ranking`, or `AI news screen` when the portfolio was already full)
- Optional `screen` fields: `rank` and `ranked_of` (position on return per unit of risk), `news_checked` (number of headlines read). `evidence` is the headline the AI relied on; the pipeline drops it if it isn't one of the real headlines.
- `notes`: things the user should know weren't checked. If no news came back for any company, a note says so and points at `FINNHUB_API_KEY`.
- Missing numbers are `null`, never `NaN`. Errors are `400` or `500` with `{"error": "..."}`, shown in the chat.

## What the chat shows

1. How the AI read the policy, and any exclusions it inferred from the mission
2. The funnel: scanned, excluded, flagged, not chosen, chosen, funds
3. The holdings table with a **Why chosen** column, built in code from rank and news-check counts
4. Excluded and flagged companies, each with its reason and evidence headline
5. A "See why the other N weren't chosen" accordion with every `not_selected` company
6. The memo

## Who owns what

| File | Owner | Notes |
| --- | --- | --- |
| `index.html`, `app.js`, `styles.css` | Norbert | `runAnalysis()`, `resultMarkdown()`, `appendNotChosen()` and `fillProfile()` in `app.js` are the bridge |
| `backend/pipeline.py`, `backend/app.py`, `backend/api.py` | Purna | `app.py` is a separate Streamlit test page |
| `backend/server.py`, `backend/sample_data/`, `backend/test_*.py` | Ameen | the bridge |

Change the request or response shape only by updating this file in the same PR.

## Known gaps

1. **ESG** isn't used: there's no ESG data source.
2. **Data** comes from Yahoo Finance, Finnhub and FRED, not LSEG. `get_universe`, `get_profiles`, `get_prices` and `get_news` in `pipeline.py` are the functions to swap.
3. **No follow-up chat:** every message is treated as a new policy and re-runs the analysis.
4. **Attachments** are listed by name only; their contents are not sent.
