from os import path
from common import *
from config import llm_exp_config

import os
import re
import subprocess as sp
import argparse
import d4j_util


def inject_prefix_rootdir(proj, bug_id):
    rpath = d4j_util.repo_path(proj, bug_id)
    return rpath
    
    
def enforce_static_assertions(gen_test):
    if 'Assert.' in gen_test:
        # force to use static assertion imports
        gen_test = gen_test.replace('Assert.fail', 'fail')
        gen_test = gen_test.replace('Assert.assert', 'assert')
    return gen_test
    

def needed_imports_by_bug_id(proj, bug_id, gen_test):
    repo_path = d4j_util.repo_path(proj, bug_id)
    src_dir = d4j_util.d4j_path_prefix(proj, bug_id)

    classpaths, needed_class_stubs, needed_asserts = needed_imports(
        repo_path, src_dir, gen_test)

    return classpaths, needed_asserts


def add_test_by_bug_id(proj, bug_id, gen_test, needed_elements, dry=False):
    repo_path = d4j_util.repo_path(proj, bug_id)
    test_prefix = d4j_util.d4j_test_path_prefix(proj, bug_id)

    # proj is needed to obtain project identifier (e.g., jackson.core)
    return add_test(proj, repo_path, test_prefix, gen_test, needed_elements, dry=dry)


def inject_test_by_bug_id(proj, bug_id, gen_test, needed_elements, dry=False):
    repo_path = inject_prefix_rootdir(proj, bug_id)
    src_dir = d4j_util.d4j_path_prefix(proj, bug_id)
    test_dir = d4j_util.d4j_test_path_prefix(proj, bug_id)

    return inject_test(repo_path, src_dir, test_dir, gen_test, needed_elements, dry=dry)


