# Ethos ethical investment analyst prototype

A responsive, dependency-free frontend concept for a charity investment-analysis assistant. It lets a user describe their mission, draft exclusions and controversy flags, set ESG and risk thresholds, select policy attachments, and review the proposed analysis brief before explicitly approving a demo response.

Assistant messages support basic Markdown formatting: headings, paragraphs, emphasis, strikethrough, lists, tables, blockquotes, fenced code blocks, inline code, horizontal rules, and HTTP(S) links. Message rendering builds DOM nodes rather than inserting Markdown as HTML; links with unsafe protocols are not made clickable.

## Run locally

From this directory, run:

```sh
python3 backend/server.py
```

Then open <http://localhost:8000>, or <http://localhost:8000/?sample=1> for a canned response that needs no API keys. See [SPEC.md](SPEC.md) for setup and the request and response schema.

## Prototype boundaries

- The chat sends the pasted policy text to `backend/server.py`, which runs `backend/pipeline.py`. The AI reads the policy into JSON rules, then the pipeline screens about 100 large US companies, news-checks the top 20 and builds a $100,000 portfolio. Output is educational, not investment advice.
- Attachments are listed by name only; their contents are not read. Paste the policy as text.
- World Bank US macro data gives an experimental economic-strength score used to re-rank news-checked companies (50% lower volatility, 50% sector fit). It's an unvalidated heuristic, not a forecast, and has not been backtested.
- Every scanned company gets a reason for being chosen, excluded, flagged or not chosen. See [SPEC.md](SPEC.md).
