# Mesos CLI

## Prerequisites

Make sure you have the following prerequisites
installed on your system before you begin.

```
python 2.7.x
virutalenv
```

## Getting Started

Once you you have the prerequisites installed, simply
run the top level `bootstrap` script to set up a python
virtual environment and start running the tool.

```
$ ./bootstrap

...

Setup complete!

To begin working, simply activate your virtual environment,
run the CLI, and then deactivate the virtual environment
when you are done.

    $ source activate
    $ mesos <command> [<args>...]
    $ source deactivate
```

**NOTE:** The virtual environment will also setup bash
autocomplete for all `mesos` commands.

## Building the CLI Into an Executable

If you want to build the CLI into a standalone executable
(with a bundled python interpreter and all of the CLI plugins
builtin), simply run `make` from within the virtual environment.

```
$ make
```

This will place an executable called `mesos` in the path of your
virtual environment at:

```
$ .virtualenv/bin/mesos
```

This executable is an actual binary (with no external dependence
on python) and can be moved around freely and distributed in standard
`rpm` and `deb` packages the same as any other binary.

The bash autocomplete script for the executable is found in
`mesos.bash_completion`. You can either source it directly or add
it to something like `~/.bash_completion` and source it from there
(this will cause it to always be sourced whenever you login to your shell).

```
$ source mesos.bash_autocompletion
```
