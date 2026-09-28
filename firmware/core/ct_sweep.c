#include "ct_sweep.h"

#include <string.h>

#include "ct_csv.h"

static uint32_t read_acc(uint32_t (*fn)(void *, uint16_t), void *ctx, uint32_t n)
{
    if (fn == NULL) {
        return 0u;
    }
    return fn(ctx, (uint16_t)n);
}

void ct_sweep_run(const ct_device_t *dev, const ct_params_t *p,
                  ct_sweep_status_t *status)
{
    ct_sweep_status_t st;
    memset(&st, 0, sizeof(st));
    st.result = CT_SWEEP_OK;

    if (dev == NULL || p == NULL) {
        if (status != NULL) {
            *status = st;
        }
        return;
    }

    int16_t temp = (dev->die_temp_c10 != NULL)
                 ? dev->die_temp_c10(dev->ctx)
                 : CT_TEMP_UNAVAILABLE;

    ct_csv_write_header(dev, p, temp);

    const char *end_reason = CT_END_OK;
    uint32_t    point      = 0u;
    int         abort_all  = 0;

    /* Denominator for the drain ramp: N points spanning 0..vds_max inclusive,
     * so the last point lands exactly on vds_max. */
    const float span = (p->n > 1u) ? (float)(p->n - 1u) : 1.0f;

    for (uint32_t g = 0u; g < p->vgs_count && !abort_all; g++) {

        uint16_t gate_code = ct_volts_to_gate_code(p->vgs_list[g]);
        if (dev->set_gate_code != NULL) {
            dev->set_gate_code(dev->ctx, gate_code);
        }
        float vgs_set = ct_gate_code_to_volts(gate_code);

        for (uint32_t i = 0u; i < p->n; i++) {

            if (dev->abort_requested != NULL && dev->abort_requested(dev->ctx)) {
                end_reason = CT_END_STOPPED;
                st.result  = CT_SWEEP_STOPPED;
                abort_all  = 1;
                break;
            }

            float    want_v    = p->vds_max * ((float)i / span);
            uint16_t sweep_code = ct_volts_to_sweep_code(want_v);

            if (dev->set_sweep_code != NULL) {
                dev->set_sweep_code(dev->ctx, sweep_code);
            }
            if (dev->delay_us != NULL) {
                dev->delay_us(dev->ctx, p->settle_us);
            }

            uint32_t i_acc = read_acc(dev->read_current_acc, dev->ctx, p->oversample_n);
            uint32_t v_acc = read_acc(dev->read_voltage_acc, dev->ctx, p->oversample_n);

            float i_ma  = ct_acc_to_current_ma(i_acc, p->oversample_n);
            float v_dut = ct_acc_to_voltage_v(v_acc, p->oversample_n);

            ct_csv_row_t row;
            row.point      = point;
            row.vgs_set_v  = vgs_set;
            row.vds_set_v  = ct_sweep_code_to_volts(sweep_code);
            row.vds_meas_v = v_dut;
            row.i_meas_ma  = i_ma;
            row.i_acc      = i_acc;
            row.v_acc      = v_acc;
            row.range      = p->range;
            row.flags      = CT_FLAG_NONE;

            /* §4: the check is before the emit, and the DAC is zeroed before
             * the emit. Emitting first would leave the DUT at an over-limit
             * bias for the ~5.5 ms it takes to transmit the row. */
            if (i_ma > p->i_limit_ma) {
                if (dev->set_sweep_code != NULL) {
                    dev->set_sweep_code(dev->ctx, 0u);
                }
                row.flags = CT_FLAG_ILIMIT;
                ct_csv_write_row(dev, &row);
                point++;

                st.trip_current_ma = i_ma;
                st.trip_vds_set_v  = row.vds_set_v;
                st.trip_vgs_set_v  = vgs_set;
                st.result          = CT_SWEEP_ILIMIT;
                end_reason         = CT_END_ILIMIT;
                abort_all          = 1;
                break;
            }

            ct_csv_write_row(dev, &row);
            point++;
        }

        /* Return the drain to zero between gate steps regardless of how the
         * inner loop ended. */
        if (dev->set_sweep_code != NULL) {
            dev->set_sweep_code(dev->ctx, 0u);
        }
        if (!abort_all) {
            st.gate_steps_done++;
        }
    }

    /* Leave the part unbiased: drain already zeroed above, now the gate. */
    if (dev->set_gate_code != NULL) {
        dev->set_gate_code(dev->ctx, 0u);
    }

    st.points_emitted = point;
    ct_csv_write_end(dev, end_reason);

    if (status != NULL) {
        *status = st;
    }
}
