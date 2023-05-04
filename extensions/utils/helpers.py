from dataclasses import fields
from datetime import datetime
from enum import Enum
from logging import Logger
import logging
import os
import platform
import re
import subprocess
from typing import Tuple
import uuid
import pandas as pd

import requests

from extensions.logger import LoggerSetup


def set_path_context():
    # Set the PATH environment variable to include the path to solc
    os.environ["SOLC_BINARY"] += (
        os.pathsep + "/Users/colinlsh88888888/.pyenv/shims/solc"
    )


def is_pragma_invalid(solidity_code):
    pattern = r"(pragma\s+solidity\s+\d+)\s*\.\s*(\d+)\s*\.\s*(\d+);?"
    match = re.search(pattern, solidity_code)
    return match is not None


def fix_pragma(file_contents: str):
    pattern = r"(pragma\s+solidity\s+\d+)\s*\.\s*(\d+)\s*\.\s*(\d+);?"
    fixed_code = re.sub(pattern, r"\1.\2.\3;", file_contents)

    return fixed_code, check_solidity_file_version(file_content=fixed_code)


def check_solidity_file_version(
    file_path: str = "", file_content: str = ""
) -> str:
    solidity_version = None
    pragma_pattern = re.compile(r"pragma\s+solidity\s+([\^>=<]*\d+\.\d+\.\d+);")

    if file_content:
        solidity_version = match_search_pragma(pragma_pattern, file_content)
    else:
        # Check solidity version
        with open(file_path, "r") as f:
            content = f.read()

            solidity_version = match_search_pragma(pragma_pattern, content)

    if solidity_version is None:
        return None

    # change_solc_version(solidity_version)

    return solidity_version


def match_search_pragma(pragma_pattern, content):
    solidity_version = None
    match = pragma_pattern.search(content)
    if match:
        # Extract version number and clean the string
        solidity_version = re.sub(r"[^0-9.]", "", match.group(1)).strip()
        if "^" in match.group(1) or ">" in match.group(1):
            version_major = solidity_version.split(".")[1]

            if int(version_major) == 4:
                solidity_version = "0.4.26"
        # elif "0.4.15" in match.group(1):
        #     solidity_version = "0.4.26"

    return solidity_version


def change_solc_version(version: str, has_caret_symbol=False) -> None:
    _current_version, _, _ = run_subprocess(f"solc --version")
    _current_available_versions, _, _ = run_subprocess(f"solc-select versions")

    if version not in _current_version:
        if version not in _current_available_versions:
            run_subprocess(f"solc-select install {version}")

    run_subprocess(f"solc-select use {version}")


def run_subprocess(
    command: str, input_data: str = None
) -> Tuple[str, str, str]:
    """wrapper function to run subprocess. It will return the exit code, output and any error messages.

    Args:
        command (str): full command that would be run in cli

    Returns:
        Tuple[str, str, str]: stdout, stderr, exitcode
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        shell=True,
    )
    stdout, stderr = process.communicate(input=input_data)
    exit_code = process.wait()

    return stdout, stderr, exit_code


def get_current_time():
    return f"{datetime.now().date().isoformat()}_{datetime.now().time().hour}_{datetime.now().time().minute}_{datetime.now().time().second}"


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def download_solc_binary(
    version: str, solc_binaries_folder: str = "solc_binaries"
) -> str:
    """download solc binary and use, note that macos dont always have binary. So it dont always work.

    Args:
        version (str): version number
        solc_binaries_folder (str, optional): output path. Defaults to "solc_binaries".

    Returns:
        str: binary path
    """
    os.makedirs(solc_binaries_folder, exist_ok=True)
    solc_binary_filename = f"solc-v{version}"
    solc_binary_path = os.path.join(solc_binaries_folder, solc_binary_filename)

    if not os.path.isfile(solc_binary_path):
        system = platform.system().lower()
        if system == "linux":
            download_url = f"https://github.com/ethereum/solidity/releases/download/v{version}/solc-static-linux"
        elif system == "darwin":
            download_url = f"https://github.com/ethereum/solidity/releases/download/v{version}/solc-macos"
        else:
            download_url = f"https://github.com/ethereum/solidity/releases/download/v{version}/solc-windows.exe"

        response = requests.get(download_url)
        response.raise_for_status()

        with open(solc_binary_path, "wb") as f:
            f.write(response.content)

        os.chmod(solc_binary_path, 0o755)

    return solc_binary_path


def get_solc_binary(
    version: str, solc_binaries_folder: str = "solc_binaries"
) -> str:
    solc_binary_filename = f"solc-v{version}"
    solc_binary_path = os.path.join(solc_binaries_folder, solc_binary_filename)

    if not os.path.exists(solc_binary_path):
        download_solc_binary(version, solc_binaries_folder)

    return solc_binary_path


class DockerSolcCompileType:
    standard_json = "--standard-json"
    ast_compact_json = "--ast-compact-json"


def compile_with_docker(
    solc_version: str,
    input_json: str,
    commands: str = DockerSolcCompileType.standard_json,
) -> Tuple[str, str, str]:
    # Generate a unique container name for each run
    container_name = f"solc-select-solc-{uuid.uuid4()}"

    # run_subprocess(
    #     f"docker pull --platform linux/amd64 ethereum/solc:{version}"
    # )

    docker_run_command = (
        f"docker run --rm --name {container_name} -i -a stdin -a stdout -a stderr solc_select_solc"
        f" /bin/bash -c 'solc-select use {solc_version} && solc {commands}'"
    )

    stdout, stderr, return_code = run_subprocess(
        docker_run_command, input_data=input_json
    )

    return stdout, stderr, return_code


def find_closing_brace(code: str, start: int) -> int:
    open_braces = 1
    position = start
    while open_braces > 0 and position < len(code):
        if code[position] == "{":
            open_braces += 1
        elif code[position] == "}":
            open_braces -= 1
        position += 1
    return position


def find_function_start_end(file_content: str):
    pattern = re.compile(
        r"(function payOwners\(\) private canPayOwners {.*?})", re.DOTALL
    )

    function_positions = [
        match.start() for match in pattern.finditer(file_content)
    ]
    function_positions.append(len(file_content))

    for i, position in enumerate(function_positions[:-1]):
        if position < function_positions[i + 1]:
            function_start = position
            function_end = function_positions[i + 1]
            break

    return function_start, function_end


def get_log_level():
    return logging.ERROR


def get_logging_instance(name: str):
    logger_setup = LoggerSetup(name, log_level=get_log_level())
    return logger_setup.get_logger()


def prettier_format(directory: str = None, file_path: str = None):
    command = ""
    if directory:
        command = f"npx prettier '{directory}/**/*.sol'"
    elif file_path:
        command = f"npx prettier '{file_path}'"

    stdout, stderr, exit_code = run_subprocess(command)


def export_to_csv(data_list: list[any], output_path: str):
    current_type = type(data_list[0])

    # Get field names from the current_type dataclass
    column_names = [field.name for field in fields(current_type)]

    # Create a dictionary with default values for all fields
    default_dict = {field.name: field.default for field in fields(current_type)}

    # Convert the list of current_type objects to a list of dictionaries with default values
    dict_list = [dict(default_dict, **vars(obj)) for obj in data_list]

    # Convert the list of dictionaries to a DataFrame
    df = pd.DataFrame(dict_list, columns=column_names)

    # Save the DataFrame to a CSV file
    df.to_csv(output_path, index=False)
