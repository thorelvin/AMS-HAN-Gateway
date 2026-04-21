#pragma once

#include "app_config.h"
#include <stdbool.h>

typedef void (*serial_command_handler_t)(const char *line);

void serial_link_init(serial_command_handler_t handler);
void serial_link_send_ok(void);
void serial_link_send_error(const char *reason);
void serial_link_send_info(const app_config_t *cfg);
void serial_link_send_wifi_status(wifi_state_t state, const char *ip);
void serial_link_send_mqtt_status(mqtt_state_t state);
void serial_link_send_status_line(const char *category, const char *state, const char *extra);
void serial_link_send_frame(uint32_t seq, const uint8_t *data, uint16_t len);
void serial_link_send_snapshot(const han_snapshot_t *snapshot);
