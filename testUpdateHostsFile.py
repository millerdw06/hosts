#!/usr/bin/env python

# Script by gfyoung
# https://github.com/gfyoung
#
# Python script for testing updateHostFiles.py

from updateHostsFile import (Colors, PY3, colorize, flush_dns_cache,
                             gather_custom_exclusions, get_defaults,
                             get_file_by_url, is_valid_domain_format,
                             move_hosts_file_into_place, normalize_rule,
                             path_join_robust, print_failure, print_success,
                             supports_color, query_yes_no, recursive_glob,
                             remove_old_hosts_file, strip_rule,
                             update_readme_data, write_data,
                             write_opening_header)
import updateHostsFile
import unittest
import tempfile
import locale
import shutil
import json
import sys
import os

if PY3:
    from io import BytesIO, StringIO
    import unittest.mock as mock
    unicode = str
else:
    from StringIO import StringIO
    BytesIO = StringIO
    import mock


# Base Test Classes
class Base(unittest.TestCase):

    @staticmethod
    def mock_property(name):
        return mock.patch(name, new_callable=mock.PropertyMock)

    @property
    def sep(self):
        return "\\" if sys.platform == "win32" else "/"


class BaseStdout(Base):

    def setUp(self):
        sys.stdout = StringIO()

    def tearDown(self):
        sys.stdout.close()
        sys.stdout = sys.__stdout__


class BaseMockDir(Base):

    @property
    def dir_count(self):
        return len(os.listdir(self.test_dir))

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)
# End Base Test Classes


# Project Settings
class TestGetDefaults(Base):

    def test_get_defaults(self):
        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = "foo"
            actual = get_defaults()
            expected = {"numberofrules": 0,
                        "datapath": "foo" + self.sep + "data",
                        "freshen": True,
                        "replace": False,
                        "backup": False,
                        "skipstatichosts": False,
                        "keepdomaincomments": False,
                        "extensionspath": "foo" + self.sep + "extensions",
                        "extensions": [],
                        "outputsubfolder": "",
                        "hostfilename": "hosts",
                        "targetip": "0.0.0.0",
                        "ziphosts": False,
                        "sourcedatafilename": "update.json",
                        "sourcesdata": [],
                        "readmefilename": "readme.md",
                        "readmetemplate": ("foo" + self.sep +
                                           "readme_template.md"),
                        "readmedata": {},
                        "readmedatafilename": ("foo" + self.sep +
                                               "readmeData.json"),
                        "exclusionpattern": "([a-zA-Z\d-]+\.){0,}",
                        "exclusionregexs": [],
                        "exclusions": [],
                        "commonexclusions": ["hulu.com"],
                        "blacklistfile": "foo" + self.sep + "blacklist",
                        "whitelistfile": "foo" + self.sep + "whitelist"}
            self.assertDictEqual(actual, expected)
# End Project Settings


# Exclusion Logic
class TestGatherCustomExclusions(BaseStdout):

    # Can only test in the invalid domain case
    # because of the settings global variable.
    @mock.patch("updateHostsFile.raw_input", side_effect=["foo", "no"])
    @mock.patch("updateHostsFile.is_valid_domain_format", return_value=False)
    def test_basic(self, *_):
        gather_custom_exclusions()

        expected = "Do you have more domains you want to enter? [Y/n]"
        output = sys.stdout.getvalue()
        self.assertIn(expected, output)

    @mock.patch("updateHostsFile.raw_input", side_effect=["foo", "yes",
                                                          "bar", "no"])
    @mock.patch("updateHostsFile.is_valid_domain_format", return_value=False)
    def test_multiple(self, *_):
        gather_custom_exclusions()

        expected = ("Do you have more domains you want to enter? [Y/n] "
                    "Do you have more domains you want to enter? [Y/n]")
        output = sys.stdout.getvalue()
        self.assertIn(expected, output)
# End Exclusion Logic


