/* ct_hold.h — HOLD: one drain level, held until the host says otherwise.
 *
 * The bench needs to set a level and read it with a meter. A sweep cannot
 * do that: each point lasts settle_us (at most 1 s), and the drain returns
 * to zero at the end. HOLD sets the sweep DAC once and keeps it there.
 *
 * Contract, the sweep's §4 contract applied to one point held indefinitely:
 *   - the gate is vgs_list's single entry; a list of more than one is rejected
 *     rather than guessed at
 *   - the current is measured every settle_us, and checked against
 *     i_limit_ma on EVERY measurement, not only on the reported ones
 *   - on exceedance the sweep DAC is zeroed BEFORE anything is emitted, the
 *     offending measurement is emitted flagged "ilimit", and HOLD ends
 *   - otherwise one row is reported per CT_HOLD_REPORT_MS, the first one
 *     after the first settle_us, so a HOLD always reports at least one row
 *   - HOLD ends on STOP / Ctrl-C (abort_requested) or on any other input
 *     (input_pending), with "# end: stopped"
 *   - both DACs are left at zero on every exit path
 */
#ifndef CT_HOLD_H
#define CT_HOLD_H

#include <stdint.h>

#include "ct_device.h"
#include "ct_params.h"

typedef enum {
    CT_HOLD_STOPPED = 0,    /* ended by STOP, Ctrl-C or another command */
    CT_HOLD_ILIMIT          /* i_limit_ma exceeded; drain zeroed */
} ct_hold_result_t;

typedef struct {
    ct_hold_result_t result;
    uint32_t rows_emitted;      /* includes the flagged ilimit row, if any */
    uint32_t measurements;      /* every limit check, reported or not */
    float    vds_set_v;         /* the level the DAC code actually commands */
    float    trip_current_ma;   /* current that tripped the limit, else 0 */
} ct_hold_status_t;

/* Validate a HOLD request without touching the hardware. Returns NULL if it
 * may run, else the error text for "! err:". */
const char *ct_hold_check(const ct_params_t *p, float vds);

/* Run HOLD. The caller must have checked the request with ct_hold_check(). */
void ct_hold_run(const ct_device_t *dev, const ct_params_t *p, float vds,
                 ct_hold_status_t *status);

#endif /* CT_HOLD_H */
