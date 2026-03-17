#!/usr/bin/env python3
"""
Site Ripper — Extract design system from any website via Playwright.

Screenshots pages at multiple breakpoints, extracts CSS (colors, fonts,
spacing, layout), downloads key assets (logo, hero, favicon), and outputs
a PressLess-compatible design system.

Usage:
    import sys; sys.path.insert(0, 'tools/lib')
    from site_ripper import SiteRipper

    ripper = SiteRipper()
    ds = ripper.rip("https://example.com", output_dir="storage/figma/example/")
    # → design system dict + screenshots + assets saved to output_dir

CLI:
    python3 site_ripper.py --url "https://example.com"
    python3 site_ripper.py --url "https://example.com" --output ./ripped/ --pages "/,/about,/contact"
    python3 site_ripper.py --url "https://example.com" --pressless

Requires:
    pip install playwright
    playwright install chromium
"""

import os
import re
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import Counter
from urllib.parse import urljoin, urlparse

try:
    from dotenv import load_dotenv
    BRAIN = Path(__file__).parent.parent.parent.resolve()
    load_dotenv(str(BRAIN / '.env'))
except Exception:
    pass


class SiteRipper:
    """Extract design system from any website using Playwright."""

    BREAKPOINTS = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 375, "height": 812},
    }

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright
            self._playwright_available = True
        except ImportError:
            self._playwright_available = False

    def rip(self, url: str, output_dir: str = "./ripped",
            pages: Optional[List[str]] = None,
            breakpoints: Optional[List[str]] = None) -> Dict[str, Any]:
        """Rip design system from a website.

        Args:
            url: Base URL to analyze
            output_dir: Where to save screenshots and assets
            pages: URL paths to visit (default: just "/")
            breakpoints: Which breakpoints to screenshot (default: all)

        Returns:
            Design system dict with palette, typography, spacing, assets, screenshots
        """
        if not self._playwright_available:
            raise ImportError("playwright required: pip install playwright && playwright install chromium")

        from playwright.sync_api import sync_playwright

        if pages is None:
            pages = ["/"]
        if breakpoints is None:
            breakpoints = list(self.BREAKPOINTS.keys())

        out = Path(output_dir)
        (out / "screenshots").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(parents=True, exist_ok=True)

        base_url = url.rstrip("/")
        result = {
            "source": "site_ripper",
            "url": base_url,
            "screenshots": [],
            "assets": [],
            "css_data": {},
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for page_path in pages:
                full_url = base_url + page_path if page_path != "/" else base_url
                slug = page_path.strip("/").replace("/", "-") or "home"

                for bp_name in breakpoints:
                    bp = self.BREAKPOINTS.get(bp_name)
                    if not bp:
                        continue

                    context = browser.new_context(
                        viewport={"width": bp["width"], "height": bp["height"]},
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    )
                    page = context.new_page()

                    try:
                        page.goto(full_url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1000)  # let animations settle

                        # Screenshot full page
                        ss_path = str(out / "screenshots" / f"{slug}-{bp_name}.png")
                        page.screenshot(path=ss_path, full_page=True)
                        result["screenshots"].append({
                            "page": page_path,
                            "breakpoint": bp_name,
                            "path": ss_path,
                        })

                        # Extract CSS data (only on desktop, once per page)
                        if bp_name == "desktop":
                            css_data = self._extract_css(page)
                            result["css_data"][page_path] = css_data

                            # Download assets on first page only
                            if page_path == pages[0]:
                                assets = self._download_assets(page, base_url, str(out / "assets"))
                                result["assets"] = assets

                    except Exception as e:
                        result.setdefault("errors", []).append({
                            "page": page_path,
                            "breakpoint": bp_name,
                            "error": str(e),
                        })
                    finally:
                        context.close()

            browser.close()

        # Build design system from extracted CSS
        result["design_system"] = self._build_design_system(result)
        return result

    def _extract_css(self, page) -> Dict[str, Any]:
        """Extract computed CSS data from the page via JavaScript."""

        css_data = page.evaluate("""() => {
            const result = {
                colors: {},
                fonts: {},
                font_sizes: {},
                spacing: [],
                border_radius: {},
                bg_colors: {},
                layout: {},
            };

            // Walk all visible elements
            const elements = document.querySelectorAll('*');
            const colorCount = {};
            const bgColorCount = {};
            const fontCount = {};
            const sizeCount = {};
            const radiusCount = {};

            for (const el of elements) {
                const style = window.getComputedStyle(el);

                // Skip invisible
                if (style.display === 'none' || style.visibility === 'hidden') continue;

                // Colors
                const color = style.color;
                if (color && color !== 'rgba(0, 0, 0, 0)') {
                    colorCount[color] = (colorCount[color] || 0) + 1;
                }

                // Background colors
                const bgColor = style.backgroundColor;
                if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                    bgColorCount[bgColor] = (bgColorCount[bgColor] || 0) + 1;
                }

                // Fonts
                const family = style.fontFamily.split(',')[0].trim().replace(/['"]/g, '');
                if (family) {
                    fontCount[family] = (fontCount[family] || 0) + 1;
                }

                // Font sizes
                const size = style.fontSize;
                if (size) {
                    sizeCount[size] = (sizeCount[size] || 0) + 1;
                }

                // Border radius
                const radius = style.borderRadius;
                if (radius && radius !== '0px') {
                    radiusCount[radius] = (radiusCount[radius] || 0) + 1;
                }
            }

            result.colors = colorCount;
            result.bg_colors = bgColorCount;
            result.fonts = fontCount;
            result.font_sizes = sizeCount;
            result.border_radius = radiusCount;

            // Layout: detect header, hero, footer
            const header = document.querySelector('header, [role="banner"], nav');
            const footer = document.querySelector('footer, [role="contentinfo"]');
            const hero = document.querySelector('.hero, [class*="hero"], [class*="banner"], section:first-of-type');

            result.layout = {
                has_header: !!header,
                has_footer: !!footer,
                has_hero: !!hero,
                header_height: header ? window.getComputedStyle(header).height : null,
                body_bg: window.getComputedStyle(document.body).backgroundColor,
                body_font: window.getComputedStyle(document.body).fontFamily.split(',')[0].trim().replace(/['"]/g, ''),
                body_font_size: window.getComputedStyle(document.body).fontSize,
                body_line_height: window.getComputedStyle(document.body).lineHeight,
                body_color: window.getComputedStyle(document.body).color,
            };

            // H1-H6 styles
            result.headings = {};
            for (let i = 1; i <= 6; i++) {
                const h = document.querySelector('h' + i);
                if (h) {
                    const hs = window.getComputedStyle(h);
                    result.headings['h' + i] = {
                        font_family: hs.fontFamily.split(',')[0].trim().replace(/['"]/g, ''),
                        font_size: hs.fontSize,
                        font_weight: hs.fontWeight,
                        line_height: hs.lineHeight,
                        color: hs.color,
                    };
                }
            }

            return result;
        }""")

        return css_data

    def _download_assets(self, page, base_url: str, output_dir: str) -> List[Dict[str, str]]:
        """Download key assets: logo, favicon, hero image, OG image."""
        import requests

        assets = []
        out = Path(output_dir)

        # Find asset URLs via JS
        asset_urls = page.evaluate("""(baseUrl) => {
            const assets = [];

            // Favicon
            const favicon = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
            if (favicon) assets.push({type: 'favicon', url: favicon.href});

            // Apple touch icon
            const apple = document.querySelector('link[rel="apple-touch-icon"]');
            if (apple) assets.push({type: 'apple-icon', url: apple.href});

            // OG image
            const og = document.querySelector('meta[property="og:image"]');
            if (og) assets.push({type: 'og-image', url: og.content});

            // Logo (heuristic: img in header/nav with "logo" in src/alt/class)
            const logoSelectors = [
                'header img[class*="logo"]',
                'header img[alt*="logo" i]',
                'header img[src*="logo"]',
                'nav img[class*="logo"]',
                'nav img[alt*="logo" i]',
                'nav img[src*="logo"]',
                'img[class*="logo"]',
                'img[alt*="logo" i]',
                'img[src*="logo"]',
                '.logo img',
                '#logo img',
            ];
            for (const sel of logoSelectors) {
                const logo = document.querySelector(sel);
                if (logo && logo.src) {
                    assets.push({type: 'logo', url: logo.src});
                    break;
                }
            }

            // SVG logo
            const svgLogo = document.querySelector('header svg, nav svg, .logo svg');
            if (svgLogo) {
                const svg = svgLogo.outerHTML;
                assets.push({type: 'logo-svg', svg: svg});
            }

            // Hero image (first large image or background)
            const heroImg = document.querySelector('.hero img, [class*="hero"] img, section:first-of-type img');
            if (heroImg && heroImg.src) {
                assets.push({type: 'hero', url: heroImg.src});
            }

            return assets;
        }""", base_url)

        for asset in asset_urls:
            asset_type = asset.get("type", "unknown")

            # SVG inline — save directly
            if asset.get("svg"):
                svg_path = out / f"{asset_type}.svg"
                svg_path.write_text(asset["svg"])
                assets.append({"type": asset_type, "path": str(svg_path)})
                continue

            url = asset.get("url")
            if not url:
                continue

            # Make absolute
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(base_url, url)

            try:
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })
                if resp.status_code == 200 and len(resp.content) > 100:
                    # Determine extension
                    ct = resp.headers.get("content-type", "")
                    ext = "png"
                    if "svg" in ct:
                        ext = "svg"
                    elif "jpeg" in ct or "jpg" in ct:
                        ext = "jpg"
                    elif "webp" in ct:
                        ext = "webp"
                    elif "gif" in ct:
                        ext = "gif"
                    elif "ico" in ct or "x-icon" in ct:
                        ext = "ico"

                    filepath = out / f"{asset_type}.{ext}"
                    filepath.write_bytes(resp.content)
                    assets.append({"type": asset_type, "path": str(filepath), "url": url})
            except Exception:
                pass

        return assets

    def _build_design_system(self, rip_result: Dict) -> Dict[str, Any]:
        """Build PressLess-compatible design system from ripped CSS data."""

        # Merge CSS data from all pages
        all_colors = Counter()
        all_bg_colors = Counter()
        all_fonts = Counter()
        all_sizes = Counter()
        all_radius = Counter()
        layout = {}
        headings = {}

        for page_path, css in rip_result.get("css_data", {}).items():
            for color, count in css.get("colors", {}).items():
                all_colors[color] += count
            for color, count in css.get("bg_colors", {}).items():
                all_bg_colors[color] += count
            for font, count in css.get("fonts", {}).items():
                all_fonts[font] += count
            for size, count in css.get("font_sizes", {}).items():
                all_sizes[size] += count
            for radius, count in css.get("border_radius", {}).items():
                all_radius[radius] += count
            if not layout and css.get("layout"):
                layout = css["layout"]
            if not headings and css.get("headings"):
                headings = css["headings"]

        # Convert CSS colors to hex
        hex_colors = []
        for color_str, count in (list(all_colors.most_common(20)) + list(all_bg_colors.most_common(20))):
            hex_val = self._css_color_to_hex(color_str)
            if hex_val:
                hex_colors.append({"hex": hex_val, "count": count, "source": color_str})

        # Deduplicate by hex
        seen = set()
        unique_colors = []
        for c in hex_colors:
            if c["hex"] not in seen:
                seen.add(c["hex"])
                unique_colors.append(c)

        # Infer palette
        palette = self._infer_palette([c["hex"] for c in unique_colors], layout)

        # Typography
        fonts_ranked = all_fonts.most_common(5)
        sizes_ranked = all_sizes.most_common(15)

        heading_font = None
        body_font = fonts_ranked[0][0] if fonts_ranked else "Inter"

        # Try to distinguish heading vs body font from headings
        if headings:
            h1 = headings.get("h1", {})
            heading_font = h1.get("font_family")

        if not heading_font and len(fonts_ranked) > 1:
            heading_font = fonts_ranked[1][0]
        elif not heading_font:
            heading_font = body_font

        # If body is same as heading but we have another font, swap
        if heading_font == body_font and len(fonts_ranked) > 1:
            body_font = fonts_ranked[1][0]

        typography = {
            "heading_font": heading_font,
            "body_font": body_font,
            "all_fonts": [f[0] for f in fonts_ranked],
            "sizes": [s[0] for s in sizes_ranked],
            "headings": headings,
            "body_size": layout.get("body_font_size"),
            "body_line_height": layout.get("body_line_height"),
        }

        return {
            "source": "site_ripper",
            "url": rip_result.get("url"),
            "palette": palette,
            "typography": typography,
            "border_radius": [r[0] for r in all_radius.most_common(5)],
            "layout": layout,
            "colors_raw": unique_colors[:15],
            "screenshots": rip_result.get("screenshots", []),
            "assets": rip_result.get("assets", []),
        }

    def _infer_palette(self, hex_colors: List[str], layout: Dict = None) -> Dict[str, str]:
        """Infer palette from extracted colors."""
        if not hex_colors:
            return {"bg": "#ffffff", "text": "#000000", "accent": "#3366ff", "theme": "light"}

        # Use body bg/color as primary hints
        bg_hex = None
        text_hex = None
        if layout:
            bg_hex = self._css_color_to_hex(layout.get("body_bg", ""))
            text_hex = self._css_color_to_hex(layout.get("body_color", ""))

        def luminance(hex_c):
            hex_c = hex_c.lstrip("#")[:6]
            if len(hex_c) != 6:
                return 128
            r, g, b = int(hex_c[:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            return 0.299 * r + 0.587 * g + 0.114 * b

        def saturation(hex_c):
            hex_c = hex_c.lstrip("#")[:6]
            if len(hex_c) != 6:
                return 0
            r, g, b = int(hex_c[:2], 16) / 255, int(hex_c[2:4], 16) / 255, int(hex_c[4:6], 16) / 255
            mx, mn = max(r, g, b), min(r, g, b)
            return (mx - mn) / mx if mx > 0 else 0

        # Find accent (most saturated, not too dark/light)
        candidates = [c for c in hex_colors if 30 < luminance(c) < 230]
        if candidates:
            accent = max(candidates, key=saturation)
            if saturation(accent) < 0.15:
                accent = "#3366ff"
        else:
            accent = "#3366ff"

        if bg_hex and text_hex:
            theme = "dark" if luminance(bg_hex) < 128 else "light"
            return {"bg": bg_hex, "text": text_hex, "accent": accent, "theme": theme}

        # Fallback: darkest/lightest
        sorted_by_lum = sorted(hex_colors[:10], key=luminance)
        darkest = sorted_by_lum[0]
        lightest = sorted_by_lum[-1]

        if luminance(darkest) < 50:
            return {"bg": darkest, "text": lightest, "accent": accent, "theme": "dark"}
        return {"bg": lightest, "text": darkest, "accent": accent, "theme": "light"}

    @staticmethod
    def _css_color_to_hex(color_str: str) -> Optional[str]:
        """Convert CSS color (rgb/rgba/hex) to hex string."""
        if not color_str:
            return None

        color_str = color_str.strip()

        # Already hex
        if color_str.startswith("#"):
            return color_str[:7]

        # rgb(r, g, b) or rgba(r, g, b, a)
        match = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"#{r:02x}{g:02x}{b:02x}"

        return None


# =========================================================
# CLI
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Site Ripper — Extract design system from any website")
    parser.add_argument("--url", required=True, help="Website URL to rip")
    parser.add_argument("--output", type=str, default="./ripped", help="Output directory")
    parser.add_argument("--pages", type=str, default="/", help="Comma-separated paths to visit (e.g. '/,/about,/contact')")
    parser.add_argument("--breakpoints", type=str, default="desktop,tablet,mobile", help="Breakpoints to screenshot")
    parser.add_argument("--pressless", action="store_true", help="Output PressLess-compatible design system JSON")
    args = parser.parse_args()

    pages = [p.strip() for p in args.pages.split(",")]
    breakpoints = [b.strip() for b in args.breakpoints.split(",")]

    ripper = SiteRipper()
    result = ripper.rip(args.url, output_dir=args.output, pages=pages, breakpoints=breakpoints)

    if args.pressless:
        print(json.dumps(result.get("design_system", {}), indent=2, ensure_ascii=False))
    else:
        ds = result.get("design_system", {})
        print(f"\n🎨 Site: {args.url}")
        print(f"Theme: {ds.get('palette', {}).get('theme', '?')}")

        palette = ds.get("palette", {})
        print(f"\nPalette:")
        print(f"  BG:     {palette.get('bg')}")
        print(f"  Text:   {palette.get('text')}")
        print(f"  Accent: {palette.get('accent')}")

        typo = ds.get("typography", {})
        print(f"\nTypography:")
        print(f"  Heading: {typo.get('heading_font')}")
        print(f"  Body:    {typo.get('body_font')}")
        print(f"  Sizes:   {typo.get('sizes', [])[:8]}")

        print(f"\nBorder radius: {ds.get('border_radius', [])[:5]}")

        ss = result.get("screenshots", [])
        print(f"\nScreenshots: {len(ss)}")
        for s in ss:
            print(f"  {s['page']} @ {s['breakpoint']} → {s['path']}")

        assets = result.get("assets", [])
        print(f"\nAssets: {len(assets)}")
        for a in assets:
            print(f"  {a['type']} → {a.get('path', '?')}")


if __name__ == "__main__":
    main()
