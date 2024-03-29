import argparse
import os
import sys
import subprocess
import re
import csv
import progressbar
import library as lib

class InstructionDefinition(object):
    def_col_idx = {'name':0, 'opcode':1, 'instruction':2,
                   '64-val':3, '32-val':4, 'cpuid':5, 'val-mask':6}
    plain_byte_matcher = re.compile('^[0-9A-F][0-9A-F]$')
    immediate_operands = ['ib', 'iw', 'id', 'io' ]
    opcode_byte_modifiers = ['+rb', '+rw', '+rd', '+ro']
    code_segment_offset = [('cb', 1), ('cw', 2), ('cd', 4), ('cp', 6), ('co', 8), ('ct', 10)]
    digit_matcher = re.compile('^/[0-7]$')
    legacy_prefix_groups = [[0xF0, 0xF2, 0xF3],
                            [0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65, 0x2E, 0x3E],
                            [0x66],
                            [0x67]]
    pseudo_op_maps = [(['cmpeqps', 'cmpltps', 'cmpleps', 'cmpunordps',
                        'cmpneqps', 'cmpnltps', 'cmpnleps', 'cmpordps'],'cmpps'),
                      (['vcmpeqps', 'vcmpltps', 'vcmpleps', 'vcmpunordps',
                        'vcmpneqps', 'vcmpnltps', 'vcmpnleps', 'vcmpordps',
                        'vcmpeq_uqps', 'vcmpngeps', 'vcmpngtps', 'vcmpfalseps',
                        'vcmpneq_oqps', 'vcmpgeps', 'vcmpgtps', 'vcmptrueps',
                        'vcmpeq_osps', 'vcmplt_oqps', 'vcmple_oqps', 'vcmpunord_sps',
                        'vcmpneq_usps', 'vcmpnlt_uqps', 'vcmpnle_uqps', 'vcmpord_sps'
                        'vcmpeq_usps', 'vcmpnge_uqps', 'vcmpngt_uqps', 'vcmpfalse_osps',
                        'vcmpneq_osps', 'vcmpge_oqps', 'vcmpgt_oqps', 'vcmptrue_usps'], 'vcmpps'),
                      (['cmpeqss', 'cmpltss', 'cmpless', 'cmpunordss',
                        'cmpneqss', 'cmpnltss', 'cmpnless', 'cmpordss'], 'cmpss'),
                      (['vcmpeqss', 'vcmpltss', 'vcmpless', 'vcmpunordss',
                        'vcmpneqss', 'vcmpnltss', 'vcmpnless', 'vcmpordss',
                        'vcmpeq_uqss', 'vcmpnegess', 'vcmpngtss', 'vcmpfalsess',
                        'vcmpneq_oqss', 'vcmpgess', 'vcmpgtss', 'vcmptruess',
                        'vcmpeq_osss', 'vcmplt_oqss', 'vcmple_oqss', 'vcmpunord_sss',
                        'vcmpneq_usss', 'vcmpnlt_uqss', 'vcmpnle_uqss', 'vcmpord_sss',
                        'vcmpeq_usss', 'vcmpeq_uqss', 'vcmpngt_uqss', 'vcmpfalse_osss',
                        'vcmpneq_osss', 'vcmpge_oqss', 'vcmpgt_oqss', 'vcmptrue_usss'], 'vcmpss'),
                      (['cmpeqpd', 'cmpltpd', 'cmplepd', 'cmpunordpd',
                        'cmpneqpd', 'cmpnltpd', 'cmpnlepd', 'cmpordpd'], 'cmppd'),
                      (['vcmpeqpd', 'vcmpltpd', 'vcmplepd', 'vcmpunordpd',
                        'vcmpneqpd', 'vcmpnltpd', 'vcmpnlepd', 'vcmpordpd',
                        'vcmpeq_uqpd', 'vcmpngepd', 'vcmpngtpd', 'vcmpfalsepd',
                        'vcmpneq_oqpd', 'vcmpgepd', 'vcmpgtpd', 'vcmptruepd',
                        'vcmpeq_ospd', 'vcmplt_oqpd', 'vcmple_oqpd', 'vcmpunord_spd',
                        'vcmpneq_uspd', 'vcmpnlt_uqpd', 'vcmpnle_uqps', 'vcmpord_spd',
                        'vcmpeq_uspd', 'vcmpnge_uqpd', 'vcmpngt_uqpd', 'vcmpfalse_ospd',
                        'vcmpneq_ospd', 'vcmpge_oqpd', 'vcmpgt_oqpd', 'vcmptrue_uspd'], 'vcmppd'),
                      (['cmpeqsd', 'cmpltsd', 'cmplesd', 'cmpunordsd',
                        'cmpneqsd', 'cmpnltsd', 'cmpnlesd', 'cmpordsd'], 'cmpsd'),
                      (['vcmpeqsd', 'vcmpltsd', 'vcmplesd', 'vcmpunordsd',
                        'vcmpneqsd', 'vcmpnltsd', 'vcmpnlesd', 'vcmpordsd',
                        'vcmpeq_uqsd', 'vcmpngesd', 'vcmpngtsd', 'vcmpfalsesd',
                        'vcmpneq_oqsd', 'vcmpgesd', 'vcmpgtsd', 'vcmptruesd',
                        'vcmpeq_ossd', 'vcmplt_oqsd', 'vcmple_oqsd', 'vcmpunord_ssd',
                        'vcmpneq_ussd', 'vcmpnlt_uqsd', 'vcmpnle_uqsd', 'vcmpord_ssd',
                        'vcmpeq_ussd', 'vcmpnge_uqsd', 'vcmpngt_uqsd', 'vcmpfalse_ossd',
                        'vcmpneq_ossd', 'vcmpge_oqsd', 'vcmpgt_oqsd', 'vcmptrue_ussd'], 'vcmpsd'),
                      (['vpcmpeq', 'vpcmplt', 'vpcmple', 'vpcmpneq',
                        'vppcmpnlt', 'vpcmpnle'], 'vpcmp'),
                      (['pclmullqlqdq', 'pclmulhqlqdq', 'pclmullqhqdq', 'pclmulhqhqdq'], 'pclmulqdq'),
                      (['vpclmullqlqdq', 'vpclmulhqlqdq', 'vpclmullqhqdq', 'vpclmulhqhqdq'], 'vpclmulqdq')]
    pseudo_op_maps += [ ([ ('vpcmp'+var+Type) for var in [ 'eq', 'lt', 'le', 'false', 'neq', 'nlt', 'nle', 'true' ]],('vpcmp'+Type)) for Type in [ 'b', 'd', 'q', 'w', 'ub', 'ud', 'uq', 'uw' ]]

    def __init__(self, inrow=[]):
        self._name = inrow[def_col_idx['name']]
        self._opcode = inrow[def_col_idx['opcode']]
        self._opcode_parts = self._opcode.split(' ')
        self._instruction = inrow[def_col_idx['instruction']]
        self._64val = inrow[def_col_idx['64-val']]
        self._32val = inrow[def_col_idx['32-val']]
        if inrow[def_col_idx['cpuid']] == '':
            self._cpuid = []
        else:
            self._cpuid = inrow[def_col_idx['cpuid']].split('|')
        self._valmasks = []
        self.build_valmasks()

    @property
    def def_hash(self):
        return hash(self.opcode+self.instruction)

    @property
    def name(self):
        return self._name

    @property
    def opcode(self):
        return self._opcode

    @property
    def instruction(self):
        return self._instruction

    @property
    def val64(self):
        return self._64val

    @property
    def val32(self):
        return self._32val

    @property
    def cpuid(self):
        return self._cpuid

    @property
    def valmasks(self):
        return self._valmasks

    # Build values/masks for this instruction
    def build_valmasks(self):
        # Initialize values and masks variables
        self._valmasks = [[]]
        valmasks = self._valmasks

        # Retrieve instruction definition
        op_i = 0
        ex_prefix_defined = False

        # Go through remaining opcode_parts
        last_simple_i = op_i # We need to track this as +rb, +rw etcc modify the opcode.
        mod_rm_i = -1
        while op_i < len(self.opcode_parts):
            if InstructionDefinition.plain_byte_matcher.match(self.opcode_parts[op_i]):
                # We have a simple byte.
                for valmask in valmasks:
                    valmask.append((int(self.opcode_parts[op_i],16), 0xFF))
                last_simple_i = op_i
                op_i += 1
            elif 'EX' in self.opcode_parts[op_i]:
                # We have a REX, VEX, EVEX prefix.
                if 'REX' == self.opcode_parts[op_i][0:3]:
                    # REX prefix
                    if 'REX' == self.opcode_parts[op_i]:
                        for valmask in valmasks:
                            valmask.append((0x40, 0xF0))
                    elif 'REX.W' == self.opcode_parts[op_i] or 'REX.w' == self.opcode_parts[op_i]:
                        for valmask in valmasks:
                            valmask.append((0x48, 0xF8))
                    elif 'REX.R' == self.opcode_parts[op_i]:
                        for valmask in valmasks:
                            valmask.append((0x42, 0xF2))
                    else:
                        raise RuntimeError("Unrecognized REX prefix!")
                    op_i += 1
                elif 'VEX' == self.opcode_parts[op_i][0:3]:
                    # VEX prefix
                    if len(valmasks) > 1:
                        raise RuntimeError("Should only be one valmask at this point!")
                    # Determine if we need to
                    vex_parts = self.opcode_parts[op_i].split('.')[1:]
                    three_byte_only = False

                    # VEX.L
                    if vex_parts[0] == '128':
                        vex_l = 0
                        vex_l_mask = 1
                    elif vex_parts[0] == '256':
                        vex_l = 1
                        vex_l_mask = 1
                    elif vex_parts[0] == 'LZ':
                        vex_l = 0
                        vex_l_mask = 1
                    elif vex_parts[0] == 'LIG':
                        # I'll just default this to 0..
                        vex_l = 0
                        vex_l_mask = 0
                    elif vex_parts[0] == 'L1':
                        vex_l = 1
                        vex_l_mask = 1
                    elif vex_parts[0] == 'L0':
                        vex_l = 0
                        vex_l_mask = 1
                    else:
                        raise RuntimeError(f"Unrecognized VEX.L! {vex_parts[0]} {self}")

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
                    else:
                        vex_w = 0
                        vex_w_mask = 1

                    if not three_byte_only:
                        # Can use the 2-byte version
                        valmask_base = valmasks[0].copy()
                        valmasks[0].append((0xC5, 0xFF))
                        valmasks[0].append(((vex_l << 2)+vex_pp,
                                            (vex_l_mask << 2)+vex_pp_mask))

                        valmasks.append(valmask_base)
                        valmasks[1].append((0xC4, 0xFF))
                        valmasks[1].append((vex_mmmmm, vex_mmmmm_mask))
                        valmasks[1].append(((vex_w << 7)+(vex_l << 2)+vex_pp,
                                            (vex_w_mask << 7)+(vex_l_mask << 2)+vex_pp_mask))
                    else:
                        # Must use the 3-byte version only
                        valmasks[0].append((0xC4, 0xFF))
                        valmasks[0].append((vex_mmmmm, vex_mmmmm_mask))
                        valmasks[0].append(((vex_w << 7)+(vex_l << 2)+vex_pp,
                                            (vex_w_mask << 7)+(vex_l_mask << 2)+vex_pp_mask))

                    op_i += 1
                elif 'EVEX' == self.opcode_parts[op_i][0:4]:
                    # EVEX prefix
                    if len(valmasks) > 1:
                        raise RuntimeError("Should only be one valmask at this point!")
                    # Determine if we need to
                    evex_parts = self.opcode_parts[op_i].split('.')[1:]

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
                    elif evex_parts[0] == 'LIG':
                        # I'll just default this to 0..
                        evex_ll = 0
                        evex_ll_mask = 0

                    # EVEX.pp
                    if '66' in evex_parts:
                        evex_pp = int('01', 2)
                        evex_pp_mask = 0x3
                    elif 'F3' in evex_parts:
                        evex_pp = int('10', 2)
                        evex_pp_mask = 0x3
                    elif 'F2' in evex_parts:
                        evex_pp = int('11', 2)
                        evex_pp_mask = 0x3
                    else:
                        evex_pp = 0
                        evex_pp_mask = 0

                    # EVEX.mmm
                    evex_mm_mask = 0x3
                    if '0F' in evex_parts:
                        evex_mm = int('01', 2)
                    elif '0F38' in evex_parts:
                        evex_mm = int('10', 2)
                    elif '0F3A' in evex_parts:
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
                    else:
                        # Lets look for this case until we're sure in the wild
                        evex_w = 0
                        evex_w_mask = 1
    
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
            elif '/is4' == self.opcode_parts[op_i]:
                # is4 is another immediate byte
                for valmask in valmasks:
                    valmask.append((0x0, 0x0))
                op_i += 1
            elif 'imm8' == self.opcode_parts[op_i]:
                # imm8 is an immediate byte
                for valmask in valmasks:
                    valmask.append((0x0, 0x0))
                op_i += 1
            elif 'NP' == self.opcode_parts[op_i]:
                # Can't use 0x66, 0xF2, or 0xF3 with this instruction
                op_i += 1
            elif 'NFx' == self.opcode_parts[op_i]:
                # Can't use 0xF2 or 0xF3 with this instruction
                op_i += 1
            elif True in [True if im_op in self.opcode_parts[op_i] else False for im_op in InstructionDefinition.immediate_operands]:
                # we have an immediate operand
                found = False
                i = 0
                while i < len(InstructionDefinition.immediate_operands):
                    if InstructionDefinition.immediate_operands[i] in self.opcode_parts[op_i]:
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
            elif True in [True if op_mod in self.opcode_parts[op_i] else False for op_mod in InstructionDefinition.opcode_byte_modifiers]:
                for i in range(len(valmasks)):
                    valmask = valmasks[i]
                    valmask[-1] = (valmask[-1][0] & 0xF8, # Remove bottom 3 bits from value
                                   valmask[-1][1] & 0xF8) # Remove bottom 3 bits from mask
                op_i += 1
            elif True in [True if cs_so in self.opcode_parts[op_i] else False for (cs_so, _) in InstructionDefinition.code_segment_offset]:
                for (cs_so, cs_size) in InstructionDefinition.code_segment_offset:
                    if cs_so in self.opcode_parts[op_i]:
                        for valmask in valmasks:
                            for i in range(cs_size):
                                valmask.append((0x0, 0x0))
                        break
                op_i += 1
            elif InstructionDefinition.digit_matcher.match(self.opcode_parts[op_i]):
                digit = int(self.opcode_parts[op_i][1:])
                # We add a val and mask for the ModR/M byte.
                # mmrrrbbb the digit goes into the reg(r) field.
                for valmask in valmasks:
                    valmask.append((digit << 3,0x38))
                mod_rm_i = op_i # Record that we have a mod_rm byte.
                op_i += 1
            elif '/r' == self.opcode_parts[op_i]:
                # From manual: Indicates that the ModR/M byte of the instruction
                # contains a register operand and an r/m operand
                # This doesn't really change our processing of the ModR/M byte

                # We can however, add an 'open' modrm byte
                if mod_rm_i == -1:
                    # No requirement on the value means the mask will zero it out.
                    for valmask in valmasks:
                        valmask.append((0x00,0x00))
                    op_i += 1
            elif '+i' == self.opcode_parts[op_i]:
                # We need to remove 3 bits from the previous opcode.
                for i in range(len(valmasks)):
                    valmask = valmasks[i]
                    valmask[-1] = (valmask[-1][0] & 0xF8, valmask[-1][1] & 0xF8)
                op_i += 1
            else:
                raise RuntimeError(f"Unrecognized opcode part {op_i} {self.opcode_parts[op_i]}")

    def valmask_string(self):
        res_string = ""
        begin = True
        for valmask in self.valmasks:
            if not begin:
                res_string += " | "
            if begin:
                begin = False
            valmask_string = ""
            begin_valmask = True
            for (val, mask) in valmask:
                if not begin_valmask:
                    valmask_string += ", "
                if begin_valmask:
                    begin_valmask = False
                valmask_string += f"{val:02X}:{mask:02X}"
            res_string += valmask_string
        return res_string

    @staticmethod
    def valmask_check_match(valmask, inst_bytes):
        match = True
        for j in range(min(len(valmask), len(inst_bytes))):
            (val, mask) = valmask[j]
            inst_byte = int(inst_bytes[j], 16)
            if (inst_byte&mask) != val:
                match = False
                break
        return match

    def plain_match_strategy(self, inst_bytes):
        # Check for match to instruction
        match = True
        for valmask in self.valmasks:
            match = InstructionDefinition.valmask_check_match(valmask, inst_bytes)
            if match:
                break
        return (match, 0)

    def extra_rex_match_strategy(self, inst_bytes):
        # Check for initial REX byte.
        val = 0x40
        mask = 0xF0

        if val == int(inst_bytes[0], 16)&mask:
            # we have an initial REX prefix
            match = True
            for valmask in self.valmasks:
                match = InstructionDefinition.valmask_check_match(valmask, inst_bytes[1:])
                if match:
                    break
            return (match, 1)
        else:
            return (False, 1)

    def extra_legacy_prefix_match_strategy(self, inst_bytes):
        if self.instruction.split(' ')[0] == 'NP':
            check_NP = True
        else:
            check_NP = False

        if self.instruction.split(' ')[0] == 'NFx':
            check_NFx = True
        else:
            check_NFx = False

        prefixes_exhausted = False
        num_prefixes = 0
        while not prefixes_exhausted:
            prefixes_exhausted = True
            prefix_search_terminate = False
            for legacy_prefix_group in InstructionDefinition.legacy_prefix_groups:
                for prefix in legacy_prefix_group:
                    if check_NP:
                        if prefix in [0x66, 0xF2, 0xF3]:
                            # These prefixes are not allowed for this instruction.
                            continue
                    if check_NFx:
                        if prefix in [0xF2, 0xF3]:
                            # These prefixes are not allowed for this instruction.
                            continue
    
                    if int(inst_bytes[num_prefixes],16) == prefix:
                        # This prefix is here!
                        prefixes_exhausted = False
                        prefix_search_terminate = True
                        num_prefixes += 1

                        match = True
                        for valmask in self.valmasks:
                            match = InstructionDefinition.valmask_check_match(valmask, inst_bytes[num_prefixes:])
                            if match:
                                break
                        if match:
                            return (match, num_prefixes)
                    if prefix_search_terminate:
                        break
                if prefix_search_terminate:
                    break
        # We didn't find a match..
        return (False, num_prefixes)

    def insert_rex_strategy(self, inst_bytes):
        for valmask in self.valmasks:
            # Test whether the initial byte in the definition is a legacy prefix.
            is_legacy_prefix = False
            v_i = 0
            i_i = 0
            for legacy_prefix_group in InstructionDefinition.legacy_prefix_groups:
                for prefix in legacy_prefix_group:
                    if valmask[v_i][0] == prefix:
                        is_legacy_prefix = True
                        break
                if is_legacy_prefix:
                    break
            if not is_legacy_prefix:
                return (False, 0)

            # Check for the matching prefix in the instruction bytes
            if valmask[v_i][0] != int(inst_bytes[i_i],16):
                return (False, 0)

            v_i += 1
            i_i += 1

            # Test for an inserted rex byte.
            if int(inst_bytes[i_i],16)&0xF0 != 0x40:
                return (False, 0)
            i_i += 1

            # Check for match on the rest.
            match = InstructionDefinition.valmask_check_match(valmask[v_i:], inst_bytes[i_i:])
            if match:
                break
        return (match, 1)

    def get_match_strategies(self):
        return [self.plain_match_strategy,
                self.extra_rex_match_strategy,
                self.extra_legacy_prefix_match_strategy,
                self.insert_rex_strategy]

    def check_for_match(self, inst_bytes, file_type='64'):
        # Check whether this instruction is appropriate for this file type
        if self.val64 != 'V':
            return False

        match = False
        strat_result = None
        for strategy in self.get_match_strategies():
            strat_result = strategy(inst_bytes)
            if strat_result[0]:
                return strat_result

        return strat_result

    @property
    def opcode_parts(self):
        return self._opcode_parts

    def __repr__(self):
        return f"{self._name} {self.opcode_parts} \"{self._instruction}\" 64:{self.val64} 32:{self.val32} {self.cpuid} {self.valmask_string()}"

