#! /usr/bin/python3

import os
import random
import re
import shutil
import string
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

unittest.TestLoader.sortTestMethodsUsing = None


class TestKaboxerCommon(unittest.TestCase):
    def setUp(self):
        self.tdname = tempfile.mkdtemp()
        self.fixdir = os.path.join(self.tdname, 'fixtures')
        shutil.copytree(os.path.join(os.getcwd(), 'tests', 'fixtures'),
                        self.fixdir)
        self.nonce = ''.join(
            random.choices(string.ascii_lowercase + string.digits, k=10))
        self.app_name = self.nonce
        self.image_name = 'kaboxer/' + self.app_name
        self.run_command(
            "sed -i -e s/CONTAINERID/%s/ %s" % (self.app_name, 'kaboxer.yaml'))
        self.run_command(
            "sed -i -e s,FIXDIR,%s, %s" % (self.fixdir,
                                           'kbx-demo.kaboxer.yaml'))
        self.run_command("mkdir -p %s/persist" % (self.fixdir,))
        self.tarfile = "%s.tar" % (self.app_name,)
        self.tarpath = os.path.join(self.fixdir, self.tarfile)
        self.desktopfiles = [
            "kaboxer-%s-default.desktop" % self.app_name,
            "kaboxer-%s-daemon-start.desktop" % self.app_name,
            "kaboxer-%s-daemon-stop.desktop" % self.app_name,
        ]

    def remove_images(self):
        self.run_command("docker images --no-trunc --filter='reference=%s' \
                --format='{{.Repository}}:{{.Tag}}' | xargs -r docker rmi"
                % self.image_name, ignore_output=True)

    def tearDown(self):
        # self.run_command("docker image ls")
        self.remove_images()
        shutil.rmtree(self.tdname)

    def run_command(self, cmd, ignore_output=False, wd=None):
        # print ("RUNNING %s" % (cmd,))
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, shell=True,
                           capture_output=ignore_output)
        return o.returncode

    def check_return_code(self, result, msg=None):
        if msg is None:
            if isinstance(result.args, str):
                cmd = result.args
            else:
                cmd = ' '.join(result.args)
            msg = "Error when running '%s'\n" % cmd
            msg += "STDOUT:\n%s\n" % result.stdout
            msg += "STDERR:\n%s\n" % result.stderr
        self.assertEqual(result.returncode, 0, msg)

    def run_and_check_command(self, cmd, msg=None, wd=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, shell=True,
                           capture_output=True, text=True)
        self.check_return_code(o, msg=msg)

    def run_and_check_command_fails(self, cmd, msg=None, wd=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, shell=True,
                           capture_output=True, text=True)
        if msg is None:
            msg = "Unexpected success when running '%s'\n" % cmd
            msg += "STDOUT:\n%s\n" % o.stdout
            msg += "STDERR:\n%s\n" % o.stderr
        self.assertNotEqual(o.returncode, 0, msg)

    def check_output_matches(self, result, expected, output='stdout', msg=None,
                             must_fail=False):
        if msg is None:
            if isinstance(result.args, str):
                cmd = result.args
            else:
                cmd = ' '.join(result.args)
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

    def run_command_check_stdout_matches(self, cmd, expected, input=None, wd=None,
                                         fail_msg=None, unexpected_msg=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, input=input, shell=True,
                           capture_output=True, text=True)
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, msg=unexpected_msg)

    def run_command_check_stdout_doesnt_match(self, cmd, expected, input=None, wd=None,
                                              fail_msg=None, unexpected_msg=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, input=input, shell=True,
                           capture_output=True, text=True)
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, msg=unexpected_msg,
                                  must_fail=True)

    def run_command_check_stderr_matches(self, cmd, expected, input=None, wd=None,
                                         fail_msg=None, unexpected_msg=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, input=input, shell=True,
                           capture_output=True, text=True)
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, output='stderr',
                                  msg=unexpected_msg)

    def run_command_check_stderr_doesnt_match(self, cmd, expected, input=None, wd=None,
                                              fail_msg=None, unexpected_msg=None):
        if wd is None:
            wd = self.fixdir
        o = subprocess.run(cmd, cwd=wd, input=input, shell=True,
                           capture_output=True, text=True)
        self.check_return_code(o, msg=fail_msg)
        self.check_output_matches(o, expected, output='stderr',
                                  msg=unexpected_msg, must_fail=True)

    def is_image_present(self, version='latest'):
        if self.run_command("docker image ls | grep -q '%s *%s'" %
                            (self.image_name, version)) == 0:
            return True
        else:
            return False

    def is_container_running(self):
        if self.run_command("docker ps -f name='%s' -f status=running | grep -q %s" %
                            (self.app_name, self.app_name)) == 0:
            return True
        else:
            return False

    def build(self):
        self.run_and_check_command("kaboxer build")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")


