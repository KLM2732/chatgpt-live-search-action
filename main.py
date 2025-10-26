import os, re, time, requests
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ACTIONS_API_KEY = os.getenv("ACTIONS_API_KEY")  # optional

if not OPENAI_API_KEY or not TAVILY_API_KEY:
    print("WARNING: Missing OPENAI_API_KEY or TAVILY_API_KEY. Set env vars in your hosting platform.")

from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI(
    title="Live Web Search Action",
    description="Backend for a ChatGPT Action that performs web search, fetches pages, and synthesizes answers with citations.",
    version="1.0.0",
)

class AnswerRequest(BaseModel):
    query: str
    max_results: int = 6

class Source(BaseModel):
    title: str
    url: str

class AnswerResponse(BaseModel):
    answer: str
    sources: List[Source]

# --- Web search (Tavily) ---
def web_search(query: str, k: int = 6) -> List[Dict]:
    try:
        from tavily import TavilyClient
        t = TavilyClient(api_key=TAVILY_API_KEY)
        res = t.search(query=query, max_results=k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")
    items = []
    seen = set()
    for r in res.get("results", []):
        url = r.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        items.append({
            "title": r.get("title") or url,
            "url": url,
            "snippet": r.get("content") or ""
        })
    return items

# --- Fetch & extract ---
HEADERS = {"User-Agent": "chatgpt-live-search-action/1.0 (+research use)"}

def _request_with_retries(url: str, attempts: int = 2, timeout: int = 12) -> str:
    for i in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if 200 <= resp.status_code < 300 and resp.text:
                return resp.text
        except requests.RequestException:
            pass
        time.sleep(0.6 * (i + 1))
    return ""

def extract_text(html: str) -> str:
    try:
        import trafilatura
        text = trafilatura.extract(html, include_links=False) or ""
    except Exception:
        text = ""
    if not text:
        text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
    return text.strip()

def fetch_and_extract(url: str, max_chars: int = 12000) -> str:
    html = _request_with_retries(url)
    if not html:
        return ""
    text = extract_text(html)
    return text[:max_chars]

# --- Synthesize with citations ---
def synthesize_answer(user_query: str, docs: List[Dict[str, str]]) -> str:
    if openai_client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured.")
    SYSTEM = (
        "You are a careful research assistant. Use only the provided source excerpts. "
        "Cite claims with [#] that link to the URL. Include dates if present in the text; "
        "admit uncertainty if sources conflict or are thin. Be concise."
    )
    sources_blob = "\n\n".join(
        f"### Source {i+1}\nTitle: {d['title']}\nURL: {d['url']}\nCONTENT:\n{d['text']}"
        for i, d in enumerate(docs)
    )
    prompt = f"""USER QUESTION:
{user_query}

SOURCES:
{sources_blob}

INSTRUCTIONS:
- Start with 3–6 bullet takeaways.
- Then 1 short paragraph explanation.
- End with 'Sources' listing [#] links (domain + title).
"""
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content

def authorize(authorization: Optional[str]) -> None:
    if ACTIONS_API_KEY:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = authorization.split(" ", 1)[1].strip()
        if token != ACTIONS_API_KEY:
            raise HTTPException(status_code=403, detail="Invalid API token")

@app.post("/answer", response_model=AnswerResponse)
def answer(payload: AnswerRequest, authorization: Optional[str] = Header(default=None, convert_underscores=False)):
    authorize(authorization)

    hits = web_search(payload.query, k=payload.max_results)
    if not hits:
        raise HTTPException(status_code=404, detail="No search results")

    docs = []
    for h in hits:
        text = fetch_and_extract(h["url"])
        if len(text) >= 600:
            docs.append({"title": h["title"], "url": h["url"], "text": text})
    if len(docs) < 2:
        raise HTTPException(status_code=502, detail="Not enough quality sources fetched")

    answer_text = synthesize_answer(payload.query, docs)
    return {
        "answer": answer_text,
        "sources": [{"title": d["title"], "url": d["url"]} for d in docs]
    }

@app.get("/healthz")
def healthz():
    return {"ok": True}