parser = argparse.ArgumentParser("Tool to get the instruction extensions required for a given program.")

parser.add_argument("-i", "--input", help="The binary file to inspect", type=str, required=True)
parser.add_argument("-d", "--definitions", help="The file containing instruction definitions. Should be a .csv file", default="instructions_fixed.csv")
parser.add_argument("-v", "--verbose", help="Verbose output", action='store_true')
parser.add_argument("-p", "--progress", help="Show progress", action='store_true')
parser.add_argument("-c", "--careful", help="Scrutinize all instructions instead of just non-trivial requirement instructions", action='store_true')
parser.add_argument("--objdump-location", help="Location of object dump command to use", type=str)
parser.add_argument("--full-stats", help="Record and report full instruction stats", action='store_true')

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
verbose = args.verbose
progress = args.progress
careful = args.careful
full_stats = args.full_stats

# Disassembler
# We need to find an appropriate dissassembler
disassemble = None

if disassemble is None:
    if args.objdump_location is None:
        objdump_location = subprocess.check_output(['which', 'objdump']).decode().strip()
    else:
        objdump_location = args.objdump_location

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

    if verbose:
        print("==== Registering Instructions: ====")

    begin = True
    for row in def_reader:
        if begin:
            begin = False
            continue

        definition = InstructionDefinition(inrow=row)

        if definition.def_hash in definitions_raw:
            if row[def_col_idx['name']] not in supported_duplicates:
                print("ERROR: instruction definitions had a hash collision")
                print(f"row {row}")
                print(f"collided with {definitions_raw[def_hash]}")
                sys.exit(1)
        else:
            if verbose:
                print(f"{definition}")
            definitions_raw[definition.def_hash] = definition

