#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")" && pwd)"
demo="${1:-all}"
profile="${2:-release}"
if [[ "$demo" == --help || "$demo" == -h ]]; then
    echo 'Usage: ./build.sh [all|gateway|can|ethernet] [release|debug]'
    exit 0
fi
case "$profile" in release|debug) ;; *) echo "Unknown profile: $profile" >&2; exit 2 ;; esac
case "$demo" in
    gateway) python3 "$root/can-gateway-iac/build.py" --profile "$profile" ;;
    can) "$root/can-pingpong-s32k3-zephyr/build.sh" "$profile" ;;
    ethernet) "$root/ethernet-pingpong-s32g-linux/build.sh" "$profile" ;;
    all)
        python3 "$root/can-gateway-iac/build.py" --profile "$profile"
        "$root/can-pingpong-s32k3-zephyr/build.sh" "$profile"
        "$root/ethernet-pingpong-s32g-linux/build.sh" "$profile"
        ;;
    *) echo "Unknown demo: $demo. Use --help for usage." >&2; exit 2 ;;
esac
