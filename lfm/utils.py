# -*- coding: utf-8 -*-

"""utils.py

This module contains useful functions.
"""


import os
import os.path
import sys
import time
import signal
import select
import cPickle
import curses

import compress
import messages
from __init__ import sysprogs, g_encoding


######################################################################
##### module variables
app = None

# first common codecs, to avoid slow down decoding
codecs_list = [g_encoding,  'utf-8', 'latin-1', 'ascii']
# if program is too slow due to too many encodings to try,
# comment out next lines or put the encodings you use first
import encodings.aliases
# Set is deprecated on python v2.6+, but set doesn't exist < v2.6
cds = {}
for c in encodings.aliases.aliases.values():
    cds[c] = 1
codecs_list += sorted(cds.keys())


######################################################################
##### InterProcess Communication
class IPC(object):
    def __init__(self):
        pipe_r, pipe_w = os.pipe()
        self.rfd = os.fdopen(pipe_r, 'rb', 0)
        self.wfd = os.fdopen(pipe_w, 'wb', 0)

    def send(self, buf):
        cPickle.dump(buf, self.wfd)
        # time.sleep(0.01)
        cPickle.dump(None, self.wfd)

    def receive(self):
        ready = select.select([self.rfd], [], [], 0.001) # 0.01
        if self.rfd in ready[0]:
            try:
                buf = cPickle.load(self.rfd)
            except:
                return -1, 'Error unmarshaling'
            if buf is None:
                return 0, None
            try:
                arg1, arg2 = buf
            except:
                return -1, 'Malformed response'
            return 1, buf
        return 0, None

    def close(self):
        self.rfd.close()
        self.wfd.close()


######################################################################
##### Process Loop Base Class
class ProcessLoopBase(object):
    """Run a function in background, so it can be stopped, continued, etc.
    There is also a graphical animation to show the program still runs and
    has not crashed."""

    anim_char = ('|', '/', '-', '\\')

    def __init__(self, action='', func=None, *args):
        self.action = action       # action label
        self.func = func           # function to run in child
        self.args = args           # additional args for func
        self.ret = []              # information to return
        self.filename = ''         # current filename
        self.file_i = 0            # index to current item
        self.cursor_i = 0          # index to cursor animation step
        self.init_gui()

    def init_gui(self):
        self.cur_win = curses.newpad(1, 2)
        self.cur_win.bkgd(curses.color_pair(1))
        if self.processloop_type == 1:
            dlg = messages.ProgressBarWindow
        elif self.processloop_type == 2:
            dlg = messages.ProgressBarWindow2
        self.dlg = dlg(self.action, 'Press Ctrl-C to stop',
                       curses.color_pair(1), curses.color_pair(1),
                       curses.color_pair(20), curses.color_pair(4),
                       waitkey=False)
        self.dlg.show()

    def end_gui(self):
        self.dlg.finish()
        self.show_parent()

    def show_parent(self):
        self.dlg.ishidden = True
        app.display()

    def show_win(self):
        raise NotImplementedError # in ProcessLoopBase_X class

    def animate_cursor(self):
        self.cur_win.erase()
        self.cur_win.addch(ProcessLoopBase.anim_char[self.cursor_i%4],
                           curses.color_pair(1) | curses.A_BOLD)
        self.cur_win.refresh(0, 0, 0, app.maxw-2, 1, app.maxw-1)
        self.cursor_i += 1
        if self.cursor_i > 3:
            self.cursor_i = 0

    def check_keys(self):
        ch = self.dlg.getch()
        if ch == 0x03:
            os.kill(self.pid_child, signal.SIGSTOP)
            self.show_parent()
            ans = messages.confirm('Stop process',
                                   'Stop \"%s\"' % self.action.lower(), 1)
            if ans:
                os.kill(self.pid_child, signal.SIGKILL)
                os.wait()
                return -100
            else:
                os.kill(self.pid_child, signal.SIGCONT)
                return 1
        return 0

    def wait_for_answer(self):
        while True:
            # feedback from user
            status = self.check_keys()
            if status == -100: # stopped and ended by user
                return ('stopped_by_user', None)
            elif status == 1: # stopped and continued by user
                self.show_win()
            self.animate_cursor()
            # check response
            code, buf = self.c2p.receive()
            if code == 1:
                return buf
            elif code == -1:
                return ('internal_error', buf)

    def ask_confirmation(self):
        raise NotImplementedError # in final class

    def prepare_args(self):
        raise NotImplementedError # in final class

    def process_response(self, result):
        raise NotImplementedError # in final class

    def exec_file(self, args):
        # update progress dialog
        self.show_win()
        # send data to child
        self.p2c.send(('exec', args))
        # wait for answer and process it
        ans, result = self.wait_for_answer()
        if ans == 'stopped_by_user':
            return -1
        elif ans == 'internal_error':
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           'Parent: Internal Error: ' + result)
            return 0
        elif ans == 'error':
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           'Parent: Error: ' + result)
            return 0
        elif ans == 'result':
            return self.process_response(result)
        else:
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           'Parent: Bad response from child')
            return 0

    def return_data(self):
        return self.ret

    def run_pre(self):
        self.p2c = IPC()
        self.c2p = IPC()
        self.pid_child = os.fork()
        if self.pid_child < 0: # error
            messages.error('Cannot %s\n' % self.action.lower() +
                           'Can\'t run function')
            return -1
        elif self.pid_child == 0: # child
            self.child_process()
            os._exit(0)

    def run(self):
        raise NotImplementedError # in ProcessLoopBase_X class

    def run_post(self):
        self.p2c.send(('quit', None))
        self.p2c.close()
        self.c2p.close()
        try:
            os.wait()
        except OSError:
            pass
        self.end_gui()

    def child_process(self):
        while True:
            # wait for command to execute
            while True:
                code, buf = self.p2c.receive()
                if code == 1:
                    break
                elif code == -1:
                    self.c2p.send(('error', 'Child: ' + buf))
                    continue
                else:
                    continue
            cmd, args = buf
            # check command
            if cmd == 'quit':
                break
            elif cmd == 'exec':
                res = self.func(*args)
                self.c2p.send(('result', res))
                continue
            else:
                result = ('error', 'Child: Bad command from parent')
                self.c2p.send(('result', result))
                continue
        # end
        # time.sleep(.25) # time to let parent get return value
        os._exit(0)


