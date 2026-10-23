# Ethos ethical investment analyst prototype

A responsive, dependency-free frontend concept for a charity investment-analysis assistant. It lets a user describe their mission, draft exclusions and controversy flags, set ESG and risk thresholds, select policy attachments, and review the proposed analysis brief before explicitly approving a demo response.

Assistant messages support basic Markdown formatting: headings, paragraphs, emphasis, strikethrough, lists, tables, blockquotes, fenced code blocks, inline code, horizontal rules, and HTTP(S) links. Message rendering builds DOM nodes rather than inserting Markdown as HTML; links with unsafe protocols are not made clickable.

## Run locally

From this directory, run:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Prototype boundaries

- The browser prototype is separate from the Python recommendation API. It does not call the portfolio backend or fetch company data.
- Attachments are selected in the browser and their names appear in the review brief. Their contents are not read or uploaded.
- The “Confirm & run demo” action demonstrates the approval flow and clearly states that no analysis was run.
- The draft profile uses lightweight keyword matching to demonstrate the interaction. It is not an AI extraction or validation system.
- The Python API fetches annual US macro indicators from World Bank Open Data, cleans invalid/future observations, and returns an experimental economic-strength score `x` in `[0, 1]`. The backend uses this only after the separate charity industry/news ethics screens, in a 50/50 ranking with normalized historical volatility.
- The macro score and sector-sensitivity mapping are transparent but unvalidated heuristics—not probabilities, forecasts, or company revenue exposure. The news-review budget examines up to 20 companies preordered by historical Sharpe; candidate ranking only covers survivors from that capped pool. This has not been backtested and is not investment advice.
- A production integration should send only the confirmed brief, show the exact request, keep citations and dates with all evidence, and return uncertainty and exclusions alongside any recommendations.