# File Logic
class TestNormalizeRule(BaseStdout):

    def test_no_match(self):
        kwargs = dict(target_ip="0.0.0.0", keep_domain_comments=False)

        for rule in ["foo", "128.0.0.1", "bar.com/usa", "0.0.0 google",
                     "0.1.2.3.4 foo/bar", "twitter.com"]:
            self.assertEqual(normalize_rule(rule, **kwargs), (None, None))

            output = sys.stdout.getvalue()
            sys.stdout = StringIO()

            expected = "==>" + rule + "<=="
            self.assertIn(expected, output)

    def test_no_comments(self):
        for target_ip in ("0.0.0.0", "127.0.0.1", "8.8.8.8"):
            rule = "127.0.0.1 google foo"
            expected = ("google", str(target_ip) + " google\n")

            actual = normalize_rule(rule, target_ip=target_ip,
                                    keep_domain_comments=False)
            self.assertEqual(actual, expected)

            # Nothing gets printed if there's a match.
            output = sys.stdout.getvalue()
            self.assertEqual(output, "")

            sys.stdout = StringIO()

    def test_with_comments(self):
        for target_ip in ("0.0.0.0", "127.0.0.1", "8.8.8.8"):
            for comment in ("foo", "bar", "baz"):
                rule = "127.0.0.1 google " + comment
                expected = ("google", (str(target_ip) + " google # " +
                                       comment + "\n"))

                actual = normalize_rule(rule, target_ip=target_ip,
                                        keep_domain_comments=True)
                self.assertEqual(actual, expected)

                # Nothing gets printed if there's a match.
                output = sys.stdout.getvalue()
                self.assertEqual(output, "")

                sys.stdout = StringIO()


class TestStripRule(Base):

    def test_strip_empty(self):
        for line in ["0.0.0.0", "domain.com", "foo"]:
            output = strip_rule(line)
            self.assertEqual(output, "")

    def test_strip_exactly_two(self):
        for line in ["0.0.0.0 twitter.com", "127.0.0.1 facebook.com",
                     "8.8.8.8 google.com", "1.2.3.4 foo.bar.edu"]:
            output = strip_rule(line)
            self.assertEqual(output, line)

    def test_strip_more_than_two(self):
        for line in ["0.0.0.0 twitter.com", "127.0.0.1 facebook.com",
                     "8.8.8.8 google.com", "1.2.3.4 foo.bar.edu"]:
            output = strip_rule(line + " # comments here galore")
            self.assertEqual(output, line)


