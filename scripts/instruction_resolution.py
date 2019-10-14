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

unique_opcode_pieces = []

selection_opcode_pieces = []

plus_pieces = lib.counting_dict()

# A series of regular expression matchers to fix known problems. Order here matters.
matchers = []
matchers.append((re.compile(r'([0-9A-F][0-9A-F])(\+[rw]*)'),
                 r'\1 \2'))
matchers.append((re.compile(r'([0-9A-F][0-9A-F])(/[0-7])'),
                 r'\1 \2'))
matchers.append((re.compile(r'([0-9A-F][0-9A-F])(/r)'),
                 r'\1 \2'))
matchers.append((re.compile(r'([0-9A-F][0-9A-F])/ '),
                 r'\1 /'))
matchers.append((re.compile(r'LLIG'),
                 r'LIG'))
matchers.append((re.compile(r'0F38.0 '),
                 r'0F38.W0 '))
matchers.append((re.compile(r'38 30.WIG '),
                 r'38.WIG 30 '))
matchers.append((re.compile(r'0F 38.WIG '),
                 r'0F38.WIG '))
matchers.append((re.compile(r'(,|\*)'),
                 r''))
matchers.append((re.compile(r'660F'),
                 r'66.0F'))
matchers.append((re.compile(r' 0F3A '),
                 r' 0F 3A '))
matchers.append((re.compile(r' 0F38 '),
                 r' 0F 38 '))
matchers.append((re.compile(r'0f'),
                 r'0F'))
matchers.append((re.compile(r' / ([0-7])( |$)'),
                 r' /\1\2'))
matchers.append((re.compile(r'([0-9A-Z\.]*\.) ([0-9A-Z\.])'),
                 r'\1\2'))
matchers.append((re.compile(r'([0-9A-Z\.]*[0-9A-Z]) (\.[0-9A-Z\.]*)'),
                 r'\1\2'))
matchers.append((re.compile(r'/ r'),
                 r'/r'))
matchers.append((re.compile(r'/ ib'),
                 r'/ib'))
matchers.append((re.compile(r'/$'),
                 r'/r'))
matchers.append((re.compile(r' ib$'),
                 r' /ib'))
matchers.append((re.compile(r'\+ (rb|rw|rd|io|id|iw|cb|cw|cd)'),
                 r'+\1'))

# Iterate through each instruction
for inst in definitions:
    # Input pre-processing We fix known problems here
    opcode_def_raw = inst[1].strip()
    for (matcher, replacement) in matchers:
        opcode_def_raw = matcher.sub(replacement, opcode_def_raw.strip()) 

    opcode_def = opcode_def_raw.split(' ')

    #if len(opcode_def) >= 3:
    #    if opcode_def[2] == "/":
    #        print(inst[0])
    #        print(inst[1])
    #        print(opcode_def)

    for def_i in range(len(opcode_def)-1):
        if opcode_def[def_i] == '+':
            plus_pieces[opcode_def[def_i+1]] += 1

    for def_i in range(len(opcode_def)):
        if def_i > len(unique_opcode_pieces)-1:
            unique_opcode_pieces.append(lib.counting_dict())
        unique_opcode_pieces[def_i][opcode_def[def_i]] += 1

    #if opcode_def[0][0:4] == "EVEX":
    #    for def_i in range(len(opcode_def)):
    #        if def_i > len(selection_opcode_pieces)-1:
    #            selection_opcode_pieces.append(lib.counting_dict())
    #        selection_opcode_pieces[def_i][opcode_def[def_i]] += 1

print("Unique pieces")
for i in range(len(unique_opcode_pieces)):
    print(f"---- Piece {i} ----")
    for key in sorted(list(unique_opcode_pieces[i].keys())):
        print(f"[{key}] -> {unique_opcode_pieces[i][key]}")

print("Selection pieces")
for i in range(len(selection_opcode_pieces)):
    print(f"---- Piece {i} ----")
    for key in sorted(list(selection_opcode_pieces[i].keys())):
        print(f"[{key}] -> {selection_opcode_pieces[i][key]}")

print("Plus pieces")
for key in sorted(list(plus_pieces.keys())):
    print(f"[{key}] -> {plus_pieces[key]}")
