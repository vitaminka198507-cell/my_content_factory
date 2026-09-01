#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output" / "carousels"
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
AVATAR_PATH = PROJECT_ROOT / "assets" / "avatar.png"

WIDTH = 1080
HEIGHT = 1350
BG_COLOR = "#2b2b2b"
HEADLINE_COLOR = "#ffffff"
BODY_COLOR = "#c5c7ff"
ACCOUNT_COLOR = (255, 255, 255, int(255 * 0.7))
ARROW_COLOR = "#ffffff"

SAFE_LEFT = 70
SAFE_RIGHT = 70
SAFE_TOP = 70
SAFE_BOTTOM = 70
CONTENT_TOP_DEFAULT = 530
CONTENT_WIDTH = WIDTH - SAFE_LEFT - SAFE_RIGHT
AVATAR_SIZE = 46
AVATAR_TOP = 48
ACCOUNT_TOP = 58
ACCOUNT_LEFT = SAFE_LEFT + AVATAR_SIZE + 12
HEADLINE_BODY_GAP = 64
ARROW_LENGTH = 135
ARROW_STROKE = 4
ARROW_HEAD = 18

VALID_ROLES = {"hook", "context", "content", "conclusion", "cta"}


def load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Font not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def slug_from_path(path: Path) -> str:
    stem = path.stem
    return re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ._-]+", "-", stem).strip("-") or "carousel"


def validate_carousel(data: dict) -> None:
    if data.get("schema_version") != "instagram-carousel/v1":
        raise ValueError("schema_version должен быть instagram-carousel/v1")
    if data.get("format") != "carousel":
        raise ValueError("format должен быть carousel")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("slides должен быть непустым массивом")

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise ValueError("каждый slide должен быть объектом")
        for field in ("slide", "role", "headline", "body"):
            if field not in slide:
                raise ValueError(f"в slide {index} отсутствует поле {field}")
        if slide["slide"] != index:
            raise ValueError("номера слайдов должны идти по порядку с 1")
        if slide["role"] not in VALID_ROLES:
            raise ValueError(f"недопустимая роль слайда: {slide['role']}")


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    if not text:
        return 0, 0
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=0)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    wrapped_lines: list[str] = []

    for paragraph in str(text or "").splitlines() or [""]:
        if not paragraph.strip():
            wrapped_lines.append("")
            continue

        words = paragraph.split()
        line = ""

        for word in words:
            candidate = word if not line else f"{line} {word}"
            candidate_width, _ = text_size(draw, candidate, font)

            if candidate_width <= max_width:
                line = candidate
                continue

            if line:
                wrapped_lines.append(line)
            line = word

        if line:
            wrapped_lines.append(line)

    return "\n".join(wrapped_lines)


def choose_headline_size(headline: str) -> int:
    length = len(str(headline or "").strip())
    if length < 34:
        return 72
    if length > 58:
        return 56
    return 64


def choose_body_size(body: str) -> int:
    length = len(str(body or "").strip())
    if length > 230:
        return 32
    return 36


def draw_avatar(overlay: Image.Image, warnings: list[str]) -> None:
    if not AVATAR_PATH.exists():
        warnings.append("Avatar file not found: assets/avatar.png")
        return

    avatar = Image.open(AVATAR_PATH).convert("RGBA")
    avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)

    alpha = avatar.getchannel("A")
    alpha = Image.composite(alpha, Image.new("L", alpha.size, 0), mask)
    avatar.putalpha(alpha)

    overlay.alpha_composite(avatar, (SAFE_LEFT, AVATAR_TOP))


def draw_next_arrow(draw: ImageDraw.ImageDraw) -> None:
    end_x = WIDTH - SAFE_RIGHT
    y = HEIGHT - SAFE_BOTTOM - 28
    start_x = end_x - ARROW_LENGTH
    draw.line((start_x, y, end_x, y), fill=ARROW_COLOR, width=ARROW_STROKE)
    draw.line(
        (end_x - ARROW_HEAD, y - ARROW_HEAD, end_x, y, end_x - ARROW_HEAD, y + ARROW_HEAD),
        fill=ARROW_COLOR,
        width=ARROW_STROKE,
        joint="curve",
    )


