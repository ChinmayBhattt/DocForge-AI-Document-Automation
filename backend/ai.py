import json
import os

from google import genai
from google.genai import types

from models import ChatRequest, DocumentSpec

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM = """You are DocForge, a senior document designer. The user gives you raw text or instructions;
you return a fully designed document as JSON. Reply with ONLY a JSON object:

{"reply": "<1-2 friendly sentences: what you made or changed>",
 "document": {
  "title": str, "subtitle": str, "author": str,
  "page": {"size": "A4"|"Letter", "orientation": "portrait"|"landscape", "margin_mm": 15-35},
  "theme": {"font": "Helvetica"|"Times"|"Courier", "primary": "#rrggbb", "accent": "#rrggbb",
            "text": "#rrggbb", "muted": "#rrggbb", "base_size": 9.5-12, "line_height": 1.3-1.6,
            "heading_scale": 0.9-1.2, "border": bool, "border_color": "#rrggbb", "border_width": 0.5-3,
            "header_text": str, "footer_text": str, "page_numbers": bool},
  "blocks": [ {"type": "heading", "text": str, "level": 1|2|3},
              {"type": "paragraph", "text": str, "align": "left"|"justify"|"center"|"right"},
              {"type": "image", "url": str, "caption": str, "align": "left"|"center"|"right", "width_mm": number},
              {"type": "bullets"|"numbered", "items": [str]},
              {"type": "table", "header": [str], "rows": [[str]]},
              {"type": "callout", "text": str, "tone": "info"|"success"|"warning"|"danger"},
              {"type": "quote", "text": str},
              {"type": "divider"}, {"type": "spacer", "level": 1-6}, {"type": "pagebreak"} ]}}

Design rules:
- Choose the page, palette and typography to suit the content: contracts/letters -> Times, restrained navy/charcoal,
  justified text; reports/proposals -> Helvetica with one strong primary and a matching accent; creative/event ->
  bolder colour, centered title content. Colours must keep strong text contrast on white.
- Use at most 2 colours plus neutrals. Use a visible hierarchy: heading levels 1 > 2 > 3, never skip levels.
- Structure raw text: split walls of text into short paragraphs, turn lists into bullets/numbered, tabular data into
  tables (every row must have the same number of cells as header), key warnings or takeaways into callouts.
- When an image or logo is provided or requested:
  Use an "image" block with the image reference or URL in "url".
  For company logos or letterheads, place the "image" block at the top of the blocks list (before content headings) with width_mm around 35-50 and align left, center, or right as requested.
  For diagrams, photos or figures, place them where relevant with width_mm 70-120 and an optional caption.
- Preserve the user's facts and wording; never invent figures, names, dates or legal terms. If content is missing,
  use clear [placeholders] for the user to fill in.
- Inline **bold** and *italic* are allowed inside text, items and cells. Do not put the document title in blocks.
- If CURRENT DOCUMENT JSON is provided and the user asks for a change, return the complete updated document and change
  only what was requested; otherwise create a new document.
- Output valid JSON only. No markdown fences."""


def _client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env")
    return genai.Client(api_key=key, http_options={"api_version": "v1beta"})


def run_chat(req: ChatRequest) -> tuple[str, DocumentSpec]:
    image_store: dict[str, str] = {}
    if req.images:
        for k, v in req.images.items():
            image_store[k] = v

    doc_for_prompt = None
    if req.document and req.document.blocks:
        doc_copy = req.document.model_copy(deep=True)
        for idx, b in enumerate(doc_copy.blocks):
            if b.type == "image" and b.url:
                short_id = f"img_existing_{idx}"
                image_store[short_id] = b.url
                image_store[b.url] = b.url
                b.url = short_id
        doc_for_prompt = doc_copy

    contents = [
        types.Content(role="user" if m.role == "user" else "model", parts=[types.Part(text=m.content)])
        for m in req.messages[:-1]
    ]
    last = req.messages[-1].content

    if req.images:
        img_info = [f'- Image: "{k}"' for k in req.images.keys()]
        last += "\n\n[USER ATTACHED IMAGES:\n" + "\n".join(img_info) + "\nWhen placing an image, set its url to the image reference (e.g. url=\"" + list(req.images.keys())[0] + "\"). Place at top for logos or wherever requested.]"

    if doc_for_prompt:
        last += "\n\nCURRENT DOCUMENT JSON:\n" + doc_for_prompt.model_dump_json()
    contents.append(types.Content(role="user", parts=[types.Part(text=last)]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM, response_mime_type="application/json", temperature=0.5
    )
    client, error = _client(), None
    for _ in range(2):  # one retry if the model returns malformed JSON
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents, config=config)
            data = json.loads(resp.text)
            spec = DocumentSpec.model_validate(data["document"])

            # Restore real image URLs
            for b in spec.blocks:
                if b.type == "image":
                    if b.url in image_store:
                        b.url = image_store[b.url]
                    elif len(req.images) == 1 and (not b.url or b.url not in image_store):
                        b.url = next(iter(req.images.values()))
                    else:
                        for k, v in image_store.items():
                            if k.lower() in b.url.lower() or b.url.lower() in k.lower():
                                b.url = v
                                break

            return data.get("reply", "Here's your document."), spec
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            error = e
    raise ValueError(f"The model returned an invalid document: {error}")
