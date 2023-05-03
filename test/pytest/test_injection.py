import logging
import pytest

from extensions.bug_injector import BugInjector, BugType
from extensions.logger import LoggerSetup


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    LoggerSetup(file_name="test_injection", log_level=logging.DEBUG)


@pytest.mark.parametrize(
    "file_path",
    [
        "test/files/contracts-dataset/Clean/1654.sol",
        "test/files/contracts-dataset/Clean/3919.sol",
        "test/files/contracts-dataset/Clean/2494.sol",
        "test/files/contracts-dataset/Clean/2121.sol",
        "test/files/contracts-dataset/Clean_Cleansed/2469.sol",
        "test/files/contracts-dataset/Clean_Cleansed/800.sol",
    ],
)
def test_inject(file_path):
    bug_injector = BugInjector()

    bug_injector.inject(file_path, BugType.timestamp_dependency)


@pytest.mark.parametrize(
    "directory", ["test/files/contracts-dataset/Clean_Cleansed"]
)
def test_multiple_injection(directory):
    bug_injector = BugInjector()

    bug_injector.inject_multiple_concurrently(
        directory, BugType.timestamp_dependency, num_of_process=5
    )
    # bug_injector.inject_multiple_concurrently(
    #     directory, BugType.reentrancy, num_of_process=5
    # )
    # bug_injector.inject_multiple_concurrently(
    #     directory, BugType.arithmetic, num_of_process=5
    # )
    # bug_injector.inject_multiple_concurrently(
    #     directory, BugType.tx_origin, num_of_process=5
    # )
    # bug_injector.inject_multiple_concurrently(
    #     directory, BugType.unchecked_send, num_of_process=5
    # )
