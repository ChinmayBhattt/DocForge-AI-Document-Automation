export type BlockType = "heading" | "paragraph" | "image" | "bullets" | "numbered" | "table" | "callout" | "quote" | "divider" | "spacer" | "pagebreak";
export interface Block {
  type: BlockType; text: string; level: number; items: string[]; header: string[]; rows: string[][];
  align: "left" | "center" | "right" | "justify"; tone: "info" | "success" | "warning" | "danger";
  url?: string; caption?: string; width_mm?: number;
}
export interface DocSpec {
  title: string; subtitle: string; author: string;
  page: { size: "A4" | "Letter"; orientation: "portrait" | "landscape"; margin_mm: number };
  theme: {
    font: string; primary: string; accent: string; text: string; muted: string; base_size: number;
    line_height: number; heading_scale: number; border: boolean; border_color: string; border_width: number;
    header_text: string; footer_text: string; page_numbers: boolean;
  };
  blocks: Block[];
}
export interface Msg { role: "user" | "assistant"; content: string; imagePreview?: string }

export const newBlock = (type: BlockType): Block => ({
  type,
  text: type === "heading" ? "New heading" : ["divider", "spacer", "pagebreak", "bullets", "numbered", "table", "image"].includes(type) ? "" : "New text",
  level: 2,
  items: type === "bullets" || type === "numbered" ? ["First item"] : [],
  header: type === "table" ? ["Column A", "Column B"] : [],
  rows: type === "table" ? [["", ""]] : [],
  align: "left", tone: "info",
  url: "", caption: "", width_mm: 45,
});
