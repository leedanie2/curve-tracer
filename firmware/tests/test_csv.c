/* test_csv.c — the wire format itself: row shape, number formatting, and the
 * framing rule the Python host depends on.
 */
#include "ct_csv.h"
#include "ct_fmt.h"
#include "ct_sim_device.h"
#include "ct_test.h"

static char g_buf[65536];

static void test_row_shape(void)
{
    char buf[CT_CSV_LINE_MAX];
    ct_csv_row_t row = {
        .point = 7u,
        .vgs_set_v = 2.5f,
        .vds_set_v = 1.25f,
        .vds_meas_v = 1.2015f,
        .i_meas_ma = 12.3456f,
        .i_acc = 31580u,
        .v_acc = 29104u,
        .range = 1u,
        .flags = CT_FLAG_NONE,
    };

    ct_csv_format_row(buf, sizeof(buf), &row);
    CT_CHECK_STR(buf, "7,2.500,1.250,1.202,12.3456,31580,29104,1,");
}

static void test_row_flagged(void)
{
    char buf[CT_CSV_LINE_MAX];
    ct_csv_row_t row = {
        .point = 87u,
        .vgs_set_v = 3.5f,
        .vds_set_v = 4.35f,
        .vds_meas_v = 4.301f,
        .i_meas_ma = 60.4127f,
        .i_acc = 77329u,
        .v_acc = 53312u,
        .range = 1u,
        .flags = CT_FLAG_ILIMIT,
    };

    ct_csv_format_row(buf, sizeof(buf), &row);
    CT_CHECK_STR(buf, "87,3.500,4.350,4.301,60.4127,77329,53312,1,ilimit");
}

/* Exactly nine fields, i.e. eight commas, in every row. */
static void test_field_count(void)
{
    char buf[CT_CSV_LINE_MAX];
    ct_csv_row_t row = {0};
    row.flags = CT_FLAG_NONE;
    row.range = 1u;

    ct_csv_format_row(buf, sizeof(buf), &row);

    int commas = 0;
    for (const char *p = buf; *p != '\0'; p++) {
        if (*p == ',') commas++;
    }
    CT_CHECK_MSG(commas == 8, "got %d commas, want 8 (9 fields)", commas);

    /* The column header must declare the same number. */
    commas = 0;
    for (const char *p = CT_CSV_COLUMNS; *p != '\0'; p++) {
        if (*p == ',') commas++;
    }
    CT_CHECK_MSG(commas == 8, "column header declares %d commas", commas);
}

/* Formatting: fixed decimals, always a '.', correct rounding, zero padding. */
static void test_float_formatting(void)
{
    char buf[64];
    size_t pos;

    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 0.0f, 3u);
    CT_CHECK_STR(buf, "0.000");

    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 1.0f, 3u);
    CT_CHECK_STR(buf, "1.000");

    /* Zero padding in the fraction: 2.05 must not render as "2.5". */
    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 2.05f, 3u);
    CT_CHECK_STR(buf, "2.050");

    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 0.0004f, 4u);
    CT_CHECK_STR(buf, "0.0004");

    /* Rounding that carries into the integer part. */
    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 9.9999f, 3u);
    CT_CHECK_STR(buf, "10.000");

    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, -1.5f, 2u);
    CT_CHECK_STR(buf, "-1.50");

    /* A negative that rounds to zero must not render as "-0.00". */
    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, -0.0001f, 2u);
    CT_CHECK_STR(buf, "0.00");

    pos = 0u; buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, 10.96f, 3u);
    CT_CHECK_STR(buf, "10.960");
}

static void test_int_formatting(void)
{
    char buf[64];
    size_t pos;

    pos = 0u; buf[0] = '\0';
    ct_fmt_u32(buf, sizeof(buf), &pos, 0u);
    CT_CHECK_STR(buf, "0");

    pos = 0u; buf[0] = '\0';
    ct_fmt_u32(buf, sizeof(buf), &pos, 262080u);
    CT_CHECK_STR(buf, "262080");

    pos = 0u; buf[0] = '\0';
    ct_fmt_u32(buf, sizeof(buf), &pos, 4294967295u);
    CT_CHECK_STR(buf, "4294967295");

    pos = 0u; buf[0] = '\0';
    ct_fmt_i32(buf, sizeof(buf), &pos, -2147483647 - 1);
    CT_CHECK_STR(buf, "-2147483648");
}

/* Truncation must fail cleanly rather than emit a half-formatted number. */
static void test_buffer_overflow_is_safe(void)
{
    char buf[4];
    size_t pos = 0u;
    buf[0] = '\0';

    size_t n = ct_fmt_f(buf, sizeof(buf), &pos, 123.456f, 3u);
    CT_CHECK_MSG(n == 0u, "expected refusal, wrote %zu", n);
    CT_CHECK_STR(buf, "");
    CT_CHECK(pos == 0u);
}

