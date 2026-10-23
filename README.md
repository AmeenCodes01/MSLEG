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

- “Confirm & run analysis” sends the approved brief to `backend/server.py`, which runs `backend/pipeline.py`. Output is educational, not investment advice.
- Only `.txt` and `.csv` attachments are read; other attachments appear in the review brief by name only.
- The draft profile uses lightweight keyword matching to demonstrate the interaction. It is not an AI extraction or validation system.
- A production integration should send only the confirmed brief, show the exact request, keep citations and dates with all evidence, and return uncertainty and exclusions alongside any recommendations.