class TestWriteOpeningHeader(BaseMockDir):

    def setUp(self):
        super(TestWriteOpeningHeader, self).setUp()
        self.final_file = BytesIO()

    def test_missing_keyword(self):
        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=False)

        for k in kwargs.keys():
            bad_kwargs = kwargs.copy()
            bad_kwargs.pop(k)

            self.assertRaises(KeyError, write_opening_header,
                              self.final_file, **bad_kwargs)

    def test_basic(self):
        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=True)
        write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        for expected in (
            "# Extensions added to this file:",
            "127.0.0.1 localhost",
            "127.0.0.1 local",
            "127.0.0.53",
            "127.0.1.1",
        ):
            self.assertNotIn(expected, contents)

    def test_basic_include_static_hosts(self):
        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=False)
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Windows"
            write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            "127.0.0.1 local",
            "127.0.0.1 localhost",
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        for expected in (
            "# Extensions added to this file:",
            "127.0.0.53",
            "127.0.1.1",
        ):
            self.assertNotIn(expected, contents)

    def test_basic_include_static_hosts_linux(self):
        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=False)
        with self.mock_property("platform.system") as system:
            system.return_value = "Linux"

            with self.mock_property("socket.gethostname") as hostname:
                hostname.return_value = "steven-hosts"
                write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            "127.0.1.1",
            "127.0.0.53",
            "steven-hosts",
            "127.0.0.1 local",
            "127.0.0.1 localhost",
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        expected = "# Extensions added to this file:"
        self.assertNotIn(expected, contents)

    def test_extensions(self):
        kwargs = dict(extensions=["epsilon", "gamma", "mu", "phi"],
                      outputsubfolder="", numberofrules=5,
                      skipstatichosts=True)
        write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            ", ".join(kwargs["extensions"]),
            "# Extensions added to this file:",
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        for expected in (
            "127.0.0.1 localhost",
            "127.0.0.1 local",
            "127.0.0.53",
            "127.0.1.1",
        ):
            self.assertNotIn(expected, contents)

    def test_no_preamble(self):
        # We should not even attempt to read this, as it is a directory.
        hosts_dir = os.path.join(self.test_dir, "myhosts")
        os.mkdir(hosts_dir)

        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=True)

        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = self.test_dir
            write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        for expected in (
            "# Extensions added to this file:",
            "127.0.0.1 localhost",
            "127.0.0.1 local",
            "127.0.0.53",
            "127.0.1.1",
        ):
            self.assertNotIn(expected, contents)

    def test_preamble(self):
        hosts_file = os.path.join(self.test_dir, "myhosts")
        with open(hosts_file, "w") as f:
            f.write("peter-piper-picked-a-pepper")

        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules=5, skipstatichosts=True)

        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = self.test_dir
            write_opening_header(self.final_file, **kwargs)

        contents = self.final_file.getvalue()
        contents = contents.decode("UTF-8")

        # Expected contents.
        for expected in (
            "peter-piper-picked-a-pepper",
            "# This hosts file is a merged collection",
            "# with a dash of crowd sourcing via Github",
            "# Number of unique domains: {count}".format(
                count=kwargs["numberofrules"]),
            "Fetch the latest version of this file:",
            "Project home page: https://github.com/StevenBlack/hosts",
        ):
            self.assertIn(expected, contents)

        # Expected non-contents.
        for expected in (
            "# Extensions added to this file:",
            "127.0.0.1 localhost",
            "127.0.0.1 local",
            "127.0.0.53",
            "127.0.1.1",
        ):
            self.assertNotIn(expected, contents)

    def tearDown(self):
        super(TestWriteOpeningHeader, self).tearDown()
        self.final_file.close()


class TestUpdateReadmeData(BaseMockDir):

    def setUp(self):
        super(TestUpdateReadmeData, self).setUp()
        self.readme_file = os.path.join(self.test_dir, "readmeData.json")

    def test_missing_keyword(self):
        kwargs = dict(extensions="", outputsubfolder="",
                      numberofrules="", sourcesdata="")

        for k in kwargs.keys():
            bad_kwargs = kwargs.copy()
            bad_kwargs.pop(k)

            self.assertRaises(KeyError, update_readme_data,
                              self.readme_file, **bad_kwargs)

    def test_add_fields(self):
        with open(self.readme_file, "w") as f:
            json.dump({"foo": "bar"}, f)

        kwargs = dict(extensions=None, outputsubfolder="foo",
                      numberofrules=5, sourcesdata="hosts")
        update_readme_data(self.readme_file, **kwargs)

        expected = {
            "base": {
                "location": "foo" + self.sep,
                "sourcesdata": "hosts",
                "entries": 5,
            },
            "foo": "bar"
        }

        with open(self.readme_file, "r") as f:
            actual = json.load(f)
            self.assertEqual(actual, expected)

    def test_modify_fields(self):
        with open(self.readme_file, "w") as f:
            json.dump({"base": "soprano"}, f)

        kwargs = dict(extensions=None, outputsubfolder="foo",
                      numberofrules=5, sourcesdata="hosts")
        update_readme_data(self.readme_file, **kwargs)

        expected = {
            "base": {
                "location": "foo" + self.sep,
                "sourcesdata": "hosts",
                "entries": 5,
            }
        }

        with open(self.readme_file, "r") as f:
            actual = json.load(f)
            self.assertEqual(actual, expected)

    def test_set_extensions(self):
        with open(self.readme_file, "w") as f:
            json.dump({}, f)

        kwargs = dict(extensions=["com", "org"], outputsubfolder="foo",
                      numberofrules=5, sourcesdata="hosts")
        update_readme_data(self.readme_file, **kwargs)

        expected = {
            "com-org": {
                "location": "foo" + self.sep,
                "sourcesdata": "hosts",
                "entries": 5,
            }
        }

        with open(self.readme_file, "r") as f:
            actual = json.load(f)
            self.assertEqual(actual, expected)


