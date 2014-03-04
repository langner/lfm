# -*- coding: utf-8 -*-

"""messages.py

This module contains some windows for lfm use.
"""


import sys
import os.path
import curses
import curses.panel
import files
import utils


######################################################################
##### module variables
app = None


######################################################################
##### history stuff
HISTORY_FILE = os.path.abspath(os.path.expanduser('~/.lfm_history'))
DEFAULT_HISTORY = {'path': [], 'file': [], 'glob': [], 'grep': [], 'exec': [], 'cli': []}
MAX_HISTORY = 100
history = DEFAULT_HISTORY.copy()

def add_to_history(hist, text):
    if text and text != '*':
        if text in hist:
            hist.remove(text)
        if len(hist) >= MAX_HISTORY:
            hist.remove(hist[0])
        hist.append(text)


######################################################################
class BaseWindow(object):
    """Base class for CommonWindow and FixSizeWindow classes"""

    def init_ui(self, h, w, title, text, br_bg, br_att, bd_att, bd_bg):
        try:
            win = curses.newwin(h, w,
                                int((app.maxh-h)/2), int((app.maxw-w)/2))
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.bkgd(br_bg, br_att)
        win.erase()
        win.box(0, 0)
        if len(title) > app.maxw - 14:
            title = title[:app.maxw-10] + '...' + '\''
        win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
                   curses.A_BOLD)
        try:
            text = utils.encode(text)
        except UnicodeDecodeError:
            pass
        for i, l in enumerate(text.split('\n')):
            win.addstr(i+2, 2, l, bd_att)
        if self.waitkey:
            win.addstr(h-1, int((w-27)/2), ' Press any key to continue ', br_att)
        win.refresh()
        win.keypad(1)
        self.win = win

    def run(self):
        if self.waitkey:
            while not self.pwin.window().getch():
                pass
        self.pwin.hide()


class CommonWindow(BaseWindow):
    """A superclass for 'error' and 'win' windows"""

    def __init__(self, title, text, br_att, br_bg, bd_att, bd_bg, waitkey=True):
        self.waitkey = waitkey
        text = text.strip().replace('\t', ' ' * 2)
        lines = text.split('\n')
        w = max(max(map(len, lines))+4, 40)
        if w > app.maxw - 10:
            w = app.maxw - 10
            newlines = []
            for l in lines:
                while len(l) > w-4:
                    newlines.append(l[:w-4])
                    l = l[w-4:]
                newlines.append(l)
            lines = newlines
            text = '\n'.join(lines)
        h = len(lines) + 4
        if h > app.maxh - 6:
            h = app.maxh - 6
            text = '\n'.join(lines[:app.maxh-10])
        self.init_ui(h, w, title, text, br_bg, br_att, bd_att, bd_bg)


class FixSizeCommonWindow(BaseWindow):
    """A superclass for messages, with fixed size"""

    def __init__(self, title, text, footer, br_att, br_bg, bd_att, bd_bg,
                 waitkey=True):
        self.waitkey = waitkey
        text = text.replace('\t', ' ' * 4)
        w = app.maxw - 20
        if len(title) > w - 4:
            title = title[:w-4]
        if len(text) > w - 4:
            text = text[:w-5]
        if len(footer) > w - 4:
            footer = footer[:w-4]
        self.init_ui(5, w, title, text, br_bg, br_att, bd_att, bd_bg)
        if footer and not self.waitkey:
            self.win.addstr(4, int((w-len(footer)-2)/2),
                            ' %s ' % utils.encode(footer), br_att)
            self.win.refresh()


def error(text):
    """show an error window"""

    CommonWindow('Error', text,
                 curses.color_pair(8), curses.color_pair(8),
                 curses.color_pair(7) | curses.A_BOLD,
                 curses.color_pair(7)).run()


def win(title, text):
    """show a message window and wait for a key"""

    CommonWindow(title, text,
                 curses.color_pair(1), curses.color_pair(1),
                 curses.color_pair(1), curses.color_pair(1)).run()


def win_nokey(title, text, footer=''):
    """show a message window, does not wait for a key"""

    FixSizeCommonWindow(title, text, footer,
                        curses.color_pair(1), curses.color_pair(1),
                        curses.color_pair(1), curses.color_pair(1),
                        waitkey = 0).run()


def notyet(title):
    """show a not-yet-implemented message"""

    CommonWindow(title,
                 'Sorry, but this function\nis not implemented yet!',
                 curses.color_pair(1) | curses.A_BOLD, curses.color_pair(1),
                 curses.color_pair(4), curses.color_pair(4)).run()


######################################################################
class ProgressBarWindowBase(object):
    """Window with 1 or 2 ProgressBar"""

    def __init__(self, title, footer, bd_att, bd_bg, pb_att, pb_bg,
                 waitkey=True, num_pb=1):
        w = app.maxw - 30
        if len(title) > w - 4:
            title = title[:w-4]
        if len(footer) > w - 4:
            footer = footer[:w-4]
        if num_pb == 1:
            h, pb_width = 7, w-10
        else:
            h, pb_width = 8, w-17
        self.h, self.w = h, w
        self.bd_att, self.pb_att = bd_att, pb_att
        self.progressbars = []
        try:
            win = curses.newwin(h, w,
                                int((app.maxh-h)/2), int((app.maxw-w)/2))
            for i in xrange(num_pb):
                self.progressbars.append(curses.newpad(1, pb_width))
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.keypad(1)
        win.nodelay(1)
        win.bkgd(bd_bg, bd_att)
        for pb in self.progressbars:
            pb.bkgd(' ', pb_bg)
        self.title = title
        self.footer = footer
        self.waitkey = waitkey
        self.ishidden = True
        self.y0 = int((app.maxh-self.h)/2) + 4

    def finish(self):
        self.pwin.window().nodelay(0)

    def getch(self):
        return self.pwin.window().getch()

    def show_common(self):
        win = self.pwin.window()
        win.erase()
        win.box(0, 0)
        win.addstr(0, int((self.w-len(self.title)-2)/2),
                   ' %s ' % utils.encode(self.title), curses.A_BOLD)
        win.addstr(2, 2, 'File:  ')
        if self.waitkey:
            win.addstr(self.h-1, int((self.w-27)/2), ' Press any key to continue ')
        elif self.footer:
            win.addstr(self.h-1, int((self.w-len(self.footer)-2)/2),
                       ' %s ' % utils.encode(self.footer))
        self.ishidden = False
        return win

    def update_common(self, text, idx_str=''):
        win = self.pwin.window()
        maxlen = self.w - 23 # 11 + len("12345/67890") + 1
        if len(text) > maxlen:
            text = text[:maxlen/2-1] + '~' + text[-maxlen/2:]
        else:
            text = text.ljust(maxlen)
        win.addstr(2, 9, utils.encode(text), curses.A_BOLD)
        y = self.w - len(idx_str) - 2
        win.addstr(2, y, idx_str)
        return win


class ProgressBarWindow(ProgressBarWindowBase):
    def __init__(self, title, footer, bd_att, bd_bg, pb_att, pb_bg, waitkey=True):
        super(ProgressBarWindow, self).__init__(title, footer, bd_att, bd_bg,
                                                pb_att, pb_bg, waitkey, 1)
        self.x0 = int((app.maxw-self.w)/2) + 2
        self.x1 = self.x0 + self.w - 12

    def show(self, text='', percent=0, idx_str=''):
        win = self.show_common()
        win.addstr(self.h-3, self.w-8, '[   %]')
        self.update(text, percent, idx_str)

    def update(self, text, percent, idx_str):
        win = self.update_common(text, idx_str)
        win.addstr(self.h-3, self.w-7, '%3d' % percent)
        w1 = percent * (self.w-11) / 100
        pb = self.progressbars[0]
        pb.erase()
        pb.addstr(0, 0, ' ' * w1, self.pb_att | curses.A_BOLD)
        pb.refresh(0, 0, self.y0, self.x0, self.y0+1, self.x1)
        win.refresh()