######################################################################
##### Process Loop Base Class, 1 progressbar
class ProcessLoopBase_1(ProcessLoopBase):
    def __init__(self, action='', func=None, lst=[], *args):
        self.processloop_type = 1
        super(ProcessLoopBase_1, self).__init__(action, func, *args)
        self.lst = lst
        self.length = len(lst)

    def show_win(self):
        filename = self.filename
        percent = 100 * self.file_i / self.length
        idx_str = '%d/%d' % (self.file_i, self.length)
        if self.dlg.ishidden:
            self.dlg.show(filename, percent, idx_str)
        else:
            self.dlg.update(filename, percent, idx_str)

    def run(self):
        if ProcessLoopBase.run_pre(self) == -1:
            return
        for self.filename in self.lst:
            ret = self.ask_confirmation()
            if ret == -1:
                break
            elif ret == 0:
                continue
            self.file_i += 1
            args = self.prepare_args()
            ret = self.exec_file(args)
            if ret == -1:
                self.ret = -1   # stopped by user
                break
        ProcessLoopBase.run_post(self)
        return self.return_data()


##### Process Loop DirSize
class ProcessLoopDirSize(ProcessLoopBase_1):
    def ask_confirmation(self):
        return 1

    def prepare_args(self):
        return (self.filename, ) + self.args

    def process_response(self, result):
        self.ret.append(result)
        return 0


##### Process Loop Un/Compress
class ProcessLoopUnCompress(ProcessLoopBase_1):
    def ask_confirmation(self):
        return 1

    def prepare_args(self):
        return (self.filename, ) + self.args

    def process_response(self, result):
        if isinstance(result, tuple): # error
            st, msg = result
            if st == -1:
                self.show_parent()
                messages.error('Cannot %s\n' % self.action.lower() + msg)
        return 0


