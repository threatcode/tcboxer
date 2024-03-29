#! /usr/bin/python3

import os
import random
import re
import shutil
import string
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

unittest.TestLoader.sortTestMethodsUsing = None


class TestKaboxerCommon(unittest.TestCase):
    def setUp(self):
        self.tdname = tempfile.mkdtemp()
        self.fixdir = os.path.join(self.tdname, "fixtures")
        shutil.copytree(os.path.join(os.getcwd(), "tests", "fixtures"), self.fixdir)
        self.nonce = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=10)
        )
        self.app_name = self.nonce
        self.image_name = "kaboxer/" + self.app_name
        self.run_command(
            "sed -i -e s/CONTAINERID/%s/ %s" % (self.app_name, "kaboxer.yaml")
        )
        self.run_command(
            "sed -i -e s,FIXDIR,%s, %s" % (self.fixdir, "kbx-demo.kaboxer.yaml")
        )
        self.run_command("mkdir -p %s/persist" % (self.fixdir,))
        self.tarfile = "%s.tar" % (self.app_name,)
        self.tarpath = os.path.join(self.fixdir, self.tarfile)
        self.clihelpers = [
            "%s-default-kbx" % self.app_name,
            "%s-interactive-kbx" % self.app_name,
            "%s-daemon-kbx" % self.app_name,
        ]
        self.desktopfiles = [
            "kaboxer-%s-default.desktop" % self.app_name,
            "kaboxer-%s-interactive.desktop" % self.app_name,
            "kaboxer-%s-daemon-start.desktop" % self.app_name,
            "kaboxer-%s-daemon-stop.desktop" % self.app_name,
        ]

    def remove_images(self):
        self.run_command(
            "docker images --no-trunc --filter='reference=%s' \
                --format='{{.Repository}}:{{.Tag}}' | xargs -r docker rmi"
            % self.image_name,
        )

    def tearDown(self):
        # self.run_command("docker image ls", show_output=True)
        self.remove_images()
        shutil.rmtree(self.tdname)

    def run_command(self, cmd, show_output=False, wd=None):
        # print ("RUNNING %s" % (cmd,))
        capture_output = not show_output
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(
            cmd, cwd=wd, shell=True, capture_output=capture_output, text=True
        )
        return o

    def check_return_code(self, result, msg=None):
        if msg is None:
            if isinstance(result.args, str):
                cmd = result.args
            else:
                cmd = " ".join(result.args)
            msg = "Error when running '%s'\n" % cmd
            msg += "STDOUT:\n%s\n" % result.stdout
            msg += "STDERR:\n%s\n" % result.stderr
        self.assertEqual(result.returncode, 0, msg)

    def run_and_check_command(self, cmd, msg=None, wd=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, shell=True, capture_output=True, text=True)
        self.check_return_code(o, msg=msg)

    def run_and_check_command_fails(self, cmd, msg=None, wd=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, shell=True, capture_output=True, text=True)
        if msg is None:
            msg = "Unexpected success when running '%s'\n" % cmd
            msg += "STDOUT:\n%s\n" % o.stdout
            msg += "STDERR:\n%s\n" % o.stderr
        self.assertNotEqual(o.returncode, 0, msg)

    def check_output_matches(
        self, result, expected, output="stdout", msg=None, must_fail=False
    ):
        if msg is None:
            if isinstance(result.args, str):
                cmd = result.args
            else:
                cmd = " ".join(result.args)
            msg = "Unexpected output when running '%s'" % cmd
        if must_fail:
            msg += " (%s matches %s)\n" % (output, expected)
        else:
            msg += " (%s doesn't match %s)\n" % (output, expected)
        msg += "STDOUT:\n%s\n" % result.stdout
        msg += "STDERR:\n%s\n" % result.stderr
        value = getattr(result, output)
        if must_fail:
            self.assertFalse(re.search(expected, value, re.MULTILINE), msg)
        else:
            self.assertTrue(re.search(expected, value, re.MULTILINE), msg)

    def run_command_check_stdout_matches(
        self,
        cmd,
        expected,
        input=None,  # noqa: A002
        wd=None,
        fail_msg=None,
        unexpected_msg=None,
    ):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(
            cmd, cwd=wd, input=input, shell=True, capture_output=True, text=True
        )
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, msg=unexpected_msg)

    def run_command_check_stdout_doesnt_match(
        self,
        cmd,
        expected,
        input=None,  # noqa: A002
        wd=None,
        fail_msg=None,
        unexpected_msg=None,
    ):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(
            cmd, cwd=wd, input=input, shell=True, capture_output=True, text=True
        )
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, msg=unexpected_msg, must_fail=True)

    def run_command_check_stderr_matches(
        self,
        cmd,
        expected,
        input=None,  # noqa: A002
        wd=None,
        fail_msg=None,
        unexpected_msg=None,
    ):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(
            cmd, cwd=wd, input=input, shell=True, capture_output=True, text=True
        )
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, output="stderr", msg=unexpected_msg)

    def run_command_check_stderr_doesnt_match(
        self,
        cmd,
        expected,
        input=None,  # noqa: A002
        wd=None,
        fail_msg=None,
        unexpected_msg=None,
    ):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(
            cmd, cwd=wd, input=input, shell=True, capture_output=True, text=True
        )
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(
            o, expected, output="stderr", msg=unexpected_msg, must_fail=True
        )

    def is_image_present(self, version="latest"):
        o = self.run_command(
            "docker image ls | grep -q '%s *%s'" % (self.image_name, version)
        )
        return True if o.returncode == 0 else False

    def is_container_running(self):
        o = self.run_command(
            "docker ps -f name='%s' -f status=running | grep -q %s"
            % (self.app_name, self.app_name)
        )
        return True if o.returncode == 0 else False

    def build(self):
        self.run_and_check_command("kaboxer build")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")

    def build_and_save(self):
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.assertTrue(
            os.path.isfile(self.tarpath),
            "Image not saved (expecting %s)" % (self.tarpath,),
        )

    def build_and_install(self, destdir):
        self.build()
        self.run_and_check_command("kaboxer install --destdir %s" % destdir)
        instdir = os.path.join(destdir, "usr", "local", "share", "kaboxer")
        configfile = "%s.kaboxer.yaml" % self.app_name
        configpath = os.path.join(instdir, configfile)
        self.assertTrue(
            os.path.isfile(configpath),
            "Kaboxer config file not installed (expecting %s)" % configpath,
        )


