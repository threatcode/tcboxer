% KBXBUILDER.CONFIG.YAML(5)
% Roland Mas, Raphaël Hertzog, Arnaud Rebillout
% 2019-2021

# NAME

*kbxbuilder.config.yaml* - Configuration file for **kbxbuilder**

# SYNOPSIS

*kbxbuilder.config.yaml*

# DESCRIPTION

The *kbxbuilder.config.yaml* file contains the
configuration for **kbxbuilder**(1).

The syntax is YAML, which is human-readable yet formal enough for use
by applications. See specific documentation for this format, for
instance at https://yaml.org/

The file describes a hierarchical data structure based on key-value
pairs where the values can themselves be hierarchical; this can be
seen as a configuration file with sections and subsections.

Note that the configuration values are interpreted as Jinja templates,
which allows variables to refer to others (see below).

# BUILDER SECTION

The *builder* section contains configuration variables for the builder:

* *basedir* is the path where kbxbuilder looks for the applications' \*.kaboxer.yaml files.

* *workdir* is a directory used by **kbxbuilder** to store various internal files.

* *datadir* is where **kbxbuilder** stores data such as version
   numbers, status of applications and so on.

* *buildlogsdir* is where the individual build logs will be stored.

* *logfile* is the log of **kbxbuilder** itself, not separated by applications.

In many cases, the workdir, datadir, buildlogsdir and logfile will all
reside under a given directory; this can be formulated as the basedir,
and referred to by the other variables using Jinja templating markup.

# ON_SUCCESS/ON_FAILURE SECTIONS

These sections follow the same structure, and they allow defining
actions to be taken when a build is either successful or failed.  Two
kinds of generic action are implemented:

* *execute_command*, which requires a ``command`` parameter;

* *send_mail*, which requires the ``from``, ``to`` and ``subject`` parameters.

In addition, the *on_success* section also understands the
``push_to_registry`` action, which requires no parameters since the
registry is defined in the **kaboxer.yaml**(5) file of each app.

# EXAMPLE

A sample configuration file could look like the following:

```
builder:
  basedir: /var/lib/kbxbuilder
  workdir: "{{ config['builder']['basedir'] }}/work"
  datadir: "{{ config['builder']['basedir'] }}/data"
  buildlogsdir: "{{ config['builder']['basedir'] }}/build-logs"
  logfile: "{{ config['builder']['datadir'] }}/kbx-builder.log"
on_success:
  - action: push_to_registry
  # - action: send_mail
  #   from: 'test@example.com'
  #   to: 'test@example.com'
  #   subject: "kbxbuilder: {{ app }} built successfully"
  - action: execute_command
    command: echo "Build of {{ app }} succeeded" | tr a-z A-Z
on_failure:
  - action: execute_command
    command: echo "Build of {{ app }} failed" | tr a-z A-Z
  # - action: send_mail
  #   from: 'test@example.com'
  #   to: 'test@example.com'
  #   subject: "kbxbuilder: {{ app }} built successfully"
```

Note the {{ \<foo> }} markup, and how it is used to refer to the basedir
(which is another variable defined in the same file) or to the
application identifier (which is filled at run time by **kbxbuilder**
with the identifier of the app being built, so that success/error
messages can be made informative).
