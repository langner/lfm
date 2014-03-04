# -*- coding: utf-8 -*-

"""files.py

This module defines files utilities for lfm.
"""


import sys
import os
import os.path
import stat
import time
import pwd
import grp
import shutil
import tempfile

from utils import get_shell_output, get_shell_output2, encode, decode, \
                  ask_convert_invalid_encoding_filename


########################################################################
##### constants
# File Type:    dir, link to directory, link, nlink, char dev,
#               block dev, fifo, socket, executable, file
(FTYPE_DIR, FTYPE_LNK2DIR, FTYPE_LNK, FTYPE_NLNK, FTYPE_CDEV, FTYPE_BDEV,
 FTYPE_FIFO, FTYPE_SOCKET, FTYPE_EXE, FTYPE_REG, FTYPE_UNKNOWN) = xrange(11)

FILETYPES = { FTYPE_DIR: (os.sep, 'Directory'),
              FTYPE_LNK2DIR: ('~', 'Link to Directory'),
              FTYPE_LNK: ('@', 'Link'), FTYPE_NLNK: ('!', 'No Link'),
              FTYPE_CDEV: ('-', 'Char Device'), FTYPE_BDEV: ('+', 'Block Device'),
              FTYPE_FIFO: ('|', 'Fifo'), FTYPE_SOCKET: ('#', 'Socket'),
              FTYPE_EXE: ('*', 'Executable'), FTYPE_REG: (' ', 'File'),
              FTYPE_UNKNOWN: ('?', 'Unknown') }

(FT_TYPE, FT_PERMS, FT_OWNER, FT_GROUP, FT_SIZE, FT_MTIME) = xrange(6)

# Sort Type:    None, byName, bySize, byDate, byType
(SORTTYPE_None, SORTTYPE_byName, SORTTYPE_byName_rev, SORTTYPE_bySize,
 SORTTYPE_bySize_rev, SORTTYPE_byDate, SORTTYPE_byDate_rev) = xrange(7)

SYSTEM_PROGRAMS = []


########################################################################
##### general functions
# HACK: checks for st_rdev in stat_result, falling back to
#       "ls -la %s" hack if Python before 2.2 or without st_rdev
try:
    os.stat_result.st_rdev
except AttributeError:
    def get_rdev(f):
        """'ls -la' to get mayor and minor number of devices"""
        try:
            buf = get_shell_output('ls -la %s' % encode(f))
        except:
            return 0
        else:
            try:
                return int(buf[4][:-1]), int(buf[5])
            except:
                # HACK: found 0xff.. encoded device numbers, ignore them...
                return 0, 0
else:
    def get_rdev(f):
        """mayor and minor number of devices"""
        r = os.stat(f).st_rdev
        return r >> 8, r & 255


def __get_size(f):
    """return the size of the directory or file via 'du -sk' command"""

    buf = get_shell_output2('du -sk \"%s\"' % encode(f))
    return (buf==None) and 0 or int(buf.split()[0])*1024


def get_realpath(path, filename, filetype):
    """return absolute path or, if path is a link, pointed file"""

    if filetype in (FTYPE_LNK2DIR, FTYPE_LNK, FTYPE_NLNK):
        try:
            return '-> ' + os.readlink(os.path.join(path, filename))
        except os.error:
            return os.path.join(path, filename)
    else:
        return os.path.join(path, filename)


def get_linkpath(path, filename):
    """return absolute path to the destination of a link"""

    link_dest = os.readlink(os.path.join(path, filename))
    return os.path.normpath(os.path.join(path, link_dest))


def join(directory, f):
    if not os.path.isdir(directory):
        directory = os.path.dirname(directory)
    return os.path.join(directory, f)


def __get_filetype(lmode, f):
    """get the type of the file. See listed types above"""

    if stat.S_ISDIR(lmode):
        return FTYPE_DIR
    if stat.S_ISLNK(lmode):
        try:
            mode = os.stat(f)[stat.ST_MODE]
        except OSError:
            return FTYPE_NLNK
        else:
            return FTYPE_LNK2DIR if stat.S_ISDIR(mode) else FTYPE_LNK
    if stat.S_ISCHR(lmode):
        return FTYPE_CDEV
    if stat.S_ISBLK(lmode):
        return FTYPE_BDEV
    if stat.S_ISFIFO(lmode):
        return FTYPE_FIFO
    if stat.S_ISSOCK(lmode):
        return FTYPE_SOCKET
    if stat.S_ISREG(lmode) and (lmode & 0111):
        return FTYPE_EXE
    else:
        return FTYPE_REG       # if no other type, regular file


