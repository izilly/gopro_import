#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (c) 2014 William Adams
#  Distributed under the terms of the Modified BSD License.
#  The full license is in the file LICENSE, distributed with this software.

import sys
import argparse
import os
import subprocess
from datetime import datetime
import re
import shutil
import tempfile
try:
    import thumbnailer
except ImportError:
    thumbnailer = None

# metadata tagnames, etc
TAGS_DATE = ['Exif.Photo.DateTimeDigitized',
             'Exif.Image.DateTime',
             'Exif.Photo.DateTimeOriginal']
TAGS_EXIFTOOL_MAP = {'DateTimeOriginal' : 'DateTimeOriginal',
                     'DateTimeDigitized': 'CreateDate',
                     'DateTime'         : 'ModifyDate'}
TAGS_EXIFTOOL = [TAGS_EXIFTOOL_MAP[i.split('.')[-1]] for i in TAGS_DATE]
TAGS_DATE_FMT = '%Y:%m:%d %H:%M:%S'
FF_TAGS_DATE_FMT = '%Y-%m-%dT%H:%M:%S'
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
    def __init__(self, path, options, outname=None, outdir=None,
                 existing_nums=[]):
        self._id = str(id(self))
        self.path = path
        self.options = options
        self.outname = outname
        self.outdir = options.outdir if options.outdir else outdir
        self.existing_nums = existing_nums
        self.imported_path = None
        self.is_chaptered = False
        self.date_time  = None
        self.duration = None
        self.thumb_paths = []
        self._dir, self.filename = os.path.split(self.path)
        self.name, self.ext = os.path.splitext(self.filename)
        self.ext = self.ext.lstrip('.')
        self.num = self.name[-4:]
        self.get_chapters()
        self.get_outfile()
        #~ self.generate_thumb_montage()

    def get_chapters(self):
        '''
        Find all the chapters associated with this file.

        Gopro splits long videos into chapters (smaller files).
        This method finds all the files that make up a single video.

        see: https://gopro.com/support/articles/hero3-and-hero3-file-naming-convention
        '''
        # find all chapters/files by checking for files ending with
        # NUM.EXT.  e.g.:
        #   GOPR1628.MP4
        #   GP011628.MP4
        #   GP021628.MP4
        self.chapters = sorted([os.path.join(self._dir,i) for i in
                                os.listdir(self._dir) if
                                i.endswith('{}.{}'.format(self.num,
                                                          self.ext))])
        # get just the basenames of each chapter.
        self.chapter_filenames = [os.path.basename(i) for i in self.chapters]
        if len(self.chapters) > 1:
            self.is_chaptered = True

    def get_exiftool_date(self):
        '''
        Get date-taken from file metadata tags.

        Requires exiftool to be installed.
        Returns the first date found by inspecting TAGS_EXIFTOOL in order.
        '''
        # check these tags defined in TAGS_EXIFTOOL
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
                # split into group/name/value
                tag_name, tag_date = tag_date.split('=')
                tag_group, tag_name = tag_name.strip('-').split(':')
                #~ if tag_group.lower() in TAGS_UTC:
                    #~ self.tag_date_in_utc = True
            if tag_date:
                return tag_date

    def get_date_time(self):
        '''
        Get date-taken from video metadata and convert to a datetime.datetime.
        '''
        date_time = None
        # get date from metadata tag
        tag_date = self.get_exiftool_date()
        if tag_date:
            # convert to datetime
            date_time = self.parse_date_str(tag_date)
        # set self.date_time (could be None)
        self.date_time = date_time
        #~ if self.tag_date_in_utc:
            #~ self.utc_to_local()

    def parse_date_str(self, date_str):
        '''
        Parse date-taken string and convert it to a datetime.datetime.
        '''
        # split into year,month,day,hour,minute,second
        date_parts = RE_DATE_TIME.search(date_str)
        if date_parts:
            date_parts = [int(i) for i in date_parts.groups()]
            # convert to a datetime.datetime.
            date_time = datetime(*date_parts)
        else:
            date_time = None
        return date_time

    def ffmpeg(self, encode=False):
        '''
        Encode and/or join output video.

        Requires ffmpeg to be installed.
        '''
        args = []
        # if chaptered video, use ffmpeg to concat to a single file
        if self.is_chaptered:
            self.write_chapter_file()
            # format date-taken into format suitable for video metadata tag
            tag_date = self.date_time.strftime(FF_TAGS_DATE_FMT)
            args.extend(['-f', 'concat',
                         '-i', self.chap_list,
                         '-metadata',
                         'creation_time={}'.format(tag_date)])
        else:
            # build ffmpeg command arguments
            args.extend(['-i', self.path,
                         '-map_metadata', '0'])
        if encode:
            # set encoder options
            args.extend(['-c:v', 'libx264',
                         '-preset', 'fast',
                         '-crf', str(self.options.crf),
                         '-vf', 'scale={}'.format(self.options.scale),
                         '-movflags', '+faststart',
                         '-c:a', 'copy'])
        else:
            # if not using encode option, just copy audio/video into
            # output container
            args.extend(['-c', 'copy'])
        cmd = ['ffmpeg'] + args + [self.outfile]
        print('\n*** ffmpeg cmd:\n{}\n'.format(' '.join(cmd)))
        o = subprocess.check_call(cmd, stderr=subprocess.DEVNULL,
                                  stdin=subprocess.DEVNULL)
        return self.outfile

    def write_chapter_file(self):
        '''
        Write a chapter file for `ffmpeg -concat` to join chaptered video.
        '''
        # write chapter file paths to a temp file
        tmpdir = tempfile.gettempdir()
        self.chap_list = os.path.join(tmpdir,
                                      'gopro.{}.chaps'.format(self.name))
        with open(self.chap_list, 'w') as f:
            for i in self.chapters:
                f.write("file '{}'\n".format(i))

    def get_outfile(self):
        '''
        Get the output filename.
        '''
        if self.outname is None:
            # get date
            if self.date_time is None:
                self.get_date_time()
            # format date for output filename
            date = '{:%Y.%m.%d_%H.%M.%S}'.format(self.date_time)
            if len(self.chapters) > 1:
                orig_name = '{}.pt00-{:02}'.format(self.name,
                                                   len(self.chapters)-1)
            else:
                orig_name = self.name
            # format output filename
            self.outname = 'gpv.{}.{}.{}'.format(date, orig_name,
                                                   self.ext.lower())
        # get full path to output file
        if self.outdir is None:
            self.outdir = os.getcwd()
        self.outfile = os.path.join(self.outdir, self.outname)

    def import_record(self, update_timestamps=True, with_thumbs=True):
        print('\n\n{}\n'.format('='*78))
        print('Importing {}\n'.format(', '.join(self.chapter_filenames)))

        if self.num not in self.existing_nums:
            if self.options.encode or self.is_chaptered:
                # encode and/or join file with ffmpeg
                self.ffmpeg(encode=self.options.encode)
            else:
                # if not encoding/joining, just copy file
                print('\n\n*** copying source file with shutil\n\n')
                shutil.copy2(self.path, self.outfile)
            self.imported_path = self.outfile
            if not self.options.keep_timestamps:
                # update imported file's timestamps to match date-taken
                self.update_file_timestamps()
            if thumbnailer and self.options.thumbnails:
                try:
                    self.thumb_montage = thumbnailer.generate_thumb_montage(
                                                                 self.outfile)
                except:
                    # todo: log a message notifying user of failure
                    pass
                self.update_file_timestamps(self.thumb_montage)
        else:
            # skip if video is already imported
            print('  File exists: skipping...')

    def update_file_timestamps(self, path=None):
        '''
        Update the output file timestamps to match date-taken.
        '''
        if self.date_time:
            if path is None:
                path = self.imported_path
            ts = self.date_time.timestamp()
            #~ os.utime(self.imported_path, (ts, ts))
            os.utime(path, (ts, ts))

    def get_duration(self):
        args = ['-print_format', 'default=nk=1:nw=1',
                '-show_entries',
                'format=duration']
        o = subprocess.check_output(['ffprobe'] + args + [self.path],
                                    stderr=subprocess.DEVNULL,
                                    universal_newlines=True)
        self.duration = float(o)