class ProgressBarWindow2(ProgressBarWindowBase):
    def __init__(self, title, footer, bd_att, bd_bg, pb_att, pb_bg, waitkey=True):
        super(ProgressBarWindow2, self).__init__(title, footer, bd_att, bd_bg,
                                                 pb_att, pb_bg, waitkey, 2)
        self.x0 = int((app.maxw-self.w)/2) + 9
        self.x1 = self.x0 + self.w - 19

    def show(self, text='', percent1=0, percent2=0, idx_str=''):
        win = self.show_common()
        win.addstr(self.h-4, 2, 'Bytes' + ' '*(self.w-15) + '[   %]')
        win.addstr(self.h-3, 2, 'Count' + ' '*(self.w-15) + '[   %]')
        self.update(text, percent1, percent2, idx_str)

    def update(self, text, percent1, percent2, idx_str):
        win = self.update_common(text, idx_str)
        win.addstr(self.h-4, self.w-7, '%3d' % percent1)
        win.addstr(self.h-3, self.w-7, '%3d' % percent2)
        w1 = percent1 * (self.w-18) / 100
        pb1 = self.progressbars[0]
        pb1.erase()
        pb1.addstr(0, 0, ' ' * w1, self.pb_att | curses.A_BOLD)
        pb1.refresh(0, 0, self.y0, self.x0, self.y0+1, self.x1)
        w2 = percent2 * (self.w-18) / 100
        pb2 = self.progressbars[1]
        pb2.erase()
        pb2.addstr(0, 0, ' ' * w2, self.pb_att | curses.A_BOLD)
        pb2.refresh(0, 0, self.y0+1, self.x0, self.y0+2, self.x1)
        win.refresh()


######################################################################
def get_a_key(title, question):
    """show a window returning key pressed"""

    question = question.replace('\t', ' ' * 4)
    lines = question.split('\n')
    length = max(map(len, lines))
    h = min(len(lines)+4, app.maxh-2)
    w = min(length+4, app.maxw-2)
    try:
        win = curses.newwin(h, w, int((app.maxh-h)/2), int((app.maxw-w)/2))
        pwin = curses.panel.new_panel(win)
        pwin.top()
    except curses.error:
        print 'Can\'t create window'
        sys.exit(-1)
    win.bkgd(curses.color_pair(1))

    win.erase()
    win.box(0, 0)
    win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
               curses.color_pair(1) | curses.A_BOLD)
    for row, l in enumerate(lines):
        win.addstr(row+2, 2, utils.encode(l))
    win.refresh()
    win.keypad(1)
    while True:
        ch = win.getch()
        if ch in (0x03, 0x1B):       # Ctrl-C, ESC
            pwin.hide()
            return -1
        elif 0x01 <= ch <= 0xFF:
            pwin.hide()
            return ch
        else:
            curses.beep()


######################################################################
def confirm(title, question, default=0):
    """show a yes/no window, returning 1/0"""

    BTN_SELECTED = curses.color_pair(9) | curses.A_BOLD
    BTN_NO_SELECTED = curses.color_pair(1) | curses.A_BOLD

    h, w = 5, min(max(34, len(question)+5), app.maxw-2)
    try:
        win = curses.newwin(h, w, int((app.maxh-h)/2), int((app.maxw-w)/2))
        pwin = curses.panel.new_panel(win)
        pwin.top()
    except curses.error:
        print 'Can\'t create window'
        sys.exit(-1)
    win.bkgd(curses.color_pair(1))

    win.erase()
    win.box(0, 0)
    win.addstr(0, int((w-len(title)-2)/2), ' %s' % \
                   utils.encode(title.capitalize()),
               curses.color_pair(1) | curses.A_BOLD)
    win.addstr(1, 2 , '%s?' % utils.encode(question))
    win.refresh()

    row = int((app.maxh-h)/2) + 3
    col = int((app.maxw-w)/2)
    col1 = col + int(w/5) + 1
    col2 = col + int(w*4/5) - 6
    win.keypad(1)
    answer = default
    while True:
        if answer == 1:
            attr_yes, attr_no = BTN_SELECTED, BTN_NO_SELECTED
        else:
            attr_yes, attr_no = BTN_NO_SELECTED, BTN_SELECTED
        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[ Yes ]', attr_yes)
        btn.refresh(0, 0, row, col1, row + 1, col1 + 6)
        btn = curses.newpad(1, 7)
        btn.addstr(0, 0, '[ No ]', attr_no)
        btn.refresh(0, 0, row, col2, row + 1, col2 + 5)

        ch = win.getch()
        if ch in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT,
                  curses.KEY_RIGHT, 9):
            answer = not answer
        elif ch in (ord('Y'), ord('y')):
            answer = 1
            break
        elif ch in (ord('N'), ord('n')):
            answer = 0
            break
        elif ch in (0x03, 0x1B):    # Ctrl-C, ESC
            answer = -1
            break
        elif ch in (10, 13):        # enter
            break
        else:
            curses.beep()

    pwin.hide()
    return answer


def confirm_all(title, question, default = 0):
    """show a yes/all/no/stop window, returning 1/2/0/-1"""

    BTN_SELECTED = curses.color_pair(9) | curses.A_BOLD
    BTN_NO_SELECTED = curses.color_pair(1) | curses.A_BOLD

    h, w = 5, min(max(45, len(question)+5), app.maxw-2)
    try:
        win = curses.newwin(h, w, int((app.maxh-h)/2), int((app.maxw-w)/2))
        pwin = curses.panel.new_panel(win)
        pwin.top()
    except curses.error:
        print 'Can\'t create window'
        sys.exit(-1)
    win.bkgd(curses.color_pair(1))

    win.erase()
    win.box(0, 0)
    win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
               curses.color_pair(1) | curses.A_BOLD)
    win.addstr(1, 2 , '%s?' % utils.encode(question))
    win.refresh()

    row = int((app.maxh-h) / 2) + 3
    col = int((app.maxw-w) / 2)
    x = (w-28) / 5
    col1 = col + x + 1
    col2 = col1 + 7 + x
    col3 = col2 + 7 + x
    col4 = col3 + 6 + x

    win.keypad(1)
    answer = default
    order = [1, 2, 0, -1]
    while True:
        attr_yes = attr_all = attr_no = attr_skipall = BTN_NO_SELECTED
        if answer == 1:
            attr_yes = BTN_SELECTED
        elif answer == 2:
            attr_all = BTN_SELECTED
        elif answer == 0:
            attr_no = BTN_SELECTED
        elif answer == -1:
            attr_skipall = BTN_SELECTED
        else:
            raise ValueError
        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[ Yes ]', attr_yes)
        btn.refresh(0, 0, row, col1, row + 1, col1 + 6)
        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[ All ]', attr_all)
        btn.refresh(0, 0, row, col2, row + 1, col2 + 6)
        btn = curses.newpad(1, 7)
        btn.addstr(0, 0, '[ No ]', attr_no)
        btn.refresh(0, 0, row, col3, row + 1, col3 + 5)
        btn = curses.newpad(1, 15)
        btn.addstr(0, 0, '[ Stop ]', attr_skipall)
        btn.refresh(0, 0, row, col4, row + 1, col4 + 7)

        ch = win.getch()
        if ch in (curses.KEY_UP, curses.KEY_LEFT):
            try:
                answer = order[order.index(answer) - 1]
            except IndexError:
                answer = order[len(order)]
        if ch in (curses.KEY_DOWN, curses.KEY_RIGHT, 9):
            try:
                answer = order[order.index(answer) + 1]
            except IndexError:
                answer = order[0]
        elif ch in (ord('Y'), ord('y')):
            answer = 1
            break
        elif ch in (ord('A'), ord('a')):
            answer = 2
            break
        elif ch in (ord('N'), ord('n')):
            answer = 0
            break
        elif ch in (ord('S'), ord('s'), 0x03, 0x1B):    # Ctrl-C, ESC
            answer = -1
            break
        elif ch in (10, 13):        # enter
            break
        else:
            curses.beep()

    pwin.hide()
    return answer


