ZIG ?= zig
COMMON_FLAGS = -target aarch64-linux-musl -Wall -Wextra -Werror -static

.PHONY: all release debug clean
all: release
release: build/release/eth_sender build/release/eth_receiver
debug: build/debug/eth_sender build/debug/eth_receiver

build/release/eth_sender: sender/main.c
	mkdir -p $(@D)
	$(ZIG) cc $(COMMON_FLAGS) -O2 -o $@ $<

build/release/eth_receiver: receiver/main.c
	mkdir -p $(@D)
	$(ZIG) cc $(COMMON_FLAGS) -O2 -o $@ $<

build/debug/eth_sender: sender/main.c
	mkdir -p $(@D)
	$(ZIG) cc $(COMMON_FLAGS) -g -O0 -o $@ $<

build/debug/eth_receiver: receiver/main.c
	mkdir -p $(@D)
	$(ZIG) cc $(COMMON_FLAGS) -g -O0 -o $@ $<

clean:
	rm -rf build
