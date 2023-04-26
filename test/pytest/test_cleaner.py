import json
import logging
import os
import pytest

from extensions.logger import LoggerSetup
from extensions.cleaner import CleanType, Cleaner
from extensions.utils.helpers import compile_with_docker, run_subprocess


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    LoggerSetup(file_name="test_cleaner", log_level=logging.DEBUG)


# @pytest.mark.parametrize(
#     "directory", ["test/files/contracts-dataset/Clean", "test/files/contracts-dataset/Etherscan_Contract/1-10k"]
# )
@pytest.mark.parametrize("directory", ["test/files/contracts-dataset/Clean"])
def test_check_concurrently(directory):
    cleaner = Cleaner()
    # cleaner.check_with_docker = False
    cleaner.clean_concurrently(directory, clean_type=CleanType.all)


@pytest.mark.parametrize(
    "directory", ["test/files/contracts-dataset/error_files"]
)
def test_clean_for_loop(directory):
    cleaner = Cleaner()

    cleaner.clean_for_loop(directory, clean_type=CleanType.all)


@pytest.mark.parametrize(
    "files",
    [
        "test/files/contracts-dataset/Clean/1371.sol",
        "test/files/contracts-dataset/Clean/2590.sol",
        "test/files/contracts-dataset/Clean/3219.sol",
        "test/files/contracts-dataset/Clean/3926.sol",
        "test/files/contracts-dataset/Clean/2594.sol",
        "test/files/contracts-dataset/Clean/4164.sol",
        "test/files/contracts-dataset/Clean/2536.sol",
        "test/files/contracts-dataset/Clean/2320.sol",
        "test/files/contracts-dataset/Clean/3665.sol",
    ],
)
def test_clean_list(files):
    cleaner = Cleaner()

    cleaner.clean(files, 0, clean_type=CleanType.constructor_enum)


@pytest.mark.parametrize(
    "files",
    [
        "test/files/contracts-dataset/Clean/1371.sol",
        "test/files/contracts-dataset/Clean/2590.sol",
        "test/files/contracts-dataset/Clean/3219.sol",
        "test/files/contracts-dataset/Clean/3926.sol",
        "test/files/contracts-dataset/Clean/2594.sol",
        "test/files/contracts-dataset/Clean/4164.sol",
        "test/files/contracts-dataset/Clean/2270.sol",
        "test/files/contracts-dataset/Clean/3280.sol",
        "test/files/contracts-dataset/Clean/707.sol",
    ],
)
def test_clean_list_solc(files):
    cleaner = Cleaner()
    cleaner.check_with_docker = True
    cleaner.clean(files, 0, clean_type=CleanType.solc_error)


@pytest.mark.parametrize(
    "files", ["test/files/contracts-dataset/Clean/2363.sol"]
)
def test_clean_list_no_pragma(files):
    cleaner = Cleaner()

    cleaner.clean(files, 0, clean_type=CleanType.no_pragma)


@pytest.mark.parametrize(
    "files",
    [
        "test/files/contracts-dataset/Clean/2818.sol",
        "test/files/contracts-dataset/Clean/172.sol",
        "test/files/contracts-dataset/Clean/2301.sol",
        "test/files/contracts-dataset/Clean/984.sol",
        "test/files/contracts-dataset/Clean/707.sol",
        "test/files/contracts-dataset/Clean/2839.sol",
        "test/files/contracts-dataset/Clean/3209.sol",
        "test/files/contracts-dataset/Clean/3722.sol",
        "test/files/contracts-dataset/Clean/2825.sol",
    ],
)
def test_clean_all(files):
    cleaner = Cleaner()
    # cleaner.check_with_docker = False
    cleaner.clean(files, 0, clean_type=CleanType.all)


@pytest.mark.parametrize(
    "path", ["test/files/contracts-dataset/Clean/3484.sol"]
)
def test_run_subprocess(path):
    stdout, stderr, exit_code = run_subprocess(f"solc-select versions")

    print(stdout)
    print(stderr)
    print(exit_code)

    with open(path, "r") as f:
        file_contents = f.read()

    head, tail = os.path.split(path)

    standard_json_input = {
        "language": "Solidity",
        "sources": {f"{tail}": {"content": file_contents}},
        "settings": {
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
        },
    }

    standard_json_input_str = json.dumps(standard_json_input)

    stdout, stderr, exit_code = run_subprocess(
        "solc --standard-json", input_data=standard_json_input_str
    )

    # Parse the JSON output from solc
    compilation_result = json.loads(stdout)

    # Check for errors
    if "errors" in compilation_result:
        errors = compilation_result["errors"]
        for error in errors:
            if error["severity"] == "error":
                source_location = error.get("sourceLocation", {})
                file = source_location.get("file", "")
                start = source_location.get("start", 0)
                line_number = file_contents[:start].count("\n") + 1
                print(f"Error at line {line_number}: {error['message']}")

    # print(stdout)
    # print(stderr)
    # print(exit_code)


@pytest.mark.parametrize(
    "path", ["test/files/contracts-dataset/Clean/3484.sol"]
)
def test_run_subprocess_docker(path):
    with open(path, "r") as f:
        file_contents = f.read()

    head, tail = os.path.split(path)

    standard_json_input = {
        "language": "Solidity",
        "sources": {f"{tail}": {"content": file_contents}},
        "settings": {
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
        },
    }

    standard_json_input_str = json.dumps(standard_json_input)

    stdout, stderr, exit_code = compile_with_docker(
        "0.4.26",
        standard_json_input_str,
    )

    # Parse the JSON output from solc
    compilation_result = json.loads(stdout)

    # Check for errors
    if "errors" in compilation_result:
        errors = compilation_result["errors"]
        for error in errors:
            if error["severity"] == "error":
                formatted_message: str = error["formattedMessage"]
                line_number = formatted_message.split(".sol:")[1].split(":")[0]
                message = error["message"]
                print(
                    f"Error found in {path}\n \tError at line {line_number}: {message}\n {formatted_message}"
                )

    # print(stdout)
    # print(stderr)
    # print(exit_code)
