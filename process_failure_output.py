import json
from common import find_between


def parse_buggy_output(buggy_output, exception_type=None, value_matching=None, exception_msg=None, mode='d4j'):
    """
    Parse failure output (mode: d4j, ghrb)
    """
    if mode == 'd4j': 
        return parse_buggy_output_d4j(buggy_output)
    elif mode == 'ghrb':
        assert exception_type is not None
        is_crash = 'Assertion' not in exception_type and 'Comparison' not in exception_type

        if value_matching is not None and 'expected:' in value_matching.lower():
            value_matching += '\n'
            if 'expected:' in value_matching:
                expected = find_between(value_matching, 'expected:', 'but was:').strip()
            elif 'Expected:' in value_matching:
                expected = find_between(value_matching, 'Expected:', 'but was:').strip()
            if expected.strip() == '':
                expected = None
            elif '<' in expected and expected.index('<') >= 0 and expected.endswith('>'):
                    expected = expected[expected.index('<')+1:-1]
                    expected = clean_output_value(expected)

            actual = find_between(value_matching, 'but was:', '\n').strip()
            if actual.strip() == '':
                actual = None
            else:
                if '<' in actual and actual.index('<') >= 0:
                    actual = actual[actual.index('<')+1:]
                actual = actual.removesuffix('>')
                actual = clean_output_value(actual)
        else:
            expected = None
            actual = None
        
        stacktrace = None # we do not consider stack trace here

    else:
        raise NotImplementedError
    

    return {
        'is_crash': is_crash,
        'expected': expected,
        'actual': actual,
        'exception_type': exception_type,
        'exception_msg': exception_msg,
        'stacktrace': stacktrace,
        'full_output': buggy_output
    }


def parse_buggy_output_d4j(buggy_output):
    exception_type = buggy_output.strip().split('\n')[1].strip().split(':')[0]
    if len(buggy_output.split('\n')[1].strip().split(':')) > 1:
        exception_msg = buggy_output.strip().split('\n')[1].strip().split(':')[1]
    else:
        exception_msg = None
    is_crash = 'Assertion' not in exception_type and 'Comparison' not in exception_type
    if is_crash:       
        stacktrace = buggy_output.strip().split('\n')[2:]
    else:
        stacktrace = None

    if 'expected:' in buggy_output.lower():
        if 'expected:' in buggy_output:
            expected = find_between(buggy_output, 'expected:', 'but was:').strip()
        elif 'Expected:' in buggy_output:
            expected = find_between(buggy_output, 'Expected:', 'but was:').strip()
        if expected.strip() == '':
            expected = None
        else:
            assert expected.index('<') >= 0 and expected.endswith('>')
            expected = expected[expected.index('<')+1:-1]
            expected = clean_output_value(expected)
        actual = find_between(buggy_output, 'but was:', '\n').strip()
        if actual.strip() == '':
            actual = None
        else:
            if '<' in actual and actual.index('<') >= 0:
                actual = actual[actual.index('<')+1:]
            actual = actual.removesuffix('>')
            actual = clean_output_value(actual)
    else:
        expected = None
        actual = None

    return {
        'is_crash': is_crash,
        'expected': expected,
        'actual': actual,
        'exception_type': exception_type,
        'exception_msg': exception_msg,
        'stacktrace': stacktrace,
        'full_output': buggy_output
    }

def clean_output_value(s):
    return s.replace('[', '').replace(']', '').replace('...', ' ')
