/* SPDX-License-Identifier: MIT
 * Deterministic synthetic Matrix Market inputs; no third-party dataset.
 * Usage: generator PREFIX ROWS COLS LENGTH PROFILE
 * PROFILE: random, banded, hot, clustered, scattered, giant, empty99, zero
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
static uint64_t mix(uint64_t x) {
    x=(x^(x>>30))*UINT64_C(0xbf58476d1ce4e5b9);
    x=(x^(x>>27))*UINT64_C(0x94d049bb133111eb);
    return x^(x>>31);
}
static int length(int r,int m,int len,const char *p) {
    if (!strcmp(p,"clustered")) return r<m/100 ? 1024 : 4;
    if (!strcmp(p,"scattered")) return r%100==0 ? 1024 : 4;
    if (!strcmp(p,"giant")) return r==0 ? 1000000 : 1;
    if (!strcmp(p,"empty99")) return r%100==0 ? 8 : 0;
    if (!strcmp(p,"zero")) return 0;
    return len;
}
int main(int argc,char **argv) {
    if(argc!=6)return 2;
    int m=atoi(argv[2]),n=atoi(argv[3]),len=atoi(argv[4]); const char *p=argv[5];
    char name[4096]; snprintf(name,sizeof(name),"%s.mtx",argv[1]);
    FILE *f=fopen(name,"w"); if(!f)return 3;
    snprintf(name,sizeof(name),"%s.expected.f32",argv[1]);
    FILE *ref=fopen(name,"wb"); if(!ref)return 4;
    int64_t nnz=0; for(int r=0;r<m;r++)nnz+=length(r,m,len,p);
    fprintf(f,"%%%%MatrixMarket matrix coordinate real general\n%% synthetic v1 seed 0x20261025\n%d %d %"PRId64"\n",m,n,nnz);
    for(int r=0;r<m;r++) {
        int l=length(r,m,len,p); float sum=0;
        for(int k=0;k<l;k++) {
            uint64_t h=mix(UINT64_C(0x20261025) ^ ((uint64_t)r<<32) ^ (uint64_t)k);
            int c;
            /* Sorted columns, possibly repeated when l>n. One pseudo-random
             * point per ordered segment; row length and x locality separate.
             */
            int span=!strcmp(p,"hot") ? (n<4096?n:4096) : n;
            if(!strcmp(p,"banded")) c=(r+k)%n;
            else {
                uint64_t start=(uint64_t)k*span/l, end=(uint64_t)(k+1)*span/l;
                c=(int)(start+(end>start ? h%(end-start) : 0));
            }
            if(c>=n)c=n-1;
            float v=(float)(1+(h>>48)%7)*0.25f;
            fprintf(f,"%d %d %.2f\n",r+1,c+1,v); sum+=v;
        }
        fwrite(&sum,sizeof(sum),1,ref);
    }
    if(fclose(f)||fclose(ref))return 5;
    return 0;
}
