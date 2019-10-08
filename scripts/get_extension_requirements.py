import argparse

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)
parser.add_argument("-d", "--definitions", help="The file containing instruction definitions. Should be a .csv file", default="instructions.csv")

args = parser.parse_args()

# We need to find an appropriate dissassembler
disassembler = None



print(f"File to inspect: {args.input}")
