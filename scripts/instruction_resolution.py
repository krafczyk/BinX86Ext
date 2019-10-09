# Module imports
import argparse
import os
import sys
import csv
import library as lib
import re

# Argument parsing
parser = argparse.ArgumentParser("Resolve instruction definitions to byte sequences")

parser.add_argument("-d", "--definitions", help="The instruction definitions file to process", type=str, required=True)

args = parser.parse_args()

definitions_file = args.definitions

# User input validation
if not os.path.isfile(definitions_file):
    sys.stderr.write(f"Definitions file {definitions_file} doesn't exist.")
    sys.exit(1)

# Read in instruction definitions
definitions = []
with open(definitions_file, 'r') as def_file:
    def_reader = csv.reader(def_file, quotechar='"', delimiter=',')
    begin = True
    for row in def_reader:
        if begin:
            begin = False
            continue
        definitions.append(row)

# Iterate through each instruction
unique_initial_bytes = lib.counting_dict()
byte_ib_matcher = re.compile('^[0-9A-F][0-9A-F]/ib')
byte_p_matcher = re.compile('^[0-9A-F][0-9A-F]\+')
byte_s_matcher = re.compile('^[0-9A-F][0-9A-F]/[0-9]')
for inst in definitions:
    # Input pre-processing We fix known problems here
    opcode_def_raw = inst[1]
    opcode_def_raw = opcode_def_raw.replace('LLIG', 'LIG')
    opcode_def_raw = opcode_def_raw.replace('/ r', '/r')
    opcode_def_raw = opcode_def_raw.replace(' ib', '/ib')
    opcode_def_raw = opcode_def_raw.replace('VEX.LZ. ', 'VEX.LX.')
    if byte_ib_matcher.match(opcode_def_raw):
        opcode_def_raw = opcode_def_raw.replace('/ib', ' /ib')
    if byte_p_matcher.match(opcode_def_raw):
        opcode_def_raw = opcode_def_raw.replace('+', ' +')
    if byte_s_matcher.match(opcode_def_raw):
        opcode_def_raw = opcode_def_raw.replace('/', ' /')

    opcode_def = opcode_def_raw.split(' ')
    unique_initial_bytes[opcode_def[0]] += 1
    if opcode_def[0] == 'VEX.LZ.':
        print(opcode_def)

print("Unique initial bytes")
for key in sorted(list(unique_initial_bytes.keys())):
    print(f"{key} -> {unique_initial_bytes[key]}")
