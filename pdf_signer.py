# -*- coding: utf-8 -*-
"""
Created on Fri Nov 21 15:05:28 2025

@author: Raquel Ibáñez Alcalá
"""

import pymupdf
from argparse import ArgumentParser
from datetime import datetime
from zoneinfo import ZoneInfo
from os import path, getcwd, mkdir

# ------------------------ Class definition -----------------------------------
class PDFSigner:
    def __init__(self, **args):
        self.input_dir = path.abspath(args.get('input_dir', f'{getcwd()}/static')) # Directory where pdf template is located
        self.output_dir = path.abspath(args.get('output_dir', f'{getcwd()}/data')) # Directory to save signed pdfs to
        self.xcoord = int(args.get('x', 50)) # X coordinate of starting point where text will be inserted
        self.ycoord = int(args.get('y', 72)) # Y coordinate of starting point where text will be inserted
        
        # Font information for text to insert
        self.font_size = int(args.get('font_size', 12))
        self.font_name = args.get('font_name', 'helv')
        self.font_colour = tuple(map(int, args.get('font_color', (0,0,1))))
        self.font_rotate = int(args.get('font_rotate', 0))
        
        self.template_name = args.get('template', 'informed_consent_template.pdf')
        self.output_name = args.get('output_name', 'informed_consent_signed.pdf')
        if not self.template_name.endswith('.pdf'):
            self.template_name = f"{self.template_name}.pdf"
        if not self.output_name.endswith('.pdf'):
            self.output_name = f"{self.output_name}.pdf"
        self.template_path = path.join(self.input_dir, self.template_name)
        self.output_path = path.join(self.output_dir, self.output_name)

        self.ts_format = r"%d-%B-%Y %H:%M:%S %z" # Dataset timestamp format, example: 21 November 2025 21:20:45 +0000
        self.ts_region = ZoneInfo( args.get('region', 'UTC') ) # Region to localize timestamps to
        self.ts_short  = r"%d-%b-%Y" # Short timestamp format, example: 24-Nov-2025
        
        self.stamp_path = path.abspath(args.get('stamp_dir', f'{getcwd()}/static/cnstformseal.png'))
    
    def make_directory(self):
        try:
            # Attempt to create output directory
            mkdir(self.output_dir)
        except FileExistsError:
            pass
        except FileNotFoundError:
            print(f"[PDFSigner] Could not create output directory at location {self.output_dir}, location not found!")
            return 1
        except Exception as e:
            print(f"[PDFSigner] Could not create output directory due to exception: {e}")
            return 1
        else:
            return 0
        
    def loc_lines(self, document, page_index=-1):
        """
        Returns
        -------
        results : list of tuples
            A list of tupes with enties as "(x0, y0, x1, y1, 'word', block_no,
            line_no, word_no)" where 'word' starts with '___'.

        """
        #document = pymupdf.open( self.template_path )
        try:
            page = document[page_index]
            text_data = page.get_text("words", sort=False)
            results = []
            for item in text_data:
                if item[4].startswith('___'):
                    results.append(item)
        except Exception as e:
            print(f"\nCould not complete operation due to error: {e}")
        else:
            return results
    
    def writeonpdf(self, document, text, page_index=-1, x=0, y=0, **args):
        page = document[page_index]
        
        # Define starting coordinates to begin writing
        if args.get('use_selfcoords', True):
            starting_pt = pymupdf.Point(self.xcoord,self.ycoord)
        else:
            starting_pt = pymupdf.Point(x,y)
        
        # Begin inserting text
        print(f"\nWriting on document {self.template_path}")
        rc = page.insert_text(starting_pt, text,
                                       fontsize=self.font_size,
                                       fontname=self.font_name,
                                       color=self.font_colour,
                                       rotate=self.font_rotate)
        
        print("  %i lines printed on page %i." % (rc, page.number))
        
    def open_pdf(self):
        print("\nOpening document...")
        try:
            self.document = pymupdf.open( self.template_path )
        except FileNotFoundError:
            print(f"\nCould not find pdf file at location {path}.")
            return None
        else:
            return self.document
    
    def save_pdf(self):
        print("\nSaving document...")
        try:
            self.document.save( self.output_path )
        except FileNotFoundError:
            print(f"\nCould not save pdf file at location {self.output_path}. Please try a different location.")
            return -1
        else:
            return 0
    
    def close_pdf(self):
        print("\nClosing document...")
        try:
            self.document.close()
        except Exception as e:
            print(f"Could not close document due to error: {e}")
            return -1
        else:
            return 0
    
    def sign_name(self, document, name, page_index=-1, line_index=[0]):
        # Determine the correct text placement by finding the "Participant’s
        # Name (printed)" line
        lines = self.loc_lines(document)
        placement = [lines[i] for i in line_index]
        # Sign pdf
        for item in placement:
            self.writeonpdf(document, name,
                              x=item[0], y=item[1], page_index=page_index,
                              use_selfcoords=False)
    
    def sign_date(self, document, timestamp_format, page_index=-1, line_index=[2,4]):
        # Determine the correct text placement by finding the "Participant’s
        # Name (printed)" line
        lines = self.loc_lines(document)
        placement = [lines[i] for i in list(line_index)]
        # Sign pdf
        for item in placement:
            self.writeonpdf(document, datetime.now(self.ts_region).strftime(timestamp_format),
                              x=item[0], y=item[1], page_index=page_index,
                              use_selfcoords=False)
        
    def sign_initials(self, document, initials, page_index=-1, line_index=[1]):
        # Determine the correct text placement by finding the "Participant’s
        # Name (printed)" line
        lines = self.loc_lines(document)
        placement = [lines[i] for i in list(line_index)]
        # Sign pdf
        for item in placement:
            self.writeonpdf(document, fr"{initials}",
                              x=item[0], y=item[1], page_index=page_index,
                              use_selfcoords=False)
    
    def stamp_pdf(self, document, x0=250, x1=400, y0=600, y1=750, page_index=-1):
        # Insert an image (f.e. logo) onto the document at the indicated page.
        
        page = document[page_index]

        page.insert_image(pymupdf.Rect(x0,y0,x1,y1), filename=self.stamp_path)
        

