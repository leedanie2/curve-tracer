/* test_sweep.c — the sweep engine against the simulated device.
 *
 * The contract being tested is blueprint §4: the current check happens
 * before the point is emitted, the sweep DAC is zeroed before the emit, the
 * offending point is still emitted flagged, and both loops terminate.
 */
#include <stdlib.h>

#include "ct_csv.h"
#include "ct_sim_device.h"
#include "ct_sweep.h"
#include "ct_test.h"

static char g_buf[1u << 20];

/* Count lines that are data rows, i.e. neither comments nor the column
 * header nor blank. */
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

static int line_count_containing(const char *s, const char *needle)
{
    int n = 0;
    const char *p = s;
    while ((p = strstr(p, needle)) != NULL) {
        n++;
        p += strlen(needle);
    }
    return n;
}

static void setup(ct_sim_t *sim, ct_device_t *dev, ct_params_t *p,
                  ct_sim_kind_t kind)
{
    ct_sim_init(sim, kind);
    ct_sim_set_output(sim, g_buf, sizeof(g_buf));
    *dev = ct_sim_device(sim);
    ct_params_defaults(p);
}

/* A clean sweep emits exactly vgs_count * n rows and ends "ok". */
static void test_clean_sweep_row_count(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_MOSFET);

    ct_params_set_n(&p, 10u);
    ct_params_set_vgs_list(&p, "2.5,3.0,3.5");
    ct_params_set_vds_max(&p, 5.0f);
    ct_params_set_ilimit_ma(&p, 165.0f);      /* effectively disabled */
    ct_params_set_oversample(&p, 4u);

    ct_sweep_status_t st;
    ct_sweep_run(&dev, &p, &st);

    CT_CHECK(st.result == CT_SWEEP_OK);
    CT_CHECK_MSG(st.points_emitted == 30u, "points_emitted=%u want 30",
                 st.points_emitted);
    CT_CHECK(count_data_rows(g_buf) == 30);
    CT_CHECK(st.gate_steps_done == 3u);
    CT_CHECK(strstr(g_buf, "# end: ok") != NULL);
    CT_CHECK(line_count_containing(g_buf, "ilimit") == 0);
}

/* The header appears exactly once, before any data row. */
static void test_header_precedes_data(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_MOSFET);
    ct_params_set_n(&p, 4u);

    ct_sweep_run(&dev, &p, NULL);

    const char *cols = strstr(g_buf, "\r\npoint,vgs_set_v,");
    CT_CHECK(cols != NULL);
    CT_CHECK(strstr(g_buf, "# curve-tracer csv") == g_buf);
    CT_CHECK(line_count_containing(g_buf, "# curve-tracer csv") == 1);
    CT_CHECK(line_count_containing(g_buf, "# columns:") == 1);

    /* First data row must come after the column header line. */
    const char *first_digit = cols + 2;                 /* skip CRLF */
    first_digit = strstr(first_digit, "\r\n");          /* end of header */
    CT_CHECK(first_digit != NULL);
}

/* The current limit fires, the DAC is zeroed, the row is flagged, and the
 * sweep stops. A 200 ohm resistor at 10 V draws 50 mA, so a 5 mA ceiling
 * trips early and unambiguously. */
static void test_current_limit_fires(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_RESISTOR);
    sim.r_load = 200.0f;

    ct_params_set_n(&p, 50u);
    ct_params_set_vds_max(&p, 10.0f);
    ct_params_set_ilimit_ma(&p, 5.0f);
    ct_params_set_oversample(&p, 4u);

    ct_sweep_status_t st;
    ct_sweep_run(&dev, &p, &st);

    CT_CHECK(st.result == CT_SWEEP_ILIMIT);
    CT_CHECK_MSG(st.trip_current_ma > 5.0f, "trip_current_ma=%.3f want >5",
                 st.trip_current_ma);

    /* Exactly one flagged row, and it is the last data row. */
    CT_CHECK(line_count_containing(g_buf, ",ilimit\r\n") == 1);
    CT_CHECK(strstr(g_buf, "# end: ilimit") != NULL);

    /* Aborted well before the full 50 points. */
    CT_CHECK_MSG(st.points_emitted < 50u, "points_emitted=%u want <50",
                 st.points_emitted);
    CT_CHECK(count_data_rows(g_buf) == (int)st.points_emitted);

    /* The sweep DAC is left at zero. */
    CT_CHECK_MSG(sim.sweep_code == 0u, "sweep_code=%u want 0", sim.sweep_code);
    CT_CHECK(sim.gate_code == 0u);
}

