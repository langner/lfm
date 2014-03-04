#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2001-11  Iñigo Serna
# Time-stamp: <2011-05-21 11:58:14 inigo>
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


u"""lfm v2.3 - (C) 2001-11, by Iñigo Serna <inigoserna@gmail.com>

'Last File Manager' is a file manager for UNIX console.
It has a curses interface and it's written in Python.
Released under GNU Public License, read
COPYING file for more details.

Usage:\tlfm <options> [path1 [path2]]

Arguments:
    path1            Directory to show in left pane
    path2            Directory to show in right pane

Options:
    -1               Start in 1-pane mode
    -2               Start in 2-panes mode (default)
    -d, --debug      Create debug file
    -h, --help       Show help
"""


__author__ = u'Iñigo Serna'
__revision__ = '2.3'


import os, os.path
import sys
import time
import datetime
import getopt
import logging
import curses
import curses.panel
import cPickle as pickle

from __init__ import *
from config import Config, colors
import files
import actions
import utils
import vfs
import messages
import pyview


######################################################################
##### Global variables
LOG_FILE = os.path.join(os.getcwd(), 'lfm.log')
MAX_TAB_HISTORY = 15


######################################################################
##### Lfm main class
class Lfm(object):
    """Main application class"""

    def __init__(self, win, prefs):
        self.win = win              # root window, needed for resizing
        self.prefs = prefs          # preferences
        self.init_ui()
        self.statusbar = StatusBar(self.maxh, self)   # statusbar
        self.cli = PowerCLI(self.maxh, self)          # powercli
        self.lpane = Pane(PANE_MODE_LEFT, self)       # left pane
        self.rpane = Pane(PANE_MODE_RIGHT, self)      # right pane
        self.act_pane, self.noact_pane = self.lpane, self.rpane
        if self.prefs.options['num_panes'] == 1:
            self.lpane.mode = PANE_MODE_FULL
            self.lpane.init_ui()
            self.rpane.mode = PANE_MODE_HIDDEN
            self.rpane.init_ui()
        actions.app = messages.app = utils.app = vfs.app = pyview.app = self


    def load_paths(self, paths1, paths2):
        self.lpane.load_tabs_with_paths(paths1)
        self.rpane.load_tabs_with_paths(paths2)


    def init_ui(self):
        """initialize curses stuff: windows, colors..."""

        self.maxh, self.maxw = self.win.getmaxyx()
        curses.cbreak()
        curses.raw()
        self.win.leaveok(1)
        messages.cursor_hide()

        # colors
        if curses.has_colors():
            # Translation table: color name -> curses color name
            colors_table = {
                'black': curses.COLOR_BLACK,
                'blue': curses.COLOR_BLUE,
                'cyan': curses.COLOR_CYAN,
                'green': curses.COLOR_GREEN,
                'magenta': curses.COLOR_MAGENTA,
                'red': curses.COLOR_RED,
                'white': curses.COLOR_WHITE,
                'yellow': curses.COLOR_YELLOW }
            # List of items to get color
            color_items = ['title', 'files', 'current_file', 'messages', 'help',
                           'file_info', 'error_messages1', 'error_messages2',
                           'buttons', 'selected_file', 'current_selected_file',
                           'tabs', 'temp_files', 'document_files', 'media_files',
                           'archive_files', 'source_files', 'graphics_files',
                           'data_files', 'current_file_otherpane',
                           'current_selected_file_otherpane',
                           'directories', 'exe_files', 'cli_prompt', 'cli_text']
            # Initialize every color pair with user colors or with the defaults
            prefs_colors = self.prefs.colors
            for i, item_name in enumerate(color_items):
                pref_color_fg, pref_color_bg = prefs_colors[item_name]
                def_color_fg = colors_table[colors[item_name][0]]
                def_color_bg = colors_table[colors[item_name][1]]
                color_fg = colors_table.get(pref_color_fg, def_color_fg)
                color_bg = colors_table.get(pref_color_bg, def_color_bg)
                curses.init_pair(i+1, color_fg, color_bg)


    def resize(self):
        """resize windows"""

        h, w = self.win.getmaxyx()
        self.maxh, self.maxw = h, w
        if w == 0 or h == 2:
            return
        self.win.resize(h, w)
        self.lpane.do_resize(h, w)
        self.rpane.do_resize(h, w)
        self.statusbar.do_resize(h, w)
        self.cli.do_resize(h, w)
        self.regenerate()
        self.display()


    def display(self):
        """display/update both panes and status bar or powercli"""

        self.lpane.display()
        self.rpane.display()
        if self.cli.visible:
            self.cli.display()
        else:
            self.statusbar.display()


    def half_display(self):
        """display/update only active pane and status bar"""

        self.act_pane.display()
        self.statusbar.display()


    def half_display_other(self):
        """display/update only non-active pane and status bar"""

        self.noact_pane.display()
        self.statusbar.display()


    def regenerate(self):
        """Rebuild panes' directories"""

        self.lpane.regenerate()
        self.rpane.regenerate()


    def quit_program(self, icode):
        """save settings and prepare to quit"""

        for tab in self.lpane.tabs + self.rpane.tabs:
            if tab.vfs:
                vfs.exit(tab)
        if self.prefs.options['save_conf_at_exit']:
            self.prefs.save()
        if self.prefs.options['save_history_at_exit']:
            pickle.dump(messages.history, file(messages.HISTORY_FILE, 'w'), -1)
        if icode == -1: # change directory
            return self.act_pane.act_tab.path
        else:           # exit, but don't change directory
            return


    def run(self):
        """run application"""

        while True:
            self.display()
            ret = self.act_pane.manage_keys()
            if ret < 0:
                return self.quit_program(ret)
            elif ret == RET_TOGGLE_PANE:
                if self.act_pane == self.lpane:
                    self.act_pane, self.noact_pane = self.rpane, self.lpane
                else:
                    self.act_pane, self.noact_pane = self.lpane, self.rpane
            elif ret == RET_TAB_NEW:
                tab = self.act_pane.act_tab
                path = tab.path if tab.vfs=='' else os.path.dirname(tab.vbase)
                idx = self.act_pane.tabs.index(tab)
                newtab = TabVfs(self.act_pane)
                newtab.init(path)
                self.act_pane.tabs.insert(idx+1, newtab)
                self.act_pane.act_tab = newtab
            elif ret == RET_TAB_CLOSE:
                tab = self.act_pane.act_tab
                idx = self.act_pane.tabs.index(tab)
                self.act_pane.act_tab = self.act_pane.tabs[idx-1]
                self.act_pane.tabs.remove(tab)
                del tab


