/* GPL-3.0-or-later. Same binary, equal warmup, rotated within-process samples. */
#include "spmv_plan.h"
#include "matrix_market.h"
#include <assert.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static double execute(struct spmv_plan *p,struct vector *x,struct vector *y,int R)
{
    int nt=omp_get_max_threads(),err=0;int64_t flops=0;
    if(p->kernel==spmv_v2&&p->v2.serial)nt=1;
    if(p->kernel==spmv_v21)nt=p->v21.threads;
    double t=now();
    if(nt==1)for(int r=0;r<R;r++){err=spmv_plan_execute(p,x,y,&flops);assert(!err);}
    else {
#pragma omp parallel num_threads(nt) reduction(|:err) reduction(max:flops)
        {flops=0;for(int r=0;r<R;r++)err=spmv_plan_execute(p,x,y,&flops);}
    }
    assert(!err);return now()-t;
}
int main(int argc,char **argv)
{
    assert(argc==6);int R=atoi(argv[2]),rounds=atoi(argv[3]),expand=atoi(argv[5]);assert(R>0&&rounds>0);
    FILE *f=fopen(argv[1],"r");assert(f);struct matrix_market mm;int line,col;
    assert(!matrix_market_read(&mm,f,&line,&col));fclose(f);
    struct csr_matrix_int32 a;assert(!csr_matrix_int32_from_matrix_market(&a,&mm,csr_value_f32,expand));matrix_market_free(&mm);
    struct vector x,y;assert(!vector_alloc(&x,a.num_columns,vector_value_f32));assert(!vector_alloc(&y,a.num_rows,vector_value_f32));assert(!vector_ones(&x));vector_zero(&y);
    struct spmv_plan p[6];const char *names[]={"original","v2-auto","v21-auto","v2-csr","v21-csr","v21-long"};
    for(int v=0;v<6;v++) {
        struct spmv_v2_options common;spmv_v2_defaults(&common);struct spmv_v21_options o;spmv_v21_defaults(&o);
        if(v>=3){common.kernel=v2_csr;common.partition=v2_rows;common.execution=v2_parallel;}
        double t=now();int err;
        if(v==0)err=spmv_plan_prepare(&p[v],&a,&x,&y,spmv_original,&common,SIZE_MAX);
        else if(v==1||v==3)err=spmv_v2_prepare(&p[v],&a,&x,&y,&common,SIZE_MAX);
        else {
            o.kernel=v==2?v21_auto:v==4?v21_csr:v21_long;if(v==2)o.profile=argv[4];
            err=spmv_v21_prepare(&p[v],&a,&x,&y,&common,&o,R,SIZE_MAX);
        }
        assert(!err);t=now()-t;
        printf("{\"type\":\"prepare\",\"backend\":\"%s\",\"prepare_s\":%.9f,\"extra_bytes\":%zu,\"actual_threads\":%d,\"selected\":\"%s\"}\n",
            names[v],t,p[v].extra_bytes,p[v].kernel==spmv_v21?p[v].v21.threads:p[v].kernel==spmv_v2&&p[v].v2.serial?1:omp_get_max_threads(),
            p[v].kernel==spmv_v21?spmv_v21_name(p[v].v21.selected):p[v].kernel==spmv_v2?spmv_v2_name(p[v].v2.kernel):"original");
        vector_zero(&y);execute(&p[v],&x,&y,1);
    }
    for(int s=0;s<rounds;s++)for(int rank=0;rank<6;rank++) {
        int v=(s+rank)%6;vector_zero(&y);double t=execute(&p[v],&x,&y,R);
        printf("{\"type\":\"sample\",\"backend\":\"%s\",\"round\":%d,\"rank\":%d,\"repeat\":%d,\"execute_s\":%.9f}\n",names[v],s+1,rank,R,t);fflush(stdout);
    }
    for(int v=0;v<6;v++)spmv_plan_free(&p[v]);vector_free(&x);vector_free(&y);csr_matrix_int32_free(&a);return 0;
}
