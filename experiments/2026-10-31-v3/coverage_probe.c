/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "spmv_v3.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    int64_t rp[33];int32_t j[256];float v[256],xv[37],yv[32],ref[32];
    for(int r=0;r<=32;r++)rp[r]=8*r;
    for(int k=0;k<256;k++){j[k]=k%37;v[k]=(k%7-3)*.25f;}
    for(int r=0;r<32;r++)ref[r]=yv[r]=(r%5)*.25f;
    struct csr_matrix_int32 a={32,37,rp,256,j,csr_value_f32,v};
    struct vector x={37,vector_value_f32,xv},y={32,vector_value_f32,yv};
    struct spmv_v3_options o;spmv_v3_defaults(&o);o.backend=v3_tile8;
    struct spmv_v3_plan p;assert(!spmv_v3_prepare(&p,&a,&x,&y,&o));int64_t flops=0;
    for(int rep=0;rep<3;rep++){
        for(int k=0;k<37;k++)xv[k]=(k-12+rep)*.125f;
        for(int r=0;r<32;r++){float s=0;for(int64_t k=rp[r];k<rp[r+1];k++)s+=v[k]*xv[j[k]];ref[r]+=s;}
        assert(!spmv_v3_execute(&p,&x,&y,&flops));
        for(int r=0;r<32;r++)assert(yv[r]==ref[r]);
    }
    assert(flops==1536);printf("simd=%d correct=1\n",p.simd);return 0;
}