def confirm_all_none(title, question, default = 0):
    """show a yes/all/no/none/stop window, returning 1/2/0/-2/-1"""

    BTN_SELECTED = curses.color_pair(9) | curses.A_BOLD
    BTN_NO_SELECTED = curses.color_pair(1) | curses.A_BOLD

    h, w = 5, min(max(50, len(question)+5), app.maxw-2)
    try:
        win = curses.newwin(h, w, int((app.maxh-h)/2), int((app.maxw-w)/2))
        pwin = curses.panel.new_panel(win)
        pwin.top()
    except curses.error:
        print 'Can\'t create window'
        sys.exit(-1)
    win.bkgd(curses.color_pair(1))

    win.erase()
    win.box(0, 0)
    win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
               curses.color_pair(1) | curses.A_BOLD)
    win.addstr(1, 2 , '%s?' % utils.encode(question))
    win.refresh()

    row = int((app.maxh-h) / 2) + 3
    col = int((app.maxw-w) / 2)
    x = (w-36) / 6
    col1 = col + x + 1
    col2 = col1 + 7 + x
    col3 = col2 + 7 + x
    col4 = col3 + 6 + x
    col5 = col4 + 8 + x

    win.keypad(1)
    answer = default
    order = [1, 2, 0, -2, -1]
    while True:
        attr_yes, attr_all, attr_no, attr_none, attr_skipall = [BTN_NO_SELECTED] * 5
        if answer == 1:
            attr_yes = BTN_SELECTED
        elif answer == 2:
            attr_all = BTN_SELECTED
        elif answer == 0:
            attr_no = BTN_SELECTED
        elif answer == -2:
            attr_none = BTN_SELECTED
        elif answer == -1:
            attr_skipall = BTN_SELECTED
        else:
            raise ValueError

        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[ Yes ]', attr_yes)
        btn.refresh(0, 0, row, col1, row + 1, col1 + 6)
        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[ All ]', attr_all)
        btn.refresh(0, 0, row, col2, row + 1, col2 + 6)
        btn = curses.newpad(1, 7)
        btn.addstr(0, 0, '[ No ]', attr_no)
        btn.refresh(0, 0, row, col3, row + 1, col3 + 5)
        btn = curses.newpad(1, 9)
        btn.addstr(0, 0, '[ NOne ]', attr_none)
        btn.refresh(0, 0, row, col4, row + 1, col4 + 7)
        btn = curses.newpad(1, 9)
        btn.addstr(0, 0, '[ Stop ]', attr_skipall)
        btn.refresh(0, 0, row, col5, row + 1, col5 + 7)

        ch = win.getch()
        if ch in (curses.KEY_UP, curses.KEY_LEFT):
            try:
                answer = order[order.index(answer) - 1]
            except IndexError:
                answer = order[len(order)]
        if ch in (curses.KEY_DOWN, curses.KEY_RIGHT, 9):
            try:
                answer = order[order.index(answer) + 1]
            except IndexError:
                answer = order[0]
        elif ch in (ord('Y'), ord('y')):
            answer = 1
            break
        elif ch in (ord('A'), ord('a')):
            answer = 2
            break
        elif ch in (ord('N'), ord('n')):
            answer = 0
            break
        elif ch in (ord('O'), ord('o')):
            answer = -2
            break
        elif ch in (ord('S'), ord('s'), 0x03, 0x1B):    # Ctrl-C, ESC
            answer = -1
            break
        elif ch in (10, 13):        # enter
            break
        else:
            curses.beep()

    pwin.hide()
    return answer


######################################################################
class Yes_No_Buttons(object):
    """Yes/No buttons"""

    def __init__(self, w, h, d):
        self.row = int((app.maxh-h) / 2) + 4 + d
        col = int((app.maxw-w) / 2)
        self.col1 = col + int(w/5) + 1
        self.col2 = col + int(w*4/5) - 6
        self.active = 0


    def show(self):
        BTN_SELECTED = curses.color_pair(9) | curses.A_BOLD
	BTN_NO_SELECTED = curses.color_pair(1) | curses.A_BOLD
        if self.active == 0:
            attr1, attr2 = BTN_NO_SELECTED, BTN_NO_SELECTED
        elif self.active == 1:
            attr1, attr2 = BTN_SELECTED, BTN_NO_SELECTED
        else:
            attr1, attr2 = BTN_NO_SELECTED, BTN_SELECTED
        btn = curses.newpad(1, 8)
        btn.addstr(0, 0, '[<Yes>]', attr1)
        btn.refresh(0, 0, self.row, self.col1, self.row + 1, self.col1 + 6)
        btn = curses.newpad(1, 7)
        btn.addstr(0, 0, '[ No ]', attr2)
        btn.refresh(0, 0, self.row, self.col2, self.row + 1, self.col2 + 5)


    def manage_keys(self):
        tmp = curses.newpad(1, 1)
        while True:
            ch = tmp.getch()
            if ch in (0x03, 0x1B):      # Ctrl-C, ESC
                return -1
            elif ch == ord('\t'):
                return ch
            elif ch in (10, 13):        # enter
                if self.active == 1:
                    return 10
                else:
                    return -1
            else:
                curses.beep()


######################################################################
# helper functions
def get_char_raw(win, first_byte):
    try:
        return unichr(first_byte)
    except:
        raise UnicodeError

def get_char_ascii(win, first_byte):
    try:
        if first_byte < 127: # <= 127
            return chr(first_byte).decode('ascii')
        else:
            raise UnicodeError
    except:
        raise UnicodeError

def get_char_codec(win, first_byte, encoding):
    try:
        if first_byte <= 255:
            return chr(first_byte).decode(encoding)
        else:
            raise UnicodeError
    except:
        raise UnicodeError

def get_char_utf8(win, first_byte):
    def get_check_next_byte():
        c = win.getch()
        if 128 <= c <= 191:
            return c
        else:
            raise UnicodeError

    bytes = []
    if first_byte <= 127:
        # 1 bytes
        bytes.append(first_byte)
    elif 194 <= first_byte <= 223:
        # 2 bytes
        bytes.append(first_byte)
        bytes.append(get_check_next_byte())
    elif 224 <= first_byte <= 239:
        # 3 bytes
        bytes.append(first_byte)
        bytes.append(get_check_next_byte())
        bytes.append(get_check_next_byte())
    elif 240 <= first_byte <= 244:
        # 4 bytes
        bytes.append(first_byte)
        bytes.append(get_check_next_byte())
        bytes.append(get_check_next_byte())
        bytes.append(get_check_next_byte())
    buf = ''.join([chr(b) for b in bytes])
    return buf.decode('utf-8')

def get_char(win, first_byte):
    from __init__ import g_encoding
    try:
        if g_encoding is None:
            return get_char_raw(win, first_byte)
        elif g_encoding == 'UTF-8':
            return get_char_utf8(win, first_byte)
        elif g_encoding == 'ASCII':
            return get_char_ascii(win, first_byte)
        else:
            return get_char_codec(win, first_byte, g_encoding)
    except UnicodeError:
        return unichr(first_byte)


