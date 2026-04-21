#pragma once

#include "app_config.h"
#include "esp_err.h"

esp_err_t config_store_init(void);
esp_err_t config_store_load(app_config_t *cfg);
esp_err_t config_store_save(const app_config_t *cfg);
esp_err_t config_store_factory_reset(void);
void config_store_fill_defaults(app_config_t *cfg);