##### Process Loop Rename
class ProcessLoopRename(ProcessLoopBase_1):
    def ask_confirmation(self):
        from actions import doEntry
        buf = 'Rename \'%s\' to' % self.filename
        tabpath = app.act_pane.act_tab.path
        self.show_parent()
        newname = doEntry(tabpath, 'Rename', buf, self.filename, with_history='file')
        if newname:
            self.newname = newname
            return 1
        else:
            return 0

    def prepare_args(self):
        return (self.filename, ) + self.args + (self.newname, )

    def process_response(self, result):
        if isinstance(result, unicode) or isinstance(result, str): # overwrite?
            self.show_parent()
            ans = messages.confirm(self.action,
                                   'Overwrite \'%s\'' % result, 1)
            if ans == -1:
                return -1
            elif ans == 0:
                return 0
            elif ans == 1:
                args = (self.filename, ) + self.args + (self.newname, False)
                self.dlg.show()
                return self.exec_file(args)
        elif isinstance(result, tuple): # error from child
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           self.filename + ': %s (%s)' % result)
            return 0
        else:
            return 0


##### Process Loop Rename
class ProcessLoopBackup(ProcessLoopBase_1):
    def ask_confirmation(self):
        return 1

    def prepare_args(self):
        return (self.filename, ) + self.args

    def process_response(self, result):
        if isinstance(result, unicode) or isinstance(result, str): # overwrite?
            self.show_parent()
            ans = messages.confirm(self.action,
                                   'Overwrite \'%s\'' % result, 1)
            if ans == -1:
                return -1
            elif ans == 0:
                return 0
            elif ans == 1:
                args = (self.filename, ) + self.args + (False, )
                self.dlg.show()
                return self.exec_file(args)
        elif isinstance(result, tuple): # error from child
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           self.filename + ': %s (%s)' % result)
            return 0
        else:
            return 0


######################################################################
##### Process Loop Base Class, 2 progressbar
class ProcessLoopBase_2(ProcessLoopBase):
    def __init__(self, action='', func=None, pc=None, *args):
        self.processloop_type = 2
        super(ProcessLoopBase_2, self).__init__(action, func, *args)
        self.pc = pc            # PathContents
        self.filesize_aggr = 0  # partial sum of processed files

    def show_win(self):
        filename = self.filename.replace(self.pc.basepath+os.sep, '')
        perc_size = 100 * self.filesize_aggr / self.pc.tsize
        perc_count = 100 * self.file_i / self.pc.tlength
        idx_str = '%d/%d' % (self.file_i, self.pc.tlength)
        if self.dlg.ishidden:
            self.dlg.show(filename, perc_size, perc_count, idx_str)
        else:
            self.dlg.update(filename, perc_size, perc_count, idx_str)

    def run(self):
        for filename, err in self.pc.errors:
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           filename + ': %s (%s)' % err)
        if ProcessLoopBase.run_pre(self) == -1:
            return
        for self.filename, filesize in self.pc.iter_walk(reverse=self.rev):
            ret = self.ask_confirmation()
            if ret == -1:
                break
            elif ret == 0:
                continue
            self.file_i += 1
            self.filesize_aggr += filesize
            args = self.prepare_args()
            ret = self.exec_file(args)
            if ret == -1:
                self.ret = -1   # stopped by user
                break
        ProcessLoopBase.run_post(self)
        return self.return_data()


