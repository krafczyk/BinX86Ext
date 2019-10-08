import argparse
import os
import sys
import subprocess

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
disassembler = None

print(subprocess.check_output(['which', 'objdump']))


print(f"File to inspect: {input_file}")
