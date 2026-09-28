#include "ct_sim_device.h"

#include <math.h>
#include <string.h>

#include "ct_config.h"
#include "ct_params.h"

#define VT_300K  0.02585f       /* kT/q at 300 K */

void ct_sim_init(ct_sim_t *s, ct_sim_kind_t kind)
{
    memset(s, 0, sizeof(*s));
    s->kind = kind;

    /* 2N7000-ish. Not a datasheet extraction — a plausible device to test
     * the engine against. */
    s->vth     = 2.1f;
    s->k       = 0.05f;
    s->lambda  = 0.01f;
    s->n_sub   = 1.5f;

    /* 1N4148-ish. */
    s->is      = 2.5e-9f;
    s->n_diode = 1.75f;
    s->rs      = 0.6f;

    s->r_load  = 200.0f;

    s->r_iso     = 22.0f;       /* blueprint §3.1 */
    s->shunt_ohm = CT_SHUNT_OHM;

    s->noise_counts = 0.0f;     /* deterministic by default */
    s->rng = 0x12345678u;
}

void ct_sim_set_output(ct_sim_t *s, char *buf, uint32_t cap)
{
    s->out = buf;
    s->out_cap = cap;
    s->out_len = 0u;
    s->out_truncated = 0u;
    if (buf != NULL && cap > 0u) {
        buf[0] = '\0';
    }
}

float ct_sim_dut_current_a(const ct_sim_t *s, float vgs, float vds)
{
    if (vds <= 0.0f) {
        return 0.0f;
    }

    switch (s->kind) {
    case CT_SIM_RESISTOR:
        return vds / s->r_load;

    case CT_SIM_DIODE:
        /* Exponential, clamped before expf overflows. */
        if (vds > 2.0f) {
            vds = 2.0f;
        }
        return s->is * (expf(vds / (s->n_diode * VT_300K)) - 1.0f);

    case CT_SIM_MOSFET:
    default: {
        float vov = vgs - s->vth;

        if (vov <= 0.0f) {
            /* Subthreshold: exponential in V_GS, saturating in V_DS. This is
             * far below range 1's floor, but it keeps the model continuous
             * and is what current range 3 would eventually measure. */
            float i = s->k * VT_300K * VT_300K
                    * expf(vov / (s->n_sub * VT_300K))
                    * (1.0f - expf(-vds / VT_300K));
            return i;
        }
        if (vds < vov) {
            /* Triode */
            return s->k * ((vov * vds) - (0.5f * vds * vds))
                 * (1.0f + s->lambda * vds);
        }
        /* Saturation */
        return 0.5f * s->k * vov * vov * (1.0f + s->lambda * vds);
    }
    }
}

/* Solve for the operating point. The commanded voltage appears at the
 * amplifier's feedback node; R_iso and the shunt sit between it and the DUT,
 * so V_dut = V_node - I*(R_iso + R_shunt) and I depends on V_dut. Bisection:
 * the I-V curves here are monotonic in V_dut, and 60 iterations is ample. */
static void solve_operating_point(const ct_sim_t *s, float v_node, float vgs,
                                  float *v_dut_out, float *i_a_out)
{
    const float r_series = s->r_iso + s->shunt_ohm;

    if (v_node <= 0.0f) {
        *v_dut_out = 0.0f;
        *i_a_out = 0.0f;
        return;
    }

    float lo = 0.0f, hi = v_node;
    for (int it = 0; it < 60; it++) {
        float mid = 0.5f * (lo + hi);
        float i   = ct_sim_dut_current_a(s, vgs, mid);
        float residual = mid + (i * r_series) - v_node;
        if (residual > 0.0f) {
            hi = mid;
        } else {
            lo = mid;
        }
    }
    float v_dut = 0.5f * (lo + hi);
    *v_dut_out = v_dut;
    *i_a_out = ct_sim_dut_current_a(s, vgs, v_dut);
}

