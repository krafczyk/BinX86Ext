import sys
import os
import argparse
import six
import re
import numpy as np
import math
import progressbar
import csv

#from pdfminer.pdfdocument import PDFDocument
#from pdfminer.pdfparser import PDFParser
from pdfminer.converter import PDFConverter
from pdfminer.layout import LTContainer
from pdfminer.layout import LTPage
from pdfminer.layout import LTText
from pdfminer.layout import LTLine
from pdfminer.layout import LTRect
from pdfminer.layout import LTCurve
from pdfminer.layout import LTFigure
from pdfminer.layout import LTImage
from pdfminer.layout import LTChar
from pdfminer.layout import LTTextLine
from pdfminer.layout import LTTextBox
from pdfminer.layout import LTTextBoxVertical
from pdfminer.layout import LTTextGroup
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import HTMLConverter
import pdfminer.utils as utils

class TextBox(object):
    dy = 0.1
    def __init__(self, text, x, y, width, height, font):
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.font = font.basefont

    def __repr__(self):
        return "(x={} y={} w={} h={} font={}) -> {}".format(self.x, self.y, self.width, self.height, self.font, self.text)

    def __lt__(self, other):
        if abs(self.y-other.y) < TextBox.dy:
            # Equal
            if self.x < other.x:
                return True
            else:
                return False
        elif self.y < other.y:
            return False
        else:
            return True

    def __gt__(self, other):
        if abs(self.y-other.y) > TextBox.dy:
            # Equal
            if self.x > other.x:
                return True
            else:
                return False
        elif self.y > other.y:
            return False
        else:
            return True

def join_boxes_and_text(text_box_list):
    text = []
    for text_box in text_box_list:
        decoded_text = text_box.text.decode('windows-1252', 'ignore')
        text.append(decoded_text.strip())
    return " ".join(text)

def dist_to_line_segment(line_segment, pt):
    p1 = line_segment[0]
    p2 = line_segment[1]
    p3 = pt
    u = ((p3[0]-p1[0])*(p2[0]-p1[0])+(p3[1]-p1[1])*(p2[1]-p1[1]))/(((p2[0]-p1[0])*(p2[0]-p1[0]))+((p2[1]-p1[1])*(p2[1]-p1[1])))
    
    if u < 0 or u > 1:
        # We're off the edge of the line segment
        dist = np.inf
        for line_pt in line_segment:
            dis = math.sqrt(((line_pt[0]-pt[0])*(line_pt[0]-pt[0]))+((line_pt[1]-pt[1])*(line_pt[1]-pt[1])))
            if dis < dist:
                dist = dis
        return dist
    else:
        pc = ((p1[0]+u*(p2[0]-p1[0])), (p1[1]+u*(p2[1]-p1[1])))
        return math.sqrt(((pc[0]-p3[0])*(pc[0]-p3[0]))+((pc[1]-p3[1])*(pc[1]-p3[1])))

def lines_intersect(seg_a, seg_b):
    p1 = seg_a[0]
    p2 = seg_a[1]
    p3 = seg_b[0]
    p4 = seg_b[1]
    denom = (p4[1]-p3[1])*(p2[0]-p1[0])-(p4[0]-p3[0])*(p2[1]-p1[1])
    # Check for lines parallel
    if denom == 0:
        return False

    ua = ((p4[0]-p3[0])*(p1[1]-p3[1])-(p4[1]-p3[1])*(p1[0]-p3[0]))/denom
    ub = ((p2[0]-p1[0])*(p1[1]-p3[1])-(p2[1]-p1[1])*(p1[0]-p3[0]))/denom

    if 0 < ua and ua < 1 and\
       0 < ub and ub < 1:
        return True
    else:
        return False

