#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2001-11  Iñigo Serna
# Time-stamp: <2011-05-14 12:12:24 inigo>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Copyright (C) 2001-11, Iñigo Serna <inigoserna@gmail.com>.
All rights reserved.

This software has been released under the GPL License, see the COPYING
file that comes with this package. There is NO WARRANTY.

'pyview' is a simple pager (viewer) to be used with Last File Manager.
"""


import os, os.path
import sys
import getopt
import logging
from time import time
import curses, curses.ascii

from __init__ import *
import messages
from utils import run_shell, encode, decode


########################################################################
##### module definitions and variables
PYVIEW_NAME = 'pyview'
PYVIEW_README = """
    %s is a pager (viewer) written in Python.
Though  initially it was written to be used with 'lfm',
it can be used standalone too.
Since version 0.9 it can read from standard input too
(eg. $ ps efax | pyview  -s)

This software has been realised under the GPL License,
see the COPYING file that comes with this package.
There is NO WARRANTY.

Keys:
=====
+ Movement
    - cursor_up, p, P
    - cursor_down, n, N
    - previous page, backspace, Ctrl-P
    - next page, space, Ctrl-N
    - home: first line
    - end: last line
    - cursor_left
    - cursor_right

+ Actions
    - h, H, F1: help
    - w, W, F2: toggle un / wrap (only in text mode)
    - m, M, F4: toggle text / hex mode
    - g, G, F5: goto line / byte offset
    - /: find (new search)
    - F6: find previous or find
    - F7: find next or find
    - 0..9: go to bookmark #
    - b, B: set bookmark #
    - Ctrl-O: open shell 'sh'. Type 'exit' to return to pyview
    - q, Q, x, X, F3, F10: exit

Goto Line / Byte Offset
=======================
    Enter the line number / byte offset you want to show.
If number / byte is preceded by '0x' it is interpreted as hexadecimal.
You can scroll relative lines from the current position using '+' or '-'
character.

Find
====
    Type the string to search. It ignores case.
