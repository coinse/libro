
repo_path_map = {
    'FasterXML_jackson-core': '../data/GHRB/repos/jackson-core/',
    'google_gson': '../data/GHRB/repos/gson/gson',
    'Hakky54_sslcontext-kickstart': '../data/GHRB/repos/sslcontext-kickstart/sslcontext-kickstart/',
    'assertj_assertj-core': '../data/GHRB/repos/assertj-core/',
    'FasterXML_jackson-databind': '../data/GHRB/repos/jackson-databind/',
    'jhy_jsoup': '../data/GHRB/repos/jsoup/',
    'google_guava': '../data/GHRB/repos/guava/',
    'checkstyle_checkstyle': '../data/GHRB/repos/checkstyle/',
    'scribejava_scribejava': '../data/GHRB/repos/scribejava/'
}


def contains_bug_label(labels):
    for label in labels:
        if 'bug' in label:
            return True
    return False


def contains_test_in_paths(paths):
    for path in paths:
        if 'test' in path.lower() and path.endswith('.java'):
            return True

        if 'assert' in path.lower() and path.endswith('.java'):
            return True 

        if 'should' in path.lower() and path.endswith('.java'):
            return True
            
    return False