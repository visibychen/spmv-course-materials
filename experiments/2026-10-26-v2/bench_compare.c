/* SPDX-License-Identifier: GPL-3.0-or-later
 * Same-binary diagnostic, unified warmup/reset and balanced order.
 * This is deliberately separate from original CLI engineering timings.
 */
#include "spmv_plan.h"
#include "matrix_market.h"
#include <assert.h>
#include <math.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
void *bench_v1_prepare(const struct csr_matrix_int32 *,const struct vector *,const struct vector *,int);
int bench_v1_execute(void *,const struct vector *,struct vector *,int64_t *);
void bench_v1_free(void *);
const char *bench_v1_reason(void *);
int bench_v1_is_sell(void *);
static double now(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+1e-9*t.tv_nsec;}
static double execute(int variant,const struct csr_matrix_int32 *a,
                       struct spmv_plan *v2,struct spmv_plan *generic,void **v1,struct vector *x,struct vector *y,int repeat)
{
    double start=now();int err=0;
#pragma omp parallel reduction(|:err)
    {
        int64_t flops=0;
        for(int r=0;r<repeat;r++) {
            if(variant==0) err=csr_matrix_int32_spmv(a,x,y,&flops);
            else if(variant==3) err=spmv_plan_execute(v2,x,y,&flops);
            else if(variant==4) err=spmv_plan_execute(generic,x,y,&flops);
            else err=bench_v1_execute(v1[variant-1],x,y,&flops);
        }
    }
    double elapsed=now()-start;assert(!err);return elapsed;
}
int main(int argc,char **argv)
{
    assert(argc==4);int repeat=atoi(argv[2]),pairs=atoi(argv[3]);assert(repeat>0 && pairs>0);
    FILE *f=fopen(argv[1],"r");assert(f);struct matrix_market mm;int l,c;
    assert(!matrix_market_read(&mm,f,&l,&c));fclose(f);
    struct csr_matrix_int32 a;assert(!csr_matrix_int32_from_matrix_market(&a,&mm,csr_value_f32,0));matrix_market_free(&mm);
    struct vector x,y;assert(!vector_alloc(&x,a.num_columns,vector_value_f32));
    assert(!vector_alloc(&y,a.num_rows,vector_value_f32));assert(!vector_ones(&x));
    vector_zero(&y);struct spmv_plan p;struct spmv_v2_options o;spmv_v2_defaults(&o);o.execution=v2_parallel;
    double start=now();assert(!spmv_v2_prepare(&p,&a,&x,&y,&o,SIZE_MAX));double prep=now()-start;
    struct spmv_plan generic;o.kernel=v2_csr;o.partition=v2_rows;
    start=now();assert(!spmv_v2_prepare(&generic,&a,&x,&y,&o,SIZE_MAX));double gprep=now()-start;
    void *v1[2];double oldprep[2];
    for(int i=0;i<2;i++) {start=now();v1[i]=bench_v1_prepare(&a,&x,&y,i);oldprep[i]=now()-start;}
    printf("{\"type\":\"prepare\",\"v2_s\":%.9f,\"v2_csr_s\":%.9f,\"v1_scalar_s\":%.9f,\"v1_sell16_s\":%.9f,\"threads\":%d,\"sell_selected\":%d,\"sell_reason\":\"%s\"}\n",prep,gprep,oldprep[0],oldprep[1],omp_get_max_threads(),bench_v1_is_sell(v1[1]),bench_v1_reason(v1[1]));
    /* One warmup per backend. Preparation and warmup are never free in CLI
     * results; these samples ONLY characterize explicitly warmed execution. */
    for(int v=0;v<5;v++) {vector_zero(&y);execute(v,&a,&p,&generic,v1,&x,&y,1);}
    const char *names[]={"original","v1-scalar","v1-sell16","v2","v2-csr-rows"};
    for(int s=0;s<pairs;s++) {
        /* Ten rounds put each backend in every rank exactly twice. */
        for(int rank=0;rank<5;rank++) {
            int v=(rank+s)%5;vector_zero(&y);
            double elapsed=execute(v,&a,&p,&generic,v1,&x,&y,repeat);
            printf("{\"type\":\"sample\",\"pair\":%d,\"order\":%d,\"backend\":\"%s\",\"execute_s\":%.9f,\"repeat\":%d}\n",s+1,rank,names[v],elapsed,repeat);
            fflush(stdout);
        }
    }
    /* Work distribution is diagnostic, collected after timed samples. */
    int nt=omp_get_max_threads();
    for(int t=0;t<nt;t++) {
        int64_t b=spmv_v2_row_cut(&a,t,nt,0),e=spmv_v2_row_cut(&a,t+1,nt,0);
        int64_t wb=spmv_v2_row_cut(&a,t,nt,1),we=spmv_v2_row_cut(&a,t+1,nt,1);
        printf("{\"type\":\"work\",\"tid\":%d,\"rows_nnz\":%lld,\"work_nnz\":%lld}\n",t,(long long)(a.row_ptr[e]-a.row_ptr[b]),(long long)(a.row_ptr[we]-a.row_ptr[wb]));
    }
    bench_v1_free(v1[0]);bench_v1_free(v1[1]);spmv_plan_free(&p);
    spmv_plan_free(&generic);
    vector_free(&x);vector_free(&y);csr_matrix_int32_free(&a);return 0;
}