class TestKaboxerLocally(TestKaboxerCommon):
    def test_build_only(self):
        self.build()

    def test_log_levels(self):
        self.run_command_check_stderr_matches(
            "kaboxer -v build",
            "Building container image for %s" % (self.app_name,))
        self.run_command_check_stderr_doesnt_match(
            "kaboxer build",
            "Building container image for %s" % (self.app_name,))

    def test_build_and_save(self):
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))

    def test_build_two_apps(self):
        self.nonce2 = ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=10))
        self.app_name2 = self.nonce2
        self.image_name2 = 'kaboxer/' + self.app_name2
        shutil.copy(os.path.join(self.fixdir, 'kaboxer.yaml'),
                    os.path.join(self.fixdir, 'app2.kaboxer.yaml'))
        self.run_command("sed -i -e s/%s/%s/ %s" %
                         (self.app_name, self.app_name2, 'app2.kaboxer.yaml'))
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))
        self.assertEqual(self.run_command("docker image ls | grep -q '%s *%s'" %
                                          (self.image_name2, 'latest')),
                         0, "No docker image present for app2 after build")
        self.tarfile2 = "%s.tar" % (self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir, self.tarfile2)
        self.assertTrue(os.path.isfile(self.tarpath2),
                        "Image not saved for app2 (expecting %s)" %
                        self.tarpath2)

    def test_build_one_app_only(self):
        self.nonce2 = ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=10))
        self.app_name2 = self.nonce2
        self.image_name2 = 'kaboxer/' + self.app_name2
        shutil.copy(os.path.join(self.fixdir, 'kaboxer.yaml'),
                    os.path.join(self.fixdir, 'app2.kaboxer.yaml'))
        self.run_command("sed -i -e s/%s/%s/ %s" %
                         (self.app_name, self.app_name2, 'app2.kaboxer.yaml'))
        self.run_and_check_command("kaboxer build --save %s" % (self.app_name,))
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))
        self.assertEqual(self.run_command("docker image ls | grep -q '%s *%s'" %
                                          (self.image_name2, 'latest')),
                         1, "Image for app2 unexpectedly present after build")
        self.tarfile2 = "%s.tar" % (self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir, self.tarfile2)
        self.assertFalse(os.path.isfile(self.tarpath2),
                         "Image saved for app2 (as %s)" % (self.tarpath2,))

    def test_build_then_separate_save(self):
        self.build()
        self.run_and_check_command("kaboxer save %s %s" %
                                   (self.app_name, self.tarfile))
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % self.tarpath)

    def test_build_clean(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer clean")
        self.assertFalse(os.path.isfile(self.tarpath),
                         "Image still present after clean (expecting %s)" %
                         self.tarfile)
        for i in self.desktopfiles:
            self.assertFalse(os.path.isfile(os.path.join(self.fixdir, i)),
                             "%s file still present after kaboxer clean" % (i,))

    def test_purge(self):
        self.build()
        self.run_and_check_command(
            "kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_purge_non_existing_app(self):
        self.run_and_check_command(
            "kaboxer purge --prune non-existing-app")

    def test_run(self):
        self.test_build_and_save()
        self.run_command_check_stdout_matches("kaboxer run %s" % self.app_name,
                                              "Hi there")
        self.run_and_check_command(
            "kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer run %s" % (self.app_name,))

    def test_run_freshly_built_image(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer -vv run %s" % self.app_name, "Hi there")

    def test_run_interactive(self):
        self.build()
        self.run_command_check_stdout_matches(
            "kaboxer run --component interactive %s" % self.app_name,
            "Hello alice", input="alice\n")

    def test_run_after_purge(self):
        self.test_build_and_save()
        self.run_and_check_command(
            "kaboxer purge --prune %s" % self.app_name)
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_command_check_stdout_matches("kaboxer run %s" % self.app_name,
                                              "Hi there")

    def test_run_detach(self):
        self.build()
        self.run_and_check_command(
            "kaboxer run --component=daemon --detach %s" % self.app_name)
        self.assertTrue(self.is_container_running(),
                        "Docker container is not running after kaboxer run --detach")
        self.run_and_check_command(
            "kaboxer stop --component=daemon %s" % self.app_name)
        self.assertFalse(self.is_container_running(),
                        "Docker container is still running after kaboxer stop")

    def test_load_purge(self):
        self.test_build_and_save()
        self.run_and_check_command(
            "kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer load %s %s" %
                                   (self.app_name, self.tarfile))
        self.assertTrue(self.is_image_present("1.0"),
                        "No Docker image present after load")
        self.run_and_check_command(
            "kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present("1.0"),
                         "Docker image still present after kaboxer purge")

    def test_install(self):
        self.test_build_and_save()
        self.run_and_check_command(
            "kaboxer install --tarball --destdir %s" %
            os.path.join(self.fixdir, 'target'))
        installed_tarfile = os.path.join(
            self.fixdir, 'target', 'usr', 'local', 'share', 'kaboxer',
            self.tarfile)
        self.assertTrue(
            os.path.isfile(installed_tarfile),
            "Tarfile not installed (expecting %s)" % installed_tarfile)
        os.unlink(installed_tarfile)
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile still present after unlink (%s)" % installed_tarfile)
        self.run_and_check_command(
            "kaboxer install --destdir %s" %
            os.path.join(self.fixdir, 'target'))
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile present after install (%s)" % installed_tarfile)
        self.run_and_check_command(
            "kaboxer install --tarball --destdir %s --prefix %s" %
            (os.path.join(self.fixdir, 'target'), '/usr'))
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Default tarfile present after install to non-default dir (%s)" %
            installed_tarfile)
        installed_tarfile_usr = os.path.join(
            self.fixdir, 'target', 'usr', 'share', 'kaboxer', self.tarfile)
        self.assertTrue(
            os.path.isfile(installed_tarfile_usr),
            "Tarfile not installed (expecting %s)" % installed_tarfile)

    def test_install_no_tarball(self):
        self.build()
        self.run_and_check_command(
            "kaboxer install --destdir %s" % (
                os.path.join(self.fixdir, 'target')))
        installed_tarfile = os.path.join(
            self.fixdir, 'target', 'usr', 'local', 'share', 'kaboxer',
            self.tarfile)
        self.assertFalse(
            os.path.isfile(installed_tarfile),
            "Tarfile unexpectedly installed (as %s)" % installed_tarfile)

    def test_auto_desktop_files(self):
        self.test_build_and_save()
        for i in self.desktopfiles:
            self.assertTrue(os.path.isfile(os.path.join(self.fixdir, i)),
                            "No %s file present after kaboxer build" % (i,))
        self.run_and_check_command(
            "kaboxer install --destdir %s" % (
                os.path.join(self.fixdir, 'target')))
        for i in self.desktopfiles:
            idf = os.path.join(self.fixdir, 'target', 'usr',
                               'local', 'share', 'applications', i)
            self.assertTrue(os.path.isfile(idf),
                            "Generated desktop file not installed at %s" % idf)
        idf = os.path.join(self.fixdir, 'target', 'usr', 'local',
                           'share', 'applications', 'sleeper.desktop')
        self.assertFalse(os.path.isfile(idf),
                         "Manual desktop file installed at %s" % (idf,))

    def test_manual_desktop_files(self):
        with open(os.path.join(self.fixdir, 'kaboxer.yaml'), 'a') as outfile:
            outfile.write("""install:
  desktop-files:
    - sleeper.desktop
""")
        self.test_build_and_save()
        for i in self.desktopfiles:
            self.assertFalse(os.path.isfile(os.path.join(self.fixdir, i)),
                             "%s file present after kaboxer build" % (i,))
        self.run_and_check_command(
            "kaboxer install --destdir %s" % (
                os.path.join(self.fixdir, 'target')))
        for i in self.desktopfiles:
            idf = os.path.join(self.fixdir, 'target', 'usr',
                               'local', 'share', 'applications', i)
            self.assertFalse(os.path.isfile(idf),
                             "Generated desktop file installed at %s" % (idf,))
        idf = os.path.join(self.fixdir, 'target', 'usr', 'local',
                           'share', 'applications', 'sleeper.desktop')
        self.assertTrue(os.path.isfile(idf),
                        "Manual desktop file not installed at %s" % (idf,))

    def test_install_icons(self):
        self.test_build_and_save()
        self.run_and_check_command(
            "kaboxer install --destdir %s" % (
                os.path.join(self.fixdir, 'target')))
        installed_shipped_icon = os.path.join(
            self.fixdir, 'target', 'usr', 'local', 'share', 'icons',
            "kaboxer-%s.svg" % self.app_name)
        self.assertTrue(
            os.path.isfile(installed_shipped_icon),
            "Shipped icon not installed (expecting %s)" %
            installed_shipped_icon)
        installed_extracted_icon = os.path.join(
            self.fixdir, 'target', 'usr', 'local', 'share', 'icons',
            "kaboxer-%s.png" % self.app_name)
        self.assertTrue(
            os.path.isfile(installed_extracted_icon),
            "Extracted icon not installed (expecting %s)" %
            installed_extracted_icon)

    def test_meta_files(self):
        self.run_and_check_command("kaboxer build")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s version" % self.app_name, "1.0")
        self.run_command_check_stdout_matches(
            "kaboxer get-upstream-version %s" % self.app_name, "1.0")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s packaging-revision" % self.app_name, "3")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s Dockerfile" % self.app_name,
            "FROM debian:stable-slim")
        self.run_command("docker image rm %s:latest" % self.image_name,
                         ignore_output=True)
        self.run_and_check_command("kaboxer build --version 1.1")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command_check_stdout_matches(
            "kaboxer get-meta-file %s version" % self.app_name, "1.1")
        self.run_command("docker image rm %s:latest" % self.image_name,
                         ignore_output=True)
        self.run_and_check_command_fails("kaboxer build %s --version 2.0"
                                         % self.app_name)
        self.run_and_check_command(
            "kaboxer build --version 2.0 --ignore-version")
        self.run_command("docker image rm %s:latest" % self.image_name,
                         ignore_output=True)
        self.run_command("docker image rm %s:2.0" % self.image_name,
                         ignore_output=True)
        self.run_command("sed -i -e s/1.0/1.5/ %s" %
                         (os.path.join(self.fixdir, 'Dockerfile'),))
        self.run_and_check_command_fails("kaboxer build %s" % self.app_name)
        self.assertFalse(self.is_image_present(),
                         "Docker image present after failed build")
        self.run_and_check_command("kaboxer build --ignore-version")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_command("docker image rm %s:1.5" % (self.image_name,),
                         ignore_output=True)

    def test_list_local(self):
        self.run_and_check_command("kaboxer build")
        self.run_command_check_stdout_matches(
            "kaboxer list --all",
            r"^%s\s+-\s+1.0\s" % self.app_name)
        self.run_command_check_stdout_matches("kaboxer list --all",
                                              "Installed version")
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --all --skip-headers", "Installed version")
        self.run_command_check_stdout_matches(
            "kaboxer list --all --skip-headers",
            r"^%s\s+-\s+1.0\s" % self.app_name)
        self.remove_images()
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --installed",
            r"^%s\s+-\s+1.0\s" % self.app_name)

    def test_list_local_with_remote_registry_configured(self):
        # Non-regression test where the code was using only the remote image
        # name and where kaboxer build + run would not find the local image
        self.run_and_check_command("kaboxer build kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer -vv list --available --installed --skip-headers",
            r"kbx-demo")

    def test_local_upgrades(self):
        self.run_and_check_command("kaboxer build --save --version 1.1")
        os.rename(os.path.join(self.fixdir, self.app_name + ".tar"),
                  os.path.join(self.fixdir, self.app_name + "-1.1.tar"))
        self.remove_images()
        self.run_and_check_command("kaboxer build --save --version 1.0")
        self.run_command_check_stdout_doesnt_match(
            "kaboxer list --installed",
            r"^%s\s+1.0\s" % self.app_name)
        self.run_and_check_command("kaboxer prepare %s=1.0" % self.app_name)
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              r"^%s\s+1.0\s" % self.app_name)
        os.rename(os.path.join(self.fixdir, self.app_name + ".tar"),
                  os.path.join(self.fixdir, self.app_name + "-1.0.tar"))
        shutil.copy(os.path.join(self.fixdir, self.app_name + "-1.1.tar"),
                    os.path.join(self.fixdir, self.app_name + ".tar"))
        self.run_command_check_stdout_matches(
            "kaboxer list --upgradeable", r"^%s\s+1.0\s+1.1\s" % self.app_name)
        self.run_and_check_command_fails(
            "kaboxer run %s=1.1" % (self.app_name,))
        self.run_and_check_command("kaboxer upgrade %s" % self.app_name)
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"^%s\s+1.1\s" % self.app_name)
        self.run_and_check_command(
            "kaboxer run --version 1.1 %s" % self.app_name)


