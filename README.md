# Artifact for Large Language Models are Few-shot Testers: Exploring LLM-based General Bug Reproduction


## To replicate results in paper
* **Replicate_Motivation:** Replicates our results in Sec. 2
* **Replicate_RQ1:** Replicates Table 3, 4 used to answer RQ1.
* **Replicate_RQ2:** Replicates Figure 2, 3, 4, and Table 6 used to answer RQ2.
* **Replicate_RQ3:** Replicates Figure 5 used to answer RQ3.

## Running bug reproducing test generation
To obtain bug reproducing tests and their execution results from LIBRO's test generation pipeline, you need some more environment setup (+ access for OpenAI Codex):

### Prerequisite
* Defects4J framework: https://github.com/rjust/defects4j
* Python 3.9.10
* Python requirements: `pip install -r requirements.txt`
* JDK versions required from GHRB projects: `JDK 11` (for `google/gson`), `JDK 17` (for other projects), `Apache Maven 3.8.6`


### Query an LLM
* To directly query LLM (e.g., Codex): OPENAI_API_KEY and D4J_HOME environment variables should be set, via such commands:

```bash
export OPENAI_API_KEY=xxx 

export D4J_HOME=/home/[...]/defects4j
```

* Use the script `llm_query.py` to prompt LLM to generate a reproducing test from a bug report. 
```bash
python llm_query.py -d d4j -p Time -b 23 --out output.txt
```

### Defects4J bug reproduction
1. Checkout Defects4J versions using the command `defects4j checkout -p [project] -v [bid]b -w data/Defects4J/repos/[project]_[bid]`, and run the provided scripts:
```bash 
cd data/Defects4J
sh tag_pre_fix_compilable.sh
sh tag_post_fix_compilable.sh
```
This scripts additionally construct "compilable" tags of the original pre- and post-fix versions (sometimes are not compilable).


2. Download LLM-generated tests for the versions ([link](https://figshare.com/s/aba0a7465f04ce45ba55))
    * `d4j-gen-tests.tar.gz`: generated tests by Codex used in our evaluation

3. Locate the versions (e.g., `Chart_1`) into the directory `data/Defects4J/repos`.

4. Locate LLM-generated tests in `data/Defects4J/gen_tests` downloaded or generated from your own query (the tests should have the same namings with the provided ones)

5. Run `postprocess_d4j.py` to postprocess the target LLM-generated test and get execution results in buggy and fixed versions.
```bash
python postprocess_d4j.py -p Time -b 18 -n 0 
```
The command basically runs 0th generated test from Time-18 bug report and get execution results from both buggy and fixed version of Time-18. As a result, you can obtain both buggy and fixed version execution results of the test.

```
[{'buggy': {'compile_error': False, 'runtime_error': False, 'failed_tests': ['org.joda.time.TestTimeOfDay_Constructors::testIssue130AutoGen'], 'autogen_failed': True, 'fib_error_msg': '--- org.joda.time.TestTimeOfDay_Constructors::testIssue130AutoGen\norg.joda.time.IllegalFieldValueException: Value 29 for dayOfMonth must be in the range [1,28]\n\tat org.joda.time.field.FieldUtils.verifyValueBounds(FieldUtils.java:233)\n\tat org.joda.time.chrono.BasicChronology.getDateMidnightMillis(BasicChronology.java:605)\n\tat org.joda.time.chrono.BasicChronology.getDateTimeMillis(BasicChronology.java:177)\n', 'compile_msg': None}, 'fixed': {'compile_error': False, 'runtime_error': False, 'failed_tests': [], 'autogen_failed': False, 'fib_error_msg': None, 'compile_msg': None}, 'success': True}]
```

### GHRB bug reproduction
1. Download all cloned target Java repositories and LLM-generated tests from this [link](https://figshare.com/s/de40ea0a3dea94560e84)
    * `ghrb-repos.tar.gz`: project repositories used in our evaluation
    * `ghrb-gen-tests.tar.gz`: generated tests by Codex used in our evaluation

2. Locate the repositories (e.g., `assertj-core`) inside the directory `data/GHRB/repos`.
    

3. Locate LLM-generated tests in `data/GHRB/gen_tests` downloaded or generated from your own query (the tests should have the same namings with the provided ones)

4. Set proper Java version: `JDK 11` for `google_gson` project, and `JDK 17` for other projects. Refer to the files `data/GHRB/set_env.sh` and `data/GHRB/set_env_gson.sh`.

4. Run `postprocess_ghrb.py` to postprocess the target LLM-generated test and get execution results in buggy and fixed versions.
```bash
python postprocess_ghrb.py -p google_gson -b 2134 -n 32 
```
The command runs 32th generated test from the bug report associated with the google_gson PR #2134, and get execution results from both pre-merge and post-merge version of google_gson.

Execution results are similar form with those in Defects4J:
```
[{'buggy': {'compile_error': false, 'runtime_error': false, 'failed_tests': ['com.google.gson.internal.bind.util.ISO8601UtilsTest.testIssue108AutoGen'],'autogen_failed': true,,'fib_error_msg': ['java.lang.AssertionError: Should\'ve thrown exception\n', '\tat org.junit.Assert.fail(Assert.java:89)\n','\tat com.google.gson.internal.bind.util.ISO8601UtilsTest.testIssue108AutoGen(ISO8601UtilsTest.java:100)\n'], 'exception_type': 'java.lang.AssertionError', 'value_matching': null, 'failure_message': 'java.lang.AssertionError: Should\'ve thrown exception'},[...]},'success': true}]
```