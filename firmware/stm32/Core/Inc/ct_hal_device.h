/* ct_hal_device.h — the real hardware behind ct_device_t.
 *
 * Pin map (every one of these is a choice made while writing this firmware,
 * not something the blueprint specified — see firmware/README.md):
 *
 *   PA4   DAC1_OUT1   gate / step source
 *   PA6   DAC2_OUT1   sweep source        (NOT PA5: that drives LD2)
 *   PA0   ADC1_IN1    current sense
 *   PC0   ADC2_IN6    voltage sense
 *   PA2   USART2_TX   ST-LINK VCP
 *   PA3   USART2_RX   ST-LINK VCP
 *   --    ADC1_IN16   internal die temperature
 */
#ifndef CT_HAL_DEVICE_H
#define CT_HAL_DEVICE_H

#include "ct_device.h"

/* Build the vtable. Call after the HAL peripherals are initialised. */
ct_device_t ct_hal_device(void);

/* Serial receive: call from the USART2 IRQ with each received byte. */
void ct_hal_rx_byte(char c);

/* Non-blocking: pull the next received byte. Returns 0 if none waiting. */
int ct_hal_rx_pop(char *out);

/* Set or clear the STOP request polled by the sweep engine. */
void ct_hal_set_abort(int on);

/* Kick the transmitter if it is idle. Called from the TX IRQ and on enqueue. */
void ct_hal_tx_pump(void);

/* Block until the transmit ring buffer has drained. Used before entering a
 * long sweep so the header is on the wire, and at shutdown. */
void ct_hal_tx_flush(void);

#endif /* CT_HAL_DEVICE_H */
