idf_component_register(
    SRCS
        "app_main.c"
        "config_store.c"
        "serial_link.c"
        "wifi_manager.c"
        "app_mqtt.c"
        "telemetry.c"
        "han_reader.c"
        "provisioning_stub.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_wifi
        esp_event
        nvs_flash
        mqtt
)