def get_fileinfo(f, pardir_flag=False, show_dirs_size=False):
    """return information about a file, with format:
    (filetype, perms, owner, group, size, mtime)"""

    f = os.path.abspath(f)
    try:
        st = os.lstat(f)
    except OSError:
        return (FTYPE_UNKNOWN, 0, 'root', 'root', 0, 0)
    typ = __get_filetype(st[stat.ST_MODE], f)
    if typ in (FTYPE_DIR, FTYPE_LNK2DIR) and not pardir_flag and show_dirs_size:
        size = __get_size(f)
    elif typ in (FTYPE_CDEV, FTYPE_BDEV):
        # HACK: it's too time consuming to calculate all files' rdevs
        #       in a directory, so we just calculate what we need
        #       at show time
        # maj_red, min_rdev = get_rdev(file)
        size = 0
    else:
        size = st[stat.ST_SIZE]
    try:
        owner = pwd.getpwuid(st[stat.ST_UID])[0]
    except:
        owner = unicode(st[stat.ST_UID])
    try:
        group = grp.getgrgid(st[stat.ST_GID])[0]
    except:
        group = unicode(st[stat.ST_GID])
    return (typ, stat.S_IMODE(st[stat.ST_MODE]), owner, group,
            size, st[stat.ST_MTIME])


def get_fileinfo_extended(f):
    """return additional information about a file, with format:
    (num_links, uid, gid, atime, mtime, ctime, inode, dev)"""

    try:
        st = os.lstat(f)
    except OSError:
        return (0, 0, 0, 0, 0, 0, 0, 0)
    else:
        return (st[stat.ST_NLINK], st[stat.ST_UID], st[stat.ST_GID],
                st[stat.ST_ATIME], st[stat.ST_MTIME], st[stat.ST_CTIME],
                st[stat.ST_DEV], st[stat.ST_INO])


def perms2str(p):
    permis = ['x', 'w', 'r']
    perms = ['-'] * 9
    for i in xrange(9):
        if p & (0400 >> i):
            perms[i] = permis[(8-i) % 3]
    if p & 04000:
        perms[2] = 's'
    if p & 02000:
        perms[5] = 's'
    if p & 01000:
        perms[8] = 't'
    return ''.join(perms)


def get_fileinfo_dict(path, filename, filevalues):
    """return a dict with file information"""

    res = {}
    res['filename'] = filename
    typ = filevalues[FT_TYPE]
    res['type_chr'] = FILETYPES[typ][0]
    if typ in (FTYPE_CDEV, FTYPE_BDEV):
        # HACK: it's too time consuming to calculate all files' rdevs
        #       in a directory, so we just calculate needed ones here
        #       at show time
        maj_rdev, min_rdev = get_rdev(os.path.join(path, filename))
        res['size'] = 0
        res['maj_rdev'] = maj_rdev
        res['min_rdev'] = min_rdev
        res['dev'] = 1
    else:
        size = filevalues[FT_SIZE]
        if size >= 1000000000L:
            size = str(size/(1024*1024)) + 'M'
        elif size >= 10000000L:
            size = str(size/1024) + 'K'
        else:
            size = str(size)
        res['size'] = size
        res['maj_rdev'] = 0
        res['min_rdev'] = 0
        res['dev'] = 0
    res['perms'] = perms2str(filevalues[1])
    res['owner'] = filevalues[FT_OWNER]
    res['group'] = filevalues[FT_GROUP]
    if -15552000 < (time.time() - filevalues[FT_MTIME]) < 15552000:
        # filedate < 6 months from now, past or future
        mtime = time.strftime('%a %b %d %H:%M', time.localtime(filevalues[FT_MTIME]))
        mtime2 = time.strftime('%d %b %H:%M', time.localtime(filevalues[FT_MTIME]))
    else:
        mtime = time.strftime('%a  %d %b %Y', time.localtime(filevalues[FT_MTIME]))
        mtime2 = time.strftime('%d %b  %Y', time.localtime(filevalues[FT_MTIME]))
    res['mtime'] = decode(mtime)
    res['mtime2'] = decode(mtime2)
    return res


