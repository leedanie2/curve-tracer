#include "ct_csv.h"

#include <string.h>

#include "ct_fmt.h"

/* Decimal places per column. vds/vgs at 3 dp resolves the 2.67 mV DAC step;
 * current at 4 dp resolves 0.1 uA, comfortably below range 1's realistic
 * ~2 uA floor (blueprint §3.3). */
#define DP_VOLTS    3u
#define DP_CURRENT  4u

static void emit(const ct_device_t *dev, const char *s, size_t len)
{
    if (dev != NULL && dev->emit != NULL && len > 0u) {
        dev->emit(dev->ctx, s, len);
    }
}

static void emit_str(const ct_device_t *dev, const char *s)
{
    emit(dev, s, strlen(s));
}

void ct_csv_write_line(const ct_device_t *dev, const char *line)
{
    emit_str(dev, line);
    emit_str(dev, CT_CSV_EOL);
}

void ct_csv_write_info(const ct_device_t *dev, const char *key, const char *value)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "# ");
    ct_fmt_s(buf, sizeof(buf), &pos, key);
    ct_fmt_s(buf, sizeof(buf), &pos, ": ");
    ct_fmt_s(buf, sizeof(buf), &pos, value);
    ct_csv_write_line(dev, buf);
}

void ct_csv_write_error(const ct_device_t *dev, const char *msg)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "! err: ");
    ct_fmt_s(buf, sizeof(buf), &pos, msg);
    ct_csv_write_line(dev, buf);
}

static void info_u32(const ct_device_t *dev, const char *key, uint32_t v)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "# ");
    ct_fmt_s(buf, sizeof(buf), &pos, key);
    ct_fmt_s(buf, sizeof(buf), &pos, ": ");
    ct_fmt_u32(buf, sizeof(buf), &pos, v);
    ct_csv_write_line(dev, buf);
}

static void info_f(const ct_device_t *dev, const char *key, float v, unsigned dp)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "# ");
    ct_fmt_s(buf, sizeof(buf), &pos, key);
    ct_fmt_s(buf, sizeof(buf), &pos, ": ");
    ct_fmt_f(buf, sizeof(buf), &pos, v, dp);
    ct_csv_write_line(dev, buf);
}

void ct_csv_write_header(const ct_device_t *dev, const ct_params_t *p,
                         int16_t die_temp_c10)
{
    ct_csv_write_header_mode(dev, p, die_temp_c10, "dc", -1.0f);
}

