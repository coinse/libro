from os import path
from common import *
from config import llm_exp_config
from collections import defaultdict
from tqdm import tqdm

import os
import re 
import glob
import shutil
import glob
import json

from ghrb_util import config, license_sslcontext_kickstart, fix_build_env, pit, split_project_bug_id

import subprocess as sp
import argparse

LIBRO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

BUG_LIST_PATH = f'{LIBRO_PATH}/data/GHRB/verified_bugs.json'

def needed_imports_and_asserts(repo_path, src_dir, gen_test, project_id):
    if 'sslcontext-kickstart' in repo_path:
        repo_path = os.path.dirname(repo_path)

    classpaths, needed_class_stubs, needed_asserts = needed_imports(
        repo_path, src_dir, gen_test)

    assertion_packages = []
    for assert_stub in needed_asserts:
        cp = sp.run(['grep', '-rh', r'import.*\.'+assert_stub+';', '.'],
                    capture_output=True, cwd=repo_path)
        example_paths = cp.stdout.decode('utf-8').split('\n')
        example_paths = [e.removeprefix('import ').removesuffix(';')
                         for e in example_paths]
        example_paths = [e for e in example_paths if len(e) > 0]
        if len(example_paths) == 0:
            if project_id == 'jsoup' or project_id == 'altindag.ssl' or project_id == 'checkstyle':
                assertion_packages.append(
                    f'static org.junit.jupiter.api.Assertions.{assert_stub}')
            else:
                assertion_packages.append(
                    f'static org.junit.Assert.{assert_stub}'
                )
        else:
            classpath = get_most_common_item(example_paths)
            assertion_packages.append(classpath)

    # needed class stubs are used for resolving already imported elements in the injection target class
    return classpaths, assertion_packages, needed_class_stubs


def enforce_static_assertions(gen_test):
    if 'Assert.' in gen_test:
        # force to use static assertion imports
        gen_test = gen_test.replace('Assert.fail', 'fail')
        gen_test = gen_test.replace('Assert.assert', 'assert')

    return gen_test


def inject_test(repo_path, test_prefix, gen_test, needed_elements, needed_class_stubs):
    """
    Overriding
    """
    needed_classpaths, needed_assert_packages = needed_elements

    best_path, best_file = get_best_test_class_for_injection(
        repo_path, test_prefix, gen_test)

    with open(best_path) as f:
        testf_lines = f.readlines()
        testf_content = ''.join(testf_lines)

    unhandled_imports = derive_unhandled_imports(
        testf_content, needed_classpaths + needed_assert_packages, needed_class_stubs)

    best_classpath = best_file.removeprefix(test_prefix).removesuffix('.java')
    best_classpath = best_classpath.replace('/', '.').strip('.')

    new_file_content, new_gen_test = inject_with_imports(
        best_classpath, testf_lines, gen_test, unhandled_imports)

    with open(best_path, 'w') as f:
        print(new_file_content, file=f)

    # Return name of test to execute
    test_name = f'{best_classpath}#'+parse_method(new_gen_test).name

    return test_name, new_file_content


def add_test(repo_path, test_prefix, gen_test, needed_elements, project_id):
    """
    Overriding
    """
    # import section
    if project_id == 'altindag.ssl':
        file_content = license_sslcontext_kickstart
    else:
        file_content = ''

    needed_classpaths, needed_asserts = needed_elements

    file_content += '/* Added by an automated tool. */\n'
    packages = map(lambda x: '.'.join(x.split('.')[:-1]), needed_classpaths)
    internal_packages = [k for k in packages if project_id.lower() in k]
    if len(internal_packages) > 0:
        test_package = get_most_common_item(internal_packages)
        file_content += f'package {test_package};\n\n'
    else:
        test_package = ''

    if project_id == 'jsoup' or project_id == 'altindag.ssl' or project_id == 'checkstyle':
        file_content += 'import org.junit.jupiter.api.Test;\n\n'
    else:
        file_content += 'import junit.framework.TestCase;\n\n'

    for ncp in needed_classpaths:
        ncp_package = '.'.join(ncp.split('.')[:-1])
        if ncp_package == test_package:
            continue  # already "imported"
        file_content += f'import {ncp};\n'

    for na in needed_asserts:
        file_content += f'import {na};\n'
    file_content += '\n'

    # TODO: check that test suite of the target project needs @Test annotation
    if project_id == 'jsoup' or project_id == 'altindag.ssl' or project_id == 'checkstyle':
        file_content += 'public class TestAutoGen {\n@Test\n'
    else:
        file_content += 'public class TestAutoGen extends TestCase {\n'
    file_content += gen_test.strip() + '\n'
    file_content += '}'

    if not SP_OUTPUT_SUPPRESS:
        print(file_content)

    # File content is complete, now write test file
    test_dir = path.join(repo_path, test_prefix,
                         test_package.replace('.', '/'))

    with open(f'{test_dir}/TestAutoGen.java', 'w') as f:
        print(file_content, file=f)

    if len(test_package) > 0:
        test_name = test_package + '.TestAutoGen#'+parse_method(gen_test).name
    else:
        test_name = 'TestAutoGen#'+parse_method(gen_test).name
    return test_name, file_content


