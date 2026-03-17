#!/usr/bin/env python3
"""
Figma Parser — Extract design system from Figma files via REST API.

Extracts colors, fonts, layout grids, spacing, and exports frames as images.
Requires FIGMA_ACCESS_TOKEN in .env (free, from figma.com/developers).

Usage:
    import sys; sys.path.insert(0, 'tools/lib')
    from figma_parser import FigmaParser

    fp = FigmaParser()  # reads FIGMA_ACCESS_TOKEN from .env

    # Parse a Figma URL
    data = fp.parse_url("https://www.figma.com/design/ABC123/My-Design")

    # Get design system
    ds = fp.extract_design_system(data)
    # → {"colors": [...], "fonts": [...], "spacing": [...], "layout": {...}}

    # Export frames as images
    images = fp.export_frames(file_key, node_ids, format="png", scale=2)
    # → {"node_id": "https://...image_url..."}

CLI:
    python3 figma_parser.py --url "https://figma.com/design/ABC/Name"
    python3 figma_parser.py --url "..." --export png --scale 2 --output ./assets/
    python3 figma_parser.py --url "..." --design-system
"""

import os
import re
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from collections import Counter

try:
    from dotenv import load_dotenv
    BRAIN = Path(__file__).parent.parent.parent.resolve()
    load_dotenv(str(BRAIN / '.env'))
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None


