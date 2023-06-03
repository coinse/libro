import os
import re
import json
import copy
import random
import pandas as pd
import argparse

from collections import defaultdict
from tqdm import tqdm

from common import normalize_test, process_result, count_test_tokens
from process_failure_output import *
from process_bug_report import *

RESULT_PATH = '../results/example2_n50.json'
GEN_TEST_PATH = '../data/Defects4J/gen_tests/'

RESULT_PATH_GHRB = '../results/example2_n50_GHRB.json'
GEN_TEST_PATH_GHRB = '../data/GHRB/gen_tests/'

BIG_NUMBER = 100000
SELECTION_THRESHOLD = 1

def select_confident_bugs(rank_feature_df, threshold=1):
    max_df = rank_feature_df.groupby('bug_id').max()
    df = max_df[max_df.clus_size_output_fib <= threshold]
    selected_df = max_df[max_df.clus_size_output_fib > threshold].reset_index()
    selected_bugs = list(selected_df.bug_id.unique())

    return rank_feature_df[rank_feature_df.bug_id.isin(selected_bugs)]


def rank_tests_using_clusters(rank_feature_df, test_clusters, random_baseline=False, seed=0):
    rows = []
    for bug_id, fib_tests_features in rank_feature_df.groupby('bug_id'):
        if random_baseline:
            sorted_fib_tests = shuffle_fib_tests(fib_tests_features, seed=seed)
        else:
            sorted_fib_tests = sort_unique_fib_tests(bug_id, fib_tests_features, test_clusters)

        success_tests = fib_tests_features[fib_tests_features.success].test_path.tolist()

        success_ranks = []
        for i, (test, score_first, score_second, score_third) in enumerate(sorted_fib_tests):
            if test in success_tests:
                success_ranks.append(i+1)    

        rows.append({
            'bug_id': bug_id,
            'total_success_fibs': len(success_tests),
            'first_success_rank': min(success_ranks) if len(success_ranks) > 0 else BIG_NUMBER,
            'success_ranks': success_ranks,
            'num_clusters': len(sorted_fib_tests),
            'score_first': score_first,
            'score_second': score_second,
            'score_third': score_third,
            'sorted_tests': [os.path.basename(test[0]) for test in sorted_fib_tests]
        })
        
    
    return pd.DataFrame(rows)


def collect_ranking_features(fib_bug_ids, fib_clusters, aggreement_scores, OB, parsed_output):
    rows = []
    success_count = 0
    for bug_id in fib_bug_ids:
        has_success = False
        for rep, test_paths in fib_clusters[bug_id].items():
            rep_test = test_paths[0]
            rep_test = os.path.basename(rep_test)
            features = {
                'bug_id': bug_id,
                'test_path': rep_test,
                'success': result_dict[bug_id][rep_test]['success'],
            }

            if features['success']:
                has_success = True

            test_content = None
            with open(test_paths[0]) as f:
                test_content = f.read().strip()
                features['test_length'] = count_test_tokens(test_content.strip())

            features[f'clus_size_output_fib'] = aggreement_scores[bug_id][rep_test]

            features[f'num_fib_tests'] = len(test_paths)
            match_output_result = match_buggy_output_w_report(parsed_output[bug_id][rep_test], OB[bug_id])
            match_test_result = match_test_body_w_report(test_content, OB[bug_id])

            features['is_crash'] = match_output_result['is_crash']
            features['actual_crash'] = match_output_result['actual_crash']
            features['actual_value_match'] = match_output_result['actual_value_match']
            features['exception_type_match'] = match_output_result['exception_type_match']
            features['test_exception_type_match'] = match_test_result['exception_type_match']
            
            rows.append(features)

        if has_success:
            success_count += 1    

    return pd.DataFrame(rows)

