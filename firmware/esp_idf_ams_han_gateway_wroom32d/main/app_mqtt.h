#pragma once

#include "app_config.h"

void app_mqtt_init(void);
void app_mqtt_apply_config(const app_config_t *cfg);
void app_mqtt_stop(void);
mqtt_state_t app_mqtt_get_state(void);
void app_mqtt_publish_snapshot(const app_config_t *cfg, const han_snapshot_t *snapshot, int wifi_rssi);
void app_mqtt_publish_status(const app_config_t *cfg, wifi_state_t wifi_state, mqtt_state_t mqtt_state, const char *ip);
void app_mqtt_publish_discovery(const app_config_t *cfg);
