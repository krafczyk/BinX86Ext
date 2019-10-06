import csv
import argparse

parser = argparse.ArgumentParser("Instruction Verification")
parser.add_argument('-i', '--input', help="Input csv file", type=str, required=True)

args = parser.parse_args()

data = []
with open(args.input, 'r') as inputfile:
    csv_reader = csv.reader(inputfile, delimiter=',', quotechar='"')
    for row in csv_reader:
        data.append(row)

unique_flag_names = []
begin = True
for row in data:
    if begin:
        begin = False
        continue
    if row[5] != "":
        flags = row[5].split('|')
        for flag in flags:
            if flag not in unique_flag_names:
                unique_flag_names.append(flag)
unique_flag_names = sorted(unique_flag_names)

unique_inst_names = []
begin = True
for row in data:
    if begin:
        begin = False
        continue
    if row[0] not in unique_inst_names:
        unique_inst_names.append(row[0])
unique_inst_names = sorted(unique_inst_names)

unique_opcode_starts = []
begin = True
for row in data:
    if begin:
        begin = False
        continue
    initial_byte = row[1].split(' ')[0]
    if '.' in initial_byte:
        byte = initial_byte.split('.')[0]
    else:
        byte = initial_byte
    if byte not in unique_opcode_starts:
        unique_opcode_starts.append(byte)

print("Unique instruction names:")
for name in unique_inst_names:
    print(name)

print("Unique flag names:")
for flag in unique_flag_names:
    print(flag)

print("Unique Opcode starts:")
for byte in unique_opcode_starts:
    print(byte)
