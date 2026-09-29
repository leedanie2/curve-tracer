/* ct_sim_device.h — a modelled DUT behind the ct_device_t interface.
 *
 * Models the whole signal chain, not just the device: the commanded DAC code
 * becomes a node voltage, the DUT draws current, that current drops across
 * R_iso and the shunt, and what remains is what ADC2 would Kelvin-sense. So
 * vds_set_v and vds_meas_v differ here for the same physical reason they
 * differ on the bench, and the sweep engine exercises that path.
 *
 * This is a test fixture, not a circuit simulator. It has no reactive
 * elements, no settling and no loop dynamics — sims 08-11 cover those. Its
 * job is to let the sweep engine, the CSV writer and the current limit be
 * exercised without hardware.
 */
#ifndef CT_SIM_DEVICE_H
#define CT_SIM_DEVICE_H

#include <stdint.h>

#include "ct_device.h"

/* Output sink. Set one and emitted bytes go straight out instead of into the
 * capture buffer — see ct_sim_set_sink(). */
typedef void (*ct_sim_sink_fn)(void *user, const char *data, uint32_t len);

typedef enum {
    CT_SIM_MOSFET = 0,      /* square-law, with a subthreshold tail */
    CT_SIM_DIODE,           /* exponential with series resistance */
    CT_SIM_RESISTOR         /* ohmic; the simplest way to trip the limit */
} ct_sim_kind_t;

typedef struct {
    ct_sim_kind_t kind;

    /* MOSFET (defaults are 2N7000-ish) */
    float vth;              /* threshold voltage, V */
    float k;                /* transconductance parameter, A/V^2 */
    float lambda;           /* channel-length modulation, 1/V */
    float n_sub;            /* subthreshold ideality */

    /* Diode */
    float is;               /* saturation current, A */
    float n_diode;          /* ideality factor */
    float rs;               /* series resistance, ohm */

    /* Resistor */
    float r_load;           /* ohm */

    /* Front end */
    float r_iso;            /* blueprint §3.1, 22 ohm */
    float shunt_ohm;
    float noise_counts;     /* peak uniform ADC noise, in counts */

    /* State written by the engine */
    uint16_t gate_code;
    uint16_t sweep_code;
    int      abort_flag;

    /* Instrumentation for the tests */
    uint32_t delay_calls;
    uint32_t last_delay_us;
    uint32_t sweep_writes;
    uint16_t last_sweep_code;
    uint32_t gate_writes;

    /* Output: either a capture buffer (the C tests) or a streaming sink
     * (main_sim). A sink takes precedence and bypasses the buffer entirely. */
    char    *out;
    uint32_t out_cap;
    uint32_t out_len;
    uint32_t out_truncated;

    ct_sim_sink_fn sink;
    void          *sink_user;

    /* Deterministic PRNG state for the noise term. */
    uint32_t rng;
} ct_sim_t;

/* Fill in defaults for a kind. Noise is off by default so tests are exact. */
void ct_sim_init(ct_sim_t *s, ct_sim_kind_t kind);

/* Attach an output buffer. Pass NULL to discard output. */
void ct_sim_set_output(ct_sim_t *s, char *buf, uint32_t cap);

/* Attach a streaming sink, which takes precedence over any capture buffer.
 * Emitted bytes are passed straight through as the sweep produces them, so a
 * consumer sees rows arrive rather than one block at the end, and no sweep is
 * large enough to overflow anything. Pass NULL to go back to buffering. */
void ct_sim_set_sink(ct_sim_t *s, ct_sim_sink_fn fn, void *user);

/* Build the ct_device_t vtable bound to this simulator. */
ct_device_t ct_sim_device(ct_sim_t *s);

/* Exposed for tests and for main_sim's --dump-iv mode: the DUT current in
 * amps at a given gate and drain voltage, ignoring the front end. */
float ct_sim_dut_current_a(const ct_sim_t *s, float vgs, float vds);

#endif /* CT_SIM_DEVICE_H */
