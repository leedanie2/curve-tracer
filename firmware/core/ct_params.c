#include "ct_params.h"

#include <string.h>

#include "ct_fmt.h"

void ct_params_defaults(ct_params_t *p)
{
    memset(p, 0, sizeof(*p));
    p->settle_us    = CT_SETTLE_US_DEFAULT;
    p->n            = CT_N_DEFAULT;
    p->oversample_n = CT_OVERSAMPLE_DEFAULT;
    p->i_limit_ma   = CT_ILIMIT_MA_DEFAULT;
    p->vds_max      = CT_VDS_MAX_DEFAULT;
    p->range        = CT_RANGE_MVP;

    /* A single gate step at 0 V. Useful on its own: it sweeps a two-terminal
     * device (diode, LED, resistor) with no gate drive at all. */
    p->vgs_list[0]  = 0.0f;
    p->vgs_count    = 1u;

    memcpy(p->device, "unknown", sizeof("unknown"));
    p->date[0] = '\0';
}

int ct_params_set_settle_us(ct_params_t *p, uint32_t v)
{
    if (v < CT_SETTLE_US_MIN || v > CT_SETTLE_US_MAX) {
        return 0;
    }
    p->settle_us = v;
    return 1;
}

int ct_params_set_n(ct_params_t *p, uint32_t v)
{
    if (v < CT_N_MIN || v > CT_N_MAX) {
        return 0;
    }
    p->n = v;
    return 1;
}

int ct_params_set_oversample(ct_params_t *p, uint32_t v)
{
    if (v < CT_OVERSAMPLE_MIN || v > CT_OVERSAMPLE_MAX) {
        return 0;
    }
    p->oversample_n = v;
    return 1;
}

int ct_params_set_ilimit_ma(ct_params_t *p, float v)
{
    if (!(v >= CT_ILIMIT_MA_MIN) || !(v <= CT_ILIMIT_MA_MAX)) {
        return 0;
    }
    p->i_limit_ma = v;
    return 1;
}

int ct_params_set_vds_max(ct_params_t *p, float v)
{
    if (!(v >= CT_VDS_MAX_MIN) || !(v <= CT_VDS_MAX_MAX)) {
        return 0;
    }
    p->vds_max = v;
    return 1;
}

static int set_string(char *dst, size_t cap, const char *s)
{
    if (s == NULL) {
        return 0;
    }
    size_t n = strlen(s);
    if (n == 0u || n >= cap) {
        return 0;
    }
    /* Whitespace and commas would break the "# key: value" and CSV framing. */
    for (size_t i = 0u; i < n; i++) {
        char c = s[i];
        if (c == ',' || c == '\r' || c == '\n' || c == '#') {
            return 0;
        }
    }
    memcpy(dst, s, n + 1u);
    return 1;
}

int ct_params_set_device(ct_params_t *p, const char *s)
{
    return set_string(p->device, CT_DEVICE_LEN, s);
}

int ct_params_set_date(ct_params_t *p, const char *s)
{
    return set_string(p->date, CT_DATE_LEN, s);
}

int ct_params_set_vgs_list(ct_params_t *p, const char *s)
{
    float    tmp[CT_VGS_LIST_MAX];
    uint32_t count = 0u;
    char     field[24];

    if (s == NULL) {
        return 0;
    }

    while (*s != '\0') {
        size_t len = 0u;
        while (*s != '\0' && *s != ',') {
            if (len + 1u >= sizeof(field)) {
                return 0;
            }
            field[len++] = *s++;
        }
        field[len] = '\0';

        if (count >= CT_VGS_LIST_MAX) {
            return 0;
        }
        if (!ct_parse_f(field, &tmp[count])) {
            return 0;
        }
        if (!(tmp[count] >= 0.0f) || !(tmp[count] <= CT_VGS_MAX)) {
            return 0;
        }
        count++;

        if (*s == ',') {
            s++;
            /* A trailing comma leaves nothing to parse: reject rather than
             * silently accepting a short list. */
            if (*s == '\0') {
                return 0;
            }
        }
    }

    if (count == 0u) {
        return 0;
    }
    for (uint32_t i = 0u; i < count; i++) {
        p->vgs_list[i] = tmp[i];
    }
    p->vgs_count = count;
    return 1;
}

/* --- Conversions -------------------------------------------------------- */

static uint16_t volts_to_code(float volts, float gain)
{
    if (!(volts > 0.0f)) {
        return 0u;
    }
    float dac_v = volts / gain;
    float code  = (dac_v / CT_VREF) * (float)CT_DAC_FULL_SCALE;

    if (code >= (float)CT_DAC_FULL_SCALE) {
        return (uint16_t)CT_DAC_FULL_SCALE;
    }
    /* Round to nearest rather than truncating: at 2.67 mV per step a
     * consistent downward bias would be a visible systematic error. */
    return (uint16_t)(code + 0.5f);
}

uint16_t ct_volts_to_sweep_code(float volts)
{
    return volts_to_code(volts, CT_GAIN_SWEEP);
}

uint16_t ct_volts_to_gate_code(float volts)
{
    return volts_to_code(volts, CT_GAIN_GATE);
}

float ct_sweep_code_to_volts(uint16_t code)
{
    return ((float)code / (float)CT_DAC_FULL_SCALE) * CT_VREF * CT_GAIN_SWEEP;
}

float ct_gate_code_to_volts(uint16_t code)
{
    return ((float)code / (float)CT_DAC_FULL_SCALE) * CT_VREF * CT_GAIN_GATE;
}

float ct_acc_to_current_ma(uint32_t acc, uint32_t n)
{
    if (n == 0u) {
        return 0.0f;
    }
    float mean_counts = (float)acc / (float)n;
    float volts = (mean_counts / (float)CT_ADC_FULL_SCALE) * CT_VREF;
    /* I = V / (diffamp gain * shunt); *1000 for mA. */
    return (volts / (CT_DIFFAMP_GAIN * CT_SHUNT_OHM)) * 1000.0f;
}

float ct_acc_to_voltage_v(uint32_t acc, uint32_t n)
{
    if (n == 0u) {
        return 0.0f;
    }
    float mean_counts = (float)acc / (float)n;
    float volts = (mean_counts / (float)CT_ADC_FULL_SCALE) * CT_VREF;
    return volts * CT_VDIV;
}
