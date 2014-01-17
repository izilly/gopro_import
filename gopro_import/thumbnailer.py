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

def get_thumbs(path, num=4, start=5, outname=None, outdir=None, scale='240:-1'):
    duration = get_duration(path)
    if duration < start*2:
        start = 0
    secs_per_thumb = ( duration - start ) / ( num + 1 )
    
    thumbs = []
    
    if outdir is None:
        #~ outdir = tempfile.gettempdir()
        outdir = os.path.join(os.path.dirname(path), '.thumbs')
        if not os.path.exists(outdir):
            os.mkdir(outdir)
    if outname is None:
        outname = '{}_thumb'.format(os.path.splitext(os.path.basename(path))[0])
    #~ outpath = os.path.join(outdir, str(id(thumbs)))
    outpath = os.path.join(outdir, outname)
    
    pos = start
    for i in range(num):
        t = '{}_{}_{}.jpg'.format(outpath, i, round(pos))
        cmd = ['ffmpeg', '-n',
               '-ss', str(pos), 
               '-i', path, 
               '-frames:v', '1']
        if scale:
            cmd.extend(['-vf', 'scale={}'.format(scale)])
        o = subprocess.check_call(cmd + [t], 
                                  stderr=subprocess.DEVNULL, 
                                  stdin=subprocess.DEVNULL
                                  )
        thumbs.append(t)
        pos += secs_per_thumb
    return thumbs

def generate_thumb_montage(path, outfile=None, ext='png', skip_existing=True):
    if outfile is None:
        outfile = '{}-thumb.{}'.format(os.path.splitext(path)[0], ext)
    
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
    
    thumbs = get_thumbs(path)
    
    margs = [
             #~ '-geometry', '240x135+4+3>', 
             '-geometry', '+4+3>', 
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
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.DEVNULL
                          )
    p2 = subprocess.Popen(bcmd,
                          stdin=p1.stdout, 
                          stderr=subprocess.DEVNULL
                          )
    p1.stdout.close()
    output, err = p2.communicate()
    
    if p2.returncode != 0:
        print('Error: montage/convert command returned non-zero exit status')
        return False
    
    return outfile

def detect_empty_glob(paths):
    if len(paths) == 1 and not os.path.exists(paths[0]):
        paths = []
        return paths
    else:
        return paths


def main():
    paths = detect_empty_glob(sys.argv[1:])
    for p in paths:
        print('\nProcessing: {}'.format(p))
        tn = generate_thumb_montage(p)
        if tn:
            print('  Generated thumbnail: {}'.format(tn))
        elif tn is None:
            print('  thumbnail exists; skipping...'.format(tn))
        elif tn is False:
            print('  skipped due to error...'.format(tn))
    return 0

if __name__ == '__main__':
    main()
