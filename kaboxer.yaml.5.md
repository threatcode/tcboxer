% KABOXER.YAML(5)
% Roland Mas
% 2019-2020

# NAME

*kaboxer.yaml* - Configuration file for **kaboxer**

# SYNOPSIS

*kaboxer.yaml* or *\<APP\>.kaboxer.yaml*

# DESCRIPTION

The *kaboxer.yaml* file (or *\<APP\>.kaboxer.yaml* file if needed –
we'll only refer to *kaboxer.yaml* from here on) contains the
configuration for applications containerized with **kaboxer**(1).

The syntax is YAML, which is human-readable yet formal enough for use
by applications. See specific documentation for this format, for
instance at https://yaml.org/

The file describes a hierarchical data structure based on key-value
pairs where the values can themselves be hierarchical; this can be
seen as a configuration file with sections and subsections.

# APPLICATION SECTION

The *application* section contains metadata about the application
itself:

* *id* (string) is the app identifier; it's used to refer to the app
  all over **kaboxer**, whether at build time, install time, run time
  and so on.

* *name* (string) is a user-friendly name used for display.

* *description* (string) is a longer description, which can be used
  in tooltips or wherever a description of the application is
  displayed.

* *categories* (string) is a semicolon-separated list of
  categories. Used for desktop files.

# CONTAINER SECTION

* *default_component* (string): the component to run unless
  specified. Must be listed in the *components* section. If not
  specified in the config file, **kaboxer** looks for a component
  named *default*; if none is found, it falls back to the first listed
  component.

* *type* (string): the isolation technology used for the app. Only
  "docker" supported for now.

* *origin*: subsection describing where to find the image.

# CONTAINER/ORIGIN SECTION

* *tarball* (string): the name of the file where the image will be
  saved (or loaded from).

* *registry* (hash): an alternative to *tarball*. If specified, must
  consist of two keys and their related values: *url* as the URL base
  for the Docker registry, and *image* for the image name used on that
  registry.

# BUILD SECTION

Since only Docker is supported, the only relevant subsection is
*docker*.

# BUILD/DOCKER SUBSECTION

* *file*: the name of the Dockerfile to use

* *parameters*: extra parameters passed to the Docker build

# PACKAGING SECTION

* *revision* (version number): a version number for the Kaboxer
  package of the application (not necessarily the version of the app
  itself).

* *min_upstream_version* (version number): the minimal upstream
  version number of the application that is supported by the Kaboxer
  packaging.

* *max_upstream_version* (version number): likewise, for the maximal
  version.

# INSTALL SECTION

* *icon* (file name): the location of an icon that should be shipped
  with the image.

* *extract-icon* (path): the location of an icon in the image that
  should be extracted at image installation time for use in the host,
  for instance in graphical menus.

* *desktop-files* (list): a list of \*.desktop files to
  install on the host in order to make the application visible in
  graphical menus.

# COMPONENTS SECTION

Each component has its own subsection identified by a component name.

# COMPONENTS/* SUBSECTIONS

* *run_mode* (string): describes how the application is to be
  run. Can be *headless* for daemon-like services, *cli* for text-mode
  applications, or *gui* for graphical applications.

* *allow_x11* (boolean): describes whether the component is liable
  to run graphical applications that should be displayed outside the
  container. Note: if the application has several components that can
  run in the same container, this option needs to be present in the
  first component that will be started.

* *run_as_root* (boolean): whether the executable is run as root in
  the container or as a non-privileged user.

* *reuse container* (boolean): whether the component is run in its
  own container or shares an already active container.

* *name* (string): a user-friendly name for the component.

* *start_message* (string): a message to be displayed before
  detaching, if relevant.

* *stop_message* (string): a message to be displayed after the service
  has stopped.

* *executable* (string): the command line to run within the
  container to start the component.

* *networks* (list): a list of network names that the container should
  be plugged into.

* *mounts* (list): a list of mounts. Each item in this list describes
  a mount, and is represented by a hash with keys *source* and
  *target*, where *source* is a path on the host side and *target* is
  a path on the container side.

* *publish_ports* (list): a list of ports that are published, so that
  an application that listens to TCP connections can be accessed from
  outside the container.

* *extra_opts* (string): extra options to be passed as command line
  arguments when starting the application in the container.
