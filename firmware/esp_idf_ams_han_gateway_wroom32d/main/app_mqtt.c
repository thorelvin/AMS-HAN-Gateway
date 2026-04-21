#include "app_mqtt.h"

#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "mqtt_client.h"

static const char *TAG = "app_mqtt";
static const char *HA_DISCOVERY_PREFIX = "homeassistant";
static const char *HA_STATUS_TOPIC = "homeassistant/status";

static esp_mqtt_client_handle_t s_client = NULL;
static mqtt_state_t s_state = MQTT_STATE_IDLE;
static app_config_t s_cfg = {0};

static void make_topic(char *out, size_t out_len, const app_config_t *cfg, const char *suffix) {
    snprintf(out, out_len, "%s/%s/%s",
             cfg->topic_prefix[0] ? cfg->topic_prefix : "amshan",
             cfg->device_id,
             suffix);
}

static void make_discovery_topic(char *out, size_t out_len, const char *component, const app_config_t *cfg, const char *object_id) {
    snprintf(out, out_len, "%s/%s/%s_%s/config",
             HA_DISCOVERY_PREFIX,
             component,
             cfg->device_id,
             object_id);
}

static void make_unique_id(char *out, size_t out_len, const app_config_t *cfg, const char *object_id) {
    snprintf(out, out_len, "%s_%s", cfg->device_id, object_id);
}

static int publish_retained(const char *topic, const char *payload, int qos) {
    if (!s_client || s_state != MQTT_STATE_CONNECTED || !topic || !payload) {
        return -1;
    }
    return esp_mqtt_client_publish(s_client, topic, payload, 0, qos, 1);
}

static int publish_unretained(const char *topic, const char *payload, int qos) {
    if (!s_client || s_state != MQTT_STATE_CONNECTED || !topic || !payload) {
        return -1;
    }
    return esp_mqtt_client_publish(s_client, topic, payload, 0, qos, 0);
}

static void publish_availability(bool online) {
    char topic[MQTT_TOPIC_MAX];
    make_topic(topic, sizeof(topic), &s_cfg, "availability");
    publish_retained(topic, online ? "online" : "offline", 1);
}

static void publish_sensor_discovery(const app_config_t *cfg,
                                     const char *object_id,
                                     const char *name,
                                     const char *state_topic,
                                     const char *value_template,
                                     const char *unit,
                                     const char *device_class,
                                     const char *state_class,
                                     const char *entity_category,
                                     const char *icon) {
    char topic[MQTT_TOPIC_MAX + 64];
    char avail_topic[MQTT_TOPIC_MAX];
    char unique_id[DEVICE_ID_MAX + 48];
    char payload[1024];
    char extras[256] = "";

    if (unit && unit[0]) {
        strncat(extras, "\"unit_of_measurement\":\"", sizeof(extras) - strlen(extras) - 1);
        strncat(extras, unit, sizeof(extras) - strlen(extras) - 1);
        strncat(extras, "\",", sizeof(extras) - strlen(extras) - 1);
    }
    if (device_class && device_class[0]) {
        strncat(extras, "\"device_class\":\"", sizeof(extras) - strlen(extras) - 1);
        strncat(extras, device_class, sizeof(extras) - strlen(extras) - 1);
        strncat(extras, "\",", sizeof(extras) - strlen(extras) - 1);
    }
    if (state_class && state_class[0]) {
        strncat(extras, "\"state_class\":\"", sizeof(extras) - strlen(extras) - 1);
        strncat(extras, state_class, sizeof(extras) - strlen(extras) - 1);
        strncat(extras, "\",", sizeof(extras) - strlen(extras) - 1);
    }
    if (entity_category && entity_category[0]) {
        strncat(extras, "\"entity_category\":\"", sizeof(extras) - strlen(extras) - 1);
        strncat(extras, entity_category, sizeof(extras) - strlen(extras) - 1);
        strncat(extras, "\",", sizeof(extras) - strlen(extras) - 1);
    }
    if (icon && icon[0]) {
        strncat(extras, "\"icon\":\"", sizeof(extras) - strlen(extras) - 1);
        strncat(extras, icon, sizeof(extras) - strlen(extras) - 1);
        strncat(extras, "\",", sizeof(extras) - strlen(extras) - 1);
    }

    make_discovery_topic(topic, sizeof(topic), "sensor", cfg, object_id);
    make_topic(avail_topic, sizeof(avail_topic), cfg, "availability");
    make_unique_id(unique_id, sizeof(unique_id), cfg, object_id);

    snprintf(payload, sizeof(payload),
             "{"
             "\"name\":\"%s\"," 
             "\"unique_id\":\"%s\"," 
             "\"state_topic\":\"%s\"," 
             "\"value_template\":\"%s\"," 
             "%s"
             "\"availability_topic\":\"%s\"," 
             "\"payload_available\":\"online\"," 
             "\"payload_not_available\":\"offline\"," 
             "\"device\":{"
                 "\"identifiers\":[\"%s\"],"
                 "\"name\":\"AMS HAN Gateway %s\"," 
                 "\"manufacturer\":\"thorelvin\"," 
                 "\"model\":\"AMS HAN Gateway (ESP32-WROOM-32D)\"," 
                 "\"sw_version\":\"%s\""
             "}"
             "}",
             name,
             unique_id,
             state_topic,
             value_template,
             extras,
             avail_topic,
             cfg->device_id,
             cfg->device_id,
             FW_VERSION);

    publish_retained(topic, payload, 1);
}