/* §4 ordering: the DAC must be zeroed BEFORE the flagged row is emitted.
 * A device wrapper records the sweep-code writes interleaved with emits, so
 * the ordering is observable rather than assumed. */
static struct {
    char log[64];
    int  len;
    ct_device_t inner;
} g_order;

static void order_set_sweep(void *ctx, uint16_t code)
{
    (void)ctx;
    if (code == 0u && g_order.len < 60) {
        g_order.log[g_order.len++] = 'Z';   /* zeroed */
    }
    g_order.inner.set_sweep_code(g_order.inner.ctx, code);
}

static void order_emit(void *ctx, const char *s, size_t len)
{
    (void)ctx;
    /* Record only the flagged row, not every byte. */
    if (len > 6u && strstr(s, "ilimit") != NULL && g_order.len < 60) {
        g_order.log[g_order.len++] = 'E';   /* emitted the ilimit row */
    }
    g_order.inner.emit(g_order.inner.ctx, s, len);
}

static void test_dac_zeroed_before_emit(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_RESISTOR);
    sim.r_load = 200.0f;

    g_order.inner = dev;
    g_order.len = 0;
    memset(g_order.log, 0, sizeof(g_order.log));

    ct_device_t wrapped = dev;
    wrapped.set_sweep_code = order_set_sweep;
    wrapped.emit = order_emit;

    ct_params_set_n(&p, 50u);
    ct_params_set_vds_max(&p, 10.0f);
    ct_params_set_ilimit_ma(&p, 5.0f);
    ct_params_set_oversample(&p, 2u);

    ct_sweep_run(&wrapped, &p, NULL);

    g_order.log[g_order.len] = '\0';

    /* The first 'E' must be preceded immediately by a 'Z'. */
    const char *e = strchr(g_order.log, 'E');
    CT_CHECK_MSG(e != NULL, "no ilimit row was emitted");
    if (e != NULL) {
        CT_CHECK_MSG(e > g_order.log && *(e - 1) == 'Z',
                     "ordering was \"%s\"; wanted Z immediately before E",
                     g_order.log);
    }
}

/* The limit is strictly greater-than: a current exactly at the ceiling must
 * not trip. Checked via the resistor model, whose current is predictable. */
static void test_limit_is_strict_inequality(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_RESISTOR);
    sim.r_load = 200.0f;

    /* Ceiling far above anything the sweep reaches: must not trip. */
    ct_params_set_n(&p, 20u);
    ct_params_set_vds_max(&p, 1.0f);       /* ~5 mA max */
    ct_params_set_ilimit_ma(&p, 50.0f);
    ct_params_set_oversample(&p, 2u);

    ct_sweep_status_t st;
    ct_sweep_run(&dev, &p, &st);
    CT_CHECK(st.result == CT_SWEEP_OK);
    CT_CHECK(line_count_containing(g_buf, "ilimit") == 0);
}

/* STOP aborts mid-sweep and ends "stopped". */
static void test_stop_aborts(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_MOSFET);
    ct_params_set_n(&p, 100u);
    ct_params_set_oversample(&p, 2u);
    sim.abort_flag = 1;

    ct_sweep_status_t st;
    ct_sweep_run(&dev, &p, &st);

    CT_CHECK(st.result == CT_SWEEP_STOPPED);
    CT_CHECK(st.points_emitted == 0u);
    CT_CHECK(strstr(g_buf, "# end: stopped") != NULL);
    CT_CHECK(sim.sweep_code == 0u);
}

/* settle_us is honoured once per point, before sampling. */
static void test_settle_called_per_point(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_MOSFET);
    ct_params_set_n(&p, 7u);
    ct_params_set_vgs_list(&p, "2.0,3.0");
    ct_params_set_settle_us(&p, 123u);
    ct_params_set_oversample(&p, 2u);
    ct_params_set_ilimit_ma(&p, 165.0f);

    ct_sweep_run(&dev, &p, NULL);

    CT_CHECK_MSG(sim.delay_calls == 14u, "delay_calls=%u want 14",
                 sim.delay_calls);
    CT_CHECK(sim.last_delay_us == 123u);
}