""" % PYVIEW_NAME
MODE_TEXT, MODE_HEX = 0, 1


app = None
LOG_FILE = os.path.join(os.getcwd(), 'pyview.log')


######################################################################
##### Internal View
class InternalView(object):
    """Internal View class"""

    def __init__(self, title, buf, center=True):
        self.title = title
        self.__validate_buf(buf, center)
        self.init_curses()

    def __validate_buf(self, buf, center):
        buf = [(l[0][:app.maxw-2], l[1] ) for l in buf]
        buf2 = [l[0] for l in buf]
        self.nlines = len(buf2)
        if self.nlines >= app.maxh - 2:
            self.large = True
            self.y0 = self.y = 0
        else:
            self.large = False
            self.y0 = int(((app.maxh-2) - self.nlines)/2)
        if center:
            col_max = max(map(len, buf2))
            self.x0 = int((app.maxw-col_max)/2)
        else:
            self.x0 = 1
            self.y0 = 0 if self.large else 1
        self.buf = buf

    def init_curses(self):
        curses.cbreak()
        curses.raw()
        curses.curs_set(0)
        try:
            self.win_title = curses.newwin(1, app.maxw, 0, 0)
            self.win_body = curses.newwin(app.maxh-2, app.maxw, 1, 0)     # h, w, y, x
            self.win_status = curses.newwin(1, app.maxw, app.maxh-1, 0)
        except curses.error:
            print 'Can\'t create windows'
            sys.exit(-1)
        if curses.has_colors():
            self.win_title.bkgd(curses.color_pair(1),
                                curses.color_pair(1) | curses.A_BOLD)
            self.win_body.bkgd(curses.color_pair(2))
            self.win_status.bkgd(curses.color_pair(1))
        self.win_body.leaveok(1)
        self.win_body.keypad(1)
        self.win_title.erase()
        self.win_status.erase()
        title = self.title
        if len(title) - 4 > app.maxw:
            title = title[:app.maxw-12] + '~' + title[-7:]
        self.win_title.addstr(0, int((app.maxw-len(title))/2), title)
        if self.large:
            status = ''
        else:
            status = 'Press any key to continue'
            self.win_status.addstr(0, int((app.maxw-len(status))/2), status)
        self.win_title.refresh()
        self.win_status.refresh()

    def show(self):
        self.win_body.erase()
        buf = self.large and self.buf[self.y:self.y+app.maxh-2] or self.buf
        for i, (l, c) in enumerate(buf):
            self.win_body.addstr(self.y0+i, self.x0, l, curses.color_pair(c))
        self.win_body.refresh()

    def run(self):
        if self.large:
            while True:
                self.show()
                ch = self.win_body.getch()
                if ch in (ord('k'), ord('K'), curses.KEY_UP):
                    self.y = max(self.y-1, 0)
                if ch in (ord('j'), ord('J'), curses.KEY_DOWN):
                    self. y = min(self.y+1, self.nlines-1)
                elif ch in (curses.KEY_HOME, 0x01):
                    self.y = 0
                elif ch in (curses.KEY_END, 0x05):
                    self.y = self.nlines - 1
                elif ch in (curses.KEY_PPAGE, 0x08, 0x02, curses.KEY_BACKSPACE):
                    self.y = max(self.y-app.maxh+2, 0)
                elif ch in (curses.KEY_NPAGE, ord(' '), 0x06):
                    self. y = min(self.y+app.maxh-2, self.nlines-1)
                elif ch in (0x1B, ord('q'), ord('Q'), ord('x'), ord('X'),
                            curses.KEY_F3, curses.KEY_F10):
                    break
        else:
            self.show()
            while not self.win_body.getch():
                pass


######################################################################
##### Utilities

def read_stdin():
    """Read from stdin with 2.0 sec timeout maximum. Returns text"""

    from select import select

    try:
        fd = select([sys.stdin], [], [], 2.0)[0][0]
        stdin = ''.join(fd.readlines())
        # close stdin (pipe) and open terminal for reading
        os.close(0)
        sys.stdin = open(os.ttyname(1), 'r')
    except IndexError:
        stdin = ''
    return stdin


def create_temp_for_stdin(buf):
    """Copy stdin in a temporary file. Returns file name"""

    from tempfile import mkstemp

    filename = mkstemp()[1]
    f = open(filename, 'w')
    f.write(buf)
    f.close()
    return filename


class FileCache(object):
    def __init__(self, filename, maxsize=1000000):
        # cache
        self.lines = {}
        self.lines_age = {}
        self.size = 0
        self.maxsize = maxsize
        # file
        self.filename = filename
        self.fd = open(filename, 'r')
        self.nbytes = os.path.getsize(filename)
        self.lines_pos = [-1, 0L] # make index start at 1, first line pos = 0
        if self.nbytes != 0:
            pos = nline = 0L
            for line in self.fd:
                nline += 1
                pos += len(line)
                self.lines_pos.append(pos)
                # prepolulate first 50 lines
                if nline <= 50:
                    buf = line.replace('\t', ' '*4)
                    self.lines[nline] = buf
                    self.lines_age[nline] = time()
                    self.size += len(buf)
            self.nlines = nline
        else:
            self.nlines = 0

    def __del__(self):
        self.fd.close()

    def __len__(self):
        return len(self.lines)

    def __repr__(self):
        return u'FileCache [%s, %d of %d lines in cache]' % \
            (self.filename, len(self), self.nlines)

    def isempty(self):
        return self.nbytes == 0

    def __getitem__(self, lineno):
        """return line# contents"""
        if lineno < 1 or lineno > self.nlines:
            return None
        if lineno in self.lines.keys():
            self.lines_age[lineno] = time()
            return self.lines[lineno]
        else:
            self.fd.seek(self.lines_pos[lineno])
            line = self.fd.readline()
            self.lines[lineno] = line
            self.lines_age[lineno] = time()
            self.size += len(line)
            self.__ensure_size()
            return line

    def __ensure_size(self):
        if self.size > self.maxsize:
            ages = [(t, len(self.lines[lno]), lno) for lno, t in self.lines_age.items()]
            ages.sort(reverse=True)
            while self.size > self.maxsize:
                t, s, lno = ages.pop()
                del self.lines[lno]
                del self.lines_age[lno]
                self.size -= s

    def line_len(self, lineno):
        """return length of line#"""
        if lineno < 1 or lineno > self.nlines:
            return None
        return len(self[lineno])

    def linecol2pos(self, lineno, col):
        """return absolute position for line# and col# in file"""
        if lineno < 1 or lineno > self.nlines or col < 0:
            return None
        return self.lines_pos[lineno] + col

    def pos2linecol(self, pos):
        """return line# and col# for absolute pos in file"""
        if pos < 0 or pos > self.nbytes:
            return None
        for i, p in enumerate(self.lines_pos):
            if pos == p:
                return i, 0
            elif pos < p:
                return i-1, p-pos
        return i, p-pos

    def get_bytes(self, n, pos):
        """return a string with n bytes starting at pos"""
        self.fd.seek(pos)
        return self.fd.read(n)


