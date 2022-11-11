#
# checkversions.py - Find if the installed version of a package is the latest
#
#   Written by Chris Lawrence <lawrencc@debian.org>
#   (C) 2002-08 Chris Lawrence
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

import sys
import urllib.error

from . import utils
from .urlutils import open_url
from reportbug.exceptions import (
    NoNetwork,
)

# needed to parse new.822
from debian.deb822 import Deb822
from debian import debian_support

RMADISON_URL = 'https://qa.debian.org/madison.php?package=%s&text=on'
NEWQUEUE_URL = 'http://ftp-master.debian.org/new.822'


def compare_versions(current, upstream):
    """
    Compare package version strings

    This is a wrapper around `debian_support.version_compare()` that
    returns 0 if one if the versions is empty.

    Parameters
    ----------
    current : str
        version assumed to be currently installed
    upstream : str
        version assumed to be available upstream

    Returns
    -------
    int
        1 if upstream is newer than current, -1 if current is
        newer than upstream, and 0 if the same.
    """
    if not current or not upstream:
        return 0
    return debian_support.version_compare(upstream, current)


def later_version(a, b):
    """
    Pick the later version of two version strings

    This is a helper function originally used in
    :func:`get_incoming_version()`, but currently not used.

    Parameters
    ----------
    a : str
        first package version
    b : str
        second package version

    Returns
    -------
    str
        the later (higher) version string
    """
    if compare_versions(a, b) > 0:
        return b
    return a


def get_versions_available(package, timeout, dists=None, http_proxy=None, arch='i386'):
    """
    Get package versions available.

    If `dists` is not given, get versions from all dists known to the
    version lookup service at https://qa.debian.org/madison.php

    Parameters
    ----------
    package : str
        package name
    timeout : int
        connection timeout in seconds
    dists : (str, ...), optional
        tuple of dist names ('stable', 'testing' etc.) to check
    http_proxy : str, optional
        http proxy url
    arch : str, optional
        architecture name

    Returns
    -------
    {str: str, ...}
        dictionary with found dists as keys and versions as values,
        e.g.,:

            {
                "oldstable": "46.1",
                "stable": "1:26.1+1-3.2+deb10u1",
                "testing": "1:26.1+1-4",
                "unstable": "1:26.3+1-1"
            }
    """
    arch = utils.get_arch()

    url = RMADISON_URL % package
    if dists:
        url += '&s=' + ','.join(dists)
    # select only those lines that refers to source pkg
    # or to binary packages available on the current arch
    url += '&a=source,all,' + arch
    try:
        page = open_url(url, http_proxy, timeout)
    except NoNetwork:
        return {}
    except urllib.error.HTTPError as x:
        print("Warning:", x, file=sys.stderr)
        return {}
    if not page:
        return {}

    # The page looks like this:
    #
    # $ wget -qO- 'https://qa.debian.org/madison.php?package=emacs&text=on&s=oldstable,stable,testing,unstable,experimental&a=source,all,x86_64'
    #  emacs | 46.1                 | stretch  | all
    #  emacs | 1:26.1+1-3.2+deb10u1 | buster   | source, all
    #  emacs | 1:26.1+1-4           | bullseye | source, all
    #  emacs | 1:26.1+1-4           | sid      | source, all
    #  emacs | 1:26.3+1-1           | sid      | source, all

    # read the content of the page, remove spaces, empty lines
    content = page.replace(' ', '').strip()

    versions = {}
    for line in content.split('\n'):
        try:
            p, v, d, a = line.split('|')
        # skip lines not having the right number of fields
        except ValueError:
            continue

        if a == 'source':
            continue

        # map suites name (returned by madison, e.g. "bullseye") to
        # dist name (e.g. "testing").
        dist = utils.CODENAME2SUITE.get(d, d)

        versions[dist] = v

    return versions


def get_newqueue_available(package, timeout, dists=None, http_proxy=None, arch='i386'):
    """
    Get package versions available in the NEW queue

    If `dists` is not given, get versions from unstable (NEW queue).

    This is a helper function for :func:`check_available()`.

    Parameters
    ----------
    package : str
        package name
    timeout : int
        connection timeout in seconds
    dists : (str, ...), optional
        tuple of dist names ('stable', 'testing' etc.) to check
    http_proxy : str, optional
        http proxy url
    arch : str, optional
        unused

    Returns
    -------
    {str: str, ...}
        dictionary with found dists as keys and versions as values
    """
    if dists is None:
        dists = ('unstable (new queue)',)
    try:
        page = open_url(NEWQUEUE_URL, http_proxy, timeout)
    except NoNetwork:
        return {}
    except urllib.error.HTTPError as x:
        print("Warning:", x, file=sys.stderr)
        return {}
    if not page:
        return {}

    versions = {}

    # iter over the entries, one paragraph at a time
    for para in Deb822.iter_paragraphs(page):
        if para['Source'] == package:
            k = para['Distribution'] + ' (' + para['Queue'] + ')'
            # in case of multiple versions, choose the bigger
            versions[k] = max(para['Version'].split())

    return versions


def check_available(package, version, timeout, dists=None,
                    check_incoming=True, check_newqueue=True,
                    http_proxy=None, arch='i386'):
    """
    Check a package version against other available versions

    The package archive contains many different versions of most
    packages. This function determines whether a given package version
    is newer than all versions available in the archive, and (if not)
    which available versions are newer.

    Parameters
    ----------
    package : str
        package name
    version : str
        package version
    timeout : int
        connection timeout in seconds
    dists : (str, ...), optional
        tuple of dist names ('stable', 'testing' etc.) to check
    check_incoming : bool
        unused/ignored
    check_newqueue : bool
        True if the NEW queue should be checked for new versions
    http_proxy : str, optional
        http proxy url
    arch : str, optional
        architecture name

    Returns
    -------
    (dict, bool)
        Tuple with a dictionary and a bool. The dictionary contains the
        versions found to be newer than the given version. E.g.,
                {"unstable": "42.1", "testing": "42.0"}

        The bool indicates whether the checked (installed)
        version is strictly newer than all available versions.
    """
    avail = {}

    stuff = get_versions_available(package, timeout, dists, http_proxy, arch)
    avail.update(stuff)
    if check_newqueue:
        srcpackage = utils.get_source_name(package)
        if srcpackage is None:
            srcpackage = package
        stuff = get_newqueue_available(srcpackage, timeout, dists, http_proxy, arch)
        avail.update(stuff)
        # print gc.garbage, stuff

    new = {}

    # Number of distributions that are outdated compared to our
    # current version.
    newer = 0

    for dist in avail:
        comparison = compare_versions(version, avail[dist])
        if comparison > 0:
            # The available version is newer than our version.
            new[dist] = avail[dist]
        elif comparison < 0:
            # Our version is newer than the available version.
            newer += 1
    too_new = (newer and newer == len(avail))
    return new, too_new
