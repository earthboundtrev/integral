"""Generate Windows .ico from source PNG for Integral builds."""

from __future__ import annotations

import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install Pillow", file=sys.stderr)
    raise SystemExit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SOURCE = os.path.join(ASSETS, "integral-icon-source.png")
OUTPUT = os.path.join(ASSETS, "icon.ico")


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"Missing source image: {SOURCE}", file=sys.stderr)
        raise SystemExit(1)

    image = Image.open(SOURCE).convert("RGBA")
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    os.makedirs(ASSETS, exist_ok=True)
    image.save(OUTPUT, format="ICO", sizes=sizes)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
