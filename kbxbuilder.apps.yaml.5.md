% KBXBUILDER.APPS.YAML(5)
% Roland Mas
% 2019-2020

# NAME

*kbxbuilder.apps.yaml* - Configuration file for **kbxbuilder**

# SYNOPSIS

*kbxbuilder.apps.yaml*

# DESCRIPTION

The *kbxbuilder.config.yaml* file contains the list of apps that
**kbxbuilder** operates on, with configuration about each app.

The syntax is YAML, which is human-readable yet formal enough for use
by applications. See specific documentation for this format, for
instance at https://yaml.org/

The file describes a hierarchical data structure based on key-value
pairs where the values can themselves be hierarchical; this can be
seen as a configuration file with sections and subsections.

Each app has its own section (named after its application identifier),
with app-specific variables defined within that section.

# APP SECTION

Each section contains the following configuration variables:

* *buildmode*: only ``kaboxer`` is implemented right now.

* *push*: ``True`` or ``False``, depending on whether **kbxbuilder**
  should push the images to their appropriate registry after building

* *git_url*: the URL of a Git repository where **kbxbuilder** fetches
  the sources of the applications to build.

* *subdir*: the subdirectory (within the Git working copy) where
  **kbxbuilder** operates.

* *branch*: the name of a branch to handle (actually, this can be any
  Git reference: a branch, a tag, a revid…)

# EXAMPLE

A sample configuration file could look like the following:

```
kbx-demo:
  buildmode: kaboxer
  push: True
  git_url: https://gitlab.com/kalilinux/tools/kaboxer.git
  subdir: tests/fixtures
  branch: master
```
