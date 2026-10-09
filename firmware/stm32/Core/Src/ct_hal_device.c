/* ct_hal_device.c — ct_device_t on real F303RE hardware. */

#include "ct_hal_device.h"

#include <string.h>

#include "main.h"

extern ADC_HandleTypeDef  hadc1;
extern ADC_HandleTypeDef  hadc2;
extern DAC_HandleTypeDef  hdac1;
extern DAC_HandleTypeDef  hdac2;
extern UART_HandleTypeDef huart2;
extern TIM_HandleTypeDef  htim6;

/* --- Transmit ring buffer ------------------------------------------------
 *
 * Blueprint §4: at 115200 a ~64-byte row takes ~5.5 ms to send against
 * ~1.1 ms of conversion, so a blocking write would hold the DUT at bias five
 * times longer than the measurement needs. Interrupt-driven TX lets the next
 * point's conversions overlap this point's transmission.
 *
 * 4 KB holds ~60 rows, comfortably more than the ADC can get ahead by.
 */
#define TX_SIZE 4096u
#define RX_SIZE 256u

static volatile uint8_t  s_tx[TX_SIZE];
static volatile uint32_t s_tx_head;     /* next write */
static volatile uint32_t s_tx_tail;     /* next read */
static volatile int      s_tx_active;

static volatile uint8_t  s_rx[RX_SIZE];
static volatile uint32_t s_rx_head;
static volatile uint32_t s_rx_tail;

static volatile int      s_abort;

void ct_hal_tx_pump(void)
{
    /* Called from both thread and IRQ context: guard the head/tail read. */
    __disable_irq();
    if (!s_tx_active && s_tx_head != s_tx_tail) {
        uint8_t byte = s_tx[s_tx_tail];
        s_tx_tail = (s_tx_tail + 1u) % TX_SIZE;
        s_tx_active = 1;
        __enable_irq();
        /* Transmit one byte; the TC interrupt pumps the next. */
        huart2.Instance->TDR = byte;
        __HAL_UART_ENABLE_IT(&huart2, UART_IT_TC);
        return;
    }
    __enable_irq();
}

void ct_hal_tx_flush(void)
{
    while (1) {
        __disable_irq();
        int busy = (s_tx_head != s_tx_tail) || s_tx_active;
        __enable_irq();
        if (!busy) {
            break;
        }
        ct_hal_tx_pump();
    }
}

/* Called from the USART2 IRQ when a byte has finished transmitting. */
void ct_hal_tx_complete_isr(void)
{
    if (s_tx_head != s_tx_tail) {
        uint8_t byte = s_tx[s_tx_tail];
        s_tx_tail = (s_tx_tail + 1u) % TX_SIZE;
        huart2.Instance->TDR = byte;
    } else {
        s_tx_active = 0;
        __HAL_UART_DISABLE_IT(&huart2, UART_IT_TC);
    }
}

void ct_hal_rx_byte(char c)
{
    uint32_t next = (s_rx_head + 1u) % RX_SIZE;
    if (next != s_rx_tail) {
        s_rx[s_rx_head] = (uint8_t)c;
        s_rx_head = next;
    }
    /* On overflow the byte is dropped; the command parser reports the
     * resulting malformed line rather than silently acting on it. */
}

int ct_hal_rx_pop(char *out)
{
    if (s_rx_head == s_rx_tail) {
        return 0;
    }
    *out = (char)s_rx[s_rx_tail];
    s_rx_tail = (s_rx_tail + 1u) % RX_SIZE;
    return 1;
}

void ct_hal_set_abort(int on)
{
    s_abort = on;
}

/* --- ct_device_t implementation ----------------------------------------- */

static void hal_set_gate(void *ctx, uint16_t code)
{
    (void)ctx;
    if (code > 4095u) {
        code = 4095u;
    }
    HAL_DAC_SetValue(&hdac1, DAC_CHANNEL_1, DAC_ALIGN_12B_R, code);
}

static void hal_set_sweep(void *ctx, uint16_t code)
{
    (void)ctx;
    if (code > 4095u) {
        code = 4095u;
    }
    HAL_DAC_SetValue(&hdac2, DAC_CHANNEL_1, DAC_ALIGN_12B_R, code);
}

static uint32_t accumulate(ADC_HandleTypeDef *h, uint16_t n)
{
    uint32_t acc = 0u;

    for (uint16_t i = 0u; i < n; i++) {
        HAL_ADC_Start(h);
        if (HAL_ADC_PollForConversion(h, 10u) == HAL_OK) {
            acc += HAL_ADC_GetValue(h);
        }
        HAL_ADC_Stop(h);
        /* Keep the transmitter fed while sampling: this is the overlap the
         * ring buffer exists for. */
        ct_hal_tx_pump();
    }
    return acc;
}

static uint32_t hal_read_current(void *ctx, uint16_t n)
{
    (void)ctx;
    return accumulate(&hadc1, n);
}

