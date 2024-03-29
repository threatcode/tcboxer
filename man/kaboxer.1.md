% KABOXER(1)
% Roland Mas, Raphaël Hertzog, Arnaud Rebillout
% 2019-2021

# NAME

**kaboxer** - Manage Kali Applications in containers

# SYNOPSIS

**kaboxer** run|start [**--component** *COMPONENT*] [**--detach**] [**--prompt-before-exit**] [**--version** *VERSION*] *APP* [*ARGUMENTS*]...

**kaboxer** stop [**--component** *COMPONENT*] [**--prompt-before-exit**] *APP*

**kaboxer** get-meta-file *APP* *FILE*

**kaboxer** get-upstream-version *APP*

**kaboxer** prepare *APP*...

**kaboxer** upgrade *APP*...

**kaboxer** list|ls [**--installed**] [**--available**] [**--upgradeable**] [**--all**] [**--skip-headers**]

**kaboxer** build [**--skip-image-build**] [**--save**] [**--push**] [**--version** *VERSION*] [**--ignore-version**] [*APP*] [*PATH*]

**kaboxer** install [**--tarball**] [**--destdir** *DESTDIR*] [**--prefix** *PREFIX*] [*APP*] [*PATH*]

**kaboxer** clean [*APP*] [*PATH*]

**kaboxer** pull *APP*...

**kaboxer** push [**--version** *VERSION*] *APP* [*PATH*]

**kaboxer** save *APP* *FILE*

**kaboxer** load *APP* *FILE*

**kaboxer** purge [**--prune**] *APP*

# DESCRIPTION

**kaboxer** is a framework to build, deploy, install and run images of
containerized applications.  The tool uses subcommands, each with
their own arguments and options.

# CONFIGURATION

Kaboxer creates a *kaboxer group* on installation. This group grants the
kaboxer command a passwordless access to the docker group. Thanks to that, a
normal user can run Kaboxer without having to type the root password.

You can make yourself a member of the kaboxer group by running the command:
*sudo usermod -aG kaboxer $USER*. Remember to log out and to log back in for
the change to take effect.

# GENERAL OPTIONS

**-h**, **--help**
:   Display a friendly help message.

**-v**, **--verbose**
:   Increase verbosity (can be used several times).

# KABOXER RUN

**kaboxer** run [**--component** *COMPONENT*] [**--detach**] [**--prompt-before-exit**] [**--version** *VERSION*] *APP* [*ARGUMENTS*]...

The run mode is how you actually run a kaboxed application *APP*. In
case several components exist for this app, use
**--component** *COMPONENT* to choose which one to run; if the
component is meant to run in the background as a daemon, use
**--detach** flag, possibly with the **--prompt-before-exit** flag
(which waits a user confirmation before exiting, so that the user has the
time to read any message displayed or so that applications started in the
after\_run hook are not immediately closed). In case several versions of
the app are installed, the **--version** *VERSION* option can be used to
select which one to actually run. The *ARGUMENTS* parameter can be used
to pass extra arguments to the application.

**kaboxer start** is an alias for **kaboxer run**.

# KABOXER STOP

**kaboxer** stop [**--component** *COMPONENT*] [**--prompt-before-exit**] *APP*

Stops a running container for application *APP*. Specify
**--component** *COMPONENT* if the app is multi-component to select
which one to stop. Use **--prompt-before-exit** to wait a user
confirmation before exiting.

# KABOXER GET-META-FILE

**kaboxer** get-meta-file *APP* *FILE*

Extracts medadata file *FILE* from the container image for application
*APP*. Mostly used internally by **kaboxer**.

# KABOXER GET-UPSTREAM-VERSION

**kaboxer** get-upstream-version *APP*

Extracts the upstream version of installed application *APP*.

# KABOXER PREPARE

**kaboxer** prepare *APP*...

Runs whatever steps are needed to make the container for application
*APP* ready to run: unpacking an image from a file, pulling from a
registry, and so on. Multiple applications can be prepared at the same time.

# KABOXER UPGRADE

**kaboxer** upgrade *APP*...

Brings the installed image for application *APP* to the latest
version. As for **kaboxer prepare**, multiple applications can be
handled at the same time.

# KABOXER LIST

**kaboxer** list [**--installed**] [**--available**] [**--upgradeable**] [**--all**] [**--skip-headers**]

Displays lists of known applications, either a single category
(**--installed** and so on), or all applications (**--all**). The
**--skip-headers** flag hides the column headers to allow for
scriptability.

**kaboxer ls** is an alias for **kaboxer list**.

# KABOXER BUILD

**kaboxer** build [**--skip-image-build**] [**--save**] [**--push**] [**--version** *VERSION*] [**--ignore-version**] [*APP*] [*PATH*]

Builds **kaboxer** images for applications. Unless an application
*APP* is specified, builds all applications found in directory *PATH*
(uses the current directory if unspecified).  With **--save**, saves
the image as a tarball. With **--push**, pushes the image to its
configured registry. With **--version** *VERSION*, passes a version
number to the build process to build an image for a specific
version. With **--ignore-version**, ignores version checks embedded in
the \*.kaboxer.yaml file. With **--skip-image-build**, only builds
the command-line helpers and desktop files, and does not try to build
the container image.

# KABOXER INSTALL

**kaboxer** install [**--tarball**] [**--destdir** *DESTDIR*] [**--prefix** *PREFIX*] [*APP*] [*PATH*]

Installs image and related files (command-line helpers, \*.desktop
files and icons). With **--tarball**, uses an image saved as a tarball.
With **--destdir** *DESTDIR*, use a specific installation directory
(can be used for packaging).

If *APP* is omitted, install all apps corresponding to \*.kaboxer.yaml
files found in path *PATH* (current directory if omitted).

# KABOXER CLEAN

**kaboxer** clean [*APP*] [*PATH*]

Removes files generated as part of **kaboxer** build (tarballs,
generated command-line helpers and \*.desktop files).

If *APP* is omitted, cleans all apps corresponding to \*.kaboxer.yaml
files found in path *PATH* (current directory if omitted).

# KABOXER PUSH

**kaboxer** push [**--version** *VERSION*] *APP* [*PATH*]

Push an image for application *APP* to its configured registry. If
**--version** *VERSION* is specified, push a specific version.

# KABOXER SAVE

**kaboxer** save *APP* *FILE*

Save the image for application *APP* into a tarball at *FILE*.

# KABOXER LOAD

**kaboxer** load *APP* *FILE*

Loads the image for application *APP* from a tarball at *FILE*.

# KABOXER PURGE

**kaboxer** purge [**--prune**] *APP*

Uninstalls application *APP* completely.
