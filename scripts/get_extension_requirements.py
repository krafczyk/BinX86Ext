import argparse
import os
import sys
import subprocess
import re
import csv

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)
parser.add_argument("-d", "--definitions", help="The file containing instruction definitions. Should be a .csv file", default="instructions_fixed.csv")

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
    def objdump_disassemble(binary_path):
        global objdump_location
        disassembly_lines = subprocess.check_output([objdump_location,
                                                     '--disassemble',
                                                     '-M', 'intel',
                                                     binary_path]).decode().split('\n')

        file_mode = None
        match_res = re.search(r'file format ([\S]*)', disassembly_lines[1])
        if match_res is None:
            print(f"Wrongly formatted output!")
            return None
        file_types_64 = ['elf64-x86-64']
        file_type = match_res.group(1)
        if file_type in file_types_64:
            file_mode = '64'
        else:
            print(f"Unsupported file type {file_type}!")
            return None

        # Extract instructions and match with definitions
        instruction_heading_matcher = re.compile(r'^ [0-9a-f]*:$')
        instruction_list = []
        for line in disassembly_lines:
            tab_list = line.split('\t')
            if len(tab_list) == 3:
                if instruction_heading_matcher.match(tab_list[0]):
                    # We have a line which is an instruction
                    inst_name_portion = tab_list[2].strip()
                    inst_name = inst_name_portion.split(' ')[0]

                    # Get byte stream
                    inst_bytes = tab_list[1].strip().upper().split(' ')
                    instruction_list.append((inst_name, inst_bytes, inst_name_portion))

        return (file_mode, instruction_list)
    disassemble = objdump_disassemble


if disassemble is None:
    print("Couldn't find an appropriate disassembly tool")
    sys.exit(1)

# Load instruction definition data
definitions_raw = {}
supported_duplicates = ['JZ', 'LEAVE', 'POP', 'REP']
def_col_idx = {'name':0, 'opcode':1, 'instruction':2,
                  '64-val':3, '32-val':4, 'cpuid':5, 'val-mask':6}
with open(definitions_file, 'r') as def_file:
    def_reader = csv.reader(def_file, delimiter=',', quotechar='"')
    begin = True
    for row in def_reader:
        if begin:
            begin = False
            continue
        def_hash = hash(row[def_col_idx['opcode']]+row[def_col_idx['instruction']])
        if row[def_col_idx['cpuid']] == '':
            row[def_col_idx['cpuid']] = []
        else:
            row[def_col_idx['cpuid']] = row[def_col_idx['cpuid']].split('|')
        if def_hash in definitions_raw:
            if row[def_col_idx['name']] not in supported_duplicates:
                print("ERROR: instruction definitions had a hash collision")
                print(f"row {row}")
                print(f"collided with {definitions_raw[def_hash]}")
                sys.exit(1)
        else:
            definitions_raw[def_hash] = row

