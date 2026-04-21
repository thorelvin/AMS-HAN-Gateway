#pragma once

#include "app_config.h"
#include <stdbool.h>

void wifi_manager_init(void);
void wifi_manager_apply_config(const app_config_t *cfg);
void wifi_manager_disconnect(void);
wifi_state_t wifi_manager_get_state(void);
bool wifi_manager_is_connected(void);
const char *wifi_manager_get_ip(void);
int wifi_manager_get_rssi(void);
