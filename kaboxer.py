#! /usr/bin/python3

import argparse
import yaml
import os
import sys

import docker

class Kaboxer:
    def __init__(self):
        self.parser = argparse.ArgumentParser()

        subparsers = self.parser.add_subparsers(title='subcommands', help='action to perform', dest='action', required=True)

        parser_run = subparsers.add_parser('run', help='run containerized app')
        parser_run.add_argument('app')
        parser_run.add_argument('executable', nargs='*')
        parser_run.set_defaults(func=self.run)

        parser_stop = subparsers.add_parser('stop', help='stop running containerized app')
        parser_stop.add_argument('app')
        parser_stop.set_defaults(func=self.stop)

        parser_build = subparsers.add_parser('build', help='build image')
        parser_build.add_argument('app')
        parser_build.set_defaults(func=self.build)

        parser_pull = subparsers.add_parser('pull', help='fetch image')
        parser_pull.add_argument('app')
        parser_pull.set_defaults(func=self.pull)

        parser_purge = subparsers.add_parser('purge', help='purge image')
        parser_purge.add_argument('app')
        parser_purge.set_defaults(func=self.purge)

    def go(self):
        self.args = self.parser.parse_args()
        print(self.args)
        self.args.func()

    def run(self):
        self.read_config()
        print (self.config)
        pass

    def stop(self):
        pass

    def build(self):
        pass

    def pull(self):
        pass

    def purge(self):
        pass

    def read_config(self):
        paths = [
            '.',
            '/etc/kaboxer',
            '/usr/share/kaboxer',
        ]
        for p in paths:
            config_file = os.path.join(p,self.args.app+'.yaml')
            if os.path.isfile(config_file):
                try:
                    self.config = yaml.load(open(config_file))
                    return
                except:
                    print("Error loading config file "+config_file)
                    sys.exit(1)
        print("Missing config file")
        sys.exit(1)

kaboxer = Kaboxer()
kaboxer.go()
