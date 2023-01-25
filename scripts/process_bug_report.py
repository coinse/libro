import re
import json

REPORT_FEAT_PATH_D4J = '../data/Defects4J/bug_report_features.json'
REPORT_FEAT_PATH_GHRB = '../data/GHRB/bug_report_features_ghrb.json'

def load_bug_report_features(dataset='d4j'):
    if dataset == 'd4j':
        with open(REPORT_FEAT_PATH_D4J, 'r') as f:
            bug_report_features = json.load(f)
    elif dataset == 'ghrb':
        with open(REPORT_FEAT_PATH_GHRB, 'r') as f:
            bug_report_features = json.load(f)
    else:
        raise NotImplementedError

    return bug_report_features


def parse_bug_report(bug_id, report_features, dataset='d4j'):
    if '_' in bug_id and dataset == 'd4j':
        bug_id = bug_id.replace('_', '-')
    report = report_features[bug_id]
    likely_crash = False 
    NL_context = [] # for later match with observed exception type
    confident_exception_types = []

    summary_text = '\n'.join(report['summary_text'])
    if 'exception' in summary_text.lower() or 'crash' in summary_text.lower() or 'throw' in summary_text.lower() or 'outofmemory' in summary_text.lower() or 'overflow' in summary_text.lower():
        likely_crash = True
        NL_context.append(summary_text)

    else:  
        for line, tags in report['desc_text']:
            if 'Caused by:' in line: # confident case
                likely_crash = True 
                NL_context.append(line)
                confident_exception_types.append(line.strip())
                break
            if 'CODE' in tags: # exception should be stated in NL context
                continue
            if line.strip().startswith('at'): # safely discard stacktrace frames
                continue
            likely_function_def = re.findall(r'\)\s+throws.*Exception', line)
            if len(likely_function_def) > 0:
                continue
            expected_exceptions = re.findall(r'should throw.*Exception', line)
            if len(expected_exceptions) > 0:
                continue
            
            if 'exception' in line.lower() or 'crash' in line.lower() or 'outofmemory' in line.lower() or 'overflow' in line.lower():
                likely_crash = True
                NL_context.append(line)
    
    expected_exceptions = re.findall(r'should throw[\s\.\w\W]*Exception', summary_text)
    if len(expected_exceptions) > 0:
        likely_crash = False

    return {
        'is_crash': likely_crash,
        'NL_context': '\n'.join(NL_context),
        'confident_exception_types': confident_exception_types,
        'full_text': '\n'.join(report['summary_text'] + [l[0] for l in report['desc_text']])
    }
