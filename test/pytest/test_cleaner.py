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
        "test/files/contracts-dataset/Clean/2301.sol",
        "test/files/contracts-dataset/Clean/984.sol",
        "test/files/contracts-dataset/Clean/707.sol",
        "test/files/contracts-dataset/Clean/2839.sol",
        "test/files/contracts-dataset/Clean/3209.sol",
        "test/files/contracts-dataset/Clean/3722.sol",
        "test/files/contracts-dataset/Clean/2825.sol",
        "test/files/contracts-dataset/Clean/4046.sol",
        "test/files/contracts-dataset/Clean/4186.sol",
        "test/files/contracts-dataset/Clean/809.sol",
        "test/files/contracts-dataset/Clean/702.sol",
        "test/files/contracts-dataset/Clean/172.sol",
        "test/files/contracts-dataset/Clean/3708.sol",
        "test/files/contracts-dataset/Clean/3390.sol",
        "test/files/contracts-dataset/Clean/1929.sol",
        "test/files/contracts-dataset/Clean/2021.sol",
        "test/files/contracts-dataset/Clean/4254.sol",
        "test/files/contracts-dataset/Clean/3911.sol",
        "test/files/contracts-dataset/Clean/1275.sol",
        "test/files/contracts-dataset/Clean/1913.sol",
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
    "path", ["test/files/contracts-dataset/Clean/1371.sol"]
)
def test_run_subprocess_docker(path):
    with open(path, "r") as f:
        file_contents = f.read()

    head, tail = os.path.split(path)
    _version = "0.4.16"
    # standard_json_input = {
    #     "language": "Solidity",
    #     "sources": {f"{tail}": {"content": file_contents}},
    #     "settings": {"outputSelection": {"*": {"*": ["*"]}}},
    # }
    standard_json_input = {
        "language": "Solidity",
        "sources": {tail: {"content": file_contents}},
        "settings": {"OutputSelection": {"*": {"*": ["*"]}}},
    }

    standard_json_input_str = json.dumps(standard_json_input)

    stdout, stderr, exit_code = compile_with_docker(
        _version,
        standard_json_input_str,
    )

    pattern = f"Switched global version to {_version}\n"
    # Parse the JSON output from solc

    if stderr:
        print(stderr)
    else:
        result = stdout.split(pattern)[1].strip("\n")

        # Parse the JSON output from solc
    compilation_result = json.loads(result)

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


@pytest.mark.parametrize(
    "file, error_message",
    [
        (
            "test/files/contracts-dataset/Clean/702.sol",
            '702.sol:564:9: TypeError: Member "value" not found or not visible after argument-dependent lookup in function (bytes32) external - did you forget the "payable" modifier?\n        ix.getPayments().payForDemocracy.value(msg.value)(democHash);\n        ^------------------------------------^\n',
        ),
        (
            "test/files/contracts-dataset/Clean/4254.sol",
            '4254.sol:580:19: TypeError: Member "value" not found or not visible after argument-dependent lookup in function (address) external returns (bool) - did you forget the "payable" modifier?\n            if (! TokenController(controller).proxyPayment.value(msg.value)(msg.sender))\n                  ^--------------------------------------------^\n',
        ),
        (
            "test/files/contracts-dataset/Clean/3209.sol",
            '3209.sol:170:13: TypeError: Member "value" not found or not visible after argument-dependent lookup in function (address) external returns (bool) - did you forget the "payable" modifier?\n        if (currentCorpBank_.deposit.value(msg.value)(msg.sender) == true) {\n            ^----------------------------^\n',
        ),
    ],
)
def test_check_dot_value_error(file, error_message):
    cleaner = Cleaner(True)

    with open(file, "r") as f:
        file_contents = f.read()

    cleaner.clean_dot_value_error(file_contents, error_message)


@pytest.mark.parametrize(
    "error_message",
    [
        '172.sol:126:5: TypeError: Overriding function changes state mutability from "payable" to "nonpayable".\n    function increaseProfit() external  returns(bool){\n    ^ (Relevant source part starts here and spans across multiple lines).\n172.sol:69:5: Overriden function is here:\n    function increaseProfit() payable external  returns(bool);\n    ^--------------------------------------------------------^\n\n',
        '702.sol:2784:5: TypeError: Overriding function changes state mutability from "payable" to "nonpayable".\n    function payForDemocracy(bytes32 democHash) external {\n    ^ (Relevant source part starts here and spans across multiple lines).\n702.sol:2590:5: Overriden function is here:\n    function payForDemocracy(bytes32 democHash) payable  external;\n    ^------------------------------------------------------------^\n\n',
    ],
)
def test_check_override_function(error_message):
    cleaner = Cleaner(True)

    file_path = "test/files/contracts-dataset/Clean/172.sol"

    with open(file_path, "r") as f:
        file_contents = f.read()

    cleaner.clean_overriding_payable_error(file_contents, error_message)


def test_check_division_by_zero():
    cleaner = Cleaner(True)
    error_message = "809.sol:1314:19: TypeError: Division by zero.\n    ownerPayout = (losingChunk - oraclizeFees) / COMMISSION; // Payout to the owner; commission of losing pot, minus the same % of the fees\n                  ^---------------------------------------^\n"

    file_path = "test/files/contracts-dataset/Clean/809.sol"

    with open(file_path, "r") as f:
        file_contents = f.read()

    cleaner.clean_division_by_zero_error(file_contents, error_message)