######################################################################
##### PyView
class FileView(object):
    """Main application class"""

    def __init__(self, win, filename, line, mode, stdin_flag):
        global app
        app, messages.app = self, self
        self.win = win        # root window, need for resizing
        self.mode = mode
        self.wrap = False
        self.stdin_flag = stdin_flag
        self.line, self.col, self.col_max, self.pos = 1, 0, 0, 0
        self.pattern = ''
        self.matches = []
        self.bookmarks = [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1]
        self.init_curses()
        try:
            self.fc = FileCache(filename)
        except (IOError, os.error), (errno, strerror):
            messages.error('Cannot view file\n%s: %s (%s)' % (filename, strerror, errno))
            sys.exit(-1)
        if self.fc.isempty():
            messages.error('Cannot view file\n%s: File is empty' % filename)
            sys.exit(-1)
        if line != 0:
            if mode == MODE_TEXT:
                self.line = max(0, min(line, self.fc.nlines))
            else:
                self.pos = max(0, min(line, self.fc.nbytes)) & 0xFFFFFFF0L

    def init_curses(self):
        self.maxh, self.maxw = self.win.getmaxyx()
        curses.cbreak()
        curses.raw()
        curses.curs_set(0)
        try:
            self.win_title = curses.newwin(1, self.maxw, 0, 0)
            self.win_file = curses.newwin(self.maxh-2, self.maxw, 1, 0)
            self.win_status = curses.newwin(1, self.maxw, self.maxh-1, 0)
        except curses.error:
            print 'Can\'t create windows'
            sys.exit(-1)
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLUE)    # title
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)    # files
            curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_CYAN)      # current file
            curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_CYAN)   # messages
            curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)    # help
            curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)      # file info
            curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_RED)      # error messages
            curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_RED)      # error messages
            curses.init_pair(9, curses.COLOR_YELLOW, curses.COLOR_RED)     # button in dialog
            curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # file selected
            curses.init_pair(11, curses.COLOR_YELLOW, curses.COLOR_CYAN)   # file selected and current
            self.win_title.bkgd(curses.color_pair(1),
                                curses.color_pair(1) | curses.A_BOLD)
            self.win_file.bkgdset(curses.color_pair(2))
            self.win_status.bkgdset(curses.color_pair(1))
        self.win_file.leaveok(1)
        self.win_file.keypad(1)

    def resize_window(self):
        h, w = self.win.getmaxyx()
        self.maxh, self.maxw = h, w
        if w == 0 or h == 2:
            return
        self.win.resize(h, w)
        self.win_title.resize(1, w)
        self.win_file.resize(h-2, w)
        self.win_status.resize(1, w)
        self.win_status.mvwin(h-1, 0)
        self.show()


    def __sanitize_char(self, c):
        if curses.ascii.iscntrl(c) or ord(c) in range(0x7F, 0xA0):
            return '.'
        elif curses.ascii.isascii(c) or curses.ascii.ismeta(c):
            return c # curses.ascii.ascii(c) = c
        else:
            return '.'

    def show_str(self, w, line):
        buf = ''.join(map(self.__sanitize_char, line))
        w.addstr(buf)

    def show_str_yx(self, y, x, w, line):
        buf = ''.join(map(self.__sanitize_char, line))
        w.addstr(y, x, buf)

    def __calc_hex_charsperline(self):
        tbl = ((152, 32), (134, 28), (116, 24), (98, 20), (80, 16), (62, 12), (44, 8), (26,4))
        for width, chars_per_line in tbl:
            if self.maxw >= width:
                return chars_per_line
        else:
            return -1

    def __move_hex(self, n):
        self.pos += self.__calc_hex_charsperline() * n
        self.pos = min(self.fc.nbytes & 0xFFFFFFF0L, max(0, self.pos))

    def show_text_nowrap(self):
        self.win_file.refresh()
        self.col_max = self.maxw
        lwin = curses.newpad(self.maxh-2, self.maxw+1)
        lwin.erase()
        for y in xrange(self.maxh-2):
            l = self.fc[self.line+y]
            if l is None:
                break
            l = l.replace('\n', '').replace('\r', '').replace('\t', ' '*4)
            largeline = (len(l)-self.col > self.maxw) and True or False
            buf = l[self.col:self.col+self.maxw]
            self.show_str_yx(y, 0, lwin, buf)
            if largeline:
                self.col_max = max(self.col_max, len(l))
                lwin.addch(y, self.maxw-1, '>', curses.color_pair(2) | curses.A_BOLD)
        lwin.refresh(0, 0, 1, 0, self.maxh-2, self.maxw-1)

    def show_text_wrap(self):
        self.win_file.refresh()
        lwin = curses.newpad(self.maxh-2, self.maxw+1)
        lwin.erase()
        i = y = 0
        dx = self.col
        while y < self.maxh - 2:
            l = self.fc[self.line+i]
            if l is None:
                break
            l = l.replace('\n', '').replace('\r', '').replace('\t', ' '*4)
            l = l[dx:] # remaining chars of line
            self.show_str_yx(y, 0, lwin, l[:self.maxw])
            y += 1
            if len(l) > self.maxw:
                dx += self.maxw
            else:
                i += 1; dx = 0
        lwin.refresh(0, 0, 1, 0, self.maxh-2, self.maxw-1)

    def show_hex(self):
        self.win_file.erase()
        chars_per_line = self.__calc_hex_charsperline()
        if chars_per_line == -1:
            return
        n = chars_per_line * (self.maxh-2)
        bytes = self.fc.get_bytes(n, self.pos)
        if len(bytes) < n:
            bytes += '\0' * (n-len(bytes))
        for y in xrange(self.maxh-2):
            pos = chars_per_line*y
            self.win_file.addstr(y, 0, '%8.8X ' % (self.pos+pos),
                                 curses.color_pair(2) | curses.A_BOLD)
            buf = '   '.join([' '.join(['%2.2X' % (ord(bytes[pos+4*i+j]) & 0xFF) \
                                     for j in xrange(4)]) \
                                  for i in xrange(chars_per_line/4)])
            buf += ' ' + bytes[y*chars_per_line:(y+1)*chars_per_line]
            self.show_str(self.win_file, buf)
        for i in xrange(chars_per_line/4-1):
            self.win_file.vline(0, 21+14*i, curses.ACS_VLINE, self.maxh-2)
        self.win_file.refresh()

    def show_title(self):
        self.win_title.erase()
        if self.mode == MODE_TEXT:
            pos = self.fc.linecol2pos(self.line, self.wrap and self.col or 0)
            lineno, col = self.line, self.col
        else:
            pos = self.pos
            lineno, col = self.fc.pos2linecol(self.pos)
        if self.maxw > 20:
            title = self.stdin_flag and 'STDIN' or os.path.basename(self.fc.filename)
            if len(title) > self.maxw-52:
                title = title[:self.maxw-58] + '~' + title[-5:]
            self.win_title.addstr('File: %s' % encode(title))
        if self.maxw >= 67:
            if (self.mode == MODE_TEXT) and (col != 0 or self.wrap):
                self.win_title.addstr(0, int(self.maxw/2)-14, 'Col: %d' % col)
            buf = 'Bytes: %d/%d' % (pos, self.fc.nbytes)
            self.win_title.addstr(0, int(self.maxw/2)-5, buf)
            buf = 'Lines: %d/%d' % (lineno, self.fc.nlines)
            self.win_title.addstr(0, int(self.maxw*3/4)-4, buf)
        if self.maxw > 5:
            percent = int(pos*100/self.fc.nbytes)
            self.win_title.addstr(0, self.maxw-5, '%3d%%' % percent)
        self.win_title.refresh()

    def show_status(self):
        self.win_status.erase()
        if self.maxw > 40:
            if self.stdin_flag:
                path = 'STDIN'
            else:
                path = os.path.dirname(self.fc.filename)
                if not path or path[0] != os.sep:
                    path = os.path.join(os.getcwd(), path)
            if len(path) > self.maxw - 37:
                path = '~' + path[-(self.maxw-38):]
            self.win_status.addstr('Path: %s' % encode(path))
        if self.maxw > 30:
            mode = (self.mode==MODE_TEXT) and 'TEXT' or 'HEX'
            self.win_status.addstr(0, self.maxw-30, 'View mode: %s' % mode)
            wrap = self.wrap and 'YES' or 'NO'
            if self.mode == MODE_TEXT:
                self.win_status.addstr(0, self.maxw-10, 'Wrap: %s' % wrap)
        self.win_status.refresh()

    def show(self):
        if self.maxh < 3:
            return
        self.show_title()
        if self.mode == MODE_TEXT:
            if self.wrap:
                self.show_text_wrap()
            else:
                self.show_text_nowrap()
        else:
            self.show_hex()
        self.show_status()


    def __find(self, title):
        self.pattern = messages.Entry(title, 'Type search string', '', True, False).run()
        if self.pattern is None or self.pattern == '':
            return -1
        filename = os.path.abspath(self.fc.filename)
        mode = (self.mode==MODE_TEXT) and 'n' or 'b'
        try:
            cmd = '%s -i%c \"%s\" \"%s\"' % (sysprogs['grep'], mode,
                                             self.pattern, filename)
            st, buf = run_shell(encode(cmd), path=u'.', return_output=True)
        except OSError:
            self.show()
            messages.error('Find error: Can\'t open file')
            return -1
        if st == -1:
            self.show()
            messages.error('Find error\n' + buf)
            self.matches = []
            return -1
        else:
            try:
                self.matches = [int(l.split(':')[0]) for l in buf.split('\n') if l]
            except (ValueError, TypeError):
                self.matches = []
            return 0

    def __find_next(self):
        pos = (self.mode==MODE_TEXT) and self.line+1 or \
            self.pos+self.__calc_hex_charsperline() # start in next line
        for next in self.matches:
            if next >= pos:
                break
        else:
            self.show()
            messages.error('Cannot find "%s"\nNo more matches' % self.pattern)
            return
        if self.mode == MODE_TEXT:
            self.line, self.col = next, 0
        else:
            self.pos = next

    def __find_prev(self):
        pos = (self.mode==MODE_TEXT) and self.line-1 or \
            self.pos - self.__calc_hex_charsperline() # start in prev line
        for prev in sorted(self.matches, reverse=True):
            if prev <= pos:
                break
        else:
            self.show()
            messages.error('Cannot find "%s"\nNo more matches' % self.pattern)
            return
        if self.mode == MODE_TEXT:
            self.line, self.col = prev, 0
        else:
            self.pos = prev


    # movement
    def move_up(self):
        if self.mode == MODE_TEXT:
            if self.wrap:
                if self.col > 0:
                    self.col -= self.maxw
                else:
                    self.line = max(1, self.line-1)
                    f, r = divmod(self.fc.line_len(self.line), self.maxw)
                    # self.col = ((r==0) and (f-1) or f) * self.maxw # Fails!
                    if r == 0 and f > 0:
                        f -= 1
                    self.col = f * self.maxw
            else:
                self.line = max(1, self.line-1)
        else:
            self.__move_hex(-1)

    def move_down(self):
        if self.mode == MODE_TEXT:
            if self.wrap:
                if self.col + self.maxw >= self.fc.line_len(self.line):
                    if self.line == self.fc.nlines:
                        return
                    self.line = min(self.fc.nlines, self.line+1)
                    self.col = 0
                else:
                    self.col += self.maxw
            else:
                self.line = min(self.fc.nlines, self.line+1)
        else:
            self.__move_hex(1)

    def move_pageprev(self):
        if self.mode == MODE_TEXT:
            if self.wrap:
                i, y = 0, self.maxh-2
                if len(self.fc[self.line]) > self.maxw:
                    y +=  int((len(self.fc[self.line])-self.col)/self.maxw)
                while y >= 0:
                    l = self.fc[self.line+i]
                    if l is None:
                        break
                    f, r = divmod(len(l), self.maxw)
                    if r == 0 and f > 0:
                        f -= 1
                    y -= f+1; i -= 1
                if f != 0:
                    self.col = -(y+1) * self.maxw
                else:
                    self.col = 0
                self.line = max(1, self.line+i+1)
            else:
                self.line = max(1, self.line-self.maxh+2)
        else:
            self.__move_hex(-(self.maxh-2))

    def move_pagenext(self):
        if self.mode == MODE_TEXT:
            if self.wrap:
                i = y = 0
                dx = old_col = self.col
                while y < self.maxh - 2:
                    l = self.fc[self.line+i]
                    if l is None:
                        break
                    f, r = divmod(len(l[dx:]), self.maxw)
                    if r == 0 and f > 0:
                        f -= 1
                    y += f+1; i += 1; dx = 0
                if f != 0:
                    i -= 1
                    self.col = dx + ((f+1)-(y-self.maxh+2)) * self.maxw
                    if l is None or self.col >= len(l[dx:]):
                        self.col = 0
                        i += 1
                else:
                    self.col = dx
                if self.line == self.fc.nlines:
                    self.col = old_col
                    return
                self.line = min(self.fc.nlines, self.line+i)
            else:
                self.line = min(self.fc.nlines, self.line+self.maxh-2)
        else:
            self.__move_hex(self.maxh-2)

    def move_home(self):
        if self.mode == MODE_TEXT:
            self.line, self.col = 1, 0
        else:
            self.pos = 0

    def move_end(self):
        if self.mode == MODE_TEXT:
            self.line, self.col = self.fc.nlines, 0
        else:
            self.pos = self.fc.nbytes & 0xFFFFFFF0L

    def move_left(self):
        if self.mode == MODE_TEXT and not self.wrap:
            if self.col > 9:
                self.col -= 10

    def move_right(self):
        if self.mode == MODE_TEXT and not self.wrap:
            if self.col_max > self.col+self.maxw:
                self.col += 10

    # goto, bookmarks
    def goto(self):
        rel = 0
        title = (self.mode==MODE_TEXT) and 'Goto line' or 'Type line number'
        help = (self.mode==MODE_TEXT) and 'Goto line' or 'Type byte offset'
        n = messages.Entry(title, help, '', True, False).run()
        if not n:
            return
        if n[0] in ('+', '-'):
            rel = 1
        try:
            if n[rel:rel+2] == '0x':
                if rel != 0:
                    n = long(n[0] + str(int(n[1:], 16)))
                else:
                    n = long(n, 16)
            else:
                n = long(n)
        except ValueError:
            self.show()
            msg = 'Goto %s' % (self.mode==MODE_TEXT and 'line' or 'byte')
            messages.error(msg + '\nInvalid number: %s' % n)
            return
        if n == 0:
            return
        if self.mode == MODE_TEXT:
            line = (rel!=0) and (self.line+n) or n
            self.line = max(1, min(line, self.fc.nlines))
        else:
            pos = (rel!=0) and (self.pos+n) or n
            self.pos = max(0, min(pos, self.fc.nbytes)) & 0xFFFFFFF0L

    def goto_bookmark(self, no):
        pos = self.bookmarks[no]
        if pos != -1:
            if self.mode == MODE_TEXT:
                self.line, self.col = self.fc.pos2linecol(pos), 0
            else:
                self.pos = pos

    def set_bookmark(self):
        while True:
            ch = messages.get_a_key('Set bookmark',
                                    'Press 0-9 to save bookmark, Ctrl-C to quit')
            if 0x30 <= ch <= 0x39:
                if self.mode == MODE_TEXT:
                    pos = self.fc.linecol2pos(self.line, self.col)
                else:
                    pos = self.pos
                self.bookmarks[ch-0x30] = pos
                break
            elif ch == -1:
                break

    def find(self):
        if self.__find('Find') != -1:
            self.__find_next()

    def find_prev(self):
        if not self.matches:
            if self.__find('Find Previous') == -1:
                return
        self.__find_prev()

    def find_next(self):
        if not self.matches:
            if self.__find('Find Next') == -1:
                return
        self.__find_next()

    # modes
    def toggle_wrap(self):
        if self.mode == MODE_TEXT:
            self.wrap = not self.wrap
            self.col = 0

    def toggle_mode(self):
        if self.mode == MODE_TEXT:
            self.mode = MODE_HEX
            self.pos = self.fc.linecol2pos(self.line, self.col) & 0xFFFFFFF0L
        else:
            self.mode = MODE_TEXT
            self.line, self.col = self.fc.pos2linecol(self.pos)[0], 0
            self.pos = 0

    # other
    def open_shell(self):
        curses.endwin()
        if self.stdin_flag:
            os.system('sh')
        else:
            os.system('cd \"%s\"; sh' % encode(os.path.dirname(self.fc.filename)))
        curses.curs_set(0)

    def show_help(self):
        buf = [('', 2)]
        buf.append(('%s v%s (C) %s, by %s' % \
                    (PYVIEW_NAME, VERSION, DATE, AUTHOR), 5))
        text = PYVIEW_README.split('\n')
        for l in text:
            buf.append((l, 6))
        InternalView('Help for %s' % PYVIEW_NAME, buf).run()


    def run(self):
        while True:
            self.show()
            ch = self.win_file.getch()

            # movement
            if ch in (ord('k'), ord('K'), curses.KEY_UP):
                self.move_up()
            elif ch in (ord('j'), ord('J'), curses.KEY_DOWN):
                self.move_down()
            elif ch in (curses.KEY_PPAGE, curses.KEY_BACKSPACE, 0x08, 0x02):
                self.move_pageprev()
            elif ch in (curses.KEY_NPAGE, ord(' '), 0x06):
                self.move_pagenext()
            elif ch in (curses.KEY_HOME, 0x01):
                self.move_home()
            elif ch in (curses.KEY_END, 0x05):
                self.move_end()
            elif ch == curses.KEY_LEFT:
                self.move_left()
            elif ch == curses.KEY_RIGHT:
                self.move_right()

            # goto, bookmarks, find
            elif ch in (ord('g'), ord('G'), curses.KEY_F5):
                self.goto()
            elif 0x30 <= ch <= 0x39:
                self.goto_bookmark(ch-0x30)
            elif ch in (ord('b'), ord('B')):
                self.set_bookmark()
            elif ch == ord('/'):
                self.find()
            elif ch == curses.KEY_F6:
                self.find_prev()
            elif ch == curses.KEY_F7:
                self.find_next()

            # modes
            elif ch in (ord('w'), ord('W'), curses.KEY_F2):
                self.toggle_wrap()
            elif ch in (ord('m'), ord('M'), curses.KEY_F4):
                self.toggle_mode()

            # other
            elif ch == 0x0F:          # Ctrl-O
                self.open_shell()
            elif ch in (ord('h'), ord('H'), curses.KEY_F1):
                self.show_help()
            elif ch == curses.KEY_RESIZE:
                self.resize_window()
            elif ch in (0x11, ord('q'), ord('Q'), ord('x'), ord('X'), # Ctrl-Q
                        curses.KEY_F3, curses.KEY_F10):
                del self.fc
                return


