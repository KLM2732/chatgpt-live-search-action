# ChatGPT Live Web Search — Action Backend

This is a tiny FastAPI service you can **attach to ChatGPT** as an **Action**.
It searches the web (Tavily), fetches pages, extracts readable text, and uses OpenAI to summarize with citations.

## Quick Start (Local)
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # fill in keys
uvicorn main:app --reload --port 8000
```
Test:
```bash
curl -X POST http://127.0.0.1:8000/answer       -H "Content-Type: application/json"       -H "Authorization: Bearer YOUR_TOKEN"       -d '{ "query": "What changed in the latest iOS release?" }'
```

## Deploy (one-click-ish options)
- **Railway.app**, **Render.com**, **Fly.io**, **Google Cloud Run**, **Azure App Service** — all work with this Dockerfile.
- Set environment variables: `OPENAI_API_KEY`, `TAVILY_API_KEY`, and (recommended) `ACTIONS_API_KEY`.
- Expose port **8000**.
- After deploy, note your public base URL, e.g. `https://your-app.onrender.com`.

## Connect as a ChatGPT Action
1. Open ChatGPT → **Explore GPTs** → **Create**.
2. Go to **Configure** → **Actions** → **Add Action**.
3. In the URL field, paste a link to your **OpenAPI schema** (this repo's `openapi.yaml`).    
   - Host it by serving the raw file from your deployment (e.g., add a static route) or from any HTTPS URL.
   - Quick workaround: temporarily use a GitHub gist/raw link to `openapi.yaml`.
4. When prompted for **Authentication**, choose **API Key** and set the header to: `Authorization: Bearer YOUR_TOKEN`.
5. Save your GPT. In a chat with your GPT, try: *"Search the web and summarize the latest on reusable methane rockets."*

## Security Notes
- Set a strong `ACTIONS_API_KEY` to prevent unauthorized use.
- Be mindful of rate limits on Tavily/OpenAI. Consider adding caching and domain allowlists.
- Avoid returning private or sensitive data. This service only processes the provided query and public web content.

## Customize
- Swap Tavily for another search API in `main.py`.
- Add date parsing, domain ranking, or caching for better quality.
- Add a `/sources` endpoint if you want separate retrieval vs synthesis.
