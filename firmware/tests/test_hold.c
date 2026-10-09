/* test_hold.c — HOLD against the simulated device.
 *
 * HOLD is the sweep's §4 contract applied to one point held indefinitely:
 * the limit is checked on every measurement, the DAC is zeroed before the
 * flagged row is emitted, and both DACs end at zero. These tests hold it to
 * that, plus its own rules: one report per CT_HOLD_REPORT_MS, the end on any
 * input, and rejection rather than guessing when the gate is ambiguous.
 */
#include <stdlib.h>

#include "ct_cmd.h"
#include "ct_csv.h"
#include "ct_hold.h"
#include "ct_sim_device.h"
#include "ct_test.h"

static char g_buf[1u << 20];

static int count_data_rows(const char *s)
{
    int n = 0;
    const char *p = s;

    while (*p != '\0') {
        const char *eol = strstr(p, "\r\n");
        size_t len = (eol != NULL) ? (size_t)(eol - p) : strlen(p);

        if (len > 0u && p[0] != '#' && p[0] != '!' &&
            strncmp(p, "point,", 6u) != 0) {
            n++;
        }
        if (eol == NULL) {
            break;
        }
        p = eol + 2;
    }
    return n;
}

static void setup(ct_sim_t *sim, ct_device_t *dev, ct_params_t *p)
{
    ct_sim_init(sim, CT_SIM_RESISTOR);
    sim->r_load = 1000.0f;
    ct_sim_set_output(sim, g_buf, sizeof(g_buf));
    *dev = ct_sim_device(sim);
    ct_params_defaults(p);
    ct_params_set_oversample(p, 4u);
}

/* Through the command parser: the levels are the ones asked for, the block
 * is labelled, rows come once per CT_HOLD_REPORT_MS of (simulated) time, and
 * input ends it with both DACs back at zero. */
static void test_hold_holds_reports_and_stops(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    ct_params_set_vgs_list(&p, "2.5");
    ct_params_set_settle_us(&p, 100000u);       /* 100 ms per measurement */
    sim.input_after_polls = 25u;                /* ~2.5 s of hold */

    ct_cmd_ctx_t c;
    ct_cmd_init(&c, &dev, &p);
    ct_cmd_execute(&c, "HOLD 5");

    CT_CHECK(strstr(g_buf, "# mode: hold") != NULL);
    CT_CHECK(strstr(g_buf, "# hold_vds_set_v: 5.000") != NULL);
    CT_CHECK(strstr(g_buf, "# end: stopped") != NULL);
    CT_CHECK(strstr(g_buf, "!") == NULL);

    /* 25 measurements at ~100 ms: reports at ~0.1, ~1.1 and ~2.1 s. */
    CT_CHECK_MSG(count_data_rows(g_buf) == 3, "rows=%d want 3",
                 count_data_rows(g_buf));
    CT_CHECK(sim.input_polls == 25u);

    /* Every row carries the held levels, as the codes actually command them
     * (2.5 V quantises to 2.499 V on the gate DAC). */
    float vgs = ct_gate_code_to_volts(ct_volts_to_gate_code(2.5f));
    char want0[48], want2[48];
    snprintf(want0, sizeof(want0), "\r\n0,%.3f,5.000,", (double)vgs);
    snprintf(want2, sizeof(want2), "\r\n2,%.3f,5.000,", (double)vgs);
    CT_CHECK_MSG(strstr(g_buf, want0) != NULL, "no row 0 like %s", want0 + 2);
    CT_CHECK_MSG(strstr(g_buf, want2) != NULL, "no row 2 like %s", want2 + 2);
    CT_CHECK(sim.gate_writes == 2u);            /* set, then zeroed */

    CT_CHECK(sim.sweep_code == 0u);
    CT_CHECK(sim.gate_code == 0u);
}

/* HOLD always reports at least one row, even with the next command queued. */
static void test_hold_reports_once_when_input_is_already_queued(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    sim.input_after_polls = 1u;

    ct_hold_status_t st;
    ct_hold_run(&dev, &p, 5.0f, &st);

    CT_CHECK(st.result == CT_HOLD_STOPPED);
    CT_CHECK(st.measurements == 1u);
    CT_CHECK(st.rows_emitted == 1u);
    CT_CHECK(count_data_rows(g_buf) == 1);
}

/* --- the limit ---------------------------------------------------------- */

static struct {
    char        log[64];
    int         len;
    ct_device_t inner;
} g_order;

static void order_set_sweep(void *ctx, uint16_t code)
{
    (void)ctx;
    if (code == 0u && g_order.len < 60) {
        g_order.log[g_order.len++] = 'Z';
    }
    g_order.inner.set_sweep_code(g_order.inner.ctx, code);
}

static void order_emit(void *ctx, const char *s, size_t len)
{
    (void)ctx;
    if (len > 6u && strstr(s, ",ilimit") != NULL && g_order.len < 60) {
        g_order.log[g_order.len++] = 'E';
    }
    g_order.inner.emit(g_order.inner.ctx, s, len);
}

/* 5 V into 200 ohm is ~22 mA against a 5 mA ceiling: the first measurement
 * trips, and the DAC must be zeroed before the flagged row goes out. */
