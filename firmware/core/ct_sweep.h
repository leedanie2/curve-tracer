/* ct_sweep.h — the blueprint §4 sweep engine.
 *
 * Depends only on ct_device.h, so it runs identically against real hardware
 * and against the simulated device in sim/.
 */
#ifndef CT_SWEEP_H
#define CT_SWEEP_H

#include <stdint.h>

#include "ct_device.h"
#include "ct_params.h"

typedef enum {
    CT_SWEEP_OK = 0,        /* ran to completion */
    CT_SWEEP_ILIMIT,        /* i_limit_ma exceeded; aborted */
    CT_SWEEP_STOPPED        /* host asked to stop */
} ct_sweep_result_t;

typedef struct {
    ct_sweep_result_t result;
    uint32_t points_emitted;    /* includes the flagged ilimit row, if any */
    uint32_t gate_steps_done;   /* gate values fully swept */
    float    trip_current_ma;   /* current that tripped the limit, else 0 */
    float    trip_vds_set_v;
    float    trip_vgs_set_v;
} ct_sweep_status_t;

/* Run a full sweep: the gate list crossed with N drain points, emitting the
 * CSV header, every row, and the terminating end record.
 *
 * Contract, from §4 and non-negotiable:
 *   - the current check happens BEFORE the point is emitted
 *   - on exceedance the sweep DAC is zeroed BEFORE anything is emitted
 *   - the offending point is still emitted, flagged "ilimit"
 *   - both loops then terminate
 *   - the sweep DAC is left at zero on every exit path
 */
void ct_sweep_run(const ct_device_t *dev, const ct_params_t *p,
                  ct_sweep_status_t *status);

#endif /* CT_SWEEP_H */