void app_mqtt_publish_discovery(const app_config_t *cfg) {
    if (!cfg || !s_client || s_state != MQTT_STATE_CONNECTED) {
        return;
    }

    char state_power[MQTT_TOPIC_MAX];
    char state_phases[MQTT_TOPIC_MAX];
    char state_metrics[MQTT_TOPIC_MAX];

    make_topic(state_power, sizeof(state_power), cfg, "live/power");
    make_topic(state_phases, sizeof(state_phases), cfg, "live/phases");
    make_topic(state_metrics, sizeof(state_metrics), cfg, "live/metrics");

    publish_sensor_discovery(cfg, "import_power", "Import power", state_power, "{{ value_json.import_w }}", "W", "power", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "export_power", "Export power", state_power, "{{ value_json.export_w }}", "W", "power", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "net_power", "Net power", state_power, "{{ value_json.net_power_w }}", "W", "power", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "apparent_power", "Apparent power", state_power, "{{ value_json.apparent_power_va }}", "VA", "apparent_power", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "power_factor", "Estimated power factor", state_power, "{{ value_json.estimated_power_factor }}", NULL, NULL, "measurement", NULL, "mdi:angle-acute");

    publish_sensor_discovery(cfg, "l1_voltage", "L1 voltage", state_phases, "{{ value_json.l1_v }}", "V", "voltage", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "l2_voltage", "L2 voltage", state_phases, "{{ value_json.l2_v }}", "V", "voltage", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "l3_voltage", "L3 voltage", state_phases, "{{ value_json.l3_v }}", "V", "voltage", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "l1_current", "L1 current", state_phases, "{{ value_json.l1_a }}", "A", "current", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "l2_current", "L2 current", state_phases, "{{ value_json.l2_a }}", "A", "current", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "l3_current", "L3 current", state_phases, "{{ value_json.l3_a }}", "A", "current", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "phase_imbalance", "Phase imbalance", state_phases, "{{ value_json.phase_imbalance_a }}", "A", NULL, "measurement", NULL, "mdi:scale-unbalanced");

    publish_sensor_discovery(cfg, "avg_voltage", "Average voltage", state_metrics, "{{ value_json.avg_voltage_v }}", "V", "voltage", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "total_current", "Total current", state_metrics, "{{ value_json.total_current_a }}", "A", "current", "measurement", NULL, NULL);
    publish_sensor_discovery(cfg, "wifi_rssi", "Wi-Fi RSSI", state_metrics, "{{ value_json.wifi_rssi }}", "dBm", "signal_strength", "measurement", "diagnostic", NULL);
    publish_sensor_discovery(cfg, "frames_rx", "Frames received", state_metrics, "{{ value_json.frames_rx }}", NULL, NULL, "measurement", "diagnostic", "mdi:counter");
    publish_sensor_discovery(cfg, "frames_bad", "Bad frames", state_metrics, "{{ value_json.frames_bad }}", NULL, NULL, "measurement", "diagnostic", "mdi:counter-alert");
    publish_sensor_discovery(cfg, "frame_age", "Frame age", state_metrics, "{{ value_json.frame_age_ms }}", "ms", NULL, "measurement", "diagnostic", "mdi:timer-sand");
}

