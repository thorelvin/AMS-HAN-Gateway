#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "driver/uart.h"

#define FW_VERSION              "0.2.0-wroom32d"
#define DEVICE_NAME_PREFIX      "amshan"

#define HAN_UART_NUM            UART_NUM_2
#define HAN_UART_RX_PIN         16
#define HAN_UART_TX_PIN         17
#define HAN_UART_BAUDRATE       2400
#define HAN_UART_BUF_SIZE       2048

#define SERIAL_LINE_MAX         512
#define MQTT_TOPIC_MAX          128
#define WIFI_STR_MAX            64
#define MQTT_HOST_MAX           64
#define MQTT_USER_MAX           64
#define MQTT_PASS_MAX           64
#define TOPIC_PREFIX_MAX        64
#define DEVICE_ID_MAX           32
#define RAW_FRAME_MAX           256
#define KFM_LIST_ID_MAX         8
#define KFM_METER_ID_MAX        17
#define KFM_METER_TYPE_MAX      9
#define ROLLING_WINDOW_FRAMES   6

typedef struct {
    bool wifi_configured;
    char wifi_ssid[WIFI_STR_MAX];
    char wifi_password[WIFI_STR_MAX];

    bool mqtt_enabled;
    char mqtt_host[MQTT_HOST_MAX];
    int  mqtt_port;
    char mqtt_user[MQTT_USER_MAX];
    char mqtt_password[MQTT_PASS_MAX];
    char topic_prefix[TOPIC_PREFIX_MAX];

    char device_id[DEVICE_ID_MAX];
} app_config_t;

typedef struct {
    uint32_t seq;
    uint32_t ts_ms;
    bool raw_valid;
    bool values_valid;
    bool kaifa_valid;

    uint8_t raw[RAW_FRAME_MAX];
    uint16_t raw_len;

    char list_id[KFM_LIST_ID_MAX];
    char meter_id[KFM_METER_ID_MAX];
    char meter_type[KFM_METER_TYPE_MAX];

    uint16_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;

    float import_w;
    float export_w;
    float q_import_var;
    float q_export_var;

    float l1_v;
    float l2_v;
    float l3_v;

    float l1_a;
    float l2_a;
    float l3_a;

    float total_current_a;
    float avg_voltage_v;
    float phase_imbalance_a;
    float net_power_w;
    float apparent_power_va;
    float estimated_power_factor;

    float rolling_import_w;
    float rolling_export_w;
    float rolling_net_power_w;
    float rolling_l1_a;
    float rolling_l2_a;
    float rolling_l3_a;
    float rolling_l1_v;
    float rolling_l2_v;
    float rolling_l3_v;
    uint8_t rolling_samples;

    uint32_t frame_age_ms;
    uint32_t frames_rx;
    uint32_t frames_bad;
} han_snapshot_t;

typedef void (*han_snapshot_callback_t)(const han_snapshot_t *snapshot);

typedef enum {
    WIFI_STATE_IDLE = 0,
    WIFI_STATE_DISCONNECTED,
    WIFI_STATE_CONNECTING,
    WIFI_STATE_CONNECTED
} wifi_state_t;

typedef enum {
    MQTT_STATE_IDLE = 0,
    MQTT_STATE_DISCONNECTED,
    MQTT_STATE_CONNECTING,
    MQTT_STATE_CONNECTED
} mqtt_state_t;
