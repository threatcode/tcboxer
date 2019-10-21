#! /usr/bin/python3

import argparse
import yaml
import os
import sys
import re

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

        self.docker_conn = docker.from_env()

    def go(self):
        self.args = self.parser.parse_args()
        print(self.args)
        self.args.func()

    def run(self):
        self.read_config()
        print(self.config)
        opts = {}
        opts['environment'] = {}
        opts['auto_remove'] = True
        try:
            netname = self.config['networks'][0]
            self.create_network(netname)
            opts['network'] = netname
            extranets = self.config['networks'][1:]
        except KeyError:
            pass
        try:
            ports = {}
            for publish_port in self.config['publish_ports']:
                ports[publish_port] = publish_port
            opts['ports'] = ports
        except KeyError:
            pass
        try:
            mounts = list(map (lambda x: docker.types.Mount(x['target'],x['source']), self.config['mounts']))
            opts['mounts'] = mounts
        except KeyError:
            pass
        run_mode = self.config['run_mode']
        try:
            image = self.config['image']
        except KeyError:
            image = self.args.app

        if run_mode == 'cli':
            opts['tty'] = True
            opts['stdin_open'] = True
        elif run_mode == 'gui':
            xsock = '/tmp/.X11-unix'
            xauth = os.path.join(os.getenv('HOME'), '.docker.auth')
            f = subprocess.Popen(['xauth', 'nlist', os.getenv('DISPLAY')], stdout=subprocess.PIPE).stdout
            g = subprocess.Popen(['xauth', '-f', xauth, 'nmerge', '-'], stdin=subprocess.PIPE).stdin
            for l in f:
                ll = re.sub('^....', 'ffff', l)
                g.write(ll)
            g.close()
            opts['environment']['DISPLAY'] = os.getenv('DISPLAY')
            opts['environment']['XAUTHORITY'] = xauth
            opts['mounts'].extend(docker.types.Mount(xauth,xauth))
            opts['mounts'].extend(docker.types.Mount(xsock,xsock))
        elif run_mode == 'server':
            opts['tty'] = True
            opts['name'] = self.args.app
        else:
            print ("Unknown run mode")
            sys.exit(1)
        print(opts)
        container = self.docker_conn.containers.create(image, *self.args.executable, **opts)
        for e in extranets:
            create_network(e).connect(container)
        container.start()

    def stop(self):
        run_mode = self.config['run_mode']
        try:
            image = self.config['image']
        except KeyError:
            image = self.args.app
        if run_mode == 'server':
            containers = self.docker_conn.containers.list(filter={'name': self.args.app})
            container = containers[0]
            container.stop()
        else:
            print ("Can't stop a non-server component")
            sys.exit(1)

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

    def create_network(self, netname):
        for n in self.docker_conn.networks.list():
            if n.name == netname:
                return n
        return self.docker_conn.networks.create(name=netname, driver='bridge')

kaboxer = Kaboxer()
kaboxer.go()
