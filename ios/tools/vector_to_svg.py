#!/usr/bin/env python3
"""Android VectorDrawable (res/drawable/ic_*.xml) -> SVG imagesets for the iOS asset catalog.

Usage (from the repo root):
    python3 ios/tools/vector_to_svg.py                # convert every ic_*.xml icon
    python3 ios/tools/vector_to_svg.py --check DIR    # also rasterize each SVG to DIR/*.png (needs ffmpeg with librsvg)

What it understands:
  <vector> android:width/height (dp), viewportWidth/viewportHeight
  <group>  rotation, pivotX/Y, scaleX/Y, translateX/Y (nested groups too)
  <path>   pathData, fillColor, fillAlpha, fillType (evenOdd), strokeColor, strokeAlpha,
           strokeWidth, strokeLineCap, strokeLineJoin, strokeMiterLimit
           <aapt:attr name="android:fillColor"><gradient type="linear|radial" .../></aapt:attr>
Android pathData uses the same grammar as SVG path data, so it is copied unchanged.
Colors: #RGB, #ARGB, #RRGGBB, #AARRGGBB. Color resources (@color/...) are not resolved (black is used).

Output: ios/Amora/Resources/Assets.xcassets/<name>.imageset/{<name>.svg, Contents.json}
with "preserves-vector-representation": true and template rendering (multi-color icons such as
ic_my_location keep their colors: rendering intent "original").
The launcher icons (ic_launcher_*) are skipped here; make_app_icon.py renders them into AppIcon.
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ANDROID = "{http://schemas.android.com/apk/res/android}"
AAPT = "{http://schemas.android.com/aapt}"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
DRAWABLE_DIR = os.path.join(REPO, "android", "app", "src", "main", "res", "drawable")
ASSETS_DIR = os.path.join(REPO, "ios", "Amora", "Resources", "Assets.xcassets")

# Icons that must keep their own colors (not tinted by the view)
ORIGINAL_COLORS = {"ic_my_location"}


def attr(element, name, default=None):
    return element.get(ANDROID + name, default)


def number(text, default=0.0):
    if text is None:
        return default
    text = text.strip()
    for suffix in ("dp", "dip", "px", "sp"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    try:
        return float(text)
    except ValueError:
        return default


def fmt(value):
    """Short decimal: 24.0 -> 24, 1.90 -> 1.9."""
    text = ("%.4f" % value).rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def parse_color(text):
    """Android color -> (svg '#rrggbb', alpha 0..1) or None for transparent/unknown."""
    if text is None:
        return None
    text = text.strip()
    if text.startswith("@"):
        # Resource reference: not resolvable here
        return ("#000000", 1.0)
    if not text.startswith("#"):
        return None
    hex_part = text[1:]
    if len(hex_part) == 3:
        a = "ff"
        rgb = "".join(c * 2 for c in hex_part)
    elif len(hex_part) == 4:
        a = hex_part[0] * 2
        rgb = "".join(c * 2 for c in hex_part[1:])
    elif len(hex_part) == 6:
        a, rgb = "ff", hex_part
    elif len(hex_part) == 8:
        a, rgb = hex_part[:2], hex_part[2:]
    else:
        return None
    alpha = int(a, 16) / 255.0
    return ("#" + rgb.lower(), alpha)


class Converter:
    def __init__(self):
        self.defs = []
        self.gradient_count = 0

    def gradient(self, element, name):
        """aapt:attr child holding a <gradient>: returns 'url(#id)' or None."""
        for child in element:
            if child.tag == AAPT + "attr" and child.get("name") == "android:" + name:
                for gradient in child:
                    if gradient.tag == "gradient":
                        return self.make_gradient(gradient)
        return None

    def make_gradient(self, gradient):
        self.gradient_count += 1
        gid = "g%d" % self.gradient_count
        kind = attr(gradient, "type", "linear")
        stops = []
        items = [item for item in gradient if item.tag == "item"]
        if items:
            for item in items:
                color = parse_color(attr(item, "color")) or ("#000000", 1.0)
                stops.append((number(attr(item, "offset")), color))
        else:
            start = parse_color(attr(gradient, "startColor")) or ("#000000", 1.0)
            end = parse_color(attr(gradient, "endColor")) or ("#000000", 1.0)
            center = attr(gradient, "centerColor")
            stops.append((0.0, start))
            if center is not None:
                stops.append((0.5, parse_color(center) or ("#000000", 1.0)))
            stops.append((1.0, end))
        stop_xml = "".join(
            '<stop offset="%s" stop-color="%s"%s/>'
            % (fmt(offset), color, "" if alpha >= 0.999 else ' stop-opacity="%s"' % fmt(alpha))
            for offset, (color, alpha) in stops
        )
        if kind == "radial":
            self.defs.append(
                '<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s">%s</radialGradient>'
                % (
                    gid,
                    fmt(number(attr(gradient, "centerX"))),
                    fmt(number(attr(gradient, "centerY"))),
                    fmt(number(attr(gradient, "gradientRadius"))),
                    stop_xml,
                )
            )
        else:
            self.defs.append(
                '<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
                % (
                    gid,
                    fmt(number(attr(gradient, "startX"))),
                    fmt(number(attr(gradient, "startY"))),
                    fmt(number(attr(gradient, "endX"))),
                    fmt(number(attr(gradient, "endY"))),
                    stop_xml,
                )
            )
        return "url(#%s)" % gid

    def path(self, element):
        data = attr(element, "pathData")
        if not data:
            return ""
        parts = ['d="%s"' % " ".join(data.split())]

        fill_url = self.gradient(element, "fillColor")
        fill = parse_color(attr(element, "fillColor"))
        fill_alpha = number(attr(element, "fillAlpha"), 1.0)
        if fill_url:
            parts.append('fill="%s"' % fill_url)
            if fill_alpha < 0.999:
                parts.append('fill-opacity="%s"' % fmt(fill_alpha))
        elif fill:
            color, alpha = fill
            parts.append('fill="%s"' % color)
            total = alpha * fill_alpha
            if total < 0.999:
                parts.append('fill-opacity="%s"' % fmt(total))
        else:
            parts.append('fill="none"')
        if (attr(element, "fillType") or "").lower() == "evenodd":
            parts.append('fill-rule="evenodd"')

        stroke_url = self.gradient(element, "strokeColor")
        stroke = parse_color(attr(element, "strokeColor"))
        stroke_width = number(attr(element, "strokeWidth"), 0.0)
        stroke_alpha = number(attr(element, "strokeAlpha"), 1.0)
        if (stroke_url or stroke) and stroke_width > 0:
            if stroke_url:
                parts.append('stroke="%s"' % stroke_url)
                if stroke_alpha < 0.999:
                    parts.append('stroke-opacity="%s"' % fmt(stroke_alpha))
            else:
                color, alpha = stroke
                parts.append('stroke="%s"' % color)
                total = alpha * stroke_alpha
                if total < 0.999:
                    parts.append('stroke-opacity="%s"' % fmt(total))
            parts.append('stroke-width="%s"' % fmt(stroke_width))
            cap = attr(element, "strokeLineCap")
            if cap in ("round", "square", "butt"):
                parts.append('stroke-linecap="%s"' % cap)
            join = attr(element, "strokeLineJoin")
            if join in ("round", "bevel", "miter"):
                parts.append('stroke-linejoin="%s"' % join)
            miter = attr(element, "strokeMiterLimit")
            if miter is not None:
                parts.append('stroke-miterlimit="%s"' % fmt(number(miter, 4.0)))
        return "<path %s/>" % " ".join(parts)

    def group(self, element, depth):
        transforms = []
        tx = number(attr(element, "translateX"))
        ty = number(attr(element, "translateY"))
        px = number(attr(element, "pivotX"))
        py = number(attr(element, "pivotY"))
        sx = number(attr(element, "scaleX"), 1.0)
        sy = number(attr(element, "scaleY"), 1.0)
        rotation = number(attr(element, "rotation"))
        # Android order: translate, then scale and rotate around the pivot
        if tx or ty:
            transforms.append("translate(%s %s)" % (fmt(tx), fmt(ty)))
        if px or py:
            transforms.append("translate(%s %s)" % (fmt(px), fmt(py)))
        if rotation:
            transforms.append("rotate(%s)" % fmt(rotation))
        if sx != 1.0 or sy != 1.0:
            transforms.append("scale(%s %s)" % (fmt(sx), fmt(sy)))
        if px or py:
            transforms.append("translate(%s %s)" % (fmt(-px), fmt(-py)))
        inner = self.children(element, depth + 1)
        if transforms:
            return '<g transform="%s">%s</g>' % (" ".join(transforms), inner)
        return "<g>%s</g>" % inner

    def children(self, element, depth):
        out = []
        for child in element:
            if child.tag == "path":
                out.append(self.path(child))
            elif child.tag == "group":
                out.append(self.group(child, depth))
            elif child.tag == "clip-path":
                # Rare in this project; ignored (warned)
                print("warning: <clip-path> ignored", file=sys.stderr)
        return "".join(out)


def convert(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != "vector":
        raise ValueError("%s: not a <vector> drawable" % xml_path)
    vw = number(attr(root, "viewportWidth"), 24.0)
    vh = number(attr(root, "viewportHeight"), 24.0)
    width = number(attr(root, "width"), vw)
    height = number(attr(root, "height"), vh)
    converter = Converter()
    body = converter.children(root, 0)
    alpha = number(attr(root, "alpha"), 1.0)
    if alpha < 0.999:
        body = '<g opacity="%s">%s</g>' % (fmt(alpha), body)
    defs = "<defs>%s</defs>" % "".join(converter.defs) if converter.defs else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">%s%s</svg>\n'
        % (fmt(width), fmt(height), fmt(vw), fmt(vh), defs, body)
    )


def write_imageset(name, svg):
    folder = os.path.join(ASSETS_DIR, name + ".imageset")
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        os.remove(os.path.join(folder, old))
    with open(os.path.join(folder, name + ".svg"), "w", encoding="utf-8") as handle:
        handle.write(svg)
    contents = {
        "images": [{"filename": name + ".svg", "idiom": "universal"}],
        "info": {"author": "xcode", "version": 1},
        "properties": {
            "preserves-vector-representation": True,
            "template-rendering-intent": "original" if name in ORIGINAL_COLORS else "template",
        },
    }
    with open(os.path.join(folder, "Contents.json"), "w", encoding="utf-8") as handle:
        json.dump(contents, handle, indent=2)
        handle.write("\n")
    return folder


def rasterize(svg_path, png_path, size=96):
    """Preview through ffmpeg's librsvg decoder (ImageMagick here has no SVG delegate)."""
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-i", svg_path,
            "-vf", "scale=%d:%d:flags=lanczos" % (size, size),
            png_path,
        ],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--drawables", default=DRAWABLE_DIR)
    parser.add_argument("--assets", default=None)
    parser.add_argument("--check", metavar="DIR", help="rasterize every SVG to DIR for a visual check")
    args = parser.parse_args()
    global ASSETS_DIR
    if args.assets:
        ASSETS_DIR = args.assets
    os.makedirs(ASSETS_DIR, exist_ok=True)

    names = sorted(
        f[:-4]
        for f in os.listdir(args.drawables)
        if f.startswith("ic_") and f.endswith(".xml") and not f.startswith("ic_launcher")
    )
    for name in names:
        svg = convert(os.path.join(args.drawables, name + ".xml"))
        folder = write_imageset(name, svg)
        print("%-18s -> %s" % (name, os.path.relpath(folder, REPO)))
        if args.check:
            os.makedirs(args.check, exist_ok=True)
            rasterize(os.path.join(folder, name + ".svg"), os.path.join(args.check, name + ".png"))
    print("%d icons" % len(names))


if __name__ == "__main__":
    main()
