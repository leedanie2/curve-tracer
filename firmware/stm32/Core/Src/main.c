/* main.c — curve tracer firmware, Nucleo-F303RE.
 *
 * Peripheral init plus the command loop. All measurement logic lives in
 * ../../core/, which has no STM32 dependency and is exercised by the host
 * tests in ../../tests/.
 *
 * Pin assignments are listed in ct_hal_device.h and justified in
 * firmware/README.md. Two are not obvious:
 *   - the sweep DAC is on PA6 (DAC2_OUT1), not PA5, because PA5 drives LD2
 *   - "USB CDC" is USART2 through the ST-LINK VCP; there is no USB stack
 */

#include "main.h"

#include "ct_cmd.h"
#include "ct_csv.h"
#include "ct_hal_device.h"
#include "ct_params.h"

ADC_HandleTypeDef  hadc1;
ADC_HandleTypeDef  hadc2;
DAC_HandleTypeDef  hdac1;
DAC_HandleTypeDef  hdac2;
UART_HandleTypeDef huart2;
TIM_HandleTypeDef  htim6;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DAC1_Init(void);
static void MX_DAC2_Init(void);
static void MX_ADC1_Init(void);
static void MX_ADC2_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_TIM6_Init(void);

int main(void)
{
    HAL_Init();
    SystemClock_Config();

    MX_GPIO_Init();
    MX_DAC1_Init();
    MX_DAC2_Init();
    MX_ADC1_Init();
    MX_ADC2_Init();
    MX_USART2_UART_Init();
    MX_TIM6_Init();

    HAL_TIM_Base_Start(&htim6);

    /* Calibrate before the first conversion: on F303 an uncalibrated ADC can
     * sit several LSB off, which at range 1 is tens of microamps. */
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);

    HAL_DAC_Start(&hdac1, DAC_CHANNEL_1);
    HAL_DAC_Start(&hdac2, DAC_CHANNEL_1);

    /* Both sources at zero before anything else. A DUT may already be in the
     * socket at power-up. */
    HAL_DAC_SetValue(&hdac1, DAC_CHANNEL_1, DAC_ALIGN_12B_R, 0u);
    HAL_DAC_SetValue(&hdac2, DAC_CHANNEL_1, DAC_ALIGN_12B_R, 0u);

    /* Receive interrupt on, one byte at a time. */
    __HAL_UART_ENABLE_IT(&huart2, UART_IT_RXNE);

    ct_device_t dev = ct_hal_device();

    ct_params_t params;
    ct_params_defaults(&params);

    ct_cmd_ctx_t cmd;
    ct_cmd_init(&cmd, &dev, &params);

    ct_csv_write_info(&dev, "fw", CT_FW_VERSION);
    ct_csv_write_info(&dev, "board", CT_BOARD);
    ct_csv_write_line(&dev, "# ready; type HELP");

    for (;;) {
        char c;
        while (ct_hal_rx_pop(&c)) {
            /* A STOP arriving mid-sweep is handled by the abort hook, which
             * the sweep engine polls; here it only needs clearing so the next
             * sweep is not aborted before it starts. */
            ct_hal_set_abort(0);
            ct_cmd_feed_char(&cmd, c);
        }
        ct_hal_tx_pump();
    }
}

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef       osc = {0};
    RCC_ClkInitTypeDef       clk = {0};
    RCC_PeriphCLKInitTypeDef per = {0};

    /* HSI 8 MHz / 2 = 4 MHz into the PLL, x18 = 72 MHz, the F303's maximum.
     * HSI rather than HSE because the Nucleo's 8 MHz comes from the ST-LINK
     * MCO, which is absent if the board is powered standalone. */
    osc.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState            = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState        = RCC_PLL_ON;
    osc.PLL.PLLSource       = RCC_PLLSOURCE_HSI;
    osc.PLL.PLLMUL          = RCC_PLL_MUL18;   /* 4 MHz x 18 = 72 MHz */
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        Error_Handler();
    }

    clk.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                         RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2) != HAL_OK) {
        Error_Handler();
    }

    per.PeriphClockSelection = RCC_PERIPHCLK_ADC12 | RCC_PERIPHCLK_USART2;
    per.Adc12ClockSelection  = RCC_ADC12PLLCLK_DIV1;
    per.Usart2ClockSelection = RCC_USART2CLKSOURCE_PCLK1;
    if (HAL_RCCEx_PeriphCLKConfig(&per) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOF_CLK_ENABLE();
    /* Analogue pins are configured by the ADC/DAC MSP init functions. */
}

