/* ct_fmt.h — locale-free, allocation-free number formatting.
 *
 * Deliberately not snprintf("%f"): newlib-nano on the STM32 build omits
 * floating-point printf by default, and pulling it in costs several KB and
 * a surprise at link time. More importantly, "%f" is locale-sensitive — a
 * host or toolchain with a comma decimal separator would silently corrupt
 * the CSV contract. These emit '.' unconditionally.
 *
 * Every function appends to buf at *pos, respects cap, NUL-terminates, and
 * returns the number of characters written (0 if it would not fit).
 */
#ifndef CT_FMT_H
#define CT_FMT_H

#include <stddef.h>
#include <stdint.h>

/* Append an unsigned decimal. */
size_t ct_fmt_u32(char *buf, size_t cap, size_t *pos, uint32_t v);

/* Append a signed decimal. */
size_t ct_fmt_i32(char *buf, size_t cap, size_t *pos, int32_t v);

/* Append a float with exactly `decimals` places (0..6), half-away-from-zero
 * rounding. Non-finite input is written as "nan". */
size_t ct_fmt_f(char *buf, size_t cap, size_t *pos, float v, unsigned decimals);

/* Append a NUL-terminated string. */
size_t ct_fmt_s(char *buf, size_t cap, size_t *pos, const char *s);

/* Append one character. */
size_t ct_fmt_c(char *buf, size_t cap, size_t *pos, char c);

/* Parse a decimal float from s. Accepts optional sign, digits, optional
 * fraction. Returns 1 on success and writes *out; 0 on malformed input or
 * trailing garbage (after skipping trailing spaces). No locale, no exponent. */
int ct_parse_f(const char *s, float *out);

/* Parse an unsigned decimal. Same contract as ct_parse_f. */
int ct_parse_u32(const char *s, uint32_t *out);

#endif /* CT_FMT_H */
