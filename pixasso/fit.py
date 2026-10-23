import io

from PIL import Image, ImageFilter, ImageOps

WIDTH, HEIGHT = 3840, 2160
TARGET_RATIO = WIDTH / HEIGHT
# Within this of 16:9 a crop takes off almost nothing, so the owner is not asked.
CROP_TOLERANCE = 0.03


def open_image(data: bytes) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def fits_screen(data: bytes) -> bool:
    img = open_image(data)
    return abs(img.width / img.height - TARGET_RATIO) / TARGET_RATIO <= CROP_TOLERANCE


def fit(data: bytes, force_crop: bool = False) -> bytes:
    """Return a 3840x2160 JPEG like the TV's own art: cropped to fill, or whole over a blurred fill."""
    img = open_image(data)
    out = cover(img) if force_crop or fits_screen(data) else blurred_fill(img)
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