# Build values/masks for each instruction
plain_byte_matcher = re.compile('^[0-9A-F][0-9A-F]$')
immediate_operands = ['ib', 'iw', 'id', 'io' ]
opcode_byte_modifiers = ['+rb', '+rw', '+rd', '+ro']
code_segment_offset = [('cb', 1), ('cw', 2), ('cd', 4), ('cp', 6), ('co', 8), ('ct', 10)]
digit_matcher = re.compile('^/[0-7]$')
for def_hash in definitions_raw:
    # Initialize values and masks variables
    valmasks = [[]]

    # Retrieve instruction definition
    definition = definitions_raw[def_hash]
    opcode = definition[def_col_idx['opcode']]
    opcode_parts = opcode.split(' ')

    op_i = 0
    ex_prefix_defined = False

    # Go through remaining opcode_parts
    last_simple_i = op_i # We need to track this as +rb, +rw etcc modify the opcode.
    mod_rm_i = -1
    while op_i < len(opcode_parts):
        if plain_byte_matcher.match(opcode_parts[op_i]):
            # We have a simple byte.
            for valmask in valmasks:
                valmask.append((int(opcode_parts[op_i],16), 0xFF))
            last_simple_i = op_i
            op_i += 1
        elif 'EX' in opcode_parts[op_i]:
            # We have a REX, VEX, EVEX prefix.
            if 'REX' == opcode_parts[op_i][0:3]:
                # REX prefix
                if 'REX' == opcode_parts[op_i]:
                    for valmask in valmasks:
                        valmask.append((0x40, 0xF0))
                elif 'REX.W' == opcode_parts[op_i] or 'REX.w' == opcode_parts[op_i]:
                    for valmask in valmasks:
                        valmask.append((0x48, 0xF8))
                elif 'REX.R' == opcode_parts[op_i]:
                    for valmask in valmasks:
                        valmask.append((0x42, 0xF2))
                else:
                    raise RuntimeError("Unrecognized REX prefix!")
                op_i += 1
            elif 'VEX' == opcode_parts[op_i][0:3]:
                # VEX prefix
                if len(valmasks) > 1:
                    raise RuntimeError("Should only be one valmask at this point!")
                # Determine if we need to
                vex_parts = opcode_parts[op_i].split('.')[1:]
                three_byte_only = False

                # VEX.L
                if vex_parts[0] == '128':
                    vex_l = 0
                    vex_l_mask = 1
                elif vex_parts[0] == '256':
                    vex_l = 1
                    vex_l_mask = 1
                elif vex_parts[0] == 'LIG':
                    # I'll just default this to 0..
                    vex_l = 0
                    vex_l_mask = 0

                # VEX.pp
                if '66' in vex_parts:
                    vex_pp = int('01', 2)
                    vex_pp_mask = 0x3
                elif 'F3' in vex_parts:
                    vex_pp = int('10', 2)
                    vex_pp_mask = 0x3
                elif 'F2' in vex_parts:
                    vex_pp = int('11', 2)
                    vex_pp_mask = 0x3
                else:
                    vex_pp = 0
                    vex_pp_mask = 0

                # VEX.mmmmm
                vex_mmmmm_mask = 0x1F
                if '0F' in vex_parts:
                    vex_mmmmm = int('00001', 2)
                    three_byte_only = True
                elif '0F38' in vex_parts:
                    vex_mmmmm = int('00010', 2)
                    three_byte_only = True
                elif '0F3A' in vex_parts:
                    vex_mmmmm = int('00011', 2)
                    three_byte_only = True
                else:
                    vex_mmmmm = 0 # I use this to imply that it isn't needed.

                # VEX.W
                if 'W0' in vex_parts:
                    vex_w = 0
                    vex_w_mask = 1
                elif 'W1' in vex_parts:
                    vex_w = 1
                    vex_w_mask = 1
                    three_byte_only = True
                elif 'WIG' in vex_parts:
                    vex_w = 0
                    vex_w_mask = 0

                if not three_byte_only and vex_mmmmm == 0:
                    # Can use the 2-byte version
                    valmask_base = valmasks[0].copy()
                    valmasks[0].append((0xC4, 0xFF))
                    valmasks[0].append(((vex_l << 2)+vex_pp,
                                        (vex_l_mask << 2)+vex_pp_mask))

                    valmasks.append(valmask_base)
                    valmasks[1].append((0xC5, 0xFF))
                    valmasks[1].append((vex_mmmmm, vex_mmmmm_mask))
                    valmasks[1].append(((vex_w << 7)+(vex_l << 2)+vex_pp,
                                        (vex_w_mask << 7)+(vex_l_mask << 2)+vex_pp_mask))
                else:
                    # Must use the 3-byte version only
                    valmasks[0].append((0xC5, 0xFF))
                    valmasks[0].append((vex_mmmmm, vex_mmmmm_mask))
                    valmasks[0].append(((vex_w << 7)+(vex_l << 2)+vex_pp,
                                        (vex_w_mask << 7)+(vex_l_mask << 2)+vex_pp_mask))

                op_i += 1
            elif 'EVEX' == opcode_parts[op_i][0:4]:
                # EVEX prefix
                if len(valmasks) > 1:
                    raise RuntimeError("Should only be one valmask at this point!")
                # Determine if we need to
                evex_parts = opcode_parts[op_i].split('.')[1:]

                print(evex_parts)

                # EVEX.LL
                if evex_parts[0] == '128':
                    evex_ll = 0
                    evex_ll_mask = 0x3
                elif evex_parts[0] == '256':
                    evex_ll = 1
                    evex_ll_mask = 0x3
                elif evex_parts[0] == '512':
                    evex_ll = 2
                    evex_ll_mask = 0x3
                elif vex_parts[0] == 'LIG':
                    # I'll just default this to 0..
                    evex_ll = 0
                    evex_ll_mask = 0

                # EVEX.pp
                if '66' in evex_parts:
                    evex_pp = int('01', 2)
                    evex_pp_mask = 0x3
                elif 'F3' in vex_parts:
                    evex_pp = int('10', 2)
                    evex_pp_mask = 0x3
                elif 'F2' in vex_parts:
                    evex_pp = int('11', 2)
                    evex_pp_mask = 0x3
                else:
                    evex_pp = 0
                    evex_pp_mask = 0

                # EVEX.mmm
                evex_mm_mask = 0x3
                if '0F' in vex_parts:
                    evex_mm = int('01', 2)
                elif '0F38' in vex_parts:
                    evex_mm = int('10', 2)
                elif '0F3A' in vex_parts:
                    evex_mm = int('11', 2)
                else:
                    raise RuntimeError("EVEX docs indicates the mm mask should never be empty.")

                # EVEX.W
                if 'W0' in evex_parts:
                    evex_w = 0
                    evex_w_mask = 1
                elif 'W1' in evex_parts:
                    evex_w = 1
                    evex_w_mask = 1
                elif 'WIG' in evex_parts:
                    evex_w = 0
                    evex_w_mask = 0

                for valmask in valmasks:
                    valmask.append((0x62, 0xFF))
                    valmask.append((evex_mm, evex_mm_mask))
                    valmask.append(((evex_w << 7)+evex_pp,(evex_w_mask << 7)+evex_pp_mask))
                    valmask.append(((evex_ll << 5), (evex_ll_mask << 5)))
                op_i += 1
            else:
                raise RuntimeError("Unrecognized prefix!!")
            # Indicate that a 'EX' prefix has been defined.
            ex_prefix_defined = True
        elif '/is4' == opcode_parts[op_i]:
            # is4 is another immediate byte
            for valmask in valmasks:
                valmask.append((0x0, 0x0))
            op_i += 1
        elif 'imm8' == opcode_parts[op_i]:
            # imm8 is an immediate byte
            for valmask in valmasks:
                valmask.append((0x0, 0x0))
            op_i += 1
        elif 'NP' == opcode_parts[op_i]:
            # Can't use 0x66, 0xF2, or 0xF3 with this instruction
            op_i += 1
        elif 'NFx' == opcode_parts[op_i]:
            # Can't use 0xF2 or 0xF3 with this instruction
            op_i += 1
        elif True in [True if im_op in opcode_parts[op_i] else False for im_op in immediate_operands]:
            # we have an immediate operand
            found = False
            i = 0
            while i < len(immediate_operands):
                if immediate_operands[i] in opcode_parts[op_i]:
                    for j in range(2**i):
                        # Could be anything
                        for valmask in valmasks:
                            valmask.append((0x00, 0x00))
                    op_i += 2**i
                    found = True
                    break
                i += 1
            if not found:
                raise RuntimeError("Didn't correctly handle immediate operand!")
        elif True in [True if op_mod in opcode_parts[op_i] else False for op_mod in opcode_byte_modifiers]:
            for i in range(len(valmasks)):
                valmask = valmasks[i]
                valmask[-1] = (valmask[-1][0] & 0xF1, # Remove bottom 3 bits from value
                               valmask[-1][1] & 0xF1) # Remove bottom 3 bits from mask
            op_i += 1
        elif True in [True if cs_so in opcode_parts[op_i] else False for (cs_so, _) in code_segment_offset]:
            for (cs_so, cs_size) in code_segment_offset:
                if cs_so in opcode_parts[op_i]:
                    for valmask in valmasks:
                        for i in range(cs_size):
                            valmask.append((0x0, 0x0))
                    break
            op_i += 1
        elif digit_matcher.match(opcode_parts[op_i]):
            digit = int(opcode_parts[op_i][1:])
            # We add a val and mask for the ModR/M byte.
            # mmrrrbbb the digit goes into the reg(r) field.
            for valmask in valmasks:
                valmask.append((digit << 3,0x38))
            mod_rm_i = op_i # Record that we have a mod_rm byte.
            op_i += 1
        elif '/r' == opcode_parts[op_i]:
            # From manual: Indicates that the ModR/M byte of the instruction
            # contains a register operand and an r/m operand
            # This doesn't really change our processing of the ModR/M byte

            # We can however, add an 'open' modrm byte
            if mod_rm_i == -1:
                # No requirement on the value means the mask will zero it out.
                for valmask in valmasks:
                    valmask.append((0x00,0x00))
                op_i += 1
        elif '+i' == opcode_parts[op_i]:
            # We need to remove 3 bits from the previous opcode.
            for i in range(len(valmasks)):
                valmask = valmasks[i]
                valmask[-1] = (valmask[-1][0] & 0xF1, valmask[-1][1] & 0xF1)
            op_i += 1
        else:
            raise RuntimeError(f"Unrecognized opcode part {op_i} {opcode_parts[op_i]}")

    print(f"------- Instruction: {definition} ----------")
    for valmask in valmasks:
        report_string = ""
        first = True
        for (v,m) in valmask:
            if not first:
                report_string += ", "
            if first:
                first = False
            report_string += f"{v:02X}:{m:02X}"
        print(report_string)

    # Add val/mask to row
    definitions_raw[def_hash].append(valmasks)

