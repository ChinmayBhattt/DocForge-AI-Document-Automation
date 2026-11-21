"use client";
import { useEffect, useRef, useState } from "react";
import Editor from "@/components/Editor";
import type { DocSpec, Msg } from "@/lib/types";

const JSON_HEADERS = { "Content-Type": "application/json" };
const IDEAS = [
  "One-page invoice for a design studio with 3 line items and a payment-terms note",
  "Formal offer letter for a Product Designer, with a bordered page and justified text",
  "Event itinerary for a 2-day offsite, as a table with a bold colour scheme",
];

async function errorOf(r: Response) {
  try { return (await r.json()).detail ?? "Request failed"; } catch { return "Request failed"; }
}

export default function Home() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [attachedImages, setAttachedImages] = useState<Array<{ id: string; name: string; dataUrl: string }>>([]);
  const [spec, setSpec] = useState<DocSpec | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [tab, setTab] = useState<"preview" | "edit">("preview");
  const [busy, setBusy] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [err, setErr] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { logRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [msgs, busy, err]);

  // Re-render the PDF whenever the spec changes (debounced so slider drags stay smooth).
  useEffect(() => {
    if (!spec) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      setRendering(true);
      try {
        const r = await fetch("/api/render/pdf", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(spec), signal: ctrl.signal });
        if (!r.ok) throw new Error(await errorOf(r));
        const url = URL.createObjectURL(await r.blob());
        setPdfUrl((old) => { if (old) URL.revokeObjectURL(old); return url; });
      } catch (e: any) { if (e.name !== "AbortError") setErr(e.message); }
      finally { setRendering(false); }
    }, 350);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [spec]);

  async function send(text: string) {
    const trimmed = text.trim();
    if ((!trimmed && attachedImages.length === 0) || busy) return;

    const promptText = trimmed || (spec ? "Add the attached image/logo to the document." : "Create a document and include the attached logo/image.");
    const userMsg: Msg = {
      role: "user",
      content: promptText,
      imagePreview: attachedImages[0]?.dataUrl,
    };
    const next: Msg[] = [...msgs, userMsg];

    const imagesPayload: Record<string, string> = {};
    attachedImages.forEach((img) => {
      imagesPayload[img.id] = img.dataUrl;
      imagesPayload[img.name] = img.dataUrl;
    });

    setMsgs(next);
    setInput("");
    setAttachedImages([]);
    setBusy(true);
    setErr("");

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ messages: next, document: spec, images: imagesPayload }),
      });
      if (!r.ok) throw new Error(await errorOf(r));
      const d = await r.json();
      setSpec(d.document);
      setTab("preview");
      setMsgs([...next, { role: "assistant", content: d.reply }]);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function download(kind: "pdf" | "docx") {
    if (!spec) return;
    const r = await fetch(kind === "pdf" ? "/api/render/pdf" : "/api/export/docx", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(spec) });
    if (!r.ok) return setErr(await errorOf(r));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob());
    a.download = `${(spec.title || "document").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "document"}.${kind}`;
    a.click(); URL.revokeObjectURL(a.href);
  }

  async function loadFile(f?: File) {
    if (!f) return;
    setInput(`Turn this into a polished document:\n\n${(await f.text()).slice(0, 20000)}`);
  }

  function handleImage(f?: File) {
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const id = `img_${Date.now()}`;
      setAttachedImages((prev) => [...prev, { id, name: f.name, dataUrl: reader.result as string }]);
    };
    reader.readAsDataURL(f);
  }

  return (
    <main className="app">
      <aside className="chat">
        <header><h1>DocForge</h1><p>Paste text or describe a document. Ask for changes any time.</p></header>
        <div className="log" ref={logRef}>
          {msgs.length === 0 && (
            <div className="ideas">
              {IDEAS.map((i) => <button key={i} onClick={() => send(i)}>{i}</button>)}
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.imagePreview && (
                <div className="msg-image">
                  <img src={m.imagePreview} alt="Attached" />
                </div>
              )}
              {m.content}
            </div>
          ))}
          {busy && <div className="msg assistant pending">Designing your document…</div>}
          {err && <div className="error" role="alert">{err}</div>}
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          {attachedImages.length > 0 && (
            <div className="attached-strip">
              {attachedImages.map((img) => (
                <div key={img.id} className="image-chip">
                  <img src={img.dataUrl} alt={img.name} />
                  <span>{img.name}</span>
                  <button type="button" aria-label="Remove image" onClick={() => setAttachedImages(attachedImages.filter((x) => x.id !== img.id))}>✕</button>
                </div>
              ))}
            </div>
          )}
          <textarea
            value={input}
            rows={3}
            placeholder={
              attachedImages.length > 0
                ? "Describe where to place the image (e.g., 'Add logo at top right', 'Put in header')…"
                : spec
                ? "Make the headings green, add a signature block, or attach a logo…"
                : "Describe the document, paste text, or attach a logo/image…"
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(input); }}
          />
          <div className="row">
            <div className="file-actions">
              <label className="file">📄 Attach .txt or .md<input type="file" accept=".txt,.md,text/plain" onChange={(e) => loadFile(e.target.files?.[0])} hidden /></label>
              <label className="file">🖼️ Attach image / logo<input type="file" accept="image/*" onChange={(e) => { handleImage(e.target.files?.[0]); e.target.value = ""; }} hidden /></label>
            </div>
            <button type="submit" disabled={busy || (!input.trim() && attachedImages.length === 0)}>{spec ? "Update document" : "Create document"}</button>
          </div>
        </form>
      </aside>

      <section className="stage">
        <div className="toolbar">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>Preview</button>
            <button role="tab" aria-selected={tab === "edit"} onClick={() => setTab("edit")} disabled={!spec}>Edit</button>
          </div>
          <span className="status">{rendering ? "Updating preview…" : spec ? "Up to date" : ""}</span>
          <button className="secondary" disabled={!spec} onClick={() => download("docx")}>Download Word</button>
          <button disabled={!spec} onClick={() => download("pdf")}>Download PDF</button>
        </div>

        {!spec ? (
          <div className="empty"><div className="sheet" aria-hidden /><p>Your document appears here after your first message.</p></div>
        ) : tab === "preview" ? (
          pdfUrl ? <iframe className="viewer" title="PDF preview" src={pdfUrl} /> : <div className="empty"><p>Rendering…</p></div>
        ) : (
          <Editor spec={spec} onChange={setSpec} />
        )}
      </section>
    </main>
  );
}
