#! /usr/bin/python3

import unittest
import tempfile
import shutil
import os
import subprocess
import random
import string
import re

unittest.TestLoader.sortTestMethodsUsing = None

class TestKaboxerCommon(unittest.TestCase):
    def setUp(self):
        self.tdname = tempfile.mkdtemp()
        self.fixdir = os.path.join(self.tdname,'fixtures')
        shutil.copytree(os.path.join(os.getcwd(),'tests','fixtures'),
                        self.fixdir)
        self.app_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.image_name = 'kaboxer/' + self.app_name
        self.run_command("sed -i -e s/CONTAINERID/%s/ %s" % (self.app_name, 'kaboxer.yaml'))
        self.tarfile = "%s.tar"%(self.app_name,)
        self.tarpath = os.path.join(self.fixdir,self.tarfile)
        self.desktopfiles = [
            "kaboxer-%s-default.desktop"%(self.app_name,),
            "kaboxer-%s-daemon-start.desktop"%(self.app_name,),
            "kaboxer-%s-daemon-stop.desktop"%(self.app_name,),
        ]

    def tearDown(self):
        self.run_command("docker image rm %s:latest" % (self.image_name,), ignore_output=True)
        shutil.rmtree(self.tdname)
        pass

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

    def run_command_check_output_matches(self,cmd,expected,fail_msg=None,unexpected_msg=None):
        o = subprocess.run(cmd, cwd=self.fixdir, shell=True, capture_output=True, text=True)
        if fail_msg is None:
            fail_msg = "Error when running %s\nSTDOUT=%s\nSTDERR=%s"%(cmd,o.stdout,o.stderr)
        self.assertEqual(o.returncode,0,fail_msg)
        if unexpected_msg is None:
            unexpected_msg = "Unexpected output when running %s"%(cmd,)
        self.assertTrue(re.search(expected,o.stdout),unexpected_msg + " (%s doesn't match %s)" % (o.stdout, expected))

    def is_image_present(self):
        if self.run_command("docker image ls | grep -q %s" % (self.image_name,)) == 0:
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

    def test_purge(self):
        self.build()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_run(self):
        self.build()
        self.run_command_check_output_matches("kaboxer run %s" % (self.app_name,),
                                      "Hi there")
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command_fails("kaboxer run %s" % (self.app_name,))

    def test_run_after_purge(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_command_check_output_matches("kaboxer run %s" % (self.app_name,),
                                      "Hi there")

    def test_load_purge(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer load %s %s" % (self.app_name,self.tarfile))
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after load")
        self.run_and_check_command("kaboxer purge --prune %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_install(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')))
        installed_tarfile = os.path.join(self.fixdir,'target','usr','local','share','kaboxer',self.tarfile)
        self.assertTrue(os.path.isfile(installed_tarfile),
                         "Tarfile not installed (expecting %s)" % (installed_tarfile,))
        os.unlink(installed_tarfile)
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Tarfile still present after unlink (%s)" % (installed_tarfile,))
        self.run_and_check_command("kaboxer install --skip-local-tarball --destdir %s" % (os.path.join(self.fixdir,'target')))
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Tarfile present after install --skip-local-tarball (%s)" % (installed_tarfile,))
        self.run_and_check_command("kaboxer install --destdir %s --prefix %s" % (os.path.join(self.fixdir,'target'),'/usr'))
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
        self.run_command_check_output_matches("kaboxer get-meta-file %s version" % (self.app_name,),
                                              "1.0")
        self.run_command_check_output_matches("kaboxer get-meta-file %s packaging-revision" % (self.app_name,),
                                              "3")
        self.run_command_check_output_matches("kaboxer get-meta-file %s Dockerfile" % (self.app_name,),
                                              "FROM debian:stable-slim")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_and_check_command("kaboxer build --version 1.1")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.run_command_check_output_matches("kaboxer get-meta-file %s version" % (self.app_name,),
                                              "1.1")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
                         ignore_output=True)
        self.run_and_check_command_fails("kaboxer build --version 2.0")
        self.run_and_check_command("kaboxer build --version 2.0 --ignore-version")
        self.run_command("docker image rm %s:latest" % (self.image_name,),
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

    def test_list(self):
        self.run_and_check_command("kaboxer build")
        self.run_command_check_output_matches("kaboxer list",
                                              "%s: 1.0" % (self.app_name,))

class TestKaboxerWithRegistry(TestKaboxerCommon):
    def test_fetch(self):
        self.app_name = "registry.gitlab.com/kalilinux/tools/kaboxer/kbx-demo"
        self.image_name = self.app_name
        if self.is_image_present():
            self.run_command("docker image rm %s" % (self.app_name,))
        self.assertFalse(self.is_image_present(),
                         msg="Image %s present at beginning of test" % (self.app_name,))
        self.run_and_check_command("kaboxer prepare kbx-demo")
        self.run_command_check_output_matches("docker image ls",
                                      self.app_name,
                                      unexpected_msg="Image not fetched from registry")
        self.run_command_check_output_matches("kaboxer run kbx-demo",
                                      "Hello World")


if __name__ == '__main__':
    unittest.main()

