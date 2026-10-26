#!/usr/bin/env python3
"""Restore ignored baseline/v1 inputs without rebuilding or rewriting history."""
import json,subprocess
import run_experiments as run
def main():
    large=json.loads((run.BASE/'matrix.json').read_text())
    (run.BASE/'data').mkdir(exist_ok=True)
    exe=run.HERE/'build/restore-large-generator'
    subprocess.run(['gcc','-O3','-std=c11','-Wall',str(run.BASE/'generate_matrix.c'),'-o',str(exe)],check=True)
    matrix=run.BASE/'data/large_random.mtx';ref=run.BASE/'data/large_expected.f32'
    if matrix.exists():assert run.sha(matrix)==large['matrix_sha256'],'Existing large matrix differs; not overwriting.'
    if not matrix.exists() or not ref.exists():
        subprocess.run([str(exe),str(matrix),str(ref),str(large['rows']),str(large['nnz_per_row']),str(large['seed_decimal'])],check=True)
    assert run.sha(matrix)==large['matrix_sha256'] and run.sha(ref)==large['expected_sha256']
    (run.OLD/'data').mkdir(exist_ok=True)
    exe=run.HERE/'build/restore-v1-generator'
    subprocess.run(['gcc','-O3','-std=c11','-Wall',str(run.OLD/'generate_cases.c'),'-o',str(exe)],check=True)
    for meta in json.loads((run.OLD/'matrices.json').read_text()):
        if meta['name']=='large':continue
        prefix=run.OLD/'data'/meta['name'];matrix=prefix.with_suffix('.mtx');ref=prefix.with_suffix('.expected.f32')
        if matrix.exists():assert run.sha(matrix)==meta['sha256'],matrix
        if not matrix.exists() or not ref.exists():
            subprocess.run([str(exe),str(prefix),str(meta['rows']),str(meta['columns']),str(meta['length']),meta['profile']],check=True)
        assert run.sha(matrix)==meta['sha256'] and run.sha(ref)==meta['expected_sha256'],matrix
    print('Restored/verified all reused inputs; old tracked records unchanged.')
if __name__=='__main__':main()
