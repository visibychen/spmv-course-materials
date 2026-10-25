/* Record the OpenMP placement actually exposed by this WSL instance. */
#define _GNU_SOURCE
#include <omp.h>
#include <sched.h>
#include <stdio.h>

int main(void)
{
#pragma omp parallel
    {
#pragma omp critical
        printf("thread=%d team=%d cpu=%d place=%d places=%d\n",
               omp_get_thread_num(), omp_get_num_threads(), sched_getcpu(),
               omp_get_place_num(), omp_get_num_places());
    }
    return 0;
}
