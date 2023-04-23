from enum import Enum
from functools import partial
import json
from multiprocessing import Manager, Pool, cpu_count
from multiprocessing.managers import ValueProxy
import os
from pathlib import Path
import re
from typing import List
from .logger import LoggerSetup

from .utils.helpers import (
    change_solc_version,
    check_solidity_file_version,
    chunks,
    compile_with_docker,
    run_subprocess,
    set_path_context,
)
from .utils.progress_updater import ProgressUpdater
from solidity_parser import parser

logger = LoggerSetup.get_logger(__name__)


class CleanType(Enum):
    others = 0
    constructor_enum = 1
    solc_error = 2
    no_pragma = 3
    all = 4


class Cleaner:
    def __init__(self) -> None:
        self.progress_updater = ProgressUpdater()

    def insert_pragma_solidity(self, file_path, version="0.4.25"):
        pragma_line = f"pragma solidity ^{version};\n\n"

        with open(file_path, "r") as f:
            content = f.read()

        updated_content = pragma_line + content

        with open(file_path, "w") as f:
            f.write(updated_content)

        return check_solidity_file_version(file_path)

    def get_contract_names(self, file_contents: str) -> list[str]:
        # Parse the Solidity code
        source_unit = parser.parse(file_contents)

        return [
            node["name"]
            for node in source_unit["children"]
            if node["type"] == "ContractDefinition"
        ]

    def get_matching_brace_indices(self, s, open_brace="{", close_brace="}"):
        stack = []
        brace_indices = []
        in_single_line_comment = False
        in_multi_line_comment = False

        for i, c in enumerate(s):
            # Check for single-line comment start
            if s[i : i + 2] == "//":
                in_single_line_comment = True
            # Check for single-line comment end
            elif c == "\n" and in_single_line_comment:
                in_single_line_comment = False
            # Check for multi-line comment start
            elif s[i : i + 2] == "/*":
                in_multi_line_comment = True
            # Check for multi-line comment end
            elif s[i - 1 : i + 1] == "*/":
                in_multi_line_comment = False

            # Ignore braces inside comments
            if in_single_line_comment or in_multi_line_comment:
                continue

            if c == open_brace:
                stack.append(i)
            elif c == close_brace:
                if len(stack) == 0:
                    raise ValueError("Unbalanced braces")
                open_index = stack.pop()
                brace_indices.append((open_index, i))

        if len(stack) != 0:
            raise ValueError("Unbalanced braces")

        return brace_indices

    def replace_constructors(
        self, file_contents: str, contract_names: list[str]
    ) -> str:
        for contract_name in contract_names:
            # Match the contract block for the current contract name
            contract_block_start_pattern = (
                rf"contract\s+{contract_name}\s*(?:is\s+(?:\w+,\s*)*\w+\s*)*{{"
            )

            contract_block_start_match = re.search(
                contract_block_start_pattern, file_contents
            )

            if contract_block_start_match:
                start_index = contract_block_start_match.end() - 1
                brace_indices = self.get_matching_brace_indices(file_contents)
                end_index = None

                for open_index, close_index in brace_indices:
                    if open_index == start_index:
                        end_index = close_index
                        break

                contract_block = file_contents[start_index : end_index + 1]

                # Match the constructor within the contract block
                constructor_pattern = (
                    rf"constructor\s*\(([\w\s,]*)\)([\s\S]*?)?\s*public\s*{{"
                )

                constructor_match = re.search(
                    constructor_pattern, contract_block, re.DOTALL
                )

                if constructor_match:
                    new_constructor = f"function {contract_name}({constructor_match.group(1)}){constructor_match.group(2)} public {{"
                    updated_contract_block = contract_block.replace(
                        constructor_match.group(0), new_constructor
                    )

                    # Replace the original contract block with the updated one in the file_contents
                    file_contents = file_contents.replace(
                        contract_block, updated_contract_block
                    )

        return file_contents

    def check_solc_error_json(
        self,
        file_contents: str,
        file_path: str,
        version: str = None,
        solc_bin_path: str = None,
        with_docker: bool = None,
    ):
        head, tail = os.path.split(file_path)

        standard_json_input = {
            "language": "Solidity",
            "sources": {f"{tail}": {"content": file_contents}},
            "settings": {
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
            },
        }

        standard_json_input_str = json.dumps(standard_json_input)

        if with_docker:
            stdout, stderr, exit_code = compile_with_docker(
                version, standard_json_input_str, logger
            )
        else:
            command = f"solc --standard-json"

            if solc_bin_path is not None:
                command = command.replace("solc", solc_bin_path)

            # change_solc_version(version)
            stdout, stderr, exit_code = run_subprocess(
                f"{command}",
                input_data=standard_json_input_str,
            )

        # Parse the JSON output from solc
        if stdout:
            try:
                compilation_result = json.loads(stdout)
            except json.JSONDecodeError:
                logger.error(
                    f"Error parsing solc output for {file_path}: {stdout}"
                )
                return

            # Check for errors
            if "errors" in compilation_result:
                errors = compilation_result["errors"]
                for error in errors:
                    if error["severity"] == "error":
                        formatted_message: str = error["formattedMessage"]
                        line_number = formatted_message.split(".sol:")[1].split(
                            ":"
                        )[0]
                        message = error["message"]
                        logger.error(
                            f"Error found in {file_path}\n \tError at line {line_number}: {message}\n {formatted_message}"
                        )

        elif stderr:
            logger.error(stderr)

    def check_solc_error_legacy(
        self,
        file_contents: str,
        file_path: str,
        version: str = None,
        solc_bin_path: str = None,
        with_docker: bool = None,
    ):
        head, tail = os.path.split(file_path)
        temp_file_path = os.path.join(head, f"{tail}.sol")

        # Create a temporary file with the contract content
        with open(temp_file_path, "w") as temp_file:
            temp_file.write(file_contents)

        if with_docker:
            stdout, stderr, exit_code = compile_with_docker(
                version, temp_file_path, logger
            )
        else:
            command = f"solc --combined-json abi,bin {temp_file_path}"

            if solc_bin_path is not None:
                command = command.replace("solc", solc_bin_path)

            # change_solc_version(version)
            stdout, stderr, exit_code = run_subprocess(
                f"{command}",
            )

            # Remove the temporary file
            os.remove(temp_file_path)

        # Check for errors
        if exit_code != 0:
            error_lines = stderr.split("\n")
            for error_line in error_lines:
                if "Error:" in error_line:
                    logger.error(f"Error found in {file_path}\n \t{error_line}")

        # Parse the JSON output from solc
        else:
            try:
                compilation_result = json.loads(stdout)
            except json.JSONDecodeError:
                logger.error(
                    f"Error parsing solc output for {file_path}: {stdout}"
                )
                return

            # Check for errors
            if "errors" in compilation_result:
                errors = compilation_result["errors"]
                for error in errors:
                    if error["severity"] == "error":
                        formatted_message: str = error["formattedMessage"]
                        line_number = formatted_message.split(".sol:")[1].split(
                            ":"
                        )[0]
                        message = error["message"]
                        logger.error(
                            f"Error found in {file_path}\n \tError at line {line_number}: {message}\n {formatted_message}"
                        )

    def clean(
        self,
        path: str,
        total_files: int,
        solidity_version: str = "0",
        shared_processed_files: ValueProxy = None,
        lock=None,
        clean_type: CleanType = 0,
    ) -> None:
        try:
            if solidity_version != "0":
                _version = solidity_version

                # change_solc_version(_version)

            else:
                _version = check_solidity_file_version(path)

            if _version == None:
                _version = self.insert_pragma_solidity(path)

            version_number = int(_version.split(".")[2])

            with open(path, "r") as f:
                file_contents = f.read()

            if clean_type == CleanType.constructor_enum:
                self._check_constructor_emit(path, _version, file_contents)
            elif clean_type == CleanType.solc_error:
                if version_number >= 11:
                    self.check_solc_error_json(
                        file_contents, path, _version, with_docker=True
                    )
                else:
                    self.check_solc_error_legacy(
                        file_contents, path, _version, with_docker=True
                    )
            elif clean_type == CleanType.all:
                self._check_constructor_emit(path, _version, file_contents)
                if version_number >= 11:
                    self.check_solc_error_json(
                        file_contents, path, _version, with_docker=True
                    )
                else:
                    self.check_solc_error_legacy(
                        file_contents, path, _version, with_docker=True
                    )

            if shared_processed_files and lock:
                with lock:
                    shared_processed_files.value += 1
                    self.progress_updater.print_progress_bar(
                        shared_processed_files.value,
                        total_files,
                        prefix="Progress:",
                        suffix="Complete",
                    )
        except Exception as e:
            logger.exception(f"Error processing file: {path}\n")
            logger.exception(f"{str(e)}\n")

    def _check_constructor_emit(self, path, _version, file_contents):
        version_number = int(_version.split(".")[2])

        if version_number < 22:
            # Get the contract names
            contract_names = self.get_contract_names(file_contents)

            # Replace constructors for each contract
            file_contents = self.replace_constructors(
                file_contents, contract_names
            )

        if version_number < 21:
            file_contents = file_contents.replace("emit ", "")

        with open(path, "w") as f:
            f.write(file_contents)

    def _clean_it(
        self,
        chunks,
        total_files,
        shared_processed_files=None,
        lock=None,
        clean_type: CleanType = 0,
    ):
        results = []
        # set_path_context()
        for file_path in chunks:
            # solidity_version = check_solidity_file_version(file_path)
            result = self.clean(
                path=Path(file_path),
                total_files=total_files,
                shared_processed_files=shared_processed_files,
                lock=lock,
                clean_type=clean_type,
            )
            results.append(result)
        return results

    def clean_concurrently(
        self,
        directory: str,
        num_of_process: int = -1,
        clean_type: CleanType = 0,
    ):
        try:
            path_list = list(Path(directory).glob("**/*.sol"))
            total_files = len(path_list)
            if num_of_process == -1:
                num_of_process = min(len(path_list), cpu_count())
            chunk_size = len(path_list) // num_of_process

            # Convert the Path objects to strings
            path_list_str = [str(file_path) for file_path in path_list]

            # Split the input files into multiple chunks
            chunks = [
                path_list_str[i : i + chunk_size]
                for i in range(0, len(path_list_str), chunk_size)
            ]

            with Manager() as manager:
                shared_processed_files: ValueProxy = manager.Value("i", 0)
                lock = manager.Lock()
                # Create a pool of worker processes
                with Pool(processes=num_of_process) as pool:
                    # Process each chunk in parallel
                    processed_files = 0
                    self.progress_updater.print_progress_bar(
                        processed_files,
                        total_files,
                        prefix="Progress:",
                        suffix="Complete",
                    )

                    for _ in pool.imap_unordered(
                        partial(
                            self._clean_it,
                            total_files=total_files,
                            shared_processed_files=shared_processed_files,
                            lock=lock,
                            clean_type=clean_type,
                        ),
                        chunks,
                    ):
                        pass
        except Exception as e:
            logger.exception(f"{str(e)}\n")

    def clean_for_loop(
        self, directory: str, clean_type: CleanType = CleanType.all
    ):
        try:
            path_list = list(Path(directory).glob("**/*.sol"))
            total_files = len(path_list)
            processed_files = 0
            for file in path_list:
                self.clean(file, total_files, clean_type=clean_type)
                self.progress_updater.print_progress_bar(
                    processed_files,
                    total_files,
                    prefix="Progress:",
                    suffix="Complete",
                )
                processed_files += 1

        except Exception as e:
            logger.error(e)
