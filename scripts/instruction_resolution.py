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
parser.add_argument("-o", "--output", help="Output file", type=str, required=False)

args = parser.parse_args()

definitions_file = args.definitions

# User input validation
if not os.path.isfile(definitions_file):
    sys.stderr.write(f"Definitions file {definitions_file} doesn't exist.")
    sys.exit(1)

# Read in instruction definitions
definitions = []
head_row = None
with open(definitions_file, 'r') as def_file:
    def_reader = csv.reader(def_file, quotechar='"', delimiter=',')
    begin = True
    for row in def_reader:
        if begin:
            begin = False
            head_row = row
            continue
        definitions.append(row)

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
matchers.append((re.compile(r' \+ '),
                 r' '))

# Iterate through each instruction
for i in range(len(definitions)):
    inst = definitions[i]
    # Input pre-processing We fix known problems here
    opcode_def_raw = inst[1].strip()
    for (matcher, replacement) in matchers:
        opcode_def_raw = matcher.sub(replacement, opcode_def_raw.strip()) 

    opcode_def = opcode_def_raw.split(' ')

    inst[1] = ' '.join(opcode_def)

# Write new rows to new destination
if args.output is not None:
    with open(args.output, 'w') as outputfile:
        csv_writer = csv.writer(outputfile, quotechar='"',delimiter=',')
        csv_writer.writerow(head_row)
        for row in definitions:
            csv_writer.writerow(row)
