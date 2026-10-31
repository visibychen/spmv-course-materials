/* SPDX-License-Identifier: GPL-3.0-or-later
 * One executable and loader for three frozen implementations. A fixture is
 * ordinary CSR produced by the unmodified original MatrixMarket converter.
 * Its creation/load is common infrastructure, never a v3 performance gain.
 */
#include "csr.h"
#include "matrix_market.h"
#include "vector.h"
#include "spmv_plan.h"
#include "spmv_v3.h"
#include <assert.h>
#include <inttypes.h>
#include <limits.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
struct header {char magic[8];uint64_t rows,columns,nnz;};
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void output(FILE *f,const void *p,size_t size,size_t n){if(n)assert(fwrite(p,size,n,f)==n);}
static void input(FILE *f,void *p,size_t size,size_t n){if(n)assert(fread(p,size,n,f)==n);}
static void export_fixture(const char *path,const char *name,int expand)
{
    FILE *f=fopen(path,"r");assert(f);struct matrix_market mm;int line,col;
    assert(!matrix_market_read(&mm,f,&line,&col));fclose(f);
    struct csr_matrix_int32 a;assert(!csr_matrix_int32_from_matrix_market(&a,&mm,csr_value_f32,expand));matrix_market_free(&mm);
    struct header h={{'V','3','C','S','R','0','1',0},a.num_rows,a.num_columns,a.num_nonzeros};
    f=fopen(name,"wb");assert(f);output(f,&h,sizeof(h),1);
    output(f,a.row_ptr,8,(size_t)a.num_rows+1);output(f,a.column_indices,4,a.num_nonzeros);output(f,a.values,4,a.num_nonzeros);assert(!fclose(f));csr_matrix_int32_free(&a);
}
static void load(const char *name,struct csr_matrix_int32 *a)
{
    FILE *f=fopen(name,"rb");assert(f);struct header h;input(f,&h,sizeof(h),1);
    assert(!memcmp(h.magic,"V3CSR01",8)&&h.rows<INT32_MAX&&h.columns<INT32_MAX&&h.nnz<=INT64_MAX/8);
    assert(!csr_matrix_int32_alloc(a,h.rows,h.columns,h.nnz,csr_value_f32));
    input(f,a->row_ptr,8,(size_t)a->num_rows+1);input(f,a->column_indices,4,a->num_nonzeros);input(f,a->values,4,a->num_nonzeros);
    assert(fgetc(f)==EOF);fclose(f);
}
int main(int argc,char **argv)
{
    assert(argc>=2);
    if(!strcmp(argv[1],"export")){assert(argc==5);export_fixture(argv[2],argv[3],atoi(argv[4]));return 0;}
    assert(!strcmp(argv[1],"run")&&argc>=5);
    int variant=atoi(argv[3]),R=atoi(argv[4]);assert(variant>=0&&variant<=8&&R>=0);
    struct csr_matrix_int32 a;load(argv[2],&a);assert(a.num_nonzeros<=INT64_MAX/2&&(!a.num_nonzeros||R<=INT64_MAX/(2*a.num_nonzeros)));
    struct vector x,y;assert(!vector_alloc(&x,a.num_columns,vector_value_f32));assert(!vector_alloc(&y,a.num_rows,vector_value_f32));
    assert(!vector_ones(&x));assert(!vector_zero(&y));
    struct spmv_plan legacy;struct spmv_v3_plan plan;
    struct spmv_v2_options vo;spmv_v2_defaults(&vo);
    struct spmv_v3_options options;spmv_v3_defaults(&options);
    if(variant==3)options.backend=v3_tile8;
    if(variant==4)options.backend=v3_pipeline4;
    if(variant==5)options.backend=v3_csr;
    if(variant==6)options.work=0;
    if(variant==7)options.allow_simd=0;
    if(variant==8)options.backend=v3_auto;
    int kind=variant==0?0:variant==1?1:2,err=0;
    double start=now();
    if(kind==1)err=spmv_plan_prepare(&legacy,&a,&x,&y,spmv_v2,&vo,4194304);
    else if(kind==2)err=spmv_v3_prepare(&plan,&a,&x,&y,&options);
    double P=kind?now()-start:0;assert(!err);
    int serial=kind==1?legacy.v2.serial:kind==2?plan.serial:0,actual=1;int64_t flops=0;
    start=now();
    if(serial){
        for(int r=0;r<R;r++)err|=kind==1?spmv_plan_execute(&legacy,&x,&y,&flops):spmv_v3_execute(&plan,&x,&y,&flops);
    }else{
#pragma omp parallel reduction(|:err) reduction(max:flops) reduction(max:actual)
        {
            actual=omp_get_num_threads();flops=0;
            for(int r=0;r<R;r++){
                if(kind==0)err|=csr_matrix_int32_spmv(&a,&x,&y,&flops);
                else if(kind==1)err|=spmv_plan_execute(&legacy,&x,&y,&flops);
                else err|=spmv_v3_execute(&plan,&x,&y,&flops);
            }
        }
    }
    double E=now()-start;assert(!err&&flops==2*a.num_nonzeros*R);
    start=now();if(kind==1)spmv_plan_free(&legacy);double D=kind==1?now()-start:0;
    printf("{\"prepare_s\":%.9f,\"execute_s\":%.9f,\"cleanup_s\":%.9f,\"total_s\":%.9f,\"actual_threads\":%d,\"repeat\":%d,\"flops\":%"PRId64",\"simd\":%d,\"backend\":\"%s\"}\n",
        P,E,D,P+E+D,actual,R,flops,kind==2?plan.simd:0,kind==2?spmv_v3_backend_name(options.backend):kind==1?"v2":"original");
    if(argc==6){FILE *f=fopen(argv[5],"wb");assert(f);output(f,y.values,4,y.num_values);assert(!fclose(f));}
    vector_free(&x);vector_free(&y);csr_matrix_int32_free(&a);return 0;
}