######################################################################
##### Main

def usage(prog, msg=''):
    prog = os.path.basename(prog)
    if msg != '':
        print '%s:\t%s\n' % (prog, msg)
    print """\
%s v%s - (C) %s, by %s

A simple pager (viewer) to be used with Last File Manager.
Released under GNU Public License, read COPYING for more details.

Usage:\t%s\t[-h | --help]
\t\t[-s | --stdin]
\t\t[-m text|hex | --mode=text|hex]
\t\t[-d | --debug]
\t\t[+n]
\t\tpathtofile
Options:
    -s, --stdin\t\tread from stdin
    -m, --mode\t\tstart in text or hexadecimal mode
    -d, --debug\t\tcreate debug file
    -h, --help\t\tshow help
    +n\t\t\tstart at line (text mode) or byte (hex mode),
    \t\t\tif n starts with '0x' is considered hexadecimal
    pathtofile\t\tfile to view
""" % (PYVIEW_NAME, VERSION, DATE, AUTHOR, prog)


def main(win, filename, line, mode, stdin_flag):
    app = FileView(win, decode(filename), line, mode, stdin_flag)
    if app == OSError:
        sys.exit(-1)
    return app.run()


def PyView(sysargs):
    # defaults
    DEBUG = False
    filename = ''
    line = 0
    stdin_flag = False
    mode = MODE_TEXT

    # args
    try:
        opts, args = getopt.getopt(sysargs[1:], 'dhsm:',
                                   ['debug', 'help', 'stdin', 'mode='])
    except getopt.GetoptError:
        usage(sysargs[0], 'Bad argument(s)')
        sys.exit(-1)
    for o, a in opts:
        if o in ('-s', '--stdin'):
            stdin_flag = True
        elif o in ('-d', '--debug'):
            DEBUG = True
        elif o in ('-h', '--help'):
            usage(sysargs[0])
            sys.exit(2)
        elif o in ('-m', '--mode'):
            if a == 'text':
                mode = MODE_TEXT
            elif a == 'hex':
                mode = MODE_HEX
            else:
                usage(sysargs[0], '<%s> is not a valid mode' % a)
                sys.exit(-1)

    if stdin_flag:
        stdin = read_stdin()
        if stdin == '':
            stdin_flag = False

    if len(args) > 2:
        usage(sysargs[0], 'Incorrect number of arguments')
        sys.exit(-1)
    while True:
        try:
            arg = args.pop()
            if arg[0] == '+':
                line = arg[1:]
                try:
                    line = (line[:2]=='0x') and int(line, 16) or int(line)
                except ValueError:
                    usage(sysargs[0], '<%s> is not a valid line number' % line)
                    sys.exit(-1)
            else:
                filename = arg
        except IndexError:
            break
    if filename == '' and not stdin_flag:
        usage(sysargs[0], 'File is missing')
        sys.exit(-1)
    if stdin_flag:
        filename = create_temp_for_stdin(stdin)
    else:
        if not os.path.isfile(filename):
            usage(sysargs[0], '<%s> is not a valid file' % filename)
            sys.exit(-1)

    # logging
    if DEBUG:
        log_file = os.path.join(os.path.abspath(u'.'), LOG_FILE)
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s\t%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S   ',
                            filename=log_file,
                            filemode='w')
    logging.info('Starting PyView...')

    # main app
    logging.info('Main application call')
    curses.wrapper(main, filename, line, mode, stdin_flag)
    logging.info('End')

    if stdin_flag:
        os.unlink(filename)


if __name__ == '__main__':
    PyView(sys.argv)
