"""Renders Turkish-safe text/subtitle PNG overlays with Pillow.

The local Homebrew FFmpeg build in this environment does not include
``drawtext``/``libass``. Rendering text to transparent PNGs and compositing
them with FFmpeg's ``overlay`` filter is deterministic, supports Turkish
characters reliably, and keeps font access explicit and local.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from tezlify_studio.domain.exceptions.studio_exceptions import (
    CompositionFontException,
)
from tezlify_studio.domain.value_objects.video_composition import TextAnchor

FONT_CANDIDATES_REGULAR = [
    os.environ.get("TEZLIFY_FONT_PATH", ""),
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

FONT_CANDIDATES_BOLD = [
    os.environ.get("TEZLIFY_FONT_BOLD_PATH", ""),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


@dataclass(frozen=True)
class OverlayImage:
    path: str
    x: int
    y: int
    width: int
    height: int


def find_turkish_font(bold: bool = False) -> str:
    """Returns an absolute font path that supports Turkish glyphs."""

    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)

    # Last resort on Linux: ask fontconfig for a Turkish-capable sans font.
    fc_match = shutil.which("fc-match")
    if fc_match:
        try:
            result = subprocess.run(
                [fc_match, "-f", "%{file}", "sans:lang=tr"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            path = result.stdout.strip()
            if result.returncode == 0 and path and os.path.isfile(path):
                return os.path.abspath(path)
        except Exception:
            pass

    raise CompositionFontException(
        "Türkçe karakterleri destekleyen bir yazı tipi bulunamadı. "
        "TEZLIFY_FONT_PATH ortam değişkeniyle geçerli bir .ttf dosyası belirtin."
    )


def _parse_hex_color(value: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    clean = value.lstrip("#")
    return (
        int(clean[0:2], 16),
        int(clean[2:4], 16),
        int(clean[4:6], 16),
        alpha,
    )


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_width: int,
    max_chars_per_line: Optional[int] = None,
) -> List[str]:
    """Wraps text by pixel width and, optionally, by character count."""

    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n")]
    lines: List[str] = []

    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue

        words = paragraph.split(" ")
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            too_long = max_chars_per_line is not None and len(candidate) > max_chars_per_line
            if current and (width > max_width or too_long):
                lines.append(current)
                current = word
            else:
                current = candidate

            # Split an individual word that is wider than the safe area.
            while draw.textbbox((0, 0), current, font=font)[2] > max_width and len(current) > 1:
                split_at = len(current)
                while split_at > 1 and draw.textbbox((0, 0), current[:split_at], font=font)[2] > max_width:
                    split_at -= 1
                lines.append(current[:split_at].rstrip())
                current = current[split_at:].lstrip()

        if current:
            lines.append(current)

    return lines or [text]


def render_text_overlay(
    text: str,
    output_path: str,
    frame_width: int,
    frame_height: int,
    anchor: TextAnchor = TextAnchor.BOTTOM_CENTER,
    x_ratio: float = 0.5,
    y_ratio: float = 0.82,
    font_size: int = 64,
    color: str = "#FFFFFF",
    background_color: Optional[str] = "#000000",
    background_opacity: float = 0.55,
    max_width_ratio: float = 0.82,
    bold: bool = True,
    stroke_width: int = 0,
    max_chars_per_line: Optional[int] = None,
) -> OverlayImage:
    """Renders ``text`` to a tightly cropped transparent PNG and computes its position."""

    font_path = find_turkish_font(bold=bold)
    font = ImageFont.truetype(font_path, size=int(font_size))

    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    probe_draw = ImageDraw.Draw(probe)

    max_width = max(40, int(frame_width * max_width_ratio))
    lines = _wrap_text(text, font, probe_draw, max_width, max_chars_per_line)

    # Measure line widths/heights using the real font metrics.
    line_boxes = [probe_draw.textbbox((0, 0), line or " ", font=font, stroke_width=stroke_width) for line in lines]
    line_widths = [max(1, box[2] - box[0]) for box in line_boxes]
    ascent, descent = font.getmetrics()
    line_height = int((ascent + descent) * 1.12) + max(2, stroke_width * 2)

    padding = max(8, int(font_size * 0.32))
    content_width = max(line_widths) if line_widths else 1
    content_height = line_height * max(1, len(lines))
    image_width = min(frame_width, content_width + padding * 2 + stroke_width * 2)
    image_height = content_height + padding * 2 + stroke_width * 2

    image = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if background_color and background_opacity > 0:
        box_fill = _parse_hex_color(background_color, int(background_opacity * 255))
        radius = max(6, int(font_size * 0.18))
        draw.rounded_rectangle(
            [(0, 0), (image_width - 1, image_height - 1)],
            radius=radius,
            fill=box_fill,
        )

    text_fill = _parse_hex_color(color, 255)
    text_stroke = (0, 0, 0, 210) if stroke_width > 0 else None

    for index, line in enumerate(lines):
        line_w = line_widths[index] if index < len(line_widths) else 1
        x = padding + max(0, (content_width - line_w) // 2)
        y = padding + index * line_height
        draw.text(
            (x, y),
            line,
            font=font,
            fill=text_fill,
            stroke_width=stroke_width,
            stroke_fill=text_stroke,
            anchor="lt",
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    image.save(output_path, format="PNG")

    # Anchor placement (x_ratio/y_ratio refer to the chosen anchor point).
    if anchor in (TextAnchor.TOP_LEFT, TextAnchor.CENTER_LEFT, TextAnchor.BOTTOM_LEFT):
        x = int(frame_width * x_ratio)
    elif anchor in (TextAnchor.TOP_RIGHT, TextAnchor.CENTER_RIGHT, TextAnchor.BOTTOM_RIGHT):
        x = int(frame_width * x_ratio) - image_width
    else:
        x = int(frame_width * x_ratio) - image_width // 2

    if anchor in (TextAnchor.TOP_LEFT, TextAnchor.TOP_CENTER, TextAnchor.TOP_RIGHT):
        y = int(frame_height * y_ratio)
    elif anchor in (TextAnchor.BOTTOM_LEFT, TextAnchor.BOTTOM_CENTER, TextAnchor.BOTTOM_RIGHT):
        y = int(frame_height * y_ratio) - image_height
    else:
        y = int(frame_height * y_ratio) - image_height // 2

    margin = max(4, int(min(frame_width, frame_height) * 0.015))
    x = max(margin, min(x, frame_width - image_width - margin))
    y = max(margin, min(y, frame_height - image_height - margin))

    return OverlayImage(path=output_path, x=x, y=y, width=image_width, height=image_height)
