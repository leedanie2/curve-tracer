#include "ct_hold.h"

#include <string.h>

#include "ct_csv.h"

static uint32_t read_acc(uint32_t (*fn)(void *, uint16_t), void *ctx, uint32_t n)
{
    if (fn == NULL) {
        return 0u;
    }
    return fn(ctx, (uint16_t)n);
}

static int should_stop(const ct_device_t *dev)
{
    if (dev->abort_requested != NULL && dev->abort_requested(dev->ctx)) {
        return 1;
    }
    if (dev->input_pending != NULL && dev->input_pending(dev->ctx)) {
        return 1;
    }
    return 0;
}

const char *ct_hold_check(const ct_params_t *p, float vds)
{
    if (!(vds >= CT_HOLD_VDS_MIN && vds <= CT_HOLD_VDS_MAX)) {
        return "HOLD voltage out of range (0..10.96)";
    }
    if (p->vgs_count != 1u) {
        return "HOLD needs vgs_list with exactly one entry; SET vgs_list <v>";
    }
    return NULL;
}

void ct_hold_run(const ct_device_t *dev, const ct_params_t *p, float vds,
                 ct_hold_status_t *status)
{
    ct_hold_status_t st;
    memset(&st, 0, sizeof(st));
    st.result = CT_HOLD_STOPPED;

    if (dev == NULL || p == NULL) {
        if (status != NULL) {
            *status = st;
        }
        return;
    }

    uint16_t gate_code  = ct_volts_to_gate_code(p->vgs_list[0]);
    uint16_t sweep_code = ct_volts_to_sweep_code(vds);
    float    vgs_set    = ct_gate_code_to_volts(gate_code);
    st.vds_set_v        = ct_sweep_code_to_volts(sweep_code);

    int16_t temp = (dev->die_temp_c10 != NULL)
                 ? dev->die_temp_c10(dev->ctx)
                 : CT_TEMP_UNAVAILABLE;
    ct_csv_write_header_mode(dev, p, temp, "hold", st.vds_set_v);

    if (dev->set_gate_code != NULL) {
        dev->set_gate_code(dev->ctx, gate_code);
    }
    if (dev->set_sweep_code != NULL) {
        dev->set_sweep_code(dev->ctx, sweep_code);
    }

    const char *end_reason = CT_END_STOPPED;
    uint32_t    last_report = 0u;
    int         reported    = 0;

    /* Measure first, then look for input: HOLD always reports at least one
     * row, even when the next command is already queued. */
    for (;;) {
        if (dev->delay_us != NULL) {
            dev->delay_us(dev->ctx, p->settle_us);
        }

        uint32_t i_acc = read_acc(dev->read_current_acc, dev->ctx, p->oversample_n);
        uint32_t v_acc = read_acc(dev->read_voltage_acc, dev->ctx, p->oversample_n);
        float v_dut = ct_acc_to_voltage_v(v_acc, p->oversample_n);
        float i_ma  = ct_dut_current_ma(
                          ct_acc_to_current_ma(i_acc, p->oversample_n), v_dut);
        st.measurements++;

        ct_csv_row_t row;
        row.point      = st.rows_emitted;
        row.vgs_set_v  = vgs_set;
        row.vds_set_v  = st.vds_set_v;
        row.vds_meas_v = v_dut;
        row.i_meas_ma  = i_ma;
        row.i_acc      = i_acc;
        row.v_acc      = v_acc;
        row.range      = p->range;
        row.flags      = CT_FLAG_NONE;

        /* The sweep's rule: check before the emit, zero before the emit. */
        if (i_ma > p->i_limit_ma) {
            if (dev->set_sweep_code != NULL) {
                dev->set_sweep_code(dev->ctx, 0u);
            }
            row.flags = CT_FLAG_ILIMIT;
            ct_csv_write_row(dev, &row);
            st.rows_emitted++;
            st.trip_current_ma = i_ma;
            st.result          = CT_HOLD_ILIMIT;
            end_reason         = CT_END_ILIMIT;
            break;
        }

        uint32_t now = (dev->now_ms != NULL) ? dev->now_ms(dev->ctx) : 0u;
        if (!reported || dev->now_ms == NULL ||
            (uint32_t)(now - last_report) >= CT_HOLD_REPORT_MS) {
            ct_csv_write_row(dev, &row);
            st.rows_emitted++;
            last_report = reported ? last_report + CT_HOLD_REPORT_MS : now;
            if ((uint32_t)(now - last_report) >= CT_HOLD_REPORT_MS) {
                last_report = now;      /* fell behind: resync, do not burst */
            }
            reported = 1;
        }

        if (should_stop(dev)) {
            break;
        }
    }

    /* Leave the part unbiased on every exit path. */
    if (dev->set_sweep_code != NULL) {
        dev->set_sweep_code(dev->ctx, 0u);
    }
    if (dev->set_gate_code != NULL) {
        dev->set_gate_code(dev->ctx, 0u);
    }
    ct_csv_write_end(dev, end_reason);

    if (status != NULL) {
        *status = st;
    }
}