######################################################################
class EntryLine(object):
    """An entry line to enter a dir. or file, a pattern, etc"""

    def __init__(self, w, h, x, y, path, with_history, with_complete,
                 panelpath, cli=False):
        try:
            self.entry = curses.newwin(1, w-4+1, x, y)
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        self.cli = cli
        self.with_complete = with_complete
        if with_history in history.keys():
            self.history = history[with_history][:]
            self.history_i = len(self.history)
        else:
            self.history = None
        self.colour = curses.color_pair(25) if cli else curses.color_pair(11)|curses.A_BOLD
        self.entry.attrset(self.colour)
        self.entry.keypad(1)
        self.entry_width = w - 4
        self.origtext = path
        self.text = path
        self.panelpath = panelpath
        self.pos = len(self.text)
        self.ins = True


    def show(self):
        text, pos, ew, ltext = self.text, self.pos, self.entry_width, len(self.text)
        if pos < ew:
            relpos = pos
            textstr = (ltext > ew) and text[:ew] or text.ljust(ew)
        else:
            if pos > ltext - (ew-1):
                relpos = ew-1 - (ltext-pos)
                textstr = text[ltext-ew+1:] + ' '
            else:
                relpos = pos - int(pos/ew)*ew
                textstr = text[int(pos/ew)*ew:int(pos/ew)*ew+ew]
        self.entry.bkgd(curses.color_pair(1))
        self.entry.erase()
        self.entry.addstr(utils.encode(textstr[:ew]), self.colour)
        self.entry.move(0, relpos)
        self.entry.refresh()


    def manage_keys(self):
        import string
        stepchars = string.whitespace + string.punctuation

        def __prev_step(pos):
            pos -= 1
            while pos > 0 and self.text[pos] not in stepchars:
                pos -=1
            return pos if pos > 0 else 0

        def __next_step(pos):
            pos += 1
            l = len(self.text)
            while pos < l and self.text[pos] not in stepchars:
                pos +=1
            return pos if pos < l  else l

        def __select_item(entries, pos0, title='', cli=False):
            if not entries:
                curses.beep()
                return
            elif len(entries) == 1:
                return entries.pop()
            else:
                y, x0 = self.entry.getbegyx()
                x = x0 + pos0
                if x > 2*app.maxw/3 - 4:
                    x = x0 + 2
                if cli:
                    y = app.maxh / 2 - 2
                selected = SelectItem(entries, y+1, x-2, title=title).run()
                if cli:
                    app.lpane.display()
                    app.rpane.display()
                else:
                    app.display()
                cursor_show2()
                return selected

        while True:
            self.show()
            ch = self.entry.getch()
            # print 'key: \'%s\' <=> %c <=> 0x%X <=> %d' % \
            #      (curses.keyname(ch), ch & 255, ch, ch)
            if ch in (0x03, 0x1B) and not self.cli:       # Ctrl-C, ESC
                return -1
            elif ch == 0x18 and self.cli:                 # Ctrl-X
                return -1
            # history
            elif ch == curses.KEY_UP:
                if self.history is not None and self.history_i > 0:
                    if self.history_i == len(self.history):
                        if self.text is None:
                            self.text = ''
                        self.history.append(self.text)
                    self.history_i -= 1
                    self.text = self.history[self.history_i]
                    self.pos = len(self.text)
            elif ch == curses.KEY_DOWN:
                if self.history is not None and self.history_i < len(self.history)-1:
                        self.history_i += 1
                        self.text = self.history[self.history_i]
                        self.pos = len(self.text)
            # special
            elif ch == ord('\t') and not self.cli:        # tab, no CLI
                return ch
            elif ch == 0x14 and not self.cli:             # Ctrl-T, no CLI
                if self.with_complete:
                    base, entries = files.complete(self.text, self.panelpath)
                    selected = __select_item(entries, len(self.text), 'Complete', False)
                    if selected is not None and selected != -1:
                        self.text = os.path.join(base, selected)
                        self.pos = len(self.text)
                    return 0x14
                else:
                    continue
            elif ch in (ord('\t'), 0x14) and self.cli:    # tab or Ctrl-T, in CLI
                if self.text.rfind(' "', 0, self.pos) != -1:
                    pos1 = self.pos-1 if self.text[self.pos-1]=='"' else self.pos
                    pos0 = self.text.rfind(' "', 0, pos1) + 2
                else:
                    pos0 = self.text.rfind(' ', 0, self.pos) + 1
                    pos1 = self.pos
                text = self.text[pos0:pos1]
                base, entries = files.complete(text, self.panelpath)
                if pos0 == 0 or not entries:
                    base = None
                    entries = files.complete_programs(text)
                selected = __select_item(entries, pos0, 'Complete', True)
                if selected is not None and selected != -1:
                    if base is None: # system program
                        selected += ' '
                    else:            # file
                        selected = os.path.join(base, selected)
                    self.text = self.text[:pos0] + selected + self.text[pos1:]
                    self.pos = len(self.text[:pos0]+selected)
            elif ch in (10, 13):         # enter
                return 10
            # movement
            elif ch in (curses.KEY_HOME, 0x01):  # home, Ctrl-A
                self.pos = 0
            elif ch in (curses.KEY_END, 0x05):   # end, Ctrl-E
                self.pos = len(self.text)
            elif ch in (curses.KEY_LEFT, 0x02):  # <-, Ctrl-B
                if self.pos > 0:
                    self.pos -= 1
            elif ch in (curses.KEY_RIGHT, 0x06): # ->, Ctr-F
                if self.pos < len(self.text):
                    self.pos += 1
            elif ch in (0x10, 0x21C):            # Ctrl-P, Ctrl-Cursor_left
                self.pos = __prev_step(self.pos)
            elif ch in (0x0E, 0x22B):            # Ctrl-N, Ctrl-Cursor_right
                self.pos = __next_step(self.pos)
            # deletion
            elif ch in (127, curses.KEY_BACKSPACE): # Backspace
                if len(self.text) > 0 and self.pos > 0:
                    self.text = self.text[:self.pos-1] + self.text[self.pos:]
                    self.pos -= 1
            elif ch == curses.KEY_DC:            # Del
                if self.pos < len(self.text):
                    self.text = self.text[:self.pos] + self.text[self.pos+1:]
            elif ch == 0x17:                     # Ctrl-W
                self.text = ''
                self.pos = 0
            elif ch == 0x08:                     # Ctrl-H
                self.text = self.text[self.pos:]
                self.pos = 0
            elif ch == 0x0B:                     # Ctrl-K
                self.text = self.text[:self.pos]
            elif ch in (0x11, 0x107):            # Ctrl-Q, Ctrl-Backspace
                pos = __prev_step(self.pos)
                self.text = self.text[:pos] + self.text[self.pos:]
                self.pos = pos
            elif ch in (0x12, 0x202):            # Ctrl-R, Ctrl-Del
                pos = __next_step(self.pos)
                self.text = self.text[:self.pos] + self.text[pos:]
            # insertion
            elif ch == 0x1A:                     # Ctrl-Z
                self.text = self.origtext
                self.pos = len(self.text)
            elif ch == 0x16:                     # Ctrl-V
                buf = app.act_pane.act_tab.get_file()
                self.text = self.text[:self.pos] + buf + self.text[self.pos:]
                self.pos += len(buf)
            elif ch == 0x13:                     # Ctrl-S
                buf = app.act_pane.act_tab.path + os.sep
                self.text = self.text[:self.pos] + buf + self.text[self.pos:]
                self.pos += len(buf)
            elif ch == 0x0F:                     # Ctrl-O
                buf = app.noact_pane.act_tab.path + os.sep
                if self.cli:
                    buf = '"' + buf + '"'
                self.text = self.text[:self.pos] + buf + self.text[self.pos:]
                self.pos += len(buf)
            elif ch in (0x04, 0x1C):             # Ctrl-D, Ctrl-\
                selected = __select_item(app.prefs.bookmarks, self.pos if self.cli else 0,
                                         'Bookmarks', self.cli)
                if selected not in (None, -1, ''):
                    if self.cli:
                        self.text = self.text[:self.pos] + selected + self.text[self.pos:]
                        self.pos = len(self.text)
                    else:
                        self.text, self.pos = selected, len(selected)
                return 0x1C # hack, to update screen
            elif ch == 0x19:                     # Ctrl-Y
                items = app.act_pane.act_tab.history[::-1]
                items.extend(reversed([h for h in app.noact_pane.act_tab.history if h not in items]))
                if items:
                    selected = __select_item(items, self.pos if self.cli else 0,
                                             'Previous paths', self.cli)
                    if selected not in (None, -1, ''):
                        if self.cli:
                            self.text = self.text[:self.pos] + selected + self.text[self.pos:]
                            self.pos = len(self.text)
                        else:
                            self.text, self.pos = selected, len(selected)
                    return 0x19 # hack, to update screen
            elif ch == 0x07 and not self.cli:    # Ctr-G, not CLI
                selected = __select_item(self.history[::-1], 0, 'Historic', False)
                if selected not in (None, -1, ''):
                    self.text, self.pos = selected, len(selected)
                return 0x07 # hack, to update screen
            elif ch == 0x07 and self.cli:        # Ctr-G, in CLI
                BOOKMARKS_STR, HISTORY_STR = '----- Stored:  -----', '----- History: -----'
                entries = [BOOKMARKS_STR]
                entries.extend([c for c in app.prefs.powercli_favs if c])
                entries.append(HISTORY_STR)
                entries.extend(history['cli'][:])
                selected = __select_item(entries, 0, 'Commands', True)
                if selected not in (None, -1, '', BOOKMARKS_STR, HISTORY_STR):
                    self.text, self.pos = selected, len(selected)
                    return 0x07 # hack, to update screen
            # chars and edit keys
            elif ch == curses.KEY_IC:            # insert
                self.ins = not self.ins
            elif len(self.text) < 255 and 32 <= ch <= 255:
                buf = get_char(self.entry, ch)
                if self.ins:
                    self.text = self.text[:self.pos] + buf + self.text[self.pos:]
                    self.pos += 1
                else:
                    self.text = self.text[:self.pos] + buf + self.text[self.pos+1:]
                    self.pos += 1
            else:
                curses.beep()