void ct_csv_write_header_mode(const ct_device_t *dev, const ct_params_t *p,
                              int16_t die_temp_c10, const char *mode,
                              float hold_vds_set_v)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos;

    ct_csv_write_line(dev, "# curve-tracer csv");
    info_u32(dev, "schema", (uint32_t)CT_CSV_SCHEMA);
    ct_csv_write_info(dev, "fw", CT_FW_VERSION);
    ct_csv_write_info(dev, "board", CT_BOARD);
    ct_csv_write_info(dev, "device", p->device[0] != '\0' ? p->device : "unknown");

    /* The MCU has no RTC time source on a Nucleo, so the date is whatever the
     * host set. Saying "unset" is honest; inventing one would not be. */
    if (p->date[0] != '\0') {
        ct_csv_write_info(dev, "date", p->date);
        ct_csv_write_info(dev, "date_src", "host");
    } else {
        ct_csv_write_info(dev, "date", "unset");
        ct_csv_write_info(dev, "date_src", "none");
    }

    info_u32(dev, "range", (uint32_t)p->range);
    ct_csv_write_info(dev, "mode", mode);

    /* Die temperature, explicitly labelled. This is NOT the DUT temperature
     * and NOT ambient — see firmware/README.md. */
    if (die_temp_c10 == CT_TEMP_UNAVAILABLE) {
        ct_csv_write_info(dev, "temp_c", "unset");
        ct_csv_write_info(dev, "temp_src", "none");
    } else {
        info_f(dev, "temp_c", (float)die_temp_c10 / 10.0f, 1u);
        ct_csv_write_info(dev, "temp_src", "mcu_die");
    }

    info_u32(dev, "settle_us", p->settle_us);
    info_u32(dev, "n", p->n);
    info_u32(dev, "oversample_n", p->oversample_n);
    info_f(dev, "i_limit_ma", p->i_limit_ma, 2u);
    info_f(dev, "vds_max", p->vds_max, DP_VOLTS);

    pos = 0u;
    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "# vgs_list: ");
    for (uint32_t i = 0u; i < p->vgs_count; i++) {
        if (i > 0u) {
            ct_fmt_c(buf, sizeof(buf), &pos, ',');
        }
        ct_fmt_f(buf, sizeof(buf), &pos, p->vgs_list[i], DP_VOLTS);
    }
    ct_csv_write_line(dev, buf);

    /* Calibration constants travel with the data so i_acc/v_acc can be
     * re-derived later against corrected values. */
    info_f(dev, "cal_gain_sweep",   CT_GAIN_SWEEP,   3u);
    info_f(dev, "cal_gain_gate",    CT_GAIN_GATE,    3u);
    info_f(dev, "cal_shunt_ohm",    CT_SHUNT_OHM,    3u);
    info_f(dev, "cal_diffamp_gain", CT_DIFFAMP_GAIN, 2u);
    info_f(dev, "cal_vdiv",         CT_VDIV,         3u);
    info_f(dev, "cal_rdiv_ohm",     CT_RDIV_OHM,     0u);
    info_f(dev, "cal_r_iso_ohm",    CT_R_ISO_OHM,    3u);
    if (CT_R_PTC_OHM < 0.0f) {
        ct_csv_write_info(dev, "cal_r_ptc_ohm", "unset");
    } else {
        info_f(dev, "cal_r_ptc_ohm", CT_R_PTC_OHM, 3u);
    }
    info_f(dev, "cal_vref",         CT_VREF,         3u);
    info_u32(dev, "cal_adc_full_scale", (uint32_t)CT_ADC_FULL_SCALE);
    info_u32(dev, "cal_dac_full_scale", (uint32_t)CT_DAC_FULL_SCALE);

    if (hold_vds_set_v >= 0.0f) {
        info_f(dev, "hold_vds_set_v", hold_vds_set_v, DP_VOLTS);
    }

    ct_csv_write_info(dev, "columns", CT_CSV_COLUMNS);
    ct_csv_write_line(dev, CT_CSV_COLUMNS);
}

size_t ct_csv_format_row(char *buf, size_t cap, const ct_csv_row_t *row)
{
    size_t pos = 0u;

    if (cap == 0u) {
        return 0u;
    }
    buf[0] = '\0';

    ct_fmt_u32(buf, cap, &pos, row->point);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_f(buf, cap, &pos, row->vgs_set_v, DP_VOLTS);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_f(buf, cap, &pos, row->vds_set_v, DP_VOLTS);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_f(buf, cap, &pos, row->vds_meas_v, DP_VOLTS);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_f(buf, cap, &pos, row->i_meas_ma, DP_CURRENT);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_u32(buf, cap, &pos, row->i_acc);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_u32(buf, cap, &pos, row->v_acc);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_u32(buf, cap, &pos, (uint32_t)row->range);
    ct_fmt_c(buf, cap, &pos, ',');
    ct_fmt_s(buf, cap, &pos, row->flags != NULL ? row->flags : CT_FLAG_NONE);

    return pos;
}

void ct_csv_write_row(const ct_device_t *dev, const ct_csv_row_t *row)
{
    char buf[CT_CSV_LINE_MAX];

    (void)ct_csv_format_row(buf, sizeof(buf), row);
    ct_csv_write_line(dev, buf);
}

void ct_csv_write_end(const ct_device_t *dev, const char *reason)
{
    ct_csv_write_info(dev, "end", reason);
}
