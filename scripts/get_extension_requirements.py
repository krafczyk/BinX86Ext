import argparse
import os
import sys
import subprocess
import re
import csv

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)
parser.add_argument("-d", "--definitions", help="The file containing instruction definitions. Should be a .csv file", default="instructions.csv")

args = parser.parse_args()

# Input Validation
if not os.path.isfile(args.input):
    print(f"Input file {args.input} doesn't exist or is a directory!")
    sys.exit(0)

if not os.path.isfile(args.definitions):
    print(f"Definitions file {args.definitions} doesn't exist or is a directory!")
    sys.exit(0)

input_file = args.input
definitions_file = args.definitions

# Disassembler
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

# Load instruction definition data
instruction_definitions_raw = []
with open(definitions_file, 'r') as def_file:
    def_reader = csv.reader(def_file, delimiter=',', quotechar='"')
    begin = True
    for row in def_reader:
        if begin:
            begin = False
            continue
        row[5] = row[5].split('|')
        instruction_definitions_raw.append(row)

# Clean instruction definitions
instruction_def_name_dict = {}
unsupported_instructions = ['repz']
for row in instruction_definitions_raw:
    name = row[0].lower()
    if name in unsupported_instructions:
        continue
    if name not in instruction_def_name_dict:
        instruction_def_name_dict[name] = [row]
    else:
        instruction_def_name_dict[name].append(row)

inst_def_count = {}
for name in sorted(list(instruction_def_name_dict.keys())):
    inst_def_count[name] = len(instruction_def_name_dict[name])

# Disassemble input file
disassembly = disassemble(input_file).decode()

# Extract instructions and match with definitions
instruction_heading_matcher = re.compile(r'^ [0-9a-f]*:$')

inst_count_dict = {}
unsupported_inst_encounters = {}

for line in disassembly.split('\n'):
    tab_list = line.split('\t')
    if len(tab_list) == 3:
        if instruction_heading_matcher.match(tab_list[0]):
            inst_name_portion = tab_list[2].strip()
            inst_name = inst_name_portion.split(' ')[0]
            if inst_name in unsupported_instructions:
                if inst_name not in unsupported_inst_encounters:
                    unsupported_inst_encounters[inst_name] = 1
                else:
                    unsupported_inst_encounters[inst_name] += 1
            if inst_name not in inst_count_dict:
                inst_count_dict[inst_name] = 1
            else:
                inst_count_dict[inst_name] += 1

for key in sorted(list(inst_count_dict.keys())):
    print(f'{key} -> {inst_count_dict[key]}')

if len(unsupported_inst_encounters) != 0:
    print("WARNING: The following instructions were encountered which are not supported")
    for key in sorted(list(unsupported_inst_encounters)):
        print(f'{key} -> {unsupported_inst_encounters[key]} times')

