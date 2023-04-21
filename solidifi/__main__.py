import os
import subprocess
import sys
import time
from extensions.logger import LoggerSetup

from extensions.utils.helpers import check_solidity_file_version

from .solidifi import Solidifi


def main(argv=None):
    solidifi = Solidifi()

    solidifi.clear_globals()
    if argv is None:
        argv = sys.argv
    try:
        if 1 != len(sys.argv):
            if argv[1] in ("--help", "-h"):
                solidifi.printUsage(sys.argv[0])
        elif len(argv) == 1:
            print(
                "Type --help or -h for list of options on how to use SolidiFI"
            )
            exit()
        start = time.time()

        if argv[1] in ("--inject", "-i"):
            if "-o" in argv:  # Check for -o option
                output_dir = argv[argv.index("-o") + 1]
            else:
                output_dir = os.getcwd()

            head, tail = os.path.split(argv[2])

            check_solidity_file_version(argv[2])

            process = subprocess.Popen(
                f"solc {argv[2]}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate()
            exit_code = process.returncode

            if exit_code != 0:
                print(
                    f"Solidity compiler returned an error (code: {exit_code}):"
                )
                print(stderr.decode("utf-8"))
            if not (os.path.isfile(argv[2])):
                print("Specified source file does not exists")

            """Inject bugs using code tranforamtion approach"""
            # code_transform(cur_contr_file, argv[3])

            """Inject bugs using weakning security mechanisms approach"""
            # weaken_sec_mec(cur_contr_file, argv[3])

            # inject
            solidifi.inject(argv[2], tail, argv[3], output_dir)

            end = time.time()
            return "%.2g" % (end - start)

    except OSError as err:
        # print >>sys.stderr, err.msg
        # print >>sys.stderr, "for help use --help"
        logger.exception(err)
        return 2


def interior_main(opr, sc, bug_type):
    out = main(["solidifi", opr, sc, bug_type])
    return out


if __name__ == "__main__":
    logger_setup = LoggerSetup(file_name="solidifi")
    logger = logger_setup.get_logger(__name__)
    sys.exit(main())
