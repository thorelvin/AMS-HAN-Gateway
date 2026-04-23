#include "serial_link.h"

#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "esp_mac.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "serial_link";
static serial_command_handler_t s_handler = NULL;

static const char *wifi_state_to_str(wifi_state_t state) {
    switch (state) {
        case WIFI_STATE_IDLE: return "IDLE";
        case WIFI_STATE_DISCONNECTED: return "DISCONNECTED";
        case WIFI_STATE_CONNECTING: return "CONNECTING";
        case WIFI_STATE_CONNECTED: return "CONNECTED";
        default: return "UNKNOWN";
    }
}

static const char *mqtt_state_to_str(mqtt_state_t state) {
    switch (state) {
        case MQTT_STATE_IDLE: return "IDLE";
        case MQTT_STATE_DISCONNECTED: return "DISCONNECTED";
        case MQTT_STATE_CONNECTING: return "CONNECTING";
        case MQTT_STATE_CONNECTED: return "CONNECTED";
        default: return "UNKNOWN";
    }
}

static void console_task(void *arg) {
    (void)arg;
    char line[SERIAL_LINE_MAX];
    while (1) {
        if (fgets(line, sizeof(line), stdin) == NULL) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len == 0) {
            continue;
        }
        ESP_LOGI(TAG, "RX CMD: %s", line);
        if (s_handler) {
            s_handler(line);
        }
    }
}

void serial_link_init(serial_command_handler_t handler) {
    s_handler = handler;
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    xTaskCreate(console_task, "console_task", 4096, NULL, 5, NULL);
}

void serial_link_send_ok(void) {
    printf("RSP:OK\n");
}

void serial_link_send_error(const char *reason) {
    printf("RSP:ERROR,%s\n", reason ? reason : "unknown");
}

void serial_link_send_info(const app_config_t *cfg) {
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    printf("RSP:INFO,%s,%s,%02X:%02X:%02X:%02X:%02X:%02X\n",
           FW_VERSION,
           cfg->device_id,
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

void serial_link_send_wifi_status(wifi_state_t state, const char *ip) {
    printf("RSP:WIFI,%s,%s\n", wifi_state_to_str(state), ip ? ip : "");
}

void serial_link_send_mqtt_status(mqtt_state_t state) {
    printf("RSP:MQTT,%s\n", mqtt_state_to_str(state));
}

void serial_link_send_status_line(const char *category, const char *state, const char *extra) {
    // STATUS lines are intentionally short because they are emitted often and are
    // consumed by both the live dashboard and replay fixtures.
    printf("STATUS,%s,%s", category ? category : "", state ? state : "");
    if (extra && extra[0]) {
        printf(",%s", extra);
    }
    printf("\n");
}

void serial_link_send_frame(uint32_t seq, const uint8_t *data, uint16_t len) {
    // Raw frames are hex-encoded so they remain printable, loggable, and replayable.
    printf("FRAME,%lu,%u,", (unsigned long)seq, (unsigned)len);
    for (uint16_t i = 0; i < len; ++i) {
        printf("%02X", data[i]);
    }
    printf("\n");
}

void serial_link_send_snapshot(const han_snapshot_t *s) {
    // SNAP is the dashboard-friendly summary row: fixed field order, compact values,
    // and easy parsing on the Python side and in replay files.
    printf("SNAP,%lu,%s,%s,%04u-%02u-%02u %02u:%02u:%02u,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.3f,%.3f,%.3f,%.1f,%.2f,%.3f,%.3f,%u,%lu,%lu\n",
           (unsigned long)s->seq,
           s->meter_id[0] ? s->meter_id : "",
           s->meter_type[0] ? s->meter_type : "",
           s->year, s->month, s->day, s->hour, s->minute, s->second,
           s->import_w, s->export_w, s->q_import_var, s->q_export_var,
           s->avg_voltage_v, s->phase_imbalance_a,
           s->l1_a, s->l2_a, s->l3_a,
           s->net_power_w, s->estimated_power_factor,
           s->total_current_a, s->apparent_power_va,
           s->rolling_samples,
           (unsigned long)s->frames_rx, (unsigned long)s->frames_bad);
}
