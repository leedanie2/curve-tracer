/* test_params.c — parameter bounds, unit conversions, and command parsing.
 *
 * Bounds matter here for a physical reason: i_limit_ma is a DUT protection
 * ceiling, so a silently-clamped or silently-ignored SET is a safety bug, not
 * a usability one. Every setter must reject rather than clamp.
 */
#include "ct_cmd.h"
#include "ct_csv.h"
#include "ct_fmt.h"
#include "ct_params.h"
#include "ct_sim_device.h"
#include "ct_test.h"

static char g_buf[65536];

static void test_defaults_match_blueprint(void)
{
    ct_params_t p;
    ct_params_defaults(&p);

    CT_CHECK(p.settle_us == 50u);
    CT_CHECK(p.n == 200u);
    CT_CHECK(p.oversample_n == 64u);
    CT_CHECK_NEAR(p.i_limit_ma, 60.0f, 1e-6);
    CT_CHECK(p.range == 1u);
    CT_CHECK(p.vgs_count == 1u);
    CT_CHECK(p.date[0] == '\0');
}

/* Out-of-range values are rejected, and the old value survives. */
static void test_setters_reject_not_clamp(void)
{
    ct_params_t p;
    ct_params_defaults(&p);

    CT_CHECK(ct_params_set_ilimit_ma(&p, 0.0f) == 0);
    CT_CHECK_NEAR(p.i_limit_ma, 60.0f, 1e-6);

    CT_CHECK(ct_params_set_ilimit_ma(&p, 1000.0f) == 0);
    CT_CHECK_NEAR(p.i_limit_ma, 60.0f, 1e-6);

    CT_CHECK(ct_params_set_ilimit_ma(&p, 5.0f) == 1);
    CT_CHECK_NEAR(p.i_limit_ma, 5.0f, 1e-6);

    CT_CHECK(ct_params_set_n(&p, 0u) == 0);
    CT_CHECK(ct_params_set_n(&p, 1u) == 0);
    CT_CHECK(ct_params_set_n(&p, 2u) == 1);
    CT_CHECK(ct_params_set_n(&p, 100000u) == 0);
    CT_CHECK(p.n == 2u);

    CT_CHECK(ct_params_set_oversample(&p, 0u) == 0);
    CT_CHECK(ct_params_set_settle_us(&p, 0u) == 0);

    /* vds_max cannot exceed what the DAC can command: 3.3 * 3.32 = 10.96 V. */
    CT_CHECK(ct_params_set_vds_max(&p, 12.0f) == 0);
    CT_CHECK(ct_params_set_vds_max(&p, 10.96f) == 1);
}

static void test_vgs_list_parsing(void)
{
    ct_params_t p;
    ct_params_defaults(&p);

    CT_CHECK(ct_params_set_vgs_list(&p, "0") == 1);
    CT_CHECK(p.vgs_count == 1u);

    CT_CHECK(ct_params_set_vgs_list(&p, "2.5,3,3.5,4") == 1);
    CT_CHECK(p.vgs_count == 4u);
    CT_CHECK_NEAR(p.vgs_list[0], 2.5f, 1e-6);
    CT_CHECK_NEAR(p.vgs_list[1], 3.0f, 1e-6);
    CT_CHECK_NEAR(p.vgs_list[3], 4.0f, 1e-6);

    /* Malformed input must not partially apply. */
    CT_CHECK(ct_params_set_vgs_list(&p, "1,,2") == 0);
    CT_CHECK(ct_params_set_vgs_list(&p, "1,2,") == 0);
    CT_CHECK(ct_params_set_vgs_list(&p, "1,abc") == 0);
    CT_CHECK(ct_params_set_vgs_list(&p, "") == 0);
    CT_CHECK(ct_params_set_vgs_list(&p, "1,99") == 0);     /* over 10.96 */
    CT_CHECK_MSG(p.vgs_count == 4u, "count=%u; a rejected list mutated state",
                 p.vgs_count);

    /* Seventeen entries exceeds CT_VGS_LIST_MAX. */
    CT_CHECK(ct_params_set_vgs_list(&p,
        "0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6") == 0);
}

