#!/usr/bin/python3
import os
from distutils.command.clean import clean
from distutils.command.build import build
from setuptools import setup


class MyBuild(build):
    def run(self):
        # Build manual pages
        os.system("make")
        super().run()


class MyClean(clean):
    def run(self):
        # Clean manual pages
        os.system("make clean")
        super().run()


setup(cmdclass={'build': MyBuild, 'clean': MyClean})
