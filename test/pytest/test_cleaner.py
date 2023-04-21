import pytest

from extensions.logger import LoggerSetup
from extensions.cleaner import CleanType, Cleaner


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    LoggerSetup(file_name="test_cleaner")


# @pytest.mark.parametrize(
#     "directory", ["test/files/contracts-dataset/Clean", "test/files/contracts-dataset/Etherscan_Contract/1-10k"]
# )
@pytest.mark.parametrize("directory", ["test/files/contracts-dataset/Clean"])
def test_check_concurrently(directory):
    cleaner = Cleaner()

    cleaner.clean_concurrently(directory)


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
        "test/files/contracts-dataset/Clean/2889.sol",
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
        "test/files/contracts-dataset/Clean/2536.sol",
        "test/files/contracts-dataset/Clean/2889.sol",
        "test/files/contracts-dataset/Clean/3500.sol",
    ],
)
def test_clean_list_solc(files):
    cleaner = Cleaner()

    cleaner.clean(files, 0, clean_type=CleanType.solc_error)


@pytest.mark.parametrize(
    "files", ["test/files/contracts-dataset/Clean/2363.sol"]
)
def test_clean_list_no_pragma(files):
    cleaner = Cleaner()

    cleaner.clean(files, 0, clean_type=CleanType.no_pragma)
