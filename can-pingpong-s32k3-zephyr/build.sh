#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")" && pwd)"
profile="${1:-release}"
case "$profile" in
    -h|--help) echo 'Usage: ./build.sh [release|debug] [tf build options]'; exit 0 ;;
    release|debug) ;;
    *) echo "Unknown profile: $profile" >&2; exit 2 ;;
esac
if (( $# )); then shift; fi
cli="${TF_CLI:-tf}"
if ! command -v "$cli" >/dev/null; then
    echo 'Install the tf CLI first: https://nebula-platform.dev/docs/getting-started/install-cli' >&2
    exit 1
fi
for app in sender receiver; do
    "$cli" build "$profile" --board s32k3x4evb --os zephyr \
        --source "$root/$app" --output "build/$profile" "$@"
done