static uint32_t hal_read_voltage(void *ctx, uint16_t n)
{
    (void)ctx;
    return accumulate(&hadc2, n);
}

/* Microsecond delay from TIM6, which is clocked to tick at 1 MHz. HAL_Delay
 * has 1 ms granularity, far too coarse for a 20 us settle. */
static void hal_delay_us(void *ctx, uint32_t us)
{
    (void)ctx;

    while (us > 0u) {
        uint32_t chunk = (us > 60000u) ? 60000u : us;
        __HAL_TIM_SET_COUNTER(&htim6, 0u);
        while (__HAL_TIM_GET_COUNTER(&htim6) < chunk) {
            /* Busy-wait, but keep the UART draining. */
            ct_hal_tx_pump();
        }
        us -= chunk;
    }
}

static void hal_emit(void *ctx, const char *s, size_t len)
{
    (void)ctx;

    for (size_t i = 0u; i < len; i++) {
        uint32_t next = (s_tx_head + 1u) % TX_SIZE;

        /* Ring full: pump and wait. This is the one place the sweep can
         * block on the UART, and only if the host stops reading. */
        while (next == s_tx_tail) {
            ct_hal_tx_pump();
        }
        s_tx[s_tx_head] = (uint8_t)s[i];
        s_tx_head = next;
    }
    ct_hal_tx_pump();
}

/* F303 has no factory temperature calibration, unlike the L4/G4 families.
 * The datasheet gives V25 = 1.43 V and a slope of 4.3 mV/degC, both typical
 * with wide tolerances, so this figure is indicative only — which is why the
 * CSV labels it temp_src: mcu_die and firmware/README.md warns against
 * treating it as a DUT or ambient reading. */
#define TS_V25_MV        1430.0f
#define TS_SLOPE_MV_C    4.3f

static int16_t hal_die_temp(void *ctx)
{
    (void)ctx;

    ADC_ChannelConfTypeDef cfg = {0};
    cfg.Channel      = ADC_CHANNEL_TEMPSENSOR;
    cfg.Rank         = ADC_REGULAR_RANK_1;
    cfg.SamplingTime = ADC_SAMPLETIME_601CYCLES_5;
    cfg.SingleDiff   = ADC_SINGLE_ENDED;
    cfg.OffsetNumber = ADC_OFFSET_NONE;
    cfg.Offset       = 0u;

    if (HAL_ADC_ConfigChannel(&hadc1, &cfg) != HAL_OK) {
        return CT_TEMP_UNAVAILABLE;
    }

    uint32_t acc = accumulate(&hadc1, 16u);
    float counts = (float)acc / 16.0f;
    float mv     = (counts / 4095.0f) * 3300.0f;
    float temp_c = ((TS_V25_MV - mv) / TS_SLOPE_MV_C) + 25.0f;

    /* Restore the current-sense channel: the sweep engine reads it next. */
    cfg.Channel      = ADC_CHANNEL_1;          /* PA0 */
    cfg.SamplingTime = ADC_SAMPLETIME_601CYCLES_5;
    (void)HAL_ADC_ConfigChannel(&hadc1, &cfg);

    if (temp_c < -40.0f || temp_c > 125.0f) {
        return CT_TEMP_UNAVAILABLE;
    }
    return (int16_t)(temp_c * 10.0f);
}

static int hal_abort(void *ctx)
{
    (void)ctx;
    return s_abort;
}

/* HOLD's "until STOP or another command": anything left in the receive ring.
 * Main thread only, the ring's sole consumer, so peeking at the tail is safe
 * against the ISR producer. Leading CR/LF is consumed: the host terminates
 * lines CRLF, the CR already ran the HOLD line, and the LF would otherwise
 * end the hold at once. A blank line is a no-op to the parser anyway. */
static int hal_input_pending(void *ctx)
{
    (void)ctx;
    while (s_rx_head != s_rx_tail) {
        uint8_t c = s_rx[s_rx_tail];
        if (c != (uint8_t)'\r' && c != (uint8_t)'\n') {
            return 1;
        }
        s_rx_tail = (s_rx_tail + 1u) % RX_SIZE;
    }
    return 0;
}

static uint32_t hal_now_ms(void *ctx)
{
    (void)ctx;
    return HAL_GetTick();
}

ct_device_t ct_hal_device(void)
{
    ct_device_t d;
    d.set_gate_code    = hal_set_gate;
    d.set_sweep_code   = hal_set_sweep;
    d.read_current_acc = hal_read_current;
    d.read_voltage_acc = hal_read_voltage;
    d.delay_us         = hal_delay_us;
    d.emit             = hal_emit;
    d.die_temp_c10     = hal_die_temp;
    d.abort_requested  = hal_abort;
    d.input_pending    = hal_input_pending;
    d.now_ms           = hal_now_ms;
    d.ctx              = NULL;
    return d;
}