class Rectangle(object):
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def __repr__(self):
        return "Rectangle x={} y={} w={} h={}".format(self.x, self.y, self.w, self.h)

    def pt_intersects(self, point):
        (x,y) = point
        if x > self.x and x < self.x+self.w and\
           y > self.y and y < self.y+self.h:
            return True

    def get_corners(self):
        corners = [ (self.x, self.y),
                    (self.x, self.y+self.h),
                    (self.x+self.w, self.y+self.h),
                    (self.x+self.w, self.y) ]
        return corners

    def get_line_points(self):
        if self.w < self.h:
            # vertical line
            return [ (self.x+(self.w/2), self.y), (self.x+(self.w/2), self.y+self.h) ]
        else:
            # horizontal line
            return [ (self.x, self.y+(self.h/2)), (self.x+self.w, self.y+(self.h/2)) ]

    def dist(self, other):
        self_points = self.get_line_points()
        other_points = other.get_line_points()

        if lines_intersect(self_points, other_points):
            return 0

        D = np.inf
        for pt in self_points:
            for opt in other_points:
                a = (pt[0]-opt[0])
                b = (pt[1]-opt[1])
                dis = a*a+b*b
                if dis < D:
                    D = dis

        return D

    def intersects(self, other):
        if (self.x+self.w) < other.x or\
           (other.x+other.w) < self.x or\
           (self.y+self.h) < other.y or\
           (other.y+other.h) < self.y:
            return False
        else:
            return True

class Cell(object):
    dy = 0.05
    def __init__(self, boundaries, all_text_boxes):
        self.text_boxes = []
        self.boundaries = boundaries

        for box in all_text_boxes:
            (x,y) = (box.x, box.y)
            if x > boundaries[0][0] and x < boundaries[0][1] and\
               y > boundaries[1][0] and y < boundaries[1][1]:
                self.text_boxes.append(box)

        self.text_boxes = sorted(self.text_boxes)

        # Drop text boxes containing super scripts (font < size 8)
        i = 0
        while i < len(self.text_boxes):
            if self.text_boxes[i].height < 7.95:
                del self.text_boxes[i]
            else:
                i += 1

        # Merge text boxes next to each other.
        # We need to ignore font in this case.

        i = 0
        while i < len(self.text_boxes)-1:
            lbox = self.text_boxes[i]
            rbox = self.text_boxes[i+1]

            if abs(lbox.y-rbox.y) < Cell.dy:
                self.text_boxes[i].text = b" ".join([self.text_boxes[i].text.strip(),rbox.text.strip()])
                del self.text_boxes[i+1]
            else:
                i += 1

    def __repr__(self):
        rep = "Cell: {}<x<{} {}<y<{} text: ".format(self.boundaries[0][0], self.boundaries[0][1],
                                            self.boundaries[1][0], self.boundaries[1][1])
        for box in self.text_boxes:
            rep = " ".join([rep, str(box)])

        return rep


class RawTable(object):
    def __init__(self, line_list, text_boxes):
        self.vert_boundaries = []
        self.horiz_boundaries = []

        for line in line_list:
            if line.w < line.h:
                # vertical
                self.vert_boundaries.append(line.x+(line.w/2))
            else:
                # horizontal
                self.horiz_boundaries.append(line.y+(line.h/2))

        def drop_duplicates(the_list):
            i = 0
            while i < len(the_list)-1:
                if the_list[i] == the_list[i+1]:
                    del the_list[i+1]
                else:
                    i += 1

        self.vert_boundaries = sorted(self.vert_boundaries)
        drop_duplicates(self.vert_boundaries)

        self.horiz_boundaries = sorted(self.horiz_boundaries)
        drop_duplicates(self.horiz_boundaries)

        self.dim = (len(self.horiz_boundaries)-1, len(self.vert_boundaries)-1)

        self.cells = []

        for i in range(self.dim[0]):
            self.cells.append([])
            for j in range(self.dim[1]):
                y_bounds = (self.horiz_boundaries[self.dim[0]-i-1], self.horiz_boundaries[self.dim[0]-i])
                x_bounds = (self.vert_boundaries[j], self.vert_boundaries[j+1])
                self.cells[i].append(Cell([x_bounds, y_bounds], text_boxes))

    def __repr__(self):
        return "RawTable dim={} vert={} horiz={}".format(self.dim, self.vert_boundaries, self.horiz_boundaries)

    def show_table(self):
        for i in range(self.dim[0]):
            for j in range(self.dim[1]):
                print("i={} j={} {}".format(i, j, self.cells[i][j]))

