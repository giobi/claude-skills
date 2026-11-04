"""Tests for slideshow.render(): themes, brand fill, fallbacks.
Run: python3 test_slideshow.py   (or pytest)"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# share.py needs a brain root to import; a throwaway one is enough here.
_tmp = tempfile.mkdtemp()
(Path(_tmp) / "boot").mkdir()
os.environ["BRAIN_ROOT"] = _tmp
sys.path.insert(0, str(HERE))
import slideshow  # noqa: E402

BRAND = {
    "primary": "#1b9cd8", "secondary": "#093449", "accent": "#04e4f8",
    "logo_html": '<img id="light-logo">', "logo_dark_html": '<img id="dark-logo">',
}
TPL = slideshow.OWN_TEMPLATE.read_text(encoding="utf-8")
SLIDES = slideshow.build_deck("Quorn", "Mission status", [("Pipeline", ["3 candidates"])], False, "")


def test_light_uses_light_logo_and_brand_colours():
    out = slideshow.render(TPL, "Quorn", SLIDES, "light", BRAND)
    assert 'data-theme="light"' in out
    assert 'id="light-logo"' in out and 'id="dark-logo"' not in out
    assert "--primary:#1b9cd8" in out and "--secondary:#093449" in out
    assert "{{" not in out, "unfilled marker left in the page"


def test_dark_uses_dark_logo():
    out = slideshow.render(TPL, "Quorn", SLIDES, "dark", BRAND)
    assert 'data-theme="dark"' in out
    assert 'id="dark-logo"' in out and 'id="light-logo"' not in out


def test_dark_without_dark_logo_falls_back_to_normal_logo():
    b = dict(BRAND, logo_dark_html="")
    out = slideshow.render(TPL, "Quorn", SLIDES, "dark", b)
    assert 'id="light-logo"' in out


def test_no_brand_renders_neutral_deck():
    out = slideshow.render(TPL, "Quorn", SLIDES, "light", {})
    assert slideshow.FALLBACK_PRIMARY in out
    assert 'aria-hidden="true"' in out
    assert "{{" not in out


def test_title_slide_has_big_logo_and_content_kept():
    out = slideshow.render(TPL, "Quorn", SLIDES, "light", BRAND)
    assert '<div class="brand-title"><img id="light-logo">' in out
    assert "<h2>Pipeline</h2>" in out and "3 candidates" in out


def test_inline_svg_logo_becomes_img_so_copies_do_not_share_ids():
    b = dict(BRAND, logo_html='<svg><defs><linearGradient id="g"/></defs></svg>')
    out = slideshow.render(TPL, "Quorn", SLIDES, "light", b)
    assert "<svg><defs>" not in out
    assert out.count('src="data:image/svg+xml;base64,') == 2


def test_logo_file_from_svg_and_png():
    import base64
    assert slideshow.logo_file("<svg a='1'></svg>") == ("logo.svg", b"<svg a='1'></svg>")
    png = base64.b64encode(b"PNGDATA").decode()
    assert slideshow.logo_file(f'<img src="data:image/png;base64,{png}" alt="">') == ("logo.png", b"PNGDATA")
    assert slideshow.logo_file("") is None


def test_linked_logo_keeps_page_small():
    big = dict(BRAND, logo_html="<svg>" + "x" * 100000 + "</svg>")
    out = slideshow.render(TPL, "Quorn", SLIDES, "light", big, "logo.svg")
    assert out.count('<img src="logo.svg" alt="">') == 2
    assert len(out) < 20000


def test_title_is_escaped():
    out = slideshow.render(TPL, "R&D <deck>", SLIDES, "light", BRAND)
    assert "<title>R&amp;D &lt;deck&gt;</title>" in out


def test_old_shared_template_still_works():
    old = "<title>{title}</title><style>a{{b:c}}</style>{slides_html}"
    out = slideshow.render(old, "T", "<section>x</section>", "dark", BRAND)
    assert out == "<title>T</title><style>a{b:c}</style><section>x</section>"


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