class FigmaParser:
    """Parse Figma files and extract design system data."""

    API_BASE = "https://api.figma.com/v1"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("FIGMA_ACCESS_TOKEN")
        if not self.token:
            raise ValueError(
                "FIGMA_ACCESS_TOKEN not found. "
                "Get one at https://www.figma.com/developers/api#access-tokens"
            )
        self.headers = {"X-Figma-Token": self.token}

    # =========================================================
    # URL PARSING
    # =========================================================

    @staticmethod
    def parse_figma_url(url: str) -> Dict[str, Optional[str]]:
        """Extract file_key and node_id from a Figma URL.

        Supports:
        - https://www.figma.com/design/FILE_KEY/Name
        - https://www.figma.com/file/FILE_KEY/Name
        - https://www.figma.com/proto/FILE_KEY/Name
        - https://www.figma.com/design/FILE_KEY/Name?node-id=123-456

        Returns:
            {"file_key": str, "node_id": str|None, "url_type": str}
        """
        result = {"file_key": None, "node_id": None, "url_type": None}

        patterns = [
            r'figma\.com/(design|file|proto)/([a-zA-Z0-9]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                result["url_type"] = match.group(1)
                result["file_key"] = match.group(2)
                break

        # Extract node-id from query params
        node_match = re.search(r'node-id=([^&]+)', url)
        if node_match:
            result["node_id"] = node_match.group(1).replace('-', ':')

        return result

    # =========================================================
    # API CALLS
    # =========================================================

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated GET request to Figma API."""
        if not requests:
            raise ImportError("requests library required: pip install requests")

        resp = requests.get(
            f"{self.API_BASE}{endpoint}",
            headers=self.headers,
            params=params or {},
            timeout=60,
        )

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403:
            raise PermissionError(f"Access denied. Check token and file sharing settings.")
        elif resp.status_code == 404:
            raise FileNotFoundError(f"File not found. Check the URL/file_key.")
        else:
            raise Exception(f"Figma API error {resp.status_code}: {resp.text[:200]}")

    def get_file(self, file_key: str, depth: Optional[int] = None,
                 node_ids: Optional[List[str]] = None) -> Dict:
        """Get file structure from Figma API.

        Args:
            file_key: The file key from the Figma URL
            depth: How deep to traverse the node tree (None = full)
            node_ids: Specific nodes to retrieve

        Returns:
            Full file response with document tree, components, styles
        """
        params = {}
        if depth is not None:
            params["depth"] = depth
        if node_ids:
            params["ids"] = ",".join(node_ids)

        return self._get(f"/files/{file_key}", params)

    def get_file_styles(self, file_key: str) -> Dict:
        """Get published styles from a file."""
        return self._get(f"/files/{file_key}/styles")

    def export_images(self, file_key: str, node_ids: List[str],
                      format: str = "png", scale: float = 2) -> Dict[str, str]:
        """Export nodes as images.

        Args:
            file_key: File key
            node_ids: List of node IDs to export
            format: "png", "jpg", "svg", or "pdf"
            scale: 0.01 to 4 (default 2x for retina)

        Returns:
            Dict mapping node_id → image URL (expires in 30 days)
        """
        params = {
            "ids": ",".join(node_ids),
            "format": format,
            "scale": scale,
        }
        if format == "svg":
            params["svg_outline_text"] = "true"
            params["svg_include_id"] = "true"

        result = self._get(f"/images/{file_key}", params)
        return result.get("images", {})

    # =========================================================
    # DESIGN SYSTEM EXTRACTION
    # =========================================================

    def parse_url(self, url: str, depth: Optional[int] = None) -> Dict:
        """Parse a Figma URL and return the full file data.

        Convenience method: URL → file_key → API call → data.
        """
        parsed = self.parse_figma_url(url)
        if not parsed["file_key"]:
            raise ValueError(f"Could not extract file key from URL: {url}")

        file_data = self.get_file(parsed["file_key"], depth=depth)
        file_data["_parsed_url"] = parsed
        return file_data

    def extract_design_system(self, file_data: Dict) -> Dict[str, Any]:
        """Extract design system from file data.

        Walks the node tree and extracts:
        - Colors (fills, strokes)
        - Fonts (family, size, weight, line height)
        - Spacing patterns
        - Layout grids
        - Component inventory

        Returns:
            Structured design system dict
        """
        ds = {
            "colors": [],
            "fonts": [],
            "spacing": [],
            "layout_grids": [],
            "components": [],
            "frames": [],
            "file_name": file_data.get("name", ""),
            "last_modified": file_data.get("lastModified", ""),
        }

        # Collect raw data
        color_counter = Counter()
        font_counter = Counter()
        spacing_values = set()

        document = file_data.get("document", {})
        self._walk_nodes(document, ds, color_counter, font_counter, spacing_values)

        # Deduplicate and sort colors by frequency
        ds["colors"] = [
            {"hex": hex_val, "count": count}
            for hex_val, count in color_counter.most_common(20)
        ]

        # Deduplicate fonts
        ds["fonts"] = [
            {"spec": spec, "count": count}
            for spec, count in font_counter.most_common(20)
        ]

        # Sort spacing
        ds["spacing"] = sorted(spacing_values)

        # Extract from styles metadata
        for style_id, style_meta in file_data.get("styles", {}).items():
            style_type = style_meta.get("styleType", "")
            if style_type == "FILL":
                ds.setdefault("named_colors", []).append({
                    "name": style_meta.get("name", ""),
                    "description": style_meta.get("description", ""),
                })
            elif style_type == "TEXT":
                ds.setdefault("named_text_styles", []).append({
                    "name": style_meta.get("name", ""),
                    "description": style_meta.get("description", ""),
                })

        return ds

    def _walk_nodes(self, node: Dict, ds: Dict, colors: Counter,
                    fonts: Counter, spacing: set, depth: int = 0):
        """Recursively walk the node tree extracting design data."""

        node_type = node.get("type", "")

        # Collect top-level frames
        if node_type == "FRAME" and depth <= 2:
            ds["frames"].append({
                "id": node.get("id"),
                "name": node.get("name", ""),
                "width": node.get("absoluteBoundingBox", {}).get("width"),
                "height": node.get("absoluteBoundingBox", {}).get("height"),
            })

        # Collect components
        if node_type == "COMPONENT":
            ds["components"].append({
                "id": node.get("id"),
                "name": node.get("name", ""),
            })

        # Extract colors from fills
        for fill in node.get("fills", []):
            if fill.get("type") == "SOLID" and "color" in fill:
                c = fill["color"]
                hex_color = self._rgba_to_hex(c)
                colors[hex_color] += 1

        # Extract colors from strokes
        for stroke in node.get("strokes", []):
            if stroke.get("type") == "SOLID" and "color" in stroke:
                c = stroke["color"]
                hex_color = self._rgba_to_hex(c)
                colors[hex_color] += 1

        # Extract fonts from text nodes
        if node_type == "TEXT":
            style = node.get("style", {})
            family = style.get("fontFamily", "")
            size = style.get("fontSize", 0)
            weight = style.get("fontWeight", 400)
            if family:
                spec = f"{family}/{weight}/{size}px"
                fonts[spec] += 1

        # Extract spacing from auto-layout
        if "itemSpacing" in node:
            spacing.add(node["itemSpacing"])
        if "paddingTop" in node:
            for pad_key in ["paddingTop", "paddingBottom", "paddingLeft", "paddingRight"]:
                val = node.get(pad_key)
                if val and val > 0:
                    spacing.add(val)

        # Extract layout grids
        for grid in node.get("layoutGrids", []):
            ds["layout_grids"].append({
                "pattern": grid.get("pattern"),  # COLUMNS, ROWS, GRID
                "count": grid.get("count"),
                "gutter_size": grid.get("gutterSize"),
                "offset": grid.get("offset"),
                "alignment": grid.get("alignment"),  # MIN, CENTER, STRETCH
            })

        # Recurse children
        for child in node.get("children", []):
            self._walk_nodes(child, ds, colors, fonts, spacing, depth + 1)

    @staticmethod
    def _rgba_to_hex(color: Dict) -> str:
        """Convert Figma RGBA (0-1 floats) to hex string."""
        r = int(color.get("r", 0) * 255)
        g = int(color.get("g", 0) * 255)
        b = int(color.get("b", 0) * 255)
        a = color.get("a", 1)
        if a < 1:
            return f"#{r:02x}{g:02x}{b:02x}{int(a*255):02x}"
        return f"#{r:02x}{g:02x}{b:02x}"

    # =========================================================
    # CONVENIENCE: PRESSLESS INTEGRATION
    # =========================================================

    def to_pressless_design_system(self, file_data: Dict) -> Dict[str, Any]:
        """Convert Figma file into PressLess-compatible design system.

        Returns a dict ready to feed into PressLess variant generation:
        - palette: primary, secondary, accent, bg, text colors
        - typography: heading_font, body_font, sizes
        - spacing: scale
        - layout: grid info
        """
        ds = self.extract_design_system(file_data)

        # Infer palette from most used colors
        hex_colors = [c["hex"] for c in ds["colors"]]
        palette = self._infer_palette(hex_colors)

        # Infer typography
        font_families = set()
        font_sizes = set()
        for f in ds["fonts"]:
            parts = f["spec"].split("/")
            font_families.add(parts[0])
            try:
                font_sizes.add(float(parts[2].replace("px", "")))
            except (IndexError, ValueError):
                pass

        # Infer heading vs body font
        families_list = list(font_families)
        typography = {
            "heading_font": families_list[0] if families_list else "Inter",
            "body_font": families_list[1] if len(families_list) > 1 else families_list[0] if families_list else "Inter",
            "sizes": sorted(font_sizes),
            "all_fonts": families_list,
        }

        return {
            "source": "figma",
            "file_name": ds["file_name"],
            "palette": palette,
            "typography": typography,
            "spacing": ds["spacing"],
            "layout_grids": ds["layout_grids"],
            "frames": ds["frames"],
            "components": ds["components"],
            "raw_colors": ds["colors"][:10],
            "raw_fonts": ds["fonts"][:10],
        }

    @staticmethod
    def _infer_palette(hex_colors: List[str]) -> Dict[str, str]:
        """Infer a palette from most-used colors.

        Heuristic: darkest = bg or text, lightest = bg or text,
        most saturated = accent/primary.
        """
        if not hex_colors:
            return {"bg": "#ffffff", "text": "#000000", "accent": "#3366ff"}

        def luminance(hex_c: str) -> float:
            hex_c = hex_c.lstrip("#")[:6]
            r, g, b = int(hex_c[:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            return 0.299 * r + 0.587 * g + 0.114 * b

        def saturation(hex_c: str) -> float:
            hex_c = hex_c.lstrip("#")[:6]
            r, g, b = int(hex_c[:2], 16) / 255, int(hex_c[2:4], 16) / 255, int(hex_c[4:6], 16) / 255
            max_c, min_c = max(r, g, b), min(r, g, b)
            if max_c == 0:
                return 0
            return (max_c - min_c) / max_c

        sorted_by_lum = sorted(hex_colors[:10], key=luminance)
        sorted_by_sat = sorted(hex_colors[:10], key=saturation, reverse=True)

        darkest = sorted_by_lum[0]
        lightest = sorted_by_lum[-1]
        most_saturated = sorted_by_sat[0] if saturation(sorted_by_sat[0]) > 0.2 else "#3366ff"

        # If darkest is very dark, it's likely bg (dark theme) or text (light theme)
        dark_lum = luminance(darkest)
        light_lum = luminance(lightest)

        if dark_lum < 50:  # Dark theme likely
            return {
                "bg": darkest,
                "text": lightest,
                "accent": most_saturated,
                "theme": "dark",
            }
        else:
            return {
                "bg": lightest,
                "text": darkest,
                "accent": most_saturated,
                "theme": "light",
            }

    # =========================================================
    # ASSET DOWNLOAD
    # =========================================================

    def download_frame_images(self, file_key: str, frame_ids: List[str],
                               output_dir: str, format: str = "png",
                               scale: float = 2) -> List[str]:
        """Export frames and download them to disk.

        Args:
            file_key: Figma file key
            frame_ids: Node IDs to export
            output_dir: Where to save
            format: png, jpg, svg, pdf
            scale: Export scale

        Returns:
            List of saved file paths
        """
        if not requests:
            raise ImportError("requests required")

        image_urls = self.export_images(file_key, frame_ids, format, scale)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved = []
        for node_id, url in image_urls.items():
            if not url:
                continue
            safe_name = node_id.replace(":", "-")
            filename = f"{safe_name}.{format}"
            filepath = output_path / filename

            resp = requests.get(url, timeout=60)
            if resp.status_code == 200:
                filepath.write_bytes(resp.content)
                saved.append(str(filepath))

        return saved


# =========================================================
# CLI
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Figma Parser — Extract design system from Figma files")
    parser.add_argument("--url", required=True, help="Figma file URL")
    parser.add_argument("--design-system", action="store_true", help="Extract design system (PressLess format)")
    parser.add_argument("--export", choices=["png", "jpg", "svg", "pdf"], help="Export frames as images")
    parser.add_argument("--scale", type=float, default=2, help="Export scale (default: 2)")
    parser.add_argument("--output", type=str, default="./figma-assets", help="Output directory for exports")
    parser.add_argument("--depth", type=int, default=None, help="Node tree depth (None=full)")
    parser.add_argument("--raw", action="store_true", help="Print raw API response")
    args = parser.parse_args()

    fp = FigmaParser()
    parsed = fp.parse_figma_url(args.url)
    file_key = parsed["file_key"]

    if not file_key:
        print(f"ERROR: Could not extract file key from URL: {args.url}")
        return

    print(f"File key: {file_key}")

    if args.raw:
        data = fp.get_file(file_key, depth=args.depth)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    data = fp.parse_url(args.url, depth=args.depth)
    print(f"File: {data.get('name', '?')}")
    print(f"Last modified: {data.get('lastModified', '?')}")

    if args.design_system:
        ds = fp.to_pressless_design_system(data)
        print(json.dumps(ds, indent=2, ensure_ascii=False))
    else:
        ds = fp.extract_design_system(data)
        print(f"\nColors: {len(ds['colors'])}")
        for c in ds["colors"][:5]:
            print(f"  {c['hex']} (used {c['count']}x)")
        print(f"\nFonts: {len(ds['fonts'])}")
        for f in ds["fonts"][:5]:
            print(f"  {f['spec']} (used {f['count']}x)")
        print(f"\nFrames: {len(ds['frames'])}")
        for fr in ds["frames"][:10]:
            print(f"  {fr['name']} ({fr['width']}x{fr['height']})")
        print(f"\nComponents: {len(ds['components'])}")
        print(f"Spacing values: {ds['spacing'][:10]}")

    if args.export:
        frame_ids = [fr["id"] for fr in ds.get("frames", []) if fr.get("id")]
        if not frame_ids:
            # Fall back to extracting from full design system
            full_ds = fp.extract_design_system(data) if args.design_system else ds
            frame_ids = [fr["id"] for fr in full_ds.get("frames", []) if fr.get("id")]

        if frame_ids:
            print(f"\nExporting {len(frame_ids)} frames as {args.export}...")
            saved = fp.download_frame_images(file_key, frame_ids, args.output, args.export, args.scale)
            for s in saved:
                print(f"  Saved: {s}")
        else:
            print("\nNo frames found to export.")


if __name__ == "__main__":
    main()