class Instruction(object):
    support_64 = ["V", "I", "N.E.", "N.P", "N.I.", "N.S." ]
    support_32 = ["V", "I", "N.E."]
    non_instructions = ["Both", "and", "flags", "or"]

    def __init__(self, opcode, instruction, description,
                       bit_validity={32:"V", 64:"V"},
                       cpuid=None):
        self.opcode = opcode
        self.instruction = instruction
        self.inst = self.instruction.split(" ")[0]
        self.bit_validity = {}
        self.bit_validity[32] = Instruction.parse_validity_32(bit_validity[32])
        self.bit_validity[64] = Instruction.parse_validity_64(bit_validity[64])
        self.cpuid_flags = Instruction.parse_cpuid(cpuid)

    def __repr__(self):
        return "Instruction={} {}".format(self.inst, self.opcode)

    def write_to_csv(self, csv_writer):
        csv_writer.writerow([self.inst, self.opcode, self.instruction,
                              self.bit_validity[64], self.bit_validity[32],
                              '|'.join(self.cpuid_flags)])

    @staticmethod
    def write_header(csv_writer):
        csv_writer.writerow(['Instruction Name', 'Opcode', 'Instruction', '64-bit validity', '32-bit validity', 'CpuId Flags'])

    @staticmethod
    def parse_cpuid(cpuid):
        flags = []
        if cpuid is None:
            return flags
        for flag in cpuid:
            if flag in Instruction.non_instructions:
                continue
            else:
                flags.append(flag)
        i = 0
        while i < len(flags)-1:
            if len(flags[i+1]) == 1:
                # Join single letter to previous
                flags[i] += flags[i+1]
                del flags[i+1]
            elif flags[i][-1] == "-":
                #Join with next
                flags[i] = flags[i][:-1]
                flags[i] += flags[i+1]
                del flags[i+1]
            else:
                i += 1
        return flags

    @staticmethod
    def parse_validity_64(validity):
        validity = validity.replace(' ', '')
        if validity in Instruction.support_64:
            return validity
        if validity == "Valid" or validity == "Valid*":
            return "V"
        if validity == "Invalid" or validity == "Inv." or validity == "Invalid*":
            return "I"
        if validity == "NE":
            return "N.E."
        if validity == "V/N.E.":
            return "V"
        raise RuntimeError("64-bit validity {} unknown.".format(validity))

    @staticmethod
    def parse_validity_32(validity):
        validity = validity.replace(' ', '')
        if validity in Instruction.support_32:
            return validity
        if validity == "Valid" or validity == "Valid*":
            return "V"
        if validity == "Invalid" or validity == "Inv." or validity == "Invalid*":
            return "I"
        if validity == "NE" or validity == "N.E":
            return "N.E."
        if validity == "NA":
            return "N.A."
        raise RuntimeError("32-bit validity {} unknown.".format(validity))

    @classmethod
    def FromTable(cls, rawtable):
        # Determine what kind of Table the raw table is.

        if rawtable.dim[1] < 5:
            return []

        if rawtable.dim[0] < 1:
            return []

        cols = []

        for j in range(rawtable.dim[1]):
            text = None
            for box in rawtable.cells[0][j].text_boxes:
                if text is None:
                    text = box.text
                else:
                    text += box.text
            # No tables we're interested in have nothing in a top cell.
            if text is None or text == "":
                return []
            text = text.decode('windows-1252', 'ignore')
            # Remove spaces around '/' characters

            text = text.replace(' / ', '/')
            text = text.replace(' /', '/')
            text = text.replace('/ ', '/')
            text = text.strip()

            cols.append(text)

        #print("Found columns:")
        #for col in cols:
        #    print(col)

        def col_match_test(func, cols):
            for col in cols:
                if func(col):
                    return True
            return False

        the_type = None
        no_titles = False
        if (cols[0] == "Opcode/Instruction" or cols[0] == "OpcodeInstruction" or cols[0] == "Opcode*/Instruction") and (cols[3] == "CPUID Feature Flag" or cols[3] == "CPUIDFeature Flag" or cols[3] == "CPUID"):
            the_type = "A"
        elif (cols[0] == "Opcode" or cols[0] == "Opcode*" or cols[0] == "Opcode**" or cols[0] == "Opcode***") and cols[1] == "Instruction" and cols[2] == "Op/En" and (cols[3] == "64-bit Mode" or cols[3] == "64-Bit Mode"):
            the_type = "B"
        elif cols[0] == "Opcode/Instruction" and cols[3] == "Compat/Leg Mode":
            the_type = "C"
        elif (cols[0] == "Opcode" or cols[0] == "Opcode*") and cols[1] == "Instruction" and cols[2] == "64-Bit Mode":
            the_type = "D"

        elif (cols[0] == "Opcode" or cols[0] == "Opcode*" or cols[0] == "Opcode**") and cols[1] == "Instruction" and cols[2] == "Op/En" and cols[3] == "64/32bit Mode Support" and cols[4] == "CPUID Feature Flag":
            # Introduced because of table on page 1199
            the_type = "E"
        elif cols[0] == "Op/En" and cols[2] == "Operand 1":
            return []
        elif cols[0] == "Op/En" and cols[1] == "Operand 1":
            return []
        elif cols[0] == "Superscript Symbol":
            return []
        elif cols[1] == "0" and cols[2] == "1":
            return []
        elif cols[1] == "8" and cols[2] == "9":
            return []
        elif cols[1] == "pfx" and cols[2] == "0":
            return []
        elif cols[1] == "pfx" and cols[2] == "8":
            return []
        elif cols[0] == "mod" and cols[1] == "nnn":
            return []
        elif cols[0] == "Operand Size":
            return []
        elif cols[1] == "SRC" and cols[2] == "SRC":
            return []
        elif cols[0] == "Operating mode/size" and (cols[1] == "Operand 1" or cols[1] == "Operand1"):
            return []
        elif col_match_test(lambda x: True if '+' in x else False, cols):
            return []
        elif col_match_test(lambda x: True if 'Exponent' in x else False, cols):
            return []
        elif cols[1] == "Operation":
            return []
        elif col_match_test(lambda x: True if 'ordered' in x else False, cols):
            return []
        elif cols[0] == "Bit Value" and cols[1] == "State Name":
            return []
        elif cols[0] == "Bits":
            return []
        elif col_match_test(lambda x: True if 'Src1' in x else False, cols):
            return []
        elif col_match_test(lambda x: True if 'Parameter' in x else False, cols):
            return []
        elif 'EVEX' == cols[0][0:4] and ('AVX' in cols[3] and '512' in cols[3]):
            no_titles = True
            the_type = "A"
        elif 'VEX' == cols[0][0:3] and ('AVX' in cols[3]):
            no_titles = True
            the_type = "A"
        else:
            print("Column names:")
            for col in cols:
                print("({})".format(col))
            raise RuntimeError("Unrecognized Table")

        # Check if the final row contains a 'Note'
        skip_final = False
        if 'NOTES' == join_boxes_and_text(rawtable.cells[rawtable.dim[0]-1][0].text_boxes)[0:5]:
            skip_final = True

        result = []
        skip = False
        init_row = 1
        end_row = rawtable.dim[0]
        if no_titles:
            init_row = 0
        if skip_final:
            end_row = end_row-1
        for i in range(init_row,end_row):
            # In some cases, we must skip the second row since Tables stack opcode and instruction
            # With a line between.
            if skip:
                skip = False
                continue
            if the_type == "A":
                opcode_cell = rawtable.cells[i][0]
                num_opcode_cell_text_boxes = len(opcode_cell.text_boxes)
                if num_opcode_cell_text_boxes == 1:
                    fail = True
                    # Here, we test whether we're in the last row.
                    if i < rawtable.dim[0]-1:
                        # we check that the next line of the other cells is empty.
                        if join_boxes_and_text(rawtable.cells[i+1][1].text_boxes) == "" and\
                           join_boxes_and_text(rawtable.cells[i+1][2].text_boxes) == "" and\
                           join_boxes_and_text(rawtable.cells[i+1][3].text_boxes) == "" and\
                           join_boxes_and_text(rawtable.cells[i+1][4].text_boxes) == "":
                            opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes)
                            instruction = join_boxes_and_text(rawtable.cells[i+1][0].text_boxes)
                            fail = False

                    # Failure mode for this set of strange cases
                    if fail:
                        raise RuntimeError("There should be more lines of text for this box")
                    else:
                        # Skip the next row
                        skip = True
                elif num_opcode_cell_text_boxes == 2:
                    test_1 = rawtable.cells[i][0].text_boxes[0].text.decode('windows-1252', 'ignore')
                    if ('xmm' in test_1) or ('ymm' in test_1) or ('zmm' in test_1):
                        # This is a tricky situation where the Opcode was really left out.
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes)
                        inst_name = test_1.split(" ")[0]
                        # Check previous result for same instruction type.
                        if result[-1].inst == inst_name:
                            # Grab opcode from prior instruction
                            opcode = result[-1].opcode
                            # The only situation we've encountered this is for an EVEX instruction
                            # Thus, we need to double the number following EVEX from the previous
                            # instruction and we're done
                            opcode_list = opcode.split(" ")
                            prefix_list = opcode_list[0].split('.')
                            prefix_list[1] = str(int(prefix_list[1])*2)
                            opcode_list[0] = '.'.join(prefix_list)
                            opcode = " ".join(opcode_list)
                        else:
                            raise RuntimeError("Can't find a similar instruction!")
                    else:
                        opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:1])
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[1:2])
                elif num_opcode_cell_text_boxes == 3:
                    test_1 = rawtable.cells[i][0].text_boxes[1].text.decode('windows-1252', 'ignore')
                    if test_1[0:2] == "/r":
                        ## This signifies the first two rows are acutally the opcode.
                        opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:2])
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[2:3])
                    else:
                        opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:1])
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[1:3])
                elif num_opcode_cell_text_boxes == 4:
                    test_1 = rawtable.cells[i][0].text_boxes[1].text.decode('windows-1252', 'ignore')
                    if ('xmm' in test_1) or ('ymm' in test_1) or ('zmm' in test_1):
                        ## This signifies that the second line here is part of the instruction.
                        opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:1])
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[1:4])
                    else:
                        opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:2])
                        instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[2:4])
                elif num_opcode_cell_text_boxes == 5:
                    opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:2])
                    instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[2:5])
                elif num_opcode_cell_text_boxes == 0:
                    rawtable.show_table()
                    raise RuntimeError("No lines in the opcode cell!")
                else:
                    print("Textboxes:")
                    for box in rawtable.cells[i][0].text_boxes:
                        print(box)
                    raise RuntimeError("Too many lines of text for an opcode cell!")

                bit_validity_text = join_boxes_and_text(rawtable.cells[i][2].text_boxes)
                if bit_validity_text == "VV":
                    bit_validity_text = "V/V"
                bvt = bit_validity_text.split('/')
                if len(bvt) != 2:
                    raise RuntimeError("Bit validity ({}) should contain one '/' character.".format(bit_validity_text))
                bit_validity = {64: bvt[0].strip(), 32: bvt[1].strip()}
                cpuflags = join_boxes_and_text(rawtable.cells[i][3].text_boxes).split(" ")
                if cpuflags == ['']:
                    cpuflags = []
                description = join_boxes_and_text(rawtable.cells[i][4].text_boxes)

            elif the_type == "B":
                opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes)
                instruction = join_boxes_and_text(rawtable.cells[i][1].text_boxes)
                bit_validity = {}
                bit_validity[64] = join_boxes_and_text(rawtable.cells[i][3].text_boxes)
                bit_validity[32] = join_boxes_and_text(rawtable.cells[i][4].text_boxes)
                description = join_boxes_and_text(rawtable.cells[i][5].text_boxes)
                cpuflags = []
            elif the_type == "C":
                opcode_cell = rawtable.cells[i][0]
                num_opcode_cell_text_boxes = len(opcode_cell.text_boxes)
                if num_opcode_cell_text_boxes == 1:
                    raise RuntimeError("There should be more lines of text for this box")
                elif num_opcode_cell_text_boxes == 2:
                    opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:1])
                    instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[1:2])
                elif num_opcode_cell_text_boxes == 3:
                    opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:1])
                    instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[1:3])
                elif num_opcode_cell_text_boxes == 4:
                    opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes[0:2])
                    instruction = join_boxes_and_text(rawtable.cells[i][0].text_boxes[2:4])
                else:
                    print("Textboxes:")
                    for box in rawtable.cells[i][0].text_boxes:
                        print(box)
                    raise RuntimeError("Too many lines of text for an opcode cell!")

                bit_validity = {}
                bit_validity[64] = join_boxes_and_text(rawtable.cells[i][2].text_boxes)
                bit_validity[32] = join_boxes_and_text(rawtable.cells[i][3].text_boxes)
                description = join_boxes_and_text(rawtable.cells[i][4].text_boxes)
                cpuflags = []

            elif the_type == "D":
                opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes)
                instruction = join_boxes_and_text(rawtable.cells[i][1].text_boxes)
                bit_validity = {}
                bit_validity[64] = join_boxes_and_text(rawtable.cells[i][2].text_boxes)
                bit_validity[32] = join_boxes_and_text(rawtable.cells[i][3].text_boxes)
                description = join_boxes_and_text(rawtable.cells[i][4].text_boxes)
                cpuflags = []

            elif the_type == "E":
                opcode = join_boxes_and_text(rawtable.cells[i][0].text_boxes)
                instruction = join_boxes_and_text(rawtable.cells[i][1].text_boxes)
                bit_validity_text = join_boxes_and_text(rawtable.cells[i][3].text_boxes)
                if bit_validity_text == "VV":
                    bit_validity_text = "V/V"
                bvt = bit_validity_text.split('/')
                if len(bvt) != 2:
                    raise RuntimeError("Bit validity ({}) should contain one '/' character.".format(bit_validity_text))
                bit_validity = {64: bvt[0], 32: bvt[1]}
                cpuflags = join_boxes_and_text(rawtable.cells[i][4].text_boxes).split(" ")
                if cpuflags == ['']:
                    cpuflags = []
                description = join_boxes_and_text(rawtable.cells[i][5].text_boxes)


            if instruction[0:2] == "ib":
                opcode = " ".join([opcode,"ib"])
                instruction = instruction[2:]
            result.append(cls(opcode, instruction, description, bit_validity, cpuid=cpuflags))
        return result

