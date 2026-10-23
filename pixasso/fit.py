import io

from PIL import Image, ImageFilter, ImageOps

WIDTH, HEIGHT = 3840, 2160
TARGET_RATIO = WIDTH / HEIGHT
# Cropping more than this off a picture loses what it is about; past it the whole picture goes over a blurred fill.
CROP_TOLERANCE = 0.12


def fit(data: bytes, force_crop: bool = False) -> bytes:
    """Return a 3840x2160 JPEG: crop when the picture is close to 16:9, otherwise blurred fill."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    near_screen = abs(img.width / img.height - TARGET_RATIO) / TARGET_RATIO <= CROP_TOLERANCE
    out = cover(img) if near_screen or force_crop else blurred_fill(img)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def cover(img: Image.Image) -> Image.Image:
    return ImageOps.fit(img, (WIDTH, HEIGHT), Image.LANCZOS)


def blurred_fill(img: Image.Image) -> Image.Image:
    # Blur a small copy and scale it up: blurring at 4K takes seconds on the Pi.
    background = ImageOps.fit(img, (WIDTH // 8, HEIGHT // 8), Image.BILINEAR)
    background = background.filter(ImageFilter.GaussianBlur(6)).resize((WIDTH, HEIGHT), Image.BILINEAR)
    foreground = ImageOps.contain(img, (WIDTH, HEIGHT), Image.LANCZOS)
    background.paste(foreground, ((WIDTH - foreground.width) // 2, (HEIGHT - foreground.height) // 2))
    return background
