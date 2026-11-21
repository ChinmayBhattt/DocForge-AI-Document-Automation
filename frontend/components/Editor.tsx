"use client";
import { useState } from "react";
import { Block, BlockType, DocSpec, newBlock } from "@/lib/types";

const TYPES: BlockType[] = ["heading", "paragraph", "image", "bullets", "numbered", "table", "callout", "quote", "divider", "spacer", "pagebreak"];

const getText = (b: Block) =>
  b.type === "bullets" || b.type === "numbered" ? b.items.join("\n")
  : b.type === "table" ? [b.header, ...b.rows].map((r) => r.join(" | ")).join("\n")
  : b.text;

function setText(b: Block, v: string): Block {
  if (b.type === "bullets" || b.type === "numbered") return { ...b, items: v.split("\n") };
  if (b.type === "table") {
    const [h, ...rows] = v.split("\n").map((l) => l.split("|").map((c) => c.trim()));
    return { ...b, header: h ?? [], rows };
  }
  return { ...b, text: v };
}

export default function Editor({ spec, onChange }: { spec: DocSpec; onChange: (s: DocSpec) => void }) {
  const [addType, setAddType] = useState<BlockType>("paragraph");
  const th = spec.theme;
  const setTheme = (p: Partial<DocSpec["theme"]>) => onChange({ ...spec, theme: { ...th, ...p } });
  const setPage = (p: Partial<DocSpec["page"]>) => onChange({ ...spec, page: { ...spec.page, ...p } });
  const setBlock = (i: number, b: Block) => onChange({ ...spec, blocks: spec.blocks.map((x, j) => (j === i ? b : x)) });
  const move = (i: number, d: number) => {
    const bl = [...spec.blocks]; const j = i + d;
    if (j < 0 || j >= bl.length) return;
    [bl[i], bl[j]] = [bl[j], bl[i]]; onChange({ ...spec, blocks: bl });
  };
  const retype = (i: number, b: Block, type: BlockType) => {
    const text = getText(b);
    const nb = newBlock(type);
    setBlock(i, setText({ ...nb, align: b.align }, text || getText(nb)));
  };

  return (
    <div className="editor">
      <section>
        <h3>Document</h3>
        <label>Title<input value={spec.title} onChange={(e) => onChange({ ...spec, title: e.target.value })} /></label>
        <label>Subtitle<input value={spec.subtitle} onChange={(e) => onChange({ ...spec, subtitle: e.target.value })} /></label>
        <label>Author<input value={spec.author} onChange={(e) => onChange({ ...spec, author: e.target.value })} /></label>
      </section>

      <section>
        <h3>Page and style</h3>
        <div className="grid2">
          <label>Size<select value={spec.page.size} onChange={(e) => setPage({ size: e.target.value as any })}><option>A4</option><option>Letter</option></select></label>
          <label>Orientation<select value={spec.page.orientation} onChange={(e) => setPage({ orientation: e.target.value as any })}><option>portrait</option><option>landscape</option></select></label>
          <label>Font<select value={th.font} onChange={(e) => setTheme({ font: e.target.value })}><option>Helvetica</option><option>Times</option><option>Courier</option><option>NotoSans</option></select></label>
          <label>Text size: {th.base_size}pt<input type="range" min={9} max={13} step={0.5} value={th.base_size} onChange={(e) => setTheme({ base_size: +e.target.value })} /></label>
          <label>Margins: {Math.round(spec.page.margin_mm)}mm<input type="range" min={12} max={40} value={spec.page.margin_mm} onChange={(e) => setPage({ margin_mm: +e.target.value })} /></label>
          <label>Line height: {th.line_height}<input type="range" min={1.2} max={1.8} step={0.05} value={th.line_height} onChange={(e) => setTheme({ line_height: +e.target.value })} /></label>
          <label>Primary colour<input type="color" value={th.primary} onChange={(e) => setTheme({ primary: e.target.value })} /></label>
          <label>Accent colour<input type="color" value={th.accent} onChange={(e) => setTheme({ accent: e.target.value })} /></label>
        </div>
        <div className="checks">
          <label><input type="checkbox" checked={th.border} onChange={(e) => setTheme({ border: e.target.checked })} /> Page border</label>
          <label><input type="checkbox" checked={th.page_numbers} onChange={(e) => setTheme({ page_numbers: e.target.checked })} /> Page numbers</label>
        </div>
        {th.border && (
          <div className="grid2">
            <label>Border colour<input type="color" value={th.border_color} onChange={(e) => setTheme({ border_color: e.target.value })} /></label>
            <label>Border width: {th.border_width}<input type="range" min={0.5} max={3} step={0.5} value={th.border_width} onChange={(e) => setTheme({ border_width: +e.target.value })} /></label>
          </div>
        )}
        <label>Header text<input value={th.header_text} onChange={(e) => setTheme({ header_text: e.target.value })} /></label>
        <label>Footer text<input value={th.footer_text} onChange={(e) => setTheme({ footer_text: e.target.value })} /></label>
      </section>

      <section>
        <h3>Content</h3>
        {spec.blocks.map((b, i) => {
          const hasText = !["divider", "pagebreak", "spacer", "image"].includes(b.type);
          const text = getText(b);
          return (
            <div className="block" key={i}>
              <div className="blockbar">
                <select value={b.type} aria-label="Block type" onChange={(e) => retype(i, b, e.target.value as BlockType)}>
                  {TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                {b.type === "heading" && <select value={b.level} aria-label="Heading level" onChange={(e) => setBlock(i, { ...b, level: +e.target.value })}>{[1, 2, 3].map((n) => <option key={n} value={n}>H{n}</option>)}</select>}
                {b.type === "spacer" && <input type="number" aria-label="Spacer size" min={1} max={6} value={b.level} onChange={(e) => setBlock(i, { ...b, level: +e.target.value })} />}
                {b.type === "callout" && <select value={b.tone} aria-label="Tone" onChange={(e) => setBlock(i, { ...b, tone: e.target.value as any })}>{["info", "success", "warning", "danger"].map((t) => <option key={t}>{t}</option>)}</select>}
                {["paragraph", "quote", "callout", "image"].includes(b.type) && <select value={b.align} aria-label="Alignment" onChange={(e) => setBlock(i, { ...b, align: e.target.value as any })}>{["left", "justify", "center", "right"].map((t) => <option key={t}>{t}</option>)}</select>}
                <span className="spacer" />
                <button onClick={() => move(i, -1)} aria-label="Move up">↑</button>
                <button onClick={() => move(i, 1)} aria-label="Move down">↓</button>
                <button onClick={() => onChange({ ...spec, blocks: spec.blocks.filter((_, j) => j !== i) })} aria-label="Delete block">✕</button>
              </div>
              {b.type === "image" && (
                <div className="image-block-editor">
                  {b.url && (
                    <div style={{ marginBottom: "8px", textAlign: b.align as any }}>
                      <img src={b.url} alt={b.caption || "Preview"} style={{ maxHeight: "110px", maxWidth: "100%", objectFit: "contain", borderRadius: "4px", border: "1px solid var(--line)" }} />
                    </div>
                  )}
                  <div className="grid2">
                    <label>
                      Upload / Replace image
                      <input type="file" accept="image/*" onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const reader = new FileReader();
                        reader.onload = () => setBlock(i, { ...b, url: reader.result as string });
                        reader.readAsDataURL(file);
                      }} />
                    </label>
                    <label>
                      Width: {b.width_mm || 45}mm
                      <input type="range" min={15} max={180} step={5} value={b.width_mm || 45} onChange={(e) => setBlock(i, { ...b, width_mm: +e.target.value })} />
                    </label>
                  </div>
                  <div className="grid2">
                    <label>
                      Image URL or Data
                      <input value={b.url?.startsWith("data:") ? "(Uploaded image data)" : b.url || ""} placeholder="https://... or upload above" onChange={(e) => setBlock(i, { ...b, url: e.target.value })} />
                    </label>
                    <label>
                      Caption (optional)
                      <input value={b.caption || ""} placeholder="e.g. Figure 1: Company Logo" onChange={(e) => setBlock(i, { ...b, caption: e.target.value })} />
                    </label>
                  </div>
                </div>
              )}
              {hasText && <textarea rows={Math.min(8, text.split("\n").length + 1)} value={text} onChange={(e) => setBlock(i, setText(b, e.target.value))}
                placeholder={b.type === "table" ? "Header A | Header B\nvalue | value" : undefined} />}
              {b.type === "table" && <small>One row per line; separate columns with “|”. The first line is the header.</small>}
              {(b.type === "bullets" || b.type === "numbered") && <small>One item per line.</small>}
            </div>
          );
        })}
        <div className="addrow">
          <select value={addType} aria-label="New block type" onChange={(e) => setAddType(e.target.value as BlockType)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
          <button className="secondary" onClick={() => onChange({ ...spec, blocks: [...spec.blocks, newBlock(addType)] })}>Add block</button>
        </div>
      </section>
    </div>
  );
}
