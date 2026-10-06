/* ct_params.h — the blueprint §4 parameter table, plus the unit conversions
 * that turn DAC codes and ADC accumulators into volts and milliamps.
 *
 * duty_off_us and pulsed mode are deliberately absent: the MVP is DC only
 * (blueprint §4). The range field exists but is pinned to 1.
 */
#ifndef CT_PARAMS_H
#define CT_PARAMS_H

#include <stdint.h>

#include "ct_config.h"

typedef struct {
    uint32_t settle_us;
    uint32_t n;                 /* points per sweep */
    uint32_t oversample_n;
    float    i_limit_ma;
    float    vds_max;
    float    vgs_list[CT_VGS_LIST_MAX];
    uint32_t vgs_count;
    uint8_t  range;             /* always CT_RANGE_MVP */
    char     device[CT_DEVICE_LEN];
    char     date[CT_DATE_LEN]; /* host-supplied; empty means unset */
} ct_params_t;

void ct_params_defaults(ct_params_t *p);

/* Setters returning 1 on success, 0 if the value is out of bounds. Bounds
 * live in ct_config.h. */
int ct_params_set_settle_us(ct_params_t *p, uint32_t v);
int ct_params_set_n(ct_params_t *p, uint32_t v);
int ct_params_set_oversample(ct_params_t *p, uint32_t v);
int ct_params_set_ilimit_ma(ct_params_t *p, float v);
int ct_params_set_vds_max(ct_params_t *p, float v);
int ct_params_set_device(ct_params_t *p, const char *s);
int ct_params_set_date(ct_params_t *p, const char *s);

/* Parse a comma-separated gate list, e.g. "0,2.5,3.0". Rejects an empty
 * list, more than CT_VGS_LIST_MAX entries, and out-of-range values. */
int ct_params_set_vgs_list(ct_params_t *p, const char *s);

/* --- Unit conversions ---------------------------------------------------
 *
 * These are the whole of the instrument's calibration. Every one is a pure
 * function of the constants in ct_config.h, so the CSV's raw accumulator
 * columns can be re-derived by the host with different constants.
 */

/* Requested volts at the amplifier output -> 12-bit DAC code, clamped. */
uint16_t ct_volts_to_sweep_code(float volts);
uint16_t ct_volts_to_gate_code(float volts);

/* Inverse: the volts a code actually commands. The CSV reports this as
 * vds_set_v, not the requested value, so quantisation is visible. */
float ct_sweep_code_to_volts(uint16_t code);
float ct_gate_code_to_volts(uint16_t code);

/* Accumulated ADC counts (sum of n samples) -> physical units. */
float ct_acc_to_current_ma(uint32_t acc, uint32_t n);
float ct_acc_to_voltage_v(uint32_t acc, uint32_t n);

/* The Kelvin divider's own current at a measured V_DS, in mA. */
float ct_divider_current_ma(float v_dut);

/* DUT current from the shunt current: the shunt also carries the divider's
 * current, which is not the DUT's. Blueprint §3.4. */
float ct_dut_current_ma(float i_shunt_ma, float v_dut);

#endif /* CT_PARAMS_H */