##### Process Loop Copy
class ProcessLoopCopy(ProcessLoopBase_2):
    def __init__(self, action='', func=None, pc=None, *args):
        super(ProcessLoopCopy, self).__init__(action, func, pc, *args)
        self.rev = False
        self.overwrite_all = not app.prefs.confirmations['overwrite']
        self.overwrite_none = False

    def ask_confirmation(self):
        return 1

    def prepare_args(self):
        if self.pc.basepath == os.sep:
            filename = self.filename.replace(self.pc.basepath, '')
        else:
            filename = self.filename.replace(self.pc.basepath+os.sep, '')
        if self.overwrite_all:
            return (filename, self.pc.basepath) + self.args + (False, )
        else:
            return (filename, self.pc.basepath) + self.args

    def process_response(self, result):
        if isinstance(result, unicode) or isinstance(result, str): # overwrite?
            if self.overwrite_none:
                self.ret.append(self.filename)
                return 0
            self.show_parent()
            ans = messages.confirm_all_none(self.action,
                                            'Overwrite \'%s\'' % result, 1)
            if ans == -1:
                self.ret.append(self.filename)
                return -1
            elif ans == -2:
                self.ret.append(self.filename)
                self.overwrite_none = True
                return 0
            elif ans == 0:
                self.ret.append(self.filename)
                return 0
            elif ans == 1:
                pass
            elif ans == 2:
                self.overwrite_all = True
            if self.pc.basepath == os.sep:
                filename = self.filename.replace(self.pc.basepath, '')
            else:
                filename = self.filename.replace(self.pc.basepath+os.sep, '')
            args = (filename, self.pc.basepath) + self.args + (False, )
            return self.exec_file(args)
        elif isinstance(result, tuple): # error from child
            self.ret.append(self.filename)
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           self.filename + ': %s (%s)' % result)
            return 0
        else:
            return 0


##### Process Loop Delete
class ProcessLoopDelete(ProcessLoopBase_2):
    def __init__(self, action='', func=None, pc=None, *args):
        super(ProcessLoopDelete, self).__init__(action, func, pc, *args)
        self.rev = True
        self.delete_all = not app.prefs.confirmations['delete']

    def ask_confirmation(self):
        if self.delete_all:
            return 2
        if app.prefs.confirmations['delete']:
            self.show_parent()
            ans = messages.confirm_all('Delete', 'Delete \'%s\'' % self.filename, 1)
            if ans == 2:
                self.delete_all = True
            return ans

    def prepare_args(self):
        return (self.filename, ) + self.args

    def process_response(self, result):
        if isinstance(result, tuple): # error from child
            self.dlg.ishidden = True
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           self.filename + ': %s (%s)' % result)
        return 0


######################################################################
##### Process Func
class ProcessFunc(object):
    """Run a function in background, so it can be stopped, continued, etc.
    There is also a graphical animation to show the program still runs and
    has not crashed.
    Parameters:
        title: title of info window
        subtitle: subtitle of info window
        func: function to run
        *args: arguments to pass to the function
    Returns:
         (status, message)"""

    anim_char = ('|', '/', '-', '\\')

    def __init__(self, title='', subtitle='', func=None, *args):
        self.func = func
        self.args = args
        self.title = title[:app.maxw-14]
        self.subtitle = subtitle[:app.maxw-14]
        self.init_gui()
        self.cursor_i = 0
        self.status = 0
        self.output = []
        self.ret = None

    def init_gui(self):
        self.cur_win = curses.newpad(1, 2)
        self.cur_win.bkgd(curses.color_pair(1))
        app.statusbar.win.nodelay(1)
        self.show_parent()
        self.show_win()

    def end_gui(self):
        app.statusbar.win.nodelay(0)
        self.show_parent()

    def show_parent(self):
        app.display()

    def show_win(self):
        messages.win_nokey(self.title, self.subtitle, 'Press Ctrl-C to stop')

    def animate_cursor(self):
        self.cur_win.erase()
        self.cur_win.addch(ProcessFunc.anim_char[self.cursor_i%4],
                           curses.color_pair(1) | curses.A_BOLD)
        self.cur_win.refresh(0, 0, 0, app.maxw-2, 1, app.maxw-1)
        self.cursor_i += 1
        if self.cursor_i > 3:
            self.cursor_i = 0

    def check_finish(self):
        (pid, status) = os.waitpid(self.pid_child, os.WNOHANG)
        if pid > 0:
            self.status = status >> 8
            return True
        else:
            return False

    def process_result(self):
        code, buf = self.c2p.receive()
        if code == 1:
            self.ret = buf
        elif code == -1:
            self.show_parent()
            messages.error('Cannot %s\n' % self.action.lower() +
                           'Parent: ' + buf)
            self.show_parent()
            self.show_win()
        else:
            pass

    def check_keys(self):
        ch = app.statusbar.win.getch()
        if ch == 0x03:
            os.kill(self.pid_child, signal.SIGSTOP)
            self.show_parent()
            ans = messages.confirm('Stop process',
                                   '%s %s' % (self.title, self.subtitle),
                                   1)
            if ans:
                os.kill(self.pid_child, signal.SIGKILL)
                os.wait()
                return -100
            else:
                self.show_win()
                os.kill(self.pid_child, signal.SIGCONT)
        return 0

    def run(self):
        self.c2p = IPC()
        self.pid_child = os.fork()
        if self.pid_child < 0: # error
            messages.error('Cannot run function')
            return
        elif self.pid_child == 0: # child
            self.child_process(self.func, *self.args)
            os._exit(0)
        # parent
        status = 0
        while True:
            if self.check_finish():
                break
            self.process_result()
            status = self.check_keys()
            if status == -100: # stopped by user
                self.status = status
                break
            self.animate_cursor()
        # finish and return
        self.c2p.close()
        try:
            os.wait()
        except OSError:
            pass
        self.end_gui()
        if self.status == -100: # stopped by user
            return -100, 'Stopped by user'
        try:
            st, buf = self.ret
        except:
            st, buf = 0, None
        return st, buf

    def child_process(self, func, *args):
        res = func(*args)
        self.c2p.send(res)
        os._exit(0)


