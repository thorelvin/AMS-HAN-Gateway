#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "app_config.h"
#include "config_store.h"
#include "serial_link.h"
#include "wifi_manager.h"
#include "app_mqtt.h"
#include "han_reader.h"
#include "provisioning_stub.h"

static const char *TAG = "app_main";
static app_config_t s_cfg;
static han_snapshot_t s_last_snapshot;
static bool s_have_snapshot = false;

typedef struct {
    size_t count;
    char *fields[8];
} command_fields_t;

static void publish_status(void) {
    serial_link_send_wifi_status(wifi_manager_get_state(), wifi_manager_get_ip());
    serial_link_send_mqtt_status(app_mqtt_get_state());
    app_mqtt_publish_status(&s_cfg, wifi_manager_get_state(), app_mqtt_get_state(), wifi_manager_get_ip());
}

static void apply_runtime_config(void) {
    if (s_cfg.wifi_configured) {
        wifi_manager_apply_config(&s_cfg);
    }
    if (s_cfg.mqtt_enabled && wifi_manager_is_connected()) {
        app_mqtt_apply_config(&s_cfg);
    } else if (!s_cfg.mqtt_enabled) {
        app_mqtt_stop();
    }
}

static bool split_command_fields(const char *line, char *buffer, size_t buffer_size, command_fields_t *out) {
    size_t src = 0;
    size_t dst = 0;
    size_t count = 0;

    if (!line || !buffer || !out || buffer_size == 0) {
        return false;
    }

    memset(out, 0, sizeof(*out));
    out->fields[count++] = &buffer[0];

    while (line[src] != '\0') {
        char ch = line[src++];
        if (ch == '\\') {
            char next = line[src];
            if (next == '\0') {
                ch = '\\';
            } else {
                src++;
                if (next == 'n') {
                    ch = '\n';
                } else if (next == 'r') {
                    ch = '\r';
                } else {
                    ch = next;
                }
            }
        } else if (ch == ',') {
            if (dst + 1 >= buffer_size || count >= (sizeof(out->fields) / sizeof(out->fields[0]))) {
                return false;
            }
            buffer[dst++] = '\0';
            out->fields[count++] = &buffer[dst];
            continue;
        }

        if (dst + 1 >= buffer_size) {
            return false;
        }
        buffer[dst++] = ch;
    }

    buffer[dst] = '\0';
    out->count = count;
    return true;
}

static bool require_field_count(const command_fields_t *fields, size_t min_count, const char *error_reason) {
    if (!fields || fields->count < min_count) {
        serial_link_send_error(error_reason);
        return false;
    }
    return true;
}

