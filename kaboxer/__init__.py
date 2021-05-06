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
import urllib.parse
from http import HTTPStatus

import docker

import dockerpty

from packaging.version import parse as parse_version

import prompt_toolkit

import requests

import tabulate

import yaml


logger = logging.getLogger("kaboxer")


# Helpers for generated artifacts


def get_cli_helper_filename(app_id, component):
    if component:
        return f"{app_id}-{component}-kbx"
    else:
        return f"{app_id}-kbx"


def get_desktop_file_filename(app_id, component):
    return f"kaboxer-{app_id}-{component}.desktop"


def get_headless_desktop_file_filenames(app_id, component):
    start = f"kaboxer-{app_id}-{component}-start.desktop"
    stop = f"kaboxer-{app_id}-{component}-stop.desktop"
    return start, stop


def get_icon_name(app_id):
    return f"kaboxer-{app_id}"


# Main class


class Kaboxer:
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog="kaboxer")
        self.parser.add_argument(
            "-v", "--verbose", action="count", default=0, help="increase verbosity"
        )

        subparsers = self.parser.add_subparsers(
            title="subcommands", help="action to perform", dest="action", required=True
        )

        parser_run = subparsers.add_parser("run", help="run containerized app")
        parser_run.add_argument("app")
        parser_run.add_argument("--component", help="component to run")
        parser_run.add_argument(
            "--reuse-container", action="store_true", help="run in existing container"
        )
        parser_run.add_argument(
            "--detach", help="run in the background", action="store_true"
        )
        parser_run.add_argument(
            "--prompt-before-exit",
            action="store_true",
            help="wait user confirmation before exit",
        )
        parser_run.add_argument("--version", help="version to run")
        parser_run.add_argument("executable", nargs="*")
        parser_run.set_defaults(func=self.cmd_run)

        parser_stop = subparsers.add_parser(
            "stop", help="stop running containerized app"
        )
        parser_stop.add_argument("app")
        parser_stop.add_argument("--component", help="component to stop")
        parser_stop.add_argument(
            "--prompt-before-exit",
            action="store_true",
            help="wait user confirmation before exit",
        )
        parser_stop.set_defaults(func=self.cmd_stop)

        parser_get_meta_file = subparsers.add_parser(
            "get-meta-file", help="get installed meta-file of containerized app"
        )
        parser_get_meta_file.add_argument("app")
        parser_get_meta_file.add_argument("file")
        parser_get_meta_file.set_defaults(func=self.cmd_get_meta_file)

        parser_get_upstream_version = subparsers.add_parser(
            "get-upstream-version",
            help="get installed upstram version of containerized app",
        )
        parser_get_upstream_version.add_argument("app")
        parser_get_upstream_version.set_defaults(func=self.cmd_get_upstream_version)

        parser_prepare = subparsers.add_parser("prepare", help="prepare container(s)")
        parser_prepare.add_argument("app", nargs="+")
        parser_prepare.set_defaults(func=self.cmd_prepare)

        parser_upgrade = subparsers.add_parser("upgrade", help="upgrade container(s)")
        parser_upgrade.add_argument("app", nargs="+")
        parser_upgrade.set_defaults(func=self.cmd_upgrade)

        parser_list = subparsers.add_parser("list", help="list containers")
        parser_list.add_argument(
            "--installed", action="store_true", help="list installed containers"
        )
        parser_list.add_argument(
            "--available", action="store_true", help="list available containers"
        )
        parser_list.add_argument(
            "--upgradeable", action="store_true", help="list upgradeable containers"
        )
        parser_list.add_argument(
            "--all", action="store_true", help="list all versions of containers"
        )
        parser_list.add_argument(
            "--skip-headers", action="store_true", help="do not display column headers"
        )
        parser_list.set_defaults(func=self.cmd_list)

        parser_build = subparsers.add_parser("build", help="build image")
        parser_build.add_argument(
            "--skip-image-build",
            action="store_true",
            help="do not build the container image",
        )
        parser_build.add_argument(
            "--save", action="store_true", help="save container image after build"
        )
        parser_build.add_argument(
            "--push",
            action="store_true",
            help="push container image to registry after build",
        )
        parser_build.add_argument("--version", help="app version")
        parser_build.add_argument(
            "--ignore-version", action="store_true", help="ignore version checks"
        )
        parser_build.add_argument("app", nargs="?")
        parser_build.add_argument("path", nargs="?", default=os.getcwd())
        parser_build.set_defaults(func=self.cmd_build)

        parser_install = subparsers.add_parser("install", help="install image")
        parser_install.add_argument(
            "--tarball", action="store_true", help="install tarball"
        )
        parser_install.add_argument(
            "--destdir", help="build-time destination dir", default=""
        )
        parser_install.add_argument(
            "--prefix", help="prefix for the installation path", default="/usr/local"
        )
        parser_install.add_argument("app", nargs="?")
        parser_install.add_argument("path", nargs="?", default=os.getcwd())
        parser_install.set_defaults(func=self.cmd_install)

        parser_clean = subparsers.add_parser("clean", help="clean directory")
        parser_clean.add_argument("app", nargs="?")
        parser_clean.add_argument("path", nargs="?", default=os.getcwd())
        parser_clean.set_defaults(func=self.cmd_clean)

        parser_push = subparsers.add_parser("push", help="push image to registry")
        parser_push.add_argument("app")
        parser_push.add_argument("path", nargs="?", default=os.getcwd())
        parser_push.add_argument("--version", help="version to push")
        parser_push.set_defaults(func=self.cmd_push)

        parser_save = subparsers.add_parser("save", help="save image")
        parser_save.add_argument("app")
        parser_save.add_argument("file")
        parser_save.set_defaults(func=self.cmd_save)

        parser_load = subparsers.add_parser("load", help="load image")
        parser_load.add_argument("app")
        parser_load.add_argument("file")
        parser_load.set_defaults(func=self.cmd_load)

        parser_purge = subparsers.add_parser("purge", help="purge image")
        parser_purge.add_argument("app")
        parser_purge.add_argument(
            "--prune", action="store_true", help="prune unused images"
        )
        parser_purge.set_defaults(func=self.cmd_purge)

        self.config_paths = [
            ".",
            "/etc/kaboxer",
            "/usr/local/share/kaboxer",
            "/usr/share/kaboxer",
        ]

        self.backend = DockerBackend()
        self.registry = ContainerRegistry()

    def setup_logging(self):
        loglevels = {
            0: "ERROR",
            1: "INFO",
            2: "DEBUG",
        }
        ll = loglevels.get(self.args.verbose, "DEBUG")
        ll = getattr(logging, ll)
        logger.setLevel(ll)
        ch = logging.StreamHandler()
        logger.addHandler(ch)

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
        if hasattr(self, "_docker_conn"):
            return self._docker_conn

        self.setup_docker()
        if self.docker_is_working():
            return self._docker_conn
        else:
            groups = list(map(lambda g: grp.getgrgid(g)[0], os.getgroups()))
            if "docker" in groups:
                logger.error(
                    "No access to Docker even though you're a "
                    "member of the docker group, is "
                    "docker.service running?"
                )
            else:
                logger.error(
                    "No access to Docker, are you a member "
                    "of group docker or kaboxer?"
                )
            sys.exit(1)

    def show_exception_in_debug_mode(self):
        if self.args.verbose >= 2:
            logger.exception("The following exception was caught")

    def go(self):
        self.args = self.parser.parse_args()
        self.setup_logging()
        self.setup_docker()
        if not self.docker_is_working():
            groups = list(map(lambda g: grp.getgrgid(g)[0], os.getgroups()))
            if "kaboxer" in groups and "docker" not in groups:
                # Try to elevate the privileges to docker group if we can
                nc = ["sudo", "-g", "docker"] + sys.argv
                sys.stdout.flush()
                sys.stderr.flush()
                os.execv("/usr/bin/sudo", nc)
            # Force a new test on first real access if any
            delattr(self, "_docker_conn")

        self.args.func()

    def run_hook_script(self, event, stop_on_failure=False):
        key = event + "_script"

        if key not in self.component_config:
            return
        script_content = self.component_config[key]
        if len(script_content) == 0:
            return

        if script_content.startswith("#!"):
            tmp_script = tempfile.NamedTemporaryFile(
                delete=False, prefix="kaboxer-hook-script"
            )
            tmp_script.write(script_content.encode("utf8"))
            tmp_script.close()
            os.chmod(
                tmp_script.name,
                stat.S_IRWXU
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH,
            )
            result = subprocess.run([tmp_script.name])
            os.unlink(tmp_script.name)
        else:
            result = subprocess.run([script_content], shell=True)

        if result.returncode != 0:
            message = "%s hook script failed with returncode %d" % (
                event,
                result.returncode,
            )
            if stop_on_failure:
                logger.error(message)
                sys.exit(1)
            else:
                logger.warning(message)

    def cmd_run(self):
        app = self.args.app
        if self.args.version:
            self.prepare_or_upgrade(["%s=%s" % (app, self.args.version)])
            tag_name = self.args.version
        else:
            self.prepare_or_upgrade([app])
            current_apps, _, _, _ = self.list_apps()
            tag_name = current_apps[app]["version"]
        self.read_config(app)
        image_name = self.backend.get_local_image_name(self.config)
        image = "%s:%s" % (image_name, tag_name)

        logger.debug("Running image %s", image)

        self.run_hook_script("before_run", stop_on_failure=True)

        if self.args.reuse_container:
            containers = self.docker_conn.containers.list(filters={"name": app})
            container = containers[0]

        run_mode = self.component_config["run_mode"]
        if self.args.detach and run_mode != "headless":
            logger.error("Can't detach a non-headless component")
            sys.exit(1)

        opts = self.component_config.get("docker_options", {})
        opts = self.parse_component_config(opts)
        extranets = []
        try:
            netname = self.component_config["networks"][0]
            self.create_network(netname)
            opts["network"] = netname
            extranets = self.component_config["networks"][1:]
        except KeyError:
            pass

        if not self.component_config["run_as_root"] and not self.args.reuse_container:
            opts2 = opts.copy()
            opts2["detach"] = False
            opts2["tty"] = True
            precmds = [
                ["addgroup", "--debug", "--gid", str(self.gid), self.gname],
                [
                    "adduser",
                    "--debug",
                    "--uid",
                    str(self.uid),
                    "--gid",
                    str(self.gid),
                    "--home",
                    self.home_in,
                    "--gecos",
                    self.gecos,
                    "--disabled-password",
                    self.uname,
                ],
            ]
            container = self.docker_conn.containers.create(image, **opts2)
            opts["entrypoint"] = container.attrs["Config"]["Entrypoint"]
            container.remove()
            try:
                del opts2["command"]
            except KeyError:
                pass
            for precmd in precmds:
                opts2["entrypoint"] = precmd
                container = self.docker_conn.containers.create(image, **opts2)
                container.start()
                container.wait()
                image = container.commit()
                container.remove()
            opts["user"] = self.uid
            opts["environment"]["HOME"] = self.home_in

        if run_mode == "cli":
            opts["tty"] = True
            opts["stdin_open"] = True
        elif run_mode == "gui":
            self.create_xauth()
            opts["environment"]["DISPLAY"] = os.getenv("DISPLAY")
            opts["environment"]["XAUTHORITY"] = self.xauth_in
            opts["mounts"].append(
                docker.types.Mount(self.xauth_in, self.xauth_out, type="bind")
            )
        elif run_mode == "headless":
            opts["name"] = self.args.app
        else:
            logger.error("Unknown run mode")
            sys.exit(1)
        if run_mode == "gui" or (
            "allow_x11" in self.component_config and self.component_config["allow_x11"]
        ):
            xsock = "/tmp/.X11-unix"
            opts["mounts"].append(docker.types.Mount(xsock, xsock, type="bind"))

        executable = self.args.executable
        if not len(executable) and "executable" in self.component_config:
            executable = self.component_config["executable"]
        if not isinstance(executable, list):
            executable = shlex.split(executable)
        try:
            executable.extend(shlex.split(self.component_config["extra_opts"]))
        except KeyError:
            pass
        try:
            opts["entrypoint"] = ""
        except KeyError:
            pass

        if self.args.reuse_container:
            if run_mode == "gui":
                self.create_xauth()
                bio = io.BytesIO()
                tf = tarfile.open(mode="w:", fileobj=bio)
                ti = tarfile.TarInfo()
                ti.name = self.xauth_in

                def tifilter(x):
                    if not self.component_config["run_as_root"]:
                        x.uid = self.uid
                        x.gid = self.gid
                        x.uname = self.uname
                        x.gname = self.gname
                    return x

                tf.add(self.xauth_out, arcname=self.xauth_in, filter=tifilter)
                tf.close()
                container.put_archive("/", bio.getvalue())
            ex_with_env = ["env"]
            for e in opts["environment"]:
                ex_with_env.append("%s=%s" % (e, shlex.quote(opts["environment"][e])))
            ex_with_env.extend(executable)
            executable = ex_with_env
            dockerpty.exec_command(self.docker_conn.api, container.id, executable)
        else:
            opts["auto_remove"] = True
            if self.args.detach:
                opts["detach"] = True
                container = self.docker_conn.containers.run(image, executable, **opts)
            else:
                container = self.docker_conn.containers.create(
                    image, executable, **opts
                )
            for e in extranets:
                self.create_network(e).connect(container)

            if not self.args.detach:
                dockerpty.start(self.docker_conn.api, container.id)

        self.run_hook_script("after_run")

        if self.args.detach:
            component_name = self.component_config["name"]
            start_message = self.component_config.get(
                "start_message", "%s started" % (component_name,)
            )
            print(start_message)
        if self.args.prompt_before_exit:
            prompt_toolkit.prompt("Press ENTER to exit")

    def cmd_stop(self):
        app = self.args.app
        self.read_config(app)
        run_mode = self.component_config["run_mode"]
        if run_mode == "headless":
            containers = self.docker_conn.containers.list(filters={"name": app})
            if not containers:
                logger.error("%s is not running", app)
                sys.exit(1)
            container = containers[0]
            self.run_hook_script("before_stop")
            container.stop()
            self.run_hook_script("after_stop")
            component_name = self.component_config["name"]
            stop_message = self.component_config.get(
                "stop_message", "%s stopped" % (component_name,)
            )
            print(stop_message)
            if self.args.prompt_before_exit:
                prompt_toolkit.prompt("Press ENTER to exit")
        else:
            logger.error("Can't stop a non-headless component")
            sys.exit(1)

    def get_meta_file(self, image, filename):
        with tempfile.NamedTemporaryFile(mode="w+t", prefix="getmetafile") as tmp:
            self.extract_file_from_image(
                image, os.path.join("/kaboxer/", filename), tmp.name
            )
            v = str(open(tmp.name).read())
            return v

    def cmd_get_meta_file(self):
        self.read_config(self.args.app)
        image = "kaboxer/" + self.args.app
        print(self.get_meta_file(image, self.args.file))

    def cmd_get_upstream_version(self):
        self.read_config(self.args.app)
        image = "kaboxer/" + self.args.app
        print(self.get_meta_file(image, "version"))

    def find_configs_in_dir(self, path, restrict=None, allow_duplicate=True):
        """Find Kaboxer app config files in a given directory

        'restrict' is a list of app ids that are allowed. If None, every app id
        is allowed (no restriction). 'allow_duplicate' decides what happens when
        more than one config files are found with the same app id: if set to
        False, only keep the first one.

        Returns a list of KaboxerAppConfig objects.
        """
        globs = ["kaboxer.yaml", "*.kaboxer.yaml"]
        yamlfiles = []
        configs = []
        for g in globs:
            for f in glob.glob(os.path.join(path, g)):
                if not os.path.isfile(f):
                    continue
                yamlfiles.append(f)
        for f in yamlfiles:
            try:
                y = KaboxerAppConfig(filename=f)
            except yaml.YAMLError:
                logger.warning("Failed to parse %s as YAML", f, exc_info=1)
                continue
            app = y.app_id
            if app is None:
                logger.info("Ignoring %s (no app id)", f)
                continue
            if restrict is not None and app not in restrict:
                continue
            if allow_duplicate is False:
                if any(c.app_id == app for c in configs):
                    logger.info("Ignoring %s (duplicate app id)", f)
                    continue
            configs.append(y)
        return configs

    def find_configs_for_build_cmds(self):
        path = self.args.path
        restrict = [self.args.app] if self.args.app else None
        configs = self.find_configs_in_dir(
            path, restrict=restrict, allow_duplicate=False
        )
        if not configs:
            logger.error("Failed to find appropriate kaboxer.yaml file")
            sys.exit(1)
        return configs

    def find_config_for_app_in_dir(self, path, app):
        filenames = [app + ".kaboxer.yaml", "kaboxer.yaml"]
        for filename in filenames:
            config_file = os.path.join(path, filename)
            if not os.path.isfile(config_file):
                continue
            try:
                y = KaboxerAppConfig(filename=config_file)
            except yaml.YAMLError:
                logger.warning("Failed to parse %s as YAML", config_file, exc_info=1)
                continue
            if y.app_id == app:
                return y
        return None

    def do_version_checks(self, v, config):
        parsed_v = parse_version(v)
        try:
            minv = str(config["packaging"]["min_upstream_version"])
            parsed_minv = parse_version(minv)
            if parsed_v < parsed_minv:
                raise Exception("Unsupported upstream version %s < %s" % (v, minv))
        except KeyError:
            pass
        try:
            maxv = str(config["packaging"]["max_upstream_version"])
            parsed_maxv = parse_version(maxv)
            if parsed_v > parsed_maxv:
                raise Exception("Unsupported upstream version %s > %s" % (v, maxv))
        except KeyError:
            pass

    def cmd_build(self):
        parsed_configs = self.find_configs_for_build_cmds()
        for config in parsed_configs:
            if not self.args.skip_image_build:
                image, saved_version = self.build_image(config)
                if self.args.save:
                    tarball = os.path.join(self.args.path, config.app_id + ".tar")
                    self.save_image_to_file(image, tarball)
                if self.args.push:
                    self.push_image(config, [saved_version])
            self.build_cli_helpers(config)
            self.build_desktop_files(config)

    def build_image(self, parsed_config):
        path = self.args.path
        app = parsed_config.app_id
        logger.info("Building container image for %s", app)
        try:
            df = os.path.join(path, parsed_config["build"]["docker"]["file"])
        except KeyError:
            df = os.path.join(path, "Dockerfile")
        try:
            buildargs = parsed_config["build"]["docker"]["parameters"]
        except KeyError:
            buildargs = {}
        if self.args.version:
            if not self.args.ignore_version:
                try:
                    self.do_version_checks(self.args.version, parsed_config)
                except Exception as e:
                    message = str(e)
                    logger.error(message)
                    sys.exit(1)
            buildargs["KBX_APP_VERSION"] = self.args.version
        (image, _) = self.docker_conn.images.build(
            path=path,
            dockerfile=df,
            rm=True,
            forcerm=True,
            nocache=True,
            pull=True,
            quiet=False,
            buildargs=buildargs,
        )
        with tempfile.NamedTemporaryFile(mode="w+t") as tmp:
            try:
                self.extract_file_from_image(image, "/kaboxer/version", tmp.name)
                saved_version = open(tmp.name).readline().strip()
                if not self.args.ignore_version:
                    try:
                        self.do_version_checks(saved_version, parsed_config)
                    except Exception as e:
                        message = str(e)
                        self.docker_conn.images.remove(image=image.id)
                        logger.error(message)
                        sys.exit(1)
            except Exception:
                if self.args.version:
                    saved_version = self.args.version
                    tmp.write(self.args.version)
                else:
                    logger.error("Unable to determine version (use --version?)")
                    self.docker_conn.images.remove(image=image.id)
                    sys.exit(1)
            tmp.flush()
            image = self.inject_file_into_image(image, tmp.name, "/kaboxer/version")
        with tempfile.NamedTemporaryFile(mode="w+t") as tmp:
            tmp.write(str(parsed_config["packaging"]["revision"]) + "\n")
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, "/kaboxer/packaging-revision"
            )
        with tempfile.NamedTemporaryFile(mode="w+t") as tmp:
            tmp.write(yaml.dump(sys.argv))
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, "/kaboxer/kaboxer-build-cmd"
            )
        image = self.inject_file_into_image(image, df, "/kaboxer/Dockerfile")
        with tempfile.NamedTemporaryFile(mode="w+t") as tmp:
            savedbuildargs = {
                "rm": True,
                "forcerm": True,
                "path": path,
                "dockerfile": df,
                "buildargs": buildargs,
            }
            tmp.write(yaml.dump(savedbuildargs))
            tmp.flush()
            image = self.inject_file_into_image(
                image, tmp.name, "/kaboxer/docker-build-parameters"
            )
        tagname = "kaboxer/%s:%s" % (app, str(saved_version))
        image.tag(tagname)
        tagname = "kaboxer/%s:latest" % (app,)
        if not self.find_image(tagname):
            image.tag(tagname)
        return image, saved_version

    def build_cli_helpers(self, parsed_config):
        app = parsed_config.app_id
        if "cli-helpers" not in parsed_config.get("install", {}):
            logger.info("Building cli helpers for %s", app)
            self.gen_cli_helpers(parsed_config)

    def build_desktop_files(self, parsed_config):
        app = parsed_config.app_id
        if "desktop-files" not in parsed_config.get("install", {}):
            logger.info("Building desktop files for %s", app)
            self.gen_desktop_files(parsed_config)

    def extract_version_from_image(self, image):
        with tempfile.NamedTemporaryFile(mode="w+t") as tmp:
            self.extract_file_from_image(image.id, "/kaboxer/version", tmp.name)
            saved_version = open(tmp.name).readline().strip()
        return parse_version(saved_version)

    def cmd_push(self):
        parsed_configs = self.find_configs_for_build_cmds()
        for config in parsed_configs:
            self.push_image(config)

    def push_image(self, parsed_config, versions=[]):
        app = parsed_config.app_id
        logger.info("Pushing %s", app)

        # Get the image names
        localname = self.backend.get_local_image_name(parsed_config)
        remotename = self.backend.get_remote_image_name(parsed_config)
        if not remotename:
            logger.error("No remote image name for %s", app)
            sys.exit(1)

        # Always fetch the latest tag to be able to compare and update
        # it if required
        self.docker_pull("%s:latest" % remotename)

        # Figure out which versions to push
        if len(versions) == 0:
            if self.args.version:
                try:
                    self.do_version_checks(self.args.version, parsed_config)
                    versions = [self.args.version]
                except Exception as e:
                    message = str(e)
                    logger.error(message)
                    sys.exit(1)
            else:
                for image in self.docker_conn.images.list():
                    for tag in image.tags:
                        (i, ver) = tag.rsplit(":", 1)
                        if i != localname:
                            continue
                        if ver == "current" or ver == "latest":
                            continue
                        versions.append(ver)

        # Push each version
        for version in versions:
            local_tagname = "%s:%s" % (localname, version)
            local_image = self.find_image(local_tagname)
            if not local_image:
                logger.error("No %s image found", local_tagname)
                sys.exit(1)
            saved_version = self.extract_version_from_image(local_image)
            remote_tagname = "%s:%s" % (remotename, saved_version)
            local_image.tag(remote_tagname)
            self.docker_conn.images.push(remote_tagname)

        # Update remote latest tag if needed
        local_tagname = "%s:latest" % localname
        local_image = self.find_image(local_tagname)
        remote_tagname = "%s:latest" % remotename
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

    def make_run_command(self, app_id, component, args):
        return f"kaboxer run {args} --component {component} {app_id}"

    def make_run_command_headless(self, app_id, component, args):
        return f"kaboxer run --detach --prompt-before-exit {args} --component {component} {app_id}"  # noqa: E501

    def make_stop_command(self, app_id, component):
        return f"kaboxer stop --prompt-before-exit --component {component} {app_id}"

    def make_run_helper(self, app_id, component, args):
        cmd = self.make_run_command(app_id, component, args)
        return f"#!/bin/sh\nexec {cmd}"

    def make_run_stop_helper(self, app_id, component, args):
        run_cmd = self.make_run_command_headless(app_id, component, args)
        stop_cmd = self.make_stop_command(app_id, component)
        return f"""#!/bin/sh
case "$1" in
  (run)  exec {run_cmd} ;;
  (stop) exec {stop_cmd} ;;
  (*)    echo >&2 "Usage: $(basename $0) run|stop"; exit 1 ;;
esac
"""

    def gen_cli_helpers(self, parsed_config):
        app_id = parsed_config.app_id
        components = parsed_config["components"]
        n_components = len(components)
        for component, data in components.items():
            run_args = ""
            if data.get("reuse_container", False):
                run_args = "--reuse-container"
            if data["run_mode"] == "headless":
                content = self.make_run_stop_helper(app_id, component, run_args)
            else:
                content = self.make_run_helper(app_id, component, run_args)
            if n_components == 1:
                outfile = get_cli_helper_filename(app_id, None)
            else:
                outfile = get_cli_helper_filename(app_id, component)
            with open(outfile, "w") as f:
                f.write(content)
            os.chmod(outfile, 0o755)

    def make_desktop_file(self, app_id, name, comment, cmd, terminal, categories):
        return f"""[Desktop Entry]
Name={name}
Comment={comment}
Exec={cmd}
Icon=kaboxer-{app_id}
Terminal={terminal}
Type=Application
Categories={categories}
"""

    def gen_desktop_files(self, parsed_config):
        app_id = parsed_config.app_id

        application = parsed_config["application"]
        categories = application.get("categories", "Uncategorized")
        comment = application.get("description", "").split("\n")[0]
        fallback_name = application["name"]

        components = parsed_config["components"]
        for component, component_data in components.items():
            component_name = component_data.get("name", fallback_name)

            run_args = ""
            if component_data.get("reuse_container", False):
                run_args = "--reuse-container"

            if component_data["run_mode"] == "headless":
                terminal = "true"
                # One .desktop file for starting
                name = f"Start {component_name}"
                cmd = self.make_run_command_headless(app_id, component, run_args)
                content_start = self.make_desktop_file(
                    app_id, name, comment, cmd, terminal, categories
                )
                # One .desktop file for stopping
                name = f"Stop {component_name}"
                cmd = self.make_stop_command(app_id, component)
                content_stop = self.make_desktop_file(
                    app_id, name, comment, cmd, terminal, categories
                )
                # Write them down
                outfile_start, outfile_stop = get_headless_desktop_file_filenames(
                    app_id, component
                )
                with open(outfile_start, "w") as f:
                    f.write(content_start)
                with open(outfile_stop, "w") as f:
                    f.write(content_stop)
            else:
                if component_data["run_mode"] == "cli":
                    terminal = "true"
                else:
                    terminal = "false"
                name = component_name
                cmd = self.make_run_command(app_id, component, run_args)
                content = self.make_desktop_file(
                    app_id, name, comment, cmd, terminal, categories
                )
                outfile = get_desktop_file_filename(app_id, component)
                with open(outfile, "w") as f:
                    f.write(content)

    def cmd_clean(self):
        parsed_configs = self.find_configs_for_build_cmds()
        for config in parsed_configs:
            self.clean_app(config)

    def clean_app(self, parsed_config):
        app = parsed_config.app_id
        path = os.path.realpath(self.args.path)
        logger.info("Cleaning %s", app)
        # Clean tarball
        tarball = os.path.join(path, app + ".tar")
        if os.path.commonpath([path, tarball]) == path and os.path.isfile(tarball):
            os.unlink(tarball)
        # Clean generated cli helpers
        cli_helpers = self._list_cli_helpers(parsed_config, generated_only=True)
        for f in cli_helpers:
            if os.path.isfile(f):
                os.unlink(f)
        # Clean generated desktop files
        desktop_files = self._list_desktop_files(parsed_config, generated_only=True)
        for f in desktop_files:
            if os.path.isfile(f):
                os.unlink(f)

    def install_to_path(self, f, path):
        if self.args.destdir == "":
            builddestpath = path
        else:
            builddestpath = os.path.join(self.args.destdir, os.path.relpath(path, "/"))
        logger.info("Installing %s to %s", f, builddestpath)
        os.makedirs(builddestpath, exist_ok=True)
        shutil.copy(f, builddestpath)

    def _list_cli_helpers(self, parsed_config, generated_only=False):
        # Return user-provided files if present
        if "cli-helpers" in parsed_config.get("install", {}):
            if generated_only:
                return []
            else:
                return parsed_config["install"]["cli-helpers"]

        # Return auto-generated files otherwise
        files = []
        app_id = parsed_config.app_id
        components = parsed_config["components"]
        if len(components) == 1:
            fn = get_cli_helper_filename(app_id, None)
            files.append(fn)
        else:
            for component in components:
                fn = get_cli_helper_filename(app_id, component)
                files.append(fn)
        return files

    def _list_desktop_files(self, parsed_config, generated_only=False):
        # Return user-provided files if present
        if "desktop-files" in parsed_config.get("install", {}):
            if generated_only:
                return []
            else:
                return parsed_config["install"]["desktop-files"]

        # Return auto-generated files otherwise
        files = []
        app_id = parsed_config.app_id
        for component, data in parsed_config["components"].items():
            if data["run_mode"] == "headless":
                fn1, fn2 = get_headless_desktop_file_filenames(app_id, component)
                files.append(fn1)
                files.append(fn2)
            else:
                fn = get_desktop_file_filename(app_id, component)
                files.append(fn)
        return files

    def cmd_install(self):
        parsed_configs = self.find_configs_for_build_cmds()
        for config in parsed_configs:
            self.install_app(config)

    def install_app(self, parsed_config):
        main_destpath = os.path.join(self.args.prefix, "share", "kaboxer")
        path = self.args.path
        app = parsed_config.app_id
        logger.info("Installing %s", app)
        # Install image tarball
        if self.args.tarball:
            tarball = os.path.join(path, app + ".tar")
            try:
                self.install_to_path(tarball, main_destpath)
            except shutil.SameFileError:
                pass
        # Install kaboxer.yaml file
        # Update it first if we ship the tarball
        with tempfile.TemporaryDirectory() as td:
            # Duplicate object
            filtered_config_file = KaboxerAppConfig(filename=parsed_config.filename)
            tf = os.path.join(td, app + ".kaboxer.yaml")
            if self.args.tarball:
                # Rewrite the YAML file with the tarball data
                origin_data = {
                    "tarball": os.path.join(main_destpath, app + ".tar"),
                }
                if "container" not in filtered_config_file:
                    filtered_config_file["container"] = {}
                filtered_config_file["container"]["origin"] = origin_data
                filtered_config_file.save(tf)
            else:
                # Copy over the unmodified file
                shutil.copy(parsed_config.filename, tf)

            self.install_to_path(tf, main_destpath)
        # Install cli helper(s)
        cli_helpers = self._list_cli_helpers(parsed_config)
        for c in cli_helpers:
            self.install_to_path(
                os.path.join(path, c),
                os.path.join(self.args.prefix, "bin"),
            )
        # Install desktop file(s)
        desktop_files = self._list_desktop_files(parsed_config)
        for d in desktop_files:
            self.install_to_path(
                os.path.join(path, d),
                os.path.join(self.args.prefix, "share", "applications"),
            )
        # Install icon file(s)
        icon_install_name = get_icon_name(parsed_config.app_id)
        try:
            icon_file = parsed_config["install"]["icon"]
            (_, ife) = os.path.splitext(os.path.basename(icon_file))
            with tempfile.TemporaryDirectory() as td:
                renamed_icon = os.path.join(td, "%s%s" % (icon_install_name, ife))
                shutil.copy(icon_file, renamed_icon)
                self.install_to_path(
                    renamed_icon, os.path.join(self.args.prefix, "share", "icons")
                )
        except KeyError:
            pass
        try:
            icon_file = parsed_config["install"]["extract-icon"]
            (_, ife) = os.path.splitext(os.path.basename(icon_file))
            with tempfile.TemporaryDirectory() as td:
                renamed_icon = os.path.join(td, "%s%s" % (icon_install_name, ife))
                self.extract_file_from_image(
                    "kaboxer/" + parsed_config.app_id, icon_file, renamed_icon
                )
                self.install_to_path(
                    renamed_icon, os.path.join(self.args.prefix, "share", "icons")
                )
        except KeyError:
            pass

    def extract_file_from_image(self, image, infile, outfile):
        temp_container = None
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
            if temp_container:
                temp_container.remove()

    def extract_file_from_tarball(self, tarball, infile, outfile):
        tf = tarfile.open(tarball)
        manifest = tf.extractfile("manifest.json")
        j = json.loads(manifest.read())
        relpath = os.path.relpath(infile, "/")
        for layer in j[0]["Layers"]:
            tfl = tarfile.open(fileobj=tf.extractfile(layer))
            try:
                with tempfile.TemporaryDirectory() as td:
                    tfl.extract(relpath, path=td)
                    shutil.move(os.path.join(td, relpath), outfile)
                    return 1
            except KeyError:
                continue
        raise Exception("Not found")

    def get_meta_file_from_tarball(self, tarball, filename):
        with tempfile.NamedTemporaryFile(mode="w+t", prefix="getmetafile") as tmp:
            self.extract_file_from_tarball(
                tarball, os.path.join("/kaboxer/", filename), tmp.name
            )
            v = str(open(tmp.name).read())
            return v

    def inject_file_into_image(self, image, outfile, infile):
        temp_container = self.docker_conn.containers.create(image)
        with tempfile.TemporaryFile() as temptar:
            tf = tarfile.open(fileobj=temptar, mode="w")
            (dirname, filename) = os.path.split(infile)
            p = pathlib.Path(dirname)
            for parent in reversed(p.parents):
                ti = tarfile.TarInfo(name=str(parent))
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            ti = tarfile.TarInfo(name=infile)
            ti.size = os.stat(outfile).st_size
            tf.addfile(ti, fileobj=open(outfile, mode="rb"))
            tf.close()
            temptar.seek(0)
            buf = b""
            while True:
                b = temptar.read()
                if not b:
                    break
                buf += b
            temp_container.put_archive("/", buf)
        image = temp_container.commit()
        temp_container.remove()
        return image

    def cmd_save(self):
        images = self.docker_conn.images.list()
        for image in images:
            for tag in image.tags:
                if tag == "kaboxer/" + self.args.app + ":latest":
                    self.save_image_to_file(image, self.args.file)
                    return
        logger.error("No image found")
        sys.exit(1)

    def save_image_to_file(self, image, destfile):
        with open(destfile, "wb") as f:
            for chunk in image.save():
                f.write(chunk)

    def load_image(self, tarfile, appname, tag):
        f = open(tarfile, "rb")
        for image in self.docker_conn.images.load(f):
            image.tag("kaboxer/" + appname, tag=tag)
        return image

    def cmd_load(self):
        v = self.get_meta_file_from_tarball(self.args.file, "version").strip()
        logger.info("Loading %s at version %s", self.args.app, v)
        self.load_image(self.args.file, self.args.app, v)

    def find_image(self, name):
        images = self.docker_conn.images.list()
        candidates = {}
        for image in images:
            for tag in image.tags:
                if tag == name:
                    return image
                if tag[: len(name)] == name and tag[len(name)] == ":":
                    ver = tag[len(name) + 1 :]
                    candidates[tag] = {"image": image, "version": parse_version(ver)}
        if len(candidates):
            versions = [candidates[x]["version"] for x in candidates.keys()]
            maxver = sorted(versions)[-1]
            for c in candidates:
                if candidates[c]["version"] == maxver:
                    return candidates[c]["image"]
        return None

    def cmd_prepare(self):
        self.prepare_or_upgrade(self.args.app)

    def cmd_upgrade(self):
        self.prepare_or_upgrade(self.args.app, upgrade=True)

    def do_upgrade_scripts(self, app, oldver, newver):
        self.read_config(app)
        if oldver is None or oldver == newver:
            return
        logger.info("Running upgrade scripts for %s (%s -> %s)", app, oldver, newver)
        image_name = self.backend.get_local_image_name(self.config)
        with tempfile.TemporaryDirectory() as td:
            s = td
            t = "/kaboxer/upgrade-data"
            opts = {"mounts": [docker.types.Mount(t, s, type="bind")]}
            opts = self.parse_component_config(opts)
            full_image_name = "%s:%s" % (image_name, oldver)
            self.backend.run_command(
                self.docker_conn,
                full_image_name,
                ["/kaboxer/scripts/pre-upgrade"],
                opts,
                allow_missing=True,
            )
            full_image_name = "%s:%s" % (image_name, newver)
            self.backend.run_command(
                self.docker_conn,
                full_image_name,
                ["/kaboxer/scripts/post-upgrade", oldver],
                opts,
                allow_missing=True,
            )

    def docker_pull(self, full_image_name, stop_on_error=False):
        logger.info("Pulling %s image from registry", full_image_name)
        try:
            image = self.docker_conn.images.pull(full_image_name)
            return image
        except docker.errors.APIError:
            logger.exception("Could not pull %s, wrong URL?", full_image_name)
            if stop_on_error:
                sys.exit(1)

    def prepare_or_upgrade(self, apps, upgrade=False):
        current_apps, registry_apps, tarball_apps, available_apps = self.list_apps(
            get_remotes=True, restrict=apps
        )
        for app in apps:
            logger.info("Preparing %s", app)
            previous_version = None
            m = re.search("([^=]+)=([^=]+)$", app)
            if m:
                app = m.group(1)
                target_version = m.group(2)
                if app in current_apps:
                    previous_version = current_apps[app]["version"]
                    if (
                        parse_version(target_version) != parse_version(previous_version)
                        and not upgrade
                    ):
                        logger.exception(
                            "%s is at version %s, can't run %s=%s",
                            app,
                            previous_version,
                            app,
                            target_version,
                        )
                        sys.exit(1)
            else:
                maxavail = ""
                try:
                    maxavail = available_apps[app]["maxversion"]["version"]
                except KeyError:
                    logger.debug("No version in local repository")
                try:
                    tarball_ver = parse_version(tarball_apps[app]["version"])
                    if maxavail == "" or tarball_ver > parse_version(maxavail):
                        maxavail = tarball_apps[app]["version"]
                except KeyError:
                    logger.debug("No version found in tarball")
                try:
                    registry_ver = parse_version(registry_apps[app]["maxversion"])
                    if maxavail == "" or registry_ver > parse_version(maxavail):
                        maxavail = registry_apps[app]["maxversion"]
                except KeyError:
                    logger.debug("No version found in remote registry")

                if app in current_apps:
                    previous_version = current_apps[app]["version"]
                    target_version = previous_version
                else:
                    target_version = maxavail
                if upgrade:
                    target_version = maxavail
                self.read_config(app)

            if (
                previous_version
                and upgrade
                and parse_version(target_version) <= parse_version(previous_version)
            ):
                target_version = previous_version

            if not target_version:
                # We could not find any version info, let's use the latest tag
                logger.debug("No target version identified, use latest")
                target_version = "latest"

            config = self.load_config(app)
            # XXX: come back here after list_apps
            local_image_name = self.backend.get_local_image_name(config)
            remote_image_name = self.backend.get_remote_image_name(config)
            full_local_image_name = "%s:%s" % (local_image_name, target_version)
            full_remote_image_name = "%s:%s" % (remote_image_name, target_version)
            current_image_name = "%s:%s" % (local_image_name, "current")
            if previous_version == target_version:
                logger.debug(
                    "Stopping because previous==target (%s==%s)",
                    previous_version,
                    target_version,
                )
                return

            if "maxversion" in available_apps.get(app, {}):
                max_avail_version = parse_version(
                    available_apps[app]["maxversion"]["version"]
                )
                logger.debug(
                    "Trying to find %s image for version %s", app, max_avail_version
                )
                if max_avail_version == parse_version(target_version):
                    image = self.find_image(full_local_image_name)
                    if not image and remote_image_name:
                        image = self.find_image(full_remote_image_name)
                    if image:
                        image.tag(current_image_name)
                    else:
                        logger.error(
                            "Could not find %s image for version %s",
                            app,
                            max_avail_version,
                        )
                    self.do_upgrade_scripts(app, previous_version, target_version)
                    return

            if config.get("container:origin:registry"):
                logger.debug("Trying to find image in registry")
                found_image = self.find_image(full_remote_image_name)
                if found_image:
                    logger.debug("Found in local registry")
                    found_image.tag(current_image_name)
                else:
                    image = self.docker_pull(full_remote_image_name, stop_on_error=True)
                    pulled_version = self.get_meta_file(image, "version").strip()
                    if target_version == "latest":
                        versioned_image_name = "%s:%s" % (
                            remote_image_name,
                            pulled_version,
                        )
                        if not self.find_image(versioned_image_name):
                            image.tag(versioned_image_name)
                    # Make remote image available in the local namespace
                    versioned_image_name = "%s:%s" % (local_image_name, pulled_version)
                    if not self.find_image(versioned_image_name):
                        image.tag(versioned_image_name)
                    image.tag(current_image_name)
                    self.do_upgrade_scripts(app, previous_version, target_version)
                return

            tarball = config.get("container:origin:tarball")
            if tarball:
                paths = [
                    ".",
                    "/usr/local/share/kaboxer",
                    "/usr/share/kaboxer",
                ]
                for p in paths:
                    tarfile = os.path.join(p, tarball)
                    if os.path.isfile(tarfile):
                        logger.info("Loading image from %s", tarfile)
                        image = self.load_image(tarfile, app, target_version)
                        image.tag(current_image_name)
                    self.do_upgrade_scripts(app, previous_version, target_version)
                    return

            if not self.find_image(full_local_image_name):
                paths = [
                    ".",
                    "/usr/local/share/kaboxer",
                    "/usr/share/kaboxer",
                ]
                for p in paths:
                    tarfile = os.path.join(p, self.config.app_id + ".tar")
                    if os.path.isfile(tarfile):
                        logger.info("Loading image from %s", tarfile)
                        self.load_image(tarfile, app, target_version)
                        self.do_upgrade_scripts(app, previous_version, target_version)
                        return

            logger.error("Cannot prepare image")
            sys.exit(1)

    def cmd_purge(self):
        """Purge (uninstall) an application

        XXX I believe we should clear all tags that are found, regardless
            of 'maxversion'
        XXX What about images that have the registry in their name, eg.
            registry.gitlab.com/kalilinux/packages/APP-kbx/kaboxer/APP?
        """

        app = self.args.app
        n_removed_images = 0

        current_apps, _, _, available_apps = self.list_apps()

        if app in current_apps:
            imgname = f"kaboxer/{app}:current"
            if self.backend.remove_image(self.docker_conn, imgname):
                n_removed_images += 1

        if app in available_apps:
            version = available_apps[app]["maxversion"]["version"]
            imgname = f"kaboxer/{app}:{version}"
            if self.backend.remove_image(self.docker_conn, imgname):
                n_removed_images += 1

            imgname = f"kaboxer/{app}"
            if self.backend.remove_image(self.docker_conn, imgname):
                n_removed_images += 1

        if n_removed_images > 0 and self.args.prune:
            self.docker_conn.images.prune(filters={"dangling": True})

    def list_apps(self, get_remotes=False, restrict=None):
        current_apps = {}
        registry_apps = {}
        tarball_apps = {}
        available_apps = {}

        if restrict is not None:
            restrict = [re.sub("=.*", "", i) for i in restrict]

        logger.debug("Finding kaboxer applications")
        for p in self.config_paths:
            parsed_configs = self.find_configs_in_dir(
                p, restrict=restrict, allow_duplicate=True
            )
            for app_config in parsed_configs:
                aid = app_config.app_id
                logger.debug("Analyzing %s", aid)
                try:
                    imagenames = (
                        self.backend.get_local_image_name(app_config),
                        self.backend.get_remote_image_name(app_config),
                    )
                    logger.debug("Looking for local docker image in %s", imagenames)
                    # XXX: factorize logic to find the right image
                    for image in self.docker_conn.images.list():
                        for tag in image.tags:
                            (imagename, ver) = tag.rsplit(":", 1)
                            if imagename not in imagenames:
                                continue
                            curver = self.get_meta_file(image, "version").strip()
                            item = {
                                "version": curver,
                                "packaging-revision-from-image": self.get_meta_file(
                                    image, "packaging-revision"
                                ).strip(),
                                "packaging-revision-from-yaml": app_config.get(
                                    "packaging:revision"
                                ),
                                "image": imagename,
                            }
                            if ver == "current":
                                current_apps[aid] = item
                            if aid not in available_apps:
                                available_apps[aid] = {}
                            available_apps[aid][ver] = item
                            _maxversion = available_apps[aid].get("maxversion")
                            if _maxversion:
                                max_avail_version = parse_version(
                                    _maxversion["version"]
                                )
                            if not _maxversion or max_avail_version <= parse_version(
                                curver
                            ):
                                available_apps[aid]["maxversion"] = item
                except Exception as e:
                    print(e)
                    pass

                registry_data = app_config.get("container:origin:registry")
                if registry_data and "url" in registry_data:
                    registry_apps[aid] = {
                        "url": registry_data["url"],
                        "image": registry_data.get("image", aid),
                        "packaging-revision-from-yaml": app_config.get(
                            "packaging:revision"
                        ),
                    }

                _tarball = app_config.get("container:origin:tarball")
                if _tarball and os.path.exists(_tarball):
                    _ver = self.get_meta_file_from_tarball(_tarball, "version").strip()
                    _pkg_rev_img = self.get_meta_file_from_tarball(
                        _tarball, "packaging-revision"
                    ).strip()
                    _pkg_rev_yaml = app_config.get("packaging:revision")
                    tarball_apps[aid] = {
                        "tarball": _tarball,
                        "version": _ver,
                        "packaging-revision-from-image": _pkg_rev_img,
                        "packaging-revision-from-yaml": _pkg_rev_yaml,
                    }

        if get_remotes:
            for aid in registry_apps:
                app = registry_apps[aid]
                app["versions"] = self.registry.get_versions_for_app(
                    app["url"], app["image"]
                )

                curmax = max(
                    app["versions"], default=None, key=lambda x: parse_version(x)
                )
                if curmax:
                    logger.debug("Maximal version for image %s is %s", aid, curmax)
                    app["maxversion"] = curmax
                else:
                    logger.debug("No versions found for image %s", aid)

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
        current_apps, registry_apps, tarball_apps, available_apps = self.list_apps(
            get_remotes=(show_available or show_upgradeable)
        )
        app_data = {}
        if show_installed:
            for aid in current_apps:
                if aid not in app_data:
                    app_data[aid] = {"app": aid}
                app_data[aid]["installed"] = current_apps[aid]["version"]
                app_data[aid]["pacrev-yaml"] = current_apps[aid][
                    "packaging-revision-from-yaml"
                ]
                app_data[aid]["pacrev-image"] = current_apps[aid][
                    "packaging-revision-from-image"
                ]
        if show_available:
            for aid in registry_apps:
                for tag in registry_apps[aid]["versions"]:
                    if aid not in app_data:
                        app_data[aid] = {"app": aid}
                    app_data[aid]["available"] = tag
            for aid in available_apps:
                if aid not in app_data:
                    app_data[aid] = {"app": aid}
                max_avail_version = parse_version(
                    available_apps[aid]["maxversion"]["version"]
                )
                if "available" not in app_data[
                    aid
                ] or max_avail_version > parse_version(app_data[aid]["available"]):
                    app_data[aid]["available"] = available_apps[aid]["maxversion"][
                        "version"
                    ]

        if show_upgradeable:
            for aid in current_apps:
                if aid not in app_data:
                    app_data[aid] = {"app": aid}
                app_data[aid]["installed"] = current_apps[aid]["version"]
                app_data[aid]["pacrev-yaml"] = current_apps[aid][
                    "packaging-revision-from-yaml"
                ]
                app_data[aid]["pacrev-image"] = current_apps[aid][
                    "packaging-revision-from-image"
                ]
                if aid in registry_apps:
                    if "maxversion" not in registry_apps[aid]:
                        continue
                    if parse_version(registry_apps[aid]["maxversion"]) > parse_version(
                        current_apps[aid]["version"]
                    ):
                        app_data[aid]["available"] = registry_apps[aid]["maxversion"]
                elif aid in tarball_apps:
                    if parse_version(tarball_apps[aid]["version"]) > parse_version(
                        current_apps[aid]["version"]
                    ):
                        app_data[aid]["available"] = tarball_apps[aid]["version"]

        app_data_fields = {
            "app": "App",
            "installed": "Installed version",
            "available": "Available version",
            "pacrev-yaml": "Packaging revision from YAML",
            "pacrev-image": "Packaging revision from image",
        }
        for aid in app_data:
            app_data[aid]["app"] = aid
            for k in app_data_fields:
                if k not in app_data[aid]:
                    app_data[aid][k] = "-"
            app_data[aid] = {k: app_data[aid][k] for k in app_data_fields}
        if self.args.skip_headers:
            print(
                tabulate.tabulate(
                    app_data.values(),
                    numalign="right",
                    disable_numparse=True,
                )
            )
        else:
            print(
                tabulate.tabulate(
                    app_data.values(),
                    headers=app_data_fields,
                    numalign="right",
                    disable_numparse=True,
                )
            )

    def load_config(self, app):
        for p in self.config_paths:
            config = self.find_config_for_app_in_dir(p, app)
            if config:
                return config
        logger.error("Could not find appropriate config file for %s", app)
        sys.exit(1)

    def read_config(self, app):
        self.config = self.load_config(app)

        components_to_try = []
        if "component" in self.args:
            # Given on command line
            components_to_try.append(self.args.component)
        components_to_try.extend(
            [
                # Specified in yaml file
                self.config.get("container", {}).get("default_component"),
                # Default name
                "default",
                # First one in alphabetical order
                sorted(self.config["components"].keys())[0],
            ]
        )

        for component in components_to_try:
            if component not in self.config["components"]:
                continue
            self.component_config = self.config["components"][component]
            if "name" not in self.component_config:
                self.component_config["name"] = "%s/%s" % (app, component)
            return

        logger.error("Can't find an appropriate component")
        sys.exit(1)

    def parse_component_config(self, opts):
        if "environment" not in opts:
            opts["environment"] = {}
        if "mounts" not in opts:
            opts["mounts"] = []
        try:
            ports = {}
            for publish_port in self.component_config["publish_ports"]:
                ports[publish_port] = publish_port
            opts["ports"] = ports
        except KeyError:
            pass
        if "run_as_root" not in self.component_config:
            self.component_config["run_as_root"] = False

        if self.component_config["run_as_root"]:
            self.home_in = "/root"
        else:
            import pwd

            self.uid = os.getuid()
            self.uname = pwd.getpwuid(self.uid).pw_name
            self.gecos = pwd.getpwuid(self.uid).pw_gecos
            self.gid = pwd.getpwuid(self.uid).pw_gid
            self.gname = grp.getgrgid(self.gid).gr_name
            self.home_in = os.path.join("/home", self.uname)

        try:
            for mount in self.component_config["mounts"]:
                s = mount["source"]
                s = os.path.expanduser(s)
                try:
                    os.makedirs(s)
                except FileExistsError:
                    pass
                t = mount["target"]
                if t == "~":
                    t = self.home_in
                else:
                    t = re.sub("^~/", self.home_in + "/", t)
                opts["mounts"].append(docker.types.Mount(t, s, type="bind"))
        except KeyError:
            pass

        return opts

    def create_network(self, netname):
        for n in self.docker_conn.networks.list():
            if n.name == netname:
                return n
        return self.docker_conn.networks.create(name=netname, driver="bridge")

    def create_xauth(self):
        if os.getenv("DISPLAY") is None:
            logger.error("No DISPLAY set, are you running in a graphical session?")
            sys.exit(1)
        self.xauth_out = os.path.join(os.getenv("HOME"), ".docker.xauth")
        self.xauth_in = os.path.join(self.home_in, ".docker.xauth")
        f = subprocess.Popen(
            ["xauth", "nlist", os.getenv("DISPLAY")], stdout=subprocess.PIPE
        ).stdout
        g = subprocess.Popen(
            ["xauth", "-f", self.xauth_out, "nmerge", "-"], stdin=subprocess.PIPE
        ).stdin
        for line in f:
            line = str(line, "utf-8")
            line.strip()
            ll = re.sub("^[^ ]*", "ffff", line) + "\n"
            g.write(bytes(ll, "utf-8"))
        g.close()
        f.close()