######################################################################
##### run_shell
# run command via shell and optionally return output, popen version
def run_shell_popen(cmd, path, return_output=False):
    if not cmd:
        return 0, ''
    cmd = 'cd "%s" && %s' % (path, cmd)
    p = popen2.Popen3(cmd, capturestderr=True)
    p.tochild.close()
    outfd, errfd = p.fromchild, p.childerr
    output, error = [], []
    while True:
        # check if finished
        (pid, status) = os.waitpid(p.pid, os.WNOHANG)
        if pid > 0:
            status = status >> 8
            o = p.fromchild.readline()
            while o: # get output before quit
                o = o.strip()
                if o:
                    output.append(o)
                o = p.fromchild.readline()
            e = p.childerr.readline()
            while e: # get error before quit
                e = e.strip()
                if e:
                    error.append(e)
                e = p.childerr.readline()
            break
        # check for output
        ready = select.select([outfd, errfd], [], [], .01)
        if outfd in ready[0]:
            o = p.fromchild.readline()
            if o:
                output.append(o)
        if errfd in ready[0]:
            e = p.childerr.readline()
            while e: # get the whole error message
                e = e.strip()
                if e:
                    error.append(e)
                e = p.childerr.readline()
            status = p.wait() >> 8
            break
        time.sleep(0.1) # extra time to update output in case execution is too fast
    # return
    p.fromchild.close()
    p.childerr.close()
    if status != 0:
        error.insert(0, 'Exit code: %d' % status)
        return -1, '\n'.join(error)
    if error != []:
        return -1, '\n'.join(error)
    if return_output:
        return 0, '\n'.join(output)
    else:
        return 0, ''

# run in background, system version
def run_in_background_system(cmd, path):
    pid = os.fork()
    if pid == 0:
        try:
            maxfd = os.sysconf("SC_OPEN_MAX")
        except (AttributeError, ValueError):
            maxfd = 256       # default maximum
        # os.closerange(0, maxfd) # python v2.6+
        for fd in xrange(0, maxfd):
            try:
                os.close(fd)
            except OSError:   # ERROR (ignore)
                pass
        # Redirect the standard file descriptors to /dev/null.
        os.open("/dev/null", os.O_RDONLY)     # standard input (0)
        os.open("/dev/null", os.O_RDWR)       # standard output (1)
        os.open("/dev/null", os.O_RDWR)       # standard error (2)
        os.system('cd "%s" && %s' % (path, cmd))
        os._exit(0)
    else:
        pass # don't wait

# get output from a command run in shell, popen version
def get_shell_output_popen(cmd):
    i, a = os.popen4(cmd)
    buf = a.read()
    i.close(), a.close()
    return buf.strip()

# get output from a command run in shell, no stderr, popen version
def get_shell_output2_popen(cmd):
    i, o, e = os.popen3(cmd)
    buf = o.read()
    i.close(), o.close(), e.close()
    if buf:
        return buf.strip()
    else:
        return ''

