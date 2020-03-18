#! /usr/bin/python3

import unittest
import tempfile
import shutil
import os
import subprocess
import random
import string

class TestKaboxer(unittest.TestCase):
    def setUp(self):
        self.tdname = tempfile.mkdtemp()
        self.fixdir = os.path.join(self.tdname,'fixtures')
        shutil.copytree(os.path.join(os.getcwd(),'tests','fixtures'),
                        self.fixdir)
        self.iname = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        subprocess.call("sed -i -e s/CONTAINERID/%s/ %s" % (self.iname,
                                                            os.path.join(self.fixdir,'kaboxer.yaml')),
                        shell=True)
        self.tarfile = "%s.tar"%(self.iname,)
        self.tarpath = os.path.join(self.fixdir,self.tarfile)
        self.desktopfiles = [
            "kaboxer-%s-default.desktop"%(self.iname,),
            "kaboxer-%s-daemon-start.desktop"%(self.iname,),
            "kaboxer-%s-daemon-stop.desktop"%(self.iname,),
        ]

    def tearDown(self):
        self.run_command("docker image rm kaboxer/%s:latest 2>&1" % (self.iname,))
        shutil.rmtree(self.tdname)
        pass

    def run_command(self,cmd):
        print ("RUNNING %s" % (cmd,))
        return subprocess.call("cd %s;%s" % (self.fixdir,cmd,),
                               shell=True)

    def run_and_check_command(self,cmd,msg):
        ret = self.run_command(cmd)
        self.assertEqual(ret,0,msg)

    def is_image_present(self):
        if self.run_command("docker image ls | grep -q kaboxer/%s" % (self.iname,)) == 0:
            return True
        else:
            return False

    def test_build_only(self):
        self.run_and_check_command("kaboxer build",
                                   "Error when running kaboxer build")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")

    def test_build_and_save(self):
        self.run_and_check_command("kaboxer build --save",
                                   "Error when running kaboxer build --save")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after build")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))

    def test_build_then_separate_save(self):
        self.test_build_only()
        tarfile = "%s.tar"%(self.iname,)
        self.run_and_check_command("kaboxer save %s %s"%(self.iname,self.tarfile),
                                   "Error when running kaboxer save")
        self.assertTrue(os.path.isfile(self.tarpath),
                        "Image not saved (expecting %s)" % (self.tarpath,))

    def test_build_clean(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer clean",
                                   "Error when running kaboxer clean")
        self.assertFalse(os.path.isfile(self.tarpath),
                         "Image still present after clean (expecting %s)" % (self.tarfile,))

    def test_purge(self):
        self.test_build_only()
        self.run_and_check_command("kaboxer purge %s" % (self.iname,),
                                   "Error when running kaboxer purge")
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_load_purge(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer purge %s" % (self.iname,),
                                   "Error when running kaboxer purge")
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")
        self.run_and_check_command("kaboxer load %s %s" % (self.iname,self.tarfile),
                                   "Error when running kaboxer load")
        self.assertTrue(self.is_image_present(),
                        "No Docker image present after load")
        self.run_and_check_command("kaboxer purge %s" % (self.iname,),
                                   "Error when running kaboxer purge")
        self.assertFalse(self.is_image_present(),
                         "Docker image still present after kaboxer purge")

    def test_install(self):
        self.test_build_and_save()
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')),
                                   "Error when running kaboxer install")
        installed_tarfile = os.path.join(self.fixdir,'target','usr','local','share','kaboxer',self.tarfile)
        self.assertTrue(os.path.isfile(installed_tarfile),
                         "Tarfile not installed (expecting %s)" % (installed_tarfile,))
        os.unlink(installed_tarfile)
        self.assertFalse(os.path.isfile(installed_tarfile),
                         "Tarfile still present after unlink (%s)" % (installed_tarfile,))
        self.run_and_check_command("kaboxer install --destdir %s --prefix %s" % (os.path.join(self.fixdir,'target'),'/usr'),
                                   "Error when running kaboxer install")
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
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')),
                                   "Error when running kaboxer install")
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
        self.run_and_check_command("kaboxer install --destdir %s" % (os.path.join(self.fixdir,'target')),
                                   "Error when running kaboxer install")
        for i in self.desktopfiles:
            idf = os.path.join(self.fixdir,'target','usr','local','share','applications',i)
            self.assertFalse(os.path.isfile(idf),
                             "Generated desktop file installed at %s" % (idf,))
        idf = os.path.join(self.fixdir,'target','usr','local','share','applications','sleeper.desktop')
        self.assertTrue(os.path.isfile(idf),
                        "Manual desktop file not installed at %s" % (idf,))

if __name__ == '__main__':
    unittest.main()