class KaboxerAppConfig:
    def __init__(self, config=None, filename=None):
        if config is not None:
            self.config = config
            self.filename = None
        elif filename is not None:
            self.load(filename)
        else:
            raise ValueError("KaboxerAppConfig.__init__() lacks configuration")

    def __getitem__(self, key):
        return self.config[key]

    def __contains__(self, key):
        return key in self.config

    @property
    def app_id(self):
        return self.config.get("application", {}).get("id", None)

    def get(self, key_path, default_value=None):
        """
        Retrieves a deeply-nested value with a convenient syntax
        where `key_path` is a colon-separated list of keys to traverse
        in the configuration dictionaries.

        `app_config.get('a:b:c')` is equivalent to `app_config[a][b][c]`
        but it doesn't fail on a non-existing entry, instead it will just
        return None.
        """
        to_traverse = self.config
        for key in key_path.split(":"):
            if key in to_traverse:
                to_traverse = to_traverse[key]
            else:
                return default_value
        return to_traverse

    def load(self, path):
        with open(path) as f:
            self.config = yaml.safe_load(f)
        self.filename = path

    def save(self, path):
        with open(path, "w") as f:
            f.write(yaml.dump(self.config))


class DockerBackend:
    def get_local_image_name(self, app_config):
        return "kaboxer/%s" % app_config.app_id

    def get_remote_image_name(self, app_config):
        registry_data = app_config.get("container:origin:registry")
        if registry_data is None:
            return None

        registry = registry_data.get("url")
        if not registry:
            return None

        registry = re.sub("^https?://", "", registry)
        image = registry_data.get("image", app_config.app_id)
        return "%s/%s" % (registry, image)

    def remove_image(self, docker_conn, image_name):
        """Remove a docker image

        Returns: True if the image was removed, False otherwise.

        XXX Should check if an image is in use before trying to remove it
        """
        try:
            _ = docker_conn.images.get(image_name)
        except docker.errors.ImageNotFound:
            return False

        docker_conn.images.remove(image_name)
        return True

    def run_command(
        self, docker_conn, image_name, command, start_options, allow_missing=False
    ):
        """Run a command within a docker container

        If the command is optional (ie. it refers to an executable file that
        might not exist, and you're OK with that), set allow_missing=True.

        If an error occurs, the method raises an exception as documented in
        <https://docker-py.readthedocs.io/en/stable/containers.html>
        """
        container = docker_conn.containers.create(image_name, command, **start_options)
        try:
            dockerpty.start(docker_conn.api, container.id)
        except docker.errors.APIError as e:
            if (
                e.response.status_code == 400
                and "no such file or directory" in str(e)
                and allow_missing is True
            ):
                pass
            else:
                raise
        container.stop()
        container.remove()


def get_possible_gitlab_project_paths(full_path):
    """Get the possible project paths from a GitLab Docker image.

    We know that the image name follows the convention
    <namespace>/<project>[/<image>]. The "project path"
    is the part '<namespace>/<project>'. Additionally:
    - <project> might contain slashes
    - <image> might contain slashes
    - <image> is optional

    With that in mind, the "possible project paths" are
    all the paths that we can derive from the image name,
    eg. for an image 'a/b/c/d', the possible project paths
    are [ 'a/b/c/d', 'a/b/c', 'a/b' ].

    There's an additional trick. We make the assumption that
    the most likely image name is <project-path>/<image>,
    where <image> does not contain any slash. Therefore the
    most likely project path is the image name with the last
    element removed.

    We put it first in the list, so that it's tried first.
    """
    paths = [full_path]
    p = full_path
    while "/" in p:
        p, _ = p.rsplit("/", 1)
        paths.append(p)
    del paths[-1]
    if len(paths) > 1:
        paths[0], paths[1] = paths[1], paths[0]

    return paths


class ContainerRegistry:
    def _request_json(self, url):
        logger.debug("Requesting %s", url)
        resp = None

        try:
            resp = requests.get(url)
        except requests.ConnectionError:
            logger.debug("Failed to request %s", url, exc_info=1)
            return None

        if not resp.ok:
            logger.debug(
                "Request failed with %d (%s)",
                resp.status_code,
                HTTPStatus(resp.status_code).phrase,
            )
            return None

        try:
            json_data = resp.json()
        except ValueError:
            logger.debug("Failed to parse response as JSON: %s", resp.text)
            return None

        logger.debug("Result: %s", json_data)

        return json_data

    def _get_tags_docker_hub_registry(self, image):
        """Get image tags on the Docker Hub Registry

        This is an undocumented API endpoint. It's interesting to note that this
        endpoint also existed in the v1 API (just replace v2 by v1 in the URL),
        so maybe it exists for compatibility, however it returns a different
        output, compared to v1.

        It's not clear at all if this endpoint exists on services other than the
        Docker Hub. However it's clear that it does not require authentication.
        """

        registry_url = "https://registry.hub.docker.com"
        url = "{}/v2/repositories/{}/tags".format(registry_url, image)

        json_data = self._request_json(url)
        if not json_data:
            return []

        results = json_data.get("results", [])
        versions = []
        for r in results:
            try:
                versions.append(r["name"])
            except KeyError:
                logger.warning("Missing key in JSON: %s", r)

        return versions

    def _get_tags_docker_registry_v2(self, registry_url, image):
        """Get image tags using the Docker Registry HTTP API V2

        This API was standardized by the Open Container Initiative under the name
        of "OCI Distribution Spec". Hence we can expect it to be implemented by
        various container registries. However it seems that it can't work without
        authentication. Tested with: registry.gitlab.com, registry.hub.docker.com.

        References:
        - https://docs.docker.com/registry/spec/api/
        - https://github.com/opencontainers/distribution-spec/blob/master/spec.md
        """

        url = "{}/v2/{}/tags/list".format(registry_url, image)

        json_data = self._request_json(url)
        if not json_data:
            return []

        results = json_data.get("tags", [])
        versions = []
        for r in results:
            versions.append(r)

        return versions

    def _get_tags_gitlab_registry(self, image):
        """Get image tags using the GitLab Container Registry API

        References:
        - https://docs.gitlab.com/ce/api/
        - https://docs.gitlab.com/ce/api/container_registry.html
        """

        api_url = "https://gitlab.com/api/v4"

        # First request, list registry repositories for a project.
        #
        # At this stage, all we know is that the image name follows the
        # convention <namespace>/<project>[/<image>].  In order to talk
        # to the API, we need to know the part '<namespace>/<project>'
        # (ie. the "project path"). The only way to find it is to send
        # HTTP requests until we get a positive result.
        #
        # References:
        # - https://docs.gitlab.com/ce/user/packages/container_registry/#image-naming-convention  # noqa: E501
        # - https://docs.gitlab.com/ce/api/#namespaced-path-encoding

        # Sanitize image, remove stray slashes
        image = image.strip("/")
        image = re.sub("/+", "/", image)

        project_paths = get_possible_gitlab_project_paths(image)
        json_data = None
        for path in project_paths:
            url = "{}/projects/{}/registry/repositories".format(
                api_url, urllib.parse.quote(path, safe="")
            )
            json_data = self._request_json(url)
            if json_data:
                break

        if not json_data:
            return []

        try:
            _ = iter(json_data)
        except TypeError:
            logger.warning("Unexpected json: %s", json_data)
            return []

        project_id = ""
        repository_id = ""
        for item in json_data:
            if item.get("path", "") != image:
                continue
            project_id = item.get("project_id", "")
            repository_id = item.get("id", "")
            break

        if not project_id or not repository_id:
            logger.warning(
                "Could not find valid image '%s' in json: %s", image, json_data
            )
            return []

        # Second request, list registry repository tags

        url = "{}/projects/{}/registry/repositories/{}/tags".format(
            api_url, project_id, repository_id
        )

        json_data = self._request_json(url)
        if not json_data:
            return []

        try:
            _ = iter(json_data)
        except TypeError:
            logger.warning("Unexpected json: %s", json_data)
            return []

        tags = []
        for item in json_data:
            try:
                tags.append(item["name"])
            except KeyError:
                logger.warning("Missing keys in json: %s", item)

        return tags

    def get_versions_for_app(self, registry_url, image):
        """List versions of an image on a remote registry.

        Returns: an array of versions.
        """

        if not re.match("^https?://", registry_url):
            registry_url = "https://" + registry_url

        if "registry.gitlab.com" in registry_url:
            versions = self._get_tags_gitlab_registry(image)
        elif "registry.hub.docker.com" in registry_url:
            versions = self._get_tags_docker_hub_registry(image)
        else:
            versions = self._get_tags_docker_registry_v2(registry_url, image)

        return versions


def main():
    kaboxer = Kaboxer()
    kaboxer.go()


if __name__ == "__main__":
    main()
