#
# checkbuildd.py - Check buildd.debian.org for successful past builds
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

from html.parser import HTMLParser

from . import utils
from .urlutils import open_url
from reportbug.exceptions import (
    NoNetwork,
)

BUILDD_URL = 'https://buildd.debian.org/build.php?arch=%s&pkg=%s'


# Check for successful in a 'td' block
class BuilddParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.versions = {}
        self.savedata = None
        self.found_succeeded = False

    # --- Formatter interface, taking care of 'savedata' mode;
    # shouldn't need to be overridden

    def handle_data(self, data):
        if self.savedata is not None:
            self.savedata = self.savedata + data

    # --- Hooks to save data; shouldn't need to be overridden
    def save_bgn(self):
        self.savedata = ''

    def save_end(self, mode=0):
        data = self.savedata
        self.savedata = None
        if not mode and data is not None:
            data = ' '.join(data.split())
        return data

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.save_bgn()

    def handle_endtag(self, tag):
        if tag == 'td':
            data = self.save_end()
            if data and 'successful' in data.lower():
                self.found_succeeded = True


def check_built(src_package, timeout, arch=None, http_proxy=None):
    """
    Check if a source package was built successfully on a buildd

    The check is not about a specific package version. If `arch` is not
    given and there is evidence that any version of the package once
    built sucessfully on any architecture, this function returns True.

    If `arch` is given, the check is restricted to that architecture.

    Parameters
    ----------
    src_package : str
        name of a source package
    timeout : int
        connection timeout in seconds
    arch : str, optional
        the arch to be checked
    http_proxy : str, optional
        Http proxy url to use for connection

    Returns
    -------
    bool
        True if the connection succeeded and the package was found to
        have built successfully, otherwise False
    """
    if not arch:
        arch = utils.get_arch()

    try:
        page = open_url(BUILDD_URL % (arch, src_package), http_proxy, timeout)
    except NoNetwork:
        return False

    if not page:
        return False

    parser = BuilddParser()
    parser.feed(page)

    return parser.found_succeeded