/* Framing: every non-data line starts with '#' or '!', and no data row does. */
static void test_framing_rule(void)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);
    ct_sim_set_output(&sim, g_buf, sizeof(g_buf));
    ct_device_t dev = ct_sim_device(&sim);

    ct_params_t p;
    ct_params_defaults(&p);
    ct_params_set_n(&p, 6u);
    ct_params_set_oversample(&p, 2u);
    ct_params_set_ilimit_ma(&p, 165.0f);

    ct_csv_write_header(&dev, &p, 254);

    int data_rows = 0, comments = 0;
    const char *pp = g_buf;
    while (*pp != '\0') {
        const char *eol = strstr(pp, "\r\n");
        size_t len = (eol != NULL) ? (size_t)(eol - pp) : strlen(pp);

        if (len > 0u) {
            if (pp[0] == '#') {
                comments++;
            } else {
                data_rows++;
                /* The only non-comment line in a header block is the column
                 * header itself. */
                CT_CHECK(strncmp(pp, "point,", 6u) == 0);
            }
        }
        if (eol == NULL) break;
        pp = eol + 2;
    }
    CT_CHECK_MSG(data_rows == 1, "header emitted %d non-comment lines, want 1",
                 data_rows);
    CT_CHECK(comments > 15);
}

/* Every line ends CRLF. */
static void test_line_endings(void)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);
    ct_sim_set_output(&sim, g_buf, sizeof(g_buf));
    ct_device_t dev = ct_sim_device(&sim);

    ct_csv_write_info(&dev, "k", "v");
    CT_CHECK_STR(g_buf, "# k: v\r\n");

    sim.out_len = 0u; g_buf[0] = '\0';
    ct_csv_write_error(&dev, "bad");
    CT_CHECK_STR(g_buf, "! err: bad\r\n");

    /* A bare LF must never appear without its CR. */
    sim.out_len = 0u; g_buf[0] = '\0';
    ct_csv_write_end(&dev, CT_END_OK);
    for (const char *p = g_buf; *p != '\0'; p++) {
        if (*p == '\n') {
            CT_CHECK(p > g_buf && *(p - 1) == '\r');
        }
    }
}

/* The header must carry everything §5 asks for, plus the calibration
 * constants the raw accumulators need to be re-derivable. */
static void test_header_metadata_present(void)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);
    ct_sim_set_output(&sim, g_buf, sizeof(g_buf));
    ct_device_t dev = ct_sim_device(&sim);

    ct_params_t p;
    ct_params_defaults(&p);
    ct_params_set_device(&p, "2N7000");
    ct_params_set_date(&p, "2026-09-28T14:03:11Z");

    ct_csv_write_header(&dev, &p, 314);

    CT_CHECK(strstr(g_buf, "# device: 2N7000") != NULL);
    CT_CHECK(strstr(g_buf, "# date: 2026-09-28T14:03:11Z") != NULL);
    CT_CHECK(strstr(g_buf, "# date_src: host") != NULL);
    CT_CHECK(strstr(g_buf, "# range: 1") != NULL);
    CT_CHECK(strstr(g_buf, "# mode: dc") != NULL);
    CT_CHECK(strstr(g_buf, "# temp_c: 31.4") != NULL);
    CT_CHECK(strstr(g_buf, "# temp_src: mcu_die") != NULL);
    CT_CHECK(strstr(g_buf, "# schema: 1") != NULL);
    CT_CHECK(strstr(g_buf, "# cal_gain_sweep: 3.320") != NULL);
    CT_CHECK(strstr(g_buf, "# cal_shunt_ohm: 1.000") != NULL);
    CT_CHECK(strstr(g_buf, "# cal_diffamp_gain: 20.00") != NULL);
    CT_CHECK(strstr(g_buf, "# cal_vdiv: 4.000") != NULL);
    CT_CHECK(strstr(g_buf, "# i_limit_ma: 60.00") != NULL);
}

/* An unset date says so rather than inventing one. */
static void test_unset_date_is_explicit(void)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);
    ct_sim_set_output(&sim, g_buf, sizeof(g_buf));
    ct_device_t dev = ct_sim_device(&sim);

    ct_params_t p;
    ct_params_defaults(&p);
    ct_csv_write_header(&dev, &p, CT_TEMP_UNAVAILABLE);

    CT_CHECK(strstr(g_buf, "# date: unset") != NULL);
    CT_CHECK(strstr(g_buf, "# date_src: none") != NULL);
    CT_CHECK(strstr(g_buf, "# temp_c: unset") != NULL);
    CT_CHECK(strstr(g_buf, "# temp_src: none") != NULL);
}

CT_MAIN_BEGIN("csv")
    CT_RUN(test_row_shape);
    CT_RUN(test_row_flagged);
    CT_RUN(test_field_count);
    CT_RUN(test_float_formatting);
    CT_RUN(test_int_formatting);
    CT_RUN(test_buffer_overflow_is_safe);
    CT_RUN(test_framing_rule);
    CT_RUN(test_line_endings);
    CT_RUN(test_header_metadata_present);
    CT_RUN(test_unset_date_is_explicit);
CT_MAIN_END()
