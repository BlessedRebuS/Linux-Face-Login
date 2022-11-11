# a graphical (GTK+) user interface
#   Written by Luca Bruno <lethalman88@gmail.com>
#   Based on gnome-reportbug work done by Philipp Kern <pkern@debian.org>
#   Copyright (C) 2006 Philipp Kern
#   Copyright (C) 2008-2009 Luca Bruno
#   Copyright (C) 2021-2022 Takahide Nojima
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

from reportbug.exceptions import UINotImportable

import os
if not ('DISPLAY' in os.environ or 'WAYLAND_DISPLAY' in os.environ):
    raise UINotImportable('No graphical display detected, falling back to text UI.')

try:
    import gi

    gi.require_version('GLib', '2.0')
    from gi.repository import GLib

    gi.require_version('Pango', '1.0')
    from gi.repository import Pango

    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk

    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf

    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource

    gi.require_foreign('cairo')
except ImportError:
    raise UINotImportable('Please install the reportbug-gtk package to use this interface.')

import sys
import re
import traceback
from queue import Queue
import threading
import textwrap
import signal

from reportbug.exceptions import NoPackage, NoBugs, QuertBTSError
from reportbug import debbugs
from reportbug.urlutils import launch_browser

ISATTY = True
DEBIAN_LOGO = "/usr/share/pixmaps/debian-logo.png"

global application, assistant, report_message, reportbug_context, ui_context
global Vte

gtkspellcheck = None


# Utilities


def _describe_context(context):
    if context == ui_context:
        return '<MainContext of UI thread>'
    elif context == reportbug_context:
        return '<MainContext of reportbug thread>'
    else:
        return repr(context)


def _assert_context(expected):
    really = GLib.MainContext.ref_thread_default()

    # This compares by pointer value of the underlying GMainContext
    if really != expected:
        raise AssertionError('Function should be called in %s but was called in %s' %
                             (_describe_context(expected), _describe_context(really)))

    if not really.is_owner():
        raise AssertionError('Function should be called with %s acquired')


def _exit():
    os.kill(os.getpid(), signal.SIGINT)


def highlight(s):
    return '<b>%s</b>' % s


re_markup_free = re.compile("<.*?>")


def markup_free(s):
    return re_markup_free.sub("", s)


def ask_free(s):
    s = s.strip()
    if s[-1] in ('?', ':'):
        return s[:-1]
    return s


def create_scrollable(widget, with_viewport=False):
    _assert_context(ui_context)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    if with_viewport:
        scrolled.add_with_viewport(widget)
    else:
        scrolled.add(widget)
    return scrolled


def info_dialog(message):
    _assert_context(ui_context)
    dialog = Gtk.MessageDialog(assistant, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                               Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, message)
    dialog.connect('response', lambda d, *args: d.destroy())
    dialog.set_title('Reportbug')
    dialog.show_all()


class CustomDialog(Gtk.Dialog):
    def __init__(self, stock_image, message, buttons, *args, **kwargs):
        _assert_context(ui_context)
        Gtk.Dialog.__init__(self, "Reportbug", assistant,
                            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            buttons)
        # Try following the HIG
        self.set_default_response(buttons[-1])  # this is the response of the last button
        self.set_border_width(5)

        vbox = Gtk.VBox(spacing=10)
        vbox.set_border_width(6)
        self.vbox.pack_start(vbox, True, True, 0)

        # The header image + label
        hbox = Gtk.HBox(spacing=10)
        vbox.pack_start(hbox, False, True, 0)

        # TODO: deprecated, new code is meant to set the halign/valign/margin
        # properties on the child widget instead. Also this is probably
        # useless without having a child widget?
        align = Gtk.Alignment(xalign=0.5, yalign=0.5, xscale=1.0, yscale=1.0)
        hbox.pack_start(align, False, True, 0)

        image = Gtk.Image.new_from_stock(stock_image, Gtk.IconSize.DIALOG)
        hbox.pack_start(image, True, True, 0)

        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.FILL)
        label.set_selectable(True)
        label.set_property("can-focus", False)
        hbox.pack_start(label, False, True, 0)

        self.setup_dialog(vbox, *args, **kwargs)


class InputStringDialog(CustomDialog):
    def __init__(self, message):
        _assert_context(ui_context)
        CustomDialog.__init__(self, Gtk.STOCK_DIALOG_INFO, message,
                              (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                               Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT))

    def setup_dialog(self, vbox):
        _assert_context(ui_context)
        self.entry = Gtk.Entry()
        vbox.pack_start(self.entry, False, True, 0)

    def get_value(self):
        _assert_context(ui_context)
        return self.entry.get_text()


class ExceptionDialog(CustomDialog):
    # Register an exception hook to display an error when the GUI breaks
    @classmethod
    def create_excepthook(cls, oldhook):
        _assert_context(reportbug_context)

        def excepthook(exctype, value, tb):
            # OK to call from any thread
            if oldhook:
                oldhook(exctype, value, tb)
            application.run_once_in_main_thread(cls.start_dialog,
                                                ''.join(traceback.format_exception(exctype, value, tb)))

        return excepthook

    @classmethod
    def start_dialog(cls, tb):
        _assert_context(ui_context)
        try:
            dialog = cls(tb)
            dialog.show_all()
        except Exception:
            _exit()

    def __init__(self, tb):
        _assert_context(ui_context)
        CustomDialog.__init__(self, Gtk.STOCK_DIALOG_ERROR, "An error has occurred while doing an operation in Reportbug.\nPlease report the bug.", (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE), tb)

    def setup_dialog(self, vbox, tb):
        # The traceback
        expander = Gtk.Expander.new_with_mnemonic("More details")
        vbox.pack_start(expander, True, True, 0)

        view = Gtk.TextView()
        view.set_editable(False)
        view.get_buffer().set_text(tb)
        scrolled = create_scrollable(view)
        expander.add(scrolled)

        self.connect('response', self.on_response)

    def on_response(self, dialog, res):
        _assert_context(ui_context)
        _exit()


class ReportViewerDialog(Gtk.Dialog):
    def __init__(self, message):
        _assert_context(ui_context)
        Gtk.Dialog.__init__(self, "Reportbug", assistant,
                            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_COPY, Gtk.ResponseType.APPLY,
                             Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        self.message = message

        self.set_default_size(400, 400)
        self.set_default_response(Gtk.ResponseType.CLOSE)
        self.set_border_width(6)
        self.connect('response', self.on_response)

        view = Gtk.TextView()
        view.get_buffer().set_text(self.message)
        self.vbox.pack_start(create_scrollable(view), True, True, 0)

        self.show_all()

    def on_response(self, dialog, res):
        _assert_context(ui_context)
        # ok Gtk.ResponseType.APPLY is ugly for Gtk.STOCK_COPY, but who cares?
        # maybe adding it as a secondary button or such is better
        if res == Gtk.ResponseType.APPLY:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.message, -1)
        else:
            self.destroy()