static bool mqtt_event_matches(const esp_mqtt_event_handle_t event, const char *topic, const char *payload) {
    if (!event || !topic || !payload) {
        return false;
    }

    size_t topic_len = strlen(topic);
    size_t payload_len = strlen(payload);
    return event->topic_len == (int)topic_len &&
           event->data_len == (int)payload_len &&
           strncmp(event->topic, topic, topic_len) == 0 &&
           strncmp(event->data, payload, payload_len) == 0;
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    (void)handler_args;
    (void)base;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            s_state = MQTT_STATE_CONNECTED;
            ESP_LOGI(TAG, "MQTT connected");
            esp_mqtt_client_subscribe(s_client, HA_STATUS_TOPIC, 1);
            publish_availability(true);
            app_mqtt_publish_discovery(&s_cfg);
            break;
        case MQTT_EVENT_DISCONNECTED:
            s_state = MQTT_STATE_DISCONNECTED;
            ESP_LOGW(TAG, "MQTT disconnected");
            break;
        case MQTT_EVENT_DATA:
            if (mqtt_event_matches(event, HA_STATUS_TOPIC, "online")) {
                ESP_LOGI(TAG, "Home Assistant birth message received, republishing discovery");
                publish_availability(true);
                app_mqtt_publish_discovery(&s_cfg);
            }
            break;
        default:
            break;
    }
}

void app_mqtt_init(void) {
    memset(&s_cfg, 0, sizeof(s_cfg));
    s_state = MQTT_STATE_IDLE;
}

void app_mqtt_stop(void) {
    if (s_client) {
        esp_mqtt_client_stop(s_client);
        esp_mqtt_client_destroy(s_client);
        s_client = NULL;
    }
    s_state = MQTT_STATE_IDLE;
}

void app_mqtt_apply_config(const app_config_t *cfg) {
    if (!cfg || !cfg->mqtt_enabled || cfg->mqtt_host[0] == '\0') {
        app_mqtt_stop();
        return;
    }

    app_mqtt_stop();
    s_cfg = *cfg;

    char broker_uri[160];
    char lwt_topic[MQTT_TOPIC_MAX];
    snprintf(broker_uri, sizeof(broker_uri), "mqtt://%s:%d", cfg->mqtt_host, cfg->mqtt_port);
    make_topic(lwt_topic, sizeof(lwt_topic), cfg, "availability");

    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = broker_uri,
        .credentials.username = cfg->mqtt_user[0] ? cfg->mqtt_user : NULL,
        .credentials.authentication.password = cfg->mqtt_password[0] ? cfg->mqtt_password : NULL,
        .session.last_will.topic = lwt_topic,
        .session.last_will.msg = "offline",
        .session.last_will.msg_len = 7,
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
    };

    s_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    s_state = MQTT_STATE_CONNECTING;
    esp_mqtt_client_start(s_client);
}

mqtt_state_t app_mqtt_get_state(void) {
    return s_state;
}

void app_mqtt_publish_status(const app_config_t *cfg, wifi_state_t wifi_state, mqtt_state_t mqtt_state, const char *ip) {
    if (!s_client || s_state != MQTT_STATE_CONNECTED || !cfg) {
        return;
    }

    char topic[MQTT_TOPIC_MAX];
    char payload[256];
    make_topic(topic, sizeof(topic), cfg, "status");

    snprintf(payload, sizeof(payload),
             "{\"wifi_state\":%d,\"mqtt_state\":%d,\"ip\":\"%s\"}",
             (int)wifi_state, (int)mqtt_state, ip ? ip : "");

    publish_retained(topic, payload, 1);
}

