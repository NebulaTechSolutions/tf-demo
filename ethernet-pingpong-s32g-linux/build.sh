#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")" && pwd)"
profile="${1:-release}"
case "$profile" in
    -h|--help) echo 'Usage: ./build.sh [release|debug]'; exit 0 ;;
    release|debug) ;;
    *) echo "Unknown profile: $profile" >&2; exit 2 ;;
esac
zig="${ZIG:-zig}"
if ! command -v "$zig" >/dev/null; then
    echo 'Install Zig 0.15.2: https://ziglang.org/download/' >&2
    exit 1
fi
exec make -C "$root" "$profile" "ZIG=$zig"
