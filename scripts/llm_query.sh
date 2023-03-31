#!/bin/bash

bug_report_path="/root/data/Defects4J/bug_report"

# get the bug id
# Chart-1.json => p=Chart, v=1
for file in `ls $bug_report_path`
do
    p=`echo $file | cut -d'-' -f1`
    v=`echo $file | cut -d'-' -f2 | cut -d'.' -f1`
    echo "p=$p, v=$v"
    # repeat 0 times
    for i in `seq 1 10`
    do
        python3.9 llm_query.py -p $p -b $v --out /root/data/Defects4J/gen_tests_gpt3.5/${p}_${v}_n${i}.txt
    done

done