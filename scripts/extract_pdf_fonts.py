import sys
import os
import argparse

from pdfminer.pdfpage import PDFPage

parser = argparse.ArgumentParser("Extract a dictionary of instructions and extensions from intel documentation")
parser.add_argument("-i", "--input", help="The pdf to use", type=str, required=True)
parser.add_argument("--font-dir", help="Directory to place fonts into when extracting fonts", required=True)

args = parser.parse_args()

input_filepath = args.input

outfp = sys.stdout

font_streams = {}
with open(input_filepath, "rb") as fp:
    for page in PDFPage.get_pages(fp,
                                  None,
                                  maxpages=0,
                                  password="",
                                  caching=True,
                                  check_extractable=True):   
        for font_label in page.resources['Font']:
            font_ref = page.resources['Font'][font_label]
            font_dictionary = font_ref.resolve() 

            # Initialize keys and vals
            font_name = font_dictionary['BaseFont'].name
            font_type = font_dictionary['Subtype'].name
            font_file_key = None
            font_stream = None

            # check for font descriptor
            font_descriptor = None
            if 'FontDescriptor' in font_dictionary:
                font_descriptor = font_dictionary['FontDescriptor'].resolve()
            else:
                descendant_1 = font_dictionary['DescendantFonts'][0].resolve()
                desc_type = descendant_1['Type'].name
                if desc_type == 'FontDescriptor':
                    font_descriptor = descendant_1
                else:
                    cid_font_dictionary = font_dictionary['DescendantFonts'][0].resolve()
                    if 'FontDescriptor' in cid_font_dictionary:
                        font_type = cid_font_dictionary['Subtype'].name
                        font_descriptor = cid_font_dictionary['FontDescriptor'].resolve()
                    else:
                        print("No font descriptor!!")
                        print(cid_font_dictionary)

            if font_descriptor is not None:
                file_keys = ['FontFile', 'FontFile2', 'FontFile3']
                for file_key in file_keys:
                    if file_key in font_descriptor:
                        font_stream = font_descriptor[file_key].resolve()
                        font_file_key = file_key

                if font_stream is None:
                    print("No font file!!")
                    print(font_descriptor)

            if font_stream is not None:
                font_streams[(font_name, font_type, font_file_key)] = font_stream.get_data()

# Check that the font directory exists
if not os.path.exists(font_dir):
    os.mkdir(font_dir)

for font_key in font_streams:
    font_name = font_key[0]
    font_type = font_key[1]
    font_stream = font_streams[font_key]
    font_filepath = '/'.join([font_dir, font_name])
    font_extension = 'ttf'
    #if 'TrueType' in font_type:
    #    font_extension = 'ttf'
    #else:
    #    print(font_type)
    #    font_extension = 'afm'
    font_filepath = "{}.{}".format(font_filepath, font_extension)
    with open(font_filepath, 'wb') as font_outfile:
        font_outfile.write(font_stream)
