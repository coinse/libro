"""
Configuration for LLM test generator w/ different datasets.
"""

llm_exp_config = {
    'bug_report_dir': {
        'ghrb': '/root/data/GHRB/bug_report/',
        'd4j': '/root/data/Defects4J/bug_report/'
    },
    'template_dir': '/root/data/prompt_templates/',
    'gen_tests_dir': {
        'ghrb': '/root/data/GHRB/gen_tests/',
        'd4j': '/root/data/Defects4J/gen_tests/'
    }
}
