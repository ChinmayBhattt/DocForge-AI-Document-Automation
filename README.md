# DocForge — AI PDF and document automation

Chat with Gemini, get a designed document, preview it, tweak it, download as PDF or Word.

```
frontend/  Next.js (App Router) + Bun     chat, live PDF preview, visual editor
backend/   FastAPI + Gemini + ReportLab   /api/chat  /api/render/pdf  /api/export/docx
```

## How it works
1. Gemini returns a structured JSON document (page, theme, blocks), not raw PDF code. It picks fonts, colours,
   margins, borders and structure; blocks include headings, paragraphs, images/logos, lists, tables, callouts and quotes.
2. FastAPI renders that JSON deterministically with ReportLab (PDF) or python-docx (Word), so layout stays consistent.
3. The editor changes the same JSON, so manual edits and AI edits share one source of truth and the preview re-renders live.

## Run
```bash
# terminal 1: backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add GEMINI_API_KEY
uvicorn main:app --reload --port 8000

# terminal 2: frontend
cd frontend
bun install
bun run dev                                           # http://localhost:3000
```
Set `BACKEND_URL` for the frontend if the API is not at http://127.0.0.1:8000.

## Notes
- Built-in PDF fonts (Helvetica, Times, Courier) lack the rupee sign and non-Latin scripts. Put NotoSans-Regular.ttf,
  NotoSans-Bold.ttf and NotoSans-Italic.ttf in `backend/fonts/` and pick "NotoSans" in the editor.
- Add auth, rate limiting and request-size limits before exposing the API publicly.
# DocForge-AI-Document-Automation