# --------------------- Run this when app.py is executed ----------------------
if __name__ == '__main__':
# ----------------------- Parse commandline arguments -------------------------
    # Define the parser
    argparser = ArgumentParser(add_help=False)
    # Declare an argument, using a default value if the argument 
    # isn't given
    argparser.add_argument('-i', '--inputpath', dest='input_dir', default=path.abspath(f"{getcwd()}/static"))
    argparser.add_argument('-o', '--outputpath', dest='output_dir', default=path.abspath(f"{getcwd()}/data"))
    argparser.add_argument('-st', '--stamppath', dest='stamp_dir', default=path.abspath(f"{getcwd()}/static/cnstformseal.png"))
    argparser.add_argument('-ti', '--templatename', dest='template', default='informed_consent_template')
    argparser.add_argument('-to', '--documentout', dest='output_name', default='informed_consent_signed')
    argparser.add_argument('-pg', '--page', dest='page', default=-1)
    argparser.add_argument('-x', '--xcoord', dest='x', default=50)
    argparser.add_argument('-y', '--ycoord', dest='y', default=72)
    argparser.add_argument('-fs', '--font_size', dest='font_size', default=12)
    argparser.add_argument('-fn', '--font_name', dest='font_name', default='helv')
    argparser.add_argument('-fc', '--font_color', dest='font_colour', default=(0,0,1))
    argparser.add_argument('-fr', '--font_rotate', dest='font_rotate', default=0)

    # Now, parse the command line arguments and store the values in the 'args'
    # variable.
    args = argparser.parse_args()
    # Convert Namespace args to dictionary
    # args = vars(args)
# -----------------------------------------------------------------------------

# ----------------------------- Load Example ----------------------------------
    
    id_no = "99999"
    args.output_dir  = path.abspath(fr"{args.output_dir}/{id_no}")
    args.output_name = fr"{args.output_name}_{id_no}"
    signer = PDFSigner(input_dir=args.input_dir, output_dir=args.output_dir,
                       page=args.page, output_name=args.output_name,
                       template=args.template, x=args.x, y=args.y,
                       font_size=args.font_size, font_name=args.font_name,
                       font_colour=args.font_colour, font_rotate=args.font_rotate,
                       stamp_dir=args.stamp_dir)
    
    if not path.isdir(signer.output_dir):
        signer.make_directory()
    
    print("START")
    try:
        document = signer.open_pdf()
        
        # Sign participant's name
        signer.sign_name(document, "Jane Doe", line_index=[0])
        # Sign date in both "Date" lines
        signer.sign_date(document, signer.ts_short, line_index=[2,4])
        # Sign participant's initials
        signer.sign_initials(document, "J.D.", line_index=[1])
        # Sign guardian's initials
        signer.sign_initials(document, "D.J.", line_index=[3])
        # Stamp document to attest that is was signed electronically
        signer.stamp_pdf(document)
        # Add a timestamp
        signer.writeonpdf(document, datetime.now(signer.ts_region).strftime(signer.ts_format),
                          x=230, y=730, use_selfcoords=False)
        
        signer.save_pdf()
    finally:
        signer.close_pdf()
    print("END")
    
    del document, signer, args, argparser
    