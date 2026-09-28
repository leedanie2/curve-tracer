/* stm32f3xx_it.c — interrupt handlers. */

#include "main.h"

#include "ct_hal_device.h"

extern UART_HandleTypeDef huart2;

void ct_hal_tx_complete_isr(void);

void NMI_Handler(void)        { for (;;) { } }
void HardFault_Handler(void)  { for (;;) { } }
void MemManage_Handler(void)  { for (;;) { } }
void BusFault_Handler(void)   { for (;;) { } }
void UsageFault_Handler(void) { for (;;) { } }
void SVC_Handler(void)        { }
void DebugMon_Handler(void)   { }
void PendSV_Handler(void)     { }

void SysTick_Handler(void)
{
    HAL_IncTick();
}

/* Hand-written rather than going through HAL_UART_IRQHandler: the ring
 * buffer needs byte-at-a-time control in both directions, and the HAL's
 * transfer-oriented API would mean either a blocking call per row or a
 * state machine on top of one. */
void USART2_IRQHandler(void)
{
    uint32_t isr = huart2.Instance->ISR;

    if ((isr & USART_ISR_RXNE) != 0u) {
        char c = (char)(huart2.Instance->RDR & 0xFFu);
        ct_hal_rx_byte(c);

        /* A lone Ctrl-C or the literal word STOP both need to reach a
         * running sweep, which is inside ct_sweep_run and not reading the
         * command queue. Set the abort flag here so the engine's poll sees
         * it on the next point. */
        if (c == 0x03) {
            ct_hal_set_abort(1);
        }
    }

    if ((isr & USART_ISR_TC) != 0u) {
        huart2.Instance->ICR = USART_ICR_TCCF;
        ct_hal_tx_complete_isr();
    }

    /* Clear any error flags; an overrun here costs one received character,
     * which the command parser will report as a malformed line. */
    if ((isr & (USART_ISR_ORE | USART_ISR_NE | USART_ISR_FE | USART_ISR_PE)) != 0u) {
        huart2.Instance->ICR = USART_ICR_ORECF | USART_ICR_NCF |
                               USART_ICR_FECF  | USART_ICR_PECF;
    }
}
