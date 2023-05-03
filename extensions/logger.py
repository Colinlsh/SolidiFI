import logging
import logging.handlers
import multiprocessing


class LoggerSetup:
    _instance = None
    _logger = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        file_name: str = "cleaner",
        output_dir: str = "test/logs",
        log_level: int = logging.INFO,
        ext: str = "log",
    ):
        self.log_level = log_level
        self.file_name = file_name
        self.output_dir = output_dir
        self.file_full_path = f"{self.output_dir}/{self.file_name}.{ext}"

        if not hasattr(self, "initialized"):
            self.setup()
            self.initialized = True

    def setup(self):
        # Set up the logger
        LoggerSetup._logger = multiprocessing.get_logger()
        LoggerSetup._logger.setLevel(self.log_level)
        formatter = logging.Formatter(
            "[%(asctime)s| %(levelname)s| %(processName)s] %(message)s"
        )
        handler = logging.FileHandler(self.file_full_path)
        handler.setFormatter(formatter)

        # this bit will make sure you won't have
        # duplicated messages in the output
        if not len(LoggerSetup._logger.handlers):
            LoggerSetup._logger.addHandler(handler)

    @staticmethod
    def get_logger():
        return LoggerSetup._logger