static void test_conversions(void)
{
    /* Full scale: 4095 -> 3.3 V at the DAC -> 10.956 V at the output. */
    CT_CHECK_NEAR(ct_sweep_code_to_volts(4095u), 10.956f, 0.002);
    CT_CHECK_NEAR(ct_sweep_code_to_volts(0u), 0.0f, 1e-6);

    /* One LSB is 3.3/4096*3.32 = 2.675 mV (blueprint §1). */
    CT_CHECK_NEAR(ct_sweep_code_to_volts(1u), 0.002675f, 2e-5);

    /* Round-trip through the code conversion. */
    uint16_t c = ct_volts_to_sweep_code(5.0f);
    CT_CHECK_NEAR(ct_sweep_code_to_volts(c), 5.0f, 0.003);

    /* Clamping, not wrapping, above full scale. */
    CT_CHECK(ct_volts_to_sweep_code(50.0f) == 4095u);
    CT_CHECK(ct_volts_to_sweep_code(-1.0f) == 0u);

    /* Current: 1.0 V at the ADC is 50 mA (1 ohm shunt, gain 20).
     * 1.0 V is 1241 counts; times 64 samples. */
    uint32_t acc = (uint32_t)((1.0f / 3.3f) * 4095.0f * 64.0f + 0.5f);
    CT_CHECK_NEAR(ct_acc_to_current_ma(acc, 64u), 50.0f, 0.05);

    /* ADC full scale is 165 mA. */
    CT_CHECK_NEAR(ct_acc_to_current_ma(4095u * 64u, 64u), 165.0f, 0.1);

    /* Voltage: divider of 4, so full scale is 13.2 V. */
    CT_CHECK_NEAR(ct_acc_to_voltage_v(4095u * 64u, 64u), 13.2f, 0.01);
    CT_CHECK_NEAR(ct_acc_to_voltage_v(0u, 64u), 0.0f, 1e-6);

    /* Division by zero must not produce NaN. */
    CT_CHECK_NEAR(ct_acc_to_current_ma(100u, 0u), 0.0f, 1e-6);
}

static void test_number_parsing(void)
{
    float f;
    uint32_t u;

    CT_CHECK(ct_parse_f("1.5", &f) == 1);  CT_CHECK_NEAR(f, 1.5f, 1e-6);
    CT_CHECK(ct_parse_f("-2.25", &f) == 1); CT_CHECK_NEAR(f, -2.25f, 1e-6);
    CT_CHECK(ct_parse_f("60", &f) == 1);   CT_CHECK_NEAR(f, 60.0f, 1e-6);
    CT_CHECK(ct_parse_f(" 3.5 ", &f) == 1); CT_CHECK_NEAR(f, 3.5f, 1e-6);

    /* Trailing garbage is an error, not silently ignored: "10x" must not
     * become 10. */
    CT_CHECK(ct_parse_f("10x", &f) == 0);
    CT_CHECK(ct_parse_f("", &f) == 0);
    CT_CHECK(ct_parse_f("abc", &f) == 0);
    CT_CHECK(ct_parse_f(".", &f) == 0);

    CT_CHECK(ct_parse_u32("200", &u) == 1); CT_CHECK(u == 200u);
    CT_CHECK(ct_parse_u32("0", &u) == 1);   CT_CHECK(u == 0u);
    CT_CHECK(ct_parse_u32("-5", &u) == 0);
    CT_CHECK(ct_parse_u32("99999999999999", &u) == 0);   /* overflow */
}

/* --- Command interface -------------------------------------------------- */

static void cmd_setup(ct_sim_t *sim, ct_device_t *dev, ct_params_t *p,
                      ct_cmd_ctx_t *cmd)
{
    ct_sim_init(sim, CT_SIM_MOSFET);
    ct_sim_set_output(sim, g_buf, sizeof(g_buf));
    *dev = ct_sim_device(sim);
    ct_params_defaults(p);
    ct_cmd_init(cmd, dev, p);
}

static void clear(ct_sim_t *sim)
{
    sim->out_len = 0u;
    g_buf[0] = '\0';
}

static void test_command_set_and_get(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p; ct_cmd_ctx_t cmd;
    cmd_setup(&sim, &dev, &p, &cmd);

    ct_cmd_execute(&cmd, "SET n 50");
    CT_CHECK(p.n == 50u);
    CT_CHECK(strstr(g_buf, "# ok: n=50") != NULL);

    clear(&sim);
    ct_cmd_execute(&cmd, "set I_LIMIT_MA 12.5");   /* case-insensitive */
    CT_CHECK_NEAR(p.i_limit_ma, 12.5f, 1e-6);
    CT_CHECK(strstr(g_buf, "# ok: i_limit_ma=12.50") != NULL);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET vgs_list 1,2,3");
    CT_CHECK(p.vgs_count == 3u);

    clear(&sim);
    ct_cmd_execute(&cmd, "GET");
    CT_CHECK(strstr(g_buf, "# n: 50") != NULL);
    CT_CHECK(strstr(g_buf, "# i_limit_ma: 12.50") != NULL);
    CT_CHECK(strstr(g_buf, "# vgs_list: 1.000,2.000,3.000") != NULL);
}