def draw_slide(slide: dict, is_last: bool) -> tuple[Image.Image, list[str]]:
    warnings: list[str] = []
    image = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    overlay_draw = ImageDraw.Draw(overlay)

    account_font = load_font("Montserrat-Regular.ttf", 24)
    headline_font = load_font("ElMessiri.ttf", choose_headline_size(slide["headline"]))
    body_font = load_font("Montserrat-Regular.ttf", choose_body_size(slide["body"]))
    draw_avatar(overlay, warnings)
    overlay_draw.text((ACCOUNT_LEFT, ACCOUNT_TOP), "@vita_vlasova", font=account_font, fill=ACCOUNT_COLOR)

    headline = wrap_text(draw, slide["headline"], headline_font, CONTENT_WIDTH)
    body = wrap_text(draw, slide["body"], body_font, CONTENT_WIDTH)

    headline_height = text_size(draw, headline, headline_font)[1]
    body_height = text_size(draw, body, body_font)[1] if body.strip() else 0
    gap = HEADLINE_BODY_GAP if body.strip() else 0
    total_height = headline_height + gap + body_height

    content_top = CONTENT_TOP_DEFAULT
    max_bottom = HEIGHT - SAFE_BOTTOM - 110
    if content_top + total_height > max_bottom:
        content_top = max(SAFE_TOP + 140, max_bottom - total_height)

    if content_top + total_height > max_bottom:
        warnings.append(
            f"Slide {slide['slide']}: text may overflow. Consider shortening headline/body."
        )

    draw.multiline_text(
        (SAFE_LEFT, content_top),
        headline,
        font=headline_font,
        fill=HEADLINE_COLOR,
        spacing=8,
    )

    if body.strip():
        draw.multiline_text(
            (SAFE_LEFT, content_top + headline_height + gap),
            body,
            font=body_font,
            fill=BODY_COLOR,
            spacing=10,
        )

    if not is_last:
        draw_next_arrow(draw)

    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"), warnings


def render_carousel(source_json: Path, output_dir: Path | None = None) -> dict:
    data = json.loads(source_json.read_text(encoding="utf-8"))
    validate_carousel(data)

    if output_dir is None:
        output_dir = OUTPUT_ROOT / slug_from_path(source_json)
    output_dir.mkdir(parents=True, exist_ok=True)

    render_slides = [slide for slide in data["slides"] if slide["slide"] != 1]
    if not render_slides:
        raise ValueError("Нет слайдов для рендера: slide 1 пропускается")

    exported: list[str] = []
    warnings: list[str] = []

    for index, slide in enumerate(render_slides):
        image, slide_warnings = draw_slide(slide, is_last=index == len(render_slides) - 1)
        output_path = output_dir / f"slide-{slide['slide']:02d}.png"
        image.save(output_path)
        exported.append(str(output_path.relative_to(PROJECT_ROOT)))
        warnings.extend(slide_warnings)

    caption_path = output_dir / "caption.txt"
    caption_path.write_text(data.get("caption", ""), encoding="utf-8")

    manifest = {
        "status": "ok",
        "source_json": str(source_json.relative_to(PROJECT_ROOT)),
        "output_dir": str(output_dir.relative_to(PROJECT_ROOT)),
        "skipped_source_slides": [1],
        "slides": exported,
        "caption": str(caption_path.relative_to(PROJECT_ROOT)),
        "warnings": warnings,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Instagram carousel JSON to PNG slides.")
    parser.add_argument("json_path", help="Path to Instagram carousel JSON")
    parser.add_argument("--output-dir", help="Optional output directory")
    args = parser.parse_args()

    source_json = Path(args.json_path)
    if not source_json.is_absolute():
        source_json = PROJECT_ROOT / source_json

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir and not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    manifest = render_carousel(source_json, output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