##  TextConverter
##
class TextBoxStripper(HTMLConverter):

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1, laparams=None,
                 scale=1, fontscale=1.0, layoutmode='normal', showpageno=True,
                 pagemargin=50, imagewriter=None, debug=0,
                 rect_colors={'curve': 'black', 'page': 'gray'},
                 text_colors={'char': 'black'}):
        HTMLConverter.__init__(self, rsrcmgr, outfp, codec=codec, pageno=pageno,
                               laparams=laparams, scale=scale, fontscale=fontscale,
                               layoutmode=layoutmode, showpageno=showpageno,
                               pagemargin=pagemargin, imagewriter=imagewriter,
                               debug=debug, rect_colors=rect_colors,
                               text_colors=text_colors)
        self.text_boxes = []
        self.temp_text = None
        self.init_p = (0,0)
        self.prev_p = (0,0)
        self.space_thresh = .1
        self.merge_xthresh = 3
        self.merge_ythresh = 0.1
        self.rectangles = []
        self.tables = []
        self.thickness_thresh = 1
        self.dist_thresh = 10
        return

    def push_textbox(self, p, h, font, matrix):
        if self.temp_text is not None:
            (xt, yt) = utils.apply_matrix_pt(matrix, self.init_p)
            self.text_boxes.append(TextBox(self.temp_text, xt,
                                           yt, (p[0]-self.init_p[0])*matrix[0], h, font))
            self.temp_text = None

    def push_char(self, char, char_width, p, h, font, matrix):
        if char is None:
            # Handle end of rendering
            self.push_textbox(self.prev_p, h, font, matrix)
        else:
            if self.temp_text == None:
                # There is no text written for this render yet.
                self.temp_text = char
                self.init_p = p
                self.prev_p = (p[0]+char_width,p[1])
            else:
                # We need to test how far from the last character we are
                if p[0]-self.prev_p[0] > self.space_thresh:
                    # We are far enough away to warrant a new textbox
                    self.push_textbox(self.prev_p, h, font, matrix)
                    self.push_char(char, char_width, p, h, font, matrix)
                else:
                    # We want to add this char to the running text
                    self.temp_text += char
                    self.prev_p = (p[0]+char_width, p[1])

    def drop_empty_textboxes(self):
        i = 0
        while i < len(self.text_boxes) - 1:
            # Get byte string removing null bytes
            byte_string = self.text_boxes[i].text.replace(b'\x00', b'')
            # Decode for text.
            dec_text = byte_string.decode('windows-1252', 'ignore').strip()
            if dec_text == '':
                del self.text_boxes[i]
            else:
                i += 1

    def merge_textboxes(self):
        # For now, we only implement consecutive merging. Usually text boxes
        # Which need to be merged occur right after each other in the content
        # stream.
        i = 0
        while i < len(self.text_boxes) - 1:
            box_i = self.text_boxes[i]
            box_j = self.text_boxes[i+1]
            xp = box_i.x+box_i.width
            xt = box_j.x
            iterate = True
            # We only consider situations where the next text box is to the right
            # of the current text box.
            if box_i.font == box_j.font and\
               box_i.y == box_j.y and box_i.x < box_j.x:
                if abs(xp-xt) < self.merge_xthresh and\
                   abs(box_i.height-box_j.height) < self.merge_ythresh:
                    box_i.text += box_j.text
                    box_i.width = box_j.x+box_j.width-box_i.x
                    del self.text_boxes[i+1]
                    iterate = False
            if iterate:
                i += 1

    def build_tables(self):
        # Drop rectangles that aren't 'lines'
        i = 0
        while i < len(self.rectangles):
            rect = self.rectangles[i]
            if rect.h < self.thickness_thresh or\
               rect.w < self.thickness_thresh:
                i += 1
            else:
                del self.rectangles[i]

        # Create new line groups 
        # While we still have rectangles available
        while len(self.rectangles) > 0:
            # Start new group with first rectangle
            new_grp = [self.rectangles[0]]
            # Remove from old list.
            del self.rectangles[0]

            i = 0
            while i < len(self.rectangles):
                join = False
                # Check for intersection with any of the new group of rectangles
                for rect in new_grp:
                    dist = rect.dist(self.rectangles[i])
                    if dist <= self.dist_thresh:
                        join = True
                        break
                if join:
                    # If it intersected, add it to the new group
                    new_grp.append(self.rectangles[i])
                    del self.rectangles[i]
                    # Restart, since we've changed the group.
                    i = 0
                else:
                    # Advance to the next available rectangle
                    i += 1
            # Append the new group of the group list
            if len(new_grp) > 4:
                self.tables.append(RawTable(new_grp, self.text_boxes))
            else:
                # Too few lines to make a table..
                pass

        #for i in range(len(self.tables)):
        #    self.tables[i] = RawTable(self.tables[i])

    def write(self, text):
        return

    def write_text(self, text):
        #text = utils.compatible_encode_method(text, self.codec, 'ignore')
        #if six.PY3 and self.outfp_binary:
        #    text = text.encode()
        #self.outfp.write(text)
        return

    def render_string_horizontal(self, seq, matrix, pos,
                                 font, fontsize, scaling, charspace, wordspace,
                                 rise, dxscale, ncs, graphicstate):
        (x, y) = pos
        needcharspace = False
        h_est = fontsize*matrix[3] # We estimate the size of the font by multiplying the fontsize by the height scaling in the textmatrix.
        for obj in seq:
            if utils.isnumber(obj):
                x -= obj*dxscale
                needcharspace = True
            else:
                for (char, cid) in zip(obj,font.decode(obj)):
                    if needcharspace:
                        x += charspace
                    char_width = self.render_char(utils.translate_matrix(matrix, (x, y)),
                                                  font, fontsize, scaling, rise, cid,
                                                  ncs, graphicstate)
                    self.push_char(bytes([char]), char_width, (x, y), h_est, font, matrix)
                    x += char_width
                    if cid == 32 and wordspace:
                        x += wordspace
                    needcharspace = True
        # Push none to indicate end of rendering.
        self.push_char(None, 0, (x,y), h_est, font, matrix)
        return (x, y)

    def paint_path(self, gstate, stroke, fill, evenodd, path):
        shape = ''.join(x[0] for x in path)
        if shape == 'ml':
            # horizontal/vertical line
            (_, x0, y0) = path[0]
            (_, x1, y1) = path[1]
            (x0, y0) = utils.apply_matrix_pt(self.ctm, (x0, y0))
            (x1, y1) = utils.apply_matrix_pt(self.ctm, (x1, y1))
            if x0 == x1 or y0 == y1:
                self.cur_item.add(LTLine(gstate.linewidth, (x0, y0), (x1, y1),
                    stroke, fill, evenodd, gstate.scolor, gstate.ncolor))
                return
        if shape == 'mlllh':
            #print("Painting rectangle!")
            # rectangle
            (_, x0, y0) = path[0]
            (_, x1, y1) = path[1]
            (_, x2, y2) = path[2]
            (_, x3, y3) = path[3]
            (x0, y0) = utils.apply_matrix_pt(self.ctm, (x0, y0))
            (x1, y1) = utils.apply_matrix_pt(self.ctm, (x1, y1))
            (x2, y2) = utils.apply_matrix_pt(self.ctm, (x2, y2))
            (x3, y3) = utils.apply_matrix_pt(self.ctm, (x3, y3))
            if ((x0 == x1 and y1 == y2 and x2 == x3 and y3 == y0) or
                (y0 == y1 and x1 == x2 and y2 == y3 and x3 == x0)):
                xlist = [x0,x1,x2,x3]
                ylist = [y0,y1,y2,y3]
                minx = min(xlist)
                maxx = max(xlist)
                miny = min(ylist)
                maxy = max(ylist)
                self.rectangles.append(Rectangle(minx, miny, maxx-minx, maxy-miny))
                self.cur_item.add(LTRect(gstate.linewidth, (x0, y0, x2, y2),
                    stroke, fill, evenodd, gstate.scolor, gstate.ncolor))
                return
        # other shapes
        pts = []
        for p in path:
            for i in range(1, len(p), 2):
                pts.append(utils.apply_matrix_pt(self.ctm, (p[i], p[i+1])))
        self.cur_item.add(LTCurve(gstate.linewidth, pts, stroke, fill,
            evenodd, gstate.scolor, gstate.ncolor))
        return


