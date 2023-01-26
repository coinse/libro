# LIBRO: LLM Induced Bug Reproduction


This repository contains the replication package of **Large Language Models are Few-shot Testers: Exploring LLM-based General Bug Reproduction** (to appear in ICSE 2023, [preprint available in arXiv](https://arxiv.org/abs/2209.11515))

![](https://coinse.kaist.ac.kr/assets/images/blog/libro_overview.png)

Simply put, LIBRO accepts a bug report and an existing test suite as input, and produces a ranked list of bug-reproducing test candidates.

## Setting up LIBRO 
* [Docker](https://docs.docker.com/get-docker/) is required to set up the environment for LIBRO. 

### Option 1: Pull Docker image
```bash 
docker pull greenmon/libro-env
sh run_docker_container.sh
```

The pulled Docker image has the `/tmp` directory and Python requirements installed, but the Java version may still need to be adjusted (see below).

### Option 2: Build Docker image from scratch
Build the Docker image with the Defects4J framework and proper Java/Python versions installed, then run the script `run_docker_container.sh` to run the container and attach to it.
```bash 
cd docker
docker build -t libro-env .
sh run_docker_container.sh
```

Inside the container:
```bash
wget https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz -P /tmp # for running projects in GHRB benchmark
tar -xzvf /tmp/apache-maven-3.8.6-bin.tar.gz -C /opt

git config --global --add safe.directory '*'

cd workspace
pip install -r requirements.txt
```

Additionally, the proper Java version should be set according depending on the benchmark to evaluate on. For example, when running Defects4J, Java version 8 is required. To switch between Java versions, use the command `update-alternatives --config java` inside the container:
```
  Selection    Path                                            Priority   Status
------------------------------------------------------------
  0            /usr/lib/jvm/java-17-openjdk-amd64/bin/java      1711      auto mode
  1            /usr/lib/jvm/java-11-openjdk-amd64/bin/java      1111      manual mode
  2            /usr/lib/jvm/java-17-openjdk-amd64/bin/java      1711      manual mode
* 3            /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java   1081      manual mode
```

### Prepare Defects4J dataset and LLM-generated tests
> To accomplish this step, JDK version should be set to 8
1. Download LLM-generated tests for the versions ([link](https://figshare.com/s/aba0a7465f04ce45ba55))
    * `d4j-gen-tests.tar.gz`: generated tests by Codex used in our evaluation

Alternatively, within the Docker container, use the command
```bash
wget -O d4j-gen-tests.tar.gz https://figshare.com/ndownloader/files/37007956?private_link=aba0a7465f04ce45ba55
```


2. Extract LLM-generated test files in `d4j-gen-tests.tar.gz` to the path of `/root/data/Defects4J/gen_tests` *(This step may be skipped if the intent is to evaluate on different tests.)*

3. Checkout Defects4J versions; for example,
```bash
defects4j checkout -p Time -v 18b -w /root/data/Defects4J/repos/Time_18
# defects4j checkout -p [project] -v [bid]b -w /root/data/Defects4J/repos/[project]_[bid]
```

To checkout all Defects4J versions, run the provided `checkout_d4j.sh` script, as provided below. Note that checking out all versions may take a significant amount of time.
```bash
cd /root/scripts
bash checkout_d4j.sh
```

After performing `checkout` on all desired bugs, run the following scripts to add "compilable" snapshots from Defects4J prefix/postfix commits:
```bash 
cd /root/data/Defects4J
bash tag_pre_fix_compilable.sh
bash tag_post_fix_compilable.sh
```

### Prepare GHRB dataset and LLM-generated tests
1. Download all cloned target Java repositories and LLM-generated tests from this [link](https://figshare.com/s/de40ea0a3dea94560e84), which contains the following files:
    * `ghrb-repos.tar.gz`: project repositories used in evaluation
    * `ghrb-gen-tests.tar.gz`: generated tests by Codex used in evaluation

Alternatively, within the Docker container, use the commands
```bash
wget -O ghrb-repos.tar.gz https://figshare.com/ndownloader/files/37005352?private_link=de40ea0a3dea94560e84
wget -O ghrb-gen-tests.tar.gz https://figshare.com/ndownloader/files/37005343?private_link=de40ea0a3dea94560e84
```

2. Extract `ghrb-repos.tar.gz` and locate the contained repositories (e.g., `assertj-core`) to the directory `/root/data/GHRB/repos`.
    
3. Extract files (.txt) in `ghrb-gen-tests.tar.gz` to the path of `/root/data/GHRB/gen_tests` *(This step may be skipped if the intent is to evaluate on different tests.)*

## Running LIBRO
We provide instructions to run LIBRO to verify that the package works. We recommend performing the following steps on a single bug (in this README, the running example is the Time-18 bug from Defects4J) to verify that the package works.

 1. (Optional) [Prompt LLM for test generation](#prompt-llm-to-generate-test)
 2. [Get execution results for tests](#get-execution-results-for-generated-tests)

For full replication of our results, one may [run LIBRO on all bugs](#collect-full-experiment-data) in the benchmark. The reader is cautioned that this can take a significant amount of time.

### Prompt LLM to generate test
> This step is optional, and provided for the ease of additional test generation via LLMs. Skip this step if the intent is to reproduce the results of the paper.

First, set the OpenAI API key by edit `env.list` file with your OpenAI API secret key.
```
OPENAI_API_KEY=<your_own_openai_api_key>
```

Next, use the Python script `llm_query.py` to prompt LLM to generate a reproducing test from a bug report. 
```bash
# For the Defects4J benchmark
python llm_query.py -d d4j -p Time -b 18 --out output.txt

# For the GHRB benchmark
python llm_query.py -d ghrb -p assertj_assertj-core -b 2324 --out output.txt
```

To see all available projects and bug IDs contained in each benchmark, check the `data/Defects4J/bug_report` and `data/GHRB/bug_report` directories.

### Get execution results for generated tests
#### Defects4J
Run `postprocess_d4j.py` to postprocess the LLM-generated tests and get evaluation results.
```bash
python postprocess_d4j.py -p Time -b 18 -n 0 
```
The command runs the 1st generated test from the Time-18 bug of Defects4J and gets execution results from both the buggy and fixed version of Time-18. As a result of the script, the test execution results on the buggy and fixed versions should be provided, along with a `'success'` value, which is `True` when the test failed on the buggy version but passed on the fixed version. For example, the following is the expected output of the command above.

```
[{'buggy': {'compile_error': False, 'runtime_error': False, 'failed_tests': ['org.joda.time.TestTimeOfDay_Constructors::testIssue130AutoGen'], 'autogen_failed': True, 'fib_error_msg': '--- org.joda.time.TestTimeOfDay_Constructors::testIssue130AutoGen\norg.joda.time.IllegalFieldValueException: Value 29 for dayOfMonth must be in the range [1,28]\n\tat org.joda.time.field.FieldUtils.verifyValueBounds(FieldUtils.java:233)\n\tat org.joda.time.chrono.BasicChronology.getDateMidnightMillis(BasicChronology.java:605)\n\tat org.joda.time.chrono.BasicChronology.getDateTimeMillis(BasicChronology.java:177)\n', 'compile_msg': None}, 'fixed': {'compile_error': False, 'runtime_error': False, 'failed_tests': [], 'autogen_failed': False, 'fib_error_msg': None, 'compile_msg': None}, 'success': True}]
```

#### GHRB
For the GHRB benchmark, select the appropriate Java version for each project.
* `google_gson`: JDK 11 (`java-11-openjdk-amd64` installed in the container)
* `assertj_assertj-core`, `FasterXML_jackson-core`, `FasterXML_jackson-databind`, `jhy_jsoup`, `Hakky54_sslcontext-kickstart`, `checkstyle_checkstyle`: JDK 17 (`java-17-openjdk-amd64`)

Run `postprocess_d4j.py` to postprocess the LLM-generated tests and get evaluation results. Below, we provide the instructions for reproducing the bug reported the Google `gson` project at pull request #2134.
```bash
update-alternatives --config java # set Java version to 11 (17 for other GHRB projects)
source /root/data/GHRB/set_env_gson.sh # use /root/data/GHRB/set_env.sh for other projects
python postprocess_ghrb.py -p google_gson -b 2134 -n 32 
```
The command runs the 33rd generated test from the bug report associated `gson` PR #2134, and gets execution results from both the pre-merge and post-merge versions of `gson`.

Execution results are in a similar format as the Defects4J benchmark. For example, the following is the expected output of the command above:
```
[{'buggy': {'compile_error': false, 'runtime_error': false, 'failed_tests': ['com.google.gson.internal.bind.util.ISO8601UtilsTest.testIssue108AutoGen'],'autogen_failed': true,,'fib_error_msg': ['java.lang.AssertionError: Should\'ve thrown exception\n', '\tat org.junit.Assert.fail(Assert.java:89)\n','\tat com.google.gson.internal.bind.util.ISO8601UtilsTest.testIssue108AutoGen(ISO8601UtilsTest.java:100)\n'], 'exception_type': 'java.lang.AssertionError', 'value_matching': null, 'failure_message': 'java.lang.AssertionError: Should\'ve thrown exception'},[...]},'success': true}]
```


### Collect full experiment data 
For the purpose of completely reproducing our experiments and results, the following commands may be run. **These commands can take a significant amount of time to complete**: for example, the Defects4J reproduction process took more than 100 hours to complete on our machine.
#### Defects4J 
```bash
python postprocess_d4j.py --all --exp_name example2_n50_replicate
# generates aggregated execution results as a file `results/example2_n50_replicate.json`
```

#### GHRB
For GHRB benchmark, the target project must be set (with `-p`, or `--project` option) to run all bugs from the project *(Only project-wise execution is supported because of dependencies to different Java versions.)*
```bash
update-alternatives --config java # set Java version to 11 (17 for other GHRB projects)
source /root/data/GHRB/set_env_gson.sh 
# source /root/data/GHRB/set_env.sh (for other projects)
python postprocess_ghrb.py -p google_gson --all --exp_name example2_n50_ghrb_replicate 
# generates aggregated execution results as a file `results/example2_n50_ghrb_replicate_google_gson.json`
```

### Get selection and ranking results
With all execution results collected, the selection and ranking results may be obtained with the following command.
```bash 
python selection_and_ranking.py -d Defects4J -f ../results/example2_n50_replicate.json # from Defects4J execution results
```

## Replicating evaluation results in paper
* You can replicate results in the paper using the Jupyter notebooks inside `notebooks` folder:
    * **Replicate_Motivation:** Replicates our results in Sec. 2
    * **Replicate_RQ1:** Replicates Table 3, 4 used to answer RQ1.
    * **Replicate_RQ2:** Replicates Figure 2, 3, 4, and Table 6 used to answer RQ2.
    * **Replicate_RQ3:** Replicates Figure 5 used to answer RQ3.

