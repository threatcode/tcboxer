# Kaboxer
Kaboxer is a framework to manage applications in containers on Kali Linux (and other Debian-based) systems. It allows shipping applications that are hard to package properly or that need to run in isolation from the rest of the system.

The framework has two parts; the ``kaboxer`` tool is the main UI for starting, stopping, creating and managing containers and the relevant images. There's also ``dh_kaboxer``, a helper that can be used in source packages and that partially automates the process of creating a package for an app that uses Kaboxer.

kaboxer
-------
The kaboxer tool has several modes of operation, each with its own subcommand.

### kaboxer run
	$ kaboxer run --help
	usage: kaboxer run [-h] [--component COMPONENT] [--reuse-container] [--detach]
	                   app [executable [executable ...]]
	
	positional arguments:
	  app
	  executable
	
	optional arguments:
	  -h, --help            show this help message and exit
	  --component COMPONENT
	                        component to run
	  --reuse-container     run in existing container
	  --detach

The main user-facing mode of operation, ``kaboxer run`` starts a containerized application. Depending on the configuration, this may result in a text-mode interface, a graphical application, or a headless daemon. If several components exist in the image, the ``--component`` option can be used to select which one to run. If the container is already running, then ``--reuse-container`` allows reusing it; both options can be combined, for instance if the image contains both a server part and a client part. 

### kaboxer stop
	$ kaboxer stop --help
	
	usage: kaboxer stop [-h] app
	
	positional arguments:
	  app
	
	optional arguments:
	  -h, --help  show this help message and exit


``kaboxer stop`` stops a running container. It can be used in system scripts for instance.

### kaboxer build
	$ kaboxer build --help
	usage: kaboxer build [-h] app [path]
	
	positional arguments:
	  app
	  path
	
	optional arguments:
	  -h, --help  show this help message and exit


``kaboxer build`` is normally only used during development. It builds the container image from the specified path.

### kaboxer save
	$ kaboxer save --help
	usage: kaboxer save [-h] app file
	
	positional arguments:
	  app
	  file
	
	optional arguments:
	  -h, --help  show this help message and exit

``kaboxer save`` generates a self-contained image of a previously-built container.

### kaboxer load
	$ kaboxer load --help
	usage: kaboxer load [-h] app file
	
	positional arguments:
	  app
	  file
	
	optional arguments:
	  -h, --help  show this help message and exit


``kaboxer load`` takes a self-contained image and makes it available for running.

### kaboxer purge
	$ kaboxer purge --help
	usage: kaboxer purge [-h] app
	
	positional arguments:
	  app
	
	optional arguments:
	  -h, --help  show this help message and exit


``kaboxer purge`` removes an image from the container engine.

### Examples
The ``kbx-hello-*`` packages provide examples for the various modes of operation.
``kbx-hello-server`` includes a systemd service that starts the server as a daemon. It uses ``kaboxer run kbx-hello-server`` and ``kaboxer stop kbx-hello-server`` to actually start or stop the container.
``kbx-hello-cli`` is a text-mode client. It runs in a terminal using ``kaboxer run kbx-hello-cli``.
``kbx-hello-gui`` is a graphical client. It runs in a terminal using ``kaboxer run kbx-hello-gui``.


dh_kaboxer
----------

``dh_kaboxer`` is a Debhelper addon that eases generation and management of Kaboxer images in packages. It automates the building of images and their shipping in the packages.

It works by specifying ``--with kaboxer`` as a parameter for ``dh``, and it expects the following for each binary package that should ship a Kaboxer image:
- a ``debian/<package>.kaboxer.yaml`` file that contains the parameters for kaboxed app: a run mode, a list of networks to create or connect to, a list of mounts, and so on.
- a ``debian/<package>.Dockerfile`` that is a standard Dockerfile for building the container image.

dh_kaboxer does not by itself create or install systemd service files or desktop files, but these files are made easy to write by the ``kaboxer`` tool since all the logic is handled by Kaboxer based on the ``.kaboxer.yaml`` configuration files.

Again, refer to the ``kbx-hello-*`` packages provided as examples by the ``kaboxer`` package.

Copyright
=========

Kaboxer is a product developed by Offensive Security. Unless documented otherwise, all files in this repository are copyrighted by Offensive Security.