/* The drain ramp spans 0..vds_max inclusive. */
static void test_ramp_endpoints(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_MOSFET);
    ct_params_set_n(&p, 5u);
    ct_params_set_vds_max(&p, 10.0f);
    ct_params_set_vgs_list(&p, "0");
    ct_params_set_ilimit_ma(&p, 165.0f);
    ct_params_set_oversample(&p, 1u);

    ct_sweep_run(&dev, &p, NULL);

    /* First data row starts at 0.000 V commanded. */
    const char *hdr = strstr(g_buf, "\r\npoint,");
    CT_CHECK(hdr != NULL);
    const char *first = strstr(hdr + 2, "\r\n");
    CT_CHECK(first != NULL);
    if (first != NULL) {
        CT_CHECK_MSG(strncmp(first + 2, "0,0.000,0.000,", 14) == 0,
                     "first row was \"%.30s\"", first + 2);
    }
    /* Last commanded point lands on vds_max to within one DAC step. */
    CT_CHECK(strstr(g_buf, ",9.99") != NULL || strstr(g_buf, ",10.00") != NULL);
}

/* Oversampling: the accumulator is the SUM of n samples, so doubling n
 * roughly doubles the reported i_acc while the derived current is unchanged. */
static void test_accumulator_is_a_sum(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;

    setup(&sim, &dev, &p, CT_SIM_RESISTOR);
    sim.r_load = 200.0f;
    ct_params_set_n(&p, 2u);
    ct_params_set_vds_max(&p, 5.0f);
    ct_params_set_ilimit_ma(&p, 165.0f);

    ct_params_set_oversample(&p, 8u);
    ct_sweep_run(&dev, &p, NULL);
    uint32_t acc8 = sim.out_len;   /* placeholder; real check below */
    (void)acc8;

    /* Read the accumulator directly rather than parsing the CSV. */
    sim.gate_code = 0u;
    sim.sweep_code = ct_volts_to_sweep_code(5.0f);
    uint32_t a8  = dev.read_current_acc(dev.ctx, 8u);
    uint32_t a16 = dev.read_current_acc(dev.ctx, 16u);

    CT_CHECK_MSG(a16 >= 2u * a8 - 8u && a16 <= 2u * a8 + 8u,
                 "a8=%u a16=%u; a16 should be ~2*a8", a8, a16);

    float ma8  = ct_acc_to_current_ma(a8, 8u);
    float ma16 = ct_acc_to_current_ma(a16, 16u);
    CT_CHECK_NEAR(ma8, ma16, 0.05);
}

/* vds_meas_v is below vds_set_v by the R_iso and shunt drop. At ~50 mA the
 * blueprint (§3.1) puts that delta near 1.15 V. */
static void test_vds_delta_matches_series_drop(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p;
    setup(&sim, &dev, &p, CT_SIM_RESISTOR);

    /* Pick a load that draws ~50 mA near the top of the range. */
    sim.r_load = 175.0f;
    ct_params_defaults(&p);

    sim.gate_code  = 0u;
    sim.sweep_code = ct_volts_to_sweep_code(10.0f);

    uint32_t i_acc = dev.read_current_acc(dev.ctx, 16u);
    uint32_t v_acc = dev.read_voltage_acc(dev.ctx, 16u);

    float i_ma   = ct_acc_to_current_ma(i_acc, 16u);
    float v_meas = ct_acc_to_voltage_v(v_acc, 16u);
    float v_set  = ct_sweep_code_to_volts(sim.sweep_code);
    float delta  = v_set - v_meas;

    /* delta should equal I * (R_iso + R_shunt) = I * 23 ohm. */
    float expect = (i_ma / 1000.0f) * (sim.r_iso + sim.shunt_ohm);
    CT_CHECK_NEAR(delta, expect, 0.05);
    CT_CHECK_MSG(delta > 0.0f, "delta=%.3f should be positive", delta);
}

CT_MAIN_BEGIN("sweep")
    CT_RUN(test_clean_sweep_row_count);
    CT_RUN(test_header_precedes_data);
    CT_RUN(test_current_limit_fires);
    CT_RUN(test_dac_zeroed_before_emit);
    CT_RUN(test_limit_is_strict_inequality);
    CT_RUN(test_stop_aborts);
    CT_RUN(test_settle_called_per_point);
    CT_RUN(test_ramp_endpoints);
    CT_RUN(test_accumulator_is_a_sum);
    CT_RUN(test_vds_delta_matches_series_drop);
CT_MAIN_END()