def sort_unique_fib_tests(bug_id, test_features, test_clusters):
    output_clusters = dict()
    cluster_feature_map = dict()
    final_deliver_list = []
    test_features = test_features.set_index('test_path')

    for c, test_paths in test_clusters[bug_id].items():
        intra_cluster_tests = []
        test_keys = []
        sum_test_length = 0
        has_test_match = False

        for test_path in test_paths:
            test_key = os.path.basename(test_path)
            if test_key not in test_features.index.tolist():
                continue
            
            test_keys.append(test_key)
            assert test_features.loc[test_key].clus_size_output_fib == len(test_paths)
        
            intra_cluster_tests.append((test_key, test_features.loc[test_key].test_length, int(test_features.loc[test_key].test_exception_type_match), 0))

            if test_features.loc[test_key].test_exception_type_match:
                has_test_match = True

            sum_test_length += test_features.loc[test_key].test_length

        test_feat = test_features.loc[test_keys[0]] # use the first (syntactically unique) test as representative
        crash_type_match_score = int(test_feat.exception_type_match and test_feat.is_crash)
        actual_value_match_score = int(test_feat.actual_value_match and not test_feat.is_crash)
        bug_report_match = crash_type_match_score + actual_value_match_score

        cluster_feature_map[c] = (bug_report_match, len(test_paths), -sum_test_length/len(test_paths))

        intra_cluster_tests.sort(key=(lambda x: (-x[2], x[1]))) # test-br match => shorter test length
        output_clusters[c] = intra_cluster_tests

    sorted_cluster_keys = sorted(output_clusters.keys(), key=lambda x: cluster_feature_map[x], reverse=True)
    for i in range(max([len(clus) for clus in output_clusters.values()])):
        for c in sorted_cluster_keys:
            if i < len(output_clusters[c]):
                final_deliver_list.append(output_clusters[c][i])

    return final_deliver_list


def shuffle_fib_tests(fib_test_features, seed):
    random_test_order = []

    for bug_id, test_feat in fib_test_features.iterrows():
        crash_type_match_score = int(test_feat.exception_type_match and test_feat.is_crash)
        actual_value_match_score = int(test_feat.actual_value_match and not test_feat.is_crash)
        output_cluster_size_score = test_feat.clus_size_output_fib

        random_test_order.append((test_feat.test_path, crash_type_match_score + actual_value_match_score, output_cluster_size_score, test_feat.test_path))
        
    random.Random(seed).shuffle(random_test_order)
    return random_test_order


def match_test_body_w_report(test_content, OB):
    if OB['is_crash']:
        for line in test_content.split('\n'):
            m = re.search(r'catch\s*\((.*Exception)', line)
            if m is not None:
                if m.group(1) in OB['NL_context']:
                    return {
                        'handled_exception_type': m.group(1),
                        'exception_type_match': True
                    }
    return {
        'handled_exception_type': None,
        'exception_type_match': False
    }


def match_buggy_output_w_report(parsed_output, OB):
    actual_crash = False
    exception_type_match = False
    actual_value_match = False
    matched_actual_values = []

    exception_type = parsed_output['exception_type'].split('.')[-1]

    if parsed_output['is_crash']:
        actual_crash = True

    if OB['is_crash']:
        if actual_crash:
            if exception_type != 'Exception' and exception_type in OB['NL_context']:
                exception_type_match = True

    else:
        if not actual_crash:
            if exception_type in OB['NL_context']:
                exception_type_match = True

            if parsed_output['actual'] is not None and len(parsed_output['actual']) > 0:
                # better cleaninig method..
                if any(c in parsed_output["actual"] for c in [',', '.', '>', '<', '"', '\'', '(', ')', '[', ']']) and len(parsed_output["actual"]) > 4:
                        m = re.search(fr'.*{re.escape(parsed_output["actual"])}.*', OB['full_text'])
                        if m is not None:
                            matched_actual_values.append((parsed_output["actual"], m.group(0)))
                            actual_value_match = True

                else:
                    m = re.search(fr'[\s\.\,\"\'\(\[\<]+{re.escape(parsed_output["actual"])}[\s\n\.\,\"\'\)\]\>]+', OB['full_text'])
                    if m is not None:
                        matched_actual_values.append((parsed_output["actual"], m.group(0)))
                        actual_value_match = True

    return {
        'is_crash': OB['is_crash'],
        'actual_crash': actual_crash,
        'exception_type_match': exception_type_match,
        'actual_value_match': actual_value_match,
        'matched_actual_values': matched_actual_values
    }


