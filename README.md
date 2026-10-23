# Ethos ethical investment analyst prototype

A responsive, dependency-free frontend concept for a charity investment-analysis assistant. It lets a user describe their mission, draft exclusions and controversy flags, set ESG and risk thresholds, select policy attachments, and review the proposed analysis brief before explicitly approving a demo response.

## Run locally

From this directory, run:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Prototype boundaries

- This is a static frontend. It does not call a backend, fetch live company or economic data, or generate investment advice.
- Attachments are selected in the browser and their names appear in the review brief. Their contents are not read or uploaded.
- The “Confirm & run demo” action demonstrates the approval flow and clearly states that no analysis was run.
- The draft profile uses lightweight keyword matching to demonstrate the interaction. It is not an AI extraction or validation system.
- A production integration should send only the confirmed brief, show the exact request, keep citations and dates with all evidence, and return uncertainty and exclusions alongside any recommendations.