parser = argparse.ArgumentParser("Extract a dictionary of instructions and extensions from intel documentation")
parser.add_argument("-i", "--input", help="The pdf to use", type=str, required=True)
parser.add_argument("-o", "--output", help="The output file to write to", type=str, required=False)
parser.add_argument("-v", "--verbose", help="Verbose storage", action='store_true')

args = parser.parse_args()

input_filepath = args.input

outfp = sys.stdout.buffer

inst_title_re = re.compile(r"^[A-Z0-9/ \[\]]*—.*$")
eps = 5
title_x = 45.12
title_y = 714.0

instructions = []
page_begin = 120
page_end = 2065
pages = [ i for i in range(page_begin,page_end) ] # All pages
total_num_pages = len(pages)
bar_widgets = [
    progressbar.Bar(),
    progressbar.Counter(format='%(value)i/%(max_value)i')
]
bar = progressbar.ProgressBar(max_value=total_num_pages, widgets=bar_widgets, redirect_stdout=True)
bar.start()
with open(input_filepath, "rb") as fp:
    rsrcmgr = PDFResourceManager(caching=True)

    device = TextBoxStripper(rsrcmgr, outfp)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for (page_num, page) in PDFPage.get_pages2(fp,
                                               pages,
                                               password="",
                                               caching=True,
                                               check_extractable=True,
                                               fallback=False):
        try:
            #print("===== Page {}".format(page_num))
            # Text box processing:
            device.text_boxes = []
            device.tables = []
            interpreter.process_page(page)
            device.drop_empty_textboxes()
            device.merge_textboxes()
            # Table processing
            device.build_tables()
            ## For now, we don't care about the title of the page.
            ## With table contents we have all the information
            #for text_box in device.text_boxes:
            #    #print(text_box)
            #    if text_box.x > (title_x-eps) and text_box.x < (title_x+eps) and\
            #        text_box.y > (title_y-eps) and text_box.y < (title_y+eps):
            #        candidate_title_text = text_box.text.decode('windows-1252', 'ignore')
            #        if inst_title_re.match(candidate_title_text):
            #            print(candidate_title_text)
            #print("---- Raw Tables")
            for table in device.tables:
                instructions += Instruction.FromTable(table)

            #print("---- Instructions")
            #for inst in instructions:
            #    print(inst)
            bar.update(page_num-page_begin)
        except Exception as e:
            print("Error on page {}".format(page_num))
            raise e
    bar.finish()

    if args.output:
        with open(args.output, 'w') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"')
            Instruction.write_header(csv_writer)
            for inst in instructions:
                inst.write_to_csv(csv_writer)

    if args.verbose:
        for inst in instructions:
            print(inst)

    device.close()
