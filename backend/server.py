"""Bridge between the static frontend and pipeline.py. Standard library only.
Run from the repo root:  python3 backend/server.py   then open http://localhost:8000
POST /api/run with the confirmed brief (see SPEC.md). Add ?sample=1 for a canned response."""
import json
import os
import pathlib
import sys
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BACKEND = pathlib.Path(__file__).resolve().parent
ROOT = BACKEND.parent
os.chdir(BACKEND)  # pipeline.py keeps its cache/ next to itself
sys.path.insert(0, str(BACKEND))

# Only the frontend is served; never .env or other files in the repo.
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
SAMPLE = BACKEND / "sample_data" / "sample_response.json"
RISK = {"Conservative": "low", "Balanced": "moderate", "Growth-oriented": "high"}


def brief_to_policy(brief):
    """Turn the frontend's structured brief into the plain-English policy pipeline.run() expects."""
    parts = []
    if brief.get("mission"):
        parts.append(f"Our mission: {brief['mission']}")
    if brief.get("exclusions"):
        parts.append("We will not invest in: " + ", ".join(brief["exclusions"]) + ".")
    if brief.get("flags"):
        parts.append("Flag any company with recent news about: " + ", ".join(brief["flags"]) + ".")
    risk = RISK.get(brief.get("risk"), brief.get("risk"))
    if risk:
        parts.append(f"Our risk tolerance is {risk}.")
    if brief.get("notes"):
        parts.append(brief["notes"])
    return "\n".join(parts)


def records(df):
    return df.astype(object).where(df.notna(), None).to_dict("records")


def to_json(out, brief):
    notes = []
    if brief.get("min_esg") is not None:
        notes.append(f"Minimum ESG score {brief['min_esg']} was not applied: the backend has no ESG data source yet.")
    return {
        "sample": False,
        "memo": out["memo"],
        "policy": out["policy"],
        "portfolio": records(out["portfolio"]),
        "screen": records(out["screen"]),
        "split": out["split"],
        "rate_note": out["rate_note"],
        "expected_return": out["expected_return"],
        "risk_free_rate": out["rf"],
        "companies_scanned": out["companies_scanned"],
        "notes": notes,
    }


def validate(brief):
    if not isinstance(brief, dict):
        return "Brief must be a JSON object."
    for key in ("exclusions", "flags"):
        if not isinstance(brief.get(key, []), list):
            return f"'{key}' must be a list."
    esg = brief.get("min_esg")
    if esg is not None and not (isinstance(esg, (int, float)) and 0 <= esg <= 100):
        return "'min_esg' must be a number from 0 to 100, or null."
    if not brief_to_policy(brief).strip():
        return "The brief is empty."
    return None


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        name = STATIC.get(self.path.split("?")[0])
        if not name:
            return self.send_error(404)
        self.path = "/" + name
        return super().do_GET()

    def do_POST(self):
        path, _, query = self.path.partition("?")
        if path != "/api/run":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            brief = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.reply(400, {"error": "Body must be valid JSON."})
        problem = validate(brief)
        if problem:
            return self.reply(400, {"error": problem})
        if "sample=1" in query.split("&"):
            return self.reply(200, json.loads(SAMPLE.read_text()))
        try:
            from pipeline import run
            return self.reply(200, to_json(run(brief_to_policy(brief)), brief))
        except Exception as e:
            traceback.print_exc()
            return self.reply(500, {"error": f"{type(e).__name__}: {e}"})

    def reply(self, code, data):
        body = json.dumps(data, default=lambda o: o.item() if hasattr(o, "item") else str(o)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Serving on http://localhost:{port}")
    ThreadingHTTPServer(("", port), lambda *a: Handler(*a, directory=str(ROOT))).serve_forever()
