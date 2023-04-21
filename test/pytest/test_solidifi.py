import os
import shutil
import subprocess
import pytest
from extensions.utils.helpers import check_solidity_file_version
from solidifi.__main__ import main

from solidifi.solidifi import Solidifi


@pytest.mark.parametrize(
    "file_path, output_dir",
    [("test/files/contracts-dataset/ts/0.sol", "test/output")],
)
def test_inject(file_path, output_dir):
    argv = "solidifi -i test/files/contracts-dataset/ts/0.sol Timestamp-Dependency -o test/output".split()
    solidifi = Solidifi()

    head, tail = os.path.split(argv[2])

    _solidity_version = check_solidity_file_version(argv[2])

    # out = subprocess.getoutput(f"solc {argv[2]}")

    process = subprocess.Popen(
        f"solc {argv[2]}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    exit_code = process.returncode

    if exit_code != 0:
        print(f"Solidity compiler returned an error (code: {exit_code}):")
        print(stderr.decode("utf-8"))
    if not (os.path.isfile(argv[2])):
        print("Specified source file does not exists")

    buggy_dir = os.path.join(output_dir, "buggy", argv[3])
    os.makedirs(buggy_dir, exist_ok=True)
    buggy_file_path = os.path.join(buggy_dir, "buggy_" + tail)

    if os.path.isfile(buggy_file_path):
        os.remove(buggy_file_path)
    shutil.copyfile(argv[2], buggy_file_path)
    solidifi.src_contr_file = argv[2]
    solidifi.cur_contr_file = buggy_file_path

    solidifi.inject(argv[2], tail, argv[3], output_dir)


def test_main():
    _main = main("solidifi -i Timestamp-Dependency -o test/output".split())
