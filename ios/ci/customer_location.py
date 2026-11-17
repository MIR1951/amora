#!/usr/bin/env python3
"""Simulyator turadigan joy: kafedan 150 metrcha narida, ya'ni yetkazish hududi ichida.

    python3 ios/ci/customer_location.py http://127.0.0.1:8000    ->  39.65620,66.97580

Kafe joylashuvi serverning /api/v1/shop javobidan o'qiladi (android/ci/smoke_test.py dagi
customer_location bilan bir xil). O'qib bo'lmasa, Samarqand markazi qaytariladi.
"""

import json
import sys
import urllib.request

DEFAULT_LOCATION = (39.6547, 66.9758)


def main() -> None:
    server = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    latitude, longitude = DEFAULT_LOCATION
    try:
        with urllib.request.urlopen(f"{server}/api/v1/shop", timeout=20) as response:
            shop = json.load(response)
        if shop.get("cafe_latitude") is not None and shop.get("cafe_longitude") is not None:
            latitude, longitude = float(shop["cafe_latitude"]) + 0.0015, float(shop["cafe_longitude"])
        else:
            print("[ogohlantirish] serverda kafe joylashuvi kiritilmagan", file=sys.stderr)
    except Exception as error:  # noqa: BLE001
        print(f"[ogohlantirish] kafe joylashuvini o'qib bo'lmadi: {error}", file=sys.stderr)
    print(f"{latitude:.5f},{longitude:.5f}")


if __name__ == "__main__":
    main()
