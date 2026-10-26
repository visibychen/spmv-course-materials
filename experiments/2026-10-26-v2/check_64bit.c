/* SPDX-License-Identifier: GPL-3.0-or-later
 * Search arithmetic only: huge logical offsets without allocating fake nnz
 * arrays. No multiplication is attempted on this structural test fixture.
 */
#include "spmv_plan.h"
#include <assert.h>
#include <limits.h>
#include <omp.h>
#include <stdio.h>
int main(void)
{
    int checks=0;
    int64_t sizes[]={((int64_t)1<<31)+123,((int64_t)1<<33)+17,INT64_MAX/2-32};
    for(int z=0;z<3;z++) {
        int64_t n=sizes[z],rp[]={0,n/3,n/3,n-1,n};
        struct csr_matrix_int32 a={0};a.num_rows=4;a.num_nonzeros=n;a.row_ptr=rp;
        int64_t points[]={0,1,2,n/3-1,n/3,n/3+1,n/3+2,n/3+3,n-1,n,n+1,n+2,n+3,n+4};
        for(size_t i=0;i<sizeof(points)/sizeof(*points);i++) {
            int64_t r,k;spmv_v2_merge_cut(&a,points[i],&r,&k);
            assert(r>=0 && r<=4 && k>=0 && k<=n && r+k==points[i]);
            /* Stable merged-prefix inequalities, independent of binary search. */
            if(r>0 && k<n) assert(rp[r]<=k);
            if(k>0 && r<4) assert(k-1<rp[r+1]);
            checks++;
        }
        for(int nt=1;nt<=257;nt++) {
            int64_t last=0;
            for(int t=0;t<=nt;t++) {
                int64_t cut=spmv_v2_row_cut(&a,t,nt,1),total=n+4;
                __int128 goal=(__int128)(total/nt)*t+(t<total%nt ? t:total%nt);
                int64_t oracle=0;
                while(oracle<4 && (__int128)rp[oracle]+oracle<goal) oracle++;
                assert(cut==oracle && cut>=last && cut<=4);last=cut;checks++;
            }
            assert(last==4);
        }
    }
    /* Nonzero results when actual team exceeds and then fits scratch. */
    int64_t rp[]={0,8,16,24};int32_t col[24]={0};float values[24],xv[]={2},yv[]={10,10,10};
    for(int i=0;i<24;i++) values[i]=1;
    struct csr_matrix_int32 a={3,1,rp,24,col,csr_value_f32,values};
    struct vector x={1,vector_value_f32,xv},y={3,vector_value_f32,yv};
    struct spmv_v2_options o;spmv_v2_defaults(&o);o.kernel=v2_merge;o.execution=v2_parallel;
    for(int capacity=1;capacity<=6;capacity+=5) {
        omp_set_num_threads(capacity);struct spmv_plan p;
        assert(!spmv_v2_prepare(&p,&a,&x,&y,&o,SIZE_MAX));
        for(int nt=2;nt<=3;nt++) {
            for(int r=0;r<3;r++) yv[r]=10;
            int err=0;int64_t flops=0;
#pragma omp parallel num_threads(nt) reduction(|:err) reduction(max:flops)
            {flops=0;err=spmv_plan_execute(&p,&x,&y,&flops);}
            assert(!err && flops==48);
            for(int r=0;r<3;r++) assert(yv[r]==26);
            checks++;
        }
        spmv_plan_free(&p);
    }
    printf("PASS wide-index and nonzero team checks: %d checks; no huge allocation\n",checks);
    return 0;
}
