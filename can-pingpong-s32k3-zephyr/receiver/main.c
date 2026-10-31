/*
 * CAN Pong Receiver
 * Receives PING messages and responds with PONG per pingpong.dbc
 *
 * PONG frame format (8 bytes, little-endian):
 *   Bytes 0-3: "PONG" ASCII identifier
 *   Byte 4:    EchoCounter (echo of received SequenceCounter)
 *   Byte 5:    ProcessingTime (0-255, simulated processing time in ms)
 *   Bytes 6-7: RoundTripTime (0-65535, calculated RTT in ms, little-endian)
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/can.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(can_receiver, LOG_LEVEL_INF);

#define PING_MSG_ID 0x123
#define PONG_MSG_ID 0x124

static const struct device *can_dev;
static uint32_t ping_count = 0;
static int64_t start_time_ms = 0;

static const struct can_filter ping_filter = {
    .id = PING_MSG_ID,
    .mask = CAN_STD_ID_MASK,
};

/* Data passed from RX callback to work handler */
struct pong_data {
    uint8_t echo_counter;
    uint16_t ping_ts_offset;
    int64_t rx_time_ms;
};
static struct pong_data pending_pong;
static struct k_work pong_work;

static void pong_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    struct can_frame pong_frame = {
        .id = PONG_MSG_ID,
        .dlc = 8,
        .flags = 0,
    };
    int ret;

    /* Bytes 0-3: ASCII identifier */
    memcpy(pong_frame.data, "PONG", 4);

    /* Byte 4: EchoCounter (bits 32-39) - echo of received sequence */
    pong_frame.data[4] = pending_pong.echo_counter;

    /* Byte 5: ProcessingTime (bits 40-47) - time since RX in ms */
    int64_t now = k_uptime_get();
    uint8_t proc_time = (uint8_t)MIN(now - pending_pong.rx_time_ms, 255);
    pong_frame.data[5] = proc_time;

    /* Bytes 6-7: RoundTripTime (bits 48-63) - estimated RTT, little-endian */
    uint16_t our_ts = (uint16_t)((now - start_time_ms) & 0xFFFF);
    uint16_t rtt = (our_ts > pending_pong.ping_ts_offset)
                   ? (our_ts - pending_pong.ping_ts_offset)
                   : 0;
    pong_frame.data[6] = rtt & 0xFF;
    pong_frame.data[7] = (rtt >> 8) & 0xFF;

    ret = can_send(can_dev, &pong_frame, K_MSEC(100), NULL, NULL);
    if (ret != 0) {
        LOG_ERR("Failed to send PONG: %d", ret);
    } else {
        LOG_INF("PONG #%d: echo=%d proc=%dms rtt=%dms",
                ping_count, pending_pong.echo_counter, proc_time, rtt);
    }
}

static void can_rx_callback(const struct device *dev, struct can_frame *frame, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(user_data);

    if (frame->id == PING_MSG_ID && frame->dlc >= 8) {
        /* Verify PING identifier in first 4 bytes */
        if (memcmp(frame->data, "PING", 4) == 0) {
            ping_count++;

            /* Extract signal data from PING frame */
            pending_pong.echo_counter = frame->data[4];
            pending_pong.ping_ts_offset = frame->data[6] | (frame->data[7] << 8);
            pending_pong.rx_time_ms = k_uptime_get();

            LOG_INF("PING #%d: seq=%d str=%d%% ts=%dms",
                    ping_count, frame->data[4], frame->data[5],
                    pending_pong.ping_ts_offset);

            /* Send PONG from work queue (not ISR context) */
            k_work_submit(&pong_work);
        }
    }
}

int main(void)
{
    int ret;

    LOG_INF("CAN Pong Receiver starting...");

    start_time_ms = k_uptime_get();
    k_work_init(&pong_work, pong_work_handler);

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

    ret = can_add_rx_filter(can_dev, can_rx_callback, NULL, &ping_filter);
    if (ret < 0) {
        LOG_ERR("Failed to add RX filter: %d", ret);
        return ret;
    }

    LOG_INF("CAN ready, waiting for PING messages...");

    /* Keep running */
    while (1) {
        k_sleep(K_SECONDS(10));
        LOG_INF("Receiver alive - %d PINGs processed", ping_count);
    }

    return 0;
}
