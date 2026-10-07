/* ct_config.h — calibration constants and hard limits.
 *
 * Every constant here is a property of the analogue front end described in
 * curve_tracer_blueprint.md, not of the MCU. Changing a resistor means
 * changing a number here and re-deriving; the raw accumulator sums are in the
 * CSV precisely so archived sweeps can be re-derived without re-measuring.
 */
#ifndef CT_CONFIG_H
#define CT_CONFIG_H

#include <stdint.h>

#define CT_FW_VERSION   "0.1.0"
#define CT_CSV_SCHEMA   2   /* 2: i_meas_ma is DUT current, divider subtracted */
#define CT_BOARD        "nucleo-f303re"

/* --- Analogue chain (blueprint §3.1, §3.3, §3.4) ------------------------- */

/* Non-inverting gain on both the sweep and gate sources: R_f = 23.2k,
 * R_g = 10k, so 1 + 23.2/10. Blueprint §3.1. */
#define CT_GAIN_SWEEP       3.32f
#define CT_GAIN_GATE        3.32f

/* Range 1 only in the MVP: 1 ohm shunt, discrete difference amp at gain 20.
 * I(A) = V_adc / (gain * shunt). Blueprint §3.3. */
#define CT_SHUNT_OHM        1.000f
#define CT_DIFFAMP_GAIN     20.0f

/* Kelvin sense divider, 300k/100k into a unity buffer. Blueprint §3.4. */
#define CT_VDIV             4.0f

/* Total resistance of that divider, KELVIN_HI to KELVIN_LO. It hangs on the
 * DUT side of the shunt, so the shunt carries I_DUT + V_DS / CT_RDIV_OHM and
 * the firmware subtracts the second term (2.5 uA per volt). Blueprint §3.4. */
#define CT_RDIV_OHM         400000.0f

/* Series resistance between the feedback node and the DUT, outside the loop:
 * the vds_set_v - vds_meas_v delta is I x (R_iso + shunt + R_PTC). These are
 * for the host's delta diagnostic only; no measurement uses them.
 * CT_R_PTC_OHM is per board and moves after every trip (1.6-15 ohm for the
 * nSMD010). Negative means not yet measured: measure the TP5 -> TP17 drop at
 * a known current at bring-up and set it here. Blueprint §3.1, §3.6. */
#define CT_R_ISO_OHM        22.0f
#define CT_R_PTC_OHM        (-1.0f)

/* DAC and ADC references. Both sit on the board's 3.3 V rail. */
#define CT_VREF             3.3f
#define CT_DAC_FULL_SCALE   4095u
#define CT_ADC_FULL_SCALE   4095u

/* --- Derived full-scale figures (documentation, not used in maths) -------
 * Sweep DAC full scale  : 3.3 * 3.32       = 10.96 V at the feedback node
 * DUT at 50 mA          : 9.06 - 9.73 V    (R_iso + shunt + PTC 1.6-15 ohm)
 * Current full scale    : 3.3 / (20 * 1)   = 165 mA at the ADC ceiling
 * Voltage full scale    : 3.3 * 4          = 13.2 V
 */

/* --- Parameter bounds (blueprint §4) ------------------------------------ */

#define CT_SETTLE_US_MIN        1u
#define CT_SETTLE_US_MAX        1000000u
/* 50 us, not the 20 us the sweep source alone would allow (it settles in
 * ~1.3 us). The binding constraint is the 1k x 10nF filter at the ADC1 pin
 * (tau = 10 us, blueprint §3.5): at 20 us the 64-sample mean still carries
 * 0.16% of the step from the previous point, a systematic lag rather than
 * noise; at 50 us, 0.008%. Costs 48 ms across a 1600-point family. */
#define CT_SETTLE_US_DEFAULT    50u

#define CT_N_MIN                2u
#define CT_N_MAX                4096u
#define CT_N_DEFAULT            200u

#define CT_OVERSAMPLE_MIN       1u
#define CT_OVERSAMPLE_MAX       1024u
#define CT_OVERSAMPLE_DEFAULT   64u

/* Default 60 mA: above the 50 mA full-scale spec so a legitimate sweep
 * cannot trip it, below the analogue limiter's 75.2 mA so firmware acts
 * first on anything it can catch. Blueprint §3.6, §4. */
#define CT_ILIMIT_MA_MIN        0.001f
#define CT_ILIMIT_MA_MAX        165.0f
#define CT_ILIMIT_MA_DEFAULT    60.0f

#define CT_VDS_MAX_MIN          0.1f
#define CT_VDS_MAX_MAX          10.96f
#define CT_VDS_MAX_DEFAULT      10.0f

#define CT_VGS_LIST_MAX         16u
#define CT_VGS_MAX              10.96f

/* String field sizes, including the terminator. */
#define CT_DEVICE_LEN           32u
#define CT_DATE_LEN             32u

/* Only range 1 exists in the MVP. The column is in the CSV for forward
 * compatibility; writes to it are rejected. */
#define CT_RANGE_MVP            1

#endif /* CT_CONFIG_H */
