/*
 * Ethernet Pong Receiver (Linux/S32G)
 * Receives "PING" messages over UDP and responds with "PONG"
 *
 * Build: aarch64-linux-gnu-gcc -static -O2 -o eth_receiver main.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define UDP_PORT    5000
#define BUFFER_SIZE 64

#define MY_IP_ADDR  "192.168.100.2"

static uint32_t ping_count = 0;

int main(void)
{
    int sock;
    struct sockaddr_in my_addr, from_addr;
    socklen_t from_len;
    char rx_buffer[BUFFER_SIZE];
    char tx_buffer[BUFFER_SIZE];
    int ret;

    printf("Ethernet Pong Receiver (S32G/Linux) starting...\n");
    printf("My IP: %s\n", MY_IP_ADDR);
    printf("Listening on UDP port %d...\n\n", UDP_PORT);

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
    my_addr.sin_addr.s_addr = INADDR_ANY;

    ret = bind(sock, (struct sockaddr *)&my_addr, sizeof(my_addr));
    if (ret < 0) {
        perror("Failed to bind socket");
        close(sock);
        return 1;
    }

    printf("Server ready. Press Ctrl+C to stop.\n\n");

    while (1) {
        from_len = sizeof(from_addr);

        /* Receive incoming packet */
        ret = recvfrom(sock, rx_buffer, sizeof(rx_buffer) - 1, 0,
                       (struct sockaddr *)&from_addr, &from_len);
        if (ret < 0) {
            perror("Failed to receive");
            continue;
        }

        rx_buffer[ret] = '\0';

        /* Check if it's a PING message */
        if (strstr(rx_buffer, "PING")) {
            ping_count++;

            /* Get sender's IP for logging */
            char sender_ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &from_addr.sin_addr, sender_ip, sizeof(sender_ip));

            printf("[%u] PING received from %s - sending PONG\n", ping_count, sender_ip);

            /* Send PONG response */
            snprintf(tx_buffer, sizeof(tx_buffer), "PONG %u", ping_count);

            ret = sendto(sock, tx_buffer, strlen(tx_buffer), 0,
                         (struct sockaddr *)&from_addr, from_len);
            if (ret < 0) {
                perror("Failed to send PONG");
            }
        }
    }

    close(sock);
    return 0;
}
