"""
Ethical Charity AI Analyst - pipeline
All company data comes from APIs, not hand-made lists:
  Yahoo Finance screener  -> which companies to consider (largest US companies)
  Yahoo Finance profiles  -> each company's official industry classification
  Yahoo Finance prices    -> return, volatility, worst fall
  FRED                    -> current interest rate
  Finnhub                 -> recent company news
Flow: policy -> universe -> industry screen -> metrics -> shortlist -> AI news screen
      -> allocation (in code) -> explanation (AI).
Educational hackathon project. Not financial advice.
"""
import os
import json
import pathlib
import datetime as dt

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from macro import MACRO_FIT_WEIGHT, VOLATILITY_WEIGHT, WorldBankDataError, WorldBankMacroAnalyzer, rank_candidates

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BUDGET = 100_000
CACHE = pathlib.Path("cache")
CACHE.mkdir(exist_ok=True)
# Set USE_CACHE=1 for the live demo so a Wi-Fi/API failure can't break it.
USE_CACHE = os.getenv("USE_CACHE", "0") == "1"

UNIVERSE_SIZE = 100      # how many of the largest US companies to scan
SHORTLIST = 20           # best risk-adjusted stocks sent to the AI news screen
MAX_STOCKS = 12          # stocks kept in the final portfolio

TAGS = ["fossil_fuels", "tobacco", "weapons", "gambling", "alcohol"]
# No fixed exclusions: what a charity avoids depends on its mission
# (a cancer charity rejects tobacco; an environmental charity rejects fossil fuels).
# Excluded companies never have their prices or news retrieved.

# Safety net: how each tag shows up in Yahoo Finance industry names (matched case-insensitively).
TAG_KEYWORDS = {
    "tobacco": ["tobacco"],
    "alcohol": ["wineries", "distiller", "brewers"],
    "fossil_fuels": ["oil & gas", "coal"],
    "weapons": ["aerospace & defense"],
    "gambling": ["gambling", "casino"],
}

# Funds are asset-class building blocks (bonds and cash can't be screened like companies).
# Their names and categories are still fetched from the API.
FUNDS = {
    "ESGU": "equity", "SUSA": "equity", "ESGV": "equity",
    "EAGG": "bond", "SUSB": "bond", "IEF": "bond",
    "SHV": "cash", "BIL": "cash",
}

SPLITS = {
    "low": {"equity": 0.30, "bond": 0.55, "cash": 0.15},
    "moderate": {"equity": 0.55, "bond": 0.35, "cash": 0.10},
    "high": {"equity": 0.75, "bond": 0.20, "cash": 0.05},
}


# ---------------------------------------------------------------- LLM client
_client = None


def _llm():
    """Azure OpenAI by default; OpenAI-compatible endpoint if OPENAI_BASE_URL is set."""
    global _client
    if _client is None:
        if os.getenv("OPENAI_BASE_URL"):
            from openai import OpenAI
            _client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"],
                             api_key=os.environ["OPENAI_API_KEY"])
        else:
            from openai import AzureOpenAI
            _client = AzureOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
    return _client


def _model():
    return os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("OPENAI_MODEL", "gpt-4o")


