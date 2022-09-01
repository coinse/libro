import glob
import os
import html
import json
import datetime
import pandas as pd
import subprocess 
import shlex
import shutil

from bs4 import BeautifulSoup

from collections import defaultdict
from dateutil import parser
from util import *

test_dir = 'src/test/java/'

def extract_test_diff(cleaned_data):
    shutil.rmtree('test_diff')
    os.makedirs('test_diff')

    new_cleaned_data = {}

    for repo_name in cleaned_data:
        if repo_name not in repo_path_map:
            continue

        new_cleaned_data[repo_name] = {}
        
        for bug_id, bug_info in cleaned_data[repo_name].items():
            merge_commit = bug_info['merge_commit']
            buggy_commits = [c['oid'] for c in bug_info['buggy_commits']]

            selected_buggy_commit = None
            diff = None
            # 1. get diff using buggy commit and fixed commit (after merge)
            for buggy_commit in buggy_commits:
                p = subprocess.run(shlex.split(f'git diff {buggy_commit} {merge_commit} -- {test_dir}'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=repo_path_map[repo_name])

                diff = p.stdout.decode()
                error_msg = p.stderr.decode()

                if len(error_msg) > 0:
                    if merge_commit in error_msg:
                        # maybe the commit is not belonged to any currently existing branches.. than just force to download that commit!
                        p = subprocess.run(shlex.split(f'git fetch origin {merge_commit}'), stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=repo_path_map[repo_name])
                    elif buggy_commit in error_msg:
                        p = subprocess.run(shlex.split(f'git fetch origin {buggy_commit}'), stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=repo_path_map[repo_name])

                    p = subprocess.run(shlex.split(f'git diff {buggy_commit} {merge_commit} -- {test_dir}'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=repo_path_map[repo_name])

                    diff = p.stdout.decode()
                    error_msg = p.stderr.decode()

                if len(diff.strip()) > 0 and len(error_msg) == 0:
                    selected_buggy_commit = buggy_commit
                    break

            if selected_buggy_commit is None:
                print(f'Failed to find target test suite change for {bug_id}')
                continue
            else:
                new_cleaned_data[repo_name][bug_id] = bug_info


            with open('test_diff/{}.diff'.format(bug_info['bug_id']), 'w') as f:
                f.write(diff)

            new_cleaned_data[repo_name][bug_id]['buggy_commit'] = selected_buggy_commit


    repo_w_no_data = []
    for repo_name in new_cleaned_data:
        if len(new_cleaned_data[repo_name]) == 0:
            repo_w_no_data.append(repo_name)
    for repo_name in repo_w_no_data:
        del new_cleaned_data[repo_name]

    return new_cleaned_data


def filter_out_unmerged_and_uncertain_issue_mapping(filtered_PRs):
    cleaned_data = defaultdict(dict)

    for repo_name in filtered_PRs:
        for pr_data in filtered_PRs[repo_name]:
            pr_data = pr_data['repository']['pullRequest']
            bug_id = f'{repo_name}-{pr_data["number"]}'

            changed_test_files = [node['node']['path'] for node in pr_data['files']['edges'] if 'test' in node['node']['path'].lower() and node['node']['path'].endswith('.java')]
            closing_issues = [node['node'] for node in pr_data['closingIssuesReferences']['edges']]

            if len(closing_issues) != 1:
                continue # discard these PRs

            closing_issue = closing_issues[0]

            merge_commit_url = pr_data['mergeCommit']['commitUrl'] if pr_data['mergeCommit'] else None
            merge_commit = pr_data['mergeCommit']['oid'] if pr_data['mergeCommit'] else None
            parents = pr_data['mergeCommit']['parents']['nodes'] if pr_data['mergeCommit'] else None

            if merge_commit_url is None:
                merge_commit_url = pr_data['potentialMergeCommit']['commitUrl'] if pr_data['potentialMergeCommit'] else None
                merge_commit = pr_data['potentialMergeCommit']['oid'] if pr_data['potentialMergeCommit'] else None
                parents = pr_data['potentialMergeCommit']['parents']['nodes'] if pr_data['potentialMergeCommit'] else None


            if merge_commit_url is None:
                continue
            
            if 'checkstyle' in bug_id and 'fix' not in pr_data['title'].lower():
                continue # checkstyle has many test changes which are not actully fixes, so additionally filter them out

            with open(f'collected_issues/{repo_name}-{pr_data["number"]}.json', 'w') as f:
                description = html.unescape(closing_issue['bodyHTML'])
                json.dump({
                    'issue_id': closing_issue['number'],
                    'issue_url': closing_issue['url'],
                    'title': closing_issue['title'],
                    'description': description,
                    'description_text': BeautifulSoup(description, 'html.parser').get_text(),
                }, f, indent=2)
            
            closing_issue = {
                'url': closing_issues[0]['url'],
                'createdAt': closing_issues[0]['createdAt'],
                'content': f'bug_report_all/{repo_name}-{pr_data["number"]}.json',
            }

            cleaned_data[repo_name][bug_id] = {
                'bug_id': f'{repo_name}-{pr_data["number"]}',
                'PR_number': pr_data['number'],
                'PR_createdAt': pr_data['createdAt'],
                'merge_commit': merge_commit,
                'buggy_commits': parents,
                'issue': closing_issue,
                'changed_tests': changed_test_files,
                'PR_url': pr_data['url'],
                'merge_commit_url': merge_commit_url,
            }

    return cleaned_data

def filter_out_PRs_wo_new_tests(filtered_PRs):
    filtered_PRs_w_changed_test = defaultdict(list)
    for repo_name in filtered_PRs:
        for pr_data in filtered_PRs[repo_name]:
            changed_files = [node['node']['path'] for node in pr_data['repository']['pullRequest']['files']['edges']]

            if contains_test_in_paths(changed_files):
                filtered_PRs_w_changed_test[repo_name].append(pr_data)


    print(f'{sum([len(filtered_PRs_w_changed_test[repo]) for repo in filtered_PRs])} PRs found with new tests introduced in fix')
    return filtered_PRs_w_changed_test


def filter_out_old_PRs(datapath='raw_data'):
    """
    Filter out PRs before June 2021 (Codex training data cutoff point)
    """
    consider_bug_label = False 
    collected_PRs = {}

    for repo_data in glob.glob(os.path.join(datapath, '*.json')):
        repo_name = os.path.basename(repo_data).replace('.json', '')
        with open(repo_data) as f:
            collected_PRs[repo_name] = json.load(f)

    print(f'# of Original collected PRs: {sum([len(collected_PRs[repo]) for repo in collected_PRs])}')

    filtered_PRs = defaultdict(list)
    for repo_name in collected_PRs:
        for pr_data in collected_PRs[repo_name]:
            issues = pr_data['repository']['pullRequest']['closingIssuesReferences']['edges']
            assert len(issues) > 0

            created_at = parser.parse(pr_data['repository']['pullRequest']['createdAt'])

            if created_at.replace(tzinfo=None) >= datetime.datetime(2021, 7, 1).replace(tzinfo=None):
                filtered_PRs[repo_name].append(pr_data)

    print(f'{sum([len(filtered_PRs[repo]) for repo in filtered_PRs])} PRs after filtering old ones')

    return filtered_PRs

if __name__ == "__main__":
    filtered_PRs = filter_out_old_PRs(datapath='raw_data')
    filtered_PRs = filter_out_PRs_wo_new_tests(filtered_PRs)
    cleaned_data = filter_out_unmerged_and_uncertain_issue_mapping(filtered_PRs)
    new_cleaned_data = extract_test_diff(cleaned_data) # we can only use bug where we can extract the test diff

    not_bug_reports = {
        "Hakky54_sslcontext-kickstart" : ['Hakky54_sslcontext-kickstart-203', 'Hakky54_sslcontext-kickstart-122']
    } # manually discards empty issue, feature requests, etc.

    for repo_name, bug_ids in not_bug_reports.items():
        for bug_id in bug_ids:
            del new_cleaned_data[repo_name][bug_id]

    with open('report_test_mappings.json', 'w') as f:
        json.dump(new_cleaned_data, f, indent=2)

    print([f'{repo_name}: {len(new_cleaned_data[repo_name])}' for repo_name in new_cleaned_data])
