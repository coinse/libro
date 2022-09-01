"""
Configuration for LLM test generator w/ different datasets.
"""

llm_exp_config = {
    'bug_report_dir': {
        'ghrb': './data/GHRB/bug_report/',
        'd4j': './data/Defects4J/bug_report/'
    },
    'template_dir': './data/prompt_templates/',
    'gen_tests_dir': {
        'ghrb': './data/GHRB/gen_tests/',
        'd4j': './data/Defects4J/gen_tests/'
    }
}