class TestMoveHostsFile(BaseStdout):

    @mock.patch("os.path.abspath", side_effect=lambda f: f)
    def test_move_hosts_no_name(self, _):
        with self.mock_property("os.name"):
            os.name = "foo"

            mock_file = mock.Mock(name="foo")
            move_hosts_file_into_place(mock_file)

            expected = ""
            output = sys.stdout.getvalue()

            self.assertEqual(output, expected)

    @mock.patch("os.path.abspath", side_effect=lambda f: f)
    def test_move_hosts_windows(self, _):
        with self.mock_property("os.name"):
            os.name = "nt"

            mock_file = mock.Mock(name="foo")
            move_hosts_file_into_place(mock_file)

            expected = ("Automatically moving the hosts "
                        "file in place is not yet supported.\n"
                        "Please move the generated file to "
                        "%SystemRoot%\system32\drivers\etc\hosts")
            output = sys.stdout.getvalue()
            self.assertIn(expected, output)

    @mock.patch("os.path.abspath", side_effect=lambda f: f)
    @mock.patch("subprocess.call", return_value=0)
    def test_move_hosts_posix(self, *_):
        with self.mock_property("os.name"):
            os.name = "posix"

            mock_file = mock.Mock(name="foo")
            move_hosts_file_into_place(mock_file)

            expected = ("Moving the file requires administrative "
                        "privileges. You might need to enter your password.")
            output = sys.stdout.getvalue()
            self.assertIn(expected, output)

    @mock.patch("os.path.abspath", side_effect=lambda f: f)
    @mock.patch("subprocess.call", return_value=1)
    def test_move_hosts_posix_fail(self, *_):
        with self.mock_property("os.name"):
            os.name = "posix"

            mock_file = mock.Mock(name="foo")
            move_hosts_file_into_place(mock_file)

            expected = "Moving the file failed."
            output = sys.stdout.getvalue()
            self.assertIn(expected, output)


class TestFlushDnsCache(BaseStdout):

    @mock.patch("subprocess.call", return_value=0)
    def test_flush_darwin(self, _):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Darwin"
            flush_dns_cache()

            expected = ("Flushing the DNS cache to utilize new hosts "
                        "file...\nFlushing the DNS cache requires "
                        "administrative privileges. You might need to "
                        "enter your password.")
            output = sys.stdout.getvalue()
            self.assertIn(expected, output)

    @mock.patch("subprocess.call", return_value=1)
    def test_flush_darwin_fail(self, _):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Darwin"
            flush_dns_cache()

            expected = "Flushing the DNS cache failed."
            output = sys.stdout.getvalue()
            self.assertIn(expected, output)

    def test_flush_windows(self):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "win32"

            with self.mock_property("os.name"):
                os.name = "nt"
                flush_dns_cache()

                expected = ("Automatically flushing the DNS cache is "
                            "not yet supported.\nPlease copy and paste "
                            "the command 'ipconfig /flushdns' in "
                            "administrator command prompt after running "
                            "this script.")
                output = sys.stdout.getvalue()
                self.assertIn(expected, output)

    @mock.patch("os.path.isfile", return_value=False)
    def test_flush_no_tool(self, _):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Linux"

            with self.mock_property("os.name"):
                os.name = "posix"
                flush_dns_cache()

                expected = "Unable to determine DNS management tool."
                output = sys.stdout.getvalue()
                self.assertIn(expected, output)

    @mock.patch("os.path.isfile", side_effect=[True] + [False] * 10)
    @mock.patch("subprocess.call", return_value=0)
    def test_flush_posix(self, *_):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Linux"

            with self.mock_property("os.name"):
                os.name = "posix"
                flush_dns_cache()

                expected = ("Flushing the DNS cache by "
                            "restarting nscd succeeded")
                output = sys.stdout.getvalue()
                self.assertIn(expected, output)

    @mock.patch("os.path.isfile", side_effect=[True] + [False] * 10)
    @mock.patch("subprocess.call", return_value=1)
    def test_flush_posix_fail(self, *_):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Linux"

            with self.mock_property("os.name"):
                os.name = "posix"
                flush_dns_cache()

                expected = ("Flushing the DNS cache by "
                            "restarting nscd failed")
                output = sys.stdout.getvalue()
                self.assertIn(expected, output)

    @mock.patch("os.path.isfile", side_effect=[True, False,
                                               True] + [False] * 10)
    @mock.patch("subprocess.call", side_effect=[1, 0])
    def test_flush_posix_fail_then_succeed(self, *_):
        with self.mock_property("platform.system") as obj:
            obj.return_value = "Linux"

            with self.mock_property("os.name"):
                os.name = "posix"
                flush_dns_cache()

                output = sys.stdout.getvalue()
                for expected in [("Flushing the DNS cache by "
                                  "restarting nscd failed"),
                                 ("Flushing the DNS cache by restarting "
                                  "NetworkManager.service succeeded")]:
                    self.assertIn(expected, output)


def mock_path_join_robust(*args):
    # We want to hard-code the backup hosts filename
    # instead of parametrizing based on current time.
    if len(args) == 2 and args[1].startswith("hosts-"):
        return os.path.join(args[0], "hosts-new")
    else:
        return os.path.join(*args)


class TestRemoveOldHostsFile(BaseMockDir):

    def setUp(self):
        super(TestRemoveOldHostsFile, self).setUp()
        self.hosts_file = os.path.join(self.test_dir, "hosts")

    def test_remove_hosts_file(self):
        old_dir_count = self.dir_count

        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = self.test_dir
            remove_old_hosts_file(backup=False)

            new_dir_count = old_dir_count + 1
            self.assertEqual(self.dir_count, new_dir_count)

            with open(self.hosts_file, "r") as f:
                contents = f.read()
                self.assertEqual(contents, "")

    def test_remove_hosts_file_exists(self):
        with open(self.hosts_file, "w") as f:
            f.write("foo")

        old_dir_count = self.dir_count

        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = self.test_dir
            remove_old_hosts_file(backup=False)

            new_dir_count = old_dir_count
            self.assertEqual(self.dir_count, new_dir_count)

            with open(self.hosts_file, "r") as f:
                contents = f.read()
                self.assertEqual(contents, "")

    @mock.patch("updateHostsFile.path_join_robust",
                side_effect=mock_path_join_robust)
    def test_remove_hosts_file_backup(self, _):
        with open(self.hosts_file, "w") as f:
            f.write("foo")

        old_dir_count = self.dir_count

        with self.mock_property("updateHostsFile.BASEDIR_PATH"):
            updateHostsFile.BASEDIR_PATH = self.test_dir
            remove_old_hosts_file(backup=True)

            new_dir_count = old_dir_count + 1
            self.assertEqual(self.dir_count, new_dir_count)

            with open(self.hosts_file, "r") as f:
                contents = f.read()
                self.assertEqual(contents, "")

            new_hosts_file = self.hosts_file + "-new"

            with open(new_hosts_file, "r") as f:
                contents = f.read()
                self.assertEqual(contents, "foo")
# End File Logic


# Helper Functions
def mock_url_open(url):
    """
    Mock of `urlopen` that returns the url in a `BytesIO` stream.

    Parameters
    ----------
    url : str
        The URL associated with the file to open.

    Returns
    -------
    bytes_stream : BytesIO
        The `url` input wrapped in a `BytesIO` stream.
    """

    return BytesIO(url)


def mock_url_open_fail(_):
    """
    Mock of `urlopen` that fails with an Exception.
    """

    raise Exception()


def mock_url_open_read_fail(_):
    """
    Mock of `urlopen` that returns an object that fails on `read`.

    Returns
    -------
    file_mock : mock.Mock
        A mock of a file object that fails when reading.
    """

    def fail_read():
        raise Exception()

    m = mock.Mock()

    m.read = fail_read
    return m


