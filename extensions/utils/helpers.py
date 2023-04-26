from datetime import datetime
from enum import Enum
from logging import Logger
import os
import platform
import re
import subprocess
from typing import Tuple

import requests


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
        elif "0.4.15" in match.group(1):
            solidity_version = "0.4.16"

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
        f"{command}",
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
    abi_compact_json = "--ast-compact-json"


def compile_with_docker(
    version: str,
    file_contents: str,
    docker_solc_compile_type: str = DockerSolcCompileType.standard_json,
) -> Tuple[str, str, str]:
    run_subprocess(
        f"docker pull --platform linux/amd64 ethereum/solc:{version}"
    )
    return run_subprocess(
        f"docker run --platform linux/amd64 --rm -i -a stdin -a stdout -a stderr ethereum/solc:{version} {docker_solc_compile_type}",
        input_data=file_contents,
    )
