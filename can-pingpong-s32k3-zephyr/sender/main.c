/*
 * CAN Ping Sender
 * Sends PING messages on CAN bus with structured signal data per pingpong.dbc
 *
 * Frame format (8 bytes, little-endian):
 *   Bytes 0-3: "PING" ASCII identifier
 *   Byte 4:    SequenceCounter (0-255, increments each message)
 *   Byte 5:    SignalStrength (0-100, simulated percentage)
 *   Bytes 6-7: TimestampOffset (0-65535, ms since start, little-endian)
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/can.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(can_sender, LOG_LEVEL_INF);

#define PING_MSG_ID      0x123
#define PONG_MSG_ID      0x124
#define PING_INTERVAL_MS 1000

static const struct device *can_dev;
static struct k_sem pong_sem;
static uint8_t sequence_counter = 0;
static uint32_t pong_count = 0;
static int64_t start_time_ms = 0;

static const struct can_filter pong_filter = {
    .id = PONG_MSG_ID,
    .mask = CAN_STD_ID_MASK,
};

static void can_rx_callback(const struct device *dev, struct can_frame *frame, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(user_data);

    if (frame->id == PONG_MSG_ID && frame->dlc >= 8) {
        /* Verify PONG identifier in first 4 bytes */
        if (memcmp(frame->data, "PONG", 4) == 0) {
            uint8_t echo_counter = frame->data[4];
            uint8_t proc_time = frame->data[5];
            uint16_t rtt = frame->data[6] | (frame->data[7] << 8);

            pong_count++;
            LOG_INF("PONG #%d: echo=%d proc=%dms rtt=%dms",
                    pong_count, echo_counter, proc_time, rtt);
            k_sem_give(&pong_sem);
        }
    }
}

int main(void)
{
    struct can_frame ping_frame = {
        .id = PING_MSG_ID,
        .dlc = 8,
        .flags = 0,
    };
    int ret;

    LOG_INF("CAN Ping Sender starting...");

    k_sem_init(&pong_sem, 0, 1);
    start_time_ms = k_uptime_get();

    /* Get CAN device */
    can_dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_can_primary));
    if (!device_is_ready(can_dev)) {
        LOG_ERR("CAN device not ready");
        return -ENODEV;
    }

    ret = can_set_mode(can_dev, CAN_MODE_NORMAL);
    if (ret != 0) {
        LOG_ERR("Failed to set CAN mode: %d", ret);
        return ret;
    }

    ret = can_start(can_dev);
    if (ret != 0) {
        LOG_ERR("Failed to start CAN: %d", ret);
        return ret;
    }

    ret = can_add_rx_filter(can_dev, can_rx_callback, NULL, &pong_filter);
    if (ret < 0) {
        LOG_ERR("Failed to add RX filter: %d", ret);
        return ret;
    }

    LOG_INF("CAN ready, starting ping loop...");

    while (1) {
        /* Build PING frame per DBC definition */
        /* Bytes 0-3: ASCII identifier */
        memcpy(ping_frame.data, "PING", 4);

        /* Byte 4: SequenceCounter (bits 32-39) */
        ping_frame.data[4] = sequence_counter;

        /* Byte 5: SignalStrength (bits 40-47) - simulate 50-100% range */
        ping_frame.data[5] = 50 + (sequence_counter % 51);

        /* Bytes 6-7: TimestampOffset (bits 48-63) - ms since start, little-endian */
        uint16_t ts_offset = (uint16_t)((k_uptime_get() - start_time_ms) & 0xFFFF);
        ping_frame.data[6] = ts_offset & 0xFF;
        ping_frame.data[7] = (ts_offset >> 8) & 0xFF;

        ret = can_send(can_dev, &ping_frame, K_MSEC(100), NULL, NULL);
        if (ret != 0) {
            LOG_ERR("Failed to send PING: %d", ret);
        } else {
            LOG_INF("PING #%d: seq=%d str=%d%% ts=%dms",
                    sequence_counter, sequence_counter,
                    ping_frame.data[5], ts_offset);

            /* Wait for PONG response */
            if (k_sem_take(&pong_sem, K_MSEC(50)) != 0) {
                LOG_WRN("No PONG for seq #%d", sequence_counter);
            }
        }

        sequence_counter++;
        k_sleep(K_MSEC(PING_INTERVAL_MS));
    }

    return 0;
}
