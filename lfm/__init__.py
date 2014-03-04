# -*- coding: utf-8 -*-

"""
Copyright (C) 2001-11, Iñigo Serna <inigoserna@gmail.com>.
All rights reserved.

This software has been realised under the GPL License, see the COPYING
file that comes with this package. There is NO WARRANTY.

'Last File Manager' is (tries to be) a simple 'midnight commander'-type
application for UNIX console.
"""


######################################################################
import locale
from sys import exit

try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    print 'lfm can\'t use the encoding defined in your system: "%s"' % \
        '.'.join(locale.getdefaultlocale())
    print 'Please configure before running lfm. Eg. $ export LANG=en_GB.UTF-8'
    exit(-1)

g_encoding = locale.getpreferredencoding()
if g_encoding is None or g_encoding == '':
    print 'lfm can\'t find a valid encoding for your terminal.'
    print 'Please configure before running lfm. Eg. $ export LANG=en_GB.UTF-8'
    exit(-1)


######################################################################
AUTHOR = u'Iñigo Serna'
VERSION = '2.3'
DATE = '2001-11'

LFM_NAME = 'lfm - Last File Manager'


######################################################################
##### lfm
sysprogs = { 'tar': 'tar',
             'bzip2': 'bzip2',
             'gzip': 'gzip',
             'zip': 'zip',
             'unzip': 'unzip',
             'rar': 'rar',
             '7z': '7z',
             'xz': 'xz',
             'grep': 'grep',
             'find': 'find',
             'which': 'which',
             'xargs': 'xargs' }

RET_QUIT, RET_EXIT = -1, -2
RET_TOGGLE_PANE, RET_TAB_NEW, RET_TAB_CLOSE, RET_NO_UPDATE, \
    RET_HALF_UPDATE, RET_HALF_UPDATE_OTHER = xrange(1, 7)
PANE_MODE_HIDDEN, PANE_MODE_LEFT, PANE_MODE_RIGHT, PANE_MODE_FULL = xrange(4)


######################################################################
