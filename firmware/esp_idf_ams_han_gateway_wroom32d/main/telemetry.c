#include "telemetry.h"
#include <math.h>
#include <string.h>

typedef struct {
    bool valid;
    float import_w;
    float export_w;
    float net_power_w;
    float l1_a;
    float l2_a;
    float l3_a;
    float l1_v;
    float l2_v;
    float l3_v;
} rolling_entry_t;

static rolling_entry_t s_window[ROLLING_WINDOW_FRAMES];
static uint8_t s_window_count = 0;
static uint8_t s_window_head = 0;

static float fmax3(float a, float b, float c) {
    float m = a > b ? a : b;
    return m > c ? m : c;
}

static float fmin3(float a, float b, float c) {
    float m = a < b ? a : b;
    return m < c ? m : c;
}

static float f_abs(float v) {
    return v < 0.0f ? -v : v;
}

static bool is_valid_voltage(float v) {
    return v > 1.0f;
}

void telemetry_apply_derivations(han_snapshot_t *s) {
    // These derived values are duplicated on the firmware side so the dashboard gets
    // useful summaries immediately, even before it does any richer analysis itself.
    s->total_current_a = s->l1_a + s->l2_a + s->l3_a;
    float voltage_sum = 0.0f;
    uint8_t voltage_count = 0;
    if (is_valid_voltage(s->l1_v)) {
        voltage_sum += s->l1_v;
        voltage_count++;
    }
    if (is_valid_voltage(s->l2_v)) {
        voltage_sum += s->l2_v;
        voltage_count++;
    }
    if (is_valid_voltage(s->l3_v)) {
        voltage_sum += s->l3_v;
        voltage_count++;
    }
    s->avg_voltage_v = voltage_count > 0 ? voltage_sum / voltage_count : 0.0f;
    s->phase_imbalance_a = fmax3(s->l1_a, s->l2_a, s->l3_a) - fmin3(s->l1_a, s->l2_a, s->l3_a);
    s->net_power_w = s->import_w - s->export_w;

    // Prefer the physically stronger P/Q model when the meter provides active and
    // reactive power. This stays stable even if one voltage channel is missing or
    // intentionally not wired, which is common in some HAN/IT setups.
    const float net_reactive_var = s->q_import_var - s->q_export_var;
    const float apparent_from_pq = sqrtf((s->net_power_w * s->net_power_w) + (net_reactive_var * net_reactive_var));

    float apparent_from_vi = 0.0f;
    if (is_valid_voltage(s->l1_v)) apparent_from_vi += s->l1_v * s->l1_a;
    if (is_valid_voltage(s->l2_v)) apparent_from_vi += s->l2_v * s->l2_a;
    if (is_valid_voltage(s->l3_v)) apparent_from_vi += s->l3_v * s->l3_a;

    s->apparent_power_va = apparent_from_pq > 1.0f ? apparent_from_pq : apparent_from_vi;
    if (s->apparent_power_va > 1.0f) {
        s->estimated_power_factor = f_abs(s->net_power_w) / s->apparent_power_va;
        if (s->estimated_power_factor > 1.0f) s->estimated_power_factor = 1.0f;
    } else {
        s->estimated_power_factor = 0.0f;
    }
}

void telemetry_apply_rolling_window(han_snapshot_t *s) {
    if (!s || !s->values_valid) {
        return;
    }

    // The rolling window smooths noisy per-frame readings and gives the dashboard a
    // stable "recent average" view without storing a large history on the device.
    rolling_entry_t e = {
        .valid = true,
        .import_w = s->import_w,
        .export_w = s->export_w,
        .net_power_w = s->net_power_w,
        .l1_a = s->l1_a,
        .l2_a = s->l2_a,
        .l3_a = s->l3_a,
        .l1_v = s->l1_v,
        .l2_v = s->l2_v,
        .l3_v = s->l3_v,
    };

    s_window[s_window_head] = e;
    s_window_head = (uint8_t)((s_window_head + 1U) % ROLLING_WINDOW_FRAMES);
    if (s_window_count < ROLLING_WINDOW_FRAMES) {
        s_window_count++;
    }

    float sum_import = 0.0f, sum_export = 0.0f, sum_net = 0.0f;
    float sum_l1a = 0.0f, sum_l2a = 0.0f, sum_l3a = 0.0f;
    float sum_l1v = 0.0f, sum_l2v = 0.0f, sum_l3v = 0.0f;
    uint8_t count = 0;

    for (uint8_t i = 0; i < s_window_count; ++i) {
        if (!s_window[i].valid) continue;
        sum_import += s_window[i].import_w;
        sum_export += s_window[i].export_w;
        sum_net += s_window[i].net_power_w;
        sum_l1a += s_window[i].l1_a;
        sum_l2a += s_window[i].l2_a;
        sum_l3a += s_window[i].l3_a;
        sum_l1v += s_window[i].l1_v;
        sum_l2v += s_window[i].l2_v;
        sum_l3v += s_window[i].l3_v;
        count++;
    }

    if (count == 0) {
        return;
    }

    s->rolling_samples = count;
    s->rolling_import_w = sum_import / count;
    s->rolling_export_w = sum_export / count;
    s->rolling_net_power_w = sum_net / count;
    s->rolling_l1_a = sum_l1a / count;
    s->rolling_l2_a = sum_l2a / count;
    s->rolling_l3_a = sum_l3a / count;
    s->rolling_l1_v = sum_l1v / count;
    s->rolling_l2_v = sum_l2v / count;
    s->rolling_l3_v = sum_l3v / count;
}