# Group instruction definitions
def_name_dict = {}
unsupported_instructions = ['repz', 'data16', 'data32', 'movabs', 'endbr66', 'movbe']
for def_hash in definitions_raw:
    definition = definitions_raw[def_hash]
    name = definition.name.lower()
    if name in unsupported_instructions:
        continue
    if name not in def_name_dict:
        def_name_dict[name] = [def_hash]
    else:
        def_name_dict[name].append(def_hash)

# Disassemble input file
(file_type, instruction_list) = disassemble(input_file)


if file_type != '64':
    raise RuntimeError("binary types other than 64 bit are not supported at this time.")

# A list of unsupported instructions which were encountered and how often
unsupported_inst_encounters = {}

byte_matcher = re.compile(r'[0-9A-F][0-9A-F]')

extension_requirements = []
instruction_count = lib.counting_dict()

# Primary program loop. Here we are looping through each line of the disassembly output

if progress:
    bar_widgets = [
        progressbar.Bar(),
        progressbar.Counter(format='%(value)i/%(max_value)i')
    ]
    bar = progressbar.ProgressBar(max_value=len(instruction_list), widgets=bar_widgets, redirect_stdout=True)
    bar.start()

inst_mem_matcher = re.compile('m(32|64|128)')

inst_num = 0
for (inst_name, inst_bytes, inst_decode) in instruction_list:
    inst_num += 1
    if progress:
        bar.update(inst_num)
    # Check whether this instruction is unsupported
    if inst_name in unsupported_instructions:
        if inst_name not in unsupported_inst_encounters:
            unsupported_inst_encounters[inst_name] = 1
        else:
            unsupported_inst_encounters[inst_name] += 1
        continue

    # Get list of candidate hashes
    cand_records = []
    while True:
        try:
            for def_hash in def_name_dict[inst_name]:
                if definitions_raw[def_hash].val64 == 'V':
                    cand_records.append((def_hash,0))
            break
        except KeyError as e:
            tryagain = False
            for (pseudo_op_map,target) in InstructionDefinition.pseudo_op_maps:
                if inst_name in pseudo_op_map:
                    inst_name = target
                    tryagain = True
                    break
            if not tryagain:
                if inst_name in ['cs', 'ds']:
                    # Chance this is a jump with a segment override.
                    inst_name = inst_decode.split(' ')[1]
                    tryagain = True
            if not tryagain:
                print(f"Couldn't find instruction {inst_name}({inst_num})! {inst_bytes} {inst_decode}")
                raise e
        
    # Check whether any candidate has a non-trivial extension requirement
    if not args.careful:
        is_nontrivial = False
        for cand_record in cand_records:
            definition = definitions_raw[cand_record[0]]
            if definition.cpuid != []:
                is_nontrivial = True
                break
        if not is_nontrivial:
            # Skip trivial instruction
            continue

    # Attempt to match each hash's valmask to the instruction bytes.
    i = 0
    while i < len(cand_records):
        # Fetch definition
        definition = definitions_raw[cand_records[i][0]]

        def_match = definition.check_for_match(inst_bytes)
        if not def_match[0]:
            del cand_records[i]
        else:
            cand_records[i] = (cand_records[i][0], def_match[1])
            i += 1

    if len(cand_records) == 0:
        print("Problem instruction binary:")
        for byte in inst_bytes:
            by_num = int(byte, 16)
            print(f"{by_num:08b}")
        raise RuntimeError(f"No candidates for this instruction ({inst_num})! {inst_name} {inst_bytes}")

    # Prune list of candidates to the candidate which had the fewest additional prefixes
    fewest_prefixes = None
    for cand_record in cand_records:
        if fewest_prefixes is None:
            fewest_prefixes = cand_record[1]
        else:
            if cand_record[1] < fewest_prefixes:
                fewest_prefixes = cand_record[1]
    i = 0
    while i < len(cand_records):
        if cand_records[i][1] > fewest_prefixes:
            del cand_records[i]
        else:
            i += 1

    # Check that the remaining candidates have identical extension requirements
    uniform_requirements = True
    for i in range(len(cand_records)-1):
        def_i = definitions_raw[cand_records[i][0]]
        for j in range(i,len(cand_records)):
            def_j = definitions_raw[cand_records[j][0]]
            if def_i.cpuid != def_j.cpuid:
                uniform_requirements = False
                break
        if not uniform_requirements:
            break

    if not uniform_requirements:
        uniform_req_failure = True
        # Strategies to resolve Final ambiguities
        if len(cand_records) == 2:
            # Can do something for these cases.
            # Check for differing instruction statements.
            def_a = definitions_raw[cand_records[0][0]]
            def_b = definitions_raw[cand_records[1][0]]
            if def_a.instruction != def_b.instruction:
                res_a = inst_mem_matcher.search(def_a.instruction)
                res_b = inst_mem_matcher.search(def_b.instruction)
                # Check that one has a memory specifier and the other doesn't
                def_a_mem = True if inst_mem_matcher.search(def_a.instruction) else False
                def_b_mem = True if inst_mem_matcher.search(def_b.instruction) else False
                if def_a_mem != def_b_mem:
                    # Check that the disassembler tells us an operand is a memory pointer.
                    uniform_req_failure = False
                    if 'PTR' in inst_decode:
                        # We want the memory version
                        if def_a_mem:
                            # Eliminate b
                            del cand_records[1]
                        else:
                            # Eliminate a
                            del cand_records[0]
                    else:
                        # We want the xmm-ymm version
                        if def_a_mem:
                            # Eliminate a
                            del cand_records[0]
                        else:
                            # Eliminate b
                            del cand_records[1]

        if uniform_req_failure:
            print(f"Candidates for instruction ({inst_num}) {inst_name}, {inst_bytes}, {inst_decode}")
            for byte in inst_bytes:
                by_num = int(byte, 16)
                print(f"{by_num:08b}")
            for cand_record in cand_records:
                print(f"{definitions_raw[cand_record[0]]}")
            raise RuntimeError("Error, not all candidates have the same cpuid requirements!")

    cpuid_reqs = definitions_raw[cand_records[0][0]].cpuid
    if full_stats:
    	instruction_count[cand_records[0][0]] += 1
    if len(cpuid_reqs) != 0:
        if cpuid_reqs not in extension_requirements:
            extension_requirements.append(cpuid_reqs)