def get_dir(path, show_dotfiles=1):
    """return a dict whose elements are formed by file name as key
    and a (filetype, perms, owner, group, size, mtime) tuple as value"""

    # bug in python: os.path.normpath(u'/') returns str instead of unicode,
    #                so convert to unicode anyway
    path = decode(os.path.normpath(path))
    files_dict = {}
    if path != os.sep:
        files_dict[os.pardir] = get_fileinfo(os.path.dirname(path), 1)
    files_list = os.listdir(path)
    if not show_dotfiles:
        files_list = [f for f in files_list if f[0] != '.']
    for f in files_list:
        if not isinstance(f, unicode):
            newf = decode(f)
            if ask_convert_invalid_encoding_filename(newf):
                convert_filename_encoding(path, f, newf)
            f = newf
        files_dict[f] = get_fileinfo(os.path.join(path, f))
    return len(files_dict), files_dict


def get_owners():
    """get a list with the users defined in the system"""
    return [e[0] for e in pwd.getpwall()]


def get_user_fullname(user):
    """return the fullname of an user"""
    try:
        return pwd.getpwnam(user)[4]
    except KeyError:
        return '<unknown user name>'


def get_groups():
    """get a list with the groups defined in the system"""
    return [e[0] for e in grp.getgrall()]


def set_perms(f, perms, recursive=False):
    """set permissions to a file"""
    ps, i = 0, 8
    for p in perms:
        if p == 'x':
            ps += 1 * 8 ** int(i/3)
        elif p == 'w':
            ps += 2 * 8 ** int(i/3)
        elif p == 'r':
            ps += 4 * 8 ** int(i/3)
        elif p == 't' and i == 0:
            ps += 1 * 8 ** 3
        elif p == 's':
            if i == 6:
                ps += 4 * 8 ** 3
            elif i == 3:
                ps += 2 * 8 ** 3
        i -= 1
    try:
        if recursive:
            pc = PathContents([f], os.path.dirname(f))
            for e, s in pc.iter_walk():
                if not os.path.isdir(e):
                    os.chmod(e, ps)
        else:
            os.chmod(f, ps)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def set_owner_group(f, owner, group, recursive=False):
    """set owner and group to a file"""
    try:
        owner_n = pwd.getpwnam(owner)[2]
    except:
        owner_n = int(owner)
    try:
        group_n = grp.getgrnam(group)[2]
    except:
        group_n = int(group)
    try:
        if recursive:
            pc = PathContents([f], os.path.dirname(f))
            for e, s in pc.iter_walk():
                os.chown(e, owner_n, group_n)
        else:
            os.chown(f, owner_n, group_n)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def get_mount_points():
    """return system mount points as list of (mountpoint, device, fstype).
    Compatible with linux and solaris"""
    try:
        buf = get_shell_output('mount')
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)
    if buf is None or buf == '':
        return ('Can\t run "mount" command', 0)
    lst = []
    for e in buf.split('\n'):
        es = e.split()
        lst.append((es[2], es[0], es[4]))
    return sorted(lst, reverse=True)


def get_mountpoint_for_file(f):
    # check mps
    mps = get_mount_points()
    for m, d, t in mps:
        if f.find(m) != -1:
            return (m, d, t)
    else:
        return ('/', '<unknown>', '<unknown>')


def convert_filename_encoding(path, filename, newname):
    curpath = os.getcwd()
    os.chdir(path)
    os.rename(filename, newname)
    os.chdir(curpath)


def get_binary_programs():
    d = {}
    for p in os.getenv('PATH').split(':'):
        try:
            for prog in os.listdir(p):
                d.setdefault(prog)
        except OSError:
            pass
    return sorted(d.keys())

SYSTEM_PROGRAMS = get_binary_programs()


########################################################################
##### temporary file
def mktemp():
    return tempfile.mkstemp()[1]

def mkdtemp():
    return tempfile.mkdtemp()


