from configparser import ConfigParser
from dataclasses import dataclass
from enum import Enum
from functools import partial
from multiprocessing import Manager, Pool, cpu_count
from multiprocessing.managers import ValueProxy
import os
from pathlib import Path
from typing import Optional
from extensions.logger import LoggerSetup
from .utils.helpers import get_logging_instance

from solidifi.solidifi import Solidifi

from .utils.progress_updater import ProgressUpdater


class BugType(Enum):
    reentrancy = 1
    timestamp_dependency = 2
    unchecked_send = 3
    transaction_order = 5
    arithmetic = 6
    tx_origin = 7


@dataclass
class BugInfo(object):
    name: str
    id: int


class BugInjector:
    def __init__(self) -> None:
        self.progress_updater = ProgressUpdater()
        self.solidifi = Solidifi()
        self.logger = LoggerSetup.get_logger()

    def inject(
        self,
        file_path: str,
        bug_type: BugType,
        output_path: str = "test/output",
        shared_processed_files=None,
        lock=None,
        total_files=None,
    ) -> None:
        # Set up the logger for this child process
        _logger = get_logging_instance("bug_injector")
        try:
            _bug_info = self._get_bug_info(bug_type)

            if not _bug_info:
                # print(f"Bug info for {bug_type} not found in the .conf file")
                return

            head, tail = os.path.split(file_path)

            self.solidifi.inject(file_path, tail, _bug_info.name, output_path)

            if shared_processed_files and lock and total_files is not None:
                with lock:
                    shared_processed_files.value += 1
                    self.progress_updater.print_progress_bar(
                        shared_processed_files.value,
                        total_files,
                        prefix="Progress:",
                        suffix="Complete",
                    )

        except Exception as e:
            _logger.error(f"Error found in file {file_path}: {e}")

    def inject_multiple_concurrently(
        self,
        directory: str,
        bug_type: BugType,
        output_path: str = "test/output",
        num_of_process: int = -1,
    ) -> None:
        """inject selected bug type concurrently using multiprocess pool

        Args:
            directory (str): directory of all files to be injected with bugs
            bug_type (BugType): bug type defined by BugType class
        """
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
                    for chunk_result in pool.imap_unordered(
                        partial(
                            self._inject_it,
                            bug_type=bug_type,
                            output_path=output_path,
                            shared_processed_files=shared_processed_files,
                            lock=lock,
                            total_files=total_files,
                        ),
                        chunks,
                    ):
                        pass
                self.progress_updater.print_progress_bar(
                    shared_processed_files.value, total_files, is_done=True
                )
        except Exception as e:
            self.logger.exception(e)

    def _inject_it(
        self,
        chunk,
        bug_type,
        output_path,
        shared_processed_files,
        lock,
        total_files,
    ):
        return [
            self.inject(
                Path(file_path),
                bug_type,
                Path(output_path),
                shared_processed_files,
                lock,
                total_files,
            )
            for file_path in chunk
        ]

    def _get_bug_info(
        self, bug_type: BugType, config_path: str = "bug_types.conf"
    ) -> Optional[BugInfo]:
        config = ConfigParser()
        config.read(config_path)

        for section in config.sections():
            bug_type_id = config.getint(section, "bug_type_id")
            bug_type_name = config.get(section, "bug_type")

            if bug_type_id == bug_type.value:
                return BugInfo(name=bug_type_name, id=bug_type_id)

        return None