static void test_hold_ilimit_zeroes_before_emit(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    sim.r_load = 200.0f;
    sim.input_after_polls = 1000u;              /* never reached */
    ct_params_set_ilimit_ma(&p, 5.0f);

    g_order.inner = dev;
    g_order.len = 0;
    memset(g_order.log, 0, sizeof(g_order.log));
    ct_device_t wrapped = dev;
    wrapped.set_sweep_code = order_set_sweep;
    wrapped.emit = order_emit;

    ct_hold_status_t st;
    ct_hold_run(&wrapped, &p, 5.0f, &st);
    g_order.log[g_order.len] = '\0';

    CT_CHECK(st.result == CT_HOLD_ILIMIT);
    CT_CHECK(st.trip_current_ma > 5.0f);
    CT_CHECK(strstr(g_buf, "# end: ilimit") != NULL);
    const char *e = strchr(g_order.log, 'E');
    CT_CHECK_MSG(e != NULL && e > g_order.log && *(e - 1) == 'Z',
                 "ordering was \"%s\"; wanted Z immediately before E", g_order.log);
    CT_CHECK(sim.sweep_code == 0u);
    CT_CHECK(sim.gate_code == 0u);
}

/* The DUT fails short between two reported rows. The limit must catch it on
 * that measurement, not wait for the next report. */
static ct_sim_t   *g_fail_sim;
static uint32_t    g_fail_after;
static ct_device_t g_fail_inner;

static void failing_delay(void *ctx, uint32_t us)
{
    g_fail_inner.delay_us(ctx, us);
    if (g_fail_sim->delay_calls == g_fail_after) {
        g_fail_sim->r_load = 50.0f;             /* 5 V / 50 ohm >> 60 mA */
    }
}

static void test_hold_limit_checked_between_reports(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    ct_params_set_settle_us(&p, 100000u);
    sim.input_after_polls = 1000u;

    g_fail_sim = &sim;
    g_fail_after = 15u;                         /* mid-way between reports */
    g_fail_inner = dev;
    ct_device_t wrapped = dev;
    wrapped.delay_us = failing_delay;

    ct_hold_status_t st;
    ct_hold_run(&wrapped, &p, 5.0f, &st);

    CT_CHECK(st.result == CT_HOLD_ILIMIT);
    CT_CHECK_MSG(st.measurements == 15u, "tripped on measurement %u, want 15",
                 st.measurements);
    /* Reports at measurements 1 and 11, then the flagged row at 15. */
    CT_CHECK_MSG(st.rows_emitted == 3u, "rows=%u want 3", st.rows_emitted);
    CT_CHECK(sim.sweep_code == 0u);
}

/* --- rejection, abort, no clock ------------------------------------------ */

static void test_hold_rejects_without_touching_the_dacs(void)
{
    static const char *bad[] = {
        "HOLD", "HOLD 11", "HOLD -1", "HOLD abc", "HOLD 5 6",
    };
    for (size_t i = 0u; i < sizeof(bad) / sizeof(bad[0]); i++) {
        ct_sim_t sim; ct_device_t dev; ct_params_t p;
        setup(&sim, &dev, &p);
        ct_cmd_ctx_t c;
        ct_cmd_init(&c, &dev, &p);
        ct_cmd_execute(&c, bad[i]);
        CT_CHECK_MSG(strncmp(g_buf, "! err:", 6u) == 0, "%s: got \"%.40s\"",
                     bad[i], g_buf);
        CT_CHECK_MSG(sim.sweep_writes == 0u && sim.gate_writes == 0u,
                     "%s touched a DAC", bad[i]);
    }

    /* Two gate values: which one to hold is ambiguous, so it is refused. */
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    ct_params_set_vgs_list(&p, "2.5,3.0");
    ct_cmd_ctx_t c;
    ct_cmd_init(&c, &dev, &p);
    ct_cmd_execute(&c, "HOLD 5");
    CT_CHECK(strstr(g_buf, "! err: HOLD needs vgs_list with exactly one entry") != NULL);
    CT_CHECK(sim.sweep_writes == 0u && sim.gate_writes == 0u);
}

/* Ctrl-C (abort_requested) ends it too. */
static void test_hold_ctrl_c_stops(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    sim.abort_flag = 1;

    ct_hold_status_t st;
    ct_hold_run(&dev, &p, 5.0f, &st);

    CT_CHECK(st.result == CT_HOLD_STOPPED);
    CT_CHECK(st.measurements == 1u);
    CT_CHECK(strstr(g_buf, "# end: stopped") != NULL);
    CT_CHECK(sim.sweep_code == 0u);
}

/* A device without a clock reports every measurement rather than none. */
static void test_hold_without_clock_reports_every_measurement(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    dev.now_ms = NULL;
    sim.input_after_polls = 7u;

    ct_hold_status_t st;
    ct_hold_run(&dev, &p, 5.0f, &st);

    CT_CHECK(st.measurements == 7u);
    CT_CHECK(st.rows_emitted == 7u);
}

/* SWEEP is unchanged: it still declares mode dc. */
static void test_sweep_still_declares_dc(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p);
    ct_cmd_ctx_t c;
    ct_cmd_init(&c, &dev, &p);
    ct_params_set_n(&p, 3u);
    ct_cmd_execute(&c, "SWEEP");
    CT_CHECK(strstr(g_buf, "# mode: dc") != NULL);
    CT_CHECK(strstr(g_buf, "hold_vds_set_v") == NULL);
}

CT_MAIN_BEGIN("hold")
    CT_RUN(test_hold_holds_reports_and_stops);
    CT_RUN(test_hold_reports_once_when_input_is_already_queued);
    CT_RUN(test_hold_ilimit_zeroes_before_emit);
    CT_RUN(test_hold_limit_checked_between_reports);
    CT_RUN(test_hold_rejects_without_touching_the_dacs);
    CT_RUN(test_hold_ctrl_c_stops);
    CT_RUN(test_hold_without_clock_reports_every_measurement);
    CT_RUN(test_sweep_still_declares_dc);
CT_MAIN_END()
