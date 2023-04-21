from enum import Enum
from functools import partial
from multiprocessing import Manager, Pool, cpu_count
from multiprocessing.managers import ValueProxy
from pathlib import Path
import re
import traceback

from extensions.utils.helpers import check_solidity_file_version, run_subprocess
from extensions.utils.progress_updater import ProgressUpdater

class CleanType(Enum):
      others = 0
      constructor_enum = 1
      solc_error = 2
      no_pragma = 3


class Cleaner():
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
            pattern = r"contract\s+(\w+)(?:\s+is\s+\w+)*\s*{"
            matches = re.findall(pattern, file_contents, re.MULTILINE)
            return matches
      
      def get_matching_brace_indices(self, s, open_brace='{', close_brace='}'):
            stack = []
            brace_indices = []

            for i, c in enumerate(s):
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


      def replace_constructors(self, file_contents: str, contract_names: list[str]) -> str:
            for contract_name in contract_names:
                  # Match the contract block for the current contract name
                  contract_block_start_pattern = fr"contract\s+{contract_name}\s*(?:is\s+\w+\s*)*{{"
                  contract_block_start_match = re.search(contract_block_start_pattern, file_contents)

                  if contract_block_start_match:
                        start_index = contract_block_start_match.end() - 1
                        brace_indices = self.get_matching_brace_indices(file_contents)
                        end_index = None

                        for open_index, close_index in brace_indices:
                              if open_index == start_index:
                                    end_index = close_index
                                    break

                        contract_block = file_contents[start_index:end_index + 1]

                        # Match the constructor within the contract block
                        constructor_pattern = fr"constructor\((.*?)\)\s*public\s*{{"
                        constructor_match = re.search(constructor_pattern, contract_block, re.DOTALL)

                        if constructor_match:
                              new_constructor = f"function {contract_name}({constructor_match.group(1)}) public {{"
                              updated_contract_block = contract_block.replace(constructor_match.group(0), new_constructor)

                              # Replace the original contract block with the updated one in the file_contents
                              file_contents = file_contents.replace(contract_block, updated_contract_block)

            return file_contents
      
      def clean(self, path: str, total_files: int, solidity_version: str = "0", shared_processed_files: ValueProxy=None, lock=None, clean_type: CleanType = 0) -> None:
            
            try:
                  if solidity_version != "0":
                        _version = solidity_version
                  else:
                        _version = check_solidity_file_version(path)
                        
                  if _version == None:
                        _version = self.insert_pragma_solidity(path)
                  
                  with open(path, "r") as f:
                        file_contents = f.read()
                  
                  if clean_type == CleanType.constructor_enum:
                        self._check_constructor_emit(path, _version, file_contents)
                  elif clean_type == CleanType.solc_error:
                        stdout, stderr, exit_code = run_subprocess(f"solc {path}")
                        if exit_code != 0:
                              print(f'Solc encountered error compling file: {path}\n')
                              print(f'{str(stderr)}\n')
                              print(f'{str(stdout)}\n')
                        
                  if shared_processed_files and lock:
                        with lock:
                              shared_processed_files.value += 1
                              self.progress_updater.print_progress_bar(
                                    shared_processed_files.value,
                                    total_files,
                                    prefix='Progress:',
                                    suffix='Complete',
                              )
            except Exception as e:
                  print(f'Error processing file: {path}\n')
                  print(f'{str(e)}\n')

      def _check_constructor_emit(self, path, _version, file_contents):
            # Get the contract names
            contract_names = self.get_contract_names(file_contents)

                        # Replace constructors for each contract
            file_contents = self.replace_constructors(file_contents, contract_names)
                        
            version_number = int(_version.split(".")[2])
                        
            if version_number < 21:
                  file_contents = file_contents.replace("emit ", "")
                              
            with open(path, "w") as f:
                  f.write(file_contents)
                  
      def _clean_it(self, chunk, total_files, shared_processed_files=None, lock=None, clean_type: CleanType = 0):
            return [self.clean(path=Path(file_path), total_files=total_files,shared_processed_files=shared_processed_files, lock=lock, clean_type=clean_type) for file_path in chunk]
                  
      def clean_concurrently(self, directory: str, num_of_process: int = -1, clean_type: CleanType = 0):
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
                        shared_processed_files: ValueProxy = manager.Value('i', 0)
                        lock = manager.Lock()
                        # Create a pool of worker processes
                        with Pool(processes=num_of_process) as pool:
                        # Process each chunk in parallel
                              processed_files = 0
                              self.progress_updater.print_progress_bar(
                                    processed_files,
                                    total_files,
                                    prefix='Progress:',
                                    suffix='Complete',
                              )
                                    
                              for _ in pool.imap_unordered(
                                    partial(
                                    self._clean_it,
                                    total_files=total_files,
                                    shared_processed_files=shared_processed_files,
                                    lock=lock,
                                    clean_type=clean_type
                                    ),
                                    chunks,
                              ):
                                    pass
                                    # # Print the result of each file processing
                                    # for file_result in chunk_result:
                                    #       processed_files += 1
                                    #       self.progress_updater.print_progress_bar(
                                    #       processed_files,
                                    #       total_files,
                                    #       prefix="Progress:",
                                    #       suffix="Complete",
                                    #       )
            except Exception as e:
                  traceback.print_exc()