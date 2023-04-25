#!/usr/bin/env python
# coding: utf-8

import os
import re
import json
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from config import llm_exp_config
import argparse

from llm_api import model_is_chat, query_llm

TEMPLATE_DIR = llm_exp_config['template_dir']
BR_DIR = llm_exp_config['bug_report_dir']['d4j']

def make_messages_from_file(rep_title, rep_content,
                          template_file=TEMPLATE_DIR+'2example_chat.json'):
    rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
    rep_content = md(rep_content.strip())

    with open(template_file) as f:
        messages = json.load(f)

        for msg in messages:
            example_text_path = re.findall(r'{%(.+?)%}', msg['content'])
            if len(example_text_path) > 0:
                for ef in example_text_path:

                    with open(os.path.join(TEMPLATE_DIR, ef)) as f:
                        example_text = f.read()
                    msg['content'] = msg['content'].replace('{%'+ef+'%}', example_text)

        current_query = messages[-1]['content']
        bug_report_content = f"""
        # {rep_title}
        ## Description
        {rep_content}
        """
        current_query = current_query.replace('{{bug_report_content}}', bug_report_content)

        messages[-1]['content'] = current_query

    return messages, None

def make_prompt_from_file(rep_title, rep_content,
                          use_plain_text, use_html,
                          template_file=TEMPLATE_DIR+'PL.txt'):
    # only a single option should be activated
    assert not (use_plain_text and use_html)

    if use_plain_text:
        rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
        rep_content = BeautifulSoup(
            rep_content.strip(), 'html.parser').get_text()
    elif not use_html:  # markdown (default)
        rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
        rep_content = md(rep_content.strip())

    with open(template_file) as f:
        template_str = f.read()
        prompt = template_str.replace('{{title}}', rep_title.strip())
        prompt = prompt.replace('{{content}}', rep_content.strip())
        nonempty_lines = [e for e in template_str.split('\n') if len(e) != 0]
        last_line = nonempty_lines[-1]
        prompt = prompt.strip().removesuffix(last_line).strip()
        end_string = last_line.removeprefix('{{endon}}:').strip()

    return prompt, [end_string]


def query_llm_for_gentest(proj, bug_id, model, template, use_plain_text=False, use_html=False, save_prompt=False, prompt_save_path=None):
    with open(BR_DIR + proj + '-' + str(bug_id) + '.json') as f:
        br = json.load(f)
    chat_mode = model_is_chat(model)

    if chat_mode:
        prompt, stop = make_messages_from_file(
            br['title'], br['description'],
            template_file=TEMPLATE_DIR+f'{template}.json')
    else:
        # handle exceptional cases in 2022-jsoup
        use_html = ('description_fixed' in br) or use_html
        use_plain_text = ('description_fixed' not in br) and use_plain_text
        desc_key = 'description_fixed' if 'description_fixed' in br else 'description'

        prompt, stop = make_prompt_from_file(
            br['title'], br[desc_key],
            use_plain_text=use_plain_text,
            use_html=use_html, template_file=TEMPLATE_DIR+f'{template}.txt')

    if save_prompt:
        ext = 'json' if chat_mode else 'txt'
        if prompt_save_path is None:
            prompt_save_path = f'prompts/{proj}-{bug_id}-{template}.{ext}'
        with open(prompt_save_path, 'w') as f:
            if ext == 'json':
                json.dump(prompt, f, indent=2)
            else:
                f.write(prompt)

    query_result = query_llm(prompt, model, stop)
    if not chat_mode:
        gen_test = 'public void test' + query_result
    else:
        if ("```") in query_result:
            gen_test = query_result.split("```")[1]
        else:
            gen_test = query_result
    return gen_test


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', default='d4j', help='dataset to use: d4j or ghrb')
    parser.add_argument('-p', '--project', default='Time')
    parser.add_argument('-b', '--bug_id', type=int, default=23)
    parser.add_argument('--use_html', action='store_true')
    parser.add_argument('--use_plain_text', action='store_true')
    parser.add_argument('--save_prompt', action='store_true')
    parser.add_argument('--template', default='2example_chat')
    parser.add_argument('--model', default='OpenAI/gpt-3.5-turbo')
    parser.add_argument('-o', '--out', default='output.txt')
    parser.add_argument('--prompt_out', default=None)
    args = parser.parse_args()

    if args.dataset == 'ghrb':
        BR_DIR = llm_exp_config['bug_report_dir']['ghrb']

    gen_test = query_llm_for_gentest(
        args.project, args.bug_id, 
        args.model,
        args.template, 
        use_plain_text=args.use_plain_text, 
        use_html=args.use_html,
        save_prompt=args.save_prompt, 
        prompt_save_path=args.prompt_out
    )

    with open(args.out, 'w') as f:
        f.write(gen_test)