def llm_json(system, user):
    r = _llm().chat.completions.create(
        model=_model(),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return json.loads(r.choices[0].message.content)


def llm_text(system, user):
    r = _llm().chat.completions.create(
        model=_model(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return r.choices[0].message.content


# ---------------------------------------------------------------- cache helpers
def _load(name):
    p = CACHE / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _save(name, data):
    (CACHE / f"{name}.json").write_text(json.dumps(data, default=str, indent=2))


def cached(name, fn):
    if USE_CACHE:
        hit = _load(name)
        if hit is not None:
            return hit
    data = fn()
    _save(name, data)
    return data


# ---------------------------------------------------------------- 1. policy
def parse_policy(text):
    system = (
        "You convert a charity's investment policy into JSON rules. "
        "Exclusions come from two places: (a) what the policy states, and (b) what the charity's "
        "MISSION implies even if not stated, because investing in an industry that harms the cause "
        "it fights would conflict with its purpose (e.g. a cancer charity must not hold tobacco; "
        "an environmental charity must not hold fossil fuels; a children's charity may avoid gambling). "
        "Only infer exclusions with a direct, clear link to the mission. "
        f"Use these tags where they fit: {TAGS}; you may add other short snake_case themes. "
        'Return JSON: {"mission": "the charity\'s cause in a few words", '
        '"exclude_tags": [all excluded themes, stated and inferred], '
        '"inferred_exclusions": [{"theme": "...", "reason": "why the mission implies it"}], '
        '"risk": "low|moderate|high", '
        '"max_position": number between 0.02 and 0.25 (default 0.10), '
        '"horizon_years": whole number of years they plan to invest for (default 5), '
        '"values_summary": "one sentence describing what the charity cares about and avoids, '
        'used to judge industries and news"}'
    )
    p = llm_json(system, text)
    p["exclude_tags"] = sorted({str(t).strip().lower() for t in p.get("exclude_tags", []) if t})
    p.setdefault("inferred_exclusions", [])
    p["risk"] = p.get("risk") if p.get("risk") in SPLITS else "moderate"
    p["max_position"] = float(min(max(float(p.get("max_position", 0.10)), 0.02), 0.25))
    try:
        p["horizon_years"] = int(min(max(int(p.get("horizon_years") or 5), 3), 10))
    except (TypeError, ValueError):
        p["horizon_years"] = 5
    p.setdefault("values_summary", text)
    return p


# ---------------------------------------------------------------- 2. universe from the API
def get_universe(n=UNIVERSE_SIZE):
    """Largest US-listed companies by market value, from the Yahoo Finance screener."""
    def fetch():
        q = yf.EquityQuery("and", [
            yf.EquityQuery("eq", ["region", "us"]),
            yf.EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),  # Nasdaq and NYSE only, no OTC
            yf.EquityQuery("gt", ["intradaymarketcap", 20_000_000_000]),
        ])
        res = yf.screen(q, size=min(n, 250), sortField="intradaymarketcap", sortAsc=False)
        return [{"ticker": x["symbol"], "name": x.get("longName") or x.get("shortName") or x["symbol"]}
                for x in res.get("quotes", []) if x.get("quoteType", "EQUITY") == "EQUITY"]
    return cached("universe", fetch)


def get_profiles(tickers, progress=None):
    """Official industry and sector for each company, from Yahoo Finance.
    Profiles rarely change, so they are always reused once saved."""
    profiles = _load("profiles") or {}
    todo = [t for t in tickers if t not in profiles]
    for i, t in enumerate(todo):
        if progress:
            progress(i / max(len(todo), 1), f"Looking up industry for {t}…")
        try:
            info = yf.Ticker(t).info
            profiles[t] = {"industry": info.get("industry") or "Unknown",
                           "sector": info.get("sector") or "Unknown",
                           "name": info.get("longName") or info.get("shortName") or t,
                           "category": info.get("category")}
        except Exception:
            profiles[t] = {"industry": "Unknown", "sector": "Unknown", "name": t, "category": None}
        if i % 10 == 9:
            _save("profiles", profiles)
    _save("profiles", profiles)
    return profiles


# ---------------------------------------------------------------- 3. industry screen
def keyword_tags(industry):
    s = (industry or "").lower()
    return {tag for tag, kws in TAG_KEYWORDS.items() if any(k in s for k in kws)}


def ai_industry_screen(industries, policy):
    """AI decides which real API industry names conflict with the charity's values."""
    system = (
        "You are an ethical-investment analyst for a charity. "
        f"The charity's values: {policy['values_summary']} "
        f"The charity's mission: {policy.get('mission', '')}. "
        f"Excluded themes: {policy['exclude_tags']}. "
        "From the list of industry names provided, choose ONLY those whose main business conflicts "
        "with these values. Do not exclude industries for weak or indirect links. "
        'Return JSON: {"excluded": [{"industry": "exact name from the list", "reason": "short reason"}]}'
    )
    out = llm_json(system, json.dumps(sorted(industries)))
    valid = set(industries)
    return {x["industry"]: x.get("reason", "Conflicts with the charity's values.")
            for x in out.get("excluded", []) if x.get("industry") in valid}


# ---------------------------------------------------------------- 4. market data
def get_risk_free():
    def fetch():
        try:
            df = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO")
            return float(pd.to_numeric(df.iloc[:, 1], errors="coerce").dropna().iloc[-1]) / 100
        except Exception:
            return 0.04  # fallback
    return cached("risk_free", fetch)


def get_prices(tickers, years=5):
    """Daily prices covering the charity's investment horizon."""
    path = CACHE / f"prices_{years}y.csv"
    if USE_CACHE and path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df[[t for t in tickers if t in df.columns]]
    df = yf.download(tickers, period=f"{years}y", auto_adjust=True, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    df.to_csv(path)
    return df


def min_history_days(years):
    return int(252 * years * 0.9)  # need ~90% of the horizon to judge a company fairly


def compute_metrics(prices, rf, years=5):
    rows = {}
    for t in prices.columns:
        p = prices[t].dropna()
        if len(p) < min_history_days(years):
            continue
        r = p.pct_change().dropna()
        years = len(p) / 252
        ann_ret = (p.iloc[-1] / p.iloc[0]) ** (1 / years) - 1
        vol = r.std() * np.sqrt(252)
        rows[t] = {
            "annual_return": ann_ret,
            "volatility": vol,
            "max_drawdown": (p / p.cummax() - 1).min(),
            "sharpe": (ann_ret - rf) / vol if vol > 0 else np.nan,
        }
    return pd.DataFrame(rows).T


def get_news(ticker, days=30):
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return []
    to = dt.date.today()
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": str(to - dt.timedelta(days=days)), "to": str(to),
                    "token": key},
            timeout=15,
        )
        items = r.json() if r.ok else []
    except Exception:
        items = []
    return [{"headline": i.get("headline"), "source": i.get("source"), "url": i.get("url"),
             "date": dt.datetime.fromtimestamp(i.get("datetime", 0)).date().isoformat()}
            for i in items[:15]]


# ---------------------------------------------------------------- 5. AI news screen
def judge_news(ticker, name, headlines, policy):
    if not headlines:
        return {"verdict": "pass", "reason": "No recent controversies found in the news sample.",
                "evidence": None}
    system = (
        "You are an ethical-investment screening analyst for a charity. "
        f"The charity's values: {policy['values_summary']} "
        "Using ONLY the headlines provided, decide whether recent news shows conduct that conflicts "
        "with these values (e.g. labour abuse, environmental damage, fraud, links to excluded sectors). "
        "Routine business news is a pass. "
        'Return JSON: {"verdict": "pass|flag|exclude", "reason": "one or two sentences", '
        '"evidence": "the exact headline you relied on, or null"}'
    )
    user = f"Company: {name} ({ticker})\nHeadlines:\n" + "\n".join(
        f"- [{h['date']}] {h['headline']} ({h['source']})" for h in headlines)
    out = llm_json(system, user)
    if out.get("verdict") not in ("pass", "flag", "exclude"):
        out["verdict"] = "flag"
    if out.get("evidence") not in {h["headline"] for h in headlines}:
        out["evidence"] = None  # never show a headline the model made up
    return out


# ---------------------------------------------------------------- 6. allocation (in code, not by the LLM)
def allocate(metrics, holdings, policy, rf):
    """holdings: DataFrame with ticker, name, asset_class, kind, flagged."""
    split = dict(SPLITS[policy["risk"]])
    rate_note = None
    if rf >= 0.04:
        split["equity"] -= 0.05
        split["cash"] += 0.05
        rate_note = (f"3-month Treasury yield is {rf:.1%}, so 5% was moved from equities to cash "
                     "because cash pays a meaningful return with almost no risk.")

    info = holdings.set_index("ticker")
    weights = {}
    for cls, share in split.items():
        names = [t for t in info.index if info.at[t, "asset_class"] == cls and t in metrics.index]
        if not names:
            continue
        inv = 1 / metrics.loc[names, "volatility"].astype(float)
        inv = inv * np.array([0.5 if info.at[t, "flagged"] else 1.0 for t in names])
        weights.update((inv / inv.sum() * share).to_dict())
    w = pd.Series(weights)

    cap = policy["max_position"]
    for _ in range(20):
        stocks = [t for t in w.index if info.at[t, "kind"] == "stock"]
        over = w[stocks][w[stocks] > cap]
        if over.empty:
            break
        excess = (over - cap).sum()
        w[over.index] = cap
        recv = [t for t in w.index if info.at[t, "asset_class"] == "equity" and info.at[t, "kind"] == "fund"]
        if not recv:
            recv = [t for t in stocks if w[t] < cap]
        w[recv] += excess * w[recv] / w[recv].sum()

    w = w / w.sum()
    port = pd.DataFrame({
        "ticker": w.index,
        "name": [info.at[t, "name"] for t in w.index],
        "industry": [info.at[t, "industry"] for t in w.index],
        "asset_class": [info.at[t, "asset_class"] for t in w.index],
        "weight": w.values,
        "dollars": (w.values * BUDGET).round(0),
        "flagged": [bool(info.at[t, "flagged"]) for t in w.index],
    }).join(metrics, on="ticker").sort_values("dollars", ascending=False).reset_index(drop=True)
    port.loc[0, "dollars"] += BUDGET - port.dollars.sum()  # make rounding add up to exactly $100,000
    return port, split, rate_note, float((port.weight * port.annual_return).sum())


# ---------------------------------------------------------------- 7. explanation
def explain(policy, port, screen_df, split, rate_note, macro_context, rf, exp_ret, n_scanned):
    system = (
        "You are an investment analyst writing a short memo to a charity's trustees. "
        "You built this portfolio and you are recommending it; write confidently as its author. "
        "Use ONLY the numbers and facts provided; do not invent figures. "
        "Rules already applied in code, so present them as met: the max_position limit applies to "
        "single-company stocks only. Funds (ETFs) hold hundreds of companies, so a larger fund "
        "holding does not break it. Industry exclusions come from each company's official industry "
        "classification, so no news evidence is needed for them; only cite evidence for AI "
        "news-screen decisions. Round dollar figures to the nearest $100. "
        "Where an exclusion was inferred from the charity's mission rather than stated, say so "
        "and give the reason (from policy.inferred_exclusions). "
        "Do not mention exclusion themes that matched no companies. "
        "Mention the charity's investment horizon (policy.horizon_years) and that all return and "
        "risk figures cover that many years of history. "
        f"Up to {SHORTLIST} companies with the best historical Sharpe ratio were news-checked; those that "
        f"passed were ranked {VOLATILITY_WEIGHT:.0%} on lower relative volatility and {MACRO_FIT_WEIGHT:.0%} "
        "on how well their broad sector fits the US economic-strength score from World Bank data, "
        "with no limit per industry. The macro score is a descriptive heuristic, "
        "not a forecast, and has not been backtested; say so. Give the score, its regime and the data "
        "years. If macro data is stale or unavailable, say the macro factor was neutral. "
        "Plain English. Sections: 1) Recommendation in two sentences, "
        "2) How the $100,000 is split and why, 3) Top holdings and why each fits, "
        "4) What we excluded and why, 5) Key risks, "
        "6) One-line disclaimer: educational project, not financial advice. Under 400 words."
    )
    payload = {
        "policy": policy,
        "companies_scanned": n_scanned,
        "risk_free_rate": rf,
        "asset_class_split": split,
        "rate_adjustment": rate_note,
        "macro_context": {k: macro_context.get(k) for k in
                          ("status", "score", "regime", "confidence", "stale", "description", "components")},
        "historical_return_estimate": exp_ret,
        "holdings": port[["ticker", "name", "industry", "asset_class", "dollars", "annual_return",
                          "volatility", "max_drawdown", "flagged"]].round(4).to_dict("records"),
        "exclusions": screen_df[screen_df.status.isin(["excluded", "flagged"])][
            ["ticker", "name", "industry", "status", "stage", "reason", "evidence"]].to_dict("records"),
        "not_selected_count": int((screen_df.status == "not_selected").sum()),
    }
    return llm_text(system, json.dumps(payload, default=str))


# ---------------------------------------------------------------- run end to end
def run(policy_text, progress=None):
    step = progress or (lambda *_: None)

    step(0.02, "Reading the charity's policy…")
    policy = parse_policy(policy_text)

    step(0.05, "Fetching the largest US companies from Yahoo Finance…")
    universe = get_universe()
    profiles = get_profiles([u["ticker"] for u in universe] + list(FUNDS),
                            progress=lambda f, m: step(0.05 + 0.20 * f, m))

    step(0.26, "AI matching the policy against real industry classifications…")
    industries = {profiles[u["ticker"]]["industry"] for u in universe}
    ai_excl = ai_industry_screen(industries, policy)

    rows, allowed = [], []
    for u in universe:
        t = u["ticker"]
        prof = profiles[t]
        ind = prof["industry"]
        name = prof["name"] or u["name"]
        rule = keyword_tags(ind) & set(policy["exclude_tags"])
        base = {"ticker": t, "name": name, "industry": ind, "evidence": None, "url": None}
        if ind in ai_excl or rule:
            why = ai_excl.get(ind) or f"Industry '{ind}' falls under excluded theme: {', '.join(sorted(rule))}."
            rows.append({**base, "status": "excluded", "stage": "industry screen (no data used)",
                         "reason": why + " No prices or news were retrieved for this company."})
        else:
            allowed.append(t)

    years = policy["horizon_years"]
    step(0.32, f"Fetching interest rates and {years} years of prices…")
    rf = get_risk_free()
    step(0.34, "Fetching US economic indicators from the World Bank…")
    try:
        macro_context = cached("macro", lambda: WorldBankMacroAnalyzer().analyze())
    except WorldBankDataError as error:
        macro_context = {"status": "unavailable", "error": str(error), "score": 0.5,
                         "confidence": "none", "regime": "unavailable", "stale": True,
                         "description": f"World Bank data unavailable, so the macro factor is neutral: {error}"}
    metrics = compute_metrics(get_prices(allowed + list(FUNDS), years), rf, years)

    # Every company gets exactly one row with a reason, including the ones not picked.
    def company(t):
        return {"ticker": t, "name": profiles[t]["name"], "industry": profiles[t]["industry"],
                "evidence": None, "url": None}

    for t in allowed:
        if t not in metrics.index:
            rows.append({**company(t), "status": "not_selected", "stage": "price history",
                         "reason": f"Fewer than {min_history_days(years)} trading days of prices (90% of the "
                                   f"{years}-year horizon), so its risk can't be judged."})

    # Shortlist the best risk-adjusted stocks, then let the AI read their news.
    ranked = metrics.loc[[t for t in allowed if t in metrics.index]].sort_values("sharpe", ascending=False)
    n_ranked = len(ranked)
    shortlist = list(ranked.index[:SHORTLIST])
    for rank, t in enumerate(ranked.index[SHORTLIST:], start=SHORTLIST + 1):
        rows.append({**company(t), "status": "not_selected", "stage": "risk ranking",
                     "rank": rank, "ranked_of": n_ranked,
                     "reason": f"Ranked #{rank} of {n_ranked} on return per unit of risk "
                               f"(Sharpe {ranked.at[t, 'sharpe']:.2f}); only the top {SHORTLIST} were news-checked."})
    candidates = []
    for i, t in enumerate(shortlist):
        name = profiles[t]["name"]
        step(0.40 + 0.45 * i / max(len(shortlist), 1), f"AI reading news for {name}…")
        news = cached(f"news_{t}", lambda t=t: get_news(t))
        j = judge_news(t, name, news, policy)
        url = next((h["url"] for h in news if h["headline"] == j.get("evidence")), None)
        status = {"pass": "included", "flag": "flagged", "exclude": "excluded"}[j["verdict"]]
        rows.append({**company(t), "status": status, "stage": "AI news screen", "reason": j.get("reason"),
                     "evidence": j.get("evidence"), "url": url,
                     "rank": i + 1, "ranked_of": n_ranked, "news_checked": len(news)})
        if status != "excluded":
            candidates.append({"ticker": t, "flagged": status == "flagged"})

    # News survivors are re-ranked on lower volatility and sector fit with the economy (macro.py).
    by_ticker = {r["ticker"]: r for r in rows}
    ranking = rank_candidates(candidates, metrics, profiles, macro_context)
    chosen = []
    for pos, c in enumerate(ranking, start=1):
        row = by_ticker[c["ticker"]]
        row.update({"selection_rank": pos, "selection_of": len(ranking), "sector": c["sector"],
                    "volatility_score": round(c["volatility_score"], 3),
                    "macro_fit_score": c["macro_fit_score"], "ranking_score": round(c["ranking_score"], 3),
                    "macro_fit_reason": c["macro_fit_reason"]})
        if len(chosen) < MAX_STOCKS:
            chosen.append((c["ticker"], c["flagged"]))
            continue
        row["status"] = "not_selected"
        row["reason"] = (f"Portfolio already holds {MAX_STOCKS} stocks; combined rank #{pos} of {len(ranking)} "
                         f"on volatility and economy fit. News check: {row['reason']}")
    for c in candidates:
        if not any(r["ticker"] == c["ticker"] for r in ranking):
            by_ticker[c["ticker"]].update(status="not_selected", reason="Its volatility couldn't be measured, so it couldn't be ranked.")

    for f in FUNDS:
        rows.append({"ticker": f, "name": profiles[f]["name"], "industry": profiles[f].get("category") or "Fund",
                     "status": "included", "stage": "fund",
                     "reason": "Diversified fund used for its asset class.", "evidence": None, "url": None})
    screen_df = pd.DataFrame(rows)

    holdings = pd.DataFrame(
        [{"ticker": t, "name": profiles[t]["name"], "industry": profiles[t]["industry"],
          "asset_class": "equity", "kind": "stock", "flagged": fl} for t, fl in chosen] +
        [{"ticker": f, "name": profiles[f]["name"], "industry": profiles[f].get("category") or "Fund",
          "asset_class": c, "kind": "fund", "flagged": False} for f, c in FUNDS.items()])

    step(0.88, "Building the allocation…")
    port, split, rate_note, exp_ret = allocate(metrics, holdings, policy, rf)
    step(0.93, "Writing the explanation…")
    memo = explain(policy, port, screen_df, split, rate_note, macro_context, rf, exp_ret, len(universe))
    step(1.0, "Done")
    return {"policy": policy, "rf": rf, "split": split, "rate_note": rate_note, "macro_context": macro_context,
            "expected_return": exp_ret, "screen": screen_df, "portfolio": port, "memo": memo,
            "companies_scanned": len(universe), "ai_excluded_industries": ai_excl}


if __name__ == "__main__":
    demo = ("We are a cancer research charity funding early-detection research. We will not invest "
            "in weapons and are investing for 5 years. We need moderate risk because we fund grants every year, "
            "and no single company should be more than 8% of the portfolio.")
    out = run(demo, progress=lambda f, m: print(f"[{f:.0%}] {m}"))
    print("\nScanned", out["companies_scanned"], "companies")
    print("Mission:", out["policy"].get("mission"))
    print("Inferred from mission:", out["policy"].get("inferred_exclusions"))
    print("AI-excluded industries:", out["ai_excluded_industries"])
    print(out["screen"][out["screen"].status != "included"][["ticker", "industry", "stage"]].to_string())
    print(out["portfolio"][["ticker", "industry", "asset_class", "dollars"]].to_string())
    print(out["memo"])