def cluster_tests(bug_result, among_fib=True, by='syntax', dataset='d4j'):
    """
    Given test results for a bug, cluster tests either by test syntax or by output value
    - among_fib: True | False
    - by: syntax | output
    """
    clusters = defaultdict(list)
    targets = []

    for test_result in bug_result.values():
        if test_result['parse_error']:
            continue

        if among_fib and not test_result['is_fib']:
            continue

        if by == 'syntax':
            with open(test_result['test_file_path']) as f:
                gen_test = f.read()
            rep = normalize_test(gen_test)
        elif by == 'output':
            fib_test_id = test_result['fib_test_id'].split('::')[0]
            if test_result['buggy_output'] is None:
                continue
            if dataset == 'd4j':
                rep = test_result['buggy_output'].split('\n')[1].strip()
                rep = rep.replace(fib_test_id, '[FIB_TEST_ID]')
            elif dataset == 'ghrb':
                rep = test_result['exception_msg'].strip()

        clusters[rep].append(test_result['test_file_path'])
        targets.append(test_result['test_file_path'])

    return clusters

def aggregate_results_from_random_baseline(rank_feature_df_selected, test_clusters):
    seeds = range(100)
    result = {}
    Ns = [1, 3, 5]

    rdf = rank_feature_df_selected

    wasted_effort_results = defaultdict(list)
    acc_results = defaultdict(list)

    for s in tqdm(seeds):
        df = rank_tests_using_clusters(rdf, test_clusters, random_baseline=True, seed=s)
        total = len(df)
        
        for N in Ns:
            rows = []
            for i, row in df.iterrows():
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

        for N in Ns:
            wasted_effort_results[N].append((float(result[N].wasted_effort.sum()), float(result[N].wasted_effort.mean())))
            acc_results[N].append(float(result[N].success.sum()))


        list_acc = []
        list_wef = []
        for i, row in df.iterrows():
            first_success = row['first_success_rank']
            num_clusters = row['num_clusters']
            if first_success <= num_clusters:
                wasted_effort = first_success - 1
            elif first_success == BIG_NUMBER:
                wasted_effort = num_clusters
            else:
                raise Exception('first success rank is bigger than number of the clusters')

            list_acc.append(wasted_effort < num_clusters)
            list_wef.append(wasted_effort)

    aggr_result = {}

    for N in Ns:
        aggr_result[N] = {
            'wefs': wasted_effort_results[N],
            'acc': acc_results[N]
        }

    return aggr_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', default='Defects4J', help='Defects4J or GHRB')
    parser.add_argument('-f', '--result_file', default=None, help='Path to the execution result file (e.g., `../results/example2_n50.json`)')
    parser.add_argument('-g', '--gen_test_path', default=None, help='Directory that contains raw generated tests (e.g., `../data/Defects4J/gen_tests/`)')
    parser.add_argument('--random', action='store_true', help='Produce random baseline results')
    args = parser.parse_args()

    if args.dataset == 'Defects4J':
        result_path = RESULT_PATH
        gen_test_path = GEN_TEST_PATH
        dname = 'd4j'
    elif args.dataset == 'GHRB':
        result_path = RESULT_PATH_GHRB
        gen_test_path = GEN_TEST_PATH_GHRB
        dname = 'ghrb'
    else:
        raise Exception('Invalid dataset')

    if args.result_file is not None:
        print(f'Use the custom result file {args.result_file}...')
        result_path = args.result_file

    if args.gen_test_path is not None:
        print(f'Use the custom generated test path {args.gen_test_path}...')
        gen_test_path = args.gen_test_path
        
    result_dict = process_result(result_path, gen_test_path)

    # 1. converts test results into dataframe
    rows = []
    for bug_id, test_results in result_dict.items():
        for filename, test_result in test_results.items():
            rows.append({
                'bug_id': bug_id,
                'test_key': filename,
                'file_path': test_result['test_file_path'],
                'parse_error': test_result['parse_error'],
                'compile_error': test_result['compile_error'],
                'FIB': test_result['is_fib'],
                'success': test_result['success'] if not test_result['has_error'] else False
            })

    result_df = pd.DataFrame(rows)
    fib_bug_ids = result_df[result_df['FIB'] == True].bug_id.unique()
    success_bug_ids = result_df[result_df['success'] == True].bug_id.unique()

    # 2. extract information from bug report and failure output for each bug
    bug_reports = load_bug_report_features(dataset=dname)
    OB = {}
    parsed_output = defaultdict(dict)

    for bug_id in fib_bug_ids:
        OB[bug_id] = parse_bug_report(bug_id, bug_reports, dataset=dname)
        for name, test_result in result_dict[bug_id].items():
            if test_result['buggy_output'] is not None:
                if dname == 'd4j':
                    parsed_output[bug_id][name] = parse_buggy_output(test_result['buggy_output'],
                    mode='d4j')
                elif dname == 'ghrb':
                    parsed_output[bug_id][name] = parse_buggy_output(test_result['buggy_output'], exception_type=test_result['exception_type'], exception_msg=test_result['exception_msg'], value_matching=test_result['value_matching'], mode='ghrb')

    # 3. group syntactically equivalent tests (syntax clusters)
    fib_clusters = {}
    for bug_id, bug_result in tqdm(result_dict.items()):
        fib_clusters[bug_id] = cluster_tests(bug_result, among_fib=True, by='syntax', dataset=dname)

    # 4. construct output clusters among FIBs
    test_clusters = dict()
    aggreement_scores = defaultdict(dict)

    for bug_id, bug_result in tqdm(result_dict.items()):
        clusters = cluster_tests(bug_result, among_fib=True, by='output', dataset=dname)
        test_clusters[bug_id] = clusters
        for c, test_paths in clusters.items():
            for test_path in test_paths:
                test_key = os.path.basename(test_path)
                aggreement_scores[bug_id][test_key] = len(test_paths)

    # 5. collect rank features and apply intra+inter cluster ranking strategy
    rank_feature_df = collect_ranking_features(fib_bug_ids, fib_clusters, aggreement_scores, OB, parsed_output)

    with open(f'../results/ranking_features_{dname}.csv', 'w') as f:
        rank_feature_df.to_csv(f, index=False)

    rank_df = rank_tests_using_clusters(rank_feature_df, test_clusters)

    with open(f'../results/ranking_{dname}.csv', 'w') as f:
        rank_df[['bug_id', 'first_success_rank', 'total_success_fibs', 'num_clusters']].to_csv(f, index=False)

    # result before selection
    print(f'\n[Ranking result before selection]')
    Ns = [1, 3, 5]
    for N in Ns:
        print(f'* acc@{N}: {len(rank_df[rank_df.first_success_rank <= N])}')
    print(f'* Total (success): {len(rank_df[rank_df.first_success_rank < BIG_NUMBER])}')
    print(f'* Total (fib): {len(rank_df)}')

    # 6. select bugs to present and rank within them (only confident ones)
    rank_feature_df_selected = select_confident_bugs(rank_feature_df, threshold=SELECTION_THRESHOLD)
    rank_df_selected = rank_tests_using_clusters(rank_feature_df_selected, test_clusters)

    with open(f'../results/ranking_{dname}_selected_th{SELECTION_THRESHOLD}.csv', 'w') as f:
        rank_df_selected[['bug_id', 'first_success_rank', 'total_success_fibs', 'num_clusters']].to_csv(f, index=False)

    # result after selection
    print(f'\n[Ranking result after selection]')
    total = len(rank_df_selected)
    for N in Ns:
        acc_N = len(rank_df_selected[rank_df_selected.first_success_rank <= N])
        print(f'* acc@{N}: {acc_N} ({round(acc_N / total, 2)})')
    print(f'* Total (success): {len(rank_df_selected[rank_df_selected.first_success_rank < BIG_NUMBER])} ({round(len(rank_df_selected[rank_df_selected.first_success_rank < BIG_NUMBER]) / total, 2)})')
    print(f'* Total: {total}')

    if args.random:
        # random baseline (metrics precomputed)
        random_baseline_result = aggregate_results_from_random_baseline(rank_feature_df_selected, test_clusters)

        with open(f'../results/ranking_random_baseline_{dname}.json', 'w') as f:
            json.dump(random_baseline_result, f, indent=2)
