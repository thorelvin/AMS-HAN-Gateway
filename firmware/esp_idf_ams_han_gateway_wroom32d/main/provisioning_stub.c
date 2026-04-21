#include "provisioning_stub.h"
#include "esp_log.h"

static const char *TAG = "provisioning";
static bool s_running = false;

void provisioning_stub_start(void) {
    s_running = true;
    ESP_LOGW(TAG, "Provisioning stub only. Hook ESP-IDF unified provisioning here.");
}

void provisioning_stub_stop(void) {
    s_running = false;
}

bool provisioning_stub_is_running(void) {
    return s_running;
}
