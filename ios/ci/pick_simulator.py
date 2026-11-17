#!/usr/bin/env python3
"""Sinov uchun iPhone simulyatorini tanlaydi va uning UDID'ini chiqaradi.

    xcrun simctl list devices available -j | python3 ios/ci/pick_simulator.py ["iPhone 16"]

Avval so'ralgan nomdagi (standart: "iPhone 16") eng yangi iOS'dagi qurilma olinadi, u bo'lmasa
eng yangi iOS'dagi birinchi iPhone. Topilmasa, chiqish kodi 1.
"""

import json
import re
import sys


def runtime_version(key: str) -> tuple[int, ...]:
    # com.apple.CoreSimulator.SimRuntime.iOS-18-2 -> (18, 2)
    match = re.search(r"iOS-([\d-]+)$", key)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("-") if part)


def main() -> int:
    wanted = sys.argv[1] if len(sys.argv) > 1 else "iPhone 16"
    data = json.load(sys.stdin)
    candidates = []
    for runtime, devices in data.get("devices", {}).items():
        version = runtime_version(runtime)
        if not version:
            continue  # watchOS, tvOS, visionOS
        for device in devices:
            if device.get("isAvailable", True) and device.get("name", "").startswith("iPhone"):
                candidates.append((version, device))
    if not candidates:
        print("iPhone simulyatori topilmadi", file=sys.stderr)
        return 1
    candidates.sort(key=lambda item: item[0], reverse=True)
    chosen = next((item for item in candidates if item[1]["name"] == wanted), candidates[0])
    version, device = chosen
    print(
        f"Tanlandi: {device['name']} (iOS {'.'.join(map(str, version))}) {device['udid']}",
        file=sys.stderr,
    )
    print(device["udid"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