######################################################################
class Entry(object):
    """An entry window to enter a dir. or file, a pattern, ..."""

    def __init__(self, title, help='', path='',
                 with_history='', with_complete=True, panelpath=''):
        h = 6
        w = max(len(help)+5, app.maxw/2)
        try:
            win = curses.newwin(h, w, int((app.maxh-h)/2), int((app.maxw-w)/2))
            self.entry = EntryLine(w, h,
                                   int((app.maxh-h)/2)+2, int((app.maxw-w+4)/2),
                                   path, with_history, with_complete,
                                   panelpath)
            self.btns = Yes_No_Buttons(w, h, 0)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.bkgd(curses.color_pair(1))
        win.erase()
        win.box(0, 0)
        win.addstr(1, 2 , '%s:' % utils.encode(help))
        win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
                   curses.color_pair(1) | curses.A_BOLD)
        win.refresh()
        self.with_history = with_history
        self.active_widget = self.entry


    def run(self):
        self.entry.entry.refresh() # needed to avoid a problem with blank paths
        self.entry.show()
        self.btns.show()
        cursor_show2()

        quit = False
        while not quit:
            self.btns.show()
            ans = self.active_widget.manage_keys()
            if ans == -1:              # Ctrl-C
                quit = True
                answer = None
            elif ans == ord('\t'):     # tab
                if self.active_widget == self.entry:
                    self.active_widget = self.btns
                    self.btns.active = 1
                    cursor_hide()
                    answer = self.entry.text
                elif self.active_widget == self.btns and self.btns.active == 1:
                    self.btns.active = 2
                    cursor_hide()
                    answer = None
                else:
                    self.active_widget = self.entry
                    self.btns.active = 0
                    cursor_show2()
            elif ans in (0x07, 0x14, 0x19, 0x1C): # Ctrl-G, Ctrl-T, Ctrl-Y, Ctrl-\
                # this is a hack, we need to return to refresh Entry
                return [self.entry.text]
            elif ans == 10:              # return values
                quit = True
                answer = self.entry.text

        cursor_hide()
        if answer:
            answer = os.path.expanduser(answer)
            if self.with_history in history.keys():
                add_to_history(history[self.with_history], self.entry.text)
        self.pwin.hide()
        return answer


######################################################################
class DoubleEntry(object):
    """An entry window to enter 2 dirs. or files, patterns, ..."""

    def __init__(self, title, help1='', path1='',
                 with_history1='', with_complete1=True, panelpath1='',
                 help2='', path2='',
                 with_history2='', with_complete2=True, panelpath2='',
                 active_entry=0):
        h = 9
        w = max(len(help1)+5, len(help2)+5, app.maxw/2)
        try:
            win = curses.newwin(h, w, int((app.maxh-h)/2)-1, int((app.maxw-w)/2))
            self.entry1 = EntryLine(w, h,
                                    int((app.maxh-h)/2) + 1,
                                    int((app.maxw-w+4) / 2),
                                    path1, with_history1, with_complete1,
                                    panelpath1)
            self.entry2 = EntryLine(w, h,
                                    int((app.maxh-h)/2) + 4,
                                    int((app.maxw-w+4) / 2),
                                    path2, with_history2, with_complete2,
                                    panelpath2)
            self.btns = Yes_No_Buttons(w, h, 2)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.bkgd(curses.color_pair(1))
        win.erase()
        win.box(0, 0)
        win.addstr(1, 2 , '%s:' % utils.encode(help1))
        win.addstr(4, 2 , '%s:' % utils.encode(help2))
        win.addstr(0, int((w-len(title)-2)/2), ' %s ' % utils.encode(title),
                   curses.color_pair(1) | curses.A_BOLD)
        win.refresh()
        self.with_history1, self.with_history2 = with_history1, with_history2
        self.active_entry = (active_entry==0) and self.entry1 or self.entry2
        self.active_entry_i = active_entry


    def run(self):
        # needed to avoid a problem with blank paths
        self.entry1.entry.refresh()
        self.entry2.entry.refresh()
        self.entry1.show()
        self.entry2.show()
        self.btns.show()
        cursor_show2()

        answer = True
        quit = False
        while not quit:
            self.btns.show()
            if self.active_entry_i in [0, 1]:
                ans = self.active_entry.manage_keys()
            else:
                ans = self.btns.manage_keys()
            if ans == -1:      # Ctrl-C
                quit = True
                answer = False
            elif ans == ord('\t'):     # tab
                self.active_entry_i += 1
                if self.active_entry_i > 3:
                    self.active_entry_i = 0
                if self.active_entry_i == 0:
                    self.active_entry = self.entry1
                    self.btns.active = 0
                    cursor_show2()
                elif self.active_entry_i == 1:
                    self.active_entry = self.entry2
                    self.btns.active = 0
                    cursor_show2()
                elif self.active_entry_i == 2:
                    self.btns.active = 1
                    cursor_hide()
                    answer = True
                else:
                    self.btns.active = 2
                    cursor_hide()
                    answer = False
            elif ans in (0x07, 0x14, 0x19, 0x1C): # Ctrl-G, Ctrl-T, Ctrl-Y, Ctrl-\
                # this is a hack, we need to return to refresh Entry
                return [self.entry1.text, self.entry2.text, self.active_entry_i]
            elif ans == 10:    # return values
                quit = True
                answer = True

        cursor_hide()
        if answer:
            if self.with_history1 in history.keys():
                add_to_history(history[self.with_history1], self.entry1.text)
            if self.with_history2 in history.keys():
                add_to_history(history[self.with_history2], self.entry2.text)
            ans1 = os.path.expanduser(self.entry1.text)
            ans2 = os.path.expanduser(self.entry2.text)
        else:
            ans1, ans2 = None, None
        self.pwin.hide()
        return ans1, ans2


