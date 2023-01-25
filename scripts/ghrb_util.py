import os
import re
import glob
import subprocess
import shlex
import enlighten


config = {
    'google_gson': {
        'repo_path': '/root/data/GHRB/repos/gson/gson/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'google_gson',
        'project_id': 'gson'
    },
    'assertj_assertj-core': {
        'repo_path': '/root/data/GHRB/repos/assertj-core/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'assertj_assertj-core',
        'project_id': 'assertj'
    },
    'FasterXML_jackson-core': {
        'repo_path': '/root/data/GHRB/repos/jackson-core/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'FasterXML_jackson-core',
        'project_id': 'jackson.core'
    },
    'FasterXML_jackson-databind': {
        'repo_path': '/root/data/GHRB/repos/jackson-databind/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'FasterXML_jackson-databind',
        'project_id': 'jackson.databind'
    },
    'jhy_jsoup': {
        'repo_path': '/root/data/GHRB/repos/jsoup/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'jhy_jsoup',
        'project_id': 'jsoup'
    },
    'Hakky54_sslcontext-kickstart': {
        'repo_path': '/root/data/GHRB/repos/sslcontext-kickstart/sslcontext-kickstart/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'Hakky54_sslcontext-kickstart',
        'project_id': 'altindag.ssl'
    },
    'checkstyle_checkstyle': {
        'repo_path': '/root/data/GHRB/repos/checkstyle/',
        'src_dir': 'src/main/java/',
        'test_prefix': 'src/test/java/',
        'project_name': 'checkstyle_checkstyle',
        'project_id': 'checkstyle'
    }
}

license_sslcontext_kickstart = '''
/*
 * Copyright 2019-2022 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
'''


properties_to_replace = {
    'jackson-core': {
        r'<javac.src.version>\s*1.6\s*</javac.src.version>': '',
        r'<javac.target.version>\s*1.6\s*</javac.target.version>': '',
        r'<maven.compiler.source>\s*1.6\s*</maven.compiler.source>': '<maven.compiler.source>11</maven.compiler.source>',
        r'<maven.compiler.target>\s*1.6\s*</maven.compiler.target>': '<maven.compiler.target>11</maven.compiler.target>',
    },
    'jackson-databind': {
        r'<version>\s*2.13.0-rc1-SNAPSHOT\s*</version>': '<version>2.14.0-SNAPSHOT</version>',
        r'<source>\s*14\s*</source>': '<source>17</source>',
        r'<release>\s*14\s*</release>': '<release>17</release>',
        r'<id>\s*java17\+\s*</id>': '<id>java17+</id>',
        r'<jdk>\s*\[17\,\)\s*</jdk>': '<jdk>[17,)</jdk>'
    }
}

def split_project_bug_id(bug_key):
    s = bug_key.split('_')
    project = '_'.join(s[:-1])
    bug_id = s[-1]

    return project, bug_id


def fix_build_env(repo_dir_path):
    if 'jackson-core' in repo_dir_path or 'jackson-databind' in repo_dir_path:
        pom_file = os.path.join(repo_dir_path, 'pom.xml')

        with open(pom_file, 'r') as f:
            content = f.read()

        if 'jackson-core' in repo_dir_path:
            replace_map = properties_to_replace['jackson-core']
        elif 'jackson-databind' in repo_dir_path:
            replace_map = properties_to_replace['jackson-databind']

        for unsupported_property in replace_map:
            content = re.sub(
                unsupported_property, replace_map[unsupported_property], content)

        with open(pom_file, 'w') as f:
            f.write(content)


def pit(it, *pargs, **nargs):
    # https://stackoverflow.com/questions/23113494/double-progress-bar-in-python

    global __pit_man__
    try:
        __pit_man__
    except NameError:
        __pit_man__ = enlighten.get_manager()
    man = __pit_man__
    try:
        it_len = len(it)
    except:
        it_len = None
    try:
        ctr = None
        for i, e in enumerate(it):
            if i == 0:
                ctr = man.counter(
                    *pargs, **{**dict(leave=False, total=it_len), **nargs})
            yield e
            ctr.update()
    finally:
        if ctr is not None:
            ctr.close()
