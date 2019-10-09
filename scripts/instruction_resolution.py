# Module imports
import argparse
import os
import sys

# Argument parsing
parser = argparse.ArgumentParser("Resolve instruction definitions to byte sequences")

parser.add_argument_group("-d", "--definitions", help="The instruction definitions file to process", type=str, required=True)

args = parser.parse_args()

definitions_file = args.definitions

# User input validation
if not os.path.isfile(definitions_file):
    sys.stderr.write(f"Definitions file {definitions_file} doesn't exist.")
    sys.exit(1)