class TestKaboxerLocally(TestKaboxerCommon):
    def test_log_levels(self):
        self.run_command_check_stderr_matches(
            "kaboxer -v build", "Building container image for %s" % (self.app_name,)
        )
        self.run_command_check_stderr_doesnt_match(
            "kaboxer build", "Building container image for %s" % (self.app_name,)
        )

    def test_build_only(self):
        self.build()

    def test_build_and_save(self):
        self.build_and_save()

    def test_build_and_install(self):
        destdir = os.path.join(self.fixdir, "target")
        self.build_and_install(destdir)

    def test_build_two_apps(self):
        self.nonce2 = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=10)
        )
        self.app_name2 = self.nonce2
        self.image_name2 = "kaboxer/" + self.app_name2
        shutil.copy(
            os.path.join(self.fixdir, "kaboxer.yaml"),
            os.path.join(self.fixdir, "app2.kaboxer.yaml"),
        )
        self.run_command(
            "sed -i -e s/%s/%s/ %s"
            % (self.app_name, self.app_name2, "app2.kaboxer.yaml")
        )
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.assertTrue(
            os.path.isfile(self.tarpath),
            "Image not saved (expecting %s)" % (self.tarpath,),
        )
        self.run_and_check_command(
            "docker image ls | grep -q '%s *%s'" % (self.image_name2, "latest"),
            "No docker image present for app2 after build",
        )
        self.tarfile2 = "%s.tar" % (self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir, self.tarfile2)
        self.assertTrue(
            os.path.isfile(self.tarpath2),
            "Image not saved for app2 (expecting %s)" % self.tarpath2,
        )

    def test_build_one_app_only(self):
        self.nonce2 = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=10)
        )
        self.app_name2 = self.nonce2
        self.image_name2 = "kaboxer/" + self.app_name2
        shutil.copy(
            os.path.join(self.fixdir, "kaboxer.yaml"),
            os.path.join(self.fixdir, "app2.kaboxer.yaml"),
        )
        self.run_command(
            "sed -i -e s/%s/%s/ %s"
            % (self.app_name, self.app_name2, "app2.kaboxer.yaml")
        )
        self.run_and_check_command("kaboxer build --save %s" % (self.app_name,))
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.assertTrue(
            os.path.isfile(self.tarpath),
            "Image not saved (expecting %s)" % (self.tarpath,),
        )
        self.run_and_check_command_fails(
            "docker image ls | grep -q '%s *%s'" % (self.image_name2, "latest"),
            "Image for app2 unexpectedly present after build",
        )
        self.tarfile2 = "%s.tar" % (self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir, self.tarfile2)
        self.assertFalse(
            os.path.isfile(self.tarpath2),
            "Image saved for app2 (as %s)" % (self.tarpath2,),
        )

    def test_build_then_separate_save(self):
        self.build()
        self.run_and_check_command("kaboxer save %s %s" % (self.app_name, self.tarfile))
        self.assertTrue(
            os.path.isfile(self.tarpath),
            "Image not saved (expecting %s)" % self.tarpath,
        )

    def test_build_clean(self):
        self.build_and_save()
        self.run_and_check_command("kaboxer clean")
        self.assertFalse(
            os.path.isfile(self.tarpath),
            "Image still present after clean (expecting %s)" % self.tarfile,
        )
        for i in self.desktopfiles:
            self.assertFalse(
                os.path.isfile(os.path.join(self.fixdir, i)),
                "%s file still present after kaboxer clean" % (i,),
            )

    def test_purge(self):
        self.build()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(
            self.is_image_present(), "Docker image still present after kaboxer purge"
        )

    def test_purge_non_existing_app(self):
        self.run_and_check_command("kaboxer purge --prune non-existing-app")

    def test_run(self):
        self.build_and_save()
        self.run_command_check_stdout_matches(
            "kaboxer run %s" % self.app_name, "Hi there"
        )
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(
            self.is_image_present(), "Docker image still present after kaboxer purge"
        )
        self.run_and_check_command("kaboxer run %s" % (self.app_name,))

    def test_run_freshly_built_image(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer -vv run %s" % self.app_name, "Hi there"
        )

    def test_run_alias_start(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer start %s" % self.app_name, "Hi there"
        )

    def test_run_with_one_arg(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer start %s Bob" % self.app_name, "Hi Bob"
        )

    def test_run_with_some_args(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer start %s alice , 'b0b m4rl3y' and 'others!'" % self.app_name,
            "Hi alice , b0b m4rl3y and others!",
        )

    def test_run_with_double_dash(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer start %s -- --help" % self.app_name, "Hi --help"
        )

    def test_run_interactive(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer run --component interactive %s" % self.app_name,
            "Hello alice",
            input="alice\n",
        )

    def test_run_after_purge(self):
        self.build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(), "Docker image still present after kaboxer purge"
        )
        self.run_command_check_stdout_matches(
            "kaboxer run %s" % self.app_name, "Hi there"
        )

    def test_run_detach(self):
        self.build()
        self.run_and_check_command(
            "kaboxer run --component=daemon --detach %s" % self.app_name
        )
        self.assertTrue(
            self.is_container_running(),
            "Docker container is not running after kaboxer run --detach",
        )
        self.run_and_check_command("kaboxer stop --component=daemon %s" % self.app_name)
        self.assertFalse(
            self.is_container_running(),
            "Docker container is still running after kaboxer stop",
        )

    def test_run_reuse_container_when_non_existing(self):
        # Add reuse_container, just after 'executable:', for each component
        # (although we only need it for the exec component here)
        self.run_command(
            r"sed -i '/executable:/a \    reuse_container: true' %s" % "kaboxer.yaml"
        )
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer run %s" % self.app_name, "Hi there"
        )

    def test_run_reuse_container_for_real(self):
        # Add reuse_container, just after 'executable:', for each component
        # (although we only need it for the exec component here)
        self.run_command(
            r"sed -i '/executable:/a \    reuse_container: true' %s" % "kaboxer.yaml"
        )
        self.build()

        # First script, start a sleeping container in the background
        #
        # `run_and_check_command()` automatically sets `capture_output=True`,
        # and as a consequence Python waits for the end of the process despite
        # the trailing `&`. Not what we want. So we need to use `run_command()`
        # with `show_output=True` (aka. `capture_output=False`) instead.
        # I know, it's a bit convoluted...
        self.run_command(
            "kaboxer run --component=exec %s "
            "-- bash -c 'echo sleeping > /tmp/my-special-file && sleep 30' &"
            % self.app_name,
            show_output=True,
        )

        # Wait a bit to be sure that the container is up
        time.sleep(10)

        # Second script, reuse the first container, read the special file
        self.run_command_check_stdout_matches(
            "kaboxer run --component=exec %s -- cat /tmp/my-special-file"
            % self.app_name,
            "sleeping",
        )

    def test_run_host_network(self):
        # Add network configuration, just after 'executable:', for each component
        self.run_command(
            r"sed -i '/executable:/a \    networks:\n      - host' %s" % "kaboxer.yaml"
        )
        self.build()
        # Get the network interfaces from the host
        o = self.run_command("ls -1 /sys/class/net")
        host_net = o.stdout
        # Check that we get the same from within the container
        self.run_command_check_stdout_matches(
            "kaboxer run --component=exec %s ls -1 /sys/class/net" % self.app_name,
            host_net,
        )

    def test_stop_non_existing_app(self):
        self.run_and_check_command_fails("kaboxer stop non-existing-app")

    def test_stop_non_headless_app(self):
        self.run_and_check_command_fails("kaboxer stop %s" % self.app_name)

    def test_stop_headless_app_not_running(self):
        self.run_and_check_command_fails(
            "kaboxer stop --component=daemon %s" % self.app_name
        )

    def test_load_purge(self):
        self.build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(
            self.is_image_present(), "Docker image still present after kaboxer purge"
        )
        self.run_and_check_command("kaboxer load %s %s" % (self.app_name, self.tarfile))
        self.assertTrue(
            self.is_image_present("1.0"), "No Docker image present after load"
        )
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(
            self.is_image_present("1.0"),
            "Docker image still present after kaboxer purge",
        )

    def test_install(self):
        destdir = os.path.join(self.fixdir, "target")
        self.build_and_install(destdir)
        instdir = os.path.join(destdir, "usr", "local", "share", "kaboxer")
        installed_tarfile = os.path.join(instdir, self.tarfile)
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile unexpectedly installed (as %s)" % installed_tarfile,
        )

    def test_install_with_tarball(self):
        self.build_and_save()
        destdir = os.path.join(self.fixdir, "target")
        self.run_and_check_command("kaboxer install --tarball --destdir %s" % destdir)
        instdir = os.path.join(destdir, "usr", "local", "share", "kaboxer")
        installed_tarfile = os.path.join(instdir, self.tarfile)
        self.assertTrue(
            os.path.isfile(installed_tarfile),
            "Tarfile not installed (expecting %s)" % installed_tarfile,
        )
        os.unlink(installed_tarfile)
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile still present after unlink (%s)" % installed_tarfile,
        )
        self.run_and_check_command("kaboxer install --destdir %s" % destdir)
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile present after install (%s)" % installed_tarfile,
        )
        self.run_and_check_command(
            "kaboxer install --tarball --destdir %s --prefix %s" % (destdir, "/usr")
        )
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Default tarfile present after install to non-default dir (%s)"
            % installed_tarfile,
        )
        instdir = os.path.join(destdir, "usr", "share", "kaboxer")
        installed_tarfile = os.path.join(instdir, self.tarfile)
        self.assertTrue(
            os.path.isfile(installed_tarfile),
            "Tarfile not installed (expecting %s)" % installed_tarfile,
        )

    def assert_generated_files(self, instdir, generated_files, manual_files, exe=False):
        # Auto-generated files should have been built and installed
        for f in generated_files:
            built_file = os.path.join(self.fixdir, f)
            self.assertTrue(
                os.path.isfile(built_file),
                "No generated file '%s' present in build dir" % f,
            )
            if exe:
                self.assertTrue(
                    os.access(built_file, os.X_OK),
                    "Generated file '%s' not executable in build dir" % f,
                )
            else:
                self.assertFalse(
                    os.access(built_file, os.X_OK),
                    "Generated file '%s' executable in build dir" % f,
                )
            installed_file = os.path.join(instdir, f)
            self.assertTrue(
                os.path.isfile(installed_file),
                "No generated file '%s' present in install dir" % f,
            )
            if exe:
                self.assertTrue(
                    os.access(installed_file, os.X_OK),
                    "Generated file '%s' not executable in install dir" % f,
                )
            else:
                self.assertFalse(
                    os.access(installed_file, os.X_OK),
                    "Generated file '%s' executable in install dir" % f,
                )
        # Manual files should not have been installed
        for f in manual_files:
            installed_file = os.path.join(instdir, f)
            self.assertFalse(
                os.path.isfile(installed_file),
                "Manual file '%s' present in install dir" % f,
            )

    def assert_manual_files(self, instdir, generated_files, manual_files, exe=False):
        # Auto-generated files should NOT have been built or installed
        for f in generated_files:
            built_file = os.path.join(self.fixdir, f)
            self.assertFalse(
                os.path.isfile(built_file),
                "Generated file '%s' present in build dir" % f,
            )
            installed_file = os.path.join(instdir, f)
            self.assertFalse(
                os.path.isfile(installed_file),
                "Generated file '%s' present in install dir" % f,
            )
        # Manual files should have been installed
        for f in manual_files:
            installed_file = os.path.join(instdir, f)
            self.assertTrue(
                os.path.isfile(installed_file),
                "No manual file '%s' present in install dir" % f,
            )
            if exe:
                self.assertTrue(
                    os.access(installed_file, os.X_OK),
                    "Manual file '%s' not executable in install dir" % f,
                )
            else:
                self.assertFalse(
                    os.access(installed_file, os.X_OK),
                    "Manual file '%s' executable in install dir" % f,
                )

    def build_install_assert_cli_helpers(self, generated=False):
        destdir = os.path.join(self.fixdir, "target")
        self.build_and_install(destdir)

        instdir = os.path.join(destdir, "usr", "local", "bin")
        generated_files = self.clihelpers
        manual_files = ["helper-kbx"]
        if generated:
            self.assert_generated_files(
                instdir, generated_files, manual_files, exe=True
            )
        else:
            self.assert_manual_files(instdir, generated_files, manual_files, exe=True)
        return instdir

    def test_generated_cli_helpers(self):
        bindir = self.build_install_assert_cli_helpers(generated=True)
        # Run cli helpers
        cmd = os.path.join(bindir, "%s-default-kbx" % self.app_name)
        self.run_command_check_stdout_matches(cmd, "Hi there")
        self.run_command_check_stdout_matches(cmd + " Carol", "Hi Carol")
        self.run_command_check_stdout_matches(cmd + " foo bar??", "Hi foo bar??")
        self.run_command_check_stdout_matches(cmd + " --help", "Hi --help")
        cmd = os.path.join(bindir, "%s-daemon-kbx" % self.app_name)
        self.run_and_check_command_fails(cmd)
        self.run_and_check_command(cmd + " start")
        self.assertTrue(
            self.is_container_running(),
            "Docker container is not running after kaboxer run --detach",
        )
        self.run_and_check_command(cmd + " stop")
        self.assertFalse(
            self.is_container_running(),
            "Docker container is still running after kaboxer stop",
        )

    def test_generated_cli_helper_single(self):
        # Remove components (assume components is at the end of the file)
        self.run_command("sed -i '/components:/Q' %s" % "kaboxer.yaml")
        # Add one and only one component
        with open(os.path.join(self.fixdir, "kaboxer.yaml"), "a") as outfile:
            outfile.write(
                """components:
  default:
    run_mode: cli
    executable: /run.sh hi
"""
            )
        # In this case, cli helper shouldn't have 'component' in their name
        self.clihelpers = ["%s-kbx" % self.app_name]
        # Run the tests
        bindir = self.build_install_assert_cli_helpers(generated=True)
        cmd = os.path.join(bindir, self.clihelpers[0])
        self.run_command_check_stdout_matches(cmd, "Hi there")

    def test_manual_cli_helpers(self):
        # we want to test that kaboxer sets the executable bit when installing helpers
        self.assertFalse(
            os.access(os.path.join(self.fixdir, "helper-kbx"), os.X_OK),
            "%s is already executable, we don't want that" % "helper-kbx",
        )
        # Add cli-helpers to the install section
        with open(os.path.join(self.fixdir, "kaboxer.yaml"), "a") as outfile:
            outfile.write(
                """install:
  cli-helpers:
    - helper-kbx
"""
            )
        # Run the test
        self.build_install_assert_cli_helpers(generated=False)

    def build_install_assert_desktop_files(self, generated=False):
        destdir = os.path.join(self.fixdir, "target")
        self.build_and_install(destdir)

        instdir = os.path.join(destdir, "usr", "local", "share", "applications")
        generated_files = self.desktopfiles
        manual_files = ["sleeper.desktop"]
        if generated:
            self.assert_generated_files(instdir, generated_files, manual_files)
        else:
            self.assert_manual_files(instdir, generated_files, manual_files)

    def test_generated_desktop_files(self):
        self.build_install_assert_desktop_files(generated=True)

    def test_manual_desktop_files(self):
        # Add desktop-files to the install section
        with open(os.path.join(self.fixdir, "kaboxer.yaml"), "a") as outfile:
            outfile.write(
                """install:
  desktop-files:
    - sleeper.desktop
"""
            )
        # Run tests
        self.build_install_assert_desktop_files(generated=False)

    def test_install_icons(self):
        destdir = os.path.join(self.fixdir, "target")
        self.build_and_install(destdir)

        instdir = os.path.join(destdir, "usr", "local", "share", "icons")
        shipped_icon = os.path.join(instdir, "kaboxer-%s.svg" % self.app_name)
        self.assertTrue(
            os.path.isfile(shipped_icon),
            "Shipped icon not installed (expecting %s)" % shipped_icon,
        )
        extracted_icon = os.path.join(instdir, "kaboxer-%s.png" % self.app_name)
        self.assertTrue(
            os.path.isfile(extracted_icon),
            "Extracted icon not installed (expecting %s)" % extracted_icon,
        )

    def test_meta_files(self):
        self.run_and_check_command("kaboxer build")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s version" % self.app_name, "1.0"
        )
        self.run_command_check_stdout_matches(
            "kaboxer get-upstream-version %s" % self.app_name, "1.0"
        )
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s packaging-revision" % self.app_name, "3"
        )
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s Dockerfile" % self.app_name,
            "FROM debian:stable-slim",
        )
        self.run_command("docker image rm %s:latest" % self.image_name)
        self.run_and_check_command("kaboxer build --version 1.1")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s version" % self.app_name, "1.1"
        )
        self.run_command("docker image rm %s:latest" % self.image_name)
        self.run_and_check_command_fails(
            "kaboxer build %s --version 2.0" % self.app_name
        )
        self.run_and_check_command("kaboxer build --version 2.0 --ignore-version")
        self.run_command("docker image rm %s:latest" % self.image_name)
        self.run_command("docker image rm %s:2.0" % self.image_name)
        self.run_command(
            "sed -i -e s/1.0/1.5/ %s" % (os.path.join(self.fixdir, "Dockerfile"),)
        )
        self.run_and_check_command_fails("kaboxer build %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(), "Docker image present after failed build"
        )
        self.run_and_check_command("kaboxer build --ignore-version")
        self.assertTrue(self.is_image_present(), "No Docker image present after build")
        self.run_command("docker image rm %s:latest" % (self.image_name,))
        self.run_command("docker image rm %s:1.5" % (self.image_name,))

    def test_list_alias_ls(self):
        self.run_and_check_command("kaboxer ls")

    def test_list_local(self):
        self.run_and_check_command("kaboxer build")
        self.run_command_check_stdout_matches(
            "kaboxer list --all", r"^%s\s+-\s+1.0\s" % self.app_name
        )
        self.run_command_check_stdout_matches("kaboxer list --all", "Installed version")
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --all --skip-headers", "Installed version"
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --all --skip-headers", r"^%s\s+-\s+1.0\s" % self.app_name
        )
        self.remove_images()
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --installed", r"^%s\s+-\s+1.0\s" % self.app_name
        )

    def test_list_local_with_remote_registry_configured(self):
        # Non-regression test where the code was using only the remote image
        # name and where kaboxer build + run would not find the local image
        self.run_and_check_command("kaboxer build kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer -vv list --available --installed --skip-headers", r"kbx-demo"
        )

    def test_local_upgrades(self):
        self.run_and_check_command("kaboxer build --save --version 1.1")
        os.rename(
            os.path.join(self.fixdir, self.app_name + ".tar"),
            os.path.join(self.fixdir, self.app_name + "-1.1.tar"),
        )
        self.remove_images()
        self.run_and_check_command("kaboxer build --save --version 1.0")
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --installed", r"^%s\s+1.0\s" % self.app_name
        )
        self.run_and_check_command("kaboxer prepare %s=1.0" % self.app_name)
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"^%s\s+1.0\s" % self.app_name
        )
        os.rename(
            os.path.join(self.fixdir, self.app_name + ".tar"),
            os.path.join(self.fixdir, self.app_name + "-1.0.tar"),
        )
        shutil.copy(
            os.path.join(self.fixdir, self.app_name + "-1.1.tar"),
            os.path.join(self.fixdir, self.app_name + ".tar"),
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --upgradeable", r"^%s\s+1.0\s+1.1\s" % self.app_name
        )
        self.run_and_check_command_fails("kaboxer run %s=1.1" % (self.app_name,))
        self.run_and_check_command("kaboxer upgrade %s" % self.app_name)
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"^%s\s+1.1\s" % self.app_name
        )
        self.run_and_check_command("kaboxer run --version 1.1 %s" % self.app_name)


