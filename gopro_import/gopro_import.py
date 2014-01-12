#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (c) 2014 William Adams
#  Distributed under the terms of the Modified BSD License.
#  The full license is in the file LICENSE, distributed with this software.

import sys
import os
import subprocess
from datetime import datetime
import re
import shutil
import tempfile


# metadata tagnames, etc
TAGS_DATE = ['Exif.Photo.DateTimeDigitized',
             'Exif.Image.DateTime',
             'Exif.Photo.DateTimeOriginal']
TAGS_EXIFTOOL_MAP = {'DateTimeOriginal' : 'DateTimeOriginal',
                     'DateTimeDigitized': 'CreateDate',
                     'DateTime'         : 'ModifyDate'}
TAGS_EXIFTOOL = [TAGS_EXIFTOOL_MAP[i.split('.')[-1]] for i in TAGS_DATE]

TAGS_DATE_FMT = '%Y:%m:%d %H:%M:%S'
TAGS_UTC = ['quicktime']

# re patterns for parsing date from metadata
PAT_SEP=r'[^a-zA-Z0-9]?'
PAT_DATE = (r'{d4}{s}{d2}{s}{d2}').format(d4=r'(\d{4})', d2=r'(\d{2})', 
                                          s=PAT_SEP)
PAT_TIME = (r'{d2}{s}{d2}{s}{d2}').format(d2=r'(\d{2})', 
                                          s=PAT_SEP)
PAT_DATE_TIME = r'{d}{s}{t}'.format(d=PAT_DATE, t=PAT_TIME, s=PAT_SEP)
RE_DATE_TIME = re.compile(PAT_DATE_TIME)



class GoproRecord(object):
    def __init__(self):
        pass


class GoproVid(GoproRecord):
    def __init__(self, path, outname=None, outdir=None):
        self.is_chaptered = False
        self.path = path
        self.outdir = outdir
        self.outname = outname
        self._dir, self.filename = os.path.split(self.path)
        self.name, self.ext = os.path.splitext(self.filename)
        self.ext = self.ext.lstrip('.')
        self.num = self.name.lstrip('GOPR')
        self.get_date_time()
        self.get_outfile()
        self.get_chaps()
        #~ self.import_record()
    
    def get_chaps(self):
        self.chap_files = sorted([os.path.join(self._dir,i) for i in 
                           os.listdir(self._dir) 
                           if i.endswith('{}.{}'.format(self.num, self.ext))])
        if len(self.chap_files) > 1:
            self.is_chaptered = True
    
    def get_exiftool_date(self):
        date_tags = TAGS_EXIFTOOL
        for i in date_tags:
            try:
                tag_date = subprocess.check_output(['exiftool', '-G', 
                                                    '-args',
                                                    '-{}'.format(i), 
                                                    self.path],
                                             universal_newlines=True,
                                             stderr=subprocess.DEVNULL).strip()
            except:
                tag_date = None
            if tag_date:
                tag_name, tag_date = tag_date.split('=')
                tag_group, tag_name = tag_name.strip('-').split(':')
                #~ if tag_group.lower() in TAGS_UTC:
                    #~ self.tag_date_in_utc = True
            if tag_date:
                return tag_date

    def get_date_time(self):
        date_time = None
        tag_date = self.get_exiftool_date()
        if tag_date:
            date_time = self.parse_date_str(tag_date)
        self.date_time = date_time
        #~ if self.tag_date_in_utc:
            #~ self.utc_to_local()
    
    def parse_date_str(self, date_str):
        date_parts = RE_DATE_TIME.search(date_str)
        if date_parts:
            date_parts = [int(i) for i in date_parts.groups()]
            date_time = datetime(*date_parts)
        else:
            date_time = None
        return date_time
    
    def cat_chaps(self):
        if self.is_chaptered:
            self.write_chap_list()
            self.unchaptered = self.ffmpeg_cat_chaps()
        else:
            self.unchaptered = self.path
            return self.unchaptered
    
    def write_chap_list(self):
        tmpdir = tempfile.gettempdir()
        self.chap_list = os.path.join(tmpdir, 'gopro.{}.chaps'.format(self.name))
        with open(self.chap_list, 'w') as f:
            for i in self.chap_files:
                f.write("file '{}'\n".format(i))
    
    def ffmpeg_cat_chaps(self):
        args = ['ffmpeg',
                '-f', 'concat',
                '-i', self.chap_list,
                '-c', 'copy',
                self.outfile]
        o = subprocess.check_call(args)
        return self.outfile
    
    def get_outfile(self):
        if self.outname is None:
            self.outname = 'gopro.{:%Y.%m.%d_%H.%M.%S}.{}.{}'.format(self.date_time, self.name, self.ext.lower())
        if self.outdir is None:
            self.outdir = os.getcwd()
        self.outfile = os.path.join(self.outdir, self.outname)
    
    def import_record(self):
        if self.is_chaptered:
            self.cat_chaps()
        else:
            shutil.copy2(self.path, self.outfile)


def main():
    paths = sys.argv[1:]
    for i in paths:
        v = GoproVid(i)
        v.import_record()
    return 0

if __name__ == '__main__':
    main()

