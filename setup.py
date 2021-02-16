#!/usr/bin/python3
import os
from distutils.command.build import build
from distutils.command.clean import clean

from setuptools import setup


class MyBuild(build):
    def run(self):
        # Build manual pages
        os.system("make -C man")
        os.system("make -C dh-kaboxer")
        super().run()


class MyClean(clean):
    def run(self):
        # Clean manual pages
        os.system("make -C man clean")
        os.system("make -C dh-kaboxer clean")
        super().run()


setup(cmdclass={'build': MyBuild, 'clean': MyClean})