class TestKaboxerWithRegistryCommon(TestKaboxerCommon):
    def setUp(self):
        super().setUp()
        self.registry_port = 5999
        self.app_name = "localhost:%s/kbx-demo" % (self.registry_port,)
        self.image_name = self.app_name
        self.run_command(
            "docker run -d -p %d:5000 --name %s "
            "-v %s:/var/lib/registry registry:2"
            % (self.registry_port, self.nonce, os.path.join(self.fixdir, "registry")),
        )

    def remove_images(self):
        super().remove_images()
        for v in ["1.0", "1.1", "1.2", "1.5", "2.0", "latest", "current"]:
            for i in ["kaboxer", "localhost:%s" % (self.registry_port,)]:
                self.run_command("docker image rm %s/kbx-demo:%s" % (i, v))
        self.run_command("docker image prune -f")

    def tearDown(self):
        # self.run_command("docker image ls", show_output=True)
        self.run_command(
            "docker container exec %s find /var/lib/registry "
            "-mindepth 1 -delete" % self.nonce,
        )
        self.run_command("docker container stop %s" % (self.nonce,))
        self.run_command("docker container rm -v %s" % (self.nonce,))
        super().tearDown()


class TestKaboxerWithRegistry(TestKaboxerWithRegistryCommon):
    def test_build_with_push_and_fetch(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer push kbx-demo")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name,
        )
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches(
            "docker image ls",
            self.app_name,
            unexpected_msg="Image not fetched from registry",
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World")

    def test_build_then_push_and_fetch(self):
        self.run_and_check_command("kaboxer build kbx-demo")
        # self.run_command("docker image ls", show_output=True)
        self.run_and_check_command("kaboxer push kbx-demo")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name,
        )
        # self.run_command("docker image ls", show_output=True)
        self.run_and_check_command("kaboxer -vv prepare kbx-demo")
        self.run_command_check_stdout_matches(
            "docker image ls",
            self.app_name,
            unexpected_msg="Image not fetched from registry",
        )
        # self.run_command("docker image ls", show_output=True)
        self.run_command_check_stdout_matches("kaboxer -vv run kbx-demo", "Hello World")

    def test_list_registry(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.remove_images()
        self.run_command_check_stdout_matches(
            "kaboxer -v -v list --available",
            r"kbx-demo\s+[-a-z]+\s+1.0",
            unexpected_msg="Image not available in registry",
        )
        self.assertFalse(
            self.is_image_present(), msg="Image %s present" % (self.app_name,)
        )
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.assertTrue(
            self.is_image_present("1.0"), msg="Image %s absent" % (self.app_name,)
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --available",
            r"kbx-demo\s+[-a-z]+\s+1.0",
            unexpected_msg="Image not available in registry",
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --installed",
            r"kbx-demo\s+1.0",
            unexpected_msg="Image not installed",
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer list --available",
            r"kbx-demo\s+[-a-z]+\s+1.1",
            unexpected_msg="Image not available in registry",
        )
        self.remove_images()
        self.assertFalse(
            self.is_image_present("1.0"),
            msg="Image %s present at version %s" % (self.app_name, "1.0"),
        )
        self.assertFalse(
            self.is_image_present("1.1"),
            msg="Image %s present at version %s" % (self.app_name, "1.1"),
        )
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo", r"Hello World 1.0"
        )
        self.run_and_check_command("kaboxer list --installed")
        self.run_command_check_stdout_matches(
            "kaboxer list --installed",
            r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed",
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --upgradeable", r"kbx-demo\s+1.0\s+1.1"
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --all",
            r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed",
        )
        self.run_command_check_stdout_matches(
            "kaboxer list --all",
            r"kbx-demo\s+[-a-z0-9.]+\s+1.1",
            unexpected_msg="Image 1.1 not listed as available",
        )
        # self.run_command_check_stdout_matches(
        #     "kaboxer list --all", "kbx-demo: .*1.1 \[available\]",
        #     unexpected_msg="Image 1.1 not listed as available")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches(
            "kaboxer list --installed",
            r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed",
        )
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo", r"Hello World 1.0"
        )
        self.run_and_check_command("kaboxer upgrade kbx-demo=1.1")
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo", r"Hello World 1.1"
        )
        self.run_and_check_command("kaboxer upgrade kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo", r"Hello World 1.2"
        )

    def test_run_version(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer run --version=1.0 kbx-demo", "Hello World 1.0"
        )
        self.run_and_check_command_fails("kaboxer run --version=1.1 kbx-demo")
        self.run_and_check_command("kaboxer upgrade kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer run --version=1.1 kbx-demo", "Hello World 1.1"
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.1")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.run_and_check_command_fails("kaboxer run --version=1.0 kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.1")
        self.run_command_check_stdout_doesnt_match(
            "kaboxer run kbx-demo", "Hello World 1.2"
        )
        self.remove_images()
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.2")

    def test_history(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_command_check_stdout_matches(
            "kaboxer run --component history kbx-demo | wc -l", "2"
        )

    def test_upgrade_script(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_command_check_stdout_matches(
            "kaboxer upgrade kbx-demo=1.1",
            "Upgrading from 1.0 to 1.1 with persisted data 1.0",
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.1")
        self.run_command_check_stdout_matches(
            "kaboxer run --component history kbx-demo", "3 1.0"
        )

    def test_upgrade_no_scripts(self):
        self.run_and_check_command(
            "grep -q '^COPY pre-upgrade post-upgrade ' %s" % "Dockerfile"
        )
        self.run_command(
            "sed -i '/^COPY pre-upgrade post-upgrade /d' %s" % "Dockerfile"
        )
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.0")
        self.run_and_check_command("kaboxer upgrade kbx-demo=1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World 1.1")


class TestKaboxerWithPublicRegistries(TestKaboxerCommon):
    def test_list_from_docker_hub(self):
        workdir = os.path.join(self.fixdir, "hello-cli-docker-hub")
        self.run_command_check_stdout_matches(
            "kaboxer list --available --skip-headers", "^hello-cli", wd=workdir
        )

    def test_list_from_gitlab(self):
        workdir = os.path.join(self.fixdir, "hello-cli-gitlab")
        self.run_command_check_stdout_matches(
            "kaboxer list --available --skip-headers", "^hello-cli", wd=workdir
        )


class TestKbxbuilder(TestKaboxerWithRegistryCommon):
    def setUp(self):
        super().setUp()
        appsfile = os.path.join(self.fixdir, "kbxbuilder.apps.yaml")
        with open(appsfile) as f:
            y = yaml.safe_load(f)
        y["kbx-demo"]["git_url"] = os.getcwd()
        with open(appsfile, "w") as f:
            f.write(yaml.dump(y))

    def tearDown(self):
        if False:
            self.run_command("cat data/kbx-builder.log", show_output=True)
            self.run_command("cat build-logs/kbx-demo.log", show_output=True)
            self.run_command("cat data/status.yaml", show_output=True)

        super().tearDown()

    def test_build_one(self):
        self.run_command_check_stdout_matches(
            "kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO SUCCEEDED"
        )
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name,
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World")

    def test_build_failure(self):
        self.run_command(
            "sed -i -e s/subdir/XXX/ %s"
            % (os.path.join(self.fixdir, "kbxbuilder.apps.yaml"),)
        )
        self.run_command_check_stdout_matches(
            "kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO FAILED"
        )

    def test_build_all(self):
        self.run_and_check_command("kbxbuilder build-all")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name,
        )
        self.run_command_check_stdout_matches("kaboxer run kbx-demo", "Hello World")

    def test_build_as_needed(self):
        self.run_command_check_stdout_matches(
            "kbxbuilder build-as-needed", "BUILD OF KBX-DEMO SUCCEEDED"
        )
        self.run_command_check_stderr_matches(
            "kbxbuilder build-as-needed", "Build of kbx-demo not needed"
        )
        self.run_command_check_stdout_matches(
            "kbxbuilder build-all", "BUILD OF KBX-DEMO SUCCEEDED"
        )


if __name__ == "__main__":
    if "USE_SYSTEM_WIDE_KABOXER" not in os.environ:
        binpath = Path(__file__).parent / Path("bin")
        os.environ["PATH"] = "%s:%s" % (binpath.absolute(), os.environ["PATH"])
    unittest.main()
