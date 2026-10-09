/* ct_csv.h — the wire format. This file and firmware/README.md are the
 * contract with the Python host; change them together or not at all.
 *
 * Framing rule, which the host parser depends on:
 *   '#' first character  -> metadata or informational
 *   '!' first character  -> error response
 *   anything else        -> a CSV row
 * That one rule lets command responses share the link with sweep output.
 *
 * Lines are terminated CRLF so a raw serial terminal stays readable.
 */
#ifndef CT_CSV_H
#define CT_CSV_H

#include <stddef.h>
#include <stdint.h>

#include "ct_device.h"
#include "ct_params.h"

#define CT_CSV_EOL          "\r\n"

/* Longest line the writers below can produce, including CRLF and NUL. The
 * vgs_list metadata line is the widest: 16 entries at 7 chars plus a key. */
#define CT_CSV_LINE_MAX     192u

/* Column order. Also emitted as a "# columns:" line so a host can validate
 * it rather than assuming. */
#define CT_CSV_COLUMNS \
    "point,vgs_set_v,vds_set_v,vds_meas_v,i_meas_ma,i_acc,v_acc,range,flags"

/* Values for the flags column. Empty means a valid measurement point.
 * ANY non-empty flags value means the row is not a valid measurement. */
#define CT_FLAG_NONE        ""
#define CT_FLAG_ILIMIT      "ilimit"

/* Reasons emitted in the trailing "# end:" line. */
#define CT_END_OK           "ok"
#define CT_END_ILIMIT       "ilimit"
#define CT_END_STOPPED      "stopped"

typedef struct {
    uint32_t point;
    float    vgs_set_v;
    float    vds_set_v;
    float    vds_meas_v;
    float    i_meas_ma;
    uint32_t i_acc;
    uint32_t v_acc;
    uint8_t  range;
    const char *flags;      /* CT_FLAG_* — never NULL */
} ct_csv_row_t;

/* Write the metadata block and the column header. */
void ct_csv_write_header(const ct_device_t *dev, const ct_params_t *p,
                         int16_t die_temp_c10);

/* The same block with an explicit mode. A HOLD block passes "hold" and the
 * commanded level, which is written as "# hold_vds_set_v:" before the column
 * header. Pass a negative hold_vds_set_v for none. */
void ct_csv_write_header_mode(const ct_device_t *dev, const ct_params_t *p,
                              int16_t die_temp_c10, const char *mode,
                              float hold_vds_set_v);

/* Write one data row. */
void ct_csv_write_row(const ct_device_t *dev, const ct_csv_row_t *row);

/* Write the terminating "# end: <reason>" line. */
void ct_csv_write_end(const ct_device_t *dev, const char *reason);

/* Helpers shared with the command interface. */
void ct_csv_write_info(const ct_device_t *dev, const char *key, const char *value);
void ct_csv_write_error(const ct_device_t *dev, const char *msg);
void ct_csv_write_line(const ct_device_t *dev, const char *line);

/* Render a row into buf without emitting it. Exposed for the tests, which
 * check formatting without needing a device. Returns the length. */
size_t ct_csv_format_row(char *buf, size_t cap, const ct_csv_row_t *row);

#endif /* CT_CSV_H */
