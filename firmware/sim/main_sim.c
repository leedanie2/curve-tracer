/* main_sim.c — the firmware's command loop and sweep engine, running on the
 * host against a modelled DUT. Reads commands on stdin, writes CSV to stdout.
 *
 * This is the same core/ code the STM32 build runs; only ct_device_t changes.
 * It exists so the Python host can be developed and the CSV contract tested
 * with no board attached.
 *
 *   echo "SWEEP" | ./ct_sim --dut mosfet
 *   printf 'SET n 20\nSET vgs_list 2.5,3.0\nSWEEP\n' | ./ct_sim
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ct_cmd.h"
#include "ct_csv.h"
#include "ct_params.h"
#include "ct_sim_device.h"

/* Large enough for a 16-gate x 4096-point sweep; the simulator streams to
 * stdout as it fills, so this is a staging buffer, not a transcript. */
#define OUT_CHUNK 65536u

static char g_out[OUT_CHUNK];

/* Flush the simulator's capture buffer to stdout and reset it. Called after
 * every command so long sweeps do not need an unbounded buffer. */
static void flush(ct_sim_t *sim)
{
    if (sim->out_len > 0u) {
        fwrite(sim->out, 1u, sim->out_len, stdout);
        sim->out_len = 0u;
        sim->out[0] = '\0';
    }
    if (sim->out_truncated) {
        fprintf(stderr, "ct_sim: output buffer overflowed\n");
        sim->out_truncated = 0u;
    }
    fflush(stdout);
}

static void usage(void)
{
    fprintf(stderr,
        "usage: ct_sim [--dut mosfet|diode|resistor] [--noise COUNTS]\n"
        "              [--vth V] [--k A/V^2] [--lambda 1/V]\n"
        "              [--is A] [--n-diode N] [--rs OHM] [--rload OHM]\n"
        "\n"
        "Reads commands on stdin (ID GET SET SWEEP STOP HELP), writes CSV to\n"
        "stdout. See firmware/README.md for the wire format.\n");
}

int main(int argc, char **argv)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        const char *v = (i + 1 < argc) ? argv[i + 1] : NULL;

        if (strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0) {
            usage();
            return 0;
        } else if (strcmp(a, "--dut") == 0 && v != NULL) {
            if (strcmp(v, "mosfet") == 0) {
                ct_sim_init(&sim, CT_SIM_MOSFET);
            } else if (strcmp(v, "diode") == 0) {
                ct_sim_init(&sim, CT_SIM_DIODE);
            } else if (strcmp(v, "resistor") == 0) {
                ct_sim_init(&sim, CT_SIM_RESISTOR);
            } else {
                fprintf(stderr, "ct_sim: unknown --dut '%s'\n", v);
                return 2;
            }
            i++;
        } else if (strcmp(a, "--noise") == 0 && v != NULL) {
            sim.noise_counts = strtof(v, NULL); i++;
        } else if (strcmp(a, "--vth") == 0 && v != NULL) {
            sim.vth = strtof(v, NULL); i++;
        } else if (strcmp(a, "--k") == 0 && v != NULL) {
            sim.k = strtof(v, NULL); i++;
        } else if (strcmp(a, "--lambda") == 0 && v != NULL) {
            sim.lambda = strtof(v, NULL); i++;
        } else if (strcmp(a, "--is") == 0 && v != NULL) {
            sim.is = strtof(v, NULL); i++;
        } else if (strcmp(a, "--n-diode") == 0 && v != NULL) {
            sim.n_diode = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rs") == 0 && v != NULL) {
            sim.rs = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rload") == 0 && v != NULL) {
            sim.r_load = strtof(v, NULL); i++;
        } else {
            fprintf(stderr, "ct_sim: unknown option '%s'\n", a);
            usage();
            return 2;
        }
    }

    ct_sim_set_output(&sim, g_out, sizeof(g_out));
    ct_device_t dev = ct_sim_device(&sim);

    ct_params_t params;
    ct_params_defaults(&params);

    /* Name the simulated part so an archived CSV is never mistaken for a
     * bench measurement. */
    switch (sim.kind) {
    case CT_SIM_DIODE:    ct_params_set_device(&params, "sim-diode");    break;
    case CT_SIM_RESISTOR: ct_params_set_device(&params, "sim-resistor"); break;
    default:              ct_params_set_device(&params, "sim-mosfet");   break;
    }

    ct_cmd_ctx_t cmd;
    ct_cmd_init(&cmd, &dev, &params);

    int c;
    while ((c = fgetc(stdin)) != EOF) {
        ct_cmd_feed_char(&cmd, (char)c);
        if (c == '\n') {
            flush(&sim);
        }
    }
    /* A final line with no trailing newline still runs. */
    ct_cmd_feed_char(&cmd, '\n');
    flush(&sim);

    return 0;
}