######################################################################
class SelectItem(object):
    """A window to select an item"""

    def __init__(self, entries, y0, x0, entry_i='', title=''):
        h = (app.maxh-1) - (y0+1) + 1
        w = min(max(max(map(len, entries)), len(title)+4, int(app.maxw/5))+4, app.maxw-8)
        if x0 + w >= app.maxw:
            w = max(10, w-x0)
        try:
            win = curses.newwin(h, w, y0, x0)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.keypad(1)
        cursor_hide()
        win.bkgd(curses.color_pair(4))
        self.entries = entries
        try:
            self.entry_i = self.entries.index(entry_i)
        except:
            self.entry_i = 0
        self.title = title


    def show(self):
        win = self.pwin.window()
        win.erase()
        win.refresh()
        win.box(0, 0)
        y, x = win.getbegyx()
        h, w = win.getmaxyx()
        h0, w0 = h - 2, w - 3
        if self.title != '':
            win.addstr(0, int((w-len(self.title)-2)/2), ' %s ' % utils.encode(self.title),
                       curses.color_pair(3))
        nels = len(self.entries)
        entry_a = int(self.entry_i/h0) * h0
        for i in xrange(h0):
            try:
                line = self.entries[entry_a+i]
            except IndexError:
                line = ''
            if line:
                win.addstr(i+1, 2, utils.encode(crop_line(line, w0)),
                           curses.color_pair(4))
        win.refresh()
        # cursor
        cursor = curses.newpad(1, w-1)
        cursor.bkgd(curses.color_pair(1))
        cursor.erase()
        line = self.entries[self.entry_i]
        cursor.addstr(0, 1, utils.encode(crop_line(line, w0)),
                      curses.color_pair(1) | curses.A_BOLD)
        y += 1; x += 1
        cur_row = y + self.entry_i % h0
        cursor.refresh(0, 0, cur_row, x, cur_row, x + w0)
        # scrollbar
        if nels > h0:
            n = max(int(h0*h0/nels), 1)
            y0 = min(max(int(int(self.entry_i/h0)*h0*h0/nels),0), h0 - n)
        else:
            y0 = n = 0
        win.vline(y0+1, w-1, curses.ACS_CKBOARD, n)
        if entry_a != 0:
            win.vline(1, w-1, '^', 1)
            if n == 1 and (y0 + 1 == 1):
                win.vline(2, w-1, curses.ACS_CKBOARD, n)
        if nels - 1 > entry_a + h0 - 1:
            win.vline(h0, w-1, 'v', 1)
            if n == 1 and (y0 == h0 - 1):
                win.vline(h0-1, w-1, curses.ACS_CKBOARD, n)


    def manage_keys(self):
        h, w = self.pwin.window().getmaxyx()
        nels = len(self.entries)
        while True:
            self.show()
            ch = self.pwin.window().getch()
            if ch in (0x03, 0x1B, ord('q'), ord('Q')):       # Ctrl-C, ESC
                return -1
            elif ch in (curses.KEY_UP, ord('k'), ord('K')):
                if self.entry_i != 0:
                    self.entry_i -= 1
            elif ch in (curses.KEY_DOWN, ord('j'), ord('J')):
                if self.entry_i < nels - 1:
                    self.entry_i += 1
            elif ch in (curses.KEY_PPAGE, curses.KEY_BACKSPACE, 0x08, 0x02):
                if self.entry_i < h - 3:
                    self.entry_i = 0
                else:
                    self.entry_i -= h - 2
            elif ch in (curses.KEY_NPAGE, ord(' '), 0x06):
                if self.entry_i + (h-2) > nels - 1:
                    self.entry_i = nels - 1
                else:
                    self.entry_i += h - 2
            elif ch in (curses.KEY_HOME, 0x01):
                self.entry_i = 0
            elif ch in (curses.KEY_END, 0x05):
                self.entry_i = nels - 1
            elif ch == 0x0C:     # Ctrl-L
                self.entry_i = int(len(self.entries)/2)
            elif ch == 0x30:         # 0
                self.entry_i = ch - 0x30 + 9
            elif 0x31 <= ch <= 0x39: # 1..9
                self.entry_i = ch - 0x30 - 1
            elif ch == 0x13:     # Ctrl-S
                theentries = self.entries[self.entry_i:]
                ch2 = self.pwin.window().getkey()
                for e in theentries:
                    if e.find(ch2) == 0:
                        break
                else:
                    continue
                self.entry_i = self.entries.index(e)
            elif ch in (0x0A, 0x0D):   # enter
                return self.entries[self.entry_i]
            else:
                curses.beep()


    def run(self):
        selected = self.manage_keys()
        self.pwin.below().top()
        self.pwin.hide()
        return selected


