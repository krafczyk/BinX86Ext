import argparse
import os
import sys
import subprocess
import re

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)
parser.add_argument("-d", "--definitions", help="The file containing instruction definitions. Should be a .csv file", default="instructions.csv")

args = parser.parse_args()

if not os.path.isfile(args.input):
    print(f"Input file {args.input} doesn't exist or is a directory!")
    sys.exit(0)

if not os.path.isfile(args.definitions):
    print(f"Definitions file {args.definitions} doesn't exist or is a directory!")
    sys.exit(0)

input_file = args.input
definitions_file = args.definitions

# We need to find an appropriate dissassembler
disassemble = None

if disassemble is None:
    objdump_location = subprocess.check_output(['which', 'objdump']).decode().strip()
    disassemble = lambda binary_path: subprocess.check_output([objdump_location,
                                                               '--disassemble',
                                                               '-M', 'intel',
                                                               binary_path])

if disassemble is None:
    print("Couldn't find an appropriate disassembly tool")
    sys.exit(1)

print(f"File to inspect: {input_file}")

disassembly = disassemble(input_file).decode()

instruction_heading_matcher = re.compile(r'^ [0-9a-f]*:$')

inst_count_dict = {}

for line in disassembly.split('\n'):
    tab_list = line.split('\t')
    if len(tab_list) == 3:
        if instruction_heading_matcher.match(tab_list[0]):
            inst_name_portion = tab_list[2].strip()
            inst_name = inst_name_portion.split(' ')[0]
            if inst_name not in inst_count_dict:
                inst_count_dict[inst_name] = 1
            else:
                inst_count_dict[inst_name] += 1

for key in sorted(list(inst_count_dict.keys())):
    print(f'{key} -> {inst_count_dict[key]}')
