"""Bridge between the static frontend and pipeline.py. Standard library only.
Run from the repo root:  python3 backend/server.py   then open http://localhost:8000
POST /api/run with {"policy": "<text>"} (see SPEC.md). Add ?sample=1 for a canned response."""
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
MAX_POLICY_CHARS = 20_000


def records(df):
    return df.astype(object).where(df.notna(), None).to_dict("records")


def to_json(out):
    scr = out["screen"]
    checked = scr[scr.stage == "AI news screen"]
    notes = ["No ESG scores were used: the backend has no ESG data source yet."]
    if len(checked) and checked["news_checked"].fillna(0).sum() == 0:
        notes.append("No news was found for any company, so the news check passed everyone. "
                     "Check FINNHUB_API_KEY in backend/.env.")
    return {
        "sample": False,
        "memo": out["memo"],
        "policy": out["policy"],
        "portfolio": records(out["portfolio"]),
        "screen": records(scr),
        "split": out["split"],
        "rate_note": out["rate_note"],
        "expected_return": out["expected_return"],
        "risk_free_rate": out["rf"],
        "companies_scanned": out["companies_scanned"],
        "notes": notes,
    }


def validate(body):
    policy = body.get("policy") if isinstance(body, dict) else None
    if not isinstance(policy, str) or not policy.strip():
        return "Send {\"policy\": \"...\"} with the charity's policy as text."
    if len(policy) > MAX_POLICY_CHARS:
        return f"Policy is too long: keep it under {MAX_POLICY_CHARS:,} characters."
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
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.reply(400, {"error": "Body must be valid JSON."})
        problem = validate(body)
        if problem:
            return self.reply(400, {"error": problem})
        if "sample=1" in query.split("&"):
            return self.reply(200, json.loads(SAMPLE.read_text()))
        try:
            from pipeline import run
            return self.reply(200, to_json(run(body["policy"])))
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
