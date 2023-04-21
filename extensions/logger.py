import logging

from .utils.helpers import get_current_time


class LoggerSetup:
    _instance = None

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
        logging.basicConfig(
            filename=self.file_full_path,
            filemode="a",
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=self.log_level,
        )

        logging.basicConfig(level=self.log_level)
        logger = logging.getLogger()
        logger.setLevel(self.log_level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Add a file handler to the logger
        file_handler = logging.FileHandler(self.file_full_path)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)  # This line was missing

    @staticmethod
    def get_logger(name):
        return logging.getLogger(name)