def compile_repo(repo_path):
    compile_proc = sp.run(['mvn', 'clean', 'compile'],
                          cwd=repo_path, capture_output=True)

    if compile_proc.returncode != 0:
        return (False, {
            'stdout': compile_proc.stdout.decode('utf-8'),
            'stderr': compile_proc.stderr.decode('utf-8')
        })

    return (True, {})


def remove_file(rel_filepath, repo_path):
    cp = sp.run(['rm', rel_filepath],
                cwd=repo_path, capture_output=True)
    assert cp.returncode == 0, "removing {rel_filepath} in {repo_path} was failed"


def git_reset(repo_dir_path):
    sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def git_clean(repo_dir_path):
    sp.run(['git', 'clean', '-df'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def git_checkout(repo_path, commit_hash, version='buggy'):
    cp = sp.run(['git', 'checkout', commit_hash],
                cwd=repo_path, capture_output=True)
    assert cp.returncode == 0, f"checkout for {version} commit was not successful: {cp.stderr.decode()}"
    out = sp.run(['git', 'rev-parse', 'HEAD'],
                 cwd=repo_path, capture_output=True)
    assert commit_hash in out.stdout.decode(
    ), f"checkout for {version} commit {commit_hash} was not successful: current commit is {out.stdout.decode()}"


def git_staged_diffs(repo_path):
    cp = sp.run(['git', 'diff', '--staged', '--name-only', '--relative'],
                cwd=repo_path, capture_output=True)
    assert cp.returncode == 0, f"'git diff --staged --name-only' failed in {repo_path}"

    return cp.stdout.decode().splitlines()


def overwrite_test_code(repo_path, buggy_commit, test_dir='src/test/java'):
    # we need to synchronize test code (in merged version) same as the buggy version
    assert buggy_commit is not None
    p = sp.run(['rm', '-rf', test_dir], cwd=repo_path)
    assert p.returncode == 0
    p = sp.run(['git', 'checkout', buggy_commit,
                '--', test_dir], cwd=repo_path)
    assert p.returncode == 0


def run_test(repo_path, test_name, record={}, record_key='stdout'):
    fix_build_env(repo_path)
    run_command = ['timeout', '2m', 'mvn', 'test', '-Denforcer.skip=true',
                   f'-Dtest={test_name}']  # TODO: extend timeout for assertj
    if 'gson' in repo_path:
        run_command.extend(['-DfailIfNoTests=false'])
    if 'sslcontext' in repo_path:
        run_command.extend(['-pl', ":sslcontext-kickstart"])
    if 'checkstyle' in repo_path:
        run_command.extend(['-Djacoco.skip=true'])
    test_process = sp.run(run_command, capture_output=True, cwd=repo_path)

    captured_stdout = test_process.stdout.decode('utf-8')
    record[record_key] = captured_stdout

    if 'compilation failure' in captured_stdout.lower() or 'compilation error' in captured_stdout.lower():
        return -2, []

    if 'BUILD SUCCESS' in captured_stdout:
        return 0, []

    # if len(captured_stdout) == 0 or 'There are test failures' not in captured_stdout:
    if len(captured_stdout) == 0 or ('<<< FAILURE!' not in captured_stdout and '<<< ERROR!' not in captured_stdout):
        return -1, []  # no compile/test failures, but something went wrong

    failed_tests = []
    output_lines = captured_stdout.split('\n')

    for i, line in enumerate(output_lines):
        if 'AutoGen' in line and '<<< FAILURE!' in line and 'Failures:' not in line:
            failed_tests.append(line.split()[1])
        if 'AutoGen' in line and '<<< ERROR!' in line and 'Failures:' not in line:
            failed_tests.append(line.split()[1].split('(')[0])

    return 0, failed_tests


def get_test_execution_result(repo_path, test_name, file_content):
    record = {}
    status, failed_tests = run_test(
        repo_path, test_name, record=record, record_key='stdout')

    return {
        'compile_error': status == -2,
        'runtime_error': status == -1,
        'failed_tests': failed_tests,
        'autogen_failed': len(failed_tests) > 0,
        'testclass': (test_name, file_content),
        'stdout': record['stdout']
    }


def individual_run(repo_path, src_dir, test_prefix, example_test, project_id, injection):
    # example extraction of needed_classes
    classpaths, assertion_packages, needed_class_stubs = needed_imports_and_asserts(
        repo_path, src_dir, example_test, project_id)

    needed_elements = (classpaths, assertion_packages)

    # test class generation & addition
    if injection:
        test_name, file_content = inject_test(
            repo_path, test_prefix, example_test, needed_elements, needed_class_stubs)
    else:
        test_name, file_content = add_test(repo_path, test_prefix,
                                           example_test, needed_elements, project_id)

    return get_test_execution_result(repo_path, test_name, file_content)


def twover_run_experiment(repo_path, src_dir, test_prefix, example_tests, buggy_commit=None, fixed_commit=None, project_id=None, injection=True):
    buggy_results = []
    fib_tests = []
    fixed_results = []

    # Running experiment for buggy version
    git_reset(repo_path)
    git_clean(repo_path)

    git_checkout(repo_path, buggy_commit, version='buggy')
    fix_build_env(repo_path)
    compile_success, _ = compile_repo(repo_path)
    if not compile_success:
        raise Exception(
            "Source Code Compilation failed: {}".format(repo_path))

    for example_test in pit(example_tests, color='red'):
        git_reset(repo_path)
        git_clean(repo_path)  # this should not delete class files
        example_test = enforce_static_assertions(example_test)
        try:
            buggy_info = individual_run(
                repo_path, src_dir, test_prefix, example_test, project_id, injection)
        except Exception as e:
            buggy_info = f'[error] {repr(e)}'
        
        if isinstance(buggy_info, dict):
            if buggy_info['autogen_failed']:
                fib_tests.append(example_test)
        buggy_results.append(buggy_info)

    # Running experiment for fixed version
    git_reset(repo_path)
    git_clean(repo_path)

    git_checkout(repo_path, fixed_commit, version='fixed')
    fix_build_env(repo_path)
    compile_success, _ = compile_repo(repo_path)
    if not compile_success:
        raise Exception(
            "Source Code Compilation failed: {}".format(repo_path))

    for example_test in pit(example_tests, color='green'):
        if example_test not in fib_tests:
            fixed_results.append(None)
            continue

        git_reset(repo_path)
        git_clean(repo_path)  
        overwrite_test_code(repo_path, buggy_commit)
        example_test = enforce_static_assertions(example_test)
        try:
            fixed_info = individual_run(
            repo_path, src_dir, test_prefix, example_test, project_id, injection)
        except Exception as e:
            fixed_info = f'[error] {repr(e)}'

        if isinstance(fixed_info, dict):
            test_name, _ = fixed_info['testclass']
            index = example_tests.index(example_test)
            prev_test_name, _ = buggy_results[index]['testclass']

            if test_name != prev_test_name:
                raise AssertionError(
                    'Injected test class is different between buggy and fixed versions')

            if fixed_info['compile_error']:
                # retry by discarding changes in the test code
                test_name, file_content = fixed_info['testclass']
                injected_test_class = os.path.join(
                    test_prefix, test_name.split('#')[0].replace('.', '/') + '.java')

                changed_test_classes = git_staged_diffs(repo_path)
                for tc in changed_test_classes:
                    if tc != injected_test_class:
                        remove_file(tc, repo_path)

                fixed_info = get_test_execution_result(
                    repo_path, test_name, file_content)
        

        fixed_results.append(fixed_info)

    # Matching results together
    final_results = []
    assert len(buggy_results) == len(fixed_results)
    for buggy_info, fixed_info in zip(buggy_results, fixed_results):
        if isinstance(buggy_info, str): # Test is syntactically incorrect (JavaSyntaxError)
            final_results.append(buggy_info)
            continue

        if fixed_info is None:
            final_results.append({
                'buggy': buggy_info,
                'fixed': fixed_info,
                'success': False
            })
        else:
            fails_in_buggy_version = any(
                map(lambda x: 'AutoGen' in x, buggy_info['failed_tests']))

            fails_in_fixed_version = any(
                map(lambda x: 'AutoGen' in x, fixed_info['failed_tests']))
            test_executable_in_fixed_version = fixed_info[
                'compile_error'] == False and fixed_info['runtime_error'] == False
            success = (
                fails_in_buggy_version and not fails_in_fixed_version and test_executable_in_fixed_version)

            final_results.append({
                'buggy': buggy_info,
                'fixed': fixed_info,
                'success': success
            })

    return final_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project', default='google_gson')
    parser.add_argument('-b', '--bug_id', default=2134)
    parser.add_argument('-n', '--test_no', type=int, default=None)
    parser.add_argument('--gen_test_dir', default='/root/data/GHRB/gen_tests/')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--exp_name', default='example2_n50_ghrb')
    args = parser.parse_args()

    with open(BUG_LIST_PATH) as f:
        data = json.load(f)

    GEN_TEST_DIR = args.gen_test_dir

    if args.all:
        assert args.project is not None # target project should be set 
        
        bug2tests = defaultdict(list)

        for gen_test_file in glob.glob(os.path.join(GEN_TEST_DIR, '*.txt')):
            bug_key = '_'.join(os.path.basename(gen_test_file).split('_')[:-1])
            project, bug_id = split_project_bug_id(bug_key)
            if project != args.project:
                continue

            bug2tests[bug_key].append(gen_test_file)

        exec_results = {}
        for bug_key, tests in tqdm(bug2tests.items()):
            project, bug_id = split_project_bug_id(bug_key)
            bug_id = int(bug_id)
            res_for_bug = {}

            example_tests = []
            for test_file in tests:
                with open(test_file) as f:
                    example_tests.append(f.read())

            repo_path = config[project]['repo_path']
            src_dir = config[project]['src_dir']
            test_prefix = config[project]['test_prefix']
            project_name = config[project]['project_name']
            project_id = config[project]['project_id']

            target_bug = data[f'{project}-{bug_id}']
            bug_no = target_bug['PR_number']
            buggy_commit = target_bug['buggy_commits'][0]['oid']
            fixed_commit = target_bug['merge_commit']

            results = twover_run_experiment(repo_path, src_dir, test_prefix, example_tests, buggy_commit, fixed_commit, project_id)

            for test_path, res in zip(tests, results):
                res_for_bug[os.path.basename(test_path)] = res
            exec_results[bug_key] = res_for_bug

            with open(f'{LIBRO_PATH}/results/{args.exp_name}_{args.project}.json', 'w') as f:
                json.dump(exec_results, f, indent=4)

    elif args.test_no is None:
        test_files = glob.glob(os.path.join(GEN_TEST_DIR, f'{args.project}_{args.bug_id}_*.txt'))
        example_tests = []
        res_for_bug = {}

        for gen_test_file in test_files:
            with open(gen_test_file) as f:
                example_tests.append(f.read())

        repo_path = config[args.project]['repo_path']
        src_dir = config[args.project]['src_dir']
        test_prefix = config[args.project]['test_prefix']
        project_name = config[args.project]['project_name']
        project_id = config[args.project]['project_id']

        target_bug = data[f'{args.project}-{args.bug_id}']
        bug_no = target_bug['PR_number']
        buggy_commit = target_bug['buggy_commits'][0]['oid']
        fixed_commit = target_bug['merge_commit']

        results = twover_run_experiment(repo_path, src_dir, test_prefix, example_tests, buggy_commit, fixed_commit, project_id)
        
        for test_path, res in zip(test_files, results):
            res_for_bug[os.path.basename(test_path)] = res

        with open(f'{LIBRO_PATH}/results/{args.exp_name}_{args.project}_{args.bug_id}.json', 'w') as f:
            json.dump(res_for_bug, f, indent=4)

    else:
        with open(os.path.join(GEN_TEST_DIR, f'{args.project}_{args.bug_id}_markdown_n{args.test_no}.txt')) as f:
            example_test = f.read()

        repo_path = config[args.project]['repo_path']
        src_dir = config[args.project]['src_dir']
        test_prefix = config[args.project]['test_prefix']
        project_name = config[args.project]['project_name']
        project_id = config[args.project]['project_id']

        target_bug = data[f'{args.project}-{args.bug_id}']
        bug_no = target_bug['PR_number']
        buggy_commit = target_bug['buggy_commits'][0]['oid']
        fixed_commit = target_bug['merge_commit']

        # example experiment execution
        print(twover_run_experiment(repo_path, src_dir, test_prefix, [example_test], buggy_commit, fixed_commit, project_id))