# Group instruction definitions
def_name_dict = {}
unsupported_instructions = ['repz']
for def_hash in definitions_raw:
    definition = definitions_raw[def_hash]
    name = definition[def_col_idx['name']].lower()
    if name in unsupported_instructions:
        continue
    if name not in def_name_dict:
        def_name_dict[name] = [def_hash]
    else:
        def_name_dict[name].append(def_hash)

# Disassemble input file
(file_type, instruction_list) = disassemble(input_file)

# A list of unsupported instructions which were encountered and how often
unsupported_inst_encounters = {}

byte_matcher = re.compile(r'[0-9A-F][0-9A-F]')

extension_requirements = []

# Primary program loop. Here we are looping through each line of the disassembly output
inst_num = 0
for (inst_name, inst_bytes, inst_decode) in instruction_list:
    inst_num += 1
    # Check whether this instruction is unsupported
    if inst_name in unsupported_instructions:
        if inst_name not in unsupported_inst_encounters:
            unsupported_inst_encounters[inst_name] = 1
        else:
            unsupported_inst_encounters[inst_name] += 1
        continue

    print(f"==== New Instruction ({inst_num}) {inst_name} - {inst_bytes} - {inst_decode} =====")

    if file_type == '64':
        # Get list of candidate hashes
        cand_hashes = []
        for def_hash in def_name_dict[inst_name]:
            if definitions_raw[def_hash][def_col_idx['64-val']] == 'V':
                cand_hashes.append(def_hash)
        
        # Attempt to match each hash's valmask to the instruction bytes.
        i = 0
        while i < len(cand_hashes):
            # Fetch definition
            definition = definitions_raw[cand_hashes[i]]

            # Get valmasks
            valmasks = definition[def_col_idx['val-mask']]

            match = True
            for valmask in valmasks:
                for j in range(min(len(valmask),len(inst_bytes))):
                    (val, mask) = valmask[j]
                    inst_byte = int(inst_bytes[j], 16)
                    if (inst_byte&mask) != val:
                        match = False
                        break
                if match:
                    break
            if not match:
                del cand_hashes[i]
            else:
                i += 1

        print("Candidate definitions:")
        for cand_hash in cand_hashes:
            print(f"{definitions_raw[cand_hash]}")
    else:
        raise RuntimeError("binary types other than 64 bit are not supported at this time.")

if len(unsupported_inst_encounters) != 0:
    print("WARNING: The following instructions were encountered which are not supported")
    for key in sorted(list(unsupported_inst_encounters)):
        print(f'{key} -> {unsupported_inst_encounters[key]} times')

