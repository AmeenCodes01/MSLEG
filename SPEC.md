# Ethos: how the frontend and backend connect

The user pastes their charity's investment policy into the chat (or clicks an example). The page sends that text to `POST /api/run`. `backend/server.py` passes it to `pipeline.run()`, where the LLM turns it into structured JSON rules and the pipeline screens, checks news, allocates and explains. The result comes back as JSON, and the chat shows it with a reason for every company. There is no separate confirm step: the chat shows how the AI read the policy as part of the result, and the right-hand panel fills in from it.

```
chat text --POST /api/run {"policy": "..."}--> backend/server.py --> pipeline.run(policy)
                                                                       |  parse_policy: LLM -> JSON rules
                                                                       |  industry screen -> prices -> Sharpe rank
                                                                       |  news check top 20 (LLM, JSON)
                                                                       |  World Bank macro re-rank -> pick 12 -> allocate
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
  "horizon_years": 5,
  "values_summary": "one sentence used to judge industries and news"
}
```

`risk` falls back to `moderate` if it's invalid, `max_position` is clamped to 2–25%, and `horizon_years` (default 5) is clamped to 3–10. The horizon sets how many years of prices are used; a company needs 90% of that history to be ranked.

## Response

```json
{
  "sample": false,
  "memo": "markdown memo for trustees",
  "policy": { "...": "as above" },
  "portfolio": [{"ticker": "MSFT", "name": "...", "industry": "...", "asset_class": "equity", "weight": 0.07, "dollars": 7000, "flagged": false, "annual_return": 0.16, "volatility": 0.23, "max_drawdown": -0.21, "sharpe": 0.52}],
  "screen": [{"ticker": "PM", "name": "...", "industry": "Tobacco", "status": "excluded", "stage": "industry screen (no data used)", "reason": "...", "evidence": null, "url": null}],
  "split": {"equity": 0.5, "bond": 0.35, "cash": 0.15},
  "macro_context": {"status": "available", "score": 0.72, "regime": "Strong", "stale": false, "components": {"gdp_growth": {"raw_value": 2.2, "observation_year": 2025}}},
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
- Optional `screen` fields: `rank` and `ranked_of` (position on return per unit of risk), `news_checked` (number of headlines read). Companies that passed the news check also get `selection_rank`, `selection_of`, `sector`, `volatility_score` (1 = calmest), `macro_fit_score`, `ranking_score` and `macro_fit_reason`. `evidence` is the headline the AI relied on; the pipeline drops it if it isn't one of the real headlines.
- `notes`: things the user should know weren't checked. If no news came back for any company, a note says so and points at `FINNHUB_API_KEY`.
- Missing numbers are `null`, never `NaN`. Errors are `400` or `500` with `{"error": "..."}`, shown in the chat.

## How the World Bank data changes the picks

`backend/macro.py` (Norbert) fetches US real GDP growth, inflation and unemployment from the World Bank and turns them into an economic-strength score from 0 to 1 (GDP 50%, inflation 25%, unemployment 25%). The top 20 companies by Sharpe ratio are news-checked; the survivors are re-ranked on **50% lower volatility + 50% sector fit with the economy**:

- cyclical sectors (industrials, financial services, consumer cyclical, real estate, basic materials) score = the macro score
- defensive sectors (healthcare, consumer defensive, utilities) score = 1 − the macro score
- other sectors (technology, energy, communication services) score 0.5

The top 12 by that combined score are picked; there is no per-industry limit. The macro data does **not** change exclusions or dollar amounts. If the World Bank is unreachable or its data is over 4 years old, every company gets a neutral 0.5. The score is an unvalidated heuristic, not a forecast.

## What the chat shows

1. How the AI read the policy, and any exclusions it inferred from the mission
2. The funnel: scanned, excluded, flagged, not chosen, chosen, funds
3. The economy line: World Bank figures, the strength score, and how it was used
4. The holdings table with a **Why chosen** column, built in code from rank, news-check counts and the final macro ranking
5. Excluded and flagged companies, each with its reason and evidence headline
6. A "See why the other N weren't chosen" accordion with every `not_selected` company
7. The memo

## Who owns what

| File | Owner | Notes |
| --- | --- | --- |
| `index.html`, `app.js`, `styles.css` | Norbert | `runAnalysis()`, `resultMarkdown()`, `appendNotChosen()` and `fillProfile()` in `app.js` are the bridge |
| `backend/macro.py`, `backend/test_macro.py` | Norbert | World Bank score and candidate ranking |
| `backend/pipeline.py`, `backend/app.py`, `backend/api.py` | Purna | `app.py` is a separate Streamlit test page |
| `backend/server.py`, `backend/sample_data/`, `backend/test_*.py` | Ameen | the bridge |

Change the request or response shape only by updating this file in the same PR.

## Known gaps

1. **ESG** isn't used: there's no ESG data source.
2. **Data** comes from Yahoo Finance, Finnhub and FRED, not LSEG. `get_universe`, `get_profiles`, `get_prices` and `get_news` in `pipeline.py` are the functions to swap.
3. **No follow-up chat:** every message is treated as a new policy and re-runs the analysis.
4. **Attachments** are listed by name only; their contents are not sent.