class TestKaboxerWithRegistryCommon(TestKaboxerCommon):
    def setUp(self):
        super().setUp()
        self.registry_port = 5999
        self.app_name = "localhost:%s/kbx-demo" % (self.registry_port,)
        self.image_name = self.app_name
        self.run_command('docker run -d -p %d:5000 --name %s '
                         '-v %s:/var/lib/registry registry:2'
                         % (self.registry_port, self.nonce,
                            os.path.join(self.fixdir, 'registry')),
                         ignore_output=True)

    def remove_images(self):
        super().remove_images()
        for v in ['1.0', '1.1', '1.2', '1.5', '2.0', 'latest', 'current']:
            for i in ['kaboxer', 'localhost:%s' % (self.registry_port,)]:
                self.run_command("docker image rm %s/kbx-demo:%s" %
                                 (i, v), ignore_output=True)
        self.run_command("docker image prune -f", ignore_output=True)

    def tearDown(self):
        # self.run_command('docker image ls')
        self.run_command('docker container exec %s find /var/lib/registry '
                         '-mindepth 1 -delete' % self.nonce, ignore_output=True)
        self.run_command('docker container stop %s' %
                         (self.nonce,), ignore_output=True)
        self.run_command('docker container rm -v %s' %
                         (self.nonce,), ignore_output=True)
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
            msg="Image %s present at beginning of test" % self.app_name)
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches(
            "docker image ls", self.app_name,
            unexpected_msg="Image not fetched from registry")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World")

    def test_build_then_push_and_fetch(self):
        self.run_and_check_command("kaboxer build kbx-demo")
        # self.run_command('docker image ls')
        self.run_and_check_command("kaboxer push kbx-demo")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name)
        self.run_command("docker image ls")
        self.run_and_check_command("kaboxer -vv prepare kbx-demo")
        self.run_command_check_stdout_matches(
            "docker image ls", self.app_name,
            unexpected_msg="Image not fetched from registry")
        self.run_command("docker image ls")
        self.run_command_check_stdout_matches("kaboxer -vv run kbx-demo",
                                              "Hello World")

    def test_list_registry(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.remove_images()
        self.run_command_check_stdout_matches(
            "kaboxer -v -v list --available", r"kbx-demo\s+[-a-z]+\s+1.0",
            unexpected_msg="Image not available in registry")
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present" % (self.app_name,))
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.assertTrue(self.is_image_present("1.0"),
                        msg="Image %s absent" % (self.app_name,))
        self.run_command_check_stdout_matches(
            "kaboxer list --available", r"kbx-demo\s+[-a-z]+\s+1.0",
            unexpected_msg="Image not available in registry")
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"kbx-demo\s+1.0",
            unexpected_msg="Image not installed")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_and_check_command(
            "kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer list --available", r"kbx-demo\s+[-a-z]+\s+1.1",
            unexpected_msg="Image not available in registry")
        self.remove_images()
        self.assertFalse(
            self.is_image_present("1.0"),
            msg="Image %s present at version %s" % (self.app_name, "1.0"))
        self.assertFalse(
            self.is_image_present("1.1"),
            msg="Image %s present at version %s" % (self.app_name, "1.1"))
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              r"Hello World 1.0")
        self.run_and_check_command("kaboxer list --installed")
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches("kaboxer list --upgradeable",
                                              r"kbx-demo\s+1.0\s+1.1")
        self.run_command_check_stdout_matches(
            "kaboxer list --all", r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches(
            "kaboxer list --all", r"kbx-demo\s+[-a-z0-9.]+\s+1.1",
            unexpected_msg="Image 1.1 not listed as available")
        # self.run_command_check_stdout_matches(
        #     "kaboxer list --all", "kbx-demo: .*1.1 \[available\]",
        #     unexpected_msg="Image 1.1 not listed as available")
        self.run_and_check_command(
            "kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches(
            "kaboxer list --installed", r"kbx-demo\s+1.0",
            unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              r"Hello World 1.0")
        self.run_and_check_command("kaboxer upgrade kbx-demo=1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              r"Hello World 1.1")
        self.run_and_check_command("kaboxer upgrade kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              r"Hello World 1.2")

    def test_run_version(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command(
            "kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer run --version=1.0 kbx-demo",
            "Hello World 1.0")
        self.run_and_check_command_fails("kaboxer run --version=1.1 kbx-demo")
        self.run_and_check_command("kaboxer upgrade kbx-demo")
        self.run_command_check_stdout_matches(
            "kaboxer run --version=1.1 kbx-demo",
            "Hello World 1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_and_check_command(
            "kaboxer build --push --version 1.2 kbx-demo")
        self.run_and_check_command_fails("kaboxer run --version=1.0 kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_command_check_stdout_doesnt_match("kaboxer run kbx-demo",
                                                   "Hello World 1.2")
        self.remove_images()
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.2")

    def test_history(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo /run.sh history | wc -l", "2")

    def test_upgrade_script(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command(
            "kaboxer build --push --version 1.1 kbx-demo")
        self.run_and_check_command(
            "kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches(
            "kaboxer upgrade kbx-demo=1.1",
            "Upgrading from 1.0 to 1.1 with persisted data 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_command_check_stdout_matches(
            "kaboxer run kbx-demo /run.sh history", "3 1.0")


class TestKaboxerWithPublicRegistries(TestKaboxerCommon):
    def test_list_from_docker_hub(self):
        workdir = os.path.join(self.fixdir, 'hello-cli-docker-hub')
        self.run_command_check_stdout_matches(
            "kaboxer list --available --skip-headers",
            "^hello-cli", wd=workdir)

    def test_list_from_gitlab(self):
        workdir = os.path.join(self.fixdir, 'hello-cli-gitlab')
        self.run_command_check_stdout_matches(
            "kaboxer list --available --skip-headers",
            "^hello-cli", wd=workdir)


class TestKbxbuilder(TestKaboxerWithRegistryCommon):
    def setUp(self):
        super().setUp()
        appsfile = os.path.join(self.fixdir, 'kbxbuilder.apps.yaml')
        with open(appsfile) as f:
            y = yaml.safe_load(f)
        y['kbx-demo']['git_url'] = os.getcwd()
        with open(appsfile, 'w') as f:
            f.write(yaml.dump(y))
        if not os.path.exists('.git'):
            self.run_command(
                'git init -q . && '
                'git config user.name "Test Suite" && '
                'git config user.email "devel@kali.org" && '
                'git add . && '
                'git commit -q -m "Test"',
                wd=os.getcwd())

    def tearDown(self):
        if False:
            self.run_command('cat data/kbx-builder.log')
            self.run_command('cat build-logs/kbx-demo.log')
            self.run_command('cat data/status.yaml')

        super().tearDown()

    def test_build_one(self):
        self.run_command_check_stdout_matches(
            "kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO SUCCEEDED")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name)
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World")

    def test_build_failure(self):
        self.run_command("sed -i -e s/subdir/XXX/ %s" %
                         (os.path.join(self.fixdir, 'kbxbuilder.apps.yaml'),))
        self.run_command_check_stdout_matches(
            "kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO FAILED")

    def test_build_all(self):
        self.run_and_check_command("kbxbuilder build-all")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % self.app_name)
        self.assertFalse(
            self.is_image_present(),
            msg="Image %s present at beginning of test" % self.app_name)
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World")

    def test_build_as_needed(self):
        self.run_command_check_stdout_matches(
            "kbxbuilder build-as-needed", "BUILD OF KBX-DEMO SUCCEEDED")
        self.run_command_check_stderr_matches(
            "kbxbuilder build-as-needed", "Build of kbx-demo not needed")
        self.run_command_check_stdout_matches(
            "kbxbuilder build-all", "BUILD OF KBX-DEMO SUCCEEDED")


if __name__ == '__main__':
    if 'USE_SYSTEM_WIDE_KABOXER' not in os.environ:
        binpath = Path(__file__).parent / Path('bin')
        os.environ['PATH'] = '%s:%s' % (binpath.absolute(), os.environ['PATH'])
    unittest.main()
