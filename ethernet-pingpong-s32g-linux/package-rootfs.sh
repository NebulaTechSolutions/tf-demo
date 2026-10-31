#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")" && pwd)"
if (( $# < 1 || $# > 2 )) || [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./package-rootfs.sh /path/to/base-rootfs.cpio.gz [release|debug]'
    if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then exit 0; fi
    exit 2
fi
base="$(realpath -- "$1")"
profile="${2:-release}"
case "$profile" in release|debug) ;; *) echo "Unknown profile: $profile" >&2; exit 2 ;; esac
for binary in eth_sender eth_receiver; do
    if [[ ! -f "$root/build/$profile/$binary" ]]; then
        echo "Missing $binary. Run ./build.sh $profile first." >&2
        exit 1
    fi
done
scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT
gzip -dc -- "$base" | (cd "$scratch" && cpio -idm --no-absolute-filenames --quiet)
mkdir -p "$scratch/opt/demo" "$scratch/app"
cp "$root/build/$profile/eth_sender" "$root/build/$profile/eth_receiver" "$scratch/opt/demo/"
chmod +x "$scratch/opt/demo/eth_sender" "$scratch/opt/demo/eth_receiver"
ln -sfn /opt/demo/eth_sender "$scratch/app/sender"
ln -sfn /opt/demo/eth_receiver "$scratch/app/receiver"
(cd "$scratch" && find . -print0 | LC_ALL=C sort -z | cpio --null -o --format=newc --quiet | gzip -n -9) > "$root/test-rootfs.cpio.gz"
echo "Built $root/test-rootfs.cpio.gz"
