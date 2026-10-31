/*
 * Ethernet Ping Sender (Linux/S32G)
 * Sends "PING" messages over UDP and waits for "PONG" responses
 *
 * Build: aarch64-linux-gnu-gcc -static -O2 -o eth_sender main.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <poll.h>

#define UDP_PORT         5000
#define PING_INTERVAL_MS 1000
#define RECV_TIMEOUT_MS  500
#define BUFFER_SIZE      64

#define MY_IP_ADDR       "192.168.100.1"
#define PEER_IP_ADDR     "192.168.100.2"

static uint32_t ping_count = 0;
static uint32_t pong_count = 0;

static uint64_t get_time_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

int main(int argc, char *argv[])
{
    int sock;
    struct sockaddr_in my_addr, peer_addr;
    char tx_buffer[BUFFER_SIZE];
    char rx_buffer[BUFFER_SIZE];
    int ret;
    int interval_ms = PING_INTERVAL_MS;

    if (argc > 1) {
        interval_ms = atoi(argv[1]);
        if (interval_ms < 100) interval_ms = 100;
    }

    printf("Ethernet Ping Sender (S32G/Linux) starting...\n");
    printf("My IP: %s\n", MY_IP_ADDR);
    printf("Target IP: %s:%d\n", PEER_IP_ADDR, UDP_PORT);
    printf("Ping interval: %d ms\n", interval_ms);

    /* Create UDP socket */
    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        perror("Failed to create socket");
        return 1;
    }

    /* Bind to our address and port */
    memset(&my_addr, 0, sizeof(my_addr));
    my_addr.sin_family = AF_INET;
    my_addr.sin_port = htons(UDP_PORT);
    inet_pton(AF_INET, MY_IP_ADDR, &my_addr.sin_addr);

    ret = bind(sock, (struct sockaddr *)&my_addr, sizeof(my_addr));
    if (ret < 0) {
        perror("Failed to bind socket");
        close(sock);
        return 1;
    }

    /* Set up peer address */
    memset(&peer_addr, 0, sizeof(peer_addr));
    peer_addr.sin_family = AF_INET;
    peer_addr.sin_port = htons(UDP_PORT);
    inet_pton(AF_INET, PEER_IP_ADDR, &peer_addr.sin_addr);

    printf("Socket ready, starting ping loop...\n\n");

    while (1) {
        ping_count++;
        uint64_t send_time = get_time_ms();

        /* Prepare PING message */
        snprintf(tx_buffer, sizeof(tx_buffer), "PING %u", ping_count);

        /* Send PING */
        ret = sendto(sock, tx_buffer, strlen(tx_buffer), 0,
                     (struct sockaddr *)&peer_addr, sizeof(peer_addr));
        if (ret < 0) {
            perror("Failed to send PING");
        } else {
            printf("[%u] PING sent (seq=%u)\n", ping_count, ping_count);

            /* Wait for PONG response with timeout */
            struct pollfd fds = {
                .fd = sock,
                .events = POLLIN
            };

            ret = poll(&fds, 1, RECV_TIMEOUT_MS);
            if (ret > 0 && (fds.revents & POLLIN)) {
                struct sockaddr_in from_addr;
                socklen_t from_len = sizeof(from_addr);

                ret = recvfrom(sock, rx_buffer, sizeof(rx_buffer) - 1, 0,
                               (struct sockaddr *)&from_addr, &from_len);
                if (ret > 0) {
                    rx_buffer[ret] = '\0';
                    uint64_t recv_time = get_time_ms();
                    uint64_t rtt = recv_time - send_time;

                    if (strstr(rx_buffer, "PONG")) {
                        pong_count++;
                        printf("[%u] PONG received (seq=%u, RTT=%lu ms)\n",
                               pong_count, pong_count, (unsigned long)rtt);
                    } else {
                        printf("[!] Unexpected response: %s\n", rx_buffer);
                    }
                }
            } else {
                printf("[!] No PONG for PING #%u (timeout)\n", ping_count);
            }
        }

        usleep(interval_ms * 1000);
    }

    close(sock);
    return 0;
}
