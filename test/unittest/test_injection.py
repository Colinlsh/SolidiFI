import pytest

from extensions.multiple_bug_injector import BugInjector, BugType

@pytest.mark.parametrize(
    "file_path", ["test/files/contracts-dataset/Clean/3458.sol"]
)
def test_inject(file_path):
    bug_injector = BugInjector()
    
    bug_injector.inject(file_path, BugType.timestamp_dependency)
    
@pytest.mark.parametrize(
    "directory", ["test/files/contracts-dataset/Clean"]
)
def test_multiple_injection(directory):
    bug_injector = BugInjector()
    
    bug_injector.inject_multiple_concurrently(directory, BugType.timestamp_dependency, num_of_process=5)