static void test_command_errors(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p; ct_cmd_ctx_t cmd;
    cmd_setup(&sim, &dev, &p, &cmd);

    ct_cmd_execute(&cmd, "NONSENSE");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET n");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET n 0");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);
    CT_CHECK_MSG(p.n == 200u, "n=%u; a rejected SET changed it", p.n);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET nosuchparam 1");
    CT_CHECK(strstr(g_buf, "! err: unknown parameter") != NULL);

    /* range is read-only in this build. */
    clear(&sim);
    ct_cmd_execute(&cmd, "SET range 2");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);
    CT_CHECK(p.range == 1u);
}

/* A rejected SET must never leave the parameter half-applied. */
static void test_rejected_set_leaves_state_intact(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p; ct_cmd_ctx_t cmd;
    cmd_setup(&sim, &dev, &p, &cmd);

    ct_cmd_execute(&cmd, "SET vgs_list 1,2,3,4");
    CT_CHECK(p.vgs_count == 4u);

    clear(&sim);
    ct_cmd_execute(&cmd, "SET vgs_list 5,bad,7");
    CT_CHECK(strstr(g_buf, "! err:") != NULL);
    CT_CHECK_MSG(p.vgs_count == 4u, "vgs_count=%u after a rejected set",
                 p.vgs_count);
    CT_CHECK_NEAR(p.vgs_list[0], 1.0f, 1e-6);
}

/* Line assembly: CR, LF and CRLF all terminate; blank lines are ignored. */
static void test_line_framing(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p; ct_cmd_ctx_t cmd;
    cmd_setup(&sim, &dev, &p, &cmd);

    ct_cmd_feed(&cmd, "SET n 42\r\n", 10u);
    CT_CHECK(p.n == 42u);

    ct_cmd_feed(&cmd, "SET n 43\n", 9u);
    CT_CHECK(p.n == 43u);

    ct_cmd_feed(&cmd, "SET n 44\r", 9u);
    CT_CHECK(p.n == 44u);

    /* A blank line produces no output at all. */
    clear(&sim);
    ct_cmd_feed(&cmd, "\r\n\r\n", 4u);
    CT_CHECK_MSG(sim.out_len == 0u, "blank lines emitted %u bytes", sim.out_len);
}

/* An over-long line is reported, not silently truncated into a valid
 * command. */
static void test_overlong_line_rejected(void)
{
    ct_sim_t sim; ct_device_t dev; ct_params_t p; ct_cmd_ctx_t cmd;
    cmd_setup(&sim, &dev, &p, &cmd);

    for (int i = 0; i < 400; i++) {
        ct_cmd_feed_char(&cmd, 'x');
    }
    ct_cmd_feed_char(&cmd, '\n');
    CT_CHECK(strstr(g_buf, "! err: line too long") != NULL);

    /* The parser recovers for the next line. */
    clear(&sim);
    ct_cmd_feed(&cmd, "SET n 77\n", 9u);
    CT_CHECK(p.n == 77u);
}

/* Strings that would break the framing must be rejected. */
static void test_string_field_validation(void)
{
    ct_params_t p;
    ct_params_defaults(&p);

    CT_CHECK(ct_params_set_device(&p, "2N7000") == 1);
    CT_CHECK(ct_params_set_device(&p, "a,b") == 0);
    CT_CHECK(ct_params_set_device(&p, "a#b") == 0);
    CT_CHECK(ct_params_set_device(&p, "") == 0);
    CT_CHECK_STR(p.device, "2N7000");

    char toolong[CT_DEVICE_LEN + 8];
    memset(toolong, 'x', sizeof(toolong) - 1u);
    toolong[sizeof(toolong) - 1u] = '\0';
    CT_CHECK(ct_params_set_device(&p, toolong) == 0);
}

CT_MAIN_BEGIN("params")
    CT_RUN(test_defaults_match_blueprint);
    CT_RUN(test_setters_reject_not_clamp);
    CT_RUN(test_vgs_list_parsing);
    CT_RUN(test_conversions);
    CT_RUN(test_number_parsing);
    CT_RUN(test_command_set_and_get);
    CT_RUN(test_command_errors);
    CT_RUN(test_rejected_set_leaves_state_intact);
    CT_RUN(test_line_framing);
    CT_RUN(test_overlong_line_rejected);
    CT_RUN(test_string_field_validation);
CT_MAIN_END()
