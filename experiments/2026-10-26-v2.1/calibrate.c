/* GPL-3.0-or-later. Offline, generated calibration inputs only. */
#include "spmv_plan.h"
#include <assert.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static uint32_t rng=19871207;
static uint32_t next(void){rng=1664525*rng+1013904223;return rng;}
static volatile int sink;
int main(void)
{
    int ts[]={1,2,4,8,12,24};
    /* m, n, fixed length; these are disjoint from all evaluation matrices. */
    int shape[][3]={{257,4099,1},{4099,65537,8},{8191,32771,17},
        {32771,65537,8},{4099,65537,64},{16381,32771,3},
        {100019,4000003,1},{250013,4000003,8},{131071,4000003,16},
        {65537,4000003,64},{8191,4000003,256},{524309,4000003,4}};
    puts("fingerprint,threads,regime,case,kernel,rows,columns,nonzeros,max_nnz,max_rows,prepare_s,execute_s,launch_s,repeat,sample");
    for(int it=0;it<6;it++) {
        int nt=ts[it];omp_set_num_threads(nt);
        double launch=1;
        for(int q=0;q<5;q++) {
            double t=now();
            if(nt==1)sink++;
            else {
#pragma omp parallel num_threads(nt)
                {if(omp_get_thread_num()==0)sink++;}
            }
            t=now()-t;if(t<launch)launch=t;
        }
        for(int c=0;c<12;c++) {
            int m=shape[c][0],n=shape[c][1],len=shape[c][2];int64_t nz=(int64_t)m*len;
            int64_t *rp=malloc(((size_t)m+1)*sizeof(*rp));int32_t *j=malloc((size_t)nz*sizeof(*j));
            float *v=malloc((size_t)nz*sizeof(*v)),*xx=malloc((size_t)n*sizeof(*xx)),*yy=calloc((size_t)m,sizeof(*yy));
            assert(rp&&j&&v&&xx&&yy);
            for(int r=0;r<=m;r++)rp[r]=(int64_t)r*len;
            for(int64_t k=0;k<nz;k++){j[k]=next()%n;v[k]=(next()%4+1)*0.25f;}
            for(int k=0;k<n;k++)xx[k]=(k%17+1)*0.125f;
            struct csr_matrix_int32 a={m,n,rp,nz,j,csr_value_f32,v};
            struct vector x={n,vector_value_f32,xx},y={m,vector_value_f32,yy};
            int R=(int)(5000000/nz);if(R<3)R=3;if(R>50)R=50;
            for(int sample=0;sample<3;sample++)for(int rank=0;rank<5;rank++) {
                int kernel=1+(rank+sample)%5;if(kernel==v21_short8&&len!=8)continue;
                struct spmv_v21_options o;spmv_v21_defaults(&o);o.kernel=kernel;o.threads=nt;
                /* Separate serial and parallel full preparation observations. */
                o.prepare_mode=nt==1?1:2;
                struct spmv_v2_options common;spmv_v2_defaults(&common);common.partition=v2_rows;
                if(kernel==v21_merge)common.partition=v2_part_auto;
                struct spmv_plan p;double prep=now();assert(!spmv_v21_prepare(&p,&a,&x,&y,&common,&o,R,SIZE_MAX));prep=now()-prep;
                int64_t flops=0;int err=0;
                /* Same one-call warmup for every candidate. */
#pragma omp parallel num_threads(nt) reduction(|:err) reduction(max:flops)
                {flops=0;err=spmv_plan_execute(&p,&x,&y,&flops);}
                assert(!err);double t=now();
                if(nt==1) {
                    for(int r=0;r<R;r++){flops=0;assert(!spmv_plan_execute(&p,&x,&y,&flops));}
                } else {
#pragma omp parallel num_threads(nt) reduction(|:err) reduction(max:flops)
                    {for(int r=0;r<R;r++){flops=0;err=spmv_plan_execute(&p,&x,&y,&flops);}}
                }
                t=now()-t;assert(!err);
                long long maxrows=(m+nt-1)/nt;
                long long maxnz=kernel==v21_merge?(nz+nt-1)/nt:maxrows*len;
                printf("%016llx,%d,%d,%d,%d,%d,%d,%ld,%lld,%lld,%.12g,%.12g,%.12g,%d,%d\n",
                    p.v21.fingerprint,nt,c>=6,c,kernel,m,n,nz,maxnz,maxrows,prep,t,launch,R,sample);
                fflush(stdout);spmv_plan_free(&p);
            }
            free(rp);free(j);free(v);free(xx);free(yy);
        }
    }
    return sink<0;
}