def mock_url_open_decode_fail(_):
    """
    Mock of `urlopen` that returns an object that fails on during decoding
    the output of `urlopen`.

    Returns
    -------
    file_mock : mock.Mock
        A mock of a file object that fails when decoding the output.
    """

    def fail_decode(_):
        raise Exception()

    def read():
        s = mock.Mock()
        s.decode = fail_decode

        return s

    m = mock.Mock()
    m.read = read
    return m


class GetFileByUrl(BaseStdout):

    @mock.patch("updateHostsFile.urlopen",
                side_effect=mock_url_open)
    def test_read_url(self, _):
        url = b"www.google.com"

        expected = "www.google.com"
        actual = get_file_by_url(url)

        self.assertEqual(actual, expected)

    @mock.patch("updateHostsFile.urlopen",
                side_effect=mock_url_open_fail)
    def test_read_url_fail(self, _):
        url = b"www.google.com"
        self.assertIsNone(get_file_by_url(url))

        expected = "Problem getting file:"
        output = sys.stdout.getvalue()

        self.assertIn(expected, output)

    @mock.patch("updateHostsFile.urlopen",
                side_effect=mock_url_open_read_fail)
    def test_read_url_read_fail(self, _):
        url = b"www.google.com"
        self.assertIsNone(get_file_by_url(url))

        expected = "Problem getting file:"
        output = sys.stdout.getvalue()

        self.assertIn(expected, output)

    @mock.patch("updateHostsFile.urlopen",
                side_effect=mock_url_open_decode_fail)
    def test_read_url_decode_fail(self, _):
        url = b"www.google.com"
        self.assertIsNone(get_file_by_url(url))

        expected = "Problem getting file:"
        output = sys.stdout.getvalue()

        self.assertIn(expected, output)


class TestWriteData(Base):

    def test_write_basic(self):
        f = BytesIO()

        data = "foo"
        write_data(f, data)

        expected = b"foo"
        actual = f.getvalue()

        self.assertEqual(actual, expected)

    def test_write_unicode(self):
        f = BytesIO()

        data = u"foo"
        write_data(f, data)

        expected = b"foo"
        actual = f.getvalue()

        self.assertEqual(actual, expected)


class TestQueryYesOrNo(BaseStdout):

    def test_invalid_default(self):
        for invalid_default in ["foo", "bar", "baz", 1, 2, 3]:
            self.assertRaises(ValueError, query_yes_no, "?", invalid_default)

    @mock.patch("updateHostsFile.raw_input", side_effect=["yes"] * 3)
    def test_valid_default(self, _):
        for valid_default, expected in [(None, "[y/n]"), ("yes", "[Y/n]"),
                                        ("no", "[y/N]")]:
            self.assertTrue(query_yes_no("?", valid_default))

            output = sys.stdout.getvalue()
            sys.stdout = StringIO()

            self.assertIn(expected, output)

    @mock.patch("updateHostsFile.raw_input", side_effect=([""] * 2))
    def test_use_valid_default(self, _):
        for valid_default in ["yes", "no"]:
            expected = (valid_default == "yes")
            actual = query_yes_no("?", valid_default)

            self.assertEqual(actual, expected)

    @mock.patch("updateHostsFile.raw_input", side_effect=["no", "NO", "N",
                                                          "n", "No", "nO"])
    def test_valid_no(self, _):
        self.assertFalse(query_yes_no("?", None))

    @mock.patch("updateHostsFile.raw_input", side_effect=["yes", "YES", "Y",
                                                          "yeS", "y", "YeS",
                                                          "yES", "YEs"])
    def test_valid_yes(self, _):
        self.assertTrue(query_yes_no("?", None))

    @mock.patch("updateHostsFile.raw_input", side_effect=["foo", "yes",
                                                          "foo", "no"])
    def test_invalid_then_valid(self, _):
        expected = "Please respond with 'yes' or 'no'"

        # The first time, we respond "yes"
        self.assertTrue(query_yes_no("?", None))

        output = sys.stdout.getvalue()
        self.assertIn(expected, output)

        sys.stdout = StringIO()

        # The second time, we respond "no"
        self.assertFalse(query_yes_no("?", None))

        output = sys.stdout.getvalue()
        self.assertIn(expected, output)


class TestIsValidDomainFormat(BaseStdout):

    def test_empty_domain(self):
        self.assertFalse(is_valid_domain_format(""))

        output = sys.stdout.getvalue()
        expected = "You didn't enter a domain. Try again."

        self.assertTrue(expected in output)

    def test_invalid_domain(self):
        expected = ("Do not include www.domain.com or "
                    "http(s)://domain.com. Try again.")

        for invalid_domain in ["www.subdomain.domain", "https://github.com",
                               "http://www.google.com"]:
            self.assertFalse(is_valid_domain_format(invalid_domain))

            output = sys.stdout.getvalue()
            sys.stdout = StringIO()

            self.assertIn(expected, output)

    def test_valid_domain(self):
        for valid_domain in ["github.com", "travis.org", "twitter.com"]:
            self.assertTrue(is_valid_domain_format(valid_domain))

            output = sys.stdout.getvalue()
            sys.stdout = StringIO()

            self.assertEqual(output, "")


def mock_walk(stem):
    """
    Mock method for `os.walk`.

    Please refer to the documentation of `os.walk` for information about
    the provided parameters.
    """

    files = ["foo.txt", "bar.bat", "baz.py", "foo/foo.c", "foo/bar.doc",
             "foo/baz/foo.py", "bar/foo/baz.c", "bar/bar/foo.bat"]

    if stem == ".":
        stem = ""

    matches = []

    for f in files:
        if not stem or f.startswith(stem + "/"):
            matches.append(("", "_", [f]))

    return matches


class TestRecursiveGlob(Base):

    @staticmethod
    def sorted_recursive_glob(stem, file_pattern):
        actual = recursive_glob(stem, file_pattern)
        actual.sort()

        return actual

    @mock.patch("os.walk", side_effect=mock_walk)
    def test_all_match(self, _):
        with self.mock_property("sys.version_info"):
            sys.version_info = (2, 6)

            expected = ["bar.bat", "bar/bar/foo.bat",
                        "bar/foo/baz.c", "baz.py",
                        "foo.txt", "foo/bar.doc",
                        "foo/baz/foo.py", "foo/foo.c"]
            actual = self.sorted_recursive_glob("*", "*")
            self.assertListEqual(actual, expected)

            expected = ["bar/bar/foo.bat", "bar/foo/baz.c"]
            actual = self.sorted_recursive_glob("bar", "*")
            self.assertListEqual(actual, expected)

            expected = ["foo/bar.doc", "foo/baz/foo.py", "foo/foo.c"]
            actual = self.sorted_recursive_glob("foo", "*")
            self.assertListEqual(actual, expected)

    @mock.patch("os.walk", side_effect=mock_walk)
    def test_file_ending(self, _):
        with self.mock_property("sys.version_info"):
            sys.version_info = (2, 6)

            expected = ["foo/baz/foo.py"]
            actual = self.sorted_recursive_glob("foo", "*.py")
            self.assertListEqual(actual, expected)

            expected = ["bar/foo/baz.c", "foo/foo.c"]
            actual = self.sorted_recursive_glob("*", "*.c")
            self.assertListEqual(actual, expected)

            expected = []
            actual = self.sorted_recursive_glob("*", ".xlsx")
            self.assertListEqual(actual, expected)


def mock_path_join(*_):
    """
    Mock method for `os.path.join`.

    Please refer to the documentation of `os.path.join` for information about
    the provided parameters.
    """

    raise UnicodeDecodeError("foo", b"", 1, 5, "foo")