# BTS
class Bug(object):
    """Encapsulate a bug report for the GTK+ UI"""
    def __init__(self, bug):
        self.id = bug.bug_num
        self.tag = ', '.join(bug.tags)
        self.package = bug.package
        self.status = bug.pending
        self.reporter = bug.originator
        self.date = bug.date
        self.severity = bug.severity
        self.version = ', '.join(bug.found_versions)
        self.filed_date = bug.date
        self.modified_date = bug.log_modified
        self.info = bug.subject

    def __iter__(self):
        yield self.id
        yield self.tag
        yield self.package
        yield self.info
        yield self.status
        yield self.reporter
        yield self.date
        yield self.severity
        yield self.version
        yield self.filed_date
        yield self.modified_date


class BugReport(object):
    def __init__(self, message):
        lines = message.split('\n')
        i = 0

        self.headers = []
        while i < len(lines):
            line = lines[i]
            i += 1
            if not line.strip():
                break
            self.headers.append(line)
            if line.startswith('Subject:'):
                break

        store = 0
        info = []
        has_other = False
        while i < len(lines):
            line = lines[i]
            info.append(line)
            i += 1
            if not line.strip():
                if store < 2:
                    store += 1
                continue
            if store == 2 and (line == '-- Package-specific info:' or line == '-- System Information:'):
                has_other = True
                break
            store = 0

        if has_other:
            self.original_info = '\n'.join(info[:-3])
            self.others = '\n'.join(lines[i - 1:])
        else:
            self.original_info = '\n'.join(info[:-2])
            self.others = ''

    def get_others(self):
        return self.others

    def get_original_info(self):
        return self.original_info

    def get_subject(self):
        for header in self.headers:
            if 'Subject' in header:
                return header[len('Subject: '):]

    def set_subject(self, subject):
        for i in range(len(self.headers)):
            if 'Subject' in self.headers[i]:
                self.headers[i] = 'Subject: ' + subject
                break

    def wrap_bug_body(self, msg, width=79, break_long_words=False):
        """Wrap every line in the message, except the pseudoheaders"""

        # resulting body text
        body = ''
        phead = True
        for line in msg.splitlines():
            if phead:
                body += line + '\n'
                if not line.strip():
                    phead = False
                continue

            # wrap long lines, it returns a list of "sub-lines"
            tmp = textwrap.wrap(line, width=width,
                                break_long_words=break_long_words)
            body += '\n'.join(tmp) + '\n'

        return body

    def create_message(self, info):
        if self.others:
            return '{}\n{}\n\n{}'.format('\n'.join(self.headers), self.wrap_bug_body(info), self.others)

        return '{}\n{}\n'.format('\n'.join(self.headers), self.wrap_bug_body(info))


# BTS GUI
class BugPage(Gtk.EventBox, threading.Thread):
    def __init__(self, assistant, dialog, number, queryonly, bts, mirrors, http_proxy, timeout, archived):
        _assert_context(ui_context)
        threading.Thread.__init__(self)
        Gtk.EventBox.__init__(self)
        self.setDaemon(True)
        self.context = GLib.MainContext()

        self.dialog = dialog
        self.assistant = assistant
        self.application = self.assistant.application
        self.number = number
        self.queryonly = queryonly
        self.bts = bts
        self.mirrors = mirrors
        self.http_proxy = http_proxy
        self.timeout = timeout
        self.archived = archived

        self.bug_status = None

        vbox = Gtk.VBox(spacing=12)
        vbox.pack_start(Gtk.Label(label="Retrieving bug information."), False, True, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_pulse_step(0.01)
        vbox.pack_start(self.progress, False, True, 0)

        self.add(vbox)

    def run(self):
        if not self.context.acquire():
            # should be impossible
            raise AssertionError('Could not acquire my own main-context')
        self.context.push_thread_default()

        # Start the progress bar
        GLib.timeout_add(10, self.pulse)

        info = debbugs.get_report(int(self.number), self.timeout,
                                  self.bts, mirrors=self.mirrors,
                                  http_proxy=self.http_proxy, archived=self.archived)
        if not info:
            self.application.run_once_in_main_thread(self.not_found)
        else:
            self.bug_status = info[0]
            self.application.run_once_in_main_thread(self.found, info)

    def drop_progressbar(self):
        _assert_context(ui_context)
        child = self.get_child()
        if child:
            self.remove(child)
            child.unparent()

    def pulse(self):
        _assert_context(ui_context)
        self.progress.pulse()
        return self.is_alive()

    def not_found(self):
        _assert_context(ui_context)
        self.drop_progressbar()
        self.add(Gtk.Label(label="The bug can't be fetched or it doesn't exist."))
        self.show_all()

    def found(self, info):
        _assert_context(ui_context)
        self.drop_progressbar()
        desc = info[0].subject
        bodies = info[1]
        vbox = Gtk.VBox(spacing=12)
        vbox.set_border_width(12)
        label = Gtk.Label(label='Description: ' + desc)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.FILL)
        vbox.pack_start(label, False, True, 0)

        views = Gtk.VBox()
        odd = False
        for body in bodies:
            view = Gtk.TextView()
            view.set_editable(False)
            # truncate excessively long messages
            # without the GTK interface can crash, e.g., reportbug -u gtk -N 711404 crashes
            # TODO: fix this properly
            view.get_buffer().set_text(body[:10000])
            if odd:
                view.set_state_flags(Gtk.StateFlags.PRELIGHT, False)
            views.pack_start(view, False, True, 0)
            odd = not odd
        scrolled = create_scrollable(views, True)
        vbox.pack_start(scrolled, True, True, 0)

        bbox = Gtk.HButtonBox()
        button = Gtk.Button(label="Open in browser")
        button.connect('clicked', self.on_open_browser)
        bbox.pack_start(button, True, True, 0)
        if not self.queryonly:
            button = Gtk.Button(label="Reply")
            button.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_EDIT, Gtk.IconSize.BUTTON))
            button.connect('clicked', self.on_reply)
            bbox.pack_start(button, True, True, 0)
        vbox.pack_start(bbox, False, True, 0)

        self.add(vbox)
        self.show_all()

    def on_open_browser(self, button):
        _assert_context(ui_context)
        launch_browser(debbugs.get_report_url(self.bts, int(self.number), self.archived))

    def on_reply(self, button):
        _assert_context(ui_context)
        # Return the bug number to reportbug
        self.application.set_next_value(self.bug_status)
        # Forward the assistant to the progress bar
        self.assistant.forward_page()
        # Though we're only a page, we are authorized to destroy our parent :)
        # This would be better handled connecting externally to self.reply_button
        try:
            self.dialog.destroy()
        except AttributeError:
            pass


