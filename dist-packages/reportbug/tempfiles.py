#
# tempfiles module - Temporary file handling for reportbug
#   Written by Chris Lawrence <lawrencc@debian.org>
#   (C) 1999-2008 Chris Lawrence
#   Copyright (C) 2008-2022 Sandro Tosi <morph@debian.org>
#
# This program is freely distributable per the following license:
#
#  Permission to use, copy, modify, and distribute this software and its
#  documentation for any purpose and without fee is hereby granted,
#  provided that the above copyright notice appears in all copies and that
#  both that copyright notice and this permission notice appear in
#  supporting documentation.
#
#  I DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING ALL
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL I
#  BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY
#  DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
#  WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
#  ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
#  SOFTWARE.

import os
import tempfile
import time


def tempfile_prefix(package=None, extra=None):
    """
    Generate filename prefix for a temporary file

    Parameters
    ----------
    package : str, optional
        package name, will be included in prefix if given
    extra : str, optional
        extra string to include in prefix

    Returns
    -------
    str
        filename prefix
    """
    plist = ['reportbug']
    if package:
        plist.append(package)
    if extra:
        plist.append(extra)
    plist.append(time.strftime('%Y%m%d%H%M%S-'))
    return '-'.join(plist)


template = tempfile_prefix()

# Derived version of mkstemp that returns a Python file object
_text_openflags = os.O_RDWR | os.O_CREAT | os.O_EXCL
if hasattr(os, 'O_NOINHERIT'):
    _text_openflags |= os.O_NOINHERIT
if hasattr(os, 'O_NOFOLLOW'):
    _text_openflags |= os.O_NOFOLLOW

_bin_openflags = _text_openflags
if hasattr(os, 'O_BINARY'):
    _bin_openflags |= os.O_BINARY


# Safe open, prevents filename races in shared tmp dirs
# Based on python-1.5.2/Lib/tempfile.py
def open_write_safe(filename, mode='w+b', bufsize=-1):
    """
    Wrapper for open() setting some flags

    Parameters
    ----------
    filename : str
        file name
    mode : str, optional
        open mode
    bufsize : int, optional
        buffer size in bytes

    Returns
    -------
    an open file object
    """
    if 'b' in mode:
        fd = os.open(filename, _bin_openflags, 0o600)
    else:
        fd = os.open(filename, _text_openflags, 0o600)

    try:
        return os.fdopen(fd, mode, bufsize)
    except Exception:
        os.close(fd)
        raise


# Wrapper for mkstemp; main difference is that text defaults to True, and it
# returns a Python file object instead of an os-level file descriptor
def TempFile(suffix="", prefix=template, dir=None, text=True,
             mode="w+", bufsize=-1):
    """
    Wrapper for tempfile.mkstemp

    Main differences are that text defaults to True, and it returns a
    Python file object instead of an os-level file descriptor.

    Parameters
    ----------
    suffix : str, optional
    prefix : str
    dir : str
    text : bool
    mode : str
    bufsize : int

    Returns
    -------
    (file object, str)
        tuple with file object and file name
    """
    fh, filename = tempfile.mkstemp(suffix, prefix, dir, text)
    fd = os.fdopen(fh, mode, bufsize)
    return (fd, filename)


def cleanup_temp_file(temp_filename):
    """
    Clean up a temporary file

    Removes (unlinks) the named file if it exists.

    Parameters
    ----------
    temp_filename : str
        Full filename of the file to clean up.

    Returns
    -------
    None
    """
    if os.path.exists(temp_filename):
        os.unlink(temp_filename)
