""" Representation of Debian binary package (.deb) files


Debfile Classes
===============
"""

# Copyright (C) 2007-2008   Stefano Zacchiroli  <zack@debian.org>
# Copyright (C) 2007        Filippo Giunchedi   <filippo@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gzip
import io
import tarfile
import sys
import os.path
from pathlib import Path

try:
    # pylint: disable=unused-import
    from typing import (
        Any,
        BinaryIO,
        Dict,
        IO,
        Iterator,
        List,
        Optional,
        Text,
        TypeVar,
        Union,
        overload,
        TYPE_CHECKING,
    )
    from typing_extensions import (
        Literal,
    )
except ImportError:
    # Missing types aren't important at runtime
    if not TYPE_CHECKING:
        overload = lambda f: None


from debian.arfile import ArFile, ArError, ArMember     # pylint: disable=unused-import
from debian.changelog import Changelog
from debian.deb822 import Deb822


DATA_PART = 'data.tar'      # w/o extension
CTRL_PART = 'control.tar'
PART_EXTS = ['gz', 'bz2', 'xz', 'lzma', 'zst']  # possible extensions
INFO_PART = 'debian-binary'
MAINT_SCRIPTS = ['preinst', 'postinst', 'prerm', 'postrm', 'config']

CONTROL_FILE = 'control'
CHANGELOG_NATIVE = 'usr/share/doc/%s/changelog.gz'  # with package stem
CHANGELOG_DEBIAN = 'usr/share/doc/%s/changelog.Debian.gz'
MD5_FILE = 'md5sums'


class DebError(ArError):
    pass


class DebPart(object):
    """'Part' of a .deb binary package.

    A .deb package is considered as made of 2 parts: a 'data' part
    (corresponding to the possibly compressed 'data.tar' archive embedded
    in a .deb) and a 'control' part (the 'control.tar.gz' archive). Each of
    them is represented by an instance of this class. Each archive should
    be a compressed tar archive although an uncompressed data.tar is permitted;
    supported compression formats are: .tar.gz, .tar.bz2, .tar.xz .

    When referring to file members of the underlying .tar.gz archive, file
    names can be specified in one of 3 formats "file", "./file", "/file". In
    all cases the file is considered relative to the root of the archive. For
    the control part the preferred mechanism is the first one (as in
    deb.control.get_content('control') ); for the data part the preferred
    mechanism is the third one (as in deb.data.get_file('/etc/vim/vimrc') ).
    """

    def __init__(self, member):
        # type: (ArMember) -> None
        self.__member = member  # arfile.ArMember file member
        self.__tgz = None   # type: Optional[tarfile.TarFile]

    def tgz(self):
        # type: () -> tarfile.TarFile
        """Return a TarFile object corresponding to this part of a .deb
        package.

        Despite the name, this method gives access to various kind of
        compressed tar archives, not only gzipped ones.
        """

        def _custom_decompress(command_list):
            # type: (List[str]) -> BinaryIO
            try:
                # pylint: disable=import-outside-toplevel
                import subprocess
                import signal

                # pylint: disable=subprocess-popen-preexec-fn,consider-using-with
                proc = subprocess.Popen(
                    command_list,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    universal_newlines=False,
                    preexec_fn=lambda:
                    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
                )
            except (OSError, ValueError) as e:
                raise DebError("error while running command '%s' as subprocess: '%s'" %
                               (' '.join(command_list), e))

            data = proc.communicate(self.__member.read())[0]
            if proc.returncode != 0:
                raise DebError("command '%s' has failed with code '%s'" %
                               (' '.join(command_list), proc.returncode))

            return io.BytesIO(data)

        if self.__tgz is None:
            name = self.__member.name
            extension = os.path.splitext(name)[1][1:]
            if extension in PART_EXTS or name == DATA_PART or name == CTRL_PART:
                # Permit compressed members and also uncompressed data.tar
                # tarfile has no zst support: https://bugs.python.org/issue37095
                if extension == 'zst':
                    buffer = _custom_decompress(['unzstd', '--stdout'])
                else:
                    buffer = self.__member  # type: ignore

                try:
                    self.__tgz = tarfile.open(fileobj=buffer, mode='r:*')    # pylint: disable = consider-using-with
                except (tarfile.ReadError, tarfile.CompressionError) as e:
                    raise DebError("tarfile has returned an error: '%s'" % e)
            else:
                raise DebError("part '%s' has unexpected extension" % name)
        return self.__tgz

    @staticmethod
    def __normalize_member(fname):
        # type: (Union[str, Path]) -> str
        """ try (not so hard) to obtain a member file name in a form that is
        stored in the .tar.gz, i.e. starting with ./ """

        # os.path and pathlib operations on windows will end up with \ as the directory separator
        fname = str(fname).replace("\\", "/")

        if fname.startswith('./'):
            return fname

        if fname.startswith('/'):
            return '.' + fname
        return './' + fname

    def __resolve_symlinks(self, path):
        # type: (str) -> Optional[str]
        """ walk the path following symlinks

        returns:
            resolved_path, info

        if the path is not found even after following symlinks within the
        archive, then None is returned.
        """
        try:
            resolved_path_parts = []
            for pathpart in path.split('/')[1:]:
                resolved_path_parts.append(pathpart)
                currpath = os.path.normpath('/'.join(resolved_path_parts))
                currpath = DebPart.__normalize_member(currpath)
                tinfo = self.tgz().getmember(currpath)
                # if this part is a symlink, pop it off the resolved_path_parts
                # and replace it with the link destination
                if tinfo.issym():
                    if tinfo.linkname.startswith("/"):
                        # absolute symlink replaces everything currently collected
                        resolved_path_parts = tinfo.linkname.split("/")
                        currpath = tinfo.linkname
                    else:
                        # relative symlink replaces the last part
                        #    foo.txt -> bar.txt
                        #    docs -> ../foo-doc/html
                        # in the latter case, the call to `normpath`
                        # will canonicalise it.
                        resolved_path_parts[-1] = tinfo.linkname

        except KeyError:
            # the specified file is not in this .deb at all
            return None

        return DebPart.__normalize_member(os.path.normpath(currpath))

    def has_file(self, fname, follow_symlinks=False):
        # type: (Union[str, Path], bool) -> bool
        """Check if this part contains a given file name.

        Symlinks within the archive can be followed.
        """
        fname = DebPart.__normalize_member(fname)

        names = self.tgz().getnames()
        if fname in names:
            return True

        if follow_symlinks:
            fname_real = self.__resolve_symlinks(fname)
            return fname_real is not None

        return fname in names

    @overload
    def get_file(self, fname, encoding=None, errors=None, follow_symlinks=False):
        # type: (Union[str, Path], None, Optional[str], bool) -> IO[bytes]
        pass

    @overload
    def get_file(self, fname, encoding, errors=None, follow_symlinks=False):
        # type: (Union[str, Path], str, Optional[str], bool) -> IO[str]
        pass

    def get_file(self, fname, encoding=None, errors=None, follow_symlinks=False):
        # type: (Union[str, Path], Optional[str], Optional[str], bool) -> Union[IO[bytes], IO[str]]
        """Return a file object corresponding to a given file name.

        If encoding is given, then the file object will return Unicode data;
        otherwise, it will return binary data.

        If follow_symlinks is True, then symlinks within the archive will be
        followed.
        """

        fname = DebPart.__normalize_member(fname)

        if follow_symlinks:
            fname_real = self.__resolve_symlinks(fname)
            if fname_real is None:
                raise DebError("File not found inside package")
            fname = fname_real

        try:
            fobj = self.tgz().extractfile(fname)
        except KeyError:
            raise DebError("File not found inside package")

        if fobj is None:
            raise DebError("File not found inside package")

        if encoding is not None:
            return io.TextIOWrapper(fobj, encoding=encoding, errors=errors)

        return fobj

    @overload
    def get_content(self,
                    fname,          # type: Union[str, Path]
                    encoding=None,  # type: Literal[None]
                    errors=None,    # type: Optional[str]
                    follow_symlinks=False,  # type: bool
                   ):
        # type: (...) -> Optional[bytes]
        pass

    @overload
    def get_content(self,
                    fname,             # type: Union[str, Path]
                    encoding,          # type: str
                    errors=None,       # type: Optional[str]
                    follow_symlinks=False,  # type: bool
                   ):
        # type: (...) -> Optional[Text]
        pass

    def get_content(self,
                    fname,          # type: Union[str, Path]
                    encoding=None,  # type: Optional[str]
                    errors=None,    # type: Optional[str]
                    follow_symlinks=False,  # type: bool
                   ):
        # type: (...) -> Optional[Union[Text,bytes]]
        """Return the string content of a given file, or None (e.g. for
        directories).

        If encoding is given, then the content will be a Unicode object;
        otherwise, it will contain binary data.

        If follow_symlinks is True, then symlinks within the archive will be
        followed.
        """
        f = self.get_file(
            str(fname),
            encoding=encoding, errors=errors,
            follow_symlinks=follow_symlinks
        )
        content = None
        if f:   # can be None for non regular or link files
            content = f.read()
            f.close()
        return content

    # container emulation

    def __iter__(self):
        # type: () -> Iterator[str]
        return iter(self.tgz().getnames())

    def __contains__(self, fname):
        # type: (Union[str, Path]) -> bool
        return self.has_file(fname)

    def __getitem__(self, fname):
        # type: (Union[str, Path]) ->  Optional[Union[bytes, Text]]
        return self.get_content(fname)

    def close(self):
        # type: () -> None
        self.__member.close()


class DebData(DebPart):

    pass


class DebControl(DebPart):

    def scripts(self):
        # type: () -> Dict[str, bytes]
        """ Return a dictionary of maintainer scripts (postinst, prerm, ...)
        mapping script names to script text. """

        scripts = {}    # type: Dict[str, bytes]
        for fname in MAINT_SCRIPTS:
            if self.has_file(fname):
                data = self.get_content(fname)
                if data is not None:
                    scripts[fname] = data

        return scripts

    def debcontrol(self):
        # type: () -> Deb822
        """ Return the debian/control as a Deb822 (a Debian-specific dict-like
        class) object.

        For a string representation of debian/control try
        .get_content('control') """

        return Deb822(self.get_content(CONTROL_FILE))

    @overload
    def md5sums(self, encoding=None, errors=None):
        # type: (Literal[None], Optional[str]) -> Dict[bytes, str]
        pass

    @overload
    def md5sums(self, encoding, errors=None):
        # type: (str, Optional[str]) -> Dict[str, str]
        pass

    def md5sums(self, encoding=None, errors=None):
        # type: (Optional[str], Optional[str]) -> Union[Dict[str, str], Dict[bytes, str]]
        """ Return a dictionary mapping filenames (of the data part) to
        md5sums. Fails if the control part does not contain a 'md5sum' file.

        Keys of the returned dictionary are the left-hand side values of lines
        in the md5sums member of control.tar.gz, usually file names relative to
        the file system root (without heading '/' or './').

        The returned keys are Unicode objects if an encoding is specified,
        otherwise binary. The returned values are always Unicode."""

        if not self.has_file(MD5_FILE):
            raise DebError(
                "'%s' file not found, can't list MD5 sums" % MD5_FILE)

        md5_file = self.get_file(MD5_FILE, encoding=encoding, errors=errors)
        sums = {}  # type:  Dict[Any, str]

        newline = '\r\n'     # type: Union[str, bytes]
        if encoding is None:
            newline = b'\r\n'

        for line in md5_file.readlines():
            # we need to support spaces in filenames, .split() is not enough
            md5, fname = line.rstrip(newline).split(None, 1)  # type: ignore
            if isinstance(md5, bytes):
                sums[fname] = md5.decode()
            else:
                sums[fname] = md5
        md5_file.close()
        return sums


class DebFile(ArFile):
    # pylint: disable=abstract-method
    """Representation of a .deb file (a Debian binary package)

    DebFile objects have the following (read-only) properties:
        - version       debian .deb file format version (not related with the
                        contained package version), 2.0 at the time of writing
                        for all .deb packages in the Debian archive
        - data          DebPart object corresponding to the data.tar.gz (or
                        other compressed or uncompressed tar) archive contained
                        in the .deb file
        - control       DebPart object corresponding to the control.tar.gz (or
                        other compressed tar) archive contained in the .deb
                        file
    """

    def __init__(self, filename=None, mode='r', fileobj=None):
        # type: (Optional[Union[str, Path]], str, Optional[BinaryIO]) -> None
        ArFile.__init__(self, filename, mode, fileobj)
        actual_names = set(self.getnames())

        def compressed_part_name(basename):
            # type: (str) -> str
            candidates = ['%s.%s' % (basename, ext) for ext in PART_EXTS]
            # also permit uncompressed data.tar and control.tar
            if basename in (DATA_PART, CTRL_PART):
                candidates.append(basename)
            parts = actual_names.intersection(set(candidates))
            if not parts:
                raise DebError(
                    "missing required part in given .deb"
                    " (expected one of: %s)" % candidates)

            if len(parts) > 1:
                raise DebError(
                    "too many parts in given .deb"
                    " (was looking for only one of: %s)" % candidates)

            return list(parts)[0]   # singleton list

        if INFO_PART not in actual_names:
            raise DebError(
                "missing required part in given .deb"
                " (expected: '%s')" % INFO_PART)

        self.__parts = {}   # type: Dict[str, DebPart]
        self.__parts[CTRL_PART] = DebControl(self.getmember(
            compressed_part_name(CTRL_PART)))
        self.__parts[DATA_PART] = DebData(self.getmember(
            compressed_part_name(DATA_PART)))
        self.__pkgname = None   # updated lazily by __updatePkgName

        f = self.getmember(INFO_PART)
        self.__version = f.read().strip()
        f.close()

    def __updatePkgName(self):
        # type: () -> None
        self.__pkgname = self.debcontrol()['package']

    @property
    def version(self):
        # type: () -> bytes
        return self.__version

    @property
    def data(self):
        # type: () -> DebData
        return self.__parts[DATA_PART]  # type: ignore

    @property
    def control(self):
        # type: () -> DebControl
        return self.__parts[CTRL_PART]  # type: ignore

    # proxy methods for the appropriate parts

    def debcontrol(self):
        # type: () -> Deb822
        """ See .control.debcontrol() """
        return self.control.debcontrol()

    def scripts(self):
        # type: () -> Dict[str, bytes]
        """ See .control.scripts() """
        return self.control.scripts()

    @overload
    def md5sums(self, encoding=None, errors=None):
        # type: (Literal[None], Optional[str]) -> Dict[bytes, str]
        pass

    @overload
    def md5sums(self, encoding, errors=None):
        # type: (str, Optional[str]) -> Dict[str, str]
        pass

    def md5sums(self, encoding=None, errors=None):
        # type: (Optional[str], Optional[str]) -> Union[Dict[str, str], Dict[bytes, str]]
        """ See .control.md5sums() """
        return self.control.md5sums(encoding=encoding, errors=errors)

    def changelog(self):
        # type: () -> Optional[Changelog]
        """ Return a Changelog object for the changelog.Debian.gz of the
        present .deb package. Return None if no changelog can be found. """

        if self.__pkgname is None:
            self.__updatePkgName()

        for fname in [CHANGELOG_DEBIAN % self.__pkgname,
                      CHANGELOG_NATIVE % self.__pkgname]:
            try:
                fh = self.data.get_file(fname, follow_symlinks=True)
            except DebError:
                continue

            with gzip.GzipFile(fileobj=fh) as gz:
                raw_changelog = gz.read()
            return Changelog(raw_changelog)

        return None

    def close(self):
        # type: () -> None
        self.control.close()
        self.data.close()

    def __enter__(self):
        # type: () -> DebFile
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # type: (Any, Any, Any) -> None
        self.close()


if __name__ == '__main__':
    deb = DebFile(filename=sys.argv[1])
    tgz = deb.control.tgz()
    print(tgz.getmember('control'))