# get error from a command run in shell, popen version
def get_shell_output3_popen(cmd):
    i, o, e = os.popen3(cmd)
    buf = e.read()
    i.close(), o.close(), e.close()
    if buf:
        return buf.strip()
    else:
        return ''

# run command via shell and optionally return output, subprocess version
def run_shell_subprocess(cmd, path, return_output=False):
    if not cmd:
        return 0, ''
    p = Popen(cmd, cwd=path, shell=True,
              stdin=None, stdout=PIPE, stderr=PIPE, close_fds=True)
    while p.wait() is None:
        time.sleep(0.2)
    output, error = p.stdout.read(), p.stderr.read()
    p.stdout.close(), p.stderr.close()
    if p.returncode < 0:
        error = 'Exit code: %d\n' % p.returncode + error
        return -1, error
    if error != '':
        return -1, error
    if return_output:
        return 0, output
    else:
        return 0, ''

# run in background, subprocess version
def run_in_background_subprocess(cmd, path):
    pid = os.fork()
    if pid == 0:
        p = Popen(cmd, cwd=path, shell=True, close_fds=True,
                  stdin=None, stdout=open('/dev/null', 'w'), stderr=STDOUT)
        os._exit(0)
    else:
        pass # don't wait

# get output from a command run in shell, subprocess version
def get_shell_output_subprocess(cmd):
    p = Popen(cmd, shell=True,
              stdin=None, stdout=PIPE, stderr=STDOUT, close_fds=True)
    while p.wait() is None:
        time.sleep(0.1)
    buf = p.stdout.read()
    p.stdout.close()
    return buf.strip() if buf else None

# get output from a command run in shell without stderr, subprocess version
def get_shell_output2_subprocess(cmd):
    p = Popen(cmd, shell=True,
              stdin=None, stdout=PIPE, stderr=PIPE, close_fds=True)
    p.stderr.close()
    while p.wait() is None:
        time.sleep(0.1)
    buf = p.stdout.read()
    p.stdout.close()
    return buf.strip() if buf else None

# get error from a command run in shell, subprocess version
def get_shell_output3_subprocess(cmd):
    p = Popen(cmd, shell=True,
              stdin=None, stdout=None, stderr=PIPE, close_fds=True)
    while p.wait() is None:
        time.sleep(0.1)
    buf = p.stderr.read()
    p.stderr.close()
    return buf.strip() if buf else None


######################################################################
##### run_dettached
def run_dettached(prog, *args):
    pid = os.fork()
    if pid == 0:
        os.setsid()
        os.chdir('/')
        try:
            maxfd = os.sysconf("SC_OPEN_MAX")
        except (AttributeError, ValueError):
            maxfd = 256       # default maximum
        # os.closerange(0, maxfd) # python v2.6+
        for fd in xrange(0, maxfd):
            try:
                os.close(fd)
            except OSError:   # ERROR (ignore)
                pass
        # Redirect the standard file descriptors to /dev/null.
        os.open("/dev/null", os.O_RDONLY)     # standard input (0)
        os.open("/dev/null", os.O_RDWR)       # standard output (1)
        os.open("/dev/null", os.O_RDWR)       # standard error (2)
        pid2 = os.fork()
        if pid2 == 0:
            os.execlp(prog, prog, *args)
        else:
            os.waitpid(-1, os.P_NOWAIT)
        os._exit(0)
    else:
        os.wait()


######################################################################
##### un/compress(ed) files
# compress/uncompress file: gzip/gunzip, bzip2/bunzip2
def do_compress_uncompress_file(filename, path, typ):
    if os.path.isabs(filename):
        fullfile = filename
        filename = os.path.basename(filename)
    else:
        fullfile = os.path.join(path, filename)
    if not os.path.isfile(fullfile):
        return -1, '%s: is not a file' % filename
    c = compress.check_compressed_file(fullfile)
    if c is None or isinstance(c, compress.PackagerTAR):
        packager = compress.packagers_by_type[typ]
        c = packager(fullfile)
        cmd = c.build_compress_cmd()
    elif c.type == typ:
        cmd = c.build_uncompress_cmd()
    else:
        return -1, '%s: can\'t un/compress with %s' % \
               (filename, compress.packagers_by_type[typ].compress_prog)
    st, msg = run_shell(encode(cmd), encode(path), return_output=True)
    return st, msg