class BugsDialog(Gtk.Dialog):
    def __init__(self, assistant, queryonly):
        _assert_context(ui_context)
        Gtk.Dialog.__init__(self, "Reportbug: bug information", assistant,
                            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        self.assistant = assistant
        self.queryonly = queryonly
        self.application = assistant.application
        self.notebook = Gtk.Notebook()
        self.vbox.pack_start(self.notebook, True, True, 0)
        self.connect('response', self.on_response)
        self.set_default_size(600, 600)

    def on_response(self, *args):
        self.destroy()

    def show_bug(self, number, *args):
        page = BugPage(self.assistant, self, number, self.queryonly, *args)
        self.notebook.append_page(page, Gtk.Label(label=number))
        page.start()


# Application
class ReportbugApplication(threading.Thread):
    def __init__(self):
        _assert_context(reportbug_context)
        threading.Thread.__init__(self)
        self.setDaemon(True)

        self.queue = Queue()
        self.next_value = None

    def run(self):
        if not ui_context.acquire():
            # should be impossible
            raise AssertionError('Could not acquire UI context')
        ui_context.push_thread_default()

        Gtk.main()

    def get_last_value(self):
        _assert_context(reportbug_context)
        return self.queue.get()

    def put_next_value(self):
        _assert_context(ui_context)
        self.queue.put(self.next_value)
        self.next_value = None

    def set_next_value(self, value):
        _assert_context(ui_context)
        self.next_value = value

    def run_once_in_main_thread(self, func, *args, **kwargs):
        # OK to call from any thread

        def callback():
            _assert_context(ui_context)
            func(*args, **kwargs)
            return False

        GLib.idle_add(callback)

    def call_in_main_thread(self, func, *args, **kwargs):
        # OK to call from any thread

        def callback():
            _assert_context(ui_context)
            try:
                ret = func(*args, **kwargs)
            except BaseException as e:
                self.set_next_value(e)
            else:
                self.set_next_value(ret)

            self.put_next_value()
            return False

        GLib.idle_add(callback)
        ret = self.get_last_value()

        if isinstance(ret, BaseException):
            raise ret
        else:
            return ret


# Connection with reportbug
# Synchronize "pipe" with reportbug
class SyncReturn(RuntimeError):
    def __init__(self, result):
        _assert_context(reportbug_context)
        RuntimeError.__init__(self, result)
        self.result = result


class ReportbugConnector(object):
    def execute_operation(self, *args, **kwargs):
        _assert_context(ui_context)
        pass

    # Executed in sync with reportbug. raise SyncResult(value) to directly return to reportbug
    # Returns args and kwargs to pass to execute_operation
    def sync_pre_operation(cls, *args, **kwargs):
        _assert_context(reportbug_context)
        return args, kwargs


# Assistant
class Page(ReportbugConnector):
    next_page_num = 0
    page_type = Gtk.AssistantPageType.CONTENT
    default_complete = False
    side_image = DEBIAN_LOGO
    WARNING_COLOR = Gdk.color_parse("#fff8ae")

    def __init__(self, assistant):
        _assert_context(ui_context)
        self.assistant = assistant
        self.application = assistant.application
        self.widget = self.create_widget()
        self.widget.page = self
        self.widget.set_border_width(6)
        self.widget.show_all()
        self.page_num = Page.next_page_num

    def execute_operation(self, *args, **kwargs):
        _assert_context(ui_context)
        self.switch_in()
        self.connect_signals()
        self.empty_ok = kwargs.pop('empty_ok', False)
        self.presubj = kwargs.pop('presubj', False)
        self.execute(*args, **kwargs)
        self.assistant.show()
        self.setup_focus()

    def connect_signals(self):
        _assert_context(ui_context)

    def set_page_complete(self, complete):
        _assert_context(ui_context)
        self.assistant.set_page_complete(self.widget, complete)

    def set_page_type(self, type):
        _assert_context(ui_context)
        self.assistant.set_page_type(self.widget, type)

    def set_page_title(self, title):
        _assert_context(ui_context)
        if title:
            self.assistant.set_page_title(self.widget, title)

    # The user will see this as next page
    def switch_in(self):
        _assert_context(ui_context)
        Page.next_page_num += 1
        self.assistant.insert_page(self.widget, self.page_num)
        self.set_page_complete(self.default_complete)
        self.set_page_type(self.page_type)
        self.set_page_title("Reportbug")
        self.assistant.set_page_side_image(self.widget, GdkPixbuf.Pixbuf.new_from_file(self.side_image))
        self.assistant.set_next_page(self)
        # reportbug cannot usefully go back
        self.assistant.commit()

    # Setup keyboard focus in the page
    def setup_focus(self):
        _assert_context(ui_context)
        self.widget.grab_focus()

    # Forward page when a widget is activated(e.g. GtkEntry) only if page is complete
    def activate_forward(self, *args):
        _assert_context(ui_context)
        if self.assistant.get_page_complete(self.widget):
            self.assistant.forward_page()

    # The user forwarded the assistant to see the next page
    def switch_out(self):
        _assert_context(ui_context)

    def is_valid(self, value):
        _assert_context(ui_context)

        if self.empty_ok:
            return True
        else:
            return bool(value)

    def validate(self, *args, **kwargs):
        _assert_context(ui_context)

        value = self.get_value()
        if self.is_valid(value):
            self.application.set_next_value(value)
            self.set_page_complete(True)
        else:
            self.set_page_complete(False)


class IntroPage(Page):
    page_type = Gtk.AssistantPageType.INTRO
    default_complete = True

    def create_widget(self):
        _assert_context(ui_context)

        vbox = Gtk.VBox(spacing=24)

        label = Gtk.Label(label="""
<b>Reportbug</b> is a tool designed to make the reporting of bugs in Debian and derived distributions relatively painless.

This wizard will guide you through the bug reporting process step by step.

<b>Note:</b> bug reports are publicly archived (including the email address of the submitter).""")
        label.set_use_markup(True)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.FILL)
        vbox.pack_start(label, False, True, 0)

        link = Gtk.LinkButton.new_with_label("https://salsa.debian.org/reportbug-team/reportbug",
                                             "Homepage of reportbug project")
        vbox.pack_start(link, False, True, 0)
        return vbox


class GetStringPage(Page):
    def setup_focus(self):
        _assert_context(ui_context)
        self.entry.grab_focus()

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=12)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        self.label.set_selectable(True)
        self.label.set_property("can-focus", False)
        self.entry = Gtk.Entry()
        vbox.pack_start(self.label, False, True, 0)
        vbox.pack_start(self.entry, False, True, 0)
        return vbox

    def connect_signals(self):
        _assert_context(ui_context)
        self.entry.connect('changed', self.validate)
        self.entry.connect('activate', self.activate_forward)

    def get_value(self):
        _assert_context(ui_context)
        return self.entry.get_text()

    def execute(self, prompt, options=None, force_prompt=False, default=''):
        _assert_context(ui_context)
        # Hackish: remove the text needed for textual UIs...
        GLib.idle_add(self.label.set_text, prompt.replace('(enter Ctrl+c to exit reportbug without reporting a bug)', ''))
        self.entry.set_text(default)

        if options:
            options.sort()
            completion = Gtk.EntryCompletion()
            model = Gtk.ListStore(str)
            for option in options:
                model.append([option])
            completion.set_model(model)
            completion.set_inline_selection(True)
            completion.set_text_column(0)
            self.entry.set_completion(completion)
        else:
            self.completion = None

        self.validate()


