#! /usr/bin/python3

import unittest
import tempfile
import shutil
import os
import subprocess
import random
import string
import re
import yaml

unittest.TestLoader.sortTestMethodsUsing = None

class TestKaboxerCommon(unittest.TestCase):
    def setUp(self):
        self.tdname = tempfile.mkdtemp()
        self.fixdir = os.path.join(self.tdname,'fixtures')
        shutil.copytree(os.path.join(os.getcwd(),'tests','fixtures'),
                        self.fixdir)
        self.nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.app_name = self.nonce
        self.image_name = 'kaboxer/' + self.app_name
        self.run_command("sed -i -e s/CONTAINERID/%s/ %s" % (self.app_name, 'kaboxer.yaml'))
        self.run_command("sed -i -e s,FIXDIR,%s, %s" % (self.fixdir, 'kbx-demo.kaboxer.yaml'))
        self.run_command("mkdir -p %s/persist" % (self.fixdir,))
        self.tarfile = "%s.tar"%(self.app_name,)
        self.tarpath = os.path.join(self.fixdir,self.tarfile)
        self.desktopfiles = [
            "kaboxer-%s-default.desktop"%(self.app_name,),
            "kaboxer-%s-daemon-start.desktop"%(self.app_name,),
            "kaboxer-%s-daemon-stop.desktop"%(self.app_name,),
        ]
        shutil.copy(os.path.join(self.fixdir, 'kbx-demo.kaboxer.yaml'),
                    os.path.join(self.fixdir, 'kbx-demo.yaml'))

    def remove_images(self):
        self.run_command("docker image rm %s:1.0" % (self.image_name,), ignore_output=True)
        self.run_command("docker image rm %s:1.1" % (self.image_name,), ignore_output=True)
        self.run_command("docker image rm %s:1.2" % (self.image_name,), ignore_output=True)
        self.run_command("docker image rm %s:latest" % (self.image_name,), ignore_output=True)

    def tearDown(self):
        # self.run_command("docker image ls")
        self.remove_images()
        shutil.rmtree(self.tdname)

    def run_command(self,cmd,ignore_output=False):
        # print ("RUNNING %s" % (cmd,))
        return subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=ignore_output).returncode

    def run_and_check_command(self,cmd,msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True)
        if msg is None:
            msg = "Error when running %s\nSTDOUT:\n%s\nSTDERR:\n%s"%(cmd,o.stdout,o.stderr)
        self.assertEqual(o.returncode,0,msg)

    def run_and_check_command_fails(self,cmd,msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True)
        if msg is None:
            msg = "Unexpected success when running %s\nSTDOUT:\n%s\nSTDERR:\n%s"%(cmd,o.stdout,o.stderr)
        self.assertNotEqual(o.returncode,0,msg)

    def run_command_check_stdout_matches(self,cmd,expected,fail_msg=None,unexpected_msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True, text=True)
        if fail_msg is None:
            fail_msg = "Error when running %s\nSTDOUT=%s\nSTDERR=%s"%(cmd,o.stdout,o.stderr)
        self.assertEqual(o.returncode,0,fail_msg)
        if unexpected_msg is None:
            unexpected_msg = "Unexpected output when running %s"%(cmd,)
        self.assertTrue(re.search(expected,o.stdout),unexpected_msg + " (%s doesn't match %s)" % (o.stdout, expected))

    def run_command_check_stdout_doesnt_match(self,cmd,expected,fail_msg=None,unexpected_msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True, text=True)
        if fail_msg is None:
            fail_msg = "Error when running %s\nSTDOUT=%s\nSTDERR=%s"%(cmd,o.stdout,o.stderr)
        self.assertEqual(o.returncode,0,fail_msg)
        if unexpected_msg is None:
            unexpected_msg = "Unexpected output when running %s"%(cmd,)
        self.assertFalse(re.search(expected,o.stdout),unexpected_msg + " (%s matches %s)" % (o.stdout, expected))

    def run_command_check_stderr_matches(self,cmd,expected,fail_msg=None,unexpected_msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True, text=True)
        if fail_msg is None:
            fail_msg = "Error when running %s\nSTDOUT=%s\nSTDERR=%s"%(cmd,o.stdout,o.stderr)
        self.assertEqual(o.returncode,0,fail_msg)
        if unexpected_msg is None:
            unexpected_msg = "Unexpected output in stderr when running %s"%(cmd,)
        self.assertTrue(re.search(expected,o.stderr),unexpected_msg + " (%s doesn't match %s)" % (o.stderr, expected))

    def is_image_present(self, version='latest'):
        if self.run_command("docker image ls | grep -q '%s *%s'" % (self.image_name,version)) == 0:
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

    def test_build_and_save(self):
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))

    def test_build_two_apps(self):
        self.nonce2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.app_name2 = self.nonce2
        self.image_name2 = 'kaboxer/' + self.app_name2
        shutil.copy(os.path.join(self.fixdir, 'kaboxer.yaml'),
                    os.path.join(self.fixdir, 'app2.kaboxer.yaml'))
        self.run_command("sed -i -e s/%s/%s/ %s" % (self.app_name, self.app_name2, 'app2.kaboxer.yaml'))
        self.run_and_check_command("kaboxer build --save")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))
        self.assertEqual(self.run_command("docker image ls | grep -q '%s *%s'" % (self.image_name2,'latest')),0, "No docker image present for app2 after build")
        self.tarfile2 = "%s.tar"%(self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir,self.tarfile2)
        self.assertTrue(os.path.isfile(self.tarpath2),
                        "Image not saved for app2 (expecting %s)" % (self.tarpath2,))

    def test_build_one_app_only(self):
        self.nonce2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.app_name2 = self.nonce2
        self.image_name2 = 'kaboxer/' + self.app_name2
        shutil.copy(os.path.join(self.fixdir, 'kaboxer.yaml'),
                    os.path.join(self.fixdir, 'app2.kaboxer.yaml'))
        self.run_command("sed -i -e s/%s/%s/ %s" % (self.app_name, self.app_name2, 'app2.kaboxer.yaml'))
        self.run_and_check_command("kaboxer build --save %s" % (self.app_name,))
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))
        self.assertEqual(self.run_command("docker image ls | grep -q '%s *%s'" % (self.image_name2,'latest')),1, "Image for app2 unexpectedly present after build")
        self.tarfile2 = "%s.tar"%(self.app_name2,)
        self.tarpath2 = os.path.join(self.fixdir,self.tarfile2)
        self.assertFalse(os.path.isfile(self.tarpath2),
                        "Image saved for app2 (as %s)" % (self.tarpath2,))

    def test_build_then_separate_save(self):
        self.build()
        tarfile = "%s.tar"%(self.app_name,)
        self.run_and_check_command("kaboxer save %s %s"%(self.app_name,self.tarfile))
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))

    def test_build_clean(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer clean")
        self.assertFalse(os.path.isfile(self.tarpath),
                         "Image still present after clean (expecting %s)" % (self.tarfile,))
        for i in self.desktopfiles:
            self.assertFalse(os.path.isfile(os.path.join(self.fixdir,i)),
                            "%s file still present after kaboxer clean"%(i,))

    def test_purge(self):
        self.build()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_run(self):
        self.test_build_and_save()
        self.run_command_check_stdout_matches("kaboxer run %s" % (self.app_name,),
                                      "Hi there")
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer run %s" % (self.app_name,))

    def test_run_after_purge(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_command_check_stdout_matches("kaboxer run %s" % (self.app_name,),
                                      "Hi there")

    def test_load_purge(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer load %s %s" % (self.app_name,self.tarfile))
        self.assertTrue(self.is_image_present("1.0"),
                        "No Docker image present after load")
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present("1.0"),
                         "Docker image still present after kaboxer purge")

    def test_install(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer install --tarball --destdir %s" % (os.path.join(self.fixdir,'target')))
        installed_tarfile = os.path.join(self.fixdir,'target','usr','local','share','kaboxer',self.tarfile)
        self.assertTrue(os.path.isfile(installed_tarfile),
                         "Tarfile not installed (expecting %s)" % (installed_tarfile,))
        os.unlink(installed_tarfile)
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Tarfile still present after unlink (%s)" % (installed_tarfile,))
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')))
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Tarfile present after install (%s)" % (installed_tarfile,))
        self.run_and_check_command("kaboxer install --tarball --destdir %s --prefix %s" % (os.path.join(self.fixdir,'target'),'/usr'))
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Default tarfile present after install to non-default dir (%s)" % (installed_tarfile,))
        installed_tarfile_usr = os.path.join(self.fixdir,'target','usr','share','kaboxer',self.tarfile)
        self.assertTrue(os.path.isfile(installed_tarfile_usr),
                         "Tarfile not installed (expecting %s)" % (installed_tarfile,))

    def test_auto_desktop_files(self):
        self.test_build_and_save()
        for i in self.desktopfiles:
            self.assertTrue(os.path.isfile(os.path.join(self.fixdir,i)),
                            "No %s file present after kaboxer build"%(i,))
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')))
        for i in self.desktopfiles:
            idf = os.path.join(self.fixdir,'target','usr','local','share','applications',i)
            self.assertTrue(os.path.isfile(idf),
                            "Generated desktop file not installed at %s" % (idf,))
        idf = os.path.join(self.fixdir,'target','usr','local','share','applications','sleeper.desktop')
        self.assertFalse(os.path.isfile(idf),
                         "Manual desktop file installed at %s" % (idf,))

    def test_manual_desktop_files(self):
        with open(os.path.join(self.fixdir,'kaboxer.yaml'), 'a') as outfile:
            outfile.write("""install:
  desktop-files:
    - sleeper.desktop
""")
        self.test_build_and_save()
        for i in self.desktopfiles:
            self.assertFalse(os.path.isfile(os.path.join(self.fixdir,i)),
                             "%s file present after kaboxer build"%(i,))
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')))
        for i in self.desktopfiles:
            idf = os.path.join(self.fixdir,'target','usr','local','share','applications',i)
            self.assertFalse(os.path.isfile(idf),
                             "Generated desktop file installed at %s" % (idf,))
        idf = os.path.join(self.fixdir,'target','usr','local','share','applications','sleeper.desktop')
        self.assertTrue(os.path.isfile(idf),
                        "Manual desktop file not installed at %s" % (idf,))

    def test_install_icons(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')))
        installed_shipped_icon = os.path.join(self.fixdir,'target','usr','local','share','icons',"kaboxer-%s.svg" % (self.app_name,))
        self.assertTrue(os.path.isfile(installed_shipped_icon),
                        "Shipped icon not installed (expecting %s)" % (installed_shipped_icon,))
        installed_extracted_icon = os.path.join(self.fixdir,'target','usr','local','share','icons',"kaboxer-%s.png" % (self.app_name,))
        self.assertTrue(os.path.isfile(installed_extracted_icon),
                        "Extracted icon not installed (expecting %s)" % (installed_extracted_icon,))

    def test_meta_files(self):
        self.run_and_check_command("kaboxer build")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command_check_stdout_matches("kaboxer get-meta-file %s version" % (self.app_name,),
                                              "1.0")
        self.run_command_check_stdout_matches("kaboxer get-meta-file %s packaging-revision" % (self.app_name,),
                                              "3")
        self.run_command_check_stdout_matches("kaboxer get-meta-file %s Dockerfile" % (self.app_name,),
                                              "FROM debian:stable-slim")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_and_check_command("kaboxer build --version 1.1")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command_check_stdout_matches("kaboxer get-meta-file %s version" % (self.app_name,),
                                              "1.1")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_and_check_command_fails("kaboxer build --version 2.0")
        self.run_and_check_command("kaboxer build --version 2.0 --ignore-version")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_command("docker image rm %s:2.0" % (self.image_name,),
                         ignore_output=True)
        self.run_command("sed -i -e s/1.0/1.5/ %s" % (os.path.join(self.fixdir,'Dockerfile'),))
        self.run_and_check_command_fails("kaboxer build")
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
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "%s: 1.0 \[installed\]" % (self.app_name,))
        self.remove_images()
        self.run_command_check_stdout_doesnt_match("kaboxer list --installed",
                                                   "%s: 1.0 \[installed\]" % (self.app_name,))

    def test_local_upgrades(self):
        self.run_and_check_command("kaboxer build --save --version 1.1")
        os.rename(os.path.join(self.fixdir, self.app_name+".tar"),
                  os.path.join(self.fixdir, self.app_name+"-1.1.tar"))
        self.remove_images()
        self.run_and_check_command("kaboxer build --save --version 1.0")
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "%s: 1.0 \[installed\]" % (self.app_name,))
        os.rename(os.path.join(self.fixdir, self.app_name+".tar"),
                  os.path.join(self.fixdir, self.app_name+"-1.0.tar"))
        shutil.copy(os.path.join(self.fixdir, self.app_name+"-1.1.tar"),
                    os.path.join(self.fixdir, self.app_name+".tar"))
        self.run_command_check_stdout_matches("kaboxer list --upgradeable",
                                              "%s: .*1.1 \[upgradeable from 1.0\]" % (self.app_name,))
        self.run_and_check_command("kaboxer upgrade %s" % (self.app_name,))
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "%s: 1.1 \[installed\]" % (self.app_name,))

class TestKaboxerWithRegistryCommon(TestKaboxerCommon):
    def setUp(self):
        super().setUp()
        self.app_name = "localhost:5999/kbx-demo"
        self.image_name = self.app_name
        self.run_command('docker run -d -p %d:5000 --name %s -v %s:/var/lib/registry registry:2' \
                         % (5999, self.nonce, os.path.join(self.fixdir, 'registry')), ignore_output=True)

    def remove_images(self):
        super().remove_images()
        self.run_command("docker image rm kaboxer/kbx-demo:1.0", ignore_output=True)
        self.run_command("docker image rm kaboxer/kbx-demo:1.1", ignore_output=True)
        self.run_command("docker image rm kaboxer/kbx-demo:1.2", ignore_output=True)
        self.run_command("docker image rm kaboxer/kbx-demo:latest", ignore_output=True)

    def tearDown(self):
        # self.run_command('docker image ls')
        self.run_command('docker container exec %s find /var/lib/registry -mindepth 1 -delete' % (self.nonce,), ignore_output=True)
        self.run_command('docker container stop %s' % (self.nonce,), ignore_output=True)
        self.run_command('docker container rm -v %s' % (self.nonce,), ignore_output=True)
        super().tearDown()

class TestKaboxerWithRegistry(TestKaboxerWithRegistryCommon):
    def test_build_with_push_and_fetch(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present at beginning of test" % (self.app_name,))
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches("docker image ls",
                                      self.app_name,
                                      unexpected_msg="Image not fetched from registry")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                      "Hello World")

    def test_build_then_push_and_fetch(self):
        self.run_and_check_command("kaboxer build kbx-demo")
        self.run_and_check_command("kaboxer push kbx-demo")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present at beginning of test" % (self.app_name,))
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_stdout_matches("docker image ls",
                                              self.app_name,
                                              unexpected_msg="Image not fetched from registry")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                      "Hello World")

    def test_list_registry(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.remove_images()
        self.run_command_check_stdout_matches("kaboxer list --available",
                                              "kbx-demo: .*1.0 \[available\]",
                                              unexpected_msg="Image not available in registry")
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present" % (self.app_name,))
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.assertTrue(self.is_image_present("1.0"),
                         msg="Image %s absent" % (self.app_name,))
        self.run_command_check_stdout_matches("kaboxer list --available",
                                              "kbx-demo: .*1.0 \[available\]",
                                              unexpected_msg="Image not available in registry")
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "kbx-demo: .*1.0 \[installed\]",
                                              unexpected_msg="Image not installed")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches("kaboxer list --available",
                                              "kbx-demo: .*1.1 \[available\]",
                                              unexpected_msg="Image not available in registry")
        self.remove_images()
        self.assertFalse(self.is_image_present("1.0"),
                         msg="Image %s present at version %s" % (self.app_name,"1.0"))
        self.assertFalse(self.is_image_present("1.1"),
                         msg="Image %s present at version %s" % (self.app_name,"1.1"))
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_and_check_command("kaboxer list --installed")
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "kbx-demo: .*1.0 \[installed\]",
                                              unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches("kaboxer list --upgradeable",
                                              "kbx-demo: .*1.1 \[upgradeable from 1.0\]")
        self.run_command_check_stdout_matches("kaboxer list --all",
                                              "kbx-demo: .*1.0 \[installed\]",
                                              unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches("kaboxer list --all",
                                              "kbx-demo: .*1.0 \[available\]",
                                              unexpected_msg="Image 1.0 not listed as available")
        self.run_command_check_stdout_matches("kaboxer list --all",
                                              "kbx-demo: .*1.1 \[available\]",
                                              unexpected_msg="Image 1.1 not listed as available")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer list --installed",
                                              "kbx-demo: .*1.0 \[installed\]",
                                              unexpected_msg="Image 1.0 not installed")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_and_check_command("kaboxer upgrade kbx-demo=1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_and_check_command("kaboxer upgrade kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.2")

    def test_run_version(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run --version=1.0 kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run --version=1.1 kbx-demo",
                                              "Hello World 1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run --version=1.0 kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.2")
        self.remove_images()
        self.run_command_check_stdout_matches("kaboxer run --version=1.0 kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run --version=1.1 kbx-demo",
                                              "Hello World 1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.remove_images()
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.2")

    def test_history(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo /run.sh history | wc -l",
                                              "2")

    def test_upgrade_script(self):
        self.run_and_check_command("kaboxer build --push kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.1 kbx-demo")
        self.run_and_check_command("kaboxer build --push --version 1.2 kbx-demo")
        self.remove_images()
        self.run_and_check_command("kaboxer prepare kbx-demo=1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.0")
        self.run_command_check_stdout_matches("kaboxer upgrade kbx-demo=1.1",
                                              "Upgrading from 1.0 to 1.1 with persisted data 1.0")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                              "Hello World 1.1")
        self.run_command_check_stdout_matches("kaboxer run kbx-demo /run.sh history",
                                              "3 1.0")

class TestKbxbuilder(TestKaboxerWithRegistryCommon):
    def setUp(self):
        super().setUp()
        appsfile = os.path.join(self.fixdir,'kbxbuilder.apps.yaml')
        with open(appsfile) as f:
            y = yaml.safe_load(f)
        y['kbx-demo']['git_url'] = os.getcwd()
        with open(appsfile,'w') as f:
            f.write(yaml.dump(y))

    def tearDown(self):
        if False:
            self.run_command('cat data/kbx-builder.log')
            self.run_command('cat build-logs/kbx-demo.log')
            self.run_command('cat data/status.yaml')

        super().tearDown()

    def test_build_one(self):
        self.run_command_check_stdout_matches("kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO SUCCEEDED")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present at beginning of test" % (self.app_name,))
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                      "Hello World")

    def test_build_failure(self):
        self.run_command("sed -i -e s/subdir/XXX/ %s" % (os.path.join(self.fixdir,'kbxbuilder.apps.yaml'),))
        self.run_command_check_stdout_matches("kbxbuilder build-one kbx-demo", "BUILD OF KBX-DEMO FAILED")

    def test_build_all(self):
        self.run_and_check_command("kbxbuilder build-all")
        self.remove_images()
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present at beginning of test" % (self.app_name,))
        self.run_command_check_stdout_matches("kaboxer run kbx-demo",
                                      "Hello World")

    def test_build_as_needed(self):
        self.run_command_check_stdout_matches("kbxbuilder build-as-needed", "BUILD OF KBX-DEMO SUCCEEDED")
        self.run_command_check_stderr_matches("kbxbuilder build-as-needed", "Build of kbx-demo not needed")
        self.run_command_check_stdout_matches("kbxbuilder build-all", "BUILD OF KBX-DEMO SUCCEEDED")

if __name__ == '__main__':
    unittest.main()