static void handle_command(const char *line) {
    char copy[SERIAL_LINE_MAX];
    command_fields_t fields;
    if (!split_command_fields(line, copy, sizeof(copy), &fields) || fields.count == 0) {
        serial_link_send_error("bad_command_encoding");
        return;
    }

    const char *command = fields.fields[0];

    if (strcmp(command, "GET_INFO") == 0) {
        serial_link_send_info(&s_cfg);
        return;
    }

    if (strcmp(command, "GET_STATUS") == 0) {
        publish_status();
        if (s_have_snapshot) {
            serial_link_send_snapshot(&s_last_snapshot);
        }
        return;
    }

    if (strcmp(command, "REPUBLISH_DISCOVERY") == 0) {
        app_mqtt_publish_discovery(&s_cfg);
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "SET_WIFI") == 0) {
        if (!require_field_count(&fields, 3, "bad_set_wifi")) {
            return;
        }
        const char *ssid = fields.fields[1];
        const char *pass = fields.fields[2];

        memset(s_cfg.wifi_ssid, 0, sizeof(s_cfg.wifi_ssid));
        memset(s_cfg.wifi_password, 0, sizeof(s_cfg.wifi_password));
        strncpy(s_cfg.wifi_ssid, ssid, sizeof(s_cfg.wifi_ssid) - 1);
        strncpy(s_cfg.wifi_password, pass, sizeof(s_cfg.wifi_password) - 1);
        s_cfg.wifi_configured = true;

        config_store_save(&s_cfg);
        wifi_manager_apply_config(&s_cfg);
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "CLEAR_WIFI") == 0) {
        memset(s_cfg.wifi_ssid, 0, sizeof(s_cfg.wifi_ssid));
        memset(s_cfg.wifi_password, 0, sizeof(s_cfg.wifi_password));
        s_cfg.wifi_configured = false;
        config_store_save(&s_cfg);
        wifi_manager_disconnect();
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "SET_MQTT") == 0) {
        if (!require_field_count(&fields, 3, "bad_set_mqtt")) {
            return;
        }
        const char *host = fields.fields[1];
        const char *port = fields.fields[2];
        const char *user = fields.count > 3 ? fields.fields[3] : NULL;
        const char *pass = fields.count > 4 ? fields.fields[4] : NULL;
        const char *prefix = fields.count > 5 ? fields.fields[5] : NULL;

        memset(s_cfg.mqtt_host, 0, sizeof(s_cfg.mqtt_host));
        memset(s_cfg.mqtt_user, 0, sizeof(s_cfg.mqtt_user));
        memset(s_cfg.mqtt_password, 0, sizeof(s_cfg.mqtt_password));

        strncpy(s_cfg.mqtt_host, host, sizeof(s_cfg.mqtt_host) - 1);
        s_cfg.mqtt_port = atoi(port);
        if (user) strncpy(s_cfg.mqtt_user, user, sizeof(s_cfg.mqtt_user) - 1);
        if (pass) strncpy(s_cfg.mqtt_password, pass, sizeof(s_cfg.mqtt_password) - 1);
        if (prefix && prefix[0]) strncpy(s_cfg.topic_prefix, prefix, sizeof(s_cfg.topic_prefix) - 1);

        config_store_save(&s_cfg);
        if (s_cfg.mqtt_enabled && wifi_manager_is_connected()) {
            app_mqtt_apply_config(&s_cfg);
        }
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "MQTT_ENABLE") == 0) {
        s_cfg.mqtt_enabled = true;
        config_store_save(&s_cfg);
        if (wifi_manager_is_connected()) {
            app_mqtt_apply_config(&s_cfg);
        }
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "MQTT_DISABLE") == 0) {
        s_cfg.mqtt_enabled = false;
        config_store_save(&s_cfg);
        app_mqtt_stop();
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "START_PROVISIONING") == 0) {
        provisioning_stub_start();
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "STOP_PROVISIONING") == 0) {
        provisioning_stub_stop();
        serial_link_send_ok();
        return;
    }

    if (strcmp(command, "REBOOT") == 0) {
        serial_link_send_ok();
        vTaskDelay(pdMS_TO_TICKS(200));
        esp_restart();
        return;
    }

    if (strcmp(command, "FACTORY_RESET") == 0) {
        config_store_factory_reset();
        config_store_fill_defaults(&s_cfg);
        app_mqtt_stop();
        wifi_manager_disconnect();
        serial_link_send_ok();
        vTaskDelay(pdMS_TO_TICKS(200));
        esp_restart();
        return;
    }

    serial_link_send_error("unknown_command");
}

static void on_snapshot(const han_snapshot_t *snapshot) {
    s_last_snapshot = *snapshot;
    s_have_snapshot = true;

    if (snapshot->raw_valid) {
        serial_link_send_frame(snapshot->seq, snapshot->raw, snapshot->raw_len);
    }
    if (snapshot->values_valid) {
        serial_link_send_snapshot(snapshot);
    }

    app_mqtt_publish_snapshot(&s_cfg, snapshot, wifi_manager_get_rssi());
}

static void status_task(void *arg) {
    while (1) {
        publish_status();

        if (wifi_manager_is_connected() && s_cfg.mqtt_enabled && app_mqtt_get_state() == MQTT_STATE_IDLE) {
            app_mqtt_apply_config(&s_cfg);
        }

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

void app_main(void) {
    esp_log_level_set("*", ESP_LOG_WARN);

    ESP_ERROR_CHECK(config_store_init());
    ESP_ERROR_CHECK(config_store_load(&s_cfg));

    serial_link_init(handle_command);
    wifi_manager_init();
    app_mqtt_init();
    han_reader_init(on_snapshot);

    apply_runtime_config();
    publish_status();

    xTaskCreate(status_task, "status_task", 4096, NULL, 4, NULL);

    ESP_LOGW(TAG, "AMS HAN gateway started");
}
