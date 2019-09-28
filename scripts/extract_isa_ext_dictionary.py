import sys
import os
import argparse
import six
import re

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
    def __init__(self, text, x, y, width):
        self.text = text
        self.x = x
        self.y = y
        self.width = width

    def __repr__(self):
        return "({},{},{}) -> {}".format(self.x, self.y, self.width, self.text)

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
        self.init_x = 0
        self.init_y = 0
        self.space_thresh = 50
        self.merge_xthresh = 3
        return

    def push_textbox(self, x, y):
        if self.temp_text is not None:
            self.text_boxes.append(TextBox(self.temp_text, self.init_x,
                                           self.init_y, x-self.init_x))
            self.temp_text = None

    def push_text(self, text, x, y):
        if self.temp_text is None:
            self.temp_text = text
            self.init_x = x
            self.init_y = y
        else:
            self.temp_text += text

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
            if box_i.y == box_j.y and box_i.x < box_j.x:
                if abs(xp-xt) < self.merge_xthresh:
                    box_i.text += box_j.text
                    box_i.width = box_j.x+box_j.width-box_i.x
                    del self.text_boxes[i+1]
                    iterate = False
            if iterate:
                i += 1

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
        for obj in seq:
            if utils.isnumber(obj):
                if abs(obj) > self.space_thresh:
                    (xt, yt) = utils.apply_matrix_pt(matrix, (x, y))
                    self.push_textbox(xt, yt)
                x -= obj*dxscale
                needcharspace = True
            else:
                (xt, yt) = utils.apply_matrix_pt(matrix, (x, y))
                self.push_text(obj, xt, yt)
                for cid in font.decode(obj):
                    if needcharspace:
                        x += charspace
                    x += self.render_char(utils.translate_matrix(matrix, (x, y)),
                                          font, fontsize, scaling, rise, cid,
                                          ncs, graphicstate)
                    if cid == 32 and wordspace:
                        x += wordspace
                    needcharspace = True
        (xt, yt) = utils.apply_matrix_pt(matrix, (x, y))
        self.push_textbox(xt, yt)
        return (x, y)

parser = argparse.ArgumentParser("Extract a dictionary of instructions and extensions from intel documentation")
parser.add_argument("-i", "--input", help="The pdf to use", type=str, required=True)

args = parser.parse_args()

input_filepath = args.input

outfp = sys.stdout.buffer

inst_title_re = re.compile(r"^[A-Z0-9/ \[\]]*—.*$")
eps = 2
title_x = 45.12
title_y = 714.0

#pages = [122]
#pages = [124]
#pages = [131]
#pages = [197]
#pages = [254]
pages = [480]
with open(input_filepath, "rb") as fp:
    rsrcmgr = PDFResourceManager(caching=True)

    device = TextBoxStripper(rsrcmgr, outfp)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    page_num = 1
    for page in PDFPage.get_pages(fp,
                                  None, # There's a mismatch between page 'numbers' and whats passed here.
                                  maxpages=0,
                                  password="",
                                  caching=True,
                                  check_extractable=True):   
        #if page_num in pages:
        if True:
            # Clear text boxes:
            device.text_boxes = []
            interpreter.process_page(page)
            device.merge_textboxes()
            for text_box in device.text_boxes:
                #print(text_box)
                if text_box.x > (title_x-eps) and text_box.x < (title_x+eps) and\
                   text_box.y > (title_y-eps) and text_box.y < (title_y+eps):
                    candidate_title_text = text_box.text.decode('windows-1252', 'ignore')
                    if inst_title_re.match(candidate_title_text):
                        print(candidate_title_text)
                    else:
                        #print("Candidate didn't match! ({})".format(candidate_title_text))
                        pass
            #page_data = page.contents[0].get_data()
            #print(page_data)
            #print(page_data.decode('windows-1252'))
            #print(page.mediabox)
            #print(page.cropbox)
        page_num += 1


    device.close()