class TestPathJoinRobust(Base):

    def test_basic(self):
        expected = "path1"
        actual = path_join_robust("path1")
        self.assertEqual(actual, expected)

        actual = path_join_robust(u"path1")
        self.assertEqual(actual, expected)

    def test_join(self):
        for i in range(1, 4):
            paths = ["pathNew"] * i
            expected = "path1" + (self.sep + "pathNew") * i
            actual = path_join_robust("path1", *paths)

            self.assertEqual(actual, expected)

    def test_join_unicode(self):
        for i in range(1, 4):
            paths = [u"pathNew"] * i
            expected = "path1" + (self.sep + "pathNew") * i
            actual = path_join_robust("path1", *paths)

            self.assertEqual(actual, expected)

    @mock.patch("os.path.join", side_effect=mock_path_join)
    def test_join_error(self, _):
        self.assertRaises(locale.Error, path_join_robust, "path")


# Colors
class TestSupportsColor(BaseStdout):

    def test_posix(self):
        with self.mock_property("sys.platform"):
            sys.platform = "Linux"

            with self.mock_property("sys.stdout.isatty") as obj:
                obj.return_value = True
                self.assertTrue(supports_color())

    def test_pocket_pc(self):
        with self.mock_property("sys.platform"):
            sys.platform = "Pocket PC"
            self.assertFalse(supports_color())

    def test_windows_no_ansicon(self):
        with self.mock_property("sys.platform"):
            sys.platform = "win32"

            with self.mock_property("os.environ"):
                os.environ = []

                self.assertFalse(supports_color())

    def test_windows_ansicon(self):
        with self.mock_property("sys.platform"):
            sys.platform = "win32"

            with self.mock_property("os.environ"):
                os.environ = ["ANSICON"]

                with self.mock_property("sys.stdout.isatty") as obj:
                    obj.return_value = True
                    self.assertTrue(supports_color())

    def test_no_isatty_attribute(self):
        with self.mock_property("sys.platform"):
            sys.platform = "Linux"

            with self.mock_property("sys.stdout"):
                sys.stdout = list()
                self.assertFalse(supports_color())

    def test_no_isatty(self):
        with self.mock_property("sys.platform"):
            sys.platform = "Linux"

            with self.mock_property("sys.stdout.isatty") as obj:
                obj.return_value = False
                self.assertFalse(supports_color())


class TestColorize(Base):

    def setUp(self):
        self.text = "house"
        self.colors = ["red", "orange", "yellow",
                       "green", "blue", "purple"]

    @mock.patch("updateHostsFile.supports_color", return_value=False)
    def test_colorize_no_support(self, _):
        for color in self.colors:
            expected = self.text
            actual = colorize(self.text, color)

            self.assertEqual(actual, expected)

    @mock.patch("updateHostsFile.supports_color", return_value=True)
    def test_colorize_support(self, _):
        for color in self.colors:
            expected = color + self.text + Colors.ENDC
            actual = colorize(self.text, color)

            self.assertEqual(actual, expected)


class TestPrintSuccess(BaseStdout):

    def setUp(self):
        super(TestPrintSuccess, self).setUp()
        self.text = "house"

    @mock.patch("updateHostsFile.supports_color", return_value=False)
    def test_print_success_no_support(self, _):
        print_success(self.text)

        expected = self.text + "\n"
        actual = sys.stdout.getvalue()

        self.assertEqual(actual, expected)

    @mock.patch("updateHostsFile.supports_color", return_value=True)
    def test_print_success_support(self, _):
        print_success(self.text)

        expected = Colors.SUCCESS + self.text + Colors.ENDC + "\n"
        actual = sys.stdout.getvalue()

        self.assertEqual(actual, expected)


class TestPrintFailure(BaseStdout):

    def setUp(self):
        super(TestPrintFailure, self).setUp()
        self.text = "house"

    @mock.patch("updateHostsFile.supports_color", return_value=False)
    def test_print_failure_no_support(self, _):
        print_failure(self.text)

        expected = self.text + "\n"
        actual = sys.stdout.getvalue()

        self.assertEqual(actual, expected)

    @mock.patch("updateHostsFile.supports_color", return_value=True)
    def test_print_failure_support(self, _):
        print_failure(self.text)

        expected = Colors.FAIL + self.text + Colors.ENDC + "\n"
        actual = sys.stdout.getvalue()

        self.assertEqual(actual, expected)
# End Helper Functions


if __name__ == "__main__":
    unittest.main()