######################################################################
class FindfilesWin(object):
    """A window to select a file"""

    def __init__(self, entries, entry_i=''):
        y0 = 1
        h = (app.maxh-1) - (y0+1) + 1
        # w = max(map(len, entries)) + 4
        w = 64
        x0 = int((app.maxw-w) / 2)
        try:
            win = curses.newwin(h, w, y0, x0)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.keypad(1)
        cursor_hide()
        win.bkgd(curses.color_pair(4))
        self.entries = entries
        try:
            self.entry_i = self.entries.index(entry_i)
        except:
            self.entry_i = 0
        self.btn_active = 0


    def show(self):
        win = self.pwin.window()
        win.erase()
        win.refresh()
        win.box(0, 0)
        y, x = win.getbegyx()
        h, w = win.getmaxyx()
        h0, w0 = h - 4, w - 3
        nels = len(self.entries)
        entry_a = int(self.entry_i/h0) * h0
        for i in xrange(h0):
            try:
                line = self.entries[entry_a+i]
            except IndexError:
                line = ''
            if len(line) >= w0:
                if w0 % 2 == 0:     # even
                    line = line[:int(w0/2)] + '~' + line[-int(w0/2)+3:]
                else:                    # odd
                    line = line[:int(w0/2)+1] + '~' + line[-int(w0/2)+3:]
            if line:
                win.addstr(i+1, 2, utils.encode(line), curses.color_pair(4))
        win.refresh()
        # cursor
        cursor = curses.newpad(1, w-2)
        cursor.attrset(curses.color_pair(1) | curses.A_BOLD)
        cursor.bkgdset(curses.color_pair(1))
        cursor.erase()
        line = self.entries[self.entry_i]
        if len(line) >= w0:
            if (w - 2) % 2 == 0:         # even
                line = line[:int((w-2)/2)] + '~' + line[-int((w-2)/2)+3:]
            else:                        # odd
                line = line[:int((w-2)/2)+1] + '~' + line[-int((w-2)/2)+3:]
        cursor.addstr(0, 1, utils.encode(line),
                      curses.color_pair(1) | curses.A_BOLD)
        y += 1; x += 1
        cursor.refresh(0, 0, y + self.entry_i % h0,
                       x, y + self.entry_i % h0, x + w0)
        # scrollbar
        if nels > h0:
            n = max(int(h0*h0/nels), 1)
            y0 = min(max(int(int(self.entry_i/h0)*h0*h0/nels),0), h0 - n)
        else:
            y0 = n = 0
        win.vline(y0+1, w-1, curses.ACS_CKBOARD, n)
        if entry_a != 0:
            win.vline(1, w-1, '^', 1)
            if n == 1 and (y0 + 1 == 1):
                win.vline(2, w-1, curses.ACS_CKBOARD, n)
        if nels - 1 > entry_a + h0 - 1:
            win.vline(h0, w-1, 'v', 1)
            if n == 1 and (y0 == h0 - 1):
                win.vline(h0-1, w-1, curses.ACS_CKBOARD, n)

        win.hline(h-3, 1, curses.ACS_HLINE, w-2)
        win.hline(h-3, 0, curses.ACS_LTEE, 1)
        win.hline(h-3, w-1, curses.ACS_RTEE, 1)
        win.addstr(h-2, 3,
                   '[ Go ]  [ Panelize ]  [ View ]  [ Edit ]  [ Do ]  [ Quit ]',
                   curses.color_pair(4))
        attr0 = attr1 = attr2 = attr3 = attr4 = attr5 = curses.color_pair(4)
        if self.btn_active == 0:
            attr0 = curses.color_pair(1) | curses.A_BOLD
        elif self.btn_active == 1:
            attr1 = curses.color_pair(1) | curses.A_BOLD
        elif self.btn_active == 2:
            attr2 = curses.color_pair(1) | curses.A_BOLD
        elif self.btn_active == 3:
            attr3 = curses.color_pair(1) | curses.A_BOLD
        elif self.btn_active == 4:
            attr4 = curses.color_pair(1) | curses.A_BOLD
        else:
            attr5 = curses.color_pair(1) | curses.A_BOLD
        win.addstr(h-2, 3, '[ Go ]', attr0)
        win.addstr(h-2, 11, '[ PAnelize ]', attr1)
        win.addstr(h-2, 25, '[ View ]', attr2)
        win.addstr(h-2, 35, '[ Edit ]', attr3)
        win.addstr(h-2, 45, '[ Do ]', attr4)
        win.addstr(h-2, 53, '[ Quit ]', attr5)
        win.refresh()


    def manage_keys(self):
        h, w = self.pwin.window().getmaxyx()
        nels = len(self.entries)
        while True:
            self.show()
            ch = self.pwin.window().getch()
            if ch in (0x03, 0x1B, ord('q'), ord('Q')):       # Ctrl-C, ESC
                return -1, None
            elif ch in (curses.KEY_UP, ord('k'), ord('K')):
                if self.entry_i != 0:
                    self.entry_i -= 1
            elif ch in (curses.KEY_DOWN, ord('j'), ord('j')):
                if self.entry_i != nels - 1:
                    self.entry_i += 1
            elif ch in (curses.KEY_PPAGE, curses.KEY_BACKSPACE, 0x08, 0x02):
                if self.entry_i < (h - 5):
                    self.entry_i = 0
                else:
                    self.entry_i -= (h - 4)
            elif ch in (curses.KEY_NPAGE, ord(' '), 0x06):
                if self.entry_i + (h-4) > nels - 1:
                    self.entry_i = nels - 1
                else:
                    self.entry_i += (h - 4)
            elif ch in (curses.KEY_HOME, 0x01):
                self.entry_i = 0
            elif ch in (curses.KEY_END, 0x05):
                self.entry_i = nels - 1
            elif ch == 0x13:     # Ctrl-S
                theentries = self.entries[self.entry_i:]
                ch2 = self.pwin.window().getkey()
                for e in theentries:
                    if e.find(ch2) == 0:
                        break
                else:
                    continue
                self.entry_i = self.entries.index(e)
            elif ch in (curses.KEY_LEFT, ):
                if self.btn_active == 0:
                    self.btn_active = 5
                else:
                    self.btn_active -= 1
            elif ch in (0x09, curses.KEY_RIGHT): # tab
                if self.btn_active == 5:
                    self.btn_active = 0
                else:
                    self.btn_active += 1
            elif ch in (0x0A, 0x0D):   # enter
                if self.btn_active == 0:
                    return 0, self.entries[self.entry_i]
                elif self.btn_active == 1:
                    return 1, None
                elif self.btn_active == 2:
                    return 2, self.entries[self.entry_i]
                elif self.btn_active == 3:
                    return 3, self.entries[self.entry_i]
                elif self.btn_active == 4:
                    return 4, self.entries[self.entry_i]
                elif self.btn_active == 5:
                    return -1, None
            elif ch in (ord('a'), ord('A')):
                return 1, None
            elif ch in (curses.KEY_F3, ord('v'), ord('V')):
                return 2, self.entries[self.entry_i]
            elif ch in (curses.KEY_F4, ord('e'), ord('E')):
                return 3, self.entries[self.entry_i]
            elif ch in (ord('@'), ord('d'), ord('D')):
                return 4, self.entries[self.entry_i]
            else:
                curses.beep()


    def run(self):
        selected = self.manage_keys()
        self.pwin.hide()
        return selected


######################################################################
class MenuWin(object):
    """A window to select a menu option"""

    def __init__(self, title, entries):
        h = len(entries) + 4
        w = min(max(len(title)+2, max(map(len, entries)))+4, app.maxw-8)
        y0 = int((app.maxh-h) / 2)
        x0 = int((app.maxw-w) / 2)
        try:
            win = curses.newwin(h, w, y0, x0)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.keypad(1)
        cursor_hide()
        win.bkgd(curses.color_pair(3))
        self.title = title
        self.entries = entries
        self.entry_i = 0
        self.keys = [e[0] for e in entries]


    def show(self):
        win = self.pwin.window()
        win.erase()
        win.box(0, 0)
        y, x = win.getbegyx()
        h, w = win.getmaxyx()
        attr = curses.color_pair(7)
        win.addstr(0, int((w-len(self.title)-2)/2), ' %s ' % \
                       utils.encode(self.title), attr)
        for i in xrange(h-2):
            try:
                line = self.entries[i]
            except IndexError:
                line = ''
            if line:
                win.addstr(i+2, 2, utils.encode(crop_line(line, w-3)),
                           curses.color_pair(3))
        win.refresh()
        # cursor
        cursor = curses.newpad(1, w-2)
        cursor.bkgd(curses.color_pair(1))
        cursor.erase()
        line = self.entries[self.entry_i]
        cursor.addstr(0, 1, utils.encode(crop_line(line, w-3)),
                      curses.color_pair(1) | curses.A_BOLD)
        y += 1; x += 1
        cursor.refresh(0, 0, y + self.entry_i % (h-4) + 1,
                       x, y + self.entry_i % (h-4) + 1, x + w-3)


    def manage_keys(self):
        while True:
            self.show()
            ch = self.pwin.window().getch()
            if ch in (0x03, 0x1B, ord('q'), ord('Q')):       # Ctrl-C, ESC
                return -1
            elif ch in (curses.KEY_UP, ord('k'), ord('K')):
                if self.entry_i != 0:
                    self.entry_i -= 1
            elif ch in (curses.KEY_DOWN, ord('j'), ord('J')):
                if self.entry_i != len(self.entries) - 1:
                    self.entry_i += 1
            elif ch in (curses.KEY_HOME, 0x01, curses.KEY_PPAGE, 0x08, 0x02,
                        curses.KEY_BACKSPACE):
                self.entry_i = 0
            elif ch in (curses.KEY_END, 0x05, curses.KEY_NPAGE, ord(' '), 0x06):
                self.entry_i = len(self.entries) - 1
            elif ch == 0x13:     # Ctrl-S
                theentries = self.entries[self.entry_i:]
                ch2 = self.pwin.window().getkey()
                for e in theentries:
                    if e.find(ch2) == 0:
                        break
                else:
                    continue
                self.entry_i = self.entries.index(e)
            elif ch in (0x0A, 0x0D):   # enter
                return self.entries[self.entry_i]
            elif 0 <= ch <= 255 and chr(ch).lower() in self.keys:
                return self.entries[self.keys.index(chr(ch).lower())]
            else:
                curses.beep()


    def run(self):
        selected = self.manage_keys()
        self.pwin.hide()
        return selected


