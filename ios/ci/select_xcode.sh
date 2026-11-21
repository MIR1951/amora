#!/usr/bin/env bash
# Runner'dagi eng yangi Xcode 26.x ni tanlaydi (beta/RC emas). ios.yml va ios-testflight.yml ishlatadi.
set -euo pipefail
ls /Applications | grep Xcode || true
XCODE=$(ls -d /Applications/Xcode_26*.app 2>/dev/null | grep -E 'Xcode_26(\.[0-9]+)*\.app$' | sort -V | tail -n 1 || true)
if [ -z "$XCODE" ]; then
  echo "::error::Xcode 26 topilmadi"
  exit 1
fi
echo "Tanlandi: $XCODE"
sudo xcode-select -s "$XCODE/Contents/Developer"
xcodebuild -version