########################################################################
##### sort
def __do_sort(f_dict, sortmode, sort_mix_cases):
    if sortmode == SORTTYPE_None:
        names = f_dict.keys()
    elif sortmode in (SORTTYPE_byName, SORTTYPE_byName_rev):
        names = sorted(f_dict.keys(),
                       key=lambda f: f.lower() if sort_mix_cases else f,
                       reverse=sortmode==SORTTYPE_byName_rev)
    elif sortmode in (SORTTYPE_bySize, SORTTYPE_bySize_rev):
        names = sorted(f_dict.keys(),
                       key=lambda f: f_dict[f][FT_SIZE],
                       reverse=sortmode==SORTTYPE_bySize_rev)
    elif sortmode in (SORTTYPE_byDate, SORTTYPE_byDate_rev):
        names = sorted(f_dict.keys(),
                       key=lambda f: f_dict[f][FT_MTIME],
                       reverse=sortmode==SORTTYPE_byDate_rev)
    if names.count(os.pardir) != 0: # move pardir to top
        names.remove(os.pardir)
        names.insert(0, os.pardir)
    return names


def sort_dir(files_dict, sortmode, sort_mix_dirs, sort_mix_cases):
    """return an array of files which are sorted by mode"""

    d, f = {}, {}
    if sort_mix_dirs:
        f = files_dict
        d1 = []
    else:
        for k, v in files_dict.items():
            if v[FT_TYPE] in (FTYPE_DIR, FTYPE_LNK2DIR):
                d[k] = v
            else:
                f[k] = v
        d1 = __do_sort(d, sortmode, sort_mix_cases)
    d2 = __do_sort(f, sortmode, sort_mix_cases)
    d1.extend(d2)
    return d1


########################################################################
##### complete
def complete(entrypath, panelpath):
    if not entrypath:
        path = panelpath + os.sep
        base = ''
    elif entrypath[0] == os.sep:
        path = entrypath
        base = os.path.dirname(entrypath)
    else:
        path = os.path.join(panelpath, entrypath)
        base = os.path.dirname(entrypath)
    # get elements
    try:
        if path.endswith(os.sep) and os.path.isdir(path):
            basedir = path
            fs = os.listdir(path)
        else:
            basedir = os.path.dirname(path)
            start = os.path.basename(path)
            try:
                entries = os.listdir(basedir)
            except OSError:
                entries = []
            fs = [f for f in entries if f.startswith(start)]
    except (IOError, os.error), (errno, strerror):
        fs = []
    # sort files with dirs first
    d1, d2 = [], []
    for f in fs:
        if os.path.isdir(os.path.join(basedir, f)):
            d1.append(f + os.sep)
        else:
            d2.append(f)
    d1.sort()
    d2.sort()
    d1.extend(d2)
    return base, d1


def complete_programs(text):
    return [prog for prog in SYSTEM_PROGRAMS if prog.startswith(text)]


########################################################################
##### actions
def do_create_link(pointto, link):
    os.symlink(pointto, link)


def modify_link(pointto, linkname):
    try:
        os.unlink(linkname)
        do_create_link(pointto, linkname)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def create_link(pointto, linkname):
    try:
        do_create_link(pointto, linkname)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def copy_bulk(src, dest):
    if os.path.isdir(src):
        shutil.copytree(src, dest, symlinks=True)
    elif os.path.isfile(src):
        shutil.copy2(src, dest)


def delete_bulk(path, ignore_errors=False):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=ignore_errors)
    elif os.path.isfile(path):
        if ignore_errors:
            try:
                os.unlink(path)
            except:
                pass
        else:
            os.unlink(path)


def do_copy(filename, basepath, dest, rename_dir=False, check_fileexists=True):
    src = os.path.join(basepath, filename)
    if os.path.exists(dest) and os.path.isdir(dest):
        if rename_dir:
            filename = os.sep.join(filename.split(os.sep)[1:])
        dest = os.path.join(dest, filename)
    if os.path.exists(dest) and check_fileexists:
        return os.path.basename(dest)
    if os.path.islink(src):
        try:
            do_create_link(os.readlink(src), dest)
        except (IOError, os.error), (errno, strerror):
            return (strerror, errno)
    elif os.path.isdir(src):
        try:
            os.mkdir(dest)
        except (IOError, os.error), (errno, strerror):
            if errno != 17:     # don't error if directory exists
                return (strerror, errno)
        else:
            # copy mode, times, owner and group
            try:
                st = os.lstat(src)
                os.chown(dest, st[stat.ST_UID], st[stat.ST_GID])
                shutil.copymode(src, dest)
                shutil.copystat(src, dest)
            except (IOError, os.error), (errno, strerror):
                pass
    elif src == dest:
        return ('Source and destination are the same file', 0)
    else:
        if os.path.isfile(src): # stat.S_ISREG(os.lstat(src)[stat.ST_MODE])
            try:
                shutil.copy2(src, dest)
            except (IOError, os.error), (errno, strerror):
                return (strerror, errno)
        else:
            return ('Special files can\'t be copied or moved', 0)