######################################################################
##### StatusBar class
class StatusBar(object):
    """Status bar"""

    def __init__(self, maxh, app):
        self.app = app
        try:
            self.win = curses.newwin(1, app.maxw, maxh-1, 0)
        except curses.error:
            print 'Can\'t create StatusBar window'
            sys.exit(-1)
        if curses.has_colors():
            self.win.bkgd(curses.color_pair(1))


    def do_resize(self, h, w):
        self.win.resize(1, w)
        self.win.mvwin(h-1, 0)


    def display(self):
        """show status bar"""

        self.win.erase()
        adir = self.app.act_pane.act_tab
        maxw = self.app.maxw
        if len(adir.selections) > 0:
            if maxw >= 45:
                size = 0
                for f in adir.selections:
                    size += adir.files[f][files.FT_SIZE]
                self.win.addstr('    %s bytes in %d files' % \
                                (num2str(size), len(adir.selections)))
        else:
            if maxw >= 80:
                self.win.addstr('File: %4d of %-4d' % \
                                (adir.file_i + 1, adir.nfiles))
                filename = adir.sorted[adir.file_i]
                if adir.vfs:
                    realpath = os.path.join(vfs.join(self.app.act_pane.act_tab),
                                            filename)
                else:
                    realpath = files.get_realpath(adir.path, filename,
                                                  adir.files[filename][files.FT_TYPE])
                path = (len(realpath)>maxw-35) and \
                    '~' + realpath[-(maxw-37):] or realpath
                self.win.addstr(0, 20, 'Path: ' + utils.encode(path))
        if maxw > 10:
            try:
                self.win.addstr(0, maxw-8, 'F1=Help')
            except:
                pass
        self.win.refresh()


