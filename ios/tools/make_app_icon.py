#!/usr/bin/env python3
"""Renders the iOS app icon and launch logo from the Android launcher vectors.

Usage (from the repo root):
    python3 ios/tools/make_app_icon.py

Inputs:  android/app/src/main/res/drawable/ic_launcher_background.xml (red gradient)
         android/app/src/main/res/drawable/ic_launcher_foreground.xml (white "A")
Outputs: ios/Amora/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png  (1024x1024, no alpha)
         ios/Amora/Resources/Assets.xcassets/LaunchLogo.imageset/LaunchLogo.svg (white "A", launch screen)

Android adaptive icons are drawn on a 108x108 canvas of which the launcher shows the middle 72x72,
so the iOS icon is that middle square (viewBox 18 18 72 72) scaled to 1024 px.
Rasterizing uses ffmpeg's librsvg decoder (ImageMagick on the dev box has no SVG delegate);
Pillow strips the alpha channel (App Store icons must be opaque).
"""

import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from vector_to_svg import convert  # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
DRAWABLE = os.path.join(REPO, "android", "app", "src", "main", "res", "drawable")
ASSETS = os.path.join(REPO, "ios", "Amora", "Resources", "Assets.xcassets")


def inner(svg):
    """<defs>..</defs> and paths of a converted SVG, without the <svg> wrapper."""
    body = svg.split(">", 2)[2]  # drop xml header and <svg ...>
    return body.rsplit("</svg>", 1)[0]


def main():
    background = convert(os.path.join(DRAWABLE, "ic_launcher_background.xml"))
    foreground = convert(os.path.join(DRAWABLE, "ic_launcher_foreground.xml"))
    icon_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="18 18 72 72">'
        + inner(background)
        + inner(foreground)
        + "</svg>\n"
    )

    icon_dir = os.path.join(ASSETS, "AppIcon.appiconset")
    os.makedirs(icon_dir, exist_ok=True)
    png_path = os.path.join(icon_dir, "AppIcon.png")
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = os.path.join(tmp, "icon.svg")
        raw_png = os.path.join(tmp, "icon.png")
        with open(svg_path, "w", encoding="utf-8") as handle:
            handle.write(icon_svg)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", svg_path, "-vf", "scale=1024:1024:flags=lanczos", raw_png],
            check=True,
        )
        from PIL import Image

        image = Image.open(raw_png).convert("RGBA")
        opaque = Image.new("RGB", image.size, (0xE5, 0x43, 0x2A))
        opaque.paste(image, mask=image.split()[3])
        opaque.save(png_path, "PNG", optimize=True)
    with open(os.path.join(icon_dir, "Contents.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "images": [
                    {"filename": "AppIcon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}
                ],
                "info": {"author": "xcode", "version": 1},
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    print("AppIcon ->", os.path.relpath(png_path, REPO))

    # Launch screen logo: the white "A" alone, 144 pt like Android's splash.xml
    logo_dir = os.path.join(ASSETS, "LaunchLogo.imageset")
    os.makedirs(logo_dir, exist_ok=True)
    logo_svg = re.sub(r'width="[^"]*" height="[^"]*"', 'width="144" height="144"', foreground, count=1)
    with open(os.path.join(logo_dir, "LaunchLogo.svg"), "w", encoding="utf-8") as handle:
        handle.write(logo_svg)
    with open(os.path.join(logo_dir, "Contents.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "images": [{"filename": "LaunchLogo.svg", "idiom": "universal"}],
                "info": {"author": "xcode", "version": 1},
                "properties": {"preserves-vector-representation": True},
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    print("LaunchLogo ->", os.path.relpath(logo_dir, REPO))


if __name__ == "__main__":
    main()
