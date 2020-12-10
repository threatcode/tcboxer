#! /usr/bin/python3

import argparse
import glob
import grp
import io
import json
import logging
import os
import pathlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

import docker

import dockerpty

import jinja2

from packaging.version import parse as parse_version

import prompt_toolkit

import requests

import tabulate

import yaml


class Kaboxer:
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog='kaboxer')
        self.parser.add_argument('--verbose', '-v', action='count', default=0,
                                 help='increase verbosity')

        subparsers = self.parser.add_subparsers(
            title='subcommands', help='action to perform', dest='action',
            required=True)

        parser_run = subparsers.add_parser('run', help='run containerized app')
        parser_run.add_argument('app')
        parser_run.add_argument("--component", help='component to run')
        parser_run.add_argument("--reuse-container", action="store_true",
                                help='run in existing container')
        parser_run.add_argument("--detach", help='run in the background',
                                action="store_true")
        parser_run.add_argument("--prompt-before-exit", action="store_true",
                                help='wait user confirmation before exit')
        parser_run.add_argument("--version", help='version to run')
        parser_run.add_argument('executable', nargs='*')
        parser_run.set_defaults(func=self.cmd_run)

        parser_stop = subparsers.add_parser(
            'stop', help='stop running containerized app')
        parser_stop.add_argument('app')
        parser_stop.add_argument("--component", help='component to stop')
        parser_stop.add_argument("--prompt-before-exit", action="store_true",
                                 help='wait user confirmation before exit')
        parser_stop.set_defaults(func=self.cmd_stop)

        parser_get_meta_file = subparsers.add_parser(
            'get-meta-file',
            help='get installed meta-file of containerized app')
        parser_get_meta_file.add_argument('app')
        parser_get_meta_file.add_argument('file')
        parser_get_meta_file.set_defaults(func=self.cmd_get_meta_file)

        parser_get_upstream_version = subparsers.add_parser(
            'get-upstream-version',
            help='get installed upstram version of containerized app')
        parser_get_upstream_version.add_argument('app')
        parser_get_upstream_version.set_defaults(
            func=self.cmd_get_upstream_version)

        parser_prepare = subparsers.add_parser('prepare',
                                               help='prepare container(s)')
        parser_prepare.add_argument('app', nargs='+')
        parser_prepare.set_defaults(func=self.cmd_prepare)

        parser_upgrade = subparsers.add_parser('upgrade',
                                               help='upgrade container(s)')
        parser_upgrade.add_argument('app', nargs='+')
        parser_upgrade.set_defaults(func=self.cmd_upgrade)

        parser_list = subparsers.add_parser('list', help='list containers')
        parser_list.add_argument("--installed", action="store_true",
                                 help='list installed containers')
        parser_list.add_argument("--available", action="store_true",
                                 help='list available containers')
        parser_list.add_argument("--upgradeable", action="store_true",
                                 help='list upgradeable containers')
        parser_list.add_argument("--all", action="store_true",
                                 help='list all versions of containers')
        parser_list.add_argument("--skip-headers", action="store_true",
                                 help='do not display column headers')
        parser_list.set_defaults(func=self.cmd_list)

        parser_build = subparsers.add_parser('build', help='build image')
        parser_build.add_argument("--skip-image-build", action="store_true",
                                  help='do not build the container image')
        parser_build.add_argument("--save", action="store_true",
                                  help='save container image after build')
        parser_build.add_argument(
            "--push", action="store_true",
            help='push container image to registry after build')
        parser_build.add_argument("--version", help='app version')
        parser_build.add_argument("--ignore-version", action="store_true",
                                  help='ignore version checks')
        parser_build.add_argument('app', nargs='?')
        parser_build.add_argument('path', nargs='?', default=os.getcwd())
        parser_build.set_defaults(func=self.cmd_build)

        parser_install = subparsers.add_parser('install', help='install image')
        parser_install.add_argument("--tarball", action="store_true",
                                    help='install tarball')
        parser_install.add_argument(
            "--destdir", help='build-time destination dir', default='')
        parser_install.add_argument(
            "--prefix", help='prefix for the installation path',
            default='/usr/local')
        parser_install.add_argument('app', nargs='?')
        parser_install.add_argument('path', nargs='?', default=os.getcwd())
        parser_install.set_defaults(func=self.cmd_install)

        parser_clean = subparsers.add_parser('clean', help='clean directory')
        parser_clean.add_argument('app', nargs='?')
        parser_clean.add_argument('path', nargs='?', default=os.getcwd())
        parser_clean.set_defaults(func=self.cmd_clean)

        parser_push = subparsers.add_parser('push',
                                            help='push image to registry')
        parser_push.add_argument('app')
        parser_push.add_argument('path', nargs='?', default=os.getcwd())
        parser_push.add_argument("--version", help='version to push')
        parser_push.set_defaults(func=self.cmd_push)

        parser_save = subparsers.add_parser('save', help='save image')
        parser_save.add_argument('app')
        parser_save.add_argument('file')
        parser_save.set_defaults(func=self.cmd_save)

        parser_load = subparsers.add_parser('load', help='load image')
        parser_load.add_argument('app')
        parser_load.add_argument('file')
        parser_load.set_defaults(func=self.cmd_load)

        parser_purge = subparsers.add_parser('purge', help='purge image')
        parser_purge.add_argument('app')
        parser_purge.add_argument("--prune", action="store_true",
                                  help='prune unused images')
        parser_purge.set_defaults(func=self.cmd_purge)

        self.config_paths = [
            '.',
            '/etc/kaboxer',
            '/usr/local/share/kaboxer',
            '/usr/share/kaboxer',
        ]

    def setup_logging(self):
        loglevels = {
            0: 'ERROR',
            1: 'INFO',
            2: 'DEBUG',
        }
        ll = loglevels.get(self.args.verbose, 'DEBUG')
        ll = getattr(logging, ll)
        self.logger = logging.Logger('kbxbuilder')
        self.logger.setLevel(ll)
        ch = logging.StreamHandler()
        self.logger.addHandler(ch)

    def setup_docker(self):
        self._docker_conn = docker.from_env()
        return self._docker_conn

    def docker_is_working(self):
        try:
            self._docker_conn.containers.list()
            return True
        except Exception:
            return False

    @property
    def docker_conn(self):
        if hasattr(self, '_docker_conn'):
            return self._docker_conn

        self.setup_docker()
        if self.docker_is_working():
            return self._docker_conn
        else:
            groups = list(map(lambda g: grp.getgrgid(g)[0], os.getgroups()))
            if 'docker' in groups:
                self.logger.error("No access to Docker even though you're a "
                                  "member of the docker group, is "
                                  "docker.service running?")
            else:
                self.logger.error("No access to Docker, are you a member "
                                  "of group docker or kaboxer?")
            sys.exit(1)

    def show_exception_in_debug_mode(self):
        if self.args.verbose >= 2:
            self.logger.exception("The following exception was caught")

    def go(self):
        self.args = self.parser.parse_args()
        self.setup_logging()
        self.setup_docker()
        if not self.docker_is_working():
            groups = list(map(lambda g: grp.getgrgid(g)[0], os.getgroups()))
            if 'kaboxer' in groups and 'docker' not in groups:
                # Try to elevate the privileges to docker group if we can
                nc = ['sudo', '-g', 'docker'] + sys.argv
                sys.stdout.flush()
                sys.stderr.flush()
                os.execv('/usr/bin/sudo', nc)
            # Force a new test on first real access if any
            delattr(self, '_docker_conn')

        self.args.func()

    def run_hook_script(self, event, stop_on_failure=False):
        key = event + '_script'

        if key not in self.component_config:
            return
        script_content = self.component_config[key]
        if len(script_content) == 0:
            return

        if script_content.startswith('#!'):
            tmp_script = tempfile.NamedTemporaryFile(
                delete=False, prefix='kaboxer-hook-script')
            tmp_script.write(script_content.encode('utf8'))
            tmp_script.close()
            os.chmod(tmp_script.name, stat.S_IRWXU | stat.S_IRGRP |
                     stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            result = subprocess.run([tmp_script.name])
            os.unlink(tmp_script.name)
        else:
            result = subprocess.run([script_content], shell=True)

        if result.returncode != 0:
            message = "%s hook script failed with returncode %d" % (
                event, result.returncode)
            if stop_on_failure:
                self.logger.error(message)
                sys.exit(1)
            else:
                self.logger.warning(message)

    def cmd_run(self):
        app = self.args.app
        if self.args.version:
            self.prepare_or_upgrade(["%s=%s" % (app, self.args.version)])
            tag_name = self.args.version
        else:
            self.prepare_or_upgrade([app])
            current_apps, _, _, _ = self.list_apps()
            tag_name = current_apps[app]['version']
        self.read_config(app)
        image_name = self.get_image_name(app)
        image = '%s:%s' % (image_name, tag_name)

        self.logger.debug("Running image %s", image)

        self.run_hook_script('before_run', stop_on_failure=True)

        if self.args.reuse_container:
            containers = self.docker_conn.containers.list(filters={'name': app})
            container = containers[0]

        run_mode = self.component_config['run_mode']
        opts = self.component_config.get('docker_options', {})
        if self.args.detach:
            if self.component_config['run_mode'] == 'headless':
                opts['detach'] = True
            else:
                self.logger.error("Can't detach a non-headless component")
                sys.exit(1)

        opts = self.parse_component_config(opts)
        extranets = []
        try:
            netname = self.component_config['networks'][0]
            self.create_network(netname)
            opts['network'] = netname
            extranets = self.component_config['networks'][1:]
        except KeyError:
            pass

        if not self.component_config['run_as_root'] and \
                not self.args.reuse_container:
            opts2 = opts.copy()
            opts2['detach'] = False
            opts2['tty'] = True
            precmds = [
                ['addgroup', '--debug', '--gid', str(self.gid), self.gname],
                ['adduser', '--debug', '--uid', str(self.uid), '--gid',
                 str(self.gid), '--home', self.home_in, '--gecos', self.gecos,
                 '--disabled-password', self.uname],
            ]
            container = self.docker_conn.containers.create(image, **opts2)
            opts['entrypoint'] = container.attrs['Config']['Entrypoint']
            container.remove()
            try:
                del (opts2['command'])
            except KeyError:
                pass
            for precmd in precmds:
                opts2['entrypoint'] = precmd
                container = self.docker_conn.containers.create(image, **opts2)
                container.start()
                container.wait()
                image = container.commit()
                container.remove()
            opts['user'] = self.uid
            opts['environment']['HOME'] = self.home_in

        if run_mode == 'cli':
            opts['tty'] = True
            opts['stdin_open'] = True
        elif run_mode == 'gui':
            self.create_xauth()
            opts['environment']['DISPLAY'] = os.getenv('DISPLAY')
            opts['environment']['XAUTHORITY'] = self.xauth_in
            opts['mounts'].append(docker.types.Mount(
                self.xauth_in, self.xauth_out, type='bind'))
        elif run_mode == 'headless':
            opts['name'] = self.args.app
        else:
            self.logger.error("Unknown run mode")
            sys.exit(1)
        if run_mode == 'gui' or ('allow_x11' in self.component_config and
                                 self.component_config['allow_x11']):
            xsock = '/tmp/.X11-unix'
            opts['mounts'].append(docker.types.Mount(xsock, xsock, type='bind'))

        executable = self.args.executable
        if not len(executable) and 'executable' in self.component_config:
            executable = self.component_config['executable']
        if not isinstance(executable, list):
            executable = shlex.split(executable)
        try:
            executable.extend(shlex.split(self.component_config['extra_opts']))
        except KeyError:
            pass
        try:
            opts['entrypoint'] = ''
        except KeyError:
            pass

        if self.args.reuse_container:
            if run_mode == 'gui':
                self.create_xauth()
                bio = io.BytesIO()
                tf = tarfile.open(mode='w:', fileobj=bio)
                ti = tarfile.TarInfo()
                ti.name = self.xauth_in

                def tifilter(x):
                    if not self.component_config['run_as_root']:
                        x.uid = self.uid
                        x.gid = self.gid
                        x.uname = self.uname
                        x.gname = self.gname
                    return x
                tf.add(self.xauth_out, arcname=self.xauth_in, filter=tifilter)
                tf.close()
                container.put_archive('/', bio.getvalue())
            ex_with_env = ['env']
            for e in opts['environment']:
                ex_with_env.append(
                    "%s=%s" % (e, shlex.quote(opts['environment'][e])))
            ex_with_env.extend(executable)
            executable = ex_with_env
            dockerpty.exec_command(self.docker_conn.api, container.id,
                                   executable)
        else:
            opts['auto_remove'] = True
            container = self.docker_conn.containers.create(image, executable,
                                                           **opts)
            for e in extranets:
                self.create_network(e).connect(container)
            dockerpty.start(self.docker_conn.api, container.id)

        self.run_hook_script('after_run')

        if self.args.detach:
            component_name = self.component_config['name']
            start_message = self.component_config.get(
                'start_message', '%s started' % (component_name, ))
            print(start_message)
        if self.args.prompt_before_exit:
            prompt_toolkit.prompt("Press ENTER to exit")

    def cmd_stop(self):
        app = self.args.app
        self.read_config(app)
        run_mode = self.component_config['run_mode']
        if run_mode == 'headless':
            containers = self.docker_conn.containers.list(filters={'name': app})
            container = containers[0]
            self.run_hook_script('before_stop')
            container.stop()
            self.run_hook_script('after_stop')
            component_name = self.component_config['name']
            stop_message = self.component_config.get(
                'stop_message', "%s stopped" % (component_name, ))
            print(stop_message)
            if self.args.prompt_before_exit:
                prompt_toolkit.prompt("Press ENTER to exit")
        else:
            self.logger.error("Can't stop a non-headless component")
            sys.exit(1)

    def get_meta_file(self, image, filename):
        with tempfile.NamedTemporaryFile(mode='w+t',
                                         prefix="getmetafile") as tmp:
            self.extract_file_from_image(
                image, os.path.join('/kaboxer/', filename), tmp.name)
            v = str(open(tmp.name).read())
            return v

    def cmd_get_meta_file(self):
        self.read_config(self.args.app)
        image = 'kaboxer/' + self.args.app
        print(self.get_meta_file(image, self.args.file))

    def cmd_get_upstream_version(self):
        self.read_config(self.args.app)
        image = 'kaboxer/' + self.args.app
        print(self.get_meta_file(image, 'version'))

    def find_config_for_build_apps(self):
        path = self.args.path
        yamlfiles = []
        globs = ['kaboxer.yaml', '*.kaboxer.yaml']
        parsed_configs = {}
        for g in globs:
            for f in glob.glob(os.path.join(path, g)):
                yamlfiles.append(f)
        for f in yamlfiles:
            y = yaml.safe_load(open(f))
            app = y.get('application', {}).get('id')
            if app is None:
                continue
            if self.args.app and self.args.app != app:
                continue
            if app in parsed_configs:
                continue
            parsed_configs[app] = y
            parsed_configs[app]['_config_file'] = f
        if not parsed_configs:
            self.logger.error("Failed to find appropriate kaboxer.yaml file")
            sys.exit(1)
        return parsed_configs

    def do_version_checks(self, v, config):
        parsed_v = parse_version(v)
        try:
            minv = str(config['packaging']['min_upstream_version'])
            parsed_minv = parse_version(minv)
            if parsed_v < parsed_minv:
                raise Exception(
                    "Unsupported upstream version %s < %s" % (v, minv))
        except KeyError:
            pass
        try:
            maxv = str(config['packaging']['max_upstream_version'])
            parsed_maxv = parse_version(maxv)
            if parsed_v > parsed_maxv:
                raise Exception(
                    "Unsupported upstream version %s > %s" % (v, maxv))
        except KeyError:
            pass

    def cmd_build(self):
        parsed_configs = self.find_config_for_build_apps()
        for app in parsed_configs:
            parsed_config = parsed_configs[app]
            if not self.args.skip_image_build:
                self.build_image(parsed_config)
            self.build_desktop_files(parsed_config)

    def build_image(self, parsed_config):
        path = self.args.path
        app = parsed_config['application']['id']
        self.logger.info("Building container image for %s", app)
        try:
            df = os.path.join(path, parsed_config['build']['docker']['file'])
        except KeyError:
            df = os.path.join(path, 'Dockerfile')
        try:
            buildargs = parsed_config['build']['docker']['parameters']
        except KeyError:
            buildargs = {}
        if self.args.version:
            if not self.args.ignore_version:
                try:
                    self.do_version_checks(self.args.version, parsed_config)
                except Exception as e:
                    message = str(e)
                    self.logger.error(message)
                    sys.exit(1)
            buildargs['KBX_APP_VERSION'] = self.args.version
        (image, _) = self.docker_conn.images.build(
            path=path, dockerfile=df, rm=True, forcerm=True, nocache=True,
            pull=True, quiet=False, buildargs=buildargs)
        with tempfile.NamedTemporaryFile(mode='w+t') as tmp:
            try:
                self.extract_file_from_image(image, '/kaboxer/version',
                                             tmp.name)
                saved_version = open(tmp.name).readline().strip()
                if not self.args.ignore_version:
                    try:
                        self.do_version_checks(saved_version, parsed_config)
                    except Exception as e:
                        message = str(e)
                        self.docker_conn.images.remove(image=image.id)
                        self.logger.error(message)
                        sys.exit(1)
            except Exception:
                if self.args.version:
                    saved_version = self.args.version
                    tmp.write(self.args.version)
                else:
                    self.logger.error(
                        "Unable to determine version (use --version?)")
                    self.docker_conn.images.remove(image=image.id)
                    sys.exit(1)
            tmp.flush()
            image = self.inject_file_into_image(image, tmp.name,
                                                '/kaboxer/version')
        with tempfile.NamedTemporaryFile(mode='w+t') as tmp:
            tmp.write(str(parsed_config['packaging']['revision']) + "\n")
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, '/kaboxer/packaging-revision')
        with tempfile.NamedTemporaryFile(mode='w+t') as tmp:
            tmp.write(yaml.dump(sys.argv))
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, '/kaboxer/kaboxer-build-cmd')
            image = self.inject_file_into_image(
                image, df, '/kaboxer/Dockerfile')
        with tempfile.NamedTemporaryFile(mode='w+t') as tmp:
            savedbuildargs = {
                'rm': True,
                'forcerm': True,
                'path': path,
                'dockerfile': df,
                'buildargs': buildargs
            }
            tmp.write(yaml.dump(savedbuildargs))
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, '/kaboxer/docker-build-parameters')
            tagname = 'kaboxer/%s:%s' % (app, str(saved_version))
            image.tag(tagname)
            tagname = 'kaboxer/%s:latest' % (app,)
            if not self.find_image(tagname):
                image.tag(tagname)
        if self.args.save:
            tarball = os.path.join(
                path, parsed_config['application']['id'] + '.tar')
            self.save_image_to_file(image, tarball)
        if self.args.push:
            self.push([saved_version])

    def build_desktop_files(self, parsed_config):
        app = parsed_config['application']['id']
        if 'desktop-files' not in parsed_config.get('install', {}):
            self.logger.info("Building desktop files for %s", app)
            self.gen_desktop_files(parsed_config)

    def extract_version_from_image(self, image):
        with tempfile.NamedTemporaryFile(mode='w+t') as tmp:
            self.extract_file_from_image(image.id, '/kaboxer/version', tmp.name)
            saved_version = open(tmp.name).readline().strip()
        return parse_version(saved_version)

    def cmd_push(self):
        self.push()

    def push(self, versions=[]):
        parsed_configs = self.find_config_for_build_apps()
        for app in parsed_configs:
            self.logger.info("Pushing %s", app)

            # Build the remote name of the image
            parsed_config = parsed_configs[app]
            if 'registry' not in parsed_config['container']['origin']:
                self.logger.error("No registry defined for %s", app)
                sys.exit(1)
            registry_data = parsed_config['container']['origin']['registry']
            registry = registry_data['url']
            registry = re.sub('^https?://', '', registry)
            try:
                imagename = registry_data['image']
            except KeyError:
                imagename = parsed_config['application']['id']
            remotename = '%s/%s' % (registry, imagename)
            localname = 'kaboxer/%s' % app

            # Always fetch the latest tag to be able to compare and update
            # it if required
            self.docker_pull('%s:latest' % remotename)

            # Figure out which versions to push
            if len(versions) == 0:
                if self.args.version:
                    try:
                        self.do_version_checks(self.args.version,
                                               parsed_configs)
                        versions = [self.args.version]
                    except Exception as e:
                        message = str(e)
                        self.logger.error(message)
                        sys.exit(1)
                else:
                    for image in self.docker_conn.images.list():
                        for tag in image.tags:
                            (i, ver) = tag.rsplit(':', 1)
                            if i != localname:
                                continue
                            if ver == 'current' or ver == 'latest':
                                continue
                            versions.append(ver)

            # Push each version
            for version in versions:
                local_tagname = "%s:%s" % (localname, version)
                local_image = self.find_image(local_tagname)
                if not local_image:
                    self.logger.error("No %s image found", local_tagname)
                    sys.exit(1)
                saved_version = self.extract_version_from_image(local_image)
                remote_tagname = '%s:%s' % (remotename, saved_version)
                local_image.tag(remote_tagname)
                self.docker_conn.images.push(remote_tagname)

            # Update remote latest tag if needed
            local_tagname = '%s:latest' % localname
            local_image = self.find_image(local_tagname)
            remote_tagname = '%s:latest' % remotename
            remote_image = self.find_image(remote_tagname)

            must_update = False
            if not remote_image and local_image:
                # Remote side has no latest tag yet, force update
                must_update = True
            elif remote_image and local_image:
                # Otherwise update only if we have newer or same version
                local_version = self.extract_version_from_image(local_image)
                remote_version = self.extract_version_from_image(remote_image)
                if local_version >= remote_version:
                    must_update = True

            if must_update:
                local_image.tag(remote_tagname)
                self.docker_conn.images.push(remote_tagname)

    def gen_desktop_files(self, parsed_config):
        template_text = """[Desktop Entry]
Name={{ p.name }}
Comment={{ p.comment }}
Exec={{ p.exec }}
Icon=kaboxer-{{ p.appid }}
Terminal={{ p.terminal }}
Type=Application
Categories={{ p.categories }}

"""
        t = jinja2.Template(template_text)
        for component, component_data in parsed_config['components'].items():
            params = {
                'comment': parsed_config['application'].get('description',
                                                            '').split('\n')[0],
                'component': component,
                'appid': parsed_config['application']['id'],
                'categories': parsed_config['application'].get('categories',
                                                               'Uncategorized'),
            }
            params['reuse_container'] = ''
            if component_data.get('reuse_container', False):
                params['reuse_container'] = '--reuse-container '

            component_name = component_data.get(
                'name', parsed_config['application']['name'])

            if component_data['run_mode'] == 'headless':
                # One .desktop file for starting
                params['name'] = "Start %s" % (component_name,)
                params['terminal'] = 'true'
                params['exec'] = (
                    "kaboxer run --detach --prompt-before-exit %s"
                    "--component %s %s" %
                    (params['reuse_container'], params['component'],
                     params['appid']))
                ofname = 'kaboxer-%s-%s-start.desktop' % (
                    parsed_config['application']['id'], component)
                with open(ofname, 'w') as outfile:
                    outfile.write(t.render(p=params))
                # One .desktop file for stopping
                params['name'] = "Stop %s" % (component_name,)
                params['terminal'] = 'true'
                params['exec'] = (
                    "kaboxer stop --prompt-before-exit %s"
                    "--component %s %s" %
                    (params['reuse_container'], params['component'],
                     params['appid']))
                ofname = 'kaboxer-%s-%s-stop.desktop' % (
                    parsed_config['application']['id'], component)
                with open(ofname, 'w') as outfile:
                    outfile.write(t.render(p=params))
            else:
                params['name'] = component_name
                ofname = 'kaboxer-%s-%s.desktop' % (
                    parsed_config['application']['id'], component)
                params['exec'] = "kaboxer run %s--component %s %s" % (
                    params['reuse_container'], params['component'],
                    params['appid'])
                if component_data['run_mode'] == 'cli':
                    params['terminal'] = 'true'
                else:
                    params['terminal'] = 'false'
                with open(ofname, 'w') as outfile:
                    outfile.write(t.render(p=params))

    def cmd_clean(self):
        path = os.path.realpath(self.args.path)
        parsed_configs = self.find_config_for_build_apps()
        for app in parsed_configs:
            self.logger.info("Cleaning %s", app)
            parsed_config = parsed_configs[app]
            app = parsed_config['application']['id']
            tarball = os.path.join(path,
                                   parsed_config['application']['id'] + '.tar')
            if os.path.commonpath([path, tarball]) == path and \
                    os.path.isfile(tarball):
                os.unlink(tarball)
            generateddesktopfiles = self._list_desktop_files(
                parsed_config, generated_only=True)
            for d in generateddesktopfiles:
                if os.path.isfile(d):
                    os.unlink(d)

    def install_to_path(self, f, path):
        if self.args.destdir == '':
            builddestpath = path
        else:
            builddestpath = os.path.join(self.args.destdir,
                                         os.path.relpath(path, '/'))
        self.logger.info("Installing %s to %s", f, builddestpath)
        os.makedirs(builddestpath, exist_ok=True)
        shutil.copy(f, builddestpath)

    def _list_desktop_files(self, parsed_config, generated_only=False):
        try:
            desktopfiles = parsed_config['install']['desktop-files']
            if generated_only:
                return []
        except KeyError:
            desktopfiles = []
            for component, data in parsed_config['components'].items():
                if data['run_mode'] == 'headless':
                    desktopfiles.append('kaboxer-%s-%s-start.desktop' % (
                        parsed_config['application']['id'], component))
                    desktopfiles.append('kaboxer-%s-%s-stop.desktop' % (
                        parsed_config['application']['id'], component))
                else:
                    desktopfiles.append('kaboxer-%s-%s.desktop' % (
                        parsed_config['application']['id'], component))
        return desktopfiles

    def cmd_install(self):
        main_destpath = os.path.join(self.args.prefix, 'share', 'kaboxer')
        path = self.args.path
        parsed_configs = self.find_config_for_build_apps()
        for app in parsed_configs:
            self.logger.info("Installing %s", app)
            parsed_config = parsed_configs[app]
            # Install image tarball
            if self.args.tarball:
                tarball = os.path.join(path, app + '.tar')
                try:
                    self.install_to_path(tarball, main_destpath)
                except shutil.SameFileError:
                    pass
            # Install kaboxer.yaml file
            # Update it first if we ship the tarball
            with tempfile.TemporaryDirectory() as td:
                filtered_config_file = parsed_config.copy()
                tf = os.path.join(td, app + '.kaboxer.yaml')
                if self.args.tarball:
                    # Rewrite the YAML file with the tarball data
                    del(filtered_config_file['_config_file'])
                    origin_data = {
                        'tarball': os.path.join(main_destpath, app + '.tar'),
                    }
                    if 'container' not in filtered_config_file:
                        filtered_config_file['container'] = {}
                    filtered_config_file['container']['origin'] = origin_data
                    with open(tf, 'w') as y:
                        y.write(yaml.dump(filtered_config_file))
                else:
                    # Copy over the unmodified file
                    shutil.copy(parsed_config['_config_file'], tf)

                self.install_to_path(tf, main_destpath)
            # Install desktop file(s)
            desktopfiles = self._list_desktop_files(parsed_config)
            for d in desktopfiles:
                self.install_to_path(
                    os.path.join(path, d),
                    os.path.join(self.args.prefix, 'share', 'applications'))
            # Install icon file(s)
            try:
                iconfile = parsed_config['install']['icon']
                (_, ife) = os.path.splitext(os.path.basename(iconfile))
                with tempfile.TemporaryDirectory() as td:
                    renamed_icon = os.path.join(td, 'kaboxer-%s%s' % (
                        parsed_config['application']['id'], ife))
                    shutil.copy(iconfile, renamed_icon)
                    self.install_to_path(renamed_icon, os.path.join(
                        self.args.prefix, 'share', 'icons'))
            except KeyError:
                pass
            try:
                iconfile = parsed_config['install']['extract-icon']
                (_, ife) = os.path.splitext(os.path.basename(iconfile))
                with tempfile.TemporaryDirectory() as td:
                    renamed_icon = os.path.join(td, 'kaboxer-%s%s' % (
                        parsed_config['application']['id'], ife))
                    self.extract_file_from_image(
                        'kaboxer/' + parsed_config['application']['id'],
                        iconfile, renamed_icon)
                    self.install_to_path(
                        renamed_icon,
                        os.path.join(self.args.prefix, 'share', 'icons'))
            except KeyError:
                pass

    def extract_file_from_image(self, image, infile, outfile):
        try:
            temp_container = self.docker_conn.containers.create(image)
            (bits, stat) = temp_container.get_archive(infile)
            with tempfile.TemporaryFile() as temptar:
                for chunk in bits:
                    temptar.write(chunk)
                temptar.seek(0)
                tf = tarfile.open(fileobj=temptar)
                ti = tf.getmembers()[0]
                with tempfile.TemporaryDirectory() as td:
                    tf.extract(ti, path=td, set_attrs=False)
                    shutil.move(os.path.join(td, ti.name), outfile)
        finally:
            temp_container.remove()

    def extract_file_from_tarball(self, tarball, infile, outfile):
        tf = tarfile.open(tarball)
        manifest = tf.extractfile('manifest.json')
        j = json.loads(manifest.read())
        relpath = os.path.relpath(infile, '/')
        for layer in j[0]['Layers']:
            tfl = tarfile.open(fileobj=tf.extractfile(layer))
            try:
                with tempfile.TemporaryDirectory() as td:
                    tfl.extract(relpath, path=td)
                    shutil.move(os.path.join(td, relpath), outfile)
                    return 1
            except KeyError:
                continue
        raise Exception('Not found')

    def get_meta_file_from_tarball(self, tarball, filename):
        with tempfile.NamedTemporaryFile(mode='w+t',
                                         prefix="getmetafile") as tmp:
            self.extract_file_from_tarball(
                tarball, os.path.join('/kaboxer/', filename), tmp.name)
            v = str(open(tmp.name).read())
            return v

    def inject_file_into_image(self, image, outfile, infile):
        temp_container = self.docker_conn.containers.create(image)
        with tempfile.TemporaryFile() as temptar:
            tf = tarfile.open(fileobj=temptar, mode='w')
            (dirname, filename) = os.path.split(infile)
            p = pathlib.Path(dirname)
            for parent in reversed(p.parents):
                ti = tarfile.TarInfo(name=str(parent))
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            ti = tarfile.TarInfo(name=infile)
            ti.size = os.stat(outfile).st_size
            tf.addfile(ti, fileobj=open(outfile, mode='rb'))
            tf.close()
            temptar.seek(0)
            buf = b''
            while True:
                b = temptar.read()
                if not b:
                    break
                buf += b
            temp_container.put_archive('/', buf)
        image = temp_container.commit()
        temp_container.remove()
        return image

    def cmd_save(self):
        images = self.docker_conn.images.list()
        for image in images:
            for tag in image.tags:
                if tag == 'kaboxer/' + self.args.app + ':latest':
                    self.save_image_to_file(image, self.args.file)
                    return
        self.logger.error("No image found")
        sys.exit(1)

    def save_image_to_file(self, image, destfile):
        with open(destfile, 'wb') as f:
            for chunk in image.save():
                f.write(chunk)

    def load_image(self, tarfile, appname, tag):
        f = open(tarfile, 'rb')
        for image in self.docker_conn.images.load(f):
            image.tag('kaboxer/' + appname, tag=tag)
        return image

    def cmd_load(self):
        v = self.get_meta_file_from_tarball(self.args.file, 'version').strip()
        self.logger.info("Loading %s at version %s", self.args.app, v)
        self.load_image(self.args.file, self.args.app, v)

    def find_image(self, name):
        images = self.docker_conn.images.list()
        candidates = {}
        for image in images:
            for tag in image.tags:
                if tag == name:
                    return image
                if tag[:len(name)] == name and tag[len(name)] == ':':
                    ver = tag[len(name) + 1:]
                    candidates[tag] = {'image': image,
                                       'version': parse_version(ver)}
        if len(candidates):
            versions = [candidates[x]['version'] for x in candidates.keys()]
            maxver = sorted(versions)[-1]
            for c in candidates:
                if candidates[c]['version'] == maxver:
                    return candidates[c]['image']
        return False

    def get_image_name(self, app, config=None):
        if config is None:
            config = self.load_config(app)
        try:
            if 'registry' in config['container']['origin']:
                registry = config['container']['origin']['registry']['url']
                registry = re.sub('^https?://', '', registry)
                try:
                    image = config['container']['origin']['registry']['image']
                except KeyError:
                    image = config['application']['id']
                return "%s/%s" % (registry, image)
        except KeyError:
            pass
        return "kaboxer/%s" % (config['application']['id'],)

    def cmd_prepare(self):
        self.prepare_or_upgrade(self.args.app)

    def cmd_upgrade(self):
        self.prepare_or_upgrade(self.args.app, upgrade=True)

    def do_upgrade_scripts(self, app, oldver, newver):
        self.read_config(app)
        if oldver is None or oldver == newver:
            return
        self.logger.info("Running upgrade scripts for %s (%s -> %s)",
                         app, oldver, newver)
        image_name = self.get_image_name(app)
        with tempfile.TemporaryDirectory() as td:
            s = td
            t = '/kaboxer/upgrade-data'
            opts = {'mounts': [docker.types.Mount(t, s, type='bind')]}
            opts = self.parse_component_config(opts)
            full_image_name = '%s:%s' % (image_name, oldver)
            container = self.docker_conn.containers.create(
                full_image_name, ['/kaboxer/scripts/pre-upgrade'], **opts)
            dockerpty.start(self.docker_conn.api, container.id)
            container.stop()
            container.remove()
            full_image_name = '%s:%s' % (image_name, newver)
            container = self.docker_conn.containers.create(
                full_image_name, ['/kaboxer/scripts/post-upgrade', oldver],
                **opts)
            dockerpty.start(self.docker_conn.api, container.id)
            container.stop()
            container.remove()

    def docker_pull(self, full_image_name, stop_on_error=False):
        self.logger.info("Pulling %s image from registry", full_image_name)
        try:
            image = self.docker_conn.images.pull(full_image_name)
            return image
        except docker.errors.APIError:
            self.logger.exception("Could not pull %s, wrong URL?",
                                  full_image_name)
            if stop_on_error:
                sys.exit(1)

    def prepare_or_upgrade(self, apps, upgrade=False):
        current_apps, registry_apps, tarball_apps, available_apps = \
            self.list_apps(get_remotes=True, restrict=apps)
        for app in apps:
            self.logger.info("Preparing %s", app)
            previous_version = None
            m = re.search('([^=]+)=([^=]+)$', app)
            if m:
                app = m.group(1)
                target_version = m.group(2)
                if app in current_apps:
                    previous_version = current_apps[app]['version']
                    if parse_version(target_version) != \
                            parse_version(previous_version) and \
                            not upgrade:
                        self.logger.exception(
                            "%s is at version %s, can't run %s=%s",
                            app, previous_version, app, target_version)
                        sys.exit(1)
            else:
                maxavail = ''
                try:
                    maxavail = available_apps[app]['maxversion']['version']
                except KeyError:
                    pass
                try:
                    tarball_ver = parse_version(tarball_apps[app]['version'])
                    if maxavail == '' or tarball_ver > parse_version(maxavail):
                        maxavail = tarball_apps[app]['version']
                except KeyError:
                    pass
                try:
                    registry_ver = parse_version(
                        registry_apps[app]['maxversion'])
                    if maxavail == '' or registry_ver > parse_version(maxavail):
                        maxavail = registry_apps[app]['maxversion']
                except KeyError:
                    pass

                if app in current_apps:
                    previous_version = current_apps[app]['version']
                    target_version = previous_version
                else:
                    target_version = maxavail
                if upgrade:
                    target_version = maxavail
                self.read_config(app)

            if previous_version and upgrade and \
                    parse_version(target_version) <= \
                    parse_version(previous_version):
                target_version = previous_version

            if not target_version:
                # We could not find any version info, let's use the latest tag
                target_version = 'latest'

            image_name = self.get_image_name(app)
            full_image_name = '%s:%s' % (image_name, target_version)
            current_image_name = '%s:%s' % (image_name, 'current')
            if previous_version == target_version:
                return
            config = self.load_config(app)
            try:
                try:
                    max_avail_version = parse_version(
                        available_apps[app]['maxversion']['version'])
                    if max_avail_version == parse_version(target_version):
                        image = self.find_image(full_image_name)
                        image.tag(current_image_name)
                        self.do_upgrade_scripts(app, previous_version,
                                                target_version)
                        return
                except Exception:
                    self.show_exception_in_debug_mode()
                if 'registry' in config['container']['origin']:
                    found_image = self.find_image(full_image_name)
                    if found_image:
                        found_image.tag(current_image_name)
                    else:
                        image = self.docker_pull(full_image_name,
                                                 stop_on_error=True)
                        if target_version == 'latest':
                            pulled_version = self.get_meta_file(
                                image, 'version').strip()
                            versioned_image_name = '%s:%s' % (
                                image_name, pulled_version)
                            if not self.find_image(versioned_image_name):
                                image.tag(versioned_image_name)
                        image.tag(current_image_name)
                        self.do_upgrade_scripts(app, previous_version,
                                                target_version)
                    return
                if 'tarball' in config['container']['origin']:
                    paths = [
                        '.',
                        '/usr/local/share/kaboxer',
                        '/usr/share/kaboxer',
                    ]
                    for p in paths:
                        tarfile = os.path.join(
                            p, config['container']['origin']['tarball'])
                        if os.path.isfile(tarfile):
                            self.logger.info("Loading image from %s", tarfile)
                            image = self.load_image(tarfile, app,
                                                    target_version)
                            image.tag(current_image_name)
                        self.do_upgrade_scripts(app, previous_version,
                                                target_version)
                        return
            except KeyError:
                pass
            if not self.find_image(full_image_name):
                paths = [
                    '.',
                    '/usr/local/share/kaboxer',
                    '/usr/share/kaboxer',
                ]
                for p in paths:
                    tarfile = os.path.join(
                        p, self.config['application']['id'] + '.tar')
                    if os.path.isfile(tarfile):
                        self.logger.info("Loading image from %s", tarfile)
                        self.load_image(tarfile, app, target_version)
                        self.do_upgrade_scripts(app, previous_version,
                                                target_version)
                        return
            self.logger.error("Cannot prepare image")
            sys.exit(1)

    def cmd_purge(self):
        current_apps, _, _, available_apps = self.list_apps()
        if self.args.app in current_apps:
            self.docker_conn.images.remove('kaboxer/%s:current' %
                                           (self.args.app,))
        if self.args.app in available_apps:
            self.docker_conn.images.remove('kaboxer/%s:%s' % (
                self.args.app,
                available_apps[self.args.app]['maxversion']['version']))
            try:
                self.docker_conn.images.remove('kaboxer/%s' % (self.args.app,))
            except Exception:
                self.show_exception_in_debug_mode()
            if self.args.prune:
                self.docker_conn.images.prune(filters={'dangling': True})

    def list_apps(self, get_remotes=False, restrict=None):
        current_apps = {}
        registry_apps = {}
        tarball_apps = {}
        available_apps = {}

        if restrict is not None:
            restrict = [re.sub('=.*', '', i) for i in restrict]

        globs = ['kaboxer.yaml', '*.kaboxer.yaml']
        for p in self.config_paths:
            # XXX: factorize logic to find yaml files in a given dir
            for g in globs:
                for f in glob.glob(os.path.join(p, g)):
                    try:
                        y = yaml.safe_load(open(f))
                        aid = y['application']['id']
                        if restrict is not None and aid not in restrict:
                            continue
                        try:
                            imagename = self.get_image_name(aid)
                            # XXX: factorize logic to find the right image
                            for image in self.docker_conn.images.list():
                                for tag in image.tags:
                                    (i, ver) = tag.rsplit(':', 1)
                                    if i != imagename:
                                        continue
                                    curver = self.get_meta_file(
                                        image, 'version').strip()
                                    item = {
                                        'version': curver,
                                        'packaging-revision-from-image':
                                        self.get_meta_file(
                                            image, 'packaging-revision'
                                        ).strip(),
                                        'packaging-revision-from-yaml':
                                        y['packaging']['revision'],
                                    }
                                    if ver == 'current':
                                        current_apps[aid] = item
                                    if aid not in available_apps:
                                        available_apps[aid] = {}
                                    available_apps[aid][ver] = item
                                    _maxversion = available_apps[aid].get(
                                        'maxversion')
                                    if _maxversion:
                                        max_avail_version = parse_version(
                                            _maxversion['version'])
                                    if not _maxversion or max_avail_version <= \
                                            parse_version(curver):
                                        available_apps[aid]['maxversion'] = item
                        except Exception as e:
                            print(e)
                            pass

                        try:
                            registry_apps[aid] = {
                                'url':
                                y['container']['origin']['registry']['url'],
                                'image':
                                y['container']['origin']['registry']['image'],
                                'packaging-revision-from-yaml':
                                y['packaging']['revision'],
                            }
                        except KeyError:
                            pass
                        try:
                            _tarball = y['container']['origin']['tarball']
                            _ver = self.get_meta_file_from_tarball(
                                _tarball, 'version').strip()
                            _pkg_rev_img = self.get_meta_file_from_tarball(
                                _tarball, 'packaging-revision').strip()
                            _pkg_rev_yaml = y['packaging']['revision']
                            tarball_apps[aid] = {
                                'tarball': _tarball,
                                'version': _ver,
                                'packaging-revision-from-image': _pkg_rev_img,
                                'packaging-revision-from-yaml': _pkg_rev_yaml,
                            }
                        except Exception:
                            pass
                    except Exception:
                        pass

        if get_remotes:
            for aid in registry_apps:
                url = registry_apps[aid]['url']
                if not re.match('https?://', url):
                    url = 'http://' + url
                comps = re.split('/', url)
                h = '/'.join(comps[:3])
                p = '/'.join(comps[3:])
                i = registry_apps[aid]['image']
                u2 = 'v2/%s/%s/tags' % (p, i)
                u2 = re.sub('//', '/', u2)
                registry_apps[aid]['versions'] = []
                fullurl = "%s/%s" % (h, u2)
                self.logger.debug("Querying registry on official API URL: %s",
                                  fullurl)
                req = None
                try:
                    req = requests.get(fullurl)
                except requests.ConnectionError:
                    self.logger.warning("Could not query registry on %s",
                                        fullurl, exc_info=1)
                if req is not None and req.ok:
                    json_data = req.json()
                    self.logger.debug('Results: %s', json_data)
                    results = json_data.get('results', [])
                    for r in results:
                        registry_apps[aid]['versions'].append(r['name'])
                elif req is not None and not req.ok:
                    self.logger.debug(
                        "HTTP request failed with status_code = %d",
                        req.status_code)
                    fullurl = "%s/%s/list" % (h, u2)
                    self.logger.debug("Querying registry on alternate URL: %s",
                                      fullurl)
                    req = None
                    try:
                        req = requests.get(fullurl)
                    except requests.ConnectionError:
                        self.logger.warning("Could not query registry on %s",
                                            fullurl, exc_info=1)
                    if req is not None and req.ok:
                        json_data = req.json()
                        self.logger.debug('Results: %s', json_data)
                        results = json_data.get('tags', [])
                        for r in results:
                            registry_apps[aid]['versions'].append(r)
                    elif req is not None and not req.ok:
                        self.logger.debug(
                            "HTTP request failed with status_code = %d",
                            req.status_code)

                curmax = max(registry_apps[aid]['versions'], default=None,
                             key=lambda x: parse_version(x))
                if curmax:
                    self.logger.debug("Maximal version for image %s is %s",
                                      aid, curmax)
                    registry_apps[aid]['maxversion'] = curmax
                else:
                    self.logger.debug("No versions found for image %s", aid)
        return (current_apps, registry_apps, tarball_apps, available_apps)

    def cmd_list(self):
        show_installed = self.args.installed
        show_available = self.args.available
        show_upgradeable = self.args.upgradeable
        if self.args.all:
            show_installed = True
            show_available = True
            show_upgradeable = True
        if not show_available and not show_upgradeable:
            show_installed = True
        current_apps, registry_apps, tarball_apps, available_apps = \
            self.list_apps(get_remotes=(show_available or show_upgradeable))
        app_data = {}
        if show_installed:
            for aid in current_apps:
                if aid not in app_data:
                    app_data[aid] = {'app': aid}
                app_data[aid]['installed'] = current_apps[aid]['version']
                app_data[aid]['pacrev-yaml'] = (
                    current_apps[aid]['packaging-revision-from-yaml'])
                app_data[aid]['pacrev-image'] = (
                    current_apps[aid]['packaging-revision-from-image'])
        if show_available:
            for aid in registry_apps:
                for tag in registry_apps[aid]['versions']:
                    if aid not in app_data:
                        app_data[aid] = {'app': aid}
                    app_data[aid]['available'] = tag
            for aid in available_apps:
                if aid not in app_data:
                    app_data[aid] = {'app': aid}
                max_avail_version = parse_version(
                    available_apps[aid]['maxversion']['version'])
                if 'available' not in app_data[aid] or max_avail_version > \
                        parse_version(app_data[aid]['available']):
                    app_data[aid]['available'] = (
                        available_apps[aid]['maxversion']['version'])

        if show_upgradeable:
            for aid in current_apps:
                if aid not in app_data:
                    app_data[aid] = {'app': aid}
                app_data[aid]['installed'] = current_apps[aid]['version']
                app_data[aid]['pacrev-yaml'] = (
                    current_apps[aid]['packaging-revision-from-yaml'])
                app_data[aid]['pacrev-image'] = (
                    current_apps[aid]['packaging-revision-from-image'])
                if aid in registry_apps:
                    if 'maxversion' not in registry_apps[aid]:
                        continue
                    if parse_version(registry_apps[aid]['maxversion']) > \
                            parse_version(current_apps[aid]['version']):
                        app_data[aid]['available'] = (
                            registry_apps[aid]['maxversion'])
                elif aid in tarball_apps:
                    if parse_version(tarball_apps[aid]['version']) > \
                            parse_version(current_apps[aid]['version']):
                        app_data[aid]['available'] = (
                            tarball_apps[aid]['version'])

        app_data_fields = {
            "app": "App",
            "installed": "Installed version",
            "available": "Available version",
            "pacrev-yaml": "Packaging revision from YAML",
            "pacrev-image": "Packaging revision from image",
        }
        for aid in app_data:
            app_data[aid]['app'] = aid
            for k in app_data_fields:
                if k not in app_data[aid]:
                    app_data[aid][k] = '-'
            app_data[aid] = {k: app_data[aid][k] for k in app_data_fields}
        if self.args.skip_headers:
            print(tabulate.tabulate(app_data.values(),
                                    numalign="right",
                                    disable_numparse=True,
                                    ))
        else:
            print(tabulate.tabulate(app_data.values(),
                                    headers=app_data_fields,
                                    numalign="right",
                                    disable_numparse=True,
                                    ))

    def load_config(self, app=None):
        for p in self.config_paths:
            for filename in [app + '.kaboxer.yaml', 'kaboxer.yaml']:
                config_file = os.path.join(p, filename)
                if os.path.isfile(config_file):
                    try:
                        y = yaml.safe_load(open(config_file))
                        if y['application']['id'] == app:
                            return y
                    except Exception:
                        self.logger.warning("Failed to parse %s as YAML",
                                            config_file, exc_info=1)
        self.logger.error("Could not find appropriate config file for %s", app)
        sys.exit(1)

    def read_config(self, app):
        self.config = self.load_config(app)

        components_to_try = []
        if 'component' in self.args:
            # Given on command line
            components_to_try.append(self.args.component)
        components_to_try.extend([
            # Specified in yaml file
            self.config.get('container', {}).get('default_component'),
            # Default name
            'default',
            # First one in alphabetical order
            sorted(self.config['components'].keys())[0]
        ])

        for component in components_to_try:
            if component not in self.config['components']:
                continue
            self.component_config = self.config['components'][component]
            if 'name' not in self.component_config:
                self.component_config['name'] = "%s/%s" % (app, component)
            return

        self.logger.error("Can't find an appropriate component")
        sys.exit(1)

    def parse_component_config(self, opts):
        if 'environment' not in opts:
            opts['environment'] = {}
        if 'mounts' not in opts:
            opts['mounts'] = []
        try:
            ports = {}
            for publish_port in self.component_config['publish_ports']:
                ports[publish_port] = publish_port
            opts['ports'] = ports
        except KeyError:
            pass
        if 'run_as_root' not in self.component_config:
            self.component_config['run_as_root'] = False

        if self.component_config['run_as_root']:
            self.home_in = '/root'
        else:
            import pwd
            self.uid = os.getuid()
            self.uname = pwd.getpwuid(self.uid).pw_name
            self.gecos = pwd.getpwuid(self.uid).pw_gecos
            self.gid = pwd.getpwuid(self.uid).pw_gid
            self.gname = grp.getgrgid(self.gid).gr_name
            self.home_in = os.path.join('/home', self.uname)

        try:
            for mount in self.component_config['mounts']:
                s = mount['source']
                s = os.path.expanduser(s)
                try:
                    os.makedirs(s)
                except FileExistsError:
                    pass
                t = mount['target']
                if t == '~':
                    t = self.home_in
                else:
                    t = re.sub('^~/', self.home_in + '/', t)
                opts['mounts'].append(docker.types.Mount(t, s, type='bind'))
        except KeyError:
            pass

        return opts

    def create_network(self, netname):
        for n in self.docker_conn.networks.list():
            if n.name == netname:
                return n
        return self.docker_conn.networks.create(name=netname, driver='bridge')

    def create_xauth(self):
        if os.getenv('DISPLAY') is None:
            self.logger.error(
                "No DISPLAY set, are you running in a graphical session?")
            sys.exit(1)
        self.xauth_out = os.path.join(os.getenv('HOME'), '.docker.xauth')
        self.xauth_in = os.path.join(self.home_in, '.docker.xauth')
        f = subprocess.Popen(['xauth', 'nlist', os.getenv('DISPLAY')],
                             stdout=subprocess.PIPE).stdout
        g = subprocess.Popen(['xauth', '-f', self.xauth_out, 'nmerge', '-'],
                             stdin=subprocess.PIPE).stdin
        for line in f:
            line = str(line, 'utf-8')
            line.strip()
            ll = re.sub('^[^ ]*', 'ffff', line) + "\n"
            g.write(bytes(ll, 'utf-8'))
        g.close()
        f.close()


def main():
    kaboxer = Kaboxer()
    kaboxer.go()


if __name__ == '__main__':
    main()