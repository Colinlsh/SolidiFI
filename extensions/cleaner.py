from enum import Enum
from functools import partial
import json
from multiprocessing import Manager, Pool, cpu_count
from multiprocessing.managers import ValueProxy
import os
from pathlib import Path
import re
import tempfile
from typing import List, Tuple
import uuid

import regex
from .logger import LoggerSetup

from .utils.helpers import (
    change_solc_version,
    check_solidity_file_version,
    compile_with_docker,
    fix_pragma,
    is_pragma_invalid,
    run_subprocess,
)
from .utils.progress_updater import ProgressUpdater
from solidity_parser import parser
from packaging import version

logger = LoggerSetup.get_logger(__name__)


class CleanType(Enum):
    others = 0
    constructor_enum = 1
    solc_error = 2
    no_pragma = 3
    all = 4


class Cleaner:
    check_with_docker = False

    def __init__(self, check_with_docker: bool = True) -> None:
        self.progress_updater = ProgressUpdater()
        self.check_with_docker = check_with_docker

    def insert_pragma_solidity(
        self, file_path, version="0.4.26"
    ) -> Tuple[str, str]:
        pragma_line = f"pragma solidity ^{version};\n\n"

        with open(file_path, "r") as f:
            content = f.read()

        updated_content = pragma_line + content

        with open(file_path, "w") as f:
            f.write(updated_content)

        return check_solidity_file_version(file_path), updated_content

    def get_contract_names(
        self, file_path, file_contents: str, _version: str = ""
    ) -> list[str]:
        head, tail = os.path.split(file_path)
        input_json_str = {
            "language": "Solidity",
            "sources": {tail: {"content": file_contents}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "": ["ast"],
                    },
                },
            },
        }

        input_json_str = json.dumps(input_json_str)

        stdout, stderr, exit_code = compile_with_docker(
            _version, input_json_str
        )

        pattern = f"Switched global version to {_version}\n"

        if stderr:
            raise Exception(
                f"get contract names compiling error {file_path}: {stderr}"
            )
        else:
            result = stdout.split(pattern)[1].strip("\n")

            compilation_result = json.loads(result)

        if tail in compilation_result["sources"]:
            if version.parse(_version) > version.parse("0.4.11"):
                return [
                    node["name"]
                    for node in compilation_result["sources"][tail]["ast"][
                        "nodes"
                    ]
                    if node["nodeType"] == "ContractDefinition"
                ]
            else:
                return [
                    child["attributes"]["name"]
                    for child in compilation_result["sources"][tail][
                        "legacyAST"
                    ]["children"]
                    if child["name"] == "ContractDefinition"
                ]
        else:
            # back up method
            source_unit = parser.parse(file_contents)
            return [
                node["name"]
                for node in source_unit["children"]
                if node["type"] == "ContractDefinition"
            ]

    def get_contract_names_legacy(self, file_contents: str) -> list[str]:
        source_unit = parser.parse(file_contents)
        return [
            node["name"]
            for node in source_unit["children"]
            if node["type"] == "ContractDefinition"
        ]

    def get_matching_brace_indices(self, s, open_brace="{", close_brace="}"):
        stack = []
        brace_indices = []

        i = 0
        while i < len(s):
            c = s[i]

            if (
                c == "/"
                and i + 1 < len(s)
                and s[i + 1] == "/"
                and not self.in_comment(s, i)
            ):
                i += 2
                while i < len(s) and s[i] != "\n":
                    i += 1

            elif (
                c == "/"
                and i + 1 < len(s)
                and s[i + 1] == "*"
                and not self.in_comment(s, i)
            ):
                i += 2
                while i < len(s) - 1 and (s[i] != "*" or s[i + 1] != "/"):
                    i += 1
                i += 1

            elif c == '"' and not self.in_comment(s, i):
                i += 1
                while i < len(s) and (
                    s[i] != '"' or (i > 0 and s[i - 1] == "\\")
                ):
                    i += 1

            elif c == open_brace and not self.in_comment(s, i):
                stack.append(i)

            elif c == close_brace and not self.in_comment(s, i):
                if len(stack) == 0:
                    raise ValueError("Unbalanced braces")
                open_index = stack.pop()
                brace_indices.append((open_index, i))

            i += 1

        if len(stack) != 0:
            raise ValueError("Unbalanced braces")

        return brace_indices

    def in_comment(self, s, i):
        in_single_line_comment = False
        in_multi_line_comment = False

        j = 0
        while j < i:
            c = s[j]

            if (
                c == "/"
                and j + 1 < i
                and s[j + 1] == "/"
                and not in_multi_line_comment
            ):
                in_single_line_comment = not in_single_line_comment
                j += 1

            elif (
                c == "/"
                and j + 1 < i
                and s[j + 1] == "*"
                and not in_single_line_comment
            ):
                in_multi_line_comment = not in_multi_line_comment
                j += 1

            elif (
                c == "*"
                and j + 1 < i
                and s[j + 1] == "/"
                and in_multi_line_comment
            ):
                in_multi_line_comment = not in_multi_line_comment
                j += 1

            elif c == "\n":
                in_single_line_comment = False

            j += 1

        return in_single_line_comment or in_multi_line_comment

    def replace_old_to_new_constructors(
        self, file_contents: str, contract_names: List[str]
    ) -> str:
        for contract_name in contract_names:
            # Match constructors with old syntax in the given contract_name
            old_constructor_pattern = rf"function\s+{contract_name}\s*\(([^)]*)\)\s*(public|internal|private|external)"
            new_constructor = r"constructor(\1) \2"

            # Replace old constructors with new syntax
            file_contents = re.sub(
                old_constructor_pattern, new_constructor, file_contents
            )

        return file_contents

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

    def count_arguments(self, arg_str: str):
        if not arg_str:
            return 0
        return len(arg_str.split(","))

    def is_if_statement(self, error_msg):
        # Regex pattern to match the specific TypeError
        line_regex = r"\s*if\s*\((.*?)\)"
        match = re.search(line_regex, error_msg)

        return bool(match)

    def is_semi_colon_parenthesis(self, error_msg):
        error_pattern = r"ParserError: Expected ';'\s+but got '}'"
        match = re.search(error_pattern, error_msg)

        return bool(match)

    def is_require(self, error_msg):
        require_pattern = r"require\((.*?)\)"
        match = re.search(require_pattern, error_msg)

        return bool(match)

    def is_return(self, error_msg):
        return_pattern = r"return\s+(\w+\.\w+\.value\(.*\)\(.*\))"
        match = re.search(return_pattern, error_msg)

        return bool(match)

    def clean_overriding_payable_error(
        self, file_contents: str, error_msg: str
    ):
        function_name = (
            error_msg.split("Overriden function is here:")[1]
            .strip()
            .split("\n")[0]
            .strip(";")
            .split("external")[0]
            .split("payable")[0]
            .strip()
            .split("function")[1]
            .split("(")[0]
            .strip()
        )

        complete_function_headers = re.findall(
            rf"(function {function_name}\([^{{]+)", file_contents
        )

        for complete_function_header in complete_function_headers:
            _header: str = (
                complete_function_header[0]
                if len(complete_function_header) > 1
                and complete_function_header[1] == ""
                else complete_function_header
            )
            if (
                "payable" not in _header
                and "internal" not in complete_function_header
            ):
                new_function_header = _header.replace(")", ") payable", 1)
                updated_file_contents = file_contents.replace(
                    _header, new_function_header, 1
                )
                return updated_file_contents

        raise Exception(f"No matching function header for {error_msg}")

    def clean_undeclared_identifier(self, file_content: str, error_msg: str):
        # Split the contract into lines
        lines = file_content.split("\n")

        # Extract the line number from the error message
        # The error message format is assumed to be 'filename:linenumber:column: ErrorMessage'
        line_number = (
            int(error_msg.split(":")[1]) - 1
        )  # Subtract 1 because list indices start at 0

        # Comment out the line
        lines[line_number] = "// " + lines[line_number]

        # Join the lines back into a single string
        new_file_content = "\n".join(lines)

        return new_file_content

    def clean_division_by_zero_error(self, file_content: str, error_msg: str):
        # Find the start of the function declaration
        function_start = file_content.find(
            "function payOwners() private canPayOwners"
        )

        # If the function name is not found, return error
        if function_start == -1:
            raise Exception(f"Function not found in the code. {error_msg}")

        # Find the opening bracket of the function block
        opening_bracket = file_content.find("{", function_start)

        if opening_bracket == -1:
            raise Exception(
                f"Opening bracket not found in the function. {error_msg}"
            )

        # Initialize bracket count
        bracket_count = 1

        # Initialize position of the closing bracket
        closing_bracket = opening_bracket

        # Iterate over the code from the opening bracket
        for i in range(opening_bracket + 1, len(file_content)):
            if file_content[i] == "{":
                bracket_count += 1
            elif file_content[i] == "}":
                bracket_count -= 1

            # If bracket count is 0, we found the closing bracket of the function
            if bracket_count == 0:
                closing_bracket = self.check_closing_bracket(file_content, i)
                break

        # _function_block = file_content[function_start : closing_bracket + 1]

        return self.comment_out_function(
            file_content, function_start, closing_bracket + 1
        )

    def check_closing_bracket(self, file_content, index):
        if file_content[index] != "}":
            return self.check_closing_bracket(file_content, index + 1)
        else:
            return index

    def comment_out_function(self, file_content: str, start: int, end: int):
        # Add comment delimiters around the function code
        commented_function = "/*" + file_content[start : end + 1] + "*/"

        # Replace the function code with the commented version
        new_file_content = (
            file_content[:start] + commented_function + file_content[end + 1 :]
        )

        return new_file_content

    def clean_dot_value_error(self, file_contents: str, error_msg: str):
        line = None
        ori_error = error_msg
        error_msg = error_msg.split("\n")[1].strip().replace(";", "")

        if self.is_if_statement(error_msg):
            line_match = re.search(
                r"if\s*\(.*?\s*([\w_.]+\.\w+\.value\(.*?\)\(.*?\)).*\)",
                error_msg,
            )
            if line_match:
                line = line_match.group(1)
            else:
                _line = error_msg.split("if")[1].strip()[1:-1].replace("!", "")
                if any(
                    op in _line for op in ["==", "!=", "<=", ">=", "<", ">"]
                ):
                    line = re.split("==|!=|<=|>=|<|>", _line)[0].strip()
                else:
                    line = _line.strip()

        elif self.is_require(error_msg):
            line_match = regex.search(
                r"require\((.*?\.value\(.*?\)\(.*?\))\)", error_msg
            )
            line = line_match.group(1)
        else:
            line = error_msg

        if not line:
            raise Exception(
                f"Problematic dot value error line not found in the error message. {error_msg}"
            )

        function_ = line.replace("return", "").strip().split("value(")
        _split_dot = function_[0].split(".")
        # Filter out empty strings
        _split_dot = [x for x in _split_dot if x]

        contract_name = _split_dot[0]
        function_name = _split_dot[-1]

        _f = function_[1].split(")(")
        function_params = _f[1][0 : _f[1].rfind(")")].strip()

        num_args = self.count_arguments(function_params)

        function_header_regex = rf"function {function_name}\("
        complete_function_headers = regex.findall(
            rf"(function {function_name}\([^{{]+)", file_contents
        )

        for complete_function_header in complete_function_headers:
            _header: str = (
                complete_function_header[0]
                if len(complete_function_header) > 1
                and complete_function_header[1] == ""
                else complete_function_header
            )

            function_args_match = regex.search(
                r"\(([^)]*)\)", complete_function_header
            )

            if not function_args_match:
                continue

            header_args = function_args_match.group(1)
            header_num_args = self.count_arguments(header_args)

            if (
                header_num_args == num_args
                and "payable" not in complete_function_header
                and "internal" not in complete_function_header
            ):
                new_function_header = _header.replace(")", ") payable ", 1)
                updated_file_contents = file_contents.replace(
                    _header, new_function_header, 1
                )
                return updated_file_contents

        raise Exception(
            f"Function header not found in the contract code. {error_msg}"
        )

    def clean_parse_error(self, file_contents: str, error_msg: str) -> str:
        line_number = error_msg.split(".sol:")[1].split(":")[0]

        file_split = file_contents.splitlines()

        # search up
        _add_to_index = self.search_up_for_semi_colon_and_underscorce(
            file_split, int(line_number)
        )

        file_split[_add_to_index] = file_split[_add_to_index] + ";"

        corrected_code = "\n".join(file_split)

        return corrected_code

    def search_up_for_semi_colon_and_underscorce(self, file_content, index):
        if "_" in file_content[index] and ";" not in file_content[index]:
            return index
        else:
            return self.search_up_for_semi_colon_and_underscorce(
                file_content, index - 1
            )

    def clean_constructor_error(self, file_contents: str, error_msg: str):
        # Extract the problematic line from the error message
        line_regex = r"\n\s*(.*);\n\s*\^"
        line_match = re.search(line_regex, error_msg)
        if line_match:
            line = line_match.group(1)

            # Extract the constructor call
            constructor_call_regex = r"\(new (\w+)\)\.value"
            constructor_call_match = re.search(constructor_call_regex, line)
            if constructor_call_match:
                contract_name = constructor_call_match.group(1)

                # print(f"Contract: {contract_name}")

                # Count the number of arguments in the problematic line
                function_args_regex = r"\(([^)]+)\)"
                function_args_match = re.findall(function_args_regex, line)
                if function_args_match:
                    num_args = self.count_arguments(function_args_match[-1])

                    # Find the constructor with the same number of arguments
                    constructor_header_regex = rf"constructor\((.*?)\)"
                    constructor_headers = re.findall(
                        constructor_header_regex, file_contents
                    )

                    for header_args in constructor_headers:
                        header_num_args = self.count_arguments(header_args)

                        if header_num_args == num_args:
                            new_constructor_header = (
                                rf"constructor({header_args}) payable "
                            )
                            constructor_header = rf"constructor({header_args})"
                            updated_contract_code = re.sub(
                                re.escape(constructor_header),
                                new_constructor_header,
                                file_contents,
                            )
                            return updated_contract_code
                else:
                    raise Exception(
                        "Arguments not found in the problematic line."
                    )
            else:
                raise Exception(
                    "Constructor call not found in the problematic line."
                )
        else:
            raise Exception("Problematic line not found in the error message.")

        return None

    def is_payable_error(self, error_msg):
        # Regex pattern to match the specific TypeError
        error_pattern = r"TypeError: Member \"value\" not found or not visible after argument-dependent lookup"
        match = re.search(error_pattern, error_msg)

        return bool(match)

    def is_payable_constructor_error(self, error_msg):
        # Regex pattern to match the specific TypeError
        pattern_regex = r"\(new (\w+)\)\.value"
        pattern_match = re.search(pattern_regex, error_msg)
        return bool(pattern_match)

    def is_function_override_payable_error(self, error_msg):
        pattern = 'TypeError: Overriding function changes state mutability from "payable" to "nonpayable"'

        return pattern in error_msg

    def is_division_by_zero(self, error_msg):
        pattern = "TypeError: Division by zero."

        return pattern in error_msg

    def clean_add_param_description(
        self, contract_code: str, error_message: str
    ) -> str:
        # Create a regex pattern to match the parameter name in the error message
        param_pattern = r"param (\w+)"

        # Find the first match in the error message
        match = re.search(param_pattern, error_message)

        param = match.group(1)
        # Create a regex pattern to find the @param line
        param_pattern = rf"(@param {param}\s*)$"

        # Define a function to add the description if not already present
        def replacement_function(match):
            if not re.search(rf"@param {param}\s+\S+", match.group(0)):
                return f"@param {param} {param}\n"
            return match.group(0)

        # Update the contract code by replacing the matched lines
        updated_contract_code = re.sub(
            param_pattern,
            replacement_function,
            contract_code,
            flags=re.MULTILINE,
        )

        return updated_contract_code

    def check_solc_error_json(
        self,
        file_content: str,
        file_path: str,
        solc_version: str,
        solc_bin_path: str = None,
    ) -> Tuple[bool, str]:
        has_error = False
        updated = None

        head, tail = os.path.split(file_path)

        if version.parse(solc_version) >= version.parse("0.4.11"):
            stdout, stderr = self.check_solc_error_new(
                file_content, solc_version, tail
            )
        else:
            stdout, stderr = self.check_solc_error_legacy(
                file_content, file_path, solc_version, tail
            )

        # Parse the JSON output from solc
        if stdout:
            try:
                pattern = f"Switched global version to {solc_version}\n"
                if pattern in stdout:
                    stdout = stdout.split(pattern)[1].strip("\n")

                compilation_result = json.loads(stdout)
            except json.JSONDecodeError:
                raise Exception(
                    f"Error parsing solc output for {file_path}: {stdout}"
                )

            # Check for errors
            if "errors" in compilation_result:
                errors = compilation_result["errors"]
                _errors = [e for e in errors if e["severity"] == "error"]

                if len(_errors) == 0:
                    return has_error, file_content

                for error in _errors:
                    formatted_message: str = error["formattedMessage"]
                    message = error["message"]
                    line_number = "no line number"
                    has_error = True

                    if self.is_payable_error(formatted_message):
                        line_number = formatted_message.split(".sol:")[1].split(
                            ":"
                        )[0]
                        if self.is_payable_constructor_error(formatted_message):
                            updated = self.clean_constructor_error(
                                file_content, formatted_message
                            )
                        else:
                            updated = self.clean_dot_value_error(
                                file_content, formatted_message
                            )
                    elif self.is_semi_colon_parenthesis(formatted_message):
                        line_number = formatted_message.split(".sol:")[1].split(
                            ":"
                        )[0]
                        updated = self.clean_parse_error(
                            file_content, formatted_message
                        )
                    elif "DocstringParsingError" == error["type"]:
                        updated = self.clean_add_param_description(
                            file_content, formatted_message
                        )
                    elif self.is_function_override_payable_error(
                        formatted_message
                    ):
                        updated = self.clean_overriding_payable_error(
                            file_content, formatted_message
                        )
                    elif self.is_division_by_zero(formatted_message):
                        updated = self.clean_division_by_zero_error(
                            file_content, formatted_message
                        )
                    elif "Undeclared identifier" in message:
                        updated = self.clean_undeclared_identifier(
                            file_content, formatted_message
                        )
                    else:
                        line_number = formatted_message.split(".sol:")[1].split(
                            ":"
                        )[0]
                        raise Exception(
                            f"Error found in {file_path}\n \tError at line {line_number}: {message}\n {formatted_message}"
                        )

                    if updated:
                        (
                            _has_error,
                            _updated,
                        ) = self.check_solc_error_json(
                            updated, file_path, solc_version
                        )
                        if not _has_error:
                            updated = _updated
                            has_error = _has_error

            return has_error, updated if updated else file_content

        elif stderr:
            logger.error(stderr)

    def check_solc_error_new(
        self, file_content: str, solc_version: str, tail: str
    ):
        standard_json_input = {
            "language": "Solidity",
            "sources": {tail: {"content": file_content}},
            "settings": {
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
            },
        }

        standard_json_input_str = json.dumps(standard_json_input)

        if self.check_with_docker:
            stdout, stderr, exit_code = compile_with_docker(
                solc_version, standard_json_input_str
            )
        else:
            command = f"solc --standard-json"

            stdout, stderr, exit_code = run_subprocess(
                f"{command}",
                input_data=standard_json_input_str,
            )

        return stdout, stderr

    def check_solc_error_legacy(
        self, file_contents: str, file_path: str, solc_version: str, tail: str
    ):
        head, tail = os.path.split(file_path)
        temp_file_path = os.path.join(f"{head}/tmp", f"{tail}")

        with tempfile.NamedTemporaryFile(
            suffix=".sol", delete=False
        ) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_contents.encode())
        # Create a temporary file with the contract content
        # with open(temp_file_path, "w") as temp_file:
        #     temp_file.write(file_contents)

        # full_temp_path = os.path.abspath(temp_file_path)

        if self.check_with_docker:
            container_name = f"solc-select-solc-{uuid.uuid4()}"
            docker_run_command = (
                f"docker run --rm --name {container_name} -v {temp_file_path}:{temp_file_path} -i -a stdin -a stdout -a stderr solc_select_solc"
                f" /bin/bash -c 'solc-select use {solc_version} && solc --combined-json abi,bin {temp_file_path}'"
            )

            stdout, stderr, exit_code = run_subprocess(
                f"{docker_run_command}",
            )

            # stdout, stderr, exit_code = compile_with_docker(
            #     solc_version, "", f"--combined-json abi,bin {full_temp_path}"
            # )
        else:
            command = f"solc --combined-json abi,bin {temp_file_path}"

            # change_solc_version(version)
            stdout, stderr, exit_code = run_subprocess(
                f"{command}",
            )

        # Remove the temporary file
        os.remove(temp_file_path)

        return stdout, stderr

        # # Parse the JSON output from solc
        # if stdout:
        #     try:
        #         pattern = f"Switched global version to {solc_version}\n"
        #         if pattern in stdout:
        #             stdout = stdout.split(pattern)[1].strip("\n")

        #         compilation_result = json.loads(stdout)
        #     except json.JSONDecodeError:
        #         raise Exception(
        #             f"Error parsing solc output for {file_path}: {stdout}"
        #         )
        # elif stderr:
        #     logger.error(stderr)

        # # Check for errors
        # if exit_code != 0:
        #     error_lines = stderr.split("\n")
        #     for error_line in error_lines:
        #         if "Error:" in error_line:
        #             logger.error(f"Error found in {file_path}\n \t{error_line}")

        # # Parse the JSON output from solc
        # else:
        #     try:
        #         compilation_result = json.loads(stdout)
        #     except json.JSONDecodeError:
        #         logger.error(
        #             f"Error parsing solc output for {file_path}: {stdout}"
        #         )
        #         return

        #     # Check for errors
        #     if "errors" in compilation_result:
        #         errors = compilation_result["errors"]
        #         for error in errors:
        #             if error["severity"] == "error":
        #                 formatted_message: str = error["formattedMessage"]
        #                 line_number = formatted_message.split(".sol:")[1].split(
        #                     ":"
        #                 )[0]
        #                 message = error["message"]
        #                 logger.error(
        #                     f"Error found in {file_path}\n \tError at line {line_number}: {message}\n {formatted_message}"
        # )

    def clean(
        self,
        file_path: str,
        total_files: int,
        solidity_version: str = "0",
        shared_processed_files: ValueProxy = None,
        lock=None,
        clean_type: CleanType = 0,
    ) -> None:
        try:
            _version_fixed = None
            _version = None

            with open(file_path, "r") as f:
                file_content = f.read()

            if solidity_version != "0":
                _version = solidity_version

                change_solc_version(_version)

            else:
                _version = check_solidity_file_version(file_path)

            if _version == None:
                if is_pragma_invalid(file_content):
                    file_content, _version_fixed = fix_pragma(file_content)
                if _version_fixed == None:
                    _version, file_content = self.insert_pragma_solidity(
                        file_path
                    )
                else:
                    _version = _version_fixed

            if clean_type == CleanType.constructor_enum:
                _cleansed = self._check_constructor_emit(
                    file_path, _version, file_content
                )
            elif clean_type == CleanType.solc_error:
                _, _cleansed = self.check_solc_error_json(
                    file_content, file_path, _version
                )
            elif clean_type == CleanType.all:
                _, _file_content = self.check_solc_error_json(
                    file_content, file_path, _version
                )
                _cleansed = self._check_constructor_emit(
                    file_path, _version, _file_content
                )
                _, _cleansed = self.check_solc_error_json(
                    _cleansed, file_path, _version
                )

            with open(file_path, "w") as f:
                f.write(_cleansed)

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
            logger.exception(f"Error processing file: {file_path}\n")
            logger.exception(f"{str(e)}\n")

    def _check_constructor_emit(self, path, _version, file_content: str):
        updated = None

        if version.parse(_version) < version.parse("0.4.22"):
            # Get the contract names
            contract_names = self.get_contract_names_legacy(file_content)

            # Replace constructors for each contract
            updated = self.replace_constructors(file_content, contract_names)
        else:
            # Get the contract names
            contract_names = self.get_contract_names(
                path, file_content, _version
            )

            # Replace constructors for each contract
            updated = self.replace_old_to_new_constructors(
                file_content, contract_names
            )

        if version.parse(_version) < version.parse("0.4.21"):
            updated = (
                updated.replace("emit ", "")
                if updated
                else file_content.replace("emit ", "")
            )

        return updated

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
            result = self.clean(
                file_path=Path(file_path),
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

                self.progress_updater.print_progress_bar(
                    shared_processed_files.value,
                    total_files,
                    prefix="All done! exporting...",
                    suffix="All done! exporting...",
                )
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
