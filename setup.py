#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""Last File Manager is a powerful file manager for the UNIX console.
Based in a curses interface, it's written in Python."""


from distutils.core import setup
import sys


DOC_FILES = ['COPYING', 'README', 'README.pyview', 'NEWS', 'TODO', 'ChangeLog']
MAN_FILES = ['lfm.1', 'pyview.1']

classifiers = """\
Development Status :: 5 - Production/Stable
Environment :: Console :: Curses
Intended Audience :: End Users/Desktop
Intended Audience :: System Administrators
License :: OSI Approved :: GNU General Public License (GPL)
Natural Language :: English
Operating System :: POSIX
Operating System :: Unix
Programming Language :: Python
Topic :: Desktop Environment :: File Managers
Topic :: System :: Filesystems
Topic :: System :: Shells
Topic :: System :: System Shells
Topic :: Utilities
"""

doclines = __doc__.split("\n")

print doclines

if sys.version_info < (2, 3):
    _setup = setup
    def setup(**kwargs):
        if kwargs.has_key("classifiers"):
            del kwargs["classifiers"]
        _setup(**kwargs)


setup(name = 'lfm',
      version = '2.3',
      license = 'GPL',
      description = doclines[0],
      long_description = '\n'.join(doclines[2:]),
      author = u'Inigo Serna',
      author_email = 'inigoserna@gmail.com',
      url = 'https://inigo.katxi.org/devel/lfm',
      platforms = 'POSIX',
      classifiers = filter(None, classifiers.split("\n")),
      py_modules = ['lfm/__init__', 'lfm/lfm', 'lfm/messages', 'lfm/files',
                    'lfm/actions', 'lfm/compress', 'lfm/utils', 'lfm/vfs',
                    'lfm/config', 'lfm/pyview'],
      scripts = ['lfm/lfm', 'lfm/pyview'],
      data_files = [('share/doc/lfm', DOC_FILES),
                    ('share/man/man1', MAN_FILES)]
#      **addargs
     )


#  import os, os.path, sys
#  from distutils.sysconfig import get_python_lib
#  os.symlink(os.path.join(get_python_lib(), 'lfm/lfm.py'),
#             os.path.join(sys.exec_prefix, 'bin/lfm'))
