#! /usr/bin/python3

import argparse
import email
import logging
import os
import re
import smtplib
import subprocess
import sys
import time

import git

import jinja2

import yaml


class Kbxbuilder:
    def __init__(self):
        self.parser = argparse.ArgumentParser()

        subparsers = self.parser.add_subparsers(
            title='subcommands', help='action to perform', dest='action',
            required=True)

        parser_build_one = subparsers.add_parser('build-one',
                                                 help='build one app')
        parser_build_one.add_argument('app')
        parser_build_one.set_defaults(func=self.cmd_build_one)

        parser_build_all = subparsers.add_parser('build-all',
                                                 help='build all apps')
        parser_build_all.set_defaults(func=self.cmd_build_all)

        parser_build_as_needed = subparsers.add_parser(
            'build-as-needed', help='build apps as needed')
        parser_build_as_needed.set_defaults(func=self.cmd_build_as_needed)

        self.logger = logging.Logger('kbxbuilder')
        ch = logging.StreamHandler()
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(ch)

        self.subloggers = {}

        self.config_paths = [
            '.',
            '/etc/kaboxer',
        ]

        self.config = {}
        self.apps = {}

        for p in self.config_paths:
            f = os.path.join(p, 'kbxbuilder.config.yaml')
            try:
                self.config = yaml.safe_load(open(f))
                self.config_file = f
                self.logger.info("Loading config file %s", f)
                break
            except Exception:
                self.logger.error("Failed when loading config file")
                raise

        def walk(node, replace_needed=False):
            for key, item in node.items():
                if isinstance(item, dict):
                    replace_needed = walk(item, replace_needed)
                else:
                    if re.search('{{', item):
                        replace_needed = True
                        t = jinja2.Template(item)
                        node[key] = t.render(config=self.config)
            return replace_needed

        i = 10
        while i > 0:
            i -= 1
            if not walk(self.config['builder']):
                break

        if 'on_success' not in self.config:
            self.config['on_success'] = []
        if 'on_failure' not in self.config:
            self.config['on_failure'] = []

        if i == 0:
            self.logger.error("Dependency loop in config file")
            sys.exit(1)

        os.makedirs(os.path.dirname(self.config['builder']['logfile']),
                    exist_ok=True)
        logfile = self.config['builder']['logfile']
        ch = logging.FileHandler(logfile)
        ch.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        ch.setLevel(logging.INFO)
        self.logger.addHandler(ch)

        os.makedirs(self.config['builder']['datadir'], exist_ok=True)
        self.statusfile = os.path.join(self.config['builder']['datadir'],
                                       'status.yaml')
        try:
            self.logger.debug("Loading status file %s", f)
            self.status = yaml.safe_load(open(self.statusfile))
        except Exception:
            self.status = {}

        for p in self.config_paths:
            f = os.path.join(p, 'kbxbuilder.apps.yaml')
            try:
                self.apps = yaml.safe_load(open(f))
                self.apps_file = f
                self.logger.info("Loading apps file %s", f)
                break
            except Exception:
                pass

    def add_status(self, app, tag, revid, status):
        if app not in self.status:
            self.status[app] = {}
        t = time.time()
        item = {
            'tag': tag,
            'revid': revid,
            'status': status,
        }
        self.status[app][t] = item
        if status:
            self.status[app]['last_success'] = item.copy()
        else:
            self.status[app]['last_failure'] = item.copy()
        self.logger.debug("Saving status file")
        with open(self.statusfile, 'w') as f:
            f.write(yaml.dump(self.status))

    def go(self):
        self.args = self.parser.parse_args()
        self.args.func()

    def build_one(self, app, force=True):
        os.makedirs(self.config['builder']['buildlogsdir'], exist_ok=True)
        if app not in self.subloggers:
            logfile = os.path.join(
                self.config['builder']['buildlogsdir'], app + '.log')
            self.subloggers[app] = logging.FileHandler(logfile)
            self.subloggers[app].setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

            def flt(x):
                try:
                    return x.app == app
                except Exception:
                    return False
            self.subloggers[app].addFilter(flt)
            self.logger.addHandler(self.subloggers[app])
        try:
            buildmode = self.apps[app]['buildmode']
        except KeyError:
            self.logger.error("Cannot find how to build %s", app)
            sys.exit(1)

        os.makedirs(self.config['builder']['workdir'], exist_ok=True)
        checkoutdir = os.path.join(self.config['builder']['workdir'], app)
        try:
            branch = self.apps[app]['branch']
        except KeyError:
            branch = 'master'
        self.logger.debug("Checking out Git repository at %s", checkoutdir)
        if os.path.isdir(checkoutdir):
            repo = git.Repo(checkoutdir)
            origin = repo.remotes['origin']
            if origin.url != self.apps[app]['git_url']:
                self.logger.debug("Switching remote URL")
                git.remote.Remote.remove(repo, 'origin')
                git.remote.Remote.add(repo, 'origin', self.apps[app]['git_url'])
                origin = repo.remotes['origin']
            else:
                self.logger.debug("Remote already on the correct URL")
            origin.fetch('--prune')
        else:
            repo = git.Repo.clone_from(self.apps[app]['git_url'], checkoutdir)
        try:
            repo.git.checkout('remotes/origin/' + branch)
        except Exception:
            repo.git.checkout(branch)

        revid = repo.head.commit.hexsha

        if not force:
            try:
                if self.status[app]['last_success']['revid'] == revid:
                    self.logger.info("Build of %s not needed", app)
                    return
            except KeyError:
                pass

        if 'subdir' in self.apps[app]:
            appdir = os.path.join(checkoutdir, self.apps[app]['subdir'])
        else:
            appdir = checkoutdir
        appdir = os.path.abspath(appdir)
        self.logger.info("Building app %s at revid %s", app, revid)
        if buildmode == 'kaboxer':
            cmd = "kaboxer build %s" % (app,)
            self.logger.debug("Building kaboxer image: %s", cmd)
            if subprocess.run(cmd, cwd=appdir, shell=True).returncode == 0:
                self.add_status(app, branch, revid, 'success')
                if self.apps[app]['push']:
                    for i in self.config['on_success']:
                        if i['action'] == 'push_to_registry':
                            cmd = "kaboxer push %s" % (app,)
                            self.logger.debug("Pushing to registry: %s", cmd)
                            if subprocess.run(cmd, cwd=appdir,
                                              shell=True).returncode != 0:
                                self.logger.error("Error when running %s", cmd)
                for i in self.config['on_success']:
                    if i['action'] == 'execute_command':
                        t = jinja2.Template(i['command'])
                        cmd = t.render(config=self.config, app=app)
                        self.logger.debug("Running command: %s", cmd)
                        if subprocess.run(cmd, cwd=appdir,
                                          shell=True).returncode != 0:
                            self.logger.error("Error when running %s", cmd)
                    if i['action'] == 'send_mail':
                        s = smtplib.SMTP('localhost')
                        with open(logfile) as f:
                            msg = email.mime.text.MIMEText(f.read(),
                                                           _charset='utf-8')
                        msg['Subject'] = jinja2.Template(
                            i['subject']).render(app=app)
                        msg['From'] = i['from']
                        msg['To'] = i['to']
                        s.sendmail(msg['From'], [msg['To']], msg.as_string())
            else:
                self.add_status(app, branch, revid, 'failure')
                self.logger.error("Error when running %s", cmd)
                for i in self.config['on_failure']:
                    if i['action'] == 'execute_command':
                        t = jinja2.Template(i['command'])
                        cmd = t.render(config=self.config, app=app)
                        self.logger.debug("Running command: %s", cmd)
                        if subprocess.run(cmd, cwd=appdir,
                                          shell=True).returncode != 0:
                            self.logger.error("Error when running %s", cmd)
                    if i['action'] == 'send_mail':
                        s = smtplib.SMTP('localhost')
                        with open(logfile) as f:
                            msg = email.mime.text.MIMEText(f.read(),
                                                           _charset='utf-8')
                        msg['Subject'] = jinja2.Template(
                            i['subject']).render(app=app)
                        msg['From'] = i['from']
                        msg['To'] = i['to']
                        s.sendmail(msg['From'], [msg['To']], msg.as_string())

    def cmd_build_one(self):
        self.logger.info("Building %s", self.args.app)
        self.build_one(self.args.app, force=True)
        self.logger.info("Built %s", self.args.app)

    def cmd_build_all(self):
        self.logger.info("Building all apps")
        for app in self.apps:
            self.logger.info("Building %s", app)
            self.build_one(app, force=True)
            self.logger.info("Built %s", app)
        self.logger.info("Built all apps")

    def cmd_build_as_needed(self):
        self.logger.info("Building apps as needed")
        for app in self.apps:
            self.build_one(app, force=False)
        self.logger.info("Built all needed apps")


def main():
    kbxbuilder = Kbxbuilder()
    kbxbuilder.go()


if __name__ == '__main__':
    main()
