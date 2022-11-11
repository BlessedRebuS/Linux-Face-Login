#
# urlutils.py - Simplified urllib handling
#
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

import http.client
import urllib.request
import urllib.error
import socket
import shlex
import os
import sys
import webbrowser
import requests

from .exceptions import (
    NoNetwork,
)

from .__init__ import VERSION_NUMBER

UA_STR = 'reportbug/' + VERSION_NUMBER + ' (Debian)'


def urlopen(url, proxies=None, timeout=60, data=None):
    """
    Open an URL and return the content

    This is a helper function for :func:`open_url()`.

    Parameters
    ----------
    url : str
        The URL to retrieve
    proxies : dict
        proxies to use
    timeout : int
        request timeout in seconds
    data
        unused

    Returns
    -------
    str
        Content of the response
    """
    if not proxies:
        proxies = urllib.request.getproxies()

    headers = {'User-Agent': UA_STR,
               'Accept-Encoding': 'gzip;q=1.0, deflate;q=0.9, identity;q=0.5'}

    return requests.get(url, headers=headers, proxies=proxies, timeout=timeout).text


# Global useful URL opener; returns None if the page is absent, otherwise
# like urlopen
def open_url(url, http_proxy=None, timeout=60):
    """
    Open an URL and return the content

    Parameters
    ----------
    url : str
        The URL to retrieve
    http_proxy : str
        HTTP proxy server URL to use for connection.
        By default, use the :func:`urllib.request.getproxies()` settings.
    timeout : int
        connection timeout in seconds

    Returns
    -------
    str
        Content of the response
    """
    # Set timeout to 60 secs (1 min), cfr bug #516449
    # in #572316 we set a user-configurable timeout
    socket.setdefaulttimeout(timeout)

    proxies = urllib.request.getproxies()
    if http_proxy:
        proxies['http'] = http_proxy
        proxies['https'] = http_proxy

    try:
        page = urlopen(url, proxies, timeout)
    except urllib.error.HTTPError as x:
        if x.code in (404, 500, 503):
            return None
        else:
            raise
    except (socket.gaierror, socket.error, urllib.error.URLError):
        raise NoNetwork
    except OSError as data:
        if data and data[0] == 'http error' and data[1] == 404:
            return None
        else:
            raise NoNetwork
    except TypeError:
        print("http_proxy environment variable must be formatted as a valid URI", file=sys.stderr)
        raise NoNetwork
    except http.client.HTTPException as exc:
        exc_name = exc.__class__.__name__
        message = f"Failed to open {url} ({exc_name}: {exc})"
        raise NoNetwork(message)
    return page


def launch_browser(url):
    """
    Launch a web browser to view an URL

    Parameters
    ----------
    url : str
        The URL to view

    Returns
    -------
    None
    """
    if not os.system('command -v xdg-open >/dev/null 2>&1'):
        cmd = 'xdg-open ' + shlex.quote(url)
        os.system(cmd)
        return

    if webbrowser:
        webbrowser.open(url)
        return
