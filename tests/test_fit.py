import io

from PIL import Image

from pixasso import fit


def jpeg(width: int, height: int, color=(200, 40, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "JPEG")
    return buf.getvalue()


def size_of(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_near_16_9_is_cropped_to_fill():
    out = Image.open(io.BytesIO(fit.fit(jpeg(4000, 2400))))
    assert out.size == (fit.WIDTH, fit.HEIGHT)
    assert out.getpixel((5, 5))[0] > 150


def test_panorama_is_shown_whole_over_a_blurred_fill():
    out = Image.open(io.BytesIO(fit.fit(jpeg(4000, 1000, (200, 40, 40)))))
    assert out.size == (fit.WIDTH, fit.HEIGHT)
    centre = out.getpixel((fit.WIDTH // 2, fit.HEIGHT // 2))
    assert centre[0] > 150 and centre[1] < 100


def test_portrait_keeps_the_whole_picture_over_a_blurred_fill():
    out = Image.open(io.BytesIO(fit.fit(jpeg(1000, 2000))))
    assert out.size == (fit.WIDTH, fit.HEIGHT)
    centre = out.getpixel((fit.WIDTH // 2, fit.HEIGHT // 2))
    assert centre[0] > 150 and centre[1] < 100


def test_force_crop_on_portrait_fills_the_screen():
    assert size_of(fit.fit(jpeg(1000, 2000), force_crop=True)) == (fit.WIDTH, fit.HEIGHT)


def test_small_picture_is_scaled_up():
    assert size_of(fit.fit(jpeg(320, 180))) == (fit.WIDTH, fit.HEIGHT)