static void MX_DAC1_Init(void)
{
    DAC_ChannelConfTypeDef cfg = {0};

    hdac1.Instance = DAC1;
    if (HAL_DAC_Init(&hdac1) != HAL_OK) {
        Error_Handler();
    }

    /* Output buffer on: the gate node is high impedance, but the buffer also
     * lets the DAC reach closer to the rails. */
    cfg.DAC_Trigger      = DAC_TRIGGER_NONE;
    cfg.DAC_OutputBuffer = DAC_OUTPUTBUFFER_ENABLE;
    if (HAL_DAC_ConfigChannel(&hdac1, &cfg, DAC_CHANNEL_1) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_DAC2_Init(void)
{
    DAC_ChannelConfTypeDef cfg = {0};

    hdac2.Instance = DAC2;
    if (HAL_DAC_Init(&hdac2) != HAL_OK) {
        Error_Handler();
    }

    cfg.DAC_Trigger      = DAC_TRIGGER_NONE;
    cfg.DAC_OutputBuffer = DAC_OUTPUTBUFFER_ENABLE;
    if (HAL_DAC_ConfigChannel(&hdac2, &cfg, DAC_CHANNEL_1) != HAL_OK) {
        Error_Handler();
    }
}

/* Longest sampling time available. Blueprint §3.5 asks for it explicitly:
 * the source impedance at the ADC pin is not negligible. At 72 MHz a
 * 601.5-cycle sample plus 12.5 cycles of conversion is ~8.5 us, so 64x
 * oversampling on two channels costs ~1.1 ms per point — the ~1 ms §3.5
 * budgets. */
#define CT_SAMPLETIME ADC_SAMPLETIME_601CYCLES_5

static void MX_ADC1_Init(void)
{
    ADC_MultiModeTypeDef   multi = {0};
    ADC_ChannelConfTypeDef cfg   = {0};

    hadc1.Instance                   = ADC1;
    hadc1.Init.ClockPrescaler        = ADC_CLOCK_ASYNC_DIV1;
    hadc1.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode          = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode    = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc1.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion       = 1;
    hadc1.Init.DMAContinuousRequests = DISABLE;
    hadc1.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    hadc1.Init.LowPowerAutoWait      = DISABLE;
    hadc1.Init.Overrun               = ADC_OVR_DATA_OVERWRITTEN;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) {
        Error_Handler();
    }

    multi.Mode = ADC_MODE_INDEPENDENT;
    if (HAL_ADCEx_MultiModeConfigChannel(&hadc1, &multi) != HAL_OK) {
        Error_Handler();
    }

    cfg.Channel      = ADC_CHANNEL_1;          /* PA0, current sense */
    cfg.Rank         = ADC_REGULAR_RANK_1;
    cfg.SingleDiff   = ADC_SINGLE_ENDED;
    cfg.SamplingTime = CT_SAMPLETIME;
    cfg.OffsetNumber = ADC_OFFSET_NONE;
    cfg.Offset       = 0;
    if (HAL_ADC_ConfigChannel(&hadc1, &cfg) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_ADC2_Init(void)
{
    ADC_ChannelConfTypeDef cfg = {0};

    hadc2.Instance                   = ADC2;
    hadc2.Init.ClockPrescaler        = ADC_CLOCK_ASYNC_DIV1;
    hadc2.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc2.Init.ScanConvMode          = ADC_SCAN_DISABLE;
    hadc2.Init.ContinuousConvMode    = DISABLE;
    hadc2.Init.DiscontinuousConvMode = DISABLE;
    hadc2.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc2.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc2.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc2.Init.NbrOfConversion       = 1;
    hadc2.Init.DMAContinuousRequests = DISABLE;
    hadc2.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    hadc2.Init.LowPowerAutoWait      = DISABLE;
    hadc2.Init.Overrun               = ADC_OVR_DATA_OVERWRITTEN;
    if (HAL_ADC_Init(&hadc2) != HAL_OK) {
        Error_Handler();
    }

    cfg.Channel      = ADC_CHANNEL_6;          /* PC0, voltage sense */
    cfg.Rank         = ADC_REGULAR_RANK_1;
    cfg.SingleDiff   = ADC_SINGLE_ENDED;
    cfg.SamplingTime = CT_SAMPLETIME;
    cfg.OffsetNumber = ADC_OFFSET_NONE;
    cfg.Offset       = 0;
    if (HAL_ADC_ConfigChannel(&hadc2, &cfg) != HAL_OK) {
        Error_Handler();
    }
}

static void MX_USART2_UART_Init(void)
{
    huart2.Instance                    = USART2;
    huart2.Init.BaudRate               = 115200;
    huart2.Init.WordLength             = UART_WORDLENGTH_8B;
    huart2.Init.StopBits               = UART_STOPBITS_1;
    huart2.Init.Parity                 = UART_PARITY_NONE;
    huart2.Init.Mode                   = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl              = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling           = UART_OVERSAMPLING_16;
    huart2.Init.OneBitSampling         = UART_ONE_BIT_SAMPLE_DISABLE;
    huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
    if (HAL_UART_Init(&huart2) != HAL_OK) {
        Error_Handler();
    }
}

/* TIM6 as a free-running 1 MHz counter for the microsecond delay. APB1 is
 * HCLK/2 = 36 MHz, and timers on APB1 see 2x that when the divider is not 1,
 * so the timer clock is 72 MHz: prescaler 71 gives 1 MHz. */
static void MX_TIM6_Init(void)
{
    htim6.Instance               = TIM6;
    htim6.Init.Prescaler         = 71;
    htim6.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim6.Init.Period            = 0xFFFF;
    htim6.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    if (HAL_TIM_Base_Init(&htim6) != HAL_OK) {
        Error_Handler();
    }
}

void Error_Handler(void)
{
    __disable_irq();
    for (;;) {
        /* Deliberately a hard stop: every call site here is a peripheral
         * that the measurement path depends on. Continuing would produce
         * numbers that look valid and are not. */
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
    (void)file;
    (void)line;
}
#endif
