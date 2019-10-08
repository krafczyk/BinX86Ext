import argparse

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)

args = parser.parse_args()

print(f"File to inspect: {args.input}")
