#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (c) 2014 William Adams
#  Distributed under the terms of the Modified BSD License.
#  The full license is in the file LICENSE, distributed with this software.

import sys
import subprocess
import tempfile
import os

def get_duration(path):
    args = ['-print_format', 'default=nk=1:nw=1',
            '-show_entries', 
            'format=duration']
    o = subprocess.check_output(['ffprobe'] + args + [path],
                                stderr=subprocess.DEVNULL,
                                universal_newlines=True)
    duration = float(o)
    return duration

def get_thumbs(path, num=4, start=5, outname=None):
    duration = get_duration(path)
    secs_per_thumb = ( duration - start ) / ( num + 1 )
    
    thumbs = []
    outdir = tempfile.gettempdir()
    outpath = os.path.join(outdir, str(id(thumbs)))
    
    pos = start
    for i in range(num):
        t = '{}_{}.jpg'.format(outpath, i)
        cmd = ['ffmpeg', '-n',
               '-ss', str(pos), 
               '-i', path, 
               '-frames:v', '1', 
               t]
        o = subprocess.check_call(cmd, stderr=subprocess.DEVNULL, 
                                  stdin=subprocess.DEVNULL)
        thumbs.append(t)
        pos += secs_per_thumb
    #~ self.thumb_paths = thumbs
    return thumbs

def generate_thumb_montage(path, outfile=None, ext='tbn', skip_existing=True):
    if outfile is None:
        outfile = '{}.{}'.format(os.path.splitext(path)[0], ext)
    
    if os.path.exists(outfile):
        if skip_existing:
            return None
        else:
            n, e = os.path.splitext(outfile)
            for i in range(1,100):
                new_name = '{}_{}{}'.format(n, i, e)
                if not os.path.exists(new_name):
                    outfile = new_name
                    break
    
    #~ print('\nGenerating thumbnail montage: {}\n'.format(outfile))

    thumbs = get_thumbs(path)
    
    margs = ['-geometry', '240x135+4+3>', 
            '-shadow',
            '-tile', '2x2',
            '-background', 'none',
            'png:-']
    bargs = ['-',
             '-bordercolor', 'none',
             '-border', '22x8']
    mcmd = ['montage'] + thumbs + margs
    bcmd = ['convert'] + bargs + ['png:{}'.format(outfile)]
    
    p1 = subprocess.Popen(mcmd,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(bcmd,
                          stdin=p1.stdout, stderr=subprocess.DEVNULL)
    p1.stdout.close()
    output, err = p2.communicate()
    
    return outfile


def main():
    paths = sys.argv[1:]
    for p in paths:
        print('\nProcessing: {}'.format(p))
        tn = generate_thumb_montage(p)
        if tn:
            print('  Generated thumbnail: {}'.format(tn))
        else:
            print('  thumbnail exists; skipping...'.format(tn))
    return 0

if __name__ == '__main__':
    main()
