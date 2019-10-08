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
instruction_definitions_raw = {}
supported_duplicates = ['JZ', 'LEAVE', 'POP', 'REP']
with open(definitions_file, 'r') as def_file:
    def_reader = csv.reader(def_file, delimiter=',', quotechar='"')
    begin = True
    for row in def_reader:
        if begin:
            begin = False
            continue
        inst_hash = hash(row[1]+row[2])
        row[5] = row[5].split('|')
        if inst_hash in instruction_definitions_raw:
            if row[0] not in supported_duplicates:
                print("ERROR: instruction definitions had a hash collision")
                print(f"row {row}")
                print(f"collided with {instruction_definitions_raw[inst_hash]}")
                sys.exit(1)
        else:
            instruction_definitions_raw[inst_hash] = row

# Clean instruction definitions
instruction_def_name_dict = {}
unsupported_instructions = ['repz']
for inst_hash in instruction_definitions_raw:
    row = instruction_definitions_raw[inst_hash]
    name = row[0].lower()
    if name in unsupported_instructions:
        continue
    if name not in instruction_def_name_dict:
        instruction_def_name_dict[name] = [inst_hash]
    else:
        instruction_def_name_dict[name].append(inst_hash)

# Disassemble input file
disassembly = disassemble(input_file).decode()

# Extract instructions and match with definitions
instruction_heading_matcher = re.compile(r'^ [0-9a-f]*:$')

unsupported_inst_encounters = {}

for line in disassembly.split('\n'):
    tab_list = line.split('\t')
    if len(tab_list) == 3:
        if instruction_heading_matcher.match(tab_list[0]):
            # We have a line which is an instruction
            inst_name_portion = tab_list[2].strip()
            inst_name = inst_name_portion.split(' ')[0]

            # Check whether this instruction is unsupported
            if inst_name in unsupported_instructions:
                if inst_name not in unsupported_inst_encounters:
                    unsupported_inst_encounters[inst_name] = 1
                else:
                    unsupported_inst_encounters[inst_name] += 1
                continue

            # Get byte stream
            inst_bytes = tab_list[1].strip().split(' ')
            print(f"instruction bytes: {inst_bytes}")

            # Check instructions with appropriate names
            inst_hashes = instruction_def_name_dict[inst_name]
            for inst_hash in inst_hashes:
                inst_def = instruction_definitions_raw[inst_hash]
                print(inst_def)

if len(unsupported_inst_encounters) != 0:
    print("WARNING: The following instructions were encountered which are not supported")
    for key in sorted(list(unsupported_inst_encounters)):
        print(f'{key} -> {unsupported_inst_encounters[key]} times')

