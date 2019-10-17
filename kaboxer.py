#! /usr/bin/python3

import argparse

def run(args):
    pass

def stop(args):
    pass

def build(args):
    pass

def pull(args):
    pass

def purge(args):
    pass

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(title='subcommands', help='action to perform', dest='action', required=True)

parser_run = subparsers.add_parser('run', help='run containerized app')
parser_run.add_argument('app')
parser_run.add_argument('executable', nargs='*')
parser_run.set_defaults(func=run)

parser_stop = subparsers.add_parser('stop', help='stop running containerized app')
parser_stop.add_argument('app')
parser_stop.set_defaults(func=stop)

parser_build = subparsers.add_parser('build', help='build image')
parser_build.add_argument('app')
parser_build.set_defaults(func=build)

parser_pull = subparsers.add_parser('pull', help='fetch image')
parser_pull.add_argument('app')
parser_pull.set_defaults(func=pull)

parser_purge = subparsers.add_parser('purge', help='purge image')
parser_purge.add_argument('app')
parser_purge.set_defaults(func=purge)

args = parser.parse_args()
print(args)
args.func(args)
