import csv
import json
import os
import shutil
import subprocess
import sys
import time

from extensions.utils.helpers import check_solidity_file_version

from .inject_file import preprocess_json_file
from .solidifi import Solidifi

def main(argv=None):
    # global cur_contr_file
    # global src_contr_file
    # global cur_contr_ast_data
    
    solidifi = Solidifi()
    
    solidifi.clear_globals()
    if argv is None:
        argv = sys.argv
    try:
        if 1 != len(sys.argv):
            if argv[1] in ('--help', '-h'):
                solidifi.printUsage(sys.argv[0])
        elif len(argv) == 1:
            print ("Type --help or -h for list of options on how to use SolidiFI")
            exit()
        start = time.time()        
    
        if  argv[1] in ('--inject', '-i'):
            if '-o' in argv:  # Check for -o option
                output_dir = argv[argv.index('-o') + 1]
            else:
                output_dir = os.getcwd()
                
            head, tail = os.path.split(argv[2])

            check_solidity_file_version(argv[2])
      
            process = subprocess.Popen(f"solc {argv[2]}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            exit_code = process.returncode
            
            if exit_code != 0:
                print(f'Solidity compiler returned an error (code: {exit_code}):')
                print(stderr.decode('utf-8'))
            if not(os.path.isfile(argv[2])):
                print("Specified source file does not exists")
    
            # buggy_dir = os.path.join(output_dir, "buggy", argv[3])
            # os.makedirs(buggy_dir, exist_ok=True)
            # buggy_file_path = os.path.join(buggy_dir, "buggy_" + tail)

            # if os.path.isfile(buggy_file_path):
            #     os.remove(buggy_file_path)
            # shutil.copyfile(argv[2],buggy_file_path)  
            # solidifi.src_contr_file = argv[2]
            # solidifi.cur_contr_file=buggy_file_path

            """Inject bugs using code tranforamtion approach"""
            #code_transform(cur_contr_file, argv[3])


            """Inject bugs using weakning security mechanisms approach"""
            #weaken_sec_mec(cur_contr_file, argv[3])
            
            #inject
            solidifi.inject(argv[2], tail, argv[3], output_dir)
            
            # tmp_buggy_file_path = os.path.join(buggy_dir,"tmp_buggy_"+tail)
            # if os.path.isfile(tmp_buggy_file_path):
            #     os.remove(tmp_buggy_file_path)
            # shutil.copyfile(buggy_file_path,tmp_buggy_file_path)  
            # solidifi.src_contr_file = tmp_buggy_file_path
            

            # """ Generate AST"""
            # ast_json_files_dir = os.path.join(output_dir, "ast")
            # os.makedirs(ast_json_files_dir, exist_ok=True)
            # ast_json_file = os.path.join(ast_json_files_dir, os.path.splitext(tail)[0] + ".json")
            
            
            # ast_cmd = "solc --ast-json {0} > {1}".format(solidifi.cur_contr_file,ast_json_file)
            # os.system(ast_cmd)
            # if not(os.path.isfile(ast_json_file)):
            #     print("unable to generate AST")
            #     exit()
            
            # preprocess_json_file(ast_json_file)

            # with open(ast_json_file) as fh:
            #     solidifi.cur_contr_ast_data = json.loads(fh.read())    

        
            # solidifi.inject_bug(argv[3])
            # csv_file = os.path.join(buggy_dir,"BugLog_"+tail[0:len(tail)-4]+".csv")
            # csv_columns = ['loc','length','bug type','approach']
            # try:
            #     with open(csv_file, 'w') as csvfile:
            #         writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            #         writer.writeheader()
            #         for data in solidifi.BugLog:
            #             writer.writerow(data)
            # except IOError:
            #     print("I/O error")
    
            # os.remove(tmp_buggy_file_path)
            end = time.time()
            return "%.2g" % (end-start)
            
    except  OSError as err:
        #print >>sys.stderr, err.msg
        #print >>sys.stderr, "for help use --help"
        return 2

def interior_main(opr, sc, bug_type):
    out = main(['solidifi' , opr, sc, bug_type])
    return out

if __name__ == "__main__":
    sys.exit(main())