class GetPasswordPage(GetStringPage):
    def create_widget(self):
        _assert_context(ui_context)
        widget = GetStringPage.create_widget(self)
        self.entry.set_visibility(False)
        return widget


class GetMultilinePage(Page):
    def setup_focus(self):
        _assert_context(ui_context)
        self.view.grab_focus()

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=12)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        self.label.set_selectable(True)
        self.label.set_property("can-focus", False)
        vbox.pack_start(self.label, False, True, 0)

        self.view = Gtk.TextView()
        self.buffer = self.view.get_buffer()
        scrolled = create_scrollable(self.view)
        vbox.pack_start(scrolled, True, True, 0)
        return vbox

    def connect_signals(self):
        _assert_context(ui_context)
        self.buffer.connect('changed', self.validate)

    def get_value(self):
        _assert_context(ui_context)
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)
        return text.split('\n')

    def execute(self, prompt):
        _assert_context(ui_context)
        self.empty_ok = True
        # The result must be iterable for reportbug even if it's empty and not modified
        GLib.idle_add(self.label.set_text, prompt)
        self.buffer.set_text("")
        self.buffer.emit('changed')


class TreePage(Page):
    value_column = None

    def __init__(self, *args, **kwargs):
        _assert_context(ui_context)
        Page.__init__(self, *args, **kwargs)
        self.selection = self.view.get_selection()

    def setup_focus(self):
        _assert_context(ui_context)
        self.view.grab_focus()

    def connect_signals(self):
        _assert_context(ui_context)
        self.selection.connect('changed', self.validate)

    def get_value(self):
        _assert_context(ui_context)
        model, paths = self.selection.get_selected_rows()
        multiple = self.selection.get_mode() == Gtk.SelectionMode.MULTIPLE
        result = []
        for path in paths:
            value = model.get_value(model.get_iter(path), self.value_column)
            if value is not None:
                result.append(markup_free(value))
        if result and not multiple:
            return result[0]
        return result


class GetListPage(TreePage):
    value_column = 0

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=12)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        vbox.pack_start(self.label, False, True, 0)

        hbox = Gtk.HBox(spacing=6)

        self.view = Gtk.TreeView()
        self.view.set_rules_hint(True)
        self.view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        scrolled = create_scrollable(self.view)
        hbox.pack_start(scrolled, True, True, 0)

        bbox = Gtk.VButtonBox()
        bbox.set_spacing(6)
        bbox.set_layout(Gtk.ButtonBoxStyle.START)
        button = Gtk.Button(stock=Gtk.STOCK_ADD)
        button.connect('clicked', self.on_add)
        bbox.pack_start(button, False, True, 0)
        button = Gtk.Button(stock=Gtk.STOCK_REMOVE)
        button.connect('clicked', self.on_remove)
        bbox.pack_start(button, False, True, 0)
        hbox.pack_start(bbox, False, True, 0)

        vbox.pack_start(hbox, True, True, 0)
        return vbox

    def get_value(self):
        _assert_context(ui_context)
        values = []
        for row in self.model:
            values.append(row[self.value_column])
        return values

    def on_add(self, button):
        _assert_context(ui_context)
        dialog = InputStringDialog("Add a new item to the list")
        dialog.show_all()
        dialog.connect('response', self.on_add_dialog_response)

    def on_add_dialog_response(self, dialog, res):
        _assert_context(ui_context)
        if res == Gtk.ResponseType.ACCEPT:
            self.model.append([dialog.get_value()])
            self.validate()
        dialog.destroy()

    def on_remove(self, button):
        _assert_context(ui_context)
        model, paths = self.selection.get_selected_rows()
        # We need to transform them to iters, since paths change when removing rows
        iters = []
        for path in paths:
            iters.append(self.model.get_iter(path))
        for iter in iters:
            self.model.remove(iter)
        self.validate()

    def execute(self, prompt):
        _assert_context(ui_context)
        self.empty_ok = True

        GLib.idle_add(self.label.set_text, prompt)

        self.model = Gtk.ListStore(str)
        self.model.connect('row-changed', self.validate)
        self.view.set_model(self.model)

        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        self.view.append_column(Gtk.TreeViewColumn('Item', Gtk.CellRendererText(), text=0))


class MenuPage(Page):
    value_column = 1

    def __init__(self, *args, **kwargs):
        _assert_context(ui_context)
        Page.__init__(self, *args, **kwargs)

    def setup_focus(self):
        _assert_context(ui_context)
        self.view.grab_focus()

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=12)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        vbox.pack_start(self.label, False, True, 0)
        self.view = Gtk.TreeView()
        style_context = self.view.get_style_context()
        style_context.add_class(Gtk.STYLE_CLASS_CELL)
        # FixMe:
        #  Replace using Gtk.StyleContext.get_background_color() with an another way,
        # because it has been deprecated.
        #  At this moment,one of choice is using
        # the Gtk.StyleContext.get_property("background-color"...),but it is
        # useless, because it has a bug shown in https://gitlab.gnome.org/GNOME/pygobject/-/issues/119
        self.background = dict(
            selected=self._rgba_to_string(style_context.get_background_color(Gtk.StateFlags.SELECTED)),
            normal=self._rgba_to_string(style_context.get_background_color(Gtk.StateFlags.NORMAL)))
        self.foreground = dict(
            selected=self._rgba_to_string(style_context.get_color(Gtk.StateFlags.SELECTED)),
            normal=self._rgba_to_string(style_context.get_color(Gtk.StateFlags.NORMAL)))
        self.selection = self.view.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.NONE)
        self.view.set_activate_on_single_click(True)
        self.chkbox = Gtk.CellRendererToggle()
        scrolled = create_scrollable(self.view)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.show_all()
        return vbox

    def connect_signals(self):
        _assert_context(ui_context)
        Page.connect_signals(self)
        self.view.connect('row-activated', self.on_toggle)

    def get_value(self):
        _assert_context(ui_context)
        result = []
        for row in self.model:
            if row[0]:
                result.append(markup_free(row[self.value_column]))
        if len(result) > 0 and not self.multiple:
            return result[0]
        return result

    def _rgba_to_string(self, rgba):
        return '#{:02x}{:02x}{:02x}'.format(int(rgba.red * 255),
                                            int(rgba.green * 255),
                                            int(rgba.blue * 255))

    def _is_suitable_radio_button(self):
        return not self.multiple and not self.empty_ok

    def execute(self, par, options, prompt, default=None, any_ok=False,
                order=None, extras=None, multiple=False):
        _assert_context(ui_context)
        GLib.idle_add(self.label.set_text, par)
        self.model = Gtk.ListStore(bool, str, str)
        self.view.set_model(self.model)
        self.multiple = multiple
        self.chkbox.set_radio(self._is_suitable_radio_button())
        column = Gtk.TreeViewColumn('Sel', self.chkbox, active=0)
        column.set_cell_data_func(self.chkbox, self.on_cell_func)
        self.view.append_column(column)
        cell_text = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Option', cell_text, markup=1)
        column.set_cell_data_func(cell_text, self.on_cell_func)
        self.view.append_column(column)
        rend = Gtk.CellRendererText()
        rend.set_property('wrap-mode', Pango.WrapMode.WORD)
        rend.set_property('wrap-width', 500)
        desc_column = Gtk.TreeViewColumn('Description', rend, text=2)
        desc_column.set_cell_data_func(rend, self.on_cell_func)
        self.view.append_column(desc_column)

        default_iter = None
        # here below, 'text' is the value of the description of the item, but
        # written all on a single line, it will be wrapped by the list settings
        if isinstance(options, dict):
            if order:
                for option in order:
                    if option in options:
                        text = ' '.join(options[option].split())
                        iter = self.model.append([False, highlight(option), text])
                        if option == default:
                            default_iter = iter
            for option, desc in options.items():
                if not order or option not in order:
                    text = ' '.join(desc.split())
                    iter = self.model.append([False, highlight(option), text])
                    if option == default:
                        default_iter = iter
        else:
            for row in options:
                text = ' '.join(row[1].split())
                iter = self.model.append([False, highlight(row[0]), text])
                if row[0] == default:
                    default_iter = iter

        if default_iter:
            self.model.set_value(default_iter, 0, True)

        self.validate()

    def on_toggle(self, widget, path, data):
        if not self.multiple:
            selected_path = Gtk.TreePath(path)
            for row in self.model:
                if row.path == selected_path:
                    if not self.empty_ok:
                        row[0] = True
                    else:
                        row[0] = not row[0]
                else:
                    row[0] = False
        else:
            self.model[path][0] = not self.model[path][0]
        self.validate()

    def on_cell_func(self, column, cell, model, it, data):
        if model.get_value(it, 0):
            if isinstance(cell, Gtk.CellRendererToggle):
                cell.set_property("cell-background", self.background['selected'])
            else:
                cell.set_property("background", self.background['selected'])
                cell.set_property("foreground", self.foreground['selected'])
        else:
            if isinstance(cell, Gtk.CellRendererToggle):
                cell.set_property("cell-background", self.background['normal'])
            else:
                cell.set_property("background", self.background['normal'])
                cell.set_property("foreground", self.foreground['normal'])


class HandleBTSQueryPage(TreePage):
    default_complete = True
    value_column = 0

    def sync_pre_operation(self, package, bts, timeout, mirrors=None, http_proxy="", queryonly=False, screen=None,
                           archived='no', source=False, title=None,
                           version=None, buglist=None, mbox_reader_cmd=None, latest_first=False):
        _assert_context(reportbug_context)
        self.bts = bts
        self.mirrors = mirrors
        self.http_proxy = http_proxy
        self.timeout = timeout
        self.archived = archived

        self.queryonly = queryonly
        if queryonly:
            self.page_type = Gtk.AssistantPageType.CONFIRM

        sysinfo = debbugs.SYSTEMS[bts]
        root = sysinfo.get('btsroot')
        if not root:
            # do we need to make a dialog for this?
            raise SyncReturn(None)

        if isinstance(package, str):
            pkgname = package
            if source:
                pkgname += '(source)'

            progress_label = 'Querying %s bug tracking system for reports on %s' % (debbugs.SYSTEMS[bts]['name'], pkgname)
        else:
            progress_label = 'Querying %s bug tracking system for reports %s' % (debbugs.SYSTEMS[bts]['name'], ' '.join([str(x) for x in package]))

        self.application.run_once_in_main_thread(self.assistant.set_progress_label, progress_label)

        try:
            (count, sectitle, hierarchy) = debbugs.get_reports(
                package, timeout, bts, mirrors=mirrors, version=version,
                http_proxy=http_proxy, archived=archived, source=source)
        except Exception as e:
            errmsg = 'Unable to connect to %s BTS (error: "%s"); ' % (debbugs.SYSTEMS[bts]['name'], repr(e))
            raise QuertBTSError(errmsg)

        try:
            if not count:
                if hierarchy is None:
                    raise NoPackage
                else:
                    raise NoBugs
            else:
                if count > 1:
                    sectitle = '%d bug reports found' % (count,)
                else:
                    sectitle = 'One bug report found'

                report = []
                for category, bugs in hierarchy:
                    buglist = sorted(bugs, key=lambda b: b.bug_num, reverse=latest_first)
                    report.append((category, list(map(Bug, buglist))))

                return(report, sectitle), {}

        except NoPackage:
            raise NoPackage

        raise SyncReturn(None)

    def setup_focus(self):
        _assert_context(ui_context)
        self.entry.grab_focus()

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=6)
        self.label = Gtk.Label(label="List of bugs. Select a bug to retrieve and submit more information.")
        vbox.pack_start(self.label, False, True, 6)

        hbox = Gtk.HBox(spacing=6)
        label = Gtk.Label(label="Filter:")
        hbox.pack_start(label, False, True, 0)
        self.entry = Gtk.Entry()
        hbox.pack_start(self.entry, True, True, 0)
        button = Gtk.Button()
        button.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_CLEAR, Gtk.IconSize.MENU))
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect('clicked', self.on_filter_clear)
        hbox.pack_start(button, False, True, 0)
        vbox.pack_start(hbox, False, True, 0)

        self.view = Gtk.TreeView()
        self.view.set_rules_hint(True)
        scrolled = create_scrollable(self.view)
        self.columns = ['ID', 'Tag', 'Package', 'Description', 'Status', 'Submitter', 'Date', 'Severity', 'Version',
                        'Filed date', 'Modified date']
        for col in zip(self.columns, list(range(len(self.columns)))):
            column = Gtk.TreeViewColumn(col[0], Gtk.CellRendererText(), text=col[1])
            column.set_reorderable(True)
            self.view.append_column(column)
        vbox.pack_start(scrolled, True, True, 0)

        button = Gtk.Button(label="Retrieve and submit bug information")
        button.set_image(Gtk.Image.new_from_stock(Gtk.STOCK_INFO, Gtk.IconSize.BUTTON))
        button.connect('clicked', self.on_retrieve_info)
        vbox.pack_start(button, False, True, 0)
        return vbox

    def connect_signals(self):
        _assert_context(ui_context)
        TreePage.connect_signals(self)
        self.view.connect('row-activated', self.on_retrieve_info)
        self.entry.connect('changed', self.on_filter_changed)

    def on_filter_clear(self, button):
        _assert_context(ui_context)
        self.entry.set_text("")

    def on_filter_changed(self, entry):
        _assert_context(ui_context)
        self.model.filter_text = entry.get_text().lower()
        self.filter.refilter()

    def on_retrieve_info(self, *args):
        _assert_context(ui_context)
        bug_ids = TreePage.get_value(self)
        if not bug_ids:
            info_dialog("Please select one or more bugs")
            return

        dialog = BugsDialog(self.assistant, self.queryonly)
        for id in bug_ids:
            dialog.show_bug(id, self.bts, self.mirrors, self.http_proxy, self.timeout, self.archived)
        dialog.show_all()

    def is_valid(self, value):
        _assert_context(ui_context)
        return True

    def get_value(self):
        _assert_context(ui_context)
        # The value returned to reportbug doesn't depend by a selection, but by the dialog of a bug
        return None

    def match_filter(self, iter):
        _assert_context(ui_context)
        # Flatten the columns into a single string
        text = ""
        for col in range(len(self.columns)):
            value = self.model.get_value(iter, col)
            if value:
                text += self.model.get_value(iter, col) + " "

        text = text.lower()
        # Tokens shouldn't be adjacent by default
        for token in self.model.filter_text.split(' '):
            if token in text:
                return True
        return False

    def filter_visible_func(self, model, iter, user_data=None):
        _assert_context(ui_context)
        matches = self.match_filter(iter)
        if not self.model.iter_parent(iter) and not matches:
            # If no children are visible, hide it
            it = model.iter_children(iter)
            while it:
                if self.match_filter(it):
                    return True
                it = model.iter_next(it)
            return False

        return matches

    def execute(self, buglist, sectitle):
        _assert_context(ui_context)
        GLib.idle_add(self.label.set_text, "%s. Double-click a bug to retrieve and submit more information, or press 'Next' if none match." % sectitle)

        self.model = Gtk.TreeStore(*([str] * len(self.columns)))
        for category in buglist:
            row = [None] * len(self.columns)
            row[3] = category[0]
            iter = self.model.append(None, row)
            for bug in category[1]:
                self.model.append(iter, list(map(str, bug)))

        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        self.model.filter_text = ""
        self.filter = self.model.filter_new()
        self.filter.set_visible_func(self.filter_visible_func)
        self.view.set_model(self.filter)


class ShowReportPage(Page):
    default_complete = True

    def create_widget(self):
        _assert_context(ui_context)
        self.page = BugPage(self.assistant, None, None, None, None, None, None, None, None)
        return self.page

    def get_value(self):
        _assert_context(ui_context)
        return None

    def is_valid(self, value):
        _assert_context(ui_context)
        return True

    def sync_pre_operation(self, *args, **kwargs):
        _assert_context(reportbug_context)
        if kwargs.get('queryonly'):
            self.page_type = Gtk.AssistantPageType.CONFIRM
        return args, kwargs

    def execute(self, number, system, mirrors, http_proxy, timeout, queryonly=False, title='', archived='no', mbox_reader_cmd=None):
        _assert_context(ui_context)
        self.page.number = number
        self.page.bts = system
        self.page.mirrors = mirrors
        self.page.http_proxy = http_proxy
        self.page.timeout = timeout
        self.page.queryonly = queryonly
        self.page.archived = archived
        self.page.start()
        self.validate()


class DisplayReportPage(Page):
    default_complete = True

    def create_widget(self):
        _assert_context(ui_context)
        self.view = Gtk.TextView()
        self.view.set_editable(False)
        scrolled = create_scrollable(self.view)
        return scrolled

    def execute(self, message, *args):
        _assert_context(ui_context)
        # 'use' args only if it's passed
        if args:
            message = message % args
        self.view.get_buffer().set_text(message)


class LongMessagePage(Page):
    default_complete = True

    def create_widget(self):
        _assert_context(ui_context)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        self.label.set_selectable(True)
        self.label.set_property("can-focus", False)
        eb = Gtk.EventBox()
        eb.add(self.label)
        return eb

    def execute(self, message, *args):
        _assert_context(ui_context)
        message = message % args
        # no need to wrap the message, it will be wrapped at display-time
        # but separate all paragraphs by an empty line
        message = '\n\n'.join(par for par in message.splitlines() if par)
        if('nnnnnn' in message):
            message = 'Thank you for your report.\n\n' + message
        GLib.idle_add(self.label.set_text, message)


class FinalMessagePage(LongMessagePage):
    page_type = Gtk.AssistantPageType.SUMMARY
    default_complete = True

    def execute(self, *args, **kwargs):
        _assert_context(ui_context)
        LongMessagePage.execute(self, *args, **kwargs)


class EditorPage(Page):
    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=6)
        hbox = Gtk.HBox(spacing=12)
        hbox.pack_start(Gtk.Label(label="Subject: "), False, True, 0)
        self.subject = Gtk.Entry()
        hbox.pack_start(self.subject, True, True, 0)
        vbox.pack_start(hbox, False, True, 0)

        self.info_buffer = GtkSource.Buffer()
        self.view = GtkSource.View(buffer=self.info_buffer)
        self.view.modify_font(Pango.FontDescription("Monospace"))
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)

        # We have to do the import in the UI thread, because it loads a
        # SQLite database at import time, and the Python SQLite bindings
        # don't allow transferring a SQLite handle between threads.
        global gtkspellcheck
        if gtkspellcheck is None:
            try:
                import gtkspellcheck
            except ImportError:
                gtkspellcheck = NotImplemented

        if gtkspellcheck is not NotImplemented:
            try:
                gtkspellcheck.SpellChecker(self.view)
            except Exception:
                pass
        scrolled = create_scrollable(self.view)
        vbox.pack_start(scrolled, True, True, 0)

        expander = Gtk.Expander.new_with_mnemonic("Other system information")
        view = Gtk.TextView()
        view.modify_font(Pango.FontDescription("Monospace"))
        view.set_editable(False)
        self.others_buffer = view.get_buffer()
        scrolled = create_scrollable(view)
        expander.add(scrolled)
        vbox.pack_start(expander, False, True, 0)

        if gtkspellcheck is NotImplemented:
            box = Gtk.EventBox()
            label = Gtk.Label(label="Please install <b>python3-gtkspellcheck</b> to enable spell checking")
            label.set_use_markup(True)
            label.set_line_wrap(True)
            label.set_selectable(True)
            label.set_property("can-focus", False)
            box.add(label)
            box.modify_bg(Gtk.StateType.NORMAL, self.WARNING_COLOR)
            box.connect('button-press-event', lambda *args: box.destroy())
            vbox.pack_start(box, False, True, 0)
        return vbox

    def switch_out(self):
        global report_message
        _assert_context(ui_context)
        report_message = self.get_value()[0]
        with open(self.filename, "w", errors='backslashreplace') as f:
            f.write(report_message)

    def connect_signals(self):
        _assert_context(ui_context)
        self.info_buffer.connect('changed', self.validate)
        self.subject.connect('changed', self.validate)

    def get_value(self):
        _assert_context(ui_context)
        info = self.info_buffer.get_text(self.info_buffer.get_start_iter(),
                                         self.info_buffer.get_end_iter(),
                                         True)
        if not info.strip():
            return None
        subject = self.subject.get_text().strip()
        if not subject.strip():
            return None

        self.report.set_subject(subject)
        message = self.report.create_message(info)
        return(message, message != self.message)

    def handle_first_info(self):
        _assert_context(ui_context)
        self.focus_in_id = self.view.connect('focus-in-event', self.on_view_focus_in_event)

    def on_view_focus_in_event(self, view, *args):
        _assert_context(ui_context)
        # Empty the buffer only the first time
        self.info_buffer.set_text("")
        view.disconnect(self.focus_in_id)

    def execute(self, message, filename, editor, charset='utf-8'):
        _assert_context(ui_context)
        self.message = message
        self.report = BugReport(message)
        self.filename = filename
        self.charset = charset
        self.subject.set_text(self.report.get_subject())
        self.others_buffer.set_text(self.report.get_others())

        info = self.report.get_original_info()
        # if info.strip() == "*** Please type your report below this line ***":
        if info.strip() == "Dear Maintainer,":
            info = "Please type your report here.\nThe text will be wrapped to be max 79 chars long per line."
            self.handle_first_info()
        self.info_buffer.set_text(info)


class SelectOptionsPage(Page):
    default_complete = False

    def create_widget(self):
        _assert_context(ui_context)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        self.vbox = Gtk.VBox(spacing=6)
        self.vbox.pack_start(self.label, False, True, 6)
        self.default = None
        return self.vbox

    def on_clicked(self, button, menuopt):
        _assert_context(ui_context)
        self.application.set_next_value(menuopt)
        self.assistant.forward_page()

    def on_display_clicked(self, button):
        global report_message
        _assert_context(ui_context)
        ReportViewerDialog(report_message)

    def setup_focus(self):
        _assert_context(ui_context)
        if self.default:
            self.default.props.can_default = True
            self.default.props.has_default = True
            self.default.grab_default()
            self.default.grab_focus()

    def execute(self, prompt, menuopts, options):
        _assert_context(ui_context)
        # remove text UI indication
        prompt = prompt.replace('(e to edit)', '')
        GLib.idle_add(self.label.set_text, prompt)

        buttons = []
        for menuopt in menuopts:
            desc = options[menuopt.lower()]
            # do we really need to launch an external editor?
            if 'Change editor' in desc:
                continue
            # this will be handled using the text view below
            if 'Pipe the message through the pager' in desc:
                continue
            # stdout is a textview for us
            if 'Print message to stdout' in desc:
                button = Gtk.Button(label="Display message in a text view")
                button.connect('clicked', self.on_display_clicked)
                buttons.append(button)
            else:
                button = Gtk.Button()
                label = Gtk.Label(label=options[menuopt.lower()])
                button.add(label)
                button.connect('clicked', self.on_clicked, menuopt.lower())
                if menuopt.isupper():
                    label.set_markup("<b>%s</b>" % label.get_text())
                    self.default = button
                    buttons.insert(0, Gtk.HSeparator())
                    buttons.insert(0, button)
                else:
                    buttons.append(button)

        for button in buttons:
            self.vbox.pack_start(button, False, True, 0)

        self.vbox.show_all()


class SystemPage(Page):
    default_complete = False

    def create_widget(self):
        _assert_context(ui_context)
        hbox = Gtk.HBox()

        self.terminal = Vte.Terminal()
        self.terminal.set_cursor_blink_mode(True)
        self.terminal.connect('child-exited', self.on_child_exited)
        hbox.pack_start(self.terminal, True, True, 0)

        scrollbar = Gtk.VScrollbar()
        scrollbar.set_adjustment(self.terminal.get_vadjustment())
        hbox.pack_start(scrollbar, False, True, 0)

        return hbox

    def on_child_exited(self, terminal, exitstatus):
        _assert_context(ui_context)
        self.application.set_next_value(exitstatus)
        self.assistant.forward_page()

    def execute(self, cmdline):
        _assert_context(ui_context)
        self.terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.environ['HOME'], ['/bin/bash', '-c', cmdline], None, GLib.SpawnFlags.DEFAULT, None, None, -1, None)


class ProgressPage(Page):
    page_type = Gtk.AssistantPageType.PROGRESS

    def pulse(self):
        _assert_context(ui_context)
        self.progress.pulse()
        return True

    def create_widget(self):
        _assert_context(ui_context)
        vbox = Gtk.VBox(spacing=6)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_justify(Gtk.Justification.FILL)
        self.progress = Gtk.ProgressBar()
        self.progress.set_pulse_step(0.01)
        vbox.pack_start(self.label, False, True, 0)
        vbox.pack_start(self.progress, False, True, 0)
        GLib.timeout_add(10, self.pulse)
        return vbox

    def set_label(self, text):
        _assert_context(ui_context)
        GLib.idle_add(self.label.set_text, text)

    def reset_label(self):
        _assert_context(ui_context)
        self.set_label("This operation may take a while")


class ReportbugAssistant(Gtk.Assistant):
    def __init__(self, application):
        _assert_context(ui_context)
        Gtk.Assistant.__init__(self)
        self.application = application

        self.set_title('Reportbug')
        self.hack_buttons()
        self.showing_page = None
        self.requested_page = None
        self.progress_page = None
        self.set_default_size(600, 400)
        self.set_forward_page_func(self.forward)
        self.connect_signals()
        self.setup_pages()

    def _hack_buttons(self, widget):
        _assert_context(ui_context)
        # This is a real hack for two reasons:
        # 1. There's no other way to access action area but inspecting the assistant and searching for the back button
        # 2. Hide back button on show, because it can be shown-hidden by the assistant depending on the page
        if isinstance(widget, Gtk.Button):
            if widget.get_label() == 'gtk-go-back':
                widget.connect('show', self.on_back_show)
                return
            if widget.get_label() == 'gtk-apply':
                widget.connect('show', self.on_back_show)
                return
            if widget.get_label() == 'gtk-cancel':
                image = Gtk.Image.new_from_stock(Gtk.STOCK_QUIT,
                                                 Gtk.IconSize.BUTTON)
                widget.set_label("_Quit")
                widget.set_image(image)
                return
            if widget.get_label() == 'gtk-go-forward':
                image = Gtk.Image.new_from_stock(Gtk.STOCK_GO_FORWARD, Gtk.IconSize.BUTTON)
                widget.set_label("_Continue")
                widget.set_image(image)
                return

        if isinstance(widget, Gtk.Container):
            widget.forall(self._hack_buttons)

    def hack_buttons(self):
        _assert_context(ui_context)
        self._hack_buttons(self)

    def connect_signals(self):
        _assert_context(ui_context)
        self.connect('cancel', self.confirm_exit)
        self.connect('prepare', self.on_prepare)
        self.connect('delete-event', self.close)
        self.connect('apply', self.close)
        self.connect('close', self.close)

    def on_back_show(self, widget):
        _assert_context(ui_context)
        widget.hide()

    def on_prepare(self, assistant, widget):
        _assert_context(ui_context)
        # If the user goes back then forward, we must ensure the feedback value to reportbug must be sent
        # when the user clicks on "Forward" to the requested page by reportbug
        if self.showing_page and self.showing_page == self.requested_page and self.get_current_page() > self.showing_page.page_num:
            self.application.put_next_value()
            # Reportbug doesn't support going back, so make widgets insensitive
            self.showing_page.widget.set_sensitive(False)
            self.showing_page.switch_out()

        self.showing_page = widget.page
        # Some pages might have changed the label in the while
        if self.showing_page == self.progress_page:
            self.progress_page.reset_label()

        GLib.idle_add(self.showing_page.setup_focus)

    def close(self, *args):
        _assert_context(ui_context)
        _exit()

    def confirm_exit(self, *args):
        _assert_context(ui_context)
        dialog = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.WARNING, Gtk.ButtonsType.YES_NO,
                                   "Are you sure you want to quit Reportbug?")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            _exit()

    def forward(self, page_num):
        _assert_context(ui_context)
        return page_num + 1

    def forward_page(self):
        _assert_context(ui_context)
        self.set_current_page(self.forward(self.showing_page.page_num))

    def set_next_page(self, page):
        _assert_context(ui_context)
        self.requested_page = page
        # If we're in progress immediately show this guy
        if self.showing_page == self.progress_page:
            self.set_current_page(page.page_num)

    def set_progress_label(self, text, *args, **kwargs):
        _assert_context(ui_context)
        self.progress_page.set_label(text % args)

    def setup_pages(self):
        _assert_context(ui_context)
        # We insert pages between the intro and the progress, so that we give the user the feedback
        # that the applications is still running when he presses the "Forward" button
        self.showing_page = IntroPage(self)
        self.showing_page.switch_in()
        self.progress_page = ProgressPage(self)
        self.progress_page.switch_in()
        Page.next_page_num = 1


# Dialogs
class YesNoDialog(ReportbugConnector, Gtk.MessageDialog):
    def __init__(self, application):
        _assert_context(ui_context)
        Gtk.MessageDialog.__init__(self, assistant, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO)
        self.application = application
        self.connect('response', self.on_response)

    def on_response(self, dialog, res):
        _assert_context(ui_context)
        self.application.set_next_value(res == Gtk.ResponseType.YES)
        self.application.put_next_value()
        self.destroy()

    def execute_operation(self, msg, yeshelp=None, nohelp=None, default=True, nowrap=False):
        _assert_context(ui_context)
        self.set_markup(msg)
        if default:
            self.set_default_response(Gtk.ResponseType.YES)
        else:
            self.set_default_response(Gtk.ResponseType.NO)
        self.show_all()


class DisplayFailureDialog(ReportbugConnector, Gtk.MessageDialog):
    def __init__(self, application):
        _assert_context(ui_context)
        Gtk.MessageDialog.__init__(self, assistant, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.WARNING, Gtk.ButtonsType.CLOSE)
        self.application = application
        self.connect('response', self.on_response)

    def on_response(self, dialog, res):
        _assert_context(ui_context)
        self.application.put_next_value()
        self.destroy()

    def execute_operation(self, msg, *args):
        _assert_context(ui_context)
        self.set_markup(msg % args)
        self.show_all()


class GetFilenameDialog(ReportbugConnector, Gtk.FileChooserDialog):
    def __init__(self, application):
        _assert_context(ui_context)
        Gtk.FileChooserDialog.__init__(self, '', assistant, buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                                     Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        self.application = application
        self.connect('response', self.on_response)

    def on_response(self, dialog, res):
        _assert_context(ui_context)
        value = None
        if res == Gtk.ResponseType.OK:
            value = self.get_filename()

        self.application.set_next_value(value)
        self.application.put_next_value()
        self.destroy()

    def execute_operation(self, title, force_prompt=False):
        _assert_context(ui_context)
        self.set_title(ask_free(title))
        self.show_all()


def log_message(*args, **kwargs):
    _assert_context(reportbug_context)
    application.run_once_in_main_thread(assistant.set_progress_label, *args, **kwargs)


def select_multiple(*args, **kwargs):
    _assert_context(reportbug_context)
    kwargs['multiple'] = True
    kwargs['empty_ok'] = True
    return menu(*args, **kwargs)  # noqa: F821


def get_multiline(prompt, *args, **kwargs):
    _assert_context(reportbug_context)
    if 'ENTER' in prompt:
        # This is a list, let's handle it the best way
        return get_list(prompt, *args, **kwargs)  # noqa: F821
    else:
        return _get_multiline(prompt, *args, **kwargs)  # noqa: F821


pages = {'get_string': GetStringPage,
         'get_password': GetPasswordPage,
         'menu': MenuPage,
         'handle_bts_query': HandleBTSQueryPage,
         'show_report': ShowReportPage,
         'long_message': LongMessagePage,
         'display_report': DisplayReportPage,
         'final_message': FinalMessagePage,
         'spawn_editor': EditorPage,
         'select_options': SelectOptionsPage,
         'get_list': GetListPage,
         'system': SystemPage,
         '_get_multiline': GetMultilinePage,
         }
dialogs = {'yes_no': YesNoDialog,
           'get_filename': GetFilenameDialog,
           'display_failure': DisplayFailureDialog,
           }


def create_forwarder(parent, klass):
    _assert_context(reportbug_context)

    def func(*args, **kwargs):
        _assert_context(reportbug_context)
        op = application.call_in_main_thread(klass, parent)
        try:
            args, kwargs = op.sync_pre_operation(*args, **kwargs)
        except SyncReturn as e:
            return e.result
        application.run_once_in_main_thread(op.execute_operation, *args, **kwargs)
        return application.get_last_value()

    return func


def forward_operations(parent, operations):
    _assert_context(reportbug_context)
    for operation, klass in operations.items():
        globals()[operation] = create_forwarder(parent, klass)


def initialize():
    global application, assistant, reportbug_context, ui_context, Vte

    try:
        gi.require_version('Vte', '2.91')
        from gi.repository import Vte
    except (ImportError, ValueError):
        message = """Please install the %s package to use the GTK+ (known as 'gtk' in reportbug) interface.
Falling back to 'text' interface."""
        dialog = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE, None)
        dialog.set_markup(message % "<b>gir1.2-vte-2.91</b>")
        dialog.run()
        dialog.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if not sys.stdout.isatty():
            os.execlp('x-terminal-emulator', 'x-terminal-emulator', '-e', 'reportbug -u text')
        return False

    # The first thread of the process runs reportbug's UI-agnostic logic
    reportbug_context = GLib.MainContext()
    if not reportbug_context.acquire():
        # should be impossible
        raise AssertionError('Could not acquire new main-context')
    reportbug_context.push_thread_default()

    # A secondary thread (the ReportbugApplication) runs the GTK UI.
    # This is the "default main context", used by GLib.idle_add() and similar
    # non-thread-aware APIs.
    ui_context = GLib.MainContext.default()

    # Exception hook
    oldhook = sys.excepthook
    sys.excepthook = ExceptionDialog.create_excepthook(oldhook)

    # GTK settings
    Gtk.Window.set_default_icon_from_file(DEBIAN_LOGO)

    application = ReportbugApplication()
    application.start()
    forward_operations(application, dialogs)

    assistant = application.call_in_main_thread(ReportbugAssistant, application)
    forward_operations(assistant, pages)

    return True


def can_input():
    _assert_context(reportbug_context)
    return True