######################################################################
##### PowerCLI class
class PowerCLI(object):
    """The PowerCLI class is an advanced 1-line cli"""

    RUN_NORMAL, RUN_BACKGROUND, RUN_NEEDCURSESWIN = xrange(3)

    def __init__(self, maxh, app):
        self.app = app
        self.visible = False
        self.text = ''
        self.pos = 0
        try:
            self.win = curses.newwin(1, app.maxw, maxh-1, 0)
            self.pwin = curses.panel.new_panel(self.win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create StatusBar window'
            sys.exit(-1)
        if curses.has_colors():
            self.win.bkgd(curses.color_pair(25))
        self.entry = None


    def do_resize(self, h, w):
        self.win.resize(1, w)
        self.win.mvwin(h-1, 0)
        if self.visible:
            self.display()


    def hide(self):
        self.visible = False
        self.pwin.bottom()
        messages.cursor_hide()
        self.app.statusbar.display()


    def display(self):
        self.visible = True
        tab = self.app.act_pane.act_tab
        path = vfs.join(tab) if tab.vfs else tab.path
        l = self.app.maxw/6 - 4
        if len(path) > l:
            path = '~'+ path[-l-1:]
        useridchar = '#' if os.getuid()==0 else '$'
        self.win.erase()
        self.win.addstr('[%s]%s ' % (utils.encode(path), useridchar),
                        curses.color_pair(24) | curses.A_BOLD)
        self.win.refresh()
        le = len(path) + 4
        self.entry = messages.EntryLine(self.app.maxw-le+4, 1, self.app.maxh-1, le,
                                        self.text, 'cli', True, tab.path, cli=True)
        self.entry.pos = self.pos
        messages.cursor_show2()
        self.pwin.top()
        while True:
            ans = self.entry.manage_keys()
            if ans == -1:           # Ctrl-C
                self.text, self.pos = self.entry.text, self.entry.pos
                cmd = ''
                break
            elif ans == 10:         # return
                self.text, self.pos = '', 0
                cmd = self.entry.text.strip()
                break
        self.hide()
        if cmd != '':
            self.execute(cmd, tab)
            if len(messages.history['cli']) >= messages.MAX_HISTORY:
                messages.history['cli'].remove(messages.history['cli'][0])
            if messages.history['cli'].count(cmd) >= 1:
                messages.history['cli'].remove(cmd)
            messages.history['cli'].append(cmd)


    def __check_loop(self, cmd, selected):
        if not selected:
            return False
        return any((var in cmd) for var in \
                       ('$f', '$v', '$F', '$E', '$i', '$tm', '$ta', '$tc'))


    def __replace_python(self, cmd, lcls):
        lcls = dict([('__lfm_%s' % k, v) for k,v in lcls.items()])
        # get chunks
        chunks, st = {}, 0
        while True:
            i = cmd.find('{', st)
            if i == -1:
                break
            j = cmd.find('}', i+1)
            if j == -1:
                raise SyntaxError('{ at %d position has not ending }' % i)
            else:
                chunks[(i+1, j)] = cmd[i+1:j].replace('$', '__lfm_')
                st = j + 1
        # evaluate
        if chunks == {}:
            return cmd
        buf, st = '', 0
        for i, j in sorted(chunks.keys()):
            buf += cmd[st:i-1]
            try:
                translated = eval(chunks[(i, j)], {}, lcls)
            except Exception, msg:
                raise SyntaxError(str(msg).replace('__lfm_', '$'))
            buf += unicode(translated)
            st = j+1
        buf += cmd[st:]
        return buf


    def __replace_variables(self, cmd, lcls):
        for k, v in lcls.items():
            if k in ('i', 'tm', 'ta', 'tc', 'tn'):
                cmd = cmd.replace('$%s' % k, unicode(v))
            elif k in ('s', 'a'):
                cmd = cmd.replace('$%s' % k,  ' '.join(['"%s"' % f for f in v]))
            else:
                cmd = cmd.replace('$%s' % k, v)
        return cmd


    def __replace_cli(self, cmd, tab, selected, filename=None):
        # prepare vars
        if not filename:
            filename = tab.sorted[tab.file_i]
        cur_directory = tab.path
        other_directory = self.app.noact_pane.act_tab.path
        fullpath = os.path.join(tab.path, filename)
        filename_noext, ext = os.path.splitext(filename)
        if filename_noext.endswith('.tar'):
            filename_noext = filename_noext.replace('.tar', '')
            ext = '.tar' + ext
        all_selected = selected
        all_files = [f for f in tab.sorted if f is not os.pardir]
        try:
            selection_idx = selected.index(filename)+1
        except ValueError:
            selection_idx = 0
        tm = datetime.datetime.fromtimestamp(os.path.getmtime(fullpath))
        ta = datetime.datetime.fromtimestamp(os.path.getatime(fullpath))
        tc = datetime.datetime.fromtimestamp(os.path.getctime(fullpath))
        tnow = datetime.datetime.now()
        # and replace, first python code, and then variables
        lcls =  {'f': filename, 'v': filename, 'F': fullpath,
                 'E': filename_noext, 'e': ext,
                 'd': cur_directory, 'o': other_directory,
                 's': all_selected, 'a': all_files, 'i': selection_idx,
                 'tm': tm, 'ta': ta, 'tc': tc, 'tn': tnow }
        for i, bmk in enumerate(self.app.prefs.bookmarks):
            lcls['b%d' % i] = bmk
        cmd = self.__replace_python(cmd, lcls)
        cmd = self.__replace_variables(cmd, lcls)
        return cmd


    def __run(self, cmd, path, mode):
        if mode == PowerCLI.RUN_NEEDCURSESWIN:
            curses.endwin()
            try:
                msg = utils.get_shell_output3('cd "%s" && %s' % (path, cmd))
            except KeyboardInterrupt:
                os.system('reset')
                msg = 'Stopped by user'
            st = -1 if msg else 0
        elif mode == PowerCLI.RUN_BACKGROUND:
            utils.run_in_background(cmd, path)
            st, msg = 0, ''
        else: # PowerCLI.RUN_NORMAL
            st, msg = utils.ProcessFunc('Executing PowerCLI', cmd,
                                        utils.run_shell, cmd, path, True).run()
        if st == -1:
            messages.error('Cannot execute PowerCLI command:\n  %s\n\n%s' % \
                               (cmd, str(msg)))
        elif st != -100 and msg is not None and msg != '':
            if self.app.prefs.options['show_output_after_exec']:
                curses.curs_set(0)
                if messages.confirm('Executing PowerCLI', 'Show output', 1):
                    lst = [(l, 2) for l in msg.split('\n')]
                    pyview.InternalView('Output of "%s"' % utils.encode(cmd),
                                        lst, center=0).run()
        return st


    def execute(self, cmd, tab):
        selected = [f for f in tab.sorted if f in tab.selections]
        loop = self.__check_loop(cmd, selected)
        if cmd[-1] == '&':
            mode = PowerCLI.RUN_BACKGROUND
            cmd_orig = cmd[:-1].strip()
        elif cmd[-1] == '%':
            mode = PowerCLI.RUN_NEEDCURSESWIN
            cmd_orig = cmd[:-1].strip()
        else:
            mode = PowerCLI.RUN_NORMAL
            cmd_orig = cmd
        if loop:
            for f in selected:
                try:
                    cmd = self.__replace_cli(cmd_orig, tab, selected, f)
                # except Exception as msg: # python v2.6+
                except Exception, msg:
                    messages.error('Cannot execute PowerCLI command:\n  %s\n\n%s' % \
                                       (cmd_orig, str(msg)))
                    st = -1
                else:
                    st = self.__run(cmd, tab.path, mode)
                if st == -1:
                    self.app.lpane.display()
                    self.app.rpane.display()
                    if messages.confirm('Error running PowerCLI',
                                        'Do you want to stop now?') == 1:
                        break
            tab.selections = []
        else:
            try:
                cmd = self.__replace_cli(cmd_orig, tab, selected)
            # except Exception as msg: # python v2.6+
            except Exception, msg:
                messages.error('Cannot execute PowerCLI command:\n  %s\n\n%s' % \
                                   (cmd_orig, str(msg)))
            else:
                st = self.__run(cmd, tab.path, mode)


######################################################################
##### Pane class
class Pane(object):
    """The Pane class is like a notebook containing TabVfs"""

    def __init__(self, mode, app):
        self.app = app
        self.mode = mode
        self.dims = [0, 0, 0, 0]    # h, w, y0, x0
        self.maxh, self.maxw = app.maxh, app.maxw
        self.init_ui()
        self.tabs = []


    def load_tabs_with_paths(self, paths):
        for path in paths:
            tab = TabVfs(self)
            err = tab.init(utils.decode(path))
            if err:
                tab.init(os.path.abspath(u'.'))
            self.tabs.append(tab)
        self.act_tab = self.tabs[0]


    def init_ui(self):
        self.dims = self.__calculate_dims()
        try:
            self.win = curses.newwin(*self.dims)
        except curses.error:
            print 'Can\'t create Pane window'
            sys.exit(-1)
        self.win.leaveok(1)
        self.win.keypad(1)
        if curses.has_colors():
            self.win.bkgd(curses.color_pair(2))
        self.__calculate_columns()


    def __calculate_dims(self):
        if self.mode == PANE_MODE_HIDDEN:
            return (self.maxh-2, self.maxw, 0, 0)     # h, w, y0, x0
        elif self.mode == PANE_MODE_LEFT:
            return (self.maxh-2, int(self.maxw/2), 1, 0)
        elif self.mode == PANE_MODE_RIGHT:
            return (self.maxh-2, self.maxw-int(self.maxw/2), 1, int(self.maxw/2))
        elif self.mode == PANE_MODE_FULL:
            return (self.maxh-2, self.maxw, 1, 0)     # h, w, y0, x0
        else:              # error
            messages.error('Cannot initialize panes\nReport bug if you can see this.')
            return (self.maxh-2, int(self.maxw/2), 1, int(self.maxw/2))


    def __calculate_columns(self):
        self.pos_col2 = self.dims[1] - 14 # sep between size and date
        self.pos_col1 = self.pos_col2 - 8 # sep between filename and size


    def do_resize(self, h, w):
        self.maxh, self.maxw = h, w
        self.dims = self.__calculate_dims()
        self.win.resize(self.dims[0], self.dims[1])
        self.win.mvwin(self.dims[2], self.dims[3])
        self.__calculate_columns()
        for tab in self.tabs:
            tab.fix_limits()


    def display(self):
        """display pane"""

        if self.mode == PANE_MODE_HIDDEN:
            return
        if self.maxw < 65:
            return
        self.display_tabs()
        self.display_files()
        self.display_cursorbar()


    def display_tabs(self):
        tabs = curses.newpad(1, self.dims[1]+1)
        tabs.bkgd(curses.color_pair(12))
        tabs.erase()
        w = self.dims[1] / 4
        if w < 10:
            w = 5
        tabs.addstr(('[' + ' '*(w-2) + ']') * len(self.tabs))
        for i, tab in enumerate(self.tabs):
            if w < 10:
                path = '[ %d ]' % (i+1, )
            else:
                if tab.vfs:
                    path = os.path.basename(tab.vbase.split('#')[0])
                else:
                    path = os.path.basename(tab.path) or os.path.dirname(tab.path)
                if len(path) > w - 2:
                    path = '[%s~]' % path[:w-3]
                else:
                    path = '[' + path + ' ' * (w-2-len(path)) + ']'
            attr = (tab==self.act_tab) and curses.color_pair(10) or curses.color_pair(1)
            tabs.addstr(0, i*w, utils.encode(path), attr)
        tabs.refresh(0, 0, 0, self.dims[3],  1, self.dims[3]+self.dims[1]-1)


    def get_filetypecolorpair(self, f, typ):
        if typ == files.FTYPE_DIR:
            return curses.color_pair(22)
        elif typ == files.FTYPE_EXE:
            return curses.color_pair(23)  | curses.A_BOLD
        ext = os.path.splitext(f)[1].lower()
        files_ext = self.app.prefs.files_ext
        if ext in files_ext['temp_files']:
            return curses.color_pair(13)
        elif ext in files_ext['document_files']:
            return curses.color_pair(14)
        elif ext in files_ext['media_files']:
            return curses.color_pair(15)
        elif ext in files_ext['archive_files']:
            return curses.color_pair(16)
        elif ext in files_ext['source_files']:
            return curses.color_pair(17)
        elif ext in files_ext['graphics_files']:
            return curses.color_pair(18)
        elif ext in files_ext['data_files']:
            return curses.color_pair(19)
        else:
            return curses.color_pair(2)


    def display_files(self):
        tab = self.act_tab
        self.win.erase()

        # calculate pane width, height and vertical start position
        w = self.dims[1]
        if self.mode != PANE_MODE_FULL:
            h, y = self.maxh-5, 2
        else:
            h, y = self.maxh-2, 0

        # headers
        if self.mode != PANE_MODE_FULL:
            if self == self.app.act_pane:
                self.win.attrset(curses.color_pair(5))
                attr = curses.color_pair(6) | curses.A_BOLD
            else:
                self.win.attrset(curses.color_pair(2))
                attr = curses.color_pair(2)
            path = tab.vfs and vfs.join(tab) or tab.path
            path = (len(path)>w-5) and '~' + path[-w+5:] or path
            self.win.box()
            self.win.addstr(0, 2, utils.encode(path), attr)
            self.win.addstr(1, 1,
                            'Name'.center(self.pos_col1-2)[:self.pos_col1-2],
                            curses.color_pair(2) | curses.A_BOLD)
            self.win.addstr(1, self.pos_col1+2, 'Size',
                            curses.color_pair(2) | curses.A_BOLD)
            self.win.addstr(1, self.pos_col2+5, 'Date',
                            curses.color_pair(2) | curses.A_BOLD)
        else:
            if tab.nfiles > h:
                self.win.vline(0, w-1, curses.ACS_VLINE, h)

        # files
        for i in xrange(tab.file_z - tab.file_a + 1):
            filename = tab.sorted[i+tab.file_a]
            # get file info
            res = files.get_fileinfo_dict(tab.path, filename,
                                          tab.files[filename])
            # get file color
            if tab.selections.count(filename):
                attr = curses.color_pair(10) | curses.A_BOLD
            else:
                if self.app.prefs.options['color_files']:
                    attr = self.get_filetypecolorpair(filename, tab.files[filename][files.FT_TYPE])
                else:
                    attr = curses.color_pair(2)
            # show
            if self.mode == PANE_MODE_FULL:
                buf = tab.get_fileinfo_str_long(res, w)
                self.win.addstr(i, 0, utils.encode(buf), attr)
            else:
                buf = tab.get_fileinfo_str_short(res, w, self.pos_col1)
                self.win.addstr(i+2, 1, utils.encode(buf), attr)

        # vertical separators
        if self.mode != PANE_MODE_FULL:
            self.win.vline(1, self.pos_col1, curses.ACS_VLINE, self.dims[0]-2)
            self.win.vline(1, self.pos_col2, curses.ACS_VLINE, self.dims[0]-2)

        # vertical scroll bar
        y0, n = self.__calculate_scrollbar_dims(h, tab.nfiles, tab.file_i)
        self.win.vline(y+y0, w-1, curses.ACS_CKBOARD, n)
        if tab.file_a != 0:
            self.win.vline(y, w-1, '^', 1)
            if (n == 1) and (y0 == 0):
                self.win.vline(y+1, w-1, curses.ACS_CKBOARD, n)
        if tab.nfiles  > tab.file_a + h:
            self.win.vline(h+y-1, w-1, 'v', 1)
            if (n == 1) and (y0 == h-1):
                self.win.vline(h+y-2, w-1, curses.ACS_CKBOARD, n)

        self.win.refresh()


    def __calculate_scrollbar_dims(self, h, nels, i):
        """calculate scrollbar initial position and size"""

        if nels > h:
            n = max(int(h*h/nels), 1)
            y0 = min(max(int(int(i/h)*h*h/nels),0), h-n)
        else:
            y0 = n = 0
        return y0, n


    def display_cursorbar(self):
        if self == self.app.act_pane:
            attr_noselected = curses.color_pair(3)
            attr_selected = curses.color_pair(11) | curses.A_BOLD
        else:
            if self.app.prefs.options['manage_otherpane']:
                attr_noselected = curses.color_pair(20)
                attr_selected = curses.color_pair(21)
            else:
                return
        if self.mode == PANE_MODE_FULL:
            cursorbar = curses.newpad(1, self.maxw)
        else:
            cursorbar = curses.newpad(1, self.dims[1]-1)
        cursorbar.bkgd(curses.color_pair(3))
        cursorbar.erase()

        tab = self.act_tab
        filename = tab.sorted[tab.file_i]
        try:
            tab.selections.index(filename)
        except ValueError:
            attr = attr_noselected
        else:
            attr = attr_selected

        res = files.get_fileinfo_dict(tab.path, filename, tab.files[filename])
        if self.mode == PANE_MODE_FULL:
            buf = tab.get_fileinfo_str_long(res, self.maxw)
            cursorbar.addstr(0, 0, utils.encode(buf), attr)
            cursorbar.refresh(0, 0,
                              tab.file_i % self.dims[0] + 1, 0,
                              tab.file_i % self.dims[0] + 1, self.maxw-2)
        else:
            buf = tab.get_fileinfo_str_short(res, self.dims[1], self.pos_col1)
            cursorbar.addstr(0, 0, utils.encode(buf), attr)
            cursorbar.addch(0, self.pos_col1-1, curses.ACS_VLINE, attr)
            cursorbar.addch(0, self.pos_col2-1, curses.ACS_VLINE, attr)
            row = tab.file_i % (self.dims[0]-3) + 3
            if self.mode == PANE_MODE_LEFT:
                cursorbar.refresh(0, 0,
                                  row, 1, row, int(self.maxw/2)-2)
            else:
                cursorbar.refresh(0, 0,
                                  row, int(self.maxw/2)+1, row, self.maxw-2)


    def regenerate(self):
        """Rebuild tabs' directories, this is needed because panel
        could be changed"""

        for tab in self.tabs:
            tab.backup()
            tab.regenerate()
            tab.fix_limits()
            tab.restore()


    def manage_keys(self):
        self.win.nodelay(1)
        while True:
            ch = self.win.getch()
            if ch == -1:       # no key pressed
                # curses.napms(1)
                time.sleep(0.05)
                curses.doupdate()
                continue
            # print 'key: \'%s\' <=> %c <=> 0x%X <=> %d' % \
            #       (curses.keyname(ch), ch & 255, ch, ch)
            # messages.win('Keyboard hitted:',
            #              'key: \'%s\' <=> %c <=> 0x%X <=> %d' % \
            #              (curses.keyname(ch), ch & 255, ch, ch))
            ret = actions.do(self.act_tab, ch)
            if ret is None:
                self.app.display()
            elif ret == RET_NO_UPDATE:
                continue
            elif ret == RET_HALF_UPDATE:
                self.app.half_display()
            elif ret == RET_HALF_UPDATE_OTHER:
                self.app.half_display_other()
            else:
                return ret


######################################################################
##### Vfs class
class Vfs(object):
    """Vfs class contains files information in a directory"""

    def __init__(self):
        self.path = ''
        self.nfiles = 0
        self.files = []
        self.sorted = []
        self.selections = []
        self.sort_mode = 0
        # vfs variables
        self.vfs = ''          # vfs? if not -> blank string
        self.base = ''         # tempdir basename
        self.vbase = self.path # virtual directory basename
        # history
        self.history = []


    def init_dir(self, path):
        old_path = self.path if self.path and not self.vfs else ''
        try:
            app = self.pane.app
            self.nfiles, self.files = files.get_dir(path, app.prefs.options['show_dotfiles'])
            sortmode = app.prefs.options['sort']
            sort_mix_dirs = app.prefs.options['sort_mix_dirs']
            sort_mix_cases = app.prefs.options['sort_mix_cases']
            self.sorted = files.sort_dir(self.files, sortmode,
                                         sort_mix_dirs, sort_mix_cases)
            self.sort_mode = sortmode
            self.path = os.path.abspath(path)
            self.selections = []
        except (IOError, OSError), (errno, strerror):
            if len(self.history) > 0:
                self.history.pop()
            return (strerror, errno)
        # vfs variables
        self.vfs = ''
        self.base = ''
        self.vbase = self.path
        # history
        if old_path:
            if old_path in self.history:
                self.history.remove(old_path)
            self.history.append(old_path)
            self.history = self.history[-MAX_TAB_HISTORY:]


    def init(self, path, old_file = ''):
        raise NotImplementedError


    def enter_dir(self, filename):
        if self.vfs:
            if self.path == self.base and filename == os.pardir:
                vfs.exit(self)
                self.init(os.path.dirname(self.vbase),
                          old_file=os.path.basename(self.vbase).replace('#vfs', ''))
            else:
                pvfs, base, vbase = self.vfs, self.base, self.vbase
                self.init(os.path.join(self.path, filename))
                self.vfs, self.base, self.vbase = pvfs, base, vbase
        else:
            if filename == os.pardir:
                self.init(os.path.dirname(self.path),
                          old_file=os.path.basename(self.path))
            else:
                self.init(os.path.join(self.path, filename),
                          old_file=self.sorted[self.file_i],
                          check_oldfile=False)


    def exit_dir(self):
        if self.vfs:
            if self.path == self.base:
                vfs.exit(self)
                self.init(os.path.dirname(self.vbase),
                          old_file=os.path.basename(self.vbase).replace('#vfs', ''))
            else:
                pvfs, base, vbase = self.vfs, self.base, self.vbase
                self.init(os.path.dirname(self.path),
                          old_file=os.path.basename(self.path))
                self.vfs, self.base, self.vbase = pvfs, base, vbase
        else:
            if self.path != os.sep:
                self.init(os.path.dirname(self.path),
                          old_file=os.path.basename(self.path))


    def backup(self):
        self.old_file = self.sorted[self.file_i]
        self.old_file_i = self.file_i
        self.old_vfs = self.vfs, self.base, self.vbase


    def restore(self):
        try:
            self.file_i = self.sorted.index(self.old_file)
        except ValueError:
            if self.old_file_i < len(self.sorted):
                self.file_i = self.old_file_i
            else:
                self.file_i = len(self.sorted) - 1
        self.vfs, self.base, self.vbase = self.old_vfs
        del self.old_file
        del self.old_file_i
        del self.old_vfs


    def regenerate(self):
        """Rebuild tabs' directories"""

        path = self.path
        if path != os.sep and path[-1] == os.sep:
            path = path[:-1]
        while not os.path.exists(path):
            path = os.path.dirname(path)

        if path != self.path:
            self.path = path
            self.file_i = 0
            pvfs, base, vbase = self.vfs, self.base, self.vbase
            self.init_dir(self.path)
            self.vfs, self.base, self.vbase = pvfs, base, vbase
            self.selections = []
        else:
            filename_old = self.sorted[self.file_i]
            selections_old = self.selections[:]
            pvfs, base, vbase = self.vfs, self.base, self.vbase
            self.init_dir(self.path)
            self.vfs, self.base, self.vbase = pvfs, base, vbase
            try:
                self.file_i = self.sorted.index(filename_old)
            except ValueError:
                self.file_i = 0
            self.selections = selections_old[:]
            for f in self.selections:
                if f not in self.sorted:
                    self.selections.remove(f)


    def refresh(self):
        file_i_old = self.file_i
        file_old = self.sorted[self.file_i]
        self.pane.app.regenerate()
        try:
            self.file_i = self.sorted.index(file_old)
        except ValueError:
            self.file_i = file_i_old
        self.fix_limits()


    def get_fileinfo_str_short(self, res, maxw, pos_col1):
        filewidth = maxw - 24
        fname = res['filename']
        if len(fname) > filewidth:
            half = int(filewidth/2)
            fname = fname[:half+2] + '~' + fname[-half+3:]
        fname = fname.ljust(pos_col1-2)[:pos_col1-2]
        res['fname'] = fname
        if res['dev']:
            res['devs'] = '%3d,%d' % (res['maj_rdev'], res['min_rdev'])
            buf = u'%(type_chr)c%(fname)s %(devs)7s %(mtime2)12s' % res
        else:
            buf = u'%(type_chr)c%(fname)s %(size)7s %(mtime2)12s' % res
        return buf


    def get_fileinfo_str_long(self, res, maxw):
        filewidth = maxw - 62
        fname = res['filename']
        if len(fname) > filewidth:
            half = int(filewidth/2)
            fname = fname[:half+2] + '~' + fname[-half+2:]
        res['fname'] = fname
        res['owner'] = res['owner'][:10]
        res['group'] = res['group'][:10]
        if res['dev']:
            res['devs'] = '%3d,%d' % (res['maj_rdev'], res['min_rdev'])
            buf = u'%(type_chr)c%(perms)9s %(owner)-10s %(group)-10s %(devs)7s  %(mtime)16s  %(fname)s' % res
        else:
            buf = u'%(type_chr)c%(perms)9s %(owner)-10s %(group)-10s %(size)7s  %(mtime)16s  %(fname)s' % res
        return buf


    def get_file(self):
        """return pointed file"""
        return self.sorted[self.file_i]


    def get_fullpathfile(self):
        """return full path for pointed file"""
        return os.path.join(self.path, self.sorted[self.file_i])


######################################################################
##### TabVfs class
class TabVfs(Vfs):
    """TabVfs class is the UI container for Vfs class"""

    def __init__(self, pane):
        Vfs.__init__(self)
        self.pane = pane


    def init(self, path, old_file='', check_oldfile=True):
        err = self.init_dir(path)
        if err:
            messages.error('Cannot change directory\n%s: %s (%d)' % (path, err[0], err[1]))
        if (check_oldfile and old_file) or (old_file and err):
            try:
                self.file_i = self.sorted.index(old_file)
            except ValueError:
                self.file_i = 0
        else:
            self.file_i = 0
        self.fix_limits()
        return err


    def fix_limits(self):
        self.file_i = max(0, min(self.file_i, self.nfiles-1))
        if self.pane.mode == PANE_MODE_HIDDEN or \
                self.pane.mode == PANE_MODE_FULL:
            height = self.pane.dims[0]
        else:
            height = self.pane.dims[0] - 3
        self.file_a = int(self.file_i/height) * height
        self.file_z = min(self.file_a+height-1, self.nfiles-1)


######################################################################
##### Utils
def num2str(num):
    # Thanks to "Fatal" in #pys60
    num = str(num)
    return (len(num) < 4) and num or (num2str(num[:-3])+","+num[-3:])


######################################################################
##### Main
def usage(msg=''):
    if msg != "":
        print 'lfm:\tERROR: %s\n' % msg
    print __doc__


def lfm_exit(ret_code, ret_path=u'.'):
    f = open('/tmp/lfm-%s.path' % (os.getppid()), 'w')
    f.write(utils.encode(ret_path))
    f.close()
    sys.exit(ret_code)


def main(win, prefs, paths1, paths2):
    app = Lfm(win, prefs)
    app.load_paths(paths1, paths2)
    if app == OSError:
        sys.exit(-1)
    ret = app.run()
    return ret


def add_path(arg, paths):
    buf = os.path.abspath(arg)
    if not os.path.isdir(buf):
        usage('<%s> is not a directory' % arg)
        lfm_exit(-1)
    paths.append(buf)


def lfm_start(sysargs):
    # get configuration & preferences
    DEBUG = False
    paths1, paths2 = [], []
    prefs = Config()
    ret = prefs.load()
    if ret == -1:
        print 'Config file does not exist, we\'ll use default values'
        prefs.save()
        time.sleep(1)
    elif ret == -2:
        print 'Config file looks corrupted, we\'ll use default values'
        prefs.save()
        time.sleep(1)

    # parse args
    try:
        opts, args = getopt.getopt(sysargs[1:], '12dh', ['debug', 'help'])
    except getopt.GetoptError:
        usage('Bad argument(s)')
        lfm_exit(-1)
    for o, a in opts:
        if o == '-1':
            prefs.options['num_panes'] = 1
        if o == '-2':
            prefs.options['num_panes'] = 2
        if o in ('-d', '--debug'):
            DEBUG = True
        if o in ('-h', '--help'):
            usage()
            lfm_exit(2)

    if len(args) == 0:
        paths1.append(os.path.abspath(u'.'))
        paths2.append(os.path.abspath(u'.'))
    elif len(args) == 1:
        add_path(args[0], paths1)
        paths2.append(os.path.abspath(u'.'))
    elif len(args) == 2:
        add_path(args[0], paths1)
        add_path(args[1], paths2)
    else:
        usage('Incorrect number of arguments')
        lfm_exit(-1)

    # history
    if prefs.options['save_history_at_exit']:
        try:
            messages.history = pickle.load(file(messages.HISTORY_FILE, 'r'))
        except:
            messages.history = messages.DEFAULT_HISTORY.copy()
    else:
        messages.history = messages.DEFAULT_HISTORY.copy()

    # logging
    if DEBUG:
        log_file = os.path.join(os.path.abspath(u'.'), LOG_FILE)
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s\t%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S   ',
                            filename=log_file,
                            filemode='w')
    logging.info('Starting Lfm...')

    # main app
    logging.info('Main application call')
    path = curses.wrapper(main, prefs, paths1, paths2)
    logging.info('End')

    # change to directory
    if path is not None:
        lfm_exit(0, path)
    else:
        lfm_exit(0)


if __name__ == '__main__':
    lfm_start(sys.argv)


######################################################################
