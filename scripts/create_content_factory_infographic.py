#!/usr/bin/env python3

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
AVATAR_PATH = PROJECT_ROOT / "assets" / "avatar.png"
OUTPUT_PATH = PROJECT_ROOT / "output" / "content-factory-infographic.png"

WIDTH = 1600
HEIGHT = 2000
BG = "#2b2b2b"
WHITE = "#ffffff"
LAVENDER = "#c5c7ff"
MUTED = (255, 255, 255, 178)
PANEL = "#373737"
PANEL_ALT = "#323232"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size=size)


def wrap(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.FreeTypeFont, width: int) -> str:
    lines = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            box = draw.textbbox((0, 0), candidate, font=font_obj)
            if box[2] - box[0] <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return "\n".join(lines)


def rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=28, fill=fill, outline=outline, width=width)


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]):
    draw.line((*start, *end), fill=WHITE, width=5)
    x, y = end
    draw.line((x - 20, y - 20, x, y, x - 20, y + 20), fill=WHITE, width=5, joint="curve")


def draw_avatar_and_account(base: Image.Image, draw: ImageDraw.ImageDraw):
    if AVATAR_PATH.exists():
        avatar_size = 58
        avatar = Image.open(AVATAR_PATH).convert("RGBA").resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
        alpha = avatar.getchannel("A")
        avatar.putalpha(Image.composite(alpha, Image.new("L", alpha.size, 0), mask))
        base.alpha_composite(avatar, (90, 82))
    draw.text((162, 96), "@vita_vlasova", font=font("Montserrat-Regular.ttf", 30), fill=MUTED)


def draw_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    number: str,
    title: str,
    body: str,
    body_size: int = 30,
):
    rounded_rect(draw, (x, y, x + w, y + h), PANEL)
    num_font = font("Montserrat-Regular.ttf", 30)
    title_font = font("ElMessiri.ttf", 54)
    body_font = font("Montserrat-Regular.ttf", body_size)

    draw.ellipse((x + 40, y + 42, x + 92, y + 94), fill=LAVENDER)
    draw.text((x + 58, y + 50), number, font=num_font, fill=BG, anchor="la")
    draw.multiline_text((x + 120, y + 35), wrap(draw, title, title_font, w - 170), font=title_font, fill=WHITE, spacing=8)
    draw.multiline_text((x + 50, y + 140), wrap(draw, body, body_font, w - 100), font=body_font, fill=LAVENDER, spacing=12)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw_avatar_and_account(image, draw)

    title_font = font("ElMessiri.ttf", 92)
    subtitle_font = font("Montserrat-Regular.ttf", 36)
    small_font = font("Montserrat-Regular.ttf", 28)

    draw.multiline_text(
        (90, 230),
        "Как работает\nконтент-завод",
        font=title_font,
        fill=WHITE,
        spacing=10,
    )
    draw.multiline_text(
        (90, 450),
        wrap(
            draw,
            "Одна идея превращается в готовый контент для Telegram, VK, Instagram и визуалы к публикации.",
            subtitle_font,
            980,
        ),
        font=subtitle_font,
        fill=LAVENDER,
        spacing=14,
    )

    draw_card(
        draw,
        90,
        650,
        620,
        300,
        "1",
        "Идея на входе",
        "Короткая заметка, черновик, личный опыт или ссылка с контекстом.",
    )
    draw_card(
        draw,
        890,
        650,
        620,
        300,
        "2",
        "Content Maker",
        "Берет базу знаний: аудиторию, tone of voice, позиционирование и правила площадок.",
    )
    draw_arrow(draw, (735, 800), (855, 800))

    rounded_rect(draw, (300, 1060, 1300, 1265), PANEL_ALT, outline=LAVENDER, width=3)
    draw.text((370, 1114), "На выходе: готовые материалы", font=font("ElMessiri.ttf", 62), fill=WHITE)
    draw.text((370, 1195), "Тексты, JSON-карусель и visual brief", font=subtitle_font, fill=LAVENDER)

    draw_card(
        draw,
        90,
        1360,
        420,
        340,
        "3",
        "Telegram",
        "Готовый пост в Markdown: можно копировать и публиковать.",
        body_size=27,
    )
    draw_card(
        draw,
        590,
        1360,
        420,
        340,
        "4",
        "Instagram",
        "JSON-карусель уходит в Carousel Renderer и становится PNG-слайдами.",
        body_size=27,
    )
    draw_card(
        draw,
        1090,
        1360,
        420,
        340,
        "5",
        "Визуал",
        "Visual brief уходит в Image Generator и превращается в обложку.",
        body_size=27,
    )

    draw.text((90, 1840), "Итог:", font=font("ElMessiri.ttf", 54), fill=WHITE)
    draw.text(
        (235, 1852),
        "контент готов быстрее, стиль сохраняется, рутина уходит в систему.",
        font=small_font,
        fill=LAVENDER,
    )

    image.convert("RGB").save(OUTPUT_PATH, quality=95)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