if progress:
    bar.finish()

if len(extension_requirements) == 0:
    print(f"No special extensions are required to run {input_file}")
else:
    if full_stats:
        print(f"Full Instruction Statistics:")
        def hash_cpuid(cpuid):
            hash_answer = 0
            for component in cpuid:
                hash_answer += hash(component)
            return hash_answer
        cpuid_name_hash_map = {}
        cpuid_hash_map = {}
        for def_hash in sorted(instruction_count.keys()):
            definition = definitions_raw[def_hash]
            cpuid_hash = hash_cpuid(definition.cpuid)
            if cpuid_hash not in cpuid_name_hash_map:
                cpuid_name_hash_map[cpuid_hash] = {}
            cpuid_name_hash_map[cpuid_hash][definition.name] = def_hash
            if cpuid_hash not in cpuid_hash_map:
                cpuid_hash_map[cpuid_hash] = definition.cpuid
            
        for cpuid_hash in sorted(list(cpuid_hash_map.keys())):
            cpuid = cpuid_hash_map[cpuid_hash]
            print(f"-- {cpuid} --")
            for name in sorted(list(cpuid_name_hash_map[cpuid_hash].keys())):
                definition = definitions_raw[cpuid_name_hash_map[cpuid_hash][name]]
                print(f"{definition.name} -> {instruction_count[cpuid_name_hash_map[cpuid_hash][name]]}")
    print("Extension Requirements:")
    for cpuid_reqs in extension_requirements:
        print(cpuid_reqs)

if len(unsupported_inst_encounters) != 0:
    print("WARNING: The following instructions were encountered which are not supported")
    for key in sorted(list(unsupported_inst_encounters)):
        print(f'{key} -> {unsupported_inst_encounters[key]} times')

