#include "config_store.h"
#include <string.h>
#include "nvs.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_check.h"
#include <stdio.h>

static const char *TAG = "config_store";
static const char *NAMESPACE = "amshan";

static void make_device_id(char *out, size_t out_len) {
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(out, out_len, "esp32-%02X%02X%02X", mac[3], mac[4], mac[5]);
}

void config_store_fill_defaults(app_config_t *cfg) {
    memset(cfg, 0, sizeof(*cfg));
    cfg->mqtt_port = 1883;
    cfg->mqtt_enabled = false;
    snprintf(cfg->topic_prefix, sizeof(cfg->topic_prefix), "amshan");
    make_device_id(cfg->device_id, sizeof(cfg->device_id));
}

esp_err_t config_store_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

esp_err_t config_store_load(app_config_t *cfg) {
    config_store_fill_defaults(cfg);

    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NAMESPACE, NVS_READONLY, &nvs);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "No saved config, using defaults");
        return ESP_OK;
    }

    size_t len = sizeof(cfg->wifi_ssid);
    if (nvs_get_str(nvs, "wifi_ssid", cfg->wifi_ssid, &len) == ESP_OK) {
        cfg->wifi_configured = (cfg->wifi_ssid[0] != '\0');
    }

    len = sizeof(cfg->wifi_password);
    nvs_get_str(nvs, "wifi_pass", cfg->wifi_password, &len);

    len = sizeof(cfg->mqtt_host);
    nvs_get_str(nvs, "mqtt_host", cfg->mqtt_host, &len);

    uint8_t mqtt_enabled = 0;
    if (nvs_get_u8(nvs, "mqtt_en", &mqtt_enabled) == ESP_OK) {
        cfg->mqtt_enabled = mqtt_enabled != 0;
    }

    uint32_t port = 1883;
    if (nvs_get_u32(nvs, "mqtt_port", &port) == ESP_OK) {
        cfg->mqtt_port = (int)port;
    }

    len = sizeof(cfg->mqtt_user);
    nvs_get_str(nvs, "mqtt_user", cfg->mqtt_user, &len);

    len = sizeof(cfg->mqtt_password);
    nvs_get_str(nvs, "mqtt_pass", cfg->mqtt_password, &len);

    len = sizeof(cfg->topic_prefix);
    nvs_get_str(nvs, "topic_pref", cfg->topic_prefix, &len);

    len = sizeof(cfg->device_id);
    nvs_get_str(nvs, "device_id", cfg->device_id, &len);

    nvs_close(nvs);
    return ESP_OK;
}

esp_err_t config_store_save(const app_config_t *cfg) {
    nvs_handle_t nvs;
    ESP_RETURN_ON_ERROR(nvs_open(NAMESPACE, NVS_READWRITE, &nvs), TAG, "nvs_open failed");

    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "wifi_ssid", cfg->wifi_ssid), TAG, "set wifi_ssid");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "wifi_pass", cfg->wifi_password), TAG, "set wifi_pass");
    ESP_RETURN_ON_ERROR(nvs_set_u8(nvs, "mqtt_en", cfg->mqtt_enabled ? 1 : 0), TAG, "set mqtt_en");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "mqtt_host", cfg->mqtt_host), TAG, "set mqtt_host");
    ESP_RETURN_ON_ERROR(nvs_set_u32(nvs, "mqtt_port", (uint32_t)cfg->mqtt_port), TAG, "set mqtt_port");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "mqtt_user", cfg->mqtt_user), TAG, "set mqtt_user");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "mqtt_pass", cfg->mqtt_password), TAG, "set mqtt_pass");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "topic_pref", cfg->topic_prefix), TAG, "set topic_pref");
    ESP_RETURN_ON_ERROR(nvs_set_str(nvs, "device_id", cfg->device_id), TAG, "set device_id");
    ESP_RETURN_ON_ERROR(nvs_commit(nvs), TAG, "commit");
    nvs_close(nvs);
    return ESP_OK;
}

esp_err_t config_store_factory_reset(void) {
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NAMESPACE, NVS_READWRITE, &nvs);
    if (err == ESP_OK) {
        nvs_erase_all(nvs);
        nvs_commit(nvs);
        nvs_close(nvs);
    }
    return err == ESP_ERR_NVS_NOT_FOUND ? ESP_OK : err;
}
