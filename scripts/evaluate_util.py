import json
import os 
import glob
import pandas as pd


def evaluate_ranking(rank_df, Ns=[1,3,5]):
    result = {}
    for N in Ns:
        rows = []
        for i, row in rank_df.iterrows():
            first_success = row['first_success_rank']
            num_clusters = row['num_clusters']
            if first_success <= N:
                wasted_effort = first_success - 1
            elif first_success > N:
                wasted_effort = min(num_clusters, N)

            rows.append({
                'bug_id': row['bug_id'],
                'success': wasted_effort < min(num_clusters, N),
                'wasted_effort': wasted_effort
            })
        
        result[N] = pd.DataFrame(rows)
    
    agg_result = {}
    for N in Ns:
        agg_result['wef@{}_sum'.format(N)] = result[N].wasted_effort.sum()
        agg_result['wef@{}_mean'.format(N)] = result[N].wasted_effort.mean()
        agg_result['acc@{}'.format(N)] = result[N].success.sum()

    return agg_result


def process_results_for_baseline(raw_result):
    rows = []
    with open('../../data/Defects4J/invalid_bug_reports.txt') as f:
        invalid_bugs = [bug.strip() for bug in f.readlines()]

    for bug_id, test_exec_results in raw_result.items():
        if bug_id.replace('_', '-') in invalid_bugs:
            continue
        for filename, res in test_exec_results.items():
            javalang_parse_error = False
            is_compile_error = False
            is_runtime_error = False
            buggy_version_failing = False
            fixed_version_failing = False
            success = res['success'] if isinstance(res, dict) else False

            if isinstance(res, str):
                javalang_parse_error = True 
            elif res['buggy']['compile_error'] or res['fixed']['compile_error']:
                is_compile_error = True
                success = False
            elif res['buggy']['runtime_error'] or res['fixed']['runtime_error']:
                is_runtime_error = True
                success = False
            else:
                if res['buggy']['autogen_failed']:
                    buggy_version_failing = True
                if res['fixed']['autogen_failed']:
                    fixed_version_failing = True
            
            rows.append({
                'project': bug_id.split('-')[0],
                'bug_id': bug_id,
                'test_file_name': filename,
                'javalang_parse_error': javalang_parse_error,
                'is_compile_error': is_compile_error,
                'is_runtime_error': is_runtime_error,
                'buggy_version_failing': buggy_version_failing,
                'fixed_version_failing': fixed_version_failing,
                'success': success
            })

    return pd.DataFrame(rows)