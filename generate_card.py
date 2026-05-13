#!/usr/bin/env python3
"""Generate a Chinese ink-wash quote card from the Zeng Guofan quote library."""

from __future__ import annotations

import argparse
import json
import os
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CARD_SIZE = (1080, 1350)


@dataclass(frozen=True)
class Quote:
    id: str
    category: str
    quote: str
    vernacular: str
    keywords: list[str]
    mood: str
    scene_hint: str
    source: str
    confidence: str
    card_title: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_quotes() -> list[Quote]:
    rows = load_json(DATA_DIR / "quotes.json")
    return [Quote(**row) for row in rows]


def pick_quote(quotes: list[Quote], quote_id: str | None, category: str | None) -> Quote:
    if quote_id:
        for quote in quotes:
            if quote.id == quote_id:
                return quote
        raise SystemExit(f"未找到语录 ID: {quote_id}")

    candidates = quotes
    if category:
        candidates = [quote for quote in quotes if quote.category == category]
        if not candidates:
            available = "、".join(sorted({quote.category for quote in quotes}))
            raise SystemExit(f"未找到分类: {category}。可用分类：{available}")

    return random.choice(candidates)


def build_prompt(quote: Quote) -> tuple[str, str]:
    templates = load_json(DATA_DIR / "prompt_templates.json")
    scene = templates["category_styles"].get(quote.category, quote.scene_hint)
    if quote.scene_hint:
        scene = f"{scene}, {quote.scene_hint}"
    prompt = templates["default_style"]["positive"].format(scene_hint=scene)
    negative = templates["default_style"]["negative"]
    return prompt, negative


def generate_background_offline(quote: Quote, output_path: Path) -> Path:
    width, height = CARD_SIZE
    base = Image.new("RGB", CARD_SIZE, (236, 230, 214))
    draw = ImageDraw.Draw(base, "RGBA")

    for y in range(height):
        shade = int(18 * y / height)
        draw.line([(0, y), (width, y)], fill=(238 - shade, 232 - shade, 216 - shade, 255))

    random.seed(quote.id)
    for _ in range(1200):
        x = random.randrange(width)
        y = random.randrange(height)
        alpha = random.randrange(8, 22)
        draw.point((x, y), fill=(70, 62, 50, alpha))

    mountain_color = (42, 54, 50, 48)
    for layer in range(5):
        y_base = 440 + layer * 95
        points = [(0, height)]
        for x in range(-120, width + 160, 120):
            peak = y_base + random.randint(-90, 70)
            points.append((x, peak))
        points.extend([(width, height), (0, height)])
        draw.polygon(points, fill=mountain_color)

    for x in (95, 140, 900, 945):
        draw.line([(x, 140), (x + random.randint(-70, 40), 760)], fill=(35, 49, 39, 72), width=8)
        for offset in range(0, 360, 42):
            y = 190 + offset
            draw.line([(x, y), (x - 80, y + 55)], fill=(35, 49, 39, 42), width=3)
            draw.line([(x, y), (x + 70, y + 45)], fill=(35, 49, 39, 34), width=3)

    moon_box = (770, 120, 930, 280)
    draw.ellipse(moon_box, fill=(245, 241, 226, 120), outline=(130, 114, 88, 35), width=2)
    base = base.filter(ImageFilter.GaussianBlur(radius=0.7))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(output_path)
    return output_path


def generate_background_fal(quote: Quote, output_path: Path, endpoint: str) -> Path:
    try:
        import fal_client
    except ImportError as exc:
        raise SystemExit("缺少 fal-client。请先运行：pip install -r requirements.txt") from exc

    if not os.getenv("FAL_KEY"):
        raise SystemExit("未检测到 FAL_KEY。请先 export FAL_KEY='你的 fal.ai API key'，或加 --offline。")

    prompt, negative = build_prompt(quote)
    result = fal_client.subscribe(
        endpoint,
        arguments={
            "prompt": prompt,
            "negative_prompt": negative,
            "image_size": {"width": CARD_SIZE[0], "height": CARD_SIZE[1]},
            "num_images": 1,
        },
        with_logs=True,
    )
    images = result.get("images") or []
    if not images or not images[0].get("url"):
        raise SystemExit(f"fal.ai 未返回图片 URL：{result}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(images[0]["url"], output_path)
    return output_path


def font(size: int, preferred: str = "song") -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    if preferred == "hei":
        candidates = candidates[1:] + candidates[:1]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font_obj)
    return box[2] - box[0], box[3] - box[1]


def draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font_obj: ImageFont.ImageFont, fill: tuple[int, int, int, int]) -> int:
    width, _ = CARD_SIZE
    text_w, text_h = text_size(draw, text, font_obj)
    draw.text(((width - text_w) / 2, y), text, font=font_obj, fill=fill)
    return y + text_h


def wrap_chinese_by_pixels(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    closing_punctuation = "，。；：！？、）】》」』"

    for char in text:
        candidate = current + char
        candidate_width, _ = text_size(draw, candidate, font_obj)
        if current and candidate_width > max_width and char not in closing_punctuation:
            lines.append(current)
            current = char
        else:
            current = candidate

    if current:
        lines.append(current)
    return lines


def quote_font_for(text: str) -> ImageFont.FreeTypeFont:
    plain_length = len(text)
    if plain_length <= 8:
        return font(84)
    if plain_length <= 15:
        return font(74)
    if plain_length <= 22:
        return font(64)
    return font(56)


def compose_card(background_path: Path, quote: Quote, output_path: Path) -> Path:
    image = Image.open(background_path).convert("RGBA").resize(CARD_SIZE)
    overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rectangle((0, 0, CARD_SIZE[0], CARD_SIZE[1]), fill=(246, 240, 224, 215))
    draw.rectangle((800, 1220, CARD_SIZE[0], CARD_SIZE[1]), fill=(246, 240, 224, 248))
    draw.rectangle((90, 130, 990, 1225), fill=(246, 240, 224, 236), outline=(82, 70, 50, 46), width=2)
    draw.line((160, 230, 920, 230), fill=(82, 70, 50, 64), width=2)
    draw.line((160, 1090, 920, 1090), fill=(82, 70, 50, 52), width=2)

    category_font = font(36, "hei")
    title_font = font(70)
    quote_font = quote_font_for(quote.quote)
    body_font = font(40)
    seal_font = font(32, "hei")

    ink = (42, 38, 31, 235)
    soft_ink = (62, 55, 44, 210)
    cinnabar = (139, 45, 35, 220)

    draw_centered(draw, quote.category, 168, category_font, soft_ink)
    draw_centered(draw, quote.card_title, 270, title_font, ink)

    quote_lines = wrap_chinese_by_pixels(draw, quote.quote, quote_font, 760)
    line_height = int(quote_font.size * 1.35)
    start_y = 470 - max(0, len(quote_lines) - 1) * int(line_height * 0.38)
    for index, line in enumerate(quote_lines):
        draw_centered(draw, line, start_y + index * line_height, quote_font, ink)

    body_lines = wrap_chinese_by_pixels(draw, quote.vernacular, body_font, 680)
    body_y = 790
    for line in body_lines[:3]:
        body_y = draw_centered(draw, line, body_y, body_font, soft_ink) + 22

    draw.text((760, 1010), "曾国藩", font=seal_font, fill=cinnabar)
    draw.rounded_rectangle((900, 1002, 954, 1058), radius=4, outline=cinnabar, width=3)
    draw.text((912, 1012), "语", font=font(28, "hei"), fill=cinnabar)

    result = Image.alpha_composite(image, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, quality=95)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成曾国藩水墨国风语录卡片")
    parser.add_argument("--quote-id", help="指定 quotes.json 中的语录 ID")
    parser.add_argument("--category", help="指定分类：修身/处世/治学/识人/持家")
    parser.add_argument("--offline", action="store_true", help="不调用 fal.ai，使用本地水墨占位背景")
    parser.add_argument("--endpoint", default="fal-ai/flux/schnell", help="fal.ai 模型 endpoint")
    args = parser.parse_args()

    quote = pick_quote(load_quotes(), args.quote_id, args.category)
    OUTPUT_DIR.mkdir(exist_ok=True)

    background_path = OUTPUT_DIR / f"{quote.id}_background.png"
    card_path = OUTPUT_DIR / f"{quote.id}_card.png"

    if args.offline:
        generate_background_offline(quote, background_path)
    else:
        generate_background_fal(quote, background_path, args.endpoint)

    compose_card(background_path, quote, card_path)
    print(f"已生成：{card_path}")
    print(f"语录：{quote.quote}")
    print(f"释义：{quote.vernacular}")


if __name__ == "__main__":
    main()