void app_mqtt_publish_snapshot(const app_config_t *cfg, const han_snapshot_t *s, int wifi_rssi) {
    if (!s_client || s_state != MQTT_STATE_CONNECTED || !cfg || !s) {
        return;
    }

    char topic[MQTT_TOPIC_MAX];
    char payload[1024];

    make_topic(topic, sizeof(topic), cfg, "live/power");
    snprintf(payload, sizeof(payload),
             "{\"seq\":%lu,\"import_w\":%.1f,\"export_w\":%.1f,\"reactive_import_var\":%.1f,\"reactive_export_var\":%.1f,\"net_power_w\":%.1f,\"apparent_power_va\":%.1f,\"estimated_power_factor\":%.3f,\"rolling_import_w\":%.1f,\"rolling_net_power_w\":%.1f,\"rolling_samples\":%u}",
             (unsigned long)s->seq, s->import_w, s->export_w,
             s->q_import_var, s->q_export_var, s->net_power_w,
             s->apparent_power_va, s->estimated_power_factor,
             s->rolling_import_w, s->rolling_net_power_w, s->rolling_samples);
    publish_retained(topic, payload, 1);

    make_topic(topic, sizeof(topic), cfg, "live/phases");
    snprintf(payload, sizeof(payload),
             "{\"l1_v\":%.1f,\"l2_v\":%.1f,\"l3_v\":%.1f,\"l1_a\":%.3f,\"l2_a\":%.3f,\"l3_a\":%.3f,\"phase_imbalance_a\":%.3f,\"rolling_l1_a\":%.3f,\"rolling_l2_a\":%.3f,\"rolling_l3_a\":%.3f}",
             s->l1_v, s->l2_v, s->l3_v,
             s->l1_a, s->l2_a, s->l3_a,
             s->phase_imbalance_a,
             s->rolling_l1_a, s->rolling_l2_a, s->rolling_l3_a);
    publish_retained(topic, payload, 1);

    make_topic(topic, sizeof(topic), cfg, "live/meta");
    snprintf(payload, sizeof(payload),
             "{\"meter_id\":\"%s\",\"meter_type\":\"%s\",\"list_id\":\"%s\",\"timestamp\":\"%04u-%02u-%02u %02u:%02u:%02u\",\"kaifa_valid\":%s}",
             s->meter_id, s->meter_type, s->list_id,
             s->year, s->month, s->day, s->hour, s->minute, s->second,
             s->kaifa_valid ? "true" : "false");
    publish_retained(topic, payload, 1);

    make_topic(topic, sizeof(topic), cfg, "live/metrics");
    snprintf(payload, sizeof(payload),
             "{\"avg_voltage_v\":%.1f,\"total_current_a\":%.3f,\"frames_rx\":%lu,\"frames_bad\":%lu,\"frame_age_ms\":%lu,\"wifi_rssi\":%d}",
             s->avg_voltage_v, s->total_current_a,
             (unsigned long)s->frames_rx, (unsigned long)s->frames_bad,
             (unsigned long)s->frame_age_ms, wifi_rssi);
    publish_retained(topic, payload, 1);

    if (s->raw_valid) {
        make_topic(topic, sizeof(topic), cfg, "live/raw");
        size_t pos = (size_t)snprintf(payload, sizeof(payload), "{\"seq\":%lu,\"len\":%u,\"hex\":\"",
                                      (unsigned long)s->seq, (unsigned)s->raw_len);
        for (uint16_t i = 0; i < s->raw_len && pos + 3 < sizeof(payload); ++i) {
            pos += (size_t)snprintf(payload + pos, sizeof(payload) - pos, "%02X", s->raw[i]);
        }
        snprintf(payload + pos, sizeof(payload) - pos, "\"}");
        publish_unretained(topic, payload, 0);
    }
}