static uint32_t rng_next(ct_sim_t *s)
{
    /* xorshift32 — deterministic, so a seeded run is reproducible. */
    uint32_t x = s->rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    s->rng = x;
    return x;
}

static float noise(ct_sim_t *s)
{
    if (s->noise_counts <= 0.0f) {
        return 0.0f;
    }
    float u = (float)(rng_next(s) & 0xFFFFu) / 65535.0f;   /* 0..1 */
    return (u - 0.5f) * 2.0f * s->noise_counts;
}

static uint32_t counts_to_acc(ct_sim_t *s, float counts, uint16_t n)
{
    uint32_t acc = 0u;
    for (uint16_t i = 0u; i < n; i++) {
        float c = counts + noise(s);
        if (c < 0.0f) {
            c = 0.0f;
        }
        if (c > (float)CT_ADC_FULL_SCALE) {
            c = (float)CT_ADC_FULL_SCALE;
        }
        acc += (uint32_t)(c + 0.5f);
    }
    return acc;
}

/* --- ct_device_t implementation ----------------------------------------- */

static void sim_set_gate(void *ctx, uint16_t code)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    s->gate_code = code;
    s->gate_writes++;
}

static void sim_set_sweep(void *ctx, uint16_t code)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    s->sweep_code = code;
    s->last_sweep_code = code;
    s->sweep_writes++;
}

static void sim_operating_point(ct_sim_t *s, float *v_dut, float *i_a)
{
    float v_node = ct_sweep_code_to_volts(s->sweep_code);
    float vgs    = ct_gate_code_to_volts(s->gate_code);
    solve_operating_point(s, v_node, vgs, v_dut, i_a);
}

static uint32_t sim_read_current(void *ctx, uint16_t n)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    float v_dut, i_a;
    sim_operating_point(s, &v_dut, &i_a);

    /* Shunt burden through the difference amp, back to ADC counts. */
    float v_adc  = i_a * s->shunt_ohm * CT_DIFFAMP_GAIN;
    float counts = (v_adc / CT_VREF) * (float)CT_ADC_FULL_SCALE;
    return counts_to_acc(s, counts, n);
}

static uint32_t sim_read_voltage(void *ctx, uint16_t n)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    float v_dut, i_a;
    sim_operating_point(s, &v_dut, &i_a);

    float v_adc  = v_dut / CT_VDIV;
    float counts = (v_adc / CT_VREF) * (float)CT_ADC_FULL_SCALE;
    return counts_to_acc(s, counts, n);
}

static void sim_delay(void *ctx, uint32_t us)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    s->delay_calls++;
    s->last_delay_us = us;
    /* No actual delay: the model has no dynamics to wait for. */
}

static void sim_emit(void *ctx, const char *str, size_t len)
{
    ct_sim_t *s = (ct_sim_t *)ctx;

    if (s->out == NULL || s->out_cap == 0u) {
        return;
    }
    for (size_t i = 0u; i < len; i++) {
        if (s->out_len + 1u >= s->out_cap) {
            s->out_truncated = 1u;
            break;
        }
        s->out[s->out_len++] = str[i];
    }
    s->out[s->out_len] = '\0';
}

static int16_t sim_temp(void *ctx)
{
    (void)ctx;
    return 254;     /* 25.4 C, fixed, so test output is stable */
}

static int sim_abort(void *ctx)
{
    ct_sim_t *s = (ct_sim_t *)ctx;
    return s->abort_flag;
}

ct_device_t ct_sim_device(ct_sim_t *s)
{
    ct_device_t d;
    d.set_gate_code    = sim_set_gate;
    d.set_sweep_code   = sim_set_sweep;
    d.read_current_acc = sim_read_current;
    d.read_voltage_acc = sim_read_voltage;
    d.delay_us         = sim_delay;
    d.emit             = sim_emit;
    d.die_temp_c10     = sim_temp;
    d.abort_requested  = sim_abort;
    d.ctx              = s;
    return d;
}
