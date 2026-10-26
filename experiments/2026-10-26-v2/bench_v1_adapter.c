/* SPDX-License-Identifier: GPL-3.0-or-later
 * Diagnostic only: compiled against the archived v1 header with plan symbols
 * renamed. No v1 source is included in the v2 branch or production binary.
 */
#include "spmv_plan.h"
#include <assert.h>
#include <stdlib.h>
void *bench_v1_prepare(const struct csr_matrix_int32 *a,const struct vector *x,
                       const struct vector *y,int sell)
{
    struct spmv_plan *p=malloc(sizeof(*p));assert(p);
    assert(!spmv_plan_prepare(p,a,x,y,sell ? spmv_sell:spmv_csr_scalar,16,SIZE_MAX));
    return p;
}
int bench_v1_execute(void *p,const struct vector *x,struct vector *y,int64_t *f)
{return spmv_plan_execute(p,x,y,f);}
void bench_v1_free(void *p) {spmv_plan_free(p);free(p);}
const char *bench_v1_reason(void *p) {return ((struct spmv_plan *)p)->reason;}
int bench_v1_is_sell(void *p) {return ((struct spmv_plan *)p)->kernel==spmv_sell;}
