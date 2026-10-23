"""Find the working connection settings for the hackathon AI portal.
Run: python test_llm.py   (reads AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT from .env)"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI

load_dotenv()
BASE = os.getenv("AZURE_OPENAI_ENDPOINT", "https://app-uoaihack2ix6ak.azurewebsites.net").rstrip("/")
KEY = os.environ["AZURE_OPENAI_API_KEY"]
MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
MSG = [{"role": "user", "content": "Reply with the word OK."}]

attempts = []
for ep in [BASE, BASE + "/api/v1"]:
    for ver in ["2024-10-21", "2024-02-01", "2023-09-01-preview"]:
        attempts.append(("azure", ep, ver))
for ep in [BASE + "/api/v1", BASE + "/v1", BASE]:
    attempts.append(("openai", ep, None))

for kind, ep, ver in attempts:
    try:
        if kind == "azure":
            c = AzureOpenAI(azure_endpoint=ep, api_key=KEY, api_version=ver, timeout=20, max_retries=0)
        else:
            c = OpenAI(base_url=ep, api_key=KEY, timeout=20, max_retries=0)
        r = c.chat.completions.create(model=MODEL, messages=MSG, max_tokens=5)
        print(f"\nWORKS: {kind}  endpoint={ep}  version={ver}  model={MODEL}")
        print("Reply:", r.choices[0].message.content)
        if kind == "azure":
            print(f"\nPut in .env:\nAZURE_OPENAI_ENDPOINT={ep}\nAZURE_OPENAI_API_VERSION={ver}")
        else:
            print(f"\nPut in .env (and delete the AZURE_ lines):\nOPENAI_BASE_URL={ep}\n"
                  f"OPENAI_API_KEY=<your key>\nOPENAI_MODEL={MODEL}")
        break
    except Exception as e:
        print(f"no:  {kind:6} {ep}  {ver or ''}  -> {type(e).__name__}: {str(e)[:120]}")
else:
    print("\nNothing worked. Check the model name in the Playground, or paste these errors to Claude.")
