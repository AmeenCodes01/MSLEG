# Ethos: an AI analyst for ethical charity investing

> Built in one day at the **Microsoft x LSEG Generative AI Hackathon**, London, 23 October 2026.
> *Educational hackathon project. Not financial advice.*

**The challenge:** a client has **$100,000** to invest. Using public data and LLMs, build a tool that recommends where the money should go and **explains why**.

**Our client:** a **cancer research charity** investing for 5 years at moderate risk, because the investments fund research grants every year.

**What Ethos does:** a trustee describes their charity in plain English in a chat. Ethos scans 100 of the largest US companies, removes everything that conflicts with the charity's mission, reads recent news for controversies, and builds a diversified $100,000 portfolio, with a reason for every decision and a memo for the board.

<!-- Add a screenshot: save it as docs/screenshot.png and uncomment the line below -->
<!-- ![Ethos chat showing a recommendation](docs/screenshot.png) -->

---

## The headline moment

The demo policy says *"no weapons or fossil fuels"* and **never mentions tobacco**. Ethos works out on its own that a **cancer charity shouldn't profit from tobacco**, excludes it, and explains why. Exclusions come from the charity's **mission**, not a fixed list: an arts charity would keep tobacco, and an environmental charity would drop fossil fuels even if the policy didn't say so.

## How it works

```
 100 largest US companies                       (Yahoo Finance)
        │  ① AI reads the policy: mission, risk, limits, and what the mission implies
        │  ② remove conflicting industries: no prices or news fetched for them
        ▼
 ~90 companies
        │  ③ rank by 5 years of return per unit of risk (Sharpe ratio), keep the top 20
        │  ④ AI reads up to 15 recent headlines for each one: pass, flag or exclude
        ▼
 ~20 companies
        │  ⑤ re-rank: 50% steadiness (low volatility) + 50% fit with today's economy (World Bank)
        │     pick the best 5, at most 1 per industry
        ▼
 5 companies + 8 bond, cash and ESG funds = $100,000
        │  ⑥ split by risk level (moderate = 50% equities, 35% bonds, 15% cash, adjusted for interest rates)
        │  ⑦ AI writes a memo for the trustees
```

**Design principle: the AI makes the judgements, the code does the maths.** The LLM reads the policy, infers exclusions, judges news and writes the explanation. Every number (returns, volatility, rankings and dollar amounts) is computed in Python from real data, so nothing is made up.

## Example result

Policy: *"We are a cancer research charity funding early-detection research. We are investing for 5 years and will not invest in weapons or fossil fuels. We need moderate risk because we fund grants every year, and no single company should be more than 8% of the portfolio."*

| | |
|---|---|
| **Inferred from the mission** | Tobacco and alcohol |
| **Excluded (9)** | Weapons: SpaceX, GE, RTX · Fossil fuels: ExxonMobil, Chevron, Shell, TotalEnergies, ConocoPhillips · Tobacco: Philip Morris |
| **5 companies chosen** | Royal Bank of Canada · Novartis · Walmart · Caterpillar · Amphenol (5 different industries) |
| **Split** | $50,000 equities · $35,000 bonds · $15,000 cash-like Treasury funds |
| **Economy score** | 0.72 / 1 ("strong"), from World Bank data |

Results change as live data changes.

## Data sources

| Data | Source |
|---|---|
| Which companies, their industries, 5 years of daily prices | Yahoo Finance (via `yfinance`) |
| 3-month Treasury rate | FRED, US Federal Reserve |
| GDP growth, inflation, unemployment | World Bank Open Data (CC BY 4.0) |
| Recent company news | Finnhub |
| Policy reading, news judgement, memo | Azure OpenAI (provided by the hackathon) |

All sources are free and public, as suggested by the organisers. In production, LSEG's licensed prices, classifications, ESG scores and news would replace them: `get_universe`, `get_profiles`, `get_prices` and `get_news` in `backend/pipeline.py` are the functions to swap.

## Tech stack

Python · pandas · NumPy · Azure OpenAI · yfinance · a standard-library HTTP server (`backend/server.py`) · vanilla JavaScript, HTML and CSS chat front end. FastAPI and Streamlit versions of the backend are also included for testing.

## Run it

```sh
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env    # add the Azure OpenAI key and a free Finnhub key
python3 backend/server.py               # serves the chat and the API on http://localhost:8000
```

- **Live mode:** <http://localhost:8000>. The first run takes 1–2 minutes; set `USE_CACHE=1` in `.env` to replay saved data and AI answers instantly.
- **Sample mode:** <http://localhost:8000/?sample=1> returns a saved result with no keys or internet.
- **Tests:** `cd backend && python test_server.py && python test_pipeline.py && python -m unittest test_macro`

See **[SPEC.md](SPEC.md)** for the request and response format and how the front end and backend connect.

## Project structure

```
index.html, app.js, styles.css   chat front end
backend/server.py                serves the page and POST /api/run
backend/pipeline.py              the analyst: screening, data, ranking, allocation, memo
backend/macro.py                 World Bank economic-strength score and ranking
backend/api.py, backend/app.py   FastAPI and Streamlit alternatives
backend/sample_data/             saved example response for offline demos
```

## Team

| | Role |
|---|---|
| **Purna Satish Dasari** ([@Sat99496](https://github.com/Sat99496)) | Data pipeline and backend: data sourcing, mission-based screening, risk metrics, allocation, AI caching, API |
| **Norbert Czarnota** | Chat front end, World Bank economic score and candidate ranking |
| **Ameen** ([@AmeenCodes01](https://github.com/AmeenCodes01)) | Front end to backend bridge (`server.py`), sample mode, tests |
| **[Name]** | Finance: client definition, portfolio rationale, pitch |

## Limitations

- Returns and volatility are **historical**, not forecasts. Picking today's largest companies and looking back flatters the winners (survivorship bias).
- The economic score is a simple, transparent rule of thumb and has **not been backtested**.
- **No ESG scores** are used yet, because there's no free ESG data source.
- Each chat message is treated as a new policy; there's no follow-up conversation.

## Next steps

- Plug in **LSEG** data, including ESG scores
- Let trustees **approve or override** each exclusion before money is allocated
- **Backtest** the strategy over past years
- Host on **Azure** so any charity can use it

---

*Educational hackathon project. Not financial advice.*
