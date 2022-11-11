# Exceptions for reportbug
#   Written by Chris Lawrence <lawrencc@debian.org>
#   (C) 2002-04 Chris Lawrence
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


class reportbug_exception(Exception):
    pass


class reportbug_ui_exception(reportbug_exception):
    pass


# Can't initialize interface
class UINotImportable(reportbug_ui_exception):
    pass


# No package found
class NoPackage(reportbug_ui_exception):
    pass


# No bugs found
class NoBugs(reportbug_ui_exception):
    pass


# Nothing to report
class NoReport(reportbug_ui_exception):
    pass


# Code is not implemented
class UINotImplemented(reportbug_ui_exception):
    pass


# Other exceptions
# No network access
class NoNetwork(reportbug_exception):
    pass


# Invalid regular expression
class InvalidRegex(reportbug_exception):
    pass


# Lame empty exception used later to save some coding
class NoMessage(reportbug_exception):
    pass


# There was a problem accessing BTS
class QuertBTSError(reportbug_exception):
    pass


# Why handle broken messages?
class BadMessage(reportbug_exception):
    pass
