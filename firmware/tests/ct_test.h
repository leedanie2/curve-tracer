/* ct_test.h — minimal assert harness. No framework dependency: these tests
 * must build with nothing but a C compiler so they can run anywhere.
 */
#ifndef CT_TEST_H
#define CT_TEST_H

#include <math.h>
#include <stdio.h>
#include <string.h>

extern int ct_test_failures;
extern int ct_test_checks;

#define CT_CHECK(cond)                                                        \
    do {                                                                      \
        ct_test_checks++;                                                     \
        if (!(cond)) {                                                        \
            ct_test_failures++;                                               \
            printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);          \
        }                                                                     \
    } while (0)

#define CT_CHECK_MSG(cond, ...)                                               \
    do {                                                                      \
        ct_test_checks++;                                                     \
        if (!(cond)) {                                                        \
            ct_test_failures++;                                               \
            printf("  FAIL %s:%d: ", __FILE__, __LINE__);                     \
            printf(__VA_ARGS__);                                              \
            printf("\n");                                                     \
        }                                                                     \
    } while (0)

#define CT_CHECK_STR(actual, expected)                                        \
    do {                                                                      \
        ct_test_checks++;                                                     \
        if (strcmp((actual), (expected)) != 0) {                              \
            ct_test_failures++;                                               \
            printf("  FAIL %s:%d: got \"%s\" want \"%s\"\n",                  \
                   __FILE__, __LINE__, (actual), (expected));                 \
        }                                                                     \
    } while (0)

#define CT_CHECK_NEAR(actual, expected, tol)                                  \
    do {                                                                      \
        ct_test_checks++;                                                     \
        double a_ = (double)(actual), e_ = (double)(expected);                \
        if (!(fabs(a_ - e_) <= (double)(tol))) {                              \
            ct_test_failures++;                                               \
            printf("  FAIL %s:%d: got %.6f want %.6f +/- %.6f\n",             \
                   __FILE__, __LINE__, a_, e_, (double)(tol));                \
        }                                                                     \
    } while (0)

#define CT_RUN(fn)                                                            \
    do {                                                                      \
        printf("- %s\n", #fn);                                                \
        fn();                                                                 \
    } while (0)

#define CT_MAIN_BEGIN(suite)                                                  \
    int ct_test_failures = 0;                                                 \
    int ct_test_checks = 0;                                                   \
    int main(void) {                                                          \
        printf("== %s ==\n", suite);

#define CT_MAIN_END()                                                         \
        printf("%d checks, %d failures\n", ct_test_checks, ct_test_failures); \
        return ct_test_failures == 0 ? 0 : 1;                                 \
    }

#endif /* CT_TEST_H */
