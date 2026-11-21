from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from ai import run_chat
from models import ChatRequest, DocumentSpec
from render_docx import build_docx
from render_pdf import build_pdf

app = FastAPI(title="DocForge API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(400, "Send at least one message.")
    try:
        reply, doc = run_chat(req)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except ValueError as e:
        raise HTTPException(502, str(e))
    except Exception as e:  # Gemini/network errors
        raise HTTPException(502, f"Gemini request failed: {e}")
    return {"reply": reply, "document": doc}


@app.post("/api/render/pdf")
def render_pdf(spec: DocumentSpec):
    return Response(build_pdf(spec), media_type="application/pdf")


@app.post("/api/export/docx")
def export_docx(spec: DocumentSpec):
    return Response(build_docx(spec),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
