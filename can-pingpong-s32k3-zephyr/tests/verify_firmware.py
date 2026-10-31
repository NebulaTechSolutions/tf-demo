#!/usr/bin/env python3
"""Check the built receiver through ECUSim's private ECU-time CAN and log adapters."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--ecusim-source", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.ecusim_source / "tests/ecu-clock"))
    from verify import VM

    checks = []
    with tempfile.TemporaryDirectory(prefix="pingpong-receiver-") as directory:
        vm = VM(str(args.qemu.resolve()), args.receiver, directory, guest_args=[
            "-machine", "s32k3x4evb", "-smp", "1", "-kernel", str(args.receiver.resolve()),
            "-object", "can-bus,id=canbus0", "-object", "can-test,id=tap,canbus=canbus0",
            "-chardev", "ecu-test,id=console", "-serial", "chardev:console", "-nic", "none",
        ])
        try:
            def advance(deadline, label):
                frames, records = [], []
                for index in range(10000):
                    vm.command("x-ecu-run-until", **{
                        "deadline-ns": deadline, "run-id": f"{label}-{index}",
                        "stop-on-output": True,
                    })
                    event = vm.event("ECU_CLOCK_STOPPED", f"{label}-{index}")
                    frames.extend(vm.command("x-ecu-can-drain", id="tap")["frames"])
                    records.extend(vm.command("x-ecu-log-drain", id="console")["records"])
                    if event["reason"] == "deadline":
                        assert event["time-ns"] == deadline
                        return frames, records
                    assert event["reason"] == "output", event
                raise RuntimeError("receiver exceeded the bounded output budget")

            now = 100_000_000
            frames, records = advance(now, "boot")
            logs = bytes(row["value"] for row in records).decode("utf-8", errors="replace")
            assert "CAN ready, waiting for PING messages..." in logs, logs
            checks.append({"name": "receiver-ready", "ecu_time_ns": now})
            assert frames == []
            probes = [
                ("bad-header", 0x123, b"NOPE\x07\x32\x00\x00", None, 20_000_000),
                ("short-ping", 0x123, b"PING\x08\x32\x00", None, 20_000_000),
                ("wrong-identifier", 0x122, b"PING\x09\x32\x00\x00", None, 20_000_000),
                ("zero-counter", 0x123, b"PING\x00\x32\x00\x00", 0, 50_000_000),
                ("maximum-counter", 0x123, b"PING\xff\x64\x00\x00", 255, 50_000_000),
            ]
            for name, identifier, data, counter, window in probes:
                receipt = vm.command("x-ecu-can-inject", id="tap", **{
                    "time-ns": now,
                    "frame": {"can-id": identifier, "flags": 0, "dlc": len(data), "data": data.hex()},
                })
                assert receipt["accepted"], receipt
                now += window
                frames, _ = advance(now, name)
                if counter is None:
                    assert frames == [], (name, frames)
                else:
                    assert len(frames) == 1, (name, frames)
                    frame = frames[0]["frame"]
                    assert frame["can-id"] == 0x124 and frame["dlc"] == 8, frame
                    assert bytes.fromhex(frame["data"])[:5] == b"PONG" + bytes([counter]), frame
                checks.append({"name": name, "ecu_time_ns": now, "frames": frames})
        finally:
            vm.close()
    print(json.dumps({"passed": True, "scope": "single receiver firmware, not a cloud suite run",
                      "firmware_sha256": hashlib.sha256(args.receiver.read_bytes()).hexdigest(),
                      "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
