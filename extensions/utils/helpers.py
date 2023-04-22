from datetime import datetime
import re
import subprocess
from typing import Tuple


def check_solidity_file_version(file_path) -> str:
    solidity_version = None
    pragma_pattern = re.compile(r"pragma\s+solidity\s+([\^>=<]*\d+\.\d+\.\d+);")

    # Check solidity version
    with open(file_path, "r") as f:
        content = f.read()
        match = pragma_pattern.search(content)

        if match:
            # Extract version number and clean the string
            solidity_version = re.sub(r"[^0-9.]", "", match.group(1)).strip()

    _current_version = subprocess.getoutput("solc --version")

    if solidity_version is None:
        return None

    if solidity_version not in _current_version:
        subprocess.getoutput(
            f"solc-select install {solidity_version} && solc-select use {solidity_version}"
        )

    return solidity_version.strip()


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
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate(input=input_data)
    exit_code = process.wait()

    return stdout, stderr, exit_code


def get_current_time():
    return f"{datetime.now().date().isoformat()}_{datetime.now().time().hour}_{datetime.now().time().minute}_{datetime.now().time().second}"
