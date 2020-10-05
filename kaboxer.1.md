% KABOXER(1)
% Roland Mas
% 2019-2020

# NAME

**kaboxer** – Kali Application boxes

# SYNOPSIS

**kaboxer** run [**--component** *COMPONENT*] [**--reuse-container**] [**--detach**] [**--prompt-before-detach**] [**--version** *VERSION*] *APP* [*EXECUTABLE*]...

**kaboxer** stop [**--component** *COMPONENT*] *APP*

**kaboxer** get-meta-file *APP* *FILE*

**kaboxer** get-upstream-version *APP*

**kaboxer** prepare *APP*...

**kaboxer** upgrade *APP*...

**kaboxer** list [**--installed**] [**--available**] [**--upgradeable**] [**--all**] [**--skip-headers**]

**kaboxer** build [**--save**] [**--push**] [**--version** *VERSION*] [**--ignore-version**] [*APP*] [*PATH*]

**kaboxer** install [**--tarball**] [**--destdir** *DESTDIR*] [**--prefix** *PREFIX*] [*APP*] [*PATH*]

**kaboxer** clean [*APP*] [*PATH*]

**kaboxer** pull *APP*...

**kaboxer** push [**--version** *VERSION*] *APP*

**kaboxer** save *APP* *FILE*

**kaboxer** load *APP* *FILE*

**kaboxer** purge [**--prune**] *APP*

# DESCRIPTION

**kaboxer** is a framework to build, deploy, install and run images of
containerized applications.  The tool uses subcommands, each with
their own arguments and options.

# GENERAL OPTIONS

**-h**, **--help**
:   Display a friendly help message.

**-v**, **--verbose**
:   Increase verbosity (can be used several times).

# KABOXER RUN

**kaboxer** run [**--component** *COMPONENT*] [**--reuse-container**] [**--detach**] [**--prompt-before-detach**] [**--version** *VERSION*] *APP* [*EXECUTABLE*]...

The run mode is how you actually run a kaboxed application *APP*. In
case several components exist for this app, use
**--component** *COMPONENT* to choose which one to run; if these
components are intended to run in the same container (rather than in
different but communicating containers), use **--reuse-container**. If
the component is meant to run in the background as a daemon, use
**--detach** flag, possibly with the **--prompt-before-detach** flag
(which can be used to display relevant information before going to
background). In case several versions of the app are installed, the
**--version** *VERSION* option can be used to select which one to
actually run. The *EXECUTABLE* parameter can be used to pass extra
arguments to the application.

# KABOXER STOP

**kaboxer** stop [**--component** *COMPONENT*] *APP*

Stops a running container for application *APP*. Specify
**--component** *COMPONENT* if the app is multi-component to select
which one to stope

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
version. As for **kaboxer**_prepare_, multiple applications can be
handled at the same time.

# KABOXER LIST

**kaboxer** list [**--installed**] [**--available**] [**--upgradeable**] [**--all**] [**--skip-headers**]

Displays lists of known applications, either a single category
(**--installed** and so on), or all applications (**--all**). The
**--skip-headers** flag hides the column headers to allow for
scriptability.

# KABOXER BUILD

**kaboxer** build [**--save**] [**--push**] [**--version** *VERSION*] [**--ignore-version**] [*APP*] [*PATH*]

Builds **kaboxer** images for applications. Unless an application
*APP* is specified, builds all applications found in directory *PATH*
(uses the current directory if unspecified).  With **--save**, saves
the image as a tarball. With **--push**, pushes the image to its
configured registry. With **--version** *VERSION*, passes a version
number to the build process to build an image for a specific
version. With **--ignore-version**, ignore version checks embedded in
the *.kaboxer.yaml file.

# KABOXER INSTALL

**kaboxer** install [**--tarball**] [**--destdir** *DESTDIR*] [**--prefix** *PREFIX*] [*APP*] [*PATH*]

Installs image and related files (\*.desktop files and icons). With
**--tarball**, uses an image saved as a tarball.  With
**--destdir** *DESTDIR*, use a specific installation directory (can be
used for packaging).
If *APP* is omitted, install all images
corresponding to \*.kaboxer.yaml files found in path *PATH* (current
directory if omitted).

# KABOXER CLEAN

**kaboxer** clean [*APP*] [*PATH*]

Removes files generated as part of **kaboxer** build (tarballs and
generated \*.desktop files). If *APP* is omitted, cleans all apps
corresponding to \*.kaboxer.yaml files found in path *PATH* (current
directory if omitted).

# KABOXER PULL

**kaboxer** pull *APP*...

Alias for **kaboxer** build. Should not be used. TODO: remove

# KABOXER PUSH

**kaboxer** push [**--version** *VERSION*] *APP*

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