def compress_uncompress_file(tab, typ):
    if tab.selections:
        fs = tab.selections[:]
    else:
        fs = [tab.sorted[tab.file_i]]
    ProcessLoopUnCompress('Un/Compress file', do_compress_uncompress_file,
                          fs, tab.path, typ).run()
    tab.selections = []
    app.regenerate()


# uncompress directory
def do_uncompress_dir(filename, path, dest, is_tmp=False):
    if os.path.isabs(filename):
        fullfile = filename
        filename = os.path.basename(filename)
    else:
        fullfile = os.path.join(path, filename)
    if not os.path.isfile(fullfile):
        return -1, '%s: is not a file' % filename
    c = compress.check_compressed_file(fullfile)
    if c is None:
        return -1, '%s: can\'t uncompress' % filename
    cmd = c.build_uncompress_cmd()
    st, msg = run_shell(encode(cmd), encode(dest), return_output=True)
    if st < 0: # (-100, -1),
        # never reached if user stops (-100) because this process is killed
        c.delete_uncompress_temp(dest, is_tmp)
    return st, msg


def uncompress_dir(tab, dest=None, is_tmp=False):
    """uncompress tarred file in path directory"""

    if dest is None:
        dest = tab.path
    if tab.selections:
        fs = tab.selections[:]
    else:
        fs = [tab.sorted[tab.file_i]]
    ProcessLoopUnCompress('Uncompress file', do_uncompress_dir,
                          fs, tab.path, dest, is_tmp).run()
    tab.selections = []


# compress directory: tar and gzip, bzip2
def do_compress_dir(filename, path, typ, dest, is_tmp=False):
    if os.path.isabs(filename):
        fullfile = filename
        filename = os.path.basename(filename)
    else:
        fullfile = os.path.join(path, filename)
    if not os.path.isdir(fullfile):
        return -1, '%s: is not a directory' % filename
    c = compress.packagers_by_type[typ](fullfile)
    if c is None:
        return -1, '%s: can\'t compress' % filename
    cmd = c.build_compress_cmd()
    st, msg = run_shell(encode(cmd), encode(dest), return_output=True)
    if st < 0: # (-100, -1):
        # never reached if user stops (-100) because this process is killed
        c.delete_compress_temp(dest, is_tmp)
    return st, msg


def compress_dir(tab, typ, dest=None, is_tmp=False):
    """compress directory to current path"""

    if dest is None:
        dest = tab.path
    if tab.selections:
        fs = tab.selections[:]
    else:
        fs = [tab.sorted[tab.file_i]]
    ProcessLoopUnCompress('Compress file', do_compress_dir,
                          fs, tab.path, typ, dest, is_tmp).run()
    tab.selections = []


######################################################################
##### find / grep
# find/grep
def do_findgrep(path, files, pattern):
    # escape special chars
    pat_re = pattern.replace('\\', '\\\\\\\\').replace('-', '\\-')
    pat_re = pat_re.replace('(', '\\(').replace(')', '\\)')
    pat_re = pat_re.replace('[', '\\[').replace(']', '\\]')
    ign = app.prefs.options['grep_ignorecase'] and 'i' or ''
    rex = app.prefs.options['grep_regex'] and 'E' or ''
    # 1. find . -type f -iname "*.py" -exec grep -EHni PATTERN {} \;
    # the slowest, 10x
    # 2. find . -type f -iname "*py" -print0 | xargs --null grep -EHni PATTERN
    # maybe the best choice
    cmd = '%s "%s" -type f -iname "%s" -print0 | %s --null %s -%sHn%s \"%s\"' % \
          (sysprogs['find'], path, files, sysprogs['xargs'], sysprogs['grep'], rex, ign, pat_re)
    # 3. grep -EHni PATTERN `find . -type f -iname "*.py"`
    # don't like `
    # 4. grep -REHni PATTERN --include "*.py" .
    # the fastest, but non-POSIX, because of: -R, --include
    # cmd = '%s -R%sHn%s \"%s\" --include "%s" "%s"' % \
    #       (sysprogs['grep'], rex, ign, pat_re, files, path)
    st, ret = ProcessFunc('Searching',
                          'Searching for \"%s\" in \"%s\" files' % (pattern, files),
                          run_shell, encode(cmd), path, True).run()
    if not ret:
        return 0, []
    if st < 0: # (-100, -1) => error
        return st, ret
    elif st == 0:
        ret = [f.strip() for f in ret.split('\n') if f.strip() != '']
    matches = []
    if len(ret) > 0:
        # filename:linenumber:matching
        # note that filename could contain ':', so we have to parse
        for l in ret:
            if not l:
                continue
            lst = l.split(':')
            if len(lst) == 1: # binary file
                linenumber = 0
                filename = lst[0].split(' ')[-2] # FIXME: filename can contain SPC
            else:
                i = len(lst) - 2
                while True:
                    filename = decode(':'.join(lst[:i]))
                    if os.path.exists(filename):
                        break
                    else:
                        i -= 1
                try:
                    linenumber = int(lst[i])
                except ValueError:
                    linenumber = 0
            filename = filename.replace(path, '')
            if filename[0] == os.sep and path != os.sep:
                filename = filename[1:]
            matches.append((filename, linenumber))
    matches = ['%s:%d' % (f, l) for f, l in sorted(matches)]
    return 0, matches