######################################################################
class ChangePerms(object):
    """A window to change permissions, owner or group"""

    def __init__(self, filename, fileinfo, i=0, n=0):
        h, w = 6+4, 64+4
        x0, y0 = int((app.maxw-w)/2), int((app.maxh-h)/2)
        try:
            win = curses.newwin(h, w, y0, x0)
            self.pwin = curses.panel.new_panel(win)
            self.pwin.top()
        except curses.error:
            print 'Can\'t create window'
            sys.exit(-1)
        win.keypad(1)
        cursor_hide()
        win.bkgd(curses.color_pair(1))

        self.file = filename
        self.perms_old = files.perms2str(fileinfo[files.FT_PERMS])
        self.perms = [l for l in self.perms_old]
        self.owner = fileinfo[files.FT_OWNER]
        self.group = fileinfo[files.FT_GROUP]
        self.owner_old = self.owner[:]
        self.group_old = self.group[:]
        self.recursive = True
        self.i, self.n, self.entry_i, self.w = i, n, 0, w


    def show_btns(self):
        win = self.pwin.window()
        h, w = win.getmaxyx()
        attr1 = curses.color_pair(1) | curses.A_BOLD
        attr2 = curses.color_pair(9) | curses.A_BOLD
        win.addstr(h-2, w-21, '[<Ok>]', (self.entry_i==11) and attr2 or attr1)
        win.addstr(h-2, w-13, '[ Cancel ]', (self.entry_i==12) and attr2 or attr1)
        if self.n > 0:
            win.addstr(h-2, 3, '[ All ]', (self.entry_i==13) and attr2 or attr1)
            win.addstr(h-2, 12, '[ Ignore ]', (self.entry_i==14) and attr2 or attr1)


    def show(self):
        win = self.pwin.window()
        win.getmaxyx()
        win.erase()
        win.box(0, 0)
        attr = curses.color_pair(1) | curses.A_BOLD
        title = 'Change permissions, owner or group'
        win.addstr(0, int((self.w-len(title)-2)/2), ' %s ' % title, attr)
        win.addstr(2, 2, 'File: ')
        win.addstr(2, 8, utils.encode(self.file), attr)
        if self.n > 0:
            win.addstr(2, self.w-12-2, '%4d of %-4d' % (self.i, self.n))
        win.addstr(4, 7, 'owner  group  other      owner         group      recursive')
        win.addstr(5, 2, 'new: [---]  [---]  [---]   [----------]  [----------]     [ ]')
        win.addstr(6, 2, 'old: [---]  [---]  [---]   [----------]  [----------]     [ ]')
        win.addstr(6, 8, self.perms_old[0:3])
        win.addstr(6, 15, self.perms_old[3:6])
        win.addstr(6, 22, self.perms_old[6:9])
        l = len(self.owner_old)
        win.addstr(6, 30, (l > 10) and self.owner_old[:10] or self.owner_old+'-'*(10-l))
        l = len(self.group_old)
        win.addstr(6, 44, (l > 10) and self.group_old[:10] or self.group_old+'-'*(10-l))

        perms = ''.join(self.perms)
        win.addstr(5, 8, perms[0:3])
        win.addstr(5, 15, perms[3:6])
        win.addstr(5, 22, perms[6:9])
        l = len(self.owner)
        owner = (l > 10) and self.owner[:10] or self.owner+'-'*(10-l)
        win.addstr(5, 30, owner)
        l = len(self.group)
        group = (l > 10) and self.group[:10] or self.group+'-'*(10-l)
        win.addstr(5, 44, group)
        recursive = self.recursive and 'X' or ' '
        win.addstr(5, 61, recursive)
        if self.entry_i == 0:
            win.addstr(5, 8, perms[0:3], curses.color_pair(5) | curses.A_BOLD)
        elif self.entry_i == 1:
            win.addstr(5, 15, perms[3:6], curses.color_pair(5) | curses.A_BOLD)
        elif self.entry_i == 2:
            win.addstr(5, 22, perms[6:9], curses.color_pair(5) | curses.A_BOLD)
        elif self.entry_i == 3:
            win.addstr(5, 30, owner, curses.color_pair(5) | curses.A_BOLD)
        elif self.entry_i == 4:
            win.addstr(5, 44, group, curses.color_pair(5) | curses.A_BOLD)
        elif self.entry_i == 5:
            win.addstr(5, 61, recursive, curses.color_pair(5) | curses.A_BOLD)
        self.show_btns()
        win.refresh()


    def manage_keys(self):
        y, x = self.pwin.window().getbegyx()
        order = (self.n > 0) and [0, 1, 2, 3, 4, 5, 13, 14, 11, 12] or [0, 1, 2, 3, 4, 5, 11, 12]
        while True:
            self.show()
            ch = self.pwin.window().getch()
            if ch in (0x03, 0x1B, ord('c'), ord('C'), ord('q'), ord('Q')):
                return -1
            elif ch in (ord('\t'), 0x09, curses.KEY_DOWN, curses.KEY_RIGHT):
                try:
                    self.entry_i = order[order.index(self.entry_i)+1]
                except IndexError:
                    self.entry_i = order[0]
            elif ch in (curses.KEY_UP, curses.KEY_LEFT):
                try:
                    self.entry_i = order[order.index(self.entry_i)-1]
                except IndexError:
                    self.entry_i = order[0]
            elif ch in (ord('r'), ord('R')):
                if not 0 <= self.entry_i <= 2:
                    continue
                d = self.entry_i * 3
                self.perms[d] = (self.perms[d]=='-') and 'r' or '-'
            elif ch in (ord('w'), ord('W')):
                if not 0 <= self.entry_i <= 2:
                    continue
                d = 1 + self.entry_i * 3
                self.perms[d] = (self.perms[d]=='-') and 'w' or '-'
            elif ch in (ord('x'), ord('X')):
                if not 0 <= self.entry_i <= 2:
                    continue
                d = 2 + self.entry_i * 3
                self.perms[d] = (self.perms[d]=='-') and 'x' or '-'
            elif ch in (ord('t'), ord('T')):
                if not self.entry_i == 2:
                    continue
                self.perms[d] = (self.perms[8]=='t') and self.perms_old[8] or 't'
            elif ch in (ord('s'), ord('S')):
                if not 0 <= self.entry_i <= 1:
                    continue
                d = 2 + self.entry_i * 3
                self.perms[d] = (self.perms[d]=='s') and self.perms_old[d] or 's'
            elif ch in (ord(' '), 0x0A, 0x0D):
                if self.entry_i == 5:
                    self.recursive = not self.recursive
                elif self.entry_i == 3:
                    owners = files.get_owners()
                    owners.sort()
                    try:
                        owners.index(self.owner)
                    except:
                        owners.append(self.owner)
                    ret = SelectItem(owners, y+6, x+30, self.owner).run()
                    if ret != -1:
                        self.owner = ret
                    app.display()
                elif self.entry_i == 4:
                    groups = files.get_groups()
                    groups.sort()
                    try:
                        groups.index(self.group)
                    except:
                        groups.append(self.group)
                    ret = SelectItem(groups, y+6, x+30, self.group).run()
                    if ret != -1:
                        self.group = ret
                    app.display()
                elif self.entry_i == 12:
                    return -1
                elif self.n > 0 and self.entry_i == 13:
                    return self.perms, self.owner, self.group, self.recursive, True
                elif self.n > 0 and self.entry_i == 14:
                    return 0
                else:
                    return self.perms, self.owner, self.group, self.recursive, False
            elif self.n > 0 and ch in (ord('i'), ord('I')):
                return 0
            elif self.n > 0 and ch in (ord('a'), ord('A')):
                return self.perms, self.owner, self.group, self.recursive, True
            else:
                curses.beep()


    def run(self):
        selected = self.manage_keys()
        self.pwin.hide()
        return selected


######################################################################
##### some utils
def crop_line(line, w):
    if len(line) > w-1:
        if w % 2 == 0: # even
            return line[:int(w/2)] + '~' + line[-int(w/2)+2:]
        else: # odd
            return line[:int(w/2)+1] + '~' + line[-int(w/2)+2:]
    else:
        return line


def cursor_show2():
    try: # some terminals don't allow '2'
        curses.curs_set(2)
    except:
        cursor_show()


def cursor_show():
    try:
        curses.curs_set(1)
    except:
        pass


def cursor_hide():
    try:
        curses.curs_set(0)
    except:
        pass


######################################################################
