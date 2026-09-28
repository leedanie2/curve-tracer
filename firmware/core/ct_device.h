/* ct_device.h — the seam between the sweep engine and the world.
 *
 * Everything below core/ depends only on this interface, never on the STM32
 * HAL. Two implementations exist:
 *
 *   stm32/Core/Src/ct_hal_device.c  real DACs, ADCs, UART
 *   sim/ct_sim_device.c             modelled DUT, CSV to a buffer
 *
 * The sweep engine cannot tell them apart, which is what makes the engine
 * testable on a host with no hardware attached.
 *
 * Accumulator convention: read_current_acc() and read_voltage_acc() return
 * the SUM of n raw 12-bit conversions, not the mean. The sum is what the CSV
 * carries (i_acc / v_acc), so a sweep archived today can be re-derived
 * against corrected calibration constants later without re-measuring. With
 * n = 64 the sum spans 0..262080, which fits a uint32_t with room to spare.
 */
#ifndef CT_DEVICE_H
#define CT_DEVICE_H

#include <stddef.h>
#include <stdint.h>

typedef struct ct_device {
    /* Write a 12-bit code to the gate/step DAC (DAC1_OUT1, PA4). */
    void (*set_gate_code)(void *ctx, uint16_t code);

    /* Write a 12-bit code to the sweep DAC (DAC2_OUT1, PA6). */
    void (*set_sweep_code)(void *ctx, uint16_t code);

    /* Sum n conversions of the current-sense channel (ADC1_IN1, PA0). */
    uint32_t (*read_current_acc)(void *ctx, uint16_t n);

    /* Sum n conversions of the voltage-sense channel (ADC2_IN6, PC0). */
    uint32_t (*read_voltage_acc)(void *ctx, uint16_t n);

    /* Busy-wait. The engine asks for settle_us between setting the sweep DAC
     * and sampling. */
    void (*delay_us)(void *ctx, uint32_t us);

    /* Emit len bytes to the serial link. Implementations must not block for
     * longer than a ring-buffer enqueue; see blueprint §4 on why. */
    void (*emit)(void *ctx, const char *s, size_t len);

    /* MCU die temperature in tenths of a degree C. NOT the DUT temperature
     * and not ambient — see firmware/README.md. Return INT16_MIN if the
     * implementation has no sensor. */
    int16_t (*die_temp_c10)(void *ctx);

    /* True if the host has asked the sweep to stop early (STOP command).
     * Polled once per point. May be NULL, meaning "never aborts". */
    int (*abort_requested)(void *ctx);

    void *ctx;
} ct_device_t;

#define CT_TEMP_UNAVAILABLE  INT16_MIN

#endif /* CT_DEVICE_H */