# find
def do_find(path, files):
    cmd = '%s %s -name \"%s\" -print' % (sysprogs['find'], path, files)
    st, ret = ProcessFunc('Searching',
                          'Searching for \"%s\" files' % files,
                          run_shell, encode(cmd), path, True).run()
    if not ret:
        return 0, []
    if st < 0: # (-100, -1) => error
        return st, ret
    elif st == 0:
        ret = [f.strip() for f in ret.split('\n') if f.strip() != '']
    matches = []
    if len(ret) > 0:
        for filename in ret:
            filename = decode(filename).strip().replace(path, '')
            if filename is not None and filename != '':
                if filename[0] == os.sep and path != os.sep:
                    filename = filename[1:]
                matches.append(filename)
    return 0, sorted(matches)


######################################################################
##### encode/decode strings
def encode(buf):
    return buf.encode(g_encoding)


def decode(buf):
    if isinstance(buf, unicode):
        return buf
    for c in codecs_list:
        try:
            buf = buf.decode(c)
        except UnicodeDecodeError:
            continue
        else:
            return buf
    else:
        return buf.decode('ascii', 'replace')


def ask_convert_invalid_encoding_filename(filename):
    auto = app.prefs.options['automatic_file_encoding_conversion']
    if auto == -1:
        return False
    elif auto == 1:
        return True
    elif auto == 0:
        ret = messages.confirm('Detected invalid encoding',
                               'In file <%s>, convert' % filename)
        try:
            app.display()
        except:
            pass
        return (ret == 1)
    else:
        raise ValueError


######################################################################
##### useful functions
def get_escaped_filename(filename):
    filename = filename.replace('$', '\\$')
    if filename.find('"') != -1:
        filename = filename.replace('"', '\\"')
    return encode(filename)


def get_escaped_command(cmd, filename):
    filename = filename.replace('$', '\$')
    if filename.find('"') != -1:
        filename = filename.replace('"', '\\"')
        return '%s \'%s\'' % (encode(cmd), encode(filename))
    else:
        return '%s \"%s\"' % (encode(cmd), encode(filename))


def run_on_current_file(program, filename):
    cmd = get_escaped_command(app.prefs.progs[program], filename)
    curses.endwin()
    os.system(cmd)
    curses.curs_set(0)


######################################################################
if sys.version_info[:2] < (2, 4):
    import popen2
    run_shell = run_shell_popen
    run_in_background = run_in_background_system
    get_shell_output = get_shell_output_popen
    get_shell_output2 = get_shell_output2_popen
    get_shell_output3 = get_shell_output3_popen
else:
    from subprocess import Popen, PIPE, STDOUT
    run_in_background = run_in_background_subprocess
    run_shell = run_shell_subprocess
    get_shell_output = get_shell_output_subprocess
    get_shell_output2 = get_shell_output2_subprocess
    get_shell_output3 = get_shell_output3_subprocess


######################################################################