def do_rename(f, path, newname, check_fileexists=True):
    src = os.path.join(path, f)
    if newname[0] != os.sep:
        dest = os.path.join(path, newname)
    else:
        dest = newname
    if src == dest:
        return ('Source and destination are the same file', 0)
    if os.path.dirname(dest) != path:
        return ('Can\'t rename to different directory', 0)
    if os.path.isfile(dest) and check_fileexists:
        return os.path.basename(newname)
    try:
        os.rename(src, dest)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def do_backup(f, path, backup_ext):
    src = os.path.join(path, f)
    dest = os.path.join(path, f+backup_ext)
    if os.path.exists(dest):
        return ('File exists', 0)
    try:
        copy_bulk(src, dest)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def do_delete(f):
    try:
        if os.path.islink(f):
            os.unlink(f)
        elif os.path.isdir(f):
            os.rmdir(f)
        else:
            os.unlink(f)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


def mkdir(path, newdir):
    fullpath = os.path.join(path, newdir)
    try:
        os.makedirs(fullpath)
    except (IOError, os.error), (errno, strerror):
        return (strerror, errno)


########################################################################
##### PathContents
class PathContents(object):
    def __init__(self, fs, basepath=None):
        """fs must be a list with relative path to files"""
        if not isinstance(fs, list) or not len(fs) > 0:
            raise TypeError, "fs must be a list of files"
        if basepath is None:
            basepath = os.getcwd()
        self.basepath = os.path.abspath(basepath)
        if not os.path.isdir(self.basepath):
            raise TypeError, "basepath must be a valid directory or None"
        self.__entries = []
        self.__errors = []
        for f in fs:
            f = os.path.join(self.basepath, f)
            try:
                if os.path.islink(f):
                    self.__entries.append((f, 0))
                else:
                    self.__entries.append((f, os.path.getsize(f)))
            except (IOError, os.error), (errno, strerror):
                self.__errors.append((f, (strerror, errno)))
            else:
                if os.path.isdir(f) and not os.path.islink(f):
                    try:
                        self.__fill_contents(f)
                    except UnicodeDecodeError:
                        raise UnicodeError
        self.length = len(fs)
        self.tlength = len(self.__entries)
        self.tsize = sum([f[1] for f in self.__entries]) or 1

    def __fill_contents(self, path):
        for root, dirs, files in os.walk(path, topdown=False, onerror=self.__on_error):
            for d in dirs:
                fullpath = os.path.join(root, d)
                try:
                    if os.path.islink(fullpath):
                        self.__entries.append((fullpath, 0))
                    else:
                        self.__entries.append((fullpath, os.path.getsize(fullpath)))
                except (IOError, os.error), (errno, strerror):
                    self.__errors.append((fullpath, (strerror, errno)))
            for f in files:
                fullpath = os.path.join(root, f)
                try:
                    if os.path.islink(fullpath):
                        self.__entries.append((fullpath, 0))
                    else:
                        self.__entries.append((fullpath, os.path.getsize(fullpath)))
                except (IOError, os.error), (errno, strerror):
                    self.__errors.append((fullpath, (strerror, errno)))

    def __on_error(self, exc):
        # print '[Error %d] %s: %s' % (exc.errno, exc.strerror, exc.filename)
        fullpath = os.path.join(self.basepath, exc.filename)
        self.__errors.append((fullpath, (exc.strerror, exc.errno)))

    def __repr__(self):
        return u'PathContents[Base:"%s" with %d entries (Total: %d items, %.2f KB)]' % \
            (self.basepath, self.length, self.tlength, self.tsize/1024)

    @property
    def entries(self, reverse=False):
        return sorted(self.__entries, reverse=reverse)

    @property
    def errors(self):
        return sorted(self.__errors)

    def iter_walk(self, reverse=False):
        for e in sorted(self.__entries, reverse=reverse):
            yield e

    def remove_files(self, fs):
        new = []
        length = self.length
        for f, s in self.__entries:
            if f in fs:
                length -= 1
            else:
                new.append((f, s))
        self.__entries = new
        self.length = (length > 0) and length or 0
        self.tlength = len(self.__entries)
        self.tsize = sum([f[1] for f in self.__entries]) or 1


########################################################################