def git_reset(repo_dir_path):
    sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def git_clean(repo_dir_path):
    sp.run(['git', 'clean', '-df'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    
def git_d4j_handle(repo_dir_path, ref_tag):
    sp.run(['git', 'checkout', ref_tag, '--', '.defects4j.config'],
           cwd=repo_dir_path)
    sp.run(['git', 'checkout', ref_tag, '--', 'defects4j.build.properties'],
           cwd=repo_dir_path)
    

def compile_repo(repo_dir_path):
    # actual compiling
    compile_proc = sp.run(
        ['defects4j', 'compile'],
        stdout=sp.PIPE, stderr=sp.PIPE, cwd=repo_dir_path)
    
    # extracting error message
    compile_error_lines = compile_proc.stderr.decode('utf-8').split('\n')[2:]
    compile_error_lines = [
        e for e in compile_error_lines if '[javac] [' not in e]
    compile_error_lines = [e for e in compile_error_lines if '[javac]' in e]
    compile_error_lines = [
        e for e in compile_error_lines if 'warning:' not in e]
    compile_error_lines = [
        e for e in compile_error_lines if '[javac] Note:' not in e]
    compile_error_lines = [
        e for e in compile_error_lines if 'compiler be upgraded.' not in e]
    compile_error_msg = '\n'.join(compile_error_lines)
    return compile_proc.returncode, compile_error_msg


def run_test(repo_dir_path, test_name):
    '''Returns failing test number.'''
    test_process = sp.run(['timeout', '1m', 'defects4j', 'test', '-t', test_name],
                          capture_output=True, cwd=repo_dir_path)
    captured_stdout = test_process.stdout.decode()
    if len(captured_stdout) == 0:
        return -1, []  # likely compile error, all tests failed
    else:
        stdout_lines = captured_stdout.split('\n')
        failed_test_num = int(stdout_lines[0].removeprefix('Failing tests: '))
        failed_tests = [e.strip(' - ') for e in stdout_lines[1:] if len(e) > 1]
        # reported failing test number and actual number of collected failing tests should match
        assert len(failed_tests) == failed_test_num

        return 0, failed_tests


def individual_run(proj, bug_id, example_test, injection):
    # test class generation & addition
    repo_path = inject_prefix_rootdir(proj, bug_id) if injection else d4j_util.repo_path(proj, bug_id)
    needed_elements = needed_imports_by_bug_id(proj, bug_id, example_test)
    test_add_func = inject_test_by_bug_id if injection else add_test_by_bug_id
    test_name = test_add_func(proj, bug_id, example_test, needed_elements)

    # actual running experiment
    fib_error_msg = None
    compile_status, compile_msg = compile_repo(repo_path)
    if compile_status != 0:
        status = -2
        failed_tests = []
    else:
        status, failed_tests = run_test(repo_path, test_name)
        if len(failed_tests) > 0:
            with open(path.join(repo_path, 'failing_tests')) as f:
                fib_error_msg = ''.join(f.readlines()[:5])
    
    if fib_error_msg is not None and 'not found' in fib_error_msg:
        print(f'Warning; test not found for {proj}-{bug_id}:{test_name}.')
    
    return {
        'compile_error': status == -2,
        'runtime_error': status == -1,
        'failed_tests': failed_tests,
        'autogen_failed': len(failed_tests) > 0,
        'fib_error_msg': fib_error_msg,
        'compile_msg': compile_msg if status == -2 else None
    }


def twover_run_experiment(proj, bug_id, example_tests, injection=True):
    """
    returns results in order of example_tests.
    """

    # init
    repo_path = inject_prefix_rootdir(proj, bug_id) if injection else d4j_util.repo_path(proj, bug_id)
    test_dir = d4j_util.d4j_test_path_prefix(proj, bug_id)
    git_reset(repo_path)
    git_clean(repo_path)
    d4j_process = sp.run(['defects4j', 'export', '-p', 'dir.bin.tests'],
                          capture_output=True, cwd=repo_path)
    test_class_dir = d4j_process.stdout.decode()
    etc_info = ''
    
    # Running experiment for buggy version
    pretag = 'PRE_FIX_COMPILABLE' if injection else 'BUGGY_VERSION'
    cp = sp.run(['git', 'checkout', f'D4J_{proj}_{bug_id}_{pretag}'],
                cwd=repo_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    assert cp.returncode == 0
    buggy_results = []
    for example_test in example_tests:
        git_reset(repo_path)
        git_clean(repo_path)
        example_test = enforce_static_assertions(example_test)
        buggy_info = individual_run(proj, bug_id, example_test, injection)
        buggy_results.append(buggy_info)
    
    # Running experiment for fixed version
    git_reset(repo_path)
    git_clean(repo_path)
    posttag = 'POST_FIX_PRE_TEST_COMPILABLE' if injection else 'FIXED_VERSION'
    cp = sp.run(['git', 'checkout', f'D4J_{proj}_{bug_id}_{posttag}'],
                cwd=repo_path, capture_output=True)
    if cp.returncode != 0:
        cp = sp.run(['git', 'checkout', f'D4J_{proj}_{bug_id}_POST_FIX_REVISION'],
                cwd=repo_path, capture_output=True)
    assert cp.returncode == 0, f'{proj}-{bug_id}: {cp.stderr}'
    fixed_results = []
    for example_test in example_tests:
        git_reset(repo_path)
        if injection:
            git_clean(repo_path)
        example_test = enforce_static_assertions(example_test)
        fixed_info = individual_run(proj, bug_id, example_test, injection)
        fixed_results.append(fixed_info)
    
    # Matching results together
    final_results = []
    for buggy_info, fixed_info in zip(buggy_results, fixed_results):
        fails_in_buggy_version = any(map(lambda x: 'AutoGen' in x, buggy_info['failed_tests']))
        fails_in_fixed_version = any(map(lambda x: 'AutoGen' in x, fixed_info['failed_tests']))

        success = (fails_in_buggy_version and not fails_in_fixed_version)

        final_results.append({
            'buggy': buggy_info,
            'fixed': fixed_info,
            'success': success,
        })
    return final_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project', default='Time')
    parser.add_argument('-b', '--bug_id', type=int, default=18)
    parser.add_argument('-n', '--test_no', type=int, default=0)
    args = parser.parse_args()

    GEN_TEST_DIR = llm_exp_config['gen_tests_dir']['d4j']

    with open(os.path.join(GEN_TEST_DIR, f'{args.project}_{args.bug_id}_n{args.test_no}.txt')) as f:
        example_test = f.read()

    # example experiment execution
    print(twover_run_experiment(args.project, args.bug_id, [example_test]))
