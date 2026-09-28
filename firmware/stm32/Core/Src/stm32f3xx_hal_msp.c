/* stm32f3xx_hal_msp.c — clocks and GPIO for each peripheral.
 *
 * This is where the pin assignments actually take effect. Cross-check
 * against the table in firmware/README.md before flashing.
 */

#include "main.h"

void HAL_MspInit(void)
{
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

void HAL_ADC_MspInit(ADC_HandleTypeDef *hadc)
{
    GPIO_InitTypeDef gpio = {0};

    if (hadc->Instance == ADC1) {
        __HAL_RCC_ADC12_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* PA0 — ADC1_IN1, current sense (Arduino A0) */
        gpio.Pin  = GPIO_PIN_0;
        gpio.Mode = GPIO_MODE_ANALOG;
        gpio.Pull = GPIO_NOPULL;
        HAL_GPIO_Init(GPIOA, &gpio);

    } else if (hadc->Instance == ADC2) {
        __HAL_RCC_ADC12_CLK_ENABLE();
        __HAL_RCC_GPIOC_CLK_ENABLE();

        /* PC0 — ADC2_IN6, voltage sense (Arduino A5) */
        gpio.Pin  = GPIO_PIN_0;
        gpio.Mode = GPIO_MODE_ANALOG;
        gpio.Pull = GPIO_NOPULL;
        HAL_GPIO_Init(GPIOC, &gpio);
    }
}

void HAL_DAC_MspInit(DAC_HandleTypeDef *hdac)
{
    GPIO_InitTypeDef gpio = {0};

    if (hdac->Instance == DAC1) {
        __HAL_RCC_DAC1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* PA4 — DAC1_OUT1, gate / step source (Arduino A2) */
        gpio.Pin  = GPIO_PIN_4;
        gpio.Mode = GPIO_MODE_ANALOG;
        gpio.Pull = GPIO_NOPULL;
        HAL_GPIO_Init(GPIOA, &gpio);

    } else if (hdac->Instance == DAC2) {
        __HAL_RCC_DAC2_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* PA6 — DAC2_OUT1, sweep source (Arduino D12).
         * NOT PA5: that pin drives LD2, whose LED and series resistor would
         * load the DAC output. See blueprint §3.5. */
        gpio.Pin  = GPIO_PIN_6;
        gpio.Mode = GPIO_MODE_ANALOG;
        gpio.Pull = GPIO_NOPULL;
        HAL_GPIO_Init(GPIOA, &gpio);
    }
}

void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    GPIO_InitTypeDef gpio = {0};

    if (huart->Instance == USART2) {
        __HAL_RCC_USART2_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* PA2 / PA3 — USART2 TX / RX, wired to the ST-LINK VCP. */
        gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
        gpio.Mode      = GPIO_MODE_AF_PP;
        gpio.Pull      = GPIO_PULLUP;
        gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
        gpio.Alternate = GPIO_AF7_USART2;
        HAL_GPIO_Init(GPIOA, &gpio);

        HAL_NVIC_SetPriority(USART2_IRQn, 1, 0);
        HAL_NVIC_EnableIRQ(USART2_IRQn);
    }
}

void HAL_TIM_Base_MspInit(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM6) {
        __HAL_RCC_TIM6_CLK_ENABLE();
    }
}
