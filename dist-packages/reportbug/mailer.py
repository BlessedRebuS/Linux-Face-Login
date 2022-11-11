#
# mailer module - Mail User Agent interface for reportbug
#   Written by Chris Lawrence <lawrencc@debian.org>
#   Copyright (C) 1999-2008 Chris Lawrence
#   Copyright (C) 2008-2022 Sandro Tosi <morph@debian.org>
#   Copyright (C) 2020-2022 Nis Martensen <nis.martensen@web.de>
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

import email
import email.policy
import os
import re
import shlex
import shutil
import urllib
from .exceptions import BadMessage


MAX_ARG_LENGTH = 130000  # the actual limit on linux is 131071


class Mua:
    def __init__(self, command, needs_terminal=True):
        self._command = command
        self.executable = command.split()[0]
        self.needs_terminal = needs_terminal

    def _check_attachable(self, afile):
        return os.path.isfile(afile) and os.access(afile, os.R_OK)

    def get_send_command(self, filename, attachments=[]):
        cmd = self._command
        if '%s' not in cmd:
            cmd += ' %s'
        cmd = cmd % shlex.quote(filename)
        return cmd


class Mutt(Mua):
    def get_send_command(self, filename, attachments=[]):
        cmd = self._command
        if '%s' not in cmd:
            cmd += ' %s'
        cmd = cmd % shlex.quote(filename)
        if attachments:
            att = [shlex.quote(os.path.abspath(a))
                   for a in attachments if self._check_attachable(a)]
            if att:
                cmd += " -a " + " ".join(att)
        return cmd


class Gnus(Mua):
    def __init__(self):
        self.executable = 'emacsclient'
        self.needs_terminal = True

    def get_send_command(self, filename, attachments=[]):
        elisp = """(progn
                      (load-file "/usr/share/reportbug/reportbug.el")
                      (tfheen-reportbug-insert-template "%s"))"""
        filename = re.sub("[\"\\\\]", "\\\\\\g<0>", filename)
        elisp = shlex.quote(elisp % filename)
        cmd = "emacsclient --no-wait --eval %s 2>/dev/null || emacs --eval %s" % (elisp, elisp)
        return cmd


class Mailto(Mua):
    def _uq(self, ins):
        return urllib.parse.quote(ins, safe='/', errors='replace')

    def _get_headerparam(self, hdr, msg):
        parmstr = ""

        hd = msg[hdr]
        if hd:
            content = self._uq(''.join(hd.splitlines()))
            parmstr = "{}={}&".format(hdr, content)

        return parmstr

    def _msg_to_mailto(self, msg, attachments=[]):
        mailto = "mailto:"
        mailto += self._uq(''.join(msg["to"].splitlines()))
        mailto += "?"

        for hdr in ["subject", "cc", "bcc"]:
            mailto += self._get_headerparam(hdr, msg)

        if msg.is_multipart():
            return mailto.rstrip('?&')

        if attachments:
            attstrlist = ['attach={}&'.format(self._uq(os.path.abspath(a)))
                          for a in attachments if self._check_attachable(a)]
            if attstrlist:
                mailto += ''.join(attstrlist)

        body = msg.get_payload(decode=True).decode(errors='replace')
        if body:
            try_mailto = mailto + 'body=' + self._uq(body)
            while len(try_mailto) > MAX_ARG_LENGTH:
                body = body[:-2000]
                if not body:
                    # should never happen
                    raise BadMessage('unreasonable message')
                body += '\n\n[ MAILBODY EXCEEDED REASONABLE LENGTH, OUTPUT TRUNCATED ]'
                try_mailto = mailto + 'body=' + self._uq(body)
            mailto = try_mailto

        return mailto.rstrip('?&')

    def get_send_command(self, filename, attachments=[]):
        with open(filename, 'r') as fp:
            message = email.message_from_file(fp, policy=email.policy.compat32)

        cmd = '{} "{}"'.format(self.executable, self._msg_to_mailto(message, attachments))
        return cmd


MUA = {
    'mutt': Mutt('mutt -H'),
    'neomutt': Mutt('neomutt -H'),
    'mh': Mua('/usr/bin/mh/comp -use -file'),
    'nmh': Mua('/usr/bin/mh/comp -use -file'),
    'gnus': Gnus(),
    'claws-mail': Mua('claws-mail --compose-from-file', needs_terminal=False),
    'alpine': Mailto('alpine -url'),
    'pine': Mailto('pine -url'),
    'evolution': Mailto('evolution', needs_terminal=False),
    'kmail': Mailto('kmail', needs_terminal=False),
    'thunderbird': Mailto('thunderbird -compose', needs_terminal=False),
    'sylpheed': Mailto('sylpheed --compose', needs_terminal=False),
    'xdg-email': Mailto('xdg-email', needs_terminal=False),
}

MUA_NEEDS_DISPLAY = [
    'claws-mail',
    'evolution',
    'kmail',
    'thunderbird',
    'sylpheed',
    # 'xdg-email', # not if MAILER is set
]


def mua_is_supported(mua):
    """
    Check if the mua is supported by reportbug

    Parameters
    ----------
    mua : Mua instance or str
        mail user agent

    Returns
    -------
    bool
        True if supported, otherwise False
    """
    if isinstance(mua, Mua) or mua in MUA.keys():
        return True
    return False


def mua_exists(mua):
    """
    Check if the mua is available on the system

    Parameters
    ----------
    mua : Mua instance or str
        mail user agent

    Returns
    -------
    bool
        True if available, otherwise False
    """
    if not isinstance(mua, Mua):
        try:
            mua = MUA[mua]
        except KeyError:
            return False
    if shutil.which(mua.executable):
        return True
    return False


def mua_can_run(mua):
    """
    Check if the mua can run in the current environment

    Some MUAs need a graphical environment and cannot run on a text
    console.

    Parameters
    ----------
    mua : Mua instance or str
        mail user agent

    Returns
    -------
    bool
        True if it can run, otherwise False
    """
    if ('DISPLAY' in os.environ
            or 'WAYLAND_DISPLAY' in os.environ):
        return True
    if isinstance(mua, Mua):
        mua = mua.executable
    if mua in MUA_NEEDS_DISPLAY:
        return False
    if mua == 'xdg-email' and 'MAILER' not in os.environ:
        return False
    return True
