from PIL import Image

from app.routers import home_blocks


def test_fill_image_size_reads_uploaded_image(tmp_path, monkeypatch):
    Image.new("RGB", (120, 40)).save(tmp_path / "a.png")
    monkeypatch.setattr(home_blocks, "UPLOADS_DIR", str(tmp_path))
    home_blocks._image_size.cache_clear()
    props = home_blocks._fill_image_size({"background_image_url": "/uploads/a.png"})
    assert (props["background_image_width"], props["background_image_height"]) == (120, 40)


def test_fill_image_size_ignores_external_or_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(home_blocks, "UPLOADS_DIR", str(tmp_path))
    home_blocks._image_size.cache_clear()
    for url in ("https://x.com/a.png", "/uploads/nope.png", None):
        props = home_blocks._fill_image_size({"background_image_url": url})
        assert props["background_image_width"] is None
