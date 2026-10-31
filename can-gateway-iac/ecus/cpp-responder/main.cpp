#include <stdint.h>

namespace {
constexpr uintptr_t flexcan0 = 0x40304000;
constexpr uintptr_t uart2Data = 0x4033001c;
constexpr uint32_t requestId = 0x125;
constexpr uint32_t responseId = 0x126;
constexpr uint32_t rxEmpty = 4u << 24;
constexpr uint32_t txData = 12u << 24;
constexpr uint32_t extendedOrRemote = (1u << 21) | (1u << 20);

volatile uint32_t& can(uintptr_t offset) {
    return *reinterpret_cast<volatile uint32_t*>(flexcan0 + offset);
}

void ready() {
    for (const char* text = "C++ responder ready\n"; *text; ++text) {
        *reinterpret_cast<volatile uint32_t*>(uart2Data) = *text;
    }
}
}

extern "C" [[noreturn]] void firmware_main() {
    // ECUSim S32K344 FlexCAN: MB0 receives, MB1 transmits, accept all IDs.
    can(0x10) = 0;
    can(0x00) = 1;
    can(0x80) = rxEmpty;
    can(0x94) = responseId << 18;
    ready();

    while (true) {
        if ((can(0x30) & 1u) == 0) {
            continue;
        }
        const uint32_t control = can(0x80);
        const uint32_t identifier = can(0x84);
        const uint32_t header = can(0x88);
        const uint32_t payload = can(0x8c);
        (void)can(0x08); // Unlock the received mailbox before rearming it.
        can(0x30) = 1;
        can(0x80) = rxEmpty;

        if ((control & extendedOrRemote) != 0 || ((control >> 16) & 15u) != 8 ||
            identifier != (requestId << 18) || header != 0x50494e47) {
            continue;
        }
        can(0x30) = 2;
        can(0x98) = 0x43505021; // "CPP!", followed by the request's four data bytes.
        can(0x9c) = payload;
        can(0x90) = txData | (8u << 16);
        while ((can(0x30) & 2u) == 0) {}
    }
}
