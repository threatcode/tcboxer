% KBXBUILDER(1)
% Roland Mas, Raphaël Hertzog, Arnaud Rebillout
% 2019-2020

# NAME

**kbxbuilder** - builder for Kaboxer images

# SYNOPSIS

**kbxbuilder** build-one *APP*

**kbxbuilder** build-all

**kbxbuilder** build-as-needed

# DESCRIPTION

**kbxbuilder** is a script that wraps around **kaboxer** in order to
build several applications in a row, and/or regularly, and/or when
needed.  It can also push the generated images to a registry.

**kbxbuilder** uses two configuration files.  A
``kbxbuilder.config.yaml`` contains generic configuration for the
program and its behaviour (directories, what to do on build
success/failure, and so on); ``kbxbuilder.apps.yaml`` contains the
list of apps that **kbxbuilder** is meant to build, with information
specific to each of these apps.  See the **kbxbuilder.config.yaml**(5)
and  **kbxbuilder.apps.yaml**(5) manpages for detailed information on
these files.

# KBXBUILDER BUILD-ONE

**kbxbuilder** build-one *APP*

The build-one mode of operation tells **kbxbuilder** to build the
image for the specified application.

# KBXBUILDER BUILD-ALL

**kbxbuilder** build-all

This mode builds all applications referenced in the
``kbxbuilder.apps.yaml`` file.

# KBXBUILDER BUILD-AS-NEEDED

**kbxbuilder** build-as-needed

This mode builds applications referenced in the
``kbxbuilder.apps.yaml`` file, but only those that need building or
rebuilding.  **kbxbuilder** records the build status of applications
and their versions, and only builds applications that have not already
been built in their current version.