def get_infiles(options, exts=['.MP4']):
    paths = options.infiles
    infiles = []
    indirs = []
    for p in paths:
        if os.path.isdir(p):
            indirs.append(p)
        else:
            infiles.append(p)

    for i in indirs:
        files = [os.path.join(i,f) for f in os.listdir(i)]
        mediafiles = [f for f in files for e in exts
                      if os.path.splitext(f)[1] == e
                      and not os.path.basename(f).startswith('GP')]
        infiles.extend(mediafiles)

    if options.mask:
        infiles = [i for i in infiles if re.search(options.mask, i)]

    if options.range:
        idxs = options.range.split('-')
        rng = range(int(idxs[0]), int(idxs[-1])+1)
        infiles = [i for i in infiles
                   if int(os.path.splitext(i)[0][-4:]) in rng]
    return sorted(infiles)

def find_existing(outdir, num_prefix='GOPR'):
    existing_nums = [i.split(num_prefix)[1][:4]
                     for i in os.listdir(outdir)
                     if i.count(num_prefix)]
    return existing_nums

def get_options():
    parser = argparse.ArgumentParser()

    parser.add_argument('infiles', nargs='+', metavar='INFILE',
                            help="""List of paths to import.
                                    %(metavar)s can be a file or a directory.
                                    """)

    parser.add_argument('-o', '--output-dir', metavar='OUTDIR', default='.',
                            dest='outdir',
                            help="""Path of the directory into which files
                                    will be imported.""")

    parser.add_argument('-O', '--existing_dirs', metavar='OUTDIR', nargs='+',
                            default=[],
                            help="""Path(s) (in addition to OUTDIR) which will
                                    be checked for existing files.""")

    parser.add_argument('-m', '--mask', metavar='REGEXP',
                            help="""Input filename mask, a python regular
                                    expression.""")

    parser.add_argument('-r', '--range', metavar='N-N',
                            help="""Range of file numbers to import,
                                    separated by a hyphen ('-').
                                    e.g., "--range 0001-0002" would import
                                    GOPR0001.MP4 and GOPR0002.MP4 (if they
                                    exist""")

    parser.add_argument('-e', '--encode', action='store_true',
                            help="""re-encode video files with ffmpeg""")

    parser.add_argument('-c', '--crf', metavar='N', default=25,
                            help="""Constant Rate Factor passed to
                                    ffmpeg/x264 if encoding is done.
                                    Ignored if the --encode option isn't
                                    used.""")

    parser.add_argument('-s', '--scale', metavar='W:H',
                            help="""Filtergraph string passed to
                                    ffmpeg if encoding is done and scaling
                                    is desired.
                                    Ignored if the --encode option isn't
                                    used.  Example: "--scale -1:720" will
                                    pass "-vf scale=-1:720" to ffmpeg,
                                    which will scale the height to 720 pixels
                                    and the width to match the input
                                    aspect ratio.""")

    parser.add_argument('-t', '--thumbnails', action='store_true',
                            help="""Create thumbnail for each video.
                                    (Requires imagemagick)""")

    parser.add_argument('-k', '--keep-timestamps', action='store_true',
                            help="""Do not modify timestamps.
                                    By default, this script modifies the
                                    timestamps of imported files to match
                                    the date/time the video was taken.
                                    With this option, the timestamps are
                                    left untouched.""")

    options = parser.parse_args()
    return options

def main():
    options = get_options()
    infiles = get_infiles(options)
    existing_nums = find_existing(options.outdir)
    for i in options.existing_dirs:
        existing_nums.extend(find_existing(i))


    innames = '\n  '.join([os.path.basename(i) for i in infiles])
    print('\n\nImporting:\n  {}\n\n'.format(innames))

    for i in infiles:
        v = GoproVid(i, options, existing_nums=existing_nums)
        v.import_record()
    return 0

if __name__ == '__main__':
    main()

