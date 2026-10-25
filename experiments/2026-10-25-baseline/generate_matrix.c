/* Deterministic synthetic input generator, authored for this experiment.
 * SPDX-License-Identifier: MIT
 * No csrspmv implementation is copied or changed here.
 */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static uint64_t mix64(uint64_t z)
{
    z += UINT64_C(0x9e3779b97f4a7c15);
    z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
    return z ^ (z >> 31);
}

int main(int argc, char **argv)
{
    if (argc != 6) {
        fprintf(stderr, "usage: %s MATRIX EXPECTED_F32 N K SEED\n", argv[0]);
        return 2;
    }
    long n = strtol(argv[3], NULL, 10);
    long k = strtol(argv[4], NULL, 10);
    uint64_t seed = strtoull(argv[5], NULL, 0);
    if (n <= 0 || n > INT32_MAX || k <= 0 || k > n) return 2;
    FILE *f = fopen(argv[1], "w");
    FILE *expected = fopen(argv[2], "wb");
    if (!f || !expected) { perror("open"); return 1; }
    setvbuf(f, NULL, _IOFBF, 4 * 1024 * 1024);
    setvbuf(expected, NULL, _IOFBF, 1024 * 1024);
    fprintf(f, "%%%%MatrixMarket matrix coordinate real general\n");
    fprintf(f, "%% synthetic stratified-random CSR baseline; generator v1; seed=%" PRIu64 "\n", seed);
    fprintf(f, "%ld %ld %" PRId64 "\n", n, n, (int64_t)n * k);
    const char *values[] = {"0", "0.25", "0.50", "0.75", "1.00", "1.25", "1.50", "1.75"};
    for (long r = 0; r < n; ++r) {
        unsigned sum = 0;
        for (long j = 0; j < k; ++j) {
            uint64_t h = mix64(seed ^ ((uint64_t)r << 32) ^ (uint64_t)j);
            int64_t lo = (int64_t)j * n / k;
            int64_t hi = (int64_t)(j + 1) * n / k;
            int64_t col = lo + (int64_t)(h % (uint64_t)(hi - lo));
            unsigned q = (unsigned)((h >> 32) % 7) + 1;
            sum += q;
            if (fprintf(f, "%ld %" PRId64 " %s\n", r + 1, col + 1, values[q]) < 0) return 1;
        }
        float y = (float)sum * 0.25f;
        if (fwrite(&y, sizeof y, 1, expected) != 1) return 1;
    }
    if (fclose(f) || fclose(expected)) { perror("close"); return 1; }
    return 0;
}
