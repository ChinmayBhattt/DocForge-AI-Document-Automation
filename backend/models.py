import re
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

Str = Annotated[str, BeforeValidator(lambda v: "" if v is None else str(v))]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def safe_hex(value: str, default: str) -> str:
    return value if isinstance(value, str) and HEX.match(value) else default


def tint(hex_color: str, amount: float) -> str:
    """Blend a colour toward white. amount=1 -> same colour, 0 -> white."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: round(255 - (255 - c) * amount)
    return "#{:02x}{:02x}{:02x}".format(mix(r), mix(g), mix(b))


class Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Block(Base):
    type: Literal["heading", "paragraph", "bullets", "numbered", "table",
                  "callout", "quote", "divider", "spacer", "pagebreak", "image"] = "paragraph"
    text: Str = ""
    level: int = 1                       # heading level 1-3, spacer size 1-6
    items: list[Str] = []                # bullets / numbered
    header: list[Str] = []               # table header
    rows: list[list[Str]] = []           # table rows
    align: Literal["left", "center", "right", "justify"] = "left"
    tone: Literal["info", "success", "warning", "danger"] = "info"
    url: Str = ""                        # image url, data URL, or image reference
    caption: Str = ""                    # optional image caption
    width_mm: float = 0                  # optional width in mm


class Page(Base):
    size: Literal["A4", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margin_mm: float = 22


class Theme(Base):
    font: str = "Helvetica"              # Helvetica | Times | Courier | NotoSans (if installed)
    primary: str = "#1f3a5f"
    accent: str = "#2f6fed"
    text: str = "#1c2430"
    muted: str = "#6b7685"
    base_size: float = 10.5
    line_height: float = 1.45
    heading_scale: float = 1.0
    border: bool = False
    border_color: str = "#1f3a5f"
    border_width: float = 1.0
    header_text: str = ""
    footer_text: str = ""
    page_numbers: bool = True


class DocumentSpec(Base):
    title: Str = "Untitled document"
    subtitle: Str = ""
    author: Str = ""
    page: Page = Field(default_factory=Page)
    theme: Theme = Field(default_factory=Theme)
    blocks: list[Block] = []


class Msg(Base):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(Base):
    messages: list[Msg]
    document: DocumentSpec | None = None
    images: dict[str, str] = Field(default_factory=dict)
