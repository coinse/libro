import os
import re
import glob
import json
from os import path
from collections import Counter
from tqdm import tqdm

from util import config, license_sslcontext_kickstart, fix_build_env

import subprocess as sp
import javalang
import argparse

DEBUG = False

def get_project_from_bug_id(bug_id):
    for project_identifier in config:
        if project_identifier in bug_id:
            return project_identifier


def verify_in_buggy_version(buggy_commit, test_patch_dir, repo_path, test_prefix):
    sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp.run(['git', 'clean', '-df'],
           cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    # checkout to the buggy version and apply patch to the buggy version
    sp.run(['git', 'checkout', buggy_commit], cwd=repo_path,
           stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp.run(['git', 'apply', test_patch_dir], cwd=repo_path,
           stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    p = sp.run(['git', 'status'], cwd=repo_path,
               stdout=sp.PIPE, stderr=sp.PIPE)

    changed_test_files = [p.strip().split()[-1] for p in p.stdout.decode(
        'utf-8').split('\n') if p.strip().endswith('.java')]

    fix_build_env(repo_path)

    changed_test_id = list(map(lambda x: x.split(
        test_prefix)[-1].split('.')[0].replace('/', '.'), changed_test_files))

    valid_tests = []
    for test_id in changed_test_id:
        test_process = sp.run(['mvn', 'clean', 'test', '-Denforcer.skip=true',
                              f'-Dtest={test_id}', '-DfailIfNoTests=false'], capture_output=True, cwd=repo_path)

        captured_stdout = test_process.stdout.decode()

        if DEBUG:
            os.makedirs(f'log/{repo_path.split("/")[-2]}', exist_ok=True)
            with open(f'./log/{repo_path.split("/")[-2]}/verify_bug_{buggy_commit}_{test_id}.log', 'w') as f:
                f.write(captured_stdout)

        if 'There are test failures' in captured_stdout:
            valid_tests.append(test_id)

    return valid_tests


def verify_in_fixed_version(fixed_commit, target_test_classes, repo_path, test_prefix):
    sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    sp.run(['git', 'clean', '-df'],
           cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    sp.run(['git', 'checkout', fixed_commit], cwd=repo_path)

    fix_build_env(repo_path)

    valid_tests = []
    for test_id in target_test_classes:
        test_process = sp.run(['mvn', 'clean', 'test', '-Denforcer.skip=true',
                              f'-Dtest={test_id}', '-DfailIfNoTests=false'], capture_output=True, cwd=repo_path)
        captured_stdout = test_process.stdout.decode()

        if DEBUG:
            os.makedirs(f'log/{repo_path.split("/")[-2]}', exist_ok=True)
            with open(f'./log/{repo_path.split("/")[-2]}/verify_bug_{fixed_commit}_{test_id}.log', 'w') as f:
                f.write(captured_stdout)

        if 'BUILD SUCCESS' in captured_stdout:
            valid_tests.append(test_id)

    return valid_tests


def verify_bug(bug_id, buggy_commit, fixed_commit):
    project = get_project_from_bug_id(bug_id)
    repo_path = config[project]['repo_path']
    src_dir = config[project]['src_dir']
    test_prefix = config[project]['test_prefix']

    test_patch_dir = os.path.abspath(os.path.join(
        './data-collector/test_diff', f'{bug_id}.diff'))

    valid_tests = verify_in_buggy_version(
        buggy_commit, test_patch_dir, repo_path, test_prefix)

    success_tests = verify_in_fixed_version(
        fixed_commit, valid_tests, repo_path, test_prefix)

    return valid_tests, success_tests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('projects', nargs='*', default=[])
    parser.add_argument('--bug', default=None)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    if args.debug:
        DEBUG = True

    with open('data-collector/report_test_mappings.json') as f:
        report_test_mappings = json.load(f)

    if args.bug is not None:
        bug_id = args.bug
        repo_name = '-'.join(bug_id.split('-')[:-1])
        buggy_commit = report_test_mappings[repo_name][bug_id]['buggy_commit']
        fixed_commit = report_test_mappings[repo_name][bug_id]['merge_commit']

        valid_tests, success_tests = verify_bug(
            bug_id, buggy_commit, fixed_commit)

        print(valid_tests)
        print(success_tests)

    else:
        if len(args.projects) == 0:
            target_projects = [config[p]['project_name'] for p in config]

        else:
            target_projects = [config[p]['project_name']
                               for p in args.projects]

        if os.path.exists('data-collector/report_test_mappings_w_execution_result.json'):
            with open('data-collector/report_test_mappings_w_execution_result.json') as f:
                report_test_mappings_w_execution_result = json.load(f)
        else:
            report_test_mappings_w_execution_result = {}

        for repo_name, dataset in report_test_mappings.items():
            if repo_name not in target_projects:
                continue
            print(repo_name)
            report_test_mappings_w_execution_result[repo_name] = {}

            for bug_id in tqdm(dataset):
                repo_name = '-'.join(bug_id.split('-')[:-1])
                buggy_commit = report_test_mappings[repo_name][bug_id]['buggy_commit']
                fixed_commit = report_test_mappings[repo_name][bug_id]['merge_commit']

                valid_tests, success_tests = verify_bug(
                    bug_id, buggy_commit, fixed_commit)

                dataset[bug_id]['execution_result'] = {
                    'valid_tests': valid_tests,
                    'success_tests': success_tests,
                }

                report_test_mappings_w_execution_result[repo_name][bug_id] = dataset[bug_id]


        # save only verified bugs
        verified_bugs = {}

        for repo_name in report_test_mappings_w_execution_result:
            for bug_id, bug_info in report_test_mappings_w_execution_result[repo_name].items():
                if len(bug_info['execution_result']['success_tests']) > 0:
                    verified_bugs[bug_id] = bug_info


        for bug_id in verified_bugs:
            shutil.copy(f'collected_issues/{bug_id}.json', f'../data/GHRB/bug_report/{bug_id}.json')

        with open('../data/GHRB/verified_bugs.json', 'w') as f:
            json.dump(verified_bugs, f, indent=2)

        
