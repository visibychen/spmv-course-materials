/* GPL-3.0-or-later. Same-binary diagnostic; no independent-process claims. */
#include "spmv_plan.h"
#include "matrix_market.h"
#include <assert.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static int planned(const struct spmv_plan *p)
{
    if(p->kernel==spmv_v22||p->kernel==spmv_v222)return p->v22.threads;
    return p->kernel==spmv_v2&&p->v2.serial?1:omp_get_max_threads();
}
static double execute(struct spmv_plan *p,struct vector *x,struct vector *y,int R,int *actual)
{
    int nt=planned(p),err=0,observed=1;int64_t flops=0;double start=now();
    if(nt==1){for(int r=0;r<R;r++)err|=spmv_plan_execute(p,x,y,&flops);}
    else {
#pragma omp parallel num_threads(nt) reduction(|:err) reduction(max:flops)
        {
            if(!omp_get_thread_num())observed=omp_get_num_threads();
            flops=0;for(int r=0;r<R;r++)err|=spmv_plan_execute(p,x,y,&flops);
        }
    }
    double elapsed=now()-start;assert(!err&&flops==2*p->matrix->num_nonzeros*R);*actual=observed;return elapsed;
}
int main(int argc,char **argv)
{
    assert(argc==5);int R=atoi(argv[2]),rounds=atoi(argv[3]),expand=atoi(argv[4]);assert(R>0&&rounds>0);
    FILE *f=fopen(argv[1],"r");assert(f);struct matrix_market mm;int line,col;
    assert(!matrix_market_read(&mm,f,&line,&col));fclose(f);
    struct csr_matrix_int32 a;assert(!csr_matrix_int32_from_matrix_market(&a,&mm,csr_value_f32,expand));matrix_market_free(&mm);
    struct vector x,y;assert(!vector_alloc(&x,a.num_columns,vector_value_f32));assert(!vector_alloc(&y,a.num_rows,vector_value_f32));assert(!vector_ones(&x));vector_zero(&y);
    struct spmv_plan plans[6];const char *names[]={"original","v2-auto","v22-auto","v222-auto","v222-policy-parent","v222-runs-off"};
    for(int v=0;v<6;v++){
        struct spmv_v2_options common;spmv_v2_defaults(&common);
        struct spmv_v22_options old={1,0};struct spmv_v222_options o={0,0};
        if(v==4)o.policy=1;
        if(v==5)o.runs=1;
        double start=now();int err;
        if(v==0)err=spmv_plan_prepare(&plans[v],&a,&x,&y,spmv_original,&common,4194304);
        else if(v==1)err=spmv_v2_prepare(&plans[v],&a,&x,&y,&common,4194304);
        else if(v==2)err=spmv_v22_prepare(&plans[v],&a,&x,&y,&common,&old,R,4194304);
        else err=spmv_v222_prepare(&plans[v],&a,&x,&y,&common,&o,R,4194304);
        assert(!err);double elapsed=now()-start;struct spmv_plan *p=&plans[v];
        printf("{\"type\":\"prepare\",\"backend\":\"%s\",\"prepare_s\":%.9f,\"extra_bytes\":%zu,\"compute_threads\":%d,\"selected\":\"%s\",\"executor\":\"%s\",\"route\":\"%s\"}\n",names[v],elapsed,p->extra_bytes,planned(p),
            p->kernel==spmv_original?"original":p->v22.empty_runs?"empty-runs":spmv_v2_name(p->v2.kernel),spmv_kernel_name(p->kernel),
            p->v222.active?"bounded-empty-runs":p->kernel==spmv_v22?p->v22.route:"control");
        vector_zero(&y);int actual;execute(p,&x,&y,1,&actual);
    }
    for(int round=0;round<rounds;round++)for(int rank=0;rank<6;rank++){
        int v=(round+rank)%6,actual;vector_zero(&y);double elapsed=execute(&plans[v],&x,&y,R,&actual);
        printf("{\"type\":\"sample\",\"backend\":\"%s\",\"round\":%d,\"rank\":%d,\"repeat\":%d,\"execute_s\":%.9f,\"actual_threads\":%d}\n",names[v],round+1,rank,R,elapsed,actual);fflush(stdout);
    }
    for(int v=0;v<6;v++)spmv_plan_free(&plans[v]);
    vector_free(&x);vector_free(&y);csr_matrix_int32_free(&a);return 0;
}
