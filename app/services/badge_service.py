import io
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

from app.models.models import Participant, BadgeTemplate

# Directory where badge template backgrounds are stored
TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static", "badge_templates",
)


class BadgeEngineService:
    def generate_qr_image(self, qr_uuid: str) -> Image.Image:
        """Generates a PIL Image of a QR code encoding the UUID."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=3,
        )
        qr.add_data(qr_uuid)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Try to load a nice font, fallback to default."""
        font_candidates = ["arial.ttf", "ArialMT.ttf", "DejaVuSans.ttf", "Roboto-Regular.ttf"]
        for font_name in font_candidates:
            try:
                return ImageFont.truetype(font_name, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    def _draw_centered_text(self, draw: ImageDraw.Draw, text: str, x_pct: float, y_pct: float,
                            img_w: int, img_h: int, font: ImageFont.FreeTypeFont,
                            color: str = "black", align: str = "center"):
        """Draw text at percentage coordinates. Supports center/left/right alignment."""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Convert percentage to pixel
        px_x = int(img_w * x_pct / 100)
        px_y = int(img_h * y_pct / 100)

        if align == "center":
            px_x = px_x - text_w // 2
        elif align == "right":
            px_x = px_x - text_w

        draw.text((px_x, px_y - text_h // 2), text, fill=color, font=font)

    def generate_badge(self, participant: Participant, template: BadgeTemplate,
                       mode: str = "full") -> bytes:
        """
        Generate a single badge image.
        Modes:
            full    - Background template + Name + QR + Company
            minimal - White background + Name + QR + Company
            qr_only - Just the QR code centered
        Returns PNG bytes.
        """
        # Calculate pixel dimensions from inches + DPI
        dpi = template.dpi or 300
        w_px = int(template.width_inches * dpi)
        h_px = int(template.height_inches * dpi)
        layout = template.layout_config or {}

        if mode == "qr_only":
            return self._generate_qr_only(participant, w_px, h_px)
        elif mode == "minimal":
            bg = Image.new("RGBA", (w_px, h_px), "white")
        else:  # full
            bg = self._load_background(template, w_px, h_px)

        draw = ImageDraw.Draw(bg)

        # Draw text fields (name, company, etc.)
        for field, config in layout.items():
            if field == "qr":
                continue

            text = str(participant.data.get(field, ""))
            if not text:
                continue

            font_size_pct = config.get("font_size", 24)
            # Scale font size: percentage of badge height
            actual_font_size = max(int(h_px * font_size_pct / 1000), 12)
            font = self._get_font(actual_font_size)

            self._draw_centered_text(
                draw, text.upper(),
                config.get("x", 50), config.get("y", 50),
                w_px, h_px, font,
                color=config.get("color", "black"),
                align=config.get("align", "center"),
            )

        # Draw QR code
        qr_config = layout.get("qr", {"x": 50, "y": 50, "size": 25})
        qr_img = self.generate_qr_image(str(participant.qr_id))
        qr_size = int(min(w_px, h_px) * qr_config.get("size", 25) / 100)
        qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

        # Center QR at percentage position
        qr_x = int(w_px * qr_config.get("x", 50) / 100) - qr_size // 2
        qr_y = int(h_px * qr_config.get("y", 50) / 100) - qr_size // 2
        bg.paste(qr_img, (qr_x, qr_y), qr_img)

        # Return as PNG bytes
        output = io.BytesIO()
        bg.convert("RGB").save(output, format="PNG", dpi=(dpi, dpi))
        output.seek(0)
        return output.read()

    def _generate_qr_only(self, participant: Participant, w_px: int, h_px: int) -> bytes:
        """Generate a badge with just the QR code centered."""
        bg = Image.new("RGBA", (w_px, h_px), "white")
        qr_img = self.generate_qr_image(str(participant.qr_id))

        # QR takes up 60% of the smaller dimension
        qr_size = int(min(w_px, h_px) * 0.6)
        qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

        qr_x = (w_px - qr_size) // 2
        qr_y = (h_px - qr_size) // 2
        bg.paste(qr_img, (qr_x, qr_y), qr_img)

        output = io.BytesIO()
        bg.convert("RGB").save(output, format="PNG")
        output.seek(0)
        return output.read()

    def _load_background(self, template: BadgeTemplate, w_px: int, h_px: int) -> Image.Image:
        """Load and resize background image to exact badge dimensions."""
        filepath = os.path.join(TEMPLATES_DIR, template.background_image_path)
        if not os.path.exists(filepath):
            # Fallback to white if file not found
            return Image.new("RGBA", (w_px, h_px), "white")
        try:
            bg = Image.open(filepath).convert("RGBA")
            bg = bg.resize((w_px, h_px), Image.LANCZOS)
            return bg
        except Exception:
            return Image.new("RGBA", (w_px, h_px), "white")
