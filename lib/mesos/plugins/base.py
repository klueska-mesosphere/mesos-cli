import sys

import mesos

from mesos.docopt import docopt


PLUGIN_NAME = "base-plugin"
PLUGIN_CLASS = "PluginBase"

VERSION = "Mesos Plugin Base 1.0"

SHORT_HELP = "This is the base plugin from which all other plugins inherit."

USAGE = \
"""
{short_help}

Usage:
  mesos {plugin} (-h | --help)
  mesos {plugin} --version
  mesos {plugin} <command> (-h | --help)
  mesos {plugin} <command> [<args>...] [options]

Options:
  -h --help  Show this screen.
  --version  Show version info.

Commands:
{commands}
"""

SUBCOMMAND_USAGE = \
"""{short_help}

Usage:
  mesos {plugin} {command} (-h | --help)
  mesos {plugin} {command} --version
  mesos {plugin} {command} {arguments} [options]

Options:
{flags}

Description:
{long_help}
"""


class PluginBase():
    COMMANDS = {}

    def __setup__(self, command, argv):
        pass

    def __module_reference__(self):
        return sys.modules[self.__module__]

    def __init__(self, config):

        self.PLUGIN_NAME  = PLUGIN_NAME
        self.PLUGIN_CLASS = PLUGIN_CLASS
        self.VERSION      = VERSION
        self.SHORT_HELP   = SHORT_HELP
        self.USAGE        = USAGE

        module = self.__module_reference__()
        if hasattr(module, "PLUGIN_NAME"):
            self.PLUGIN_NAME = getattr(module, "PLUGIN_NAME")
        if hasattr(module, "PLUGIN_CLASS"):
            self.PLUGIN_CLASS = getattr(module, "PLUGIN_CLASS")
        if hasattr(module, "VERSION"):
            self.VERSION = getattr(module, "VERSION")
        if hasattr(module, "SHORT_HELP"):
            self.SHORT_HELP = getattr(module, "SHORT_HELP")
        if hasattr(module, "USAGE"):
            self.USAGE = getattr(module, "USAGE")

        self.config = config

    def __autocomplete__(self, command, current_word, argv):
        return ("default", [])

    def __autocomplete_base__(self, current_word, argv):
        option = "default"

        # <command>
        comp_words = list(self.COMMANDS.keys())
        comp_words = mesos.util.completions(comp_words, current_word, argv)
        if comp_words != None:
            return (option, comp_words)

        # <args>...
        comp_words = self.__autocomplete__(argv[0], current_word, argv[1:])

        # In general, we expect a tuple to be returned from __autocomplete__,
        # with the first element being a valid autocomplete option, and the
        # second being a list of completion words. However, in the common
        # case we usually use the default option, so it's OK for a plugin to
        # just return a list. We will add the "default" option for them.
        if (isinstance(comp_words, tuple)):
            option, comp_words = comp_words

        return (option, comp_words)

    def main(self, argv):
        command_strings = mesos.util.format_commands_help(self.COMMANDS)

        usage = self.USAGE.format(
            plugin=self.PLUGIN_NAME,
            short_help=self.SHORT_HELP,
            commands=command_strings)

        arguments = docopt(
            usage,
            argv=argv,
            version=self.VERSION,
            program="mesos " + self.PLUGIN_NAME,
            options_first=True)

        cmd = arguments["<command>"]
        argv = arguments["<args>"]

        if cmd in self.COMMANDS.keys():
            if "external" not in self.COMMANDS[cmd]:
                argument_format, short_help, long_help, flag_format = \
                    mesos.util.format_subcommands_help(self.COMMANDS[cmd])

                usage = SUBCOMMAND_USAGE.format(
                    plugin=self.PLUGIN_NAME,
                    command=cmd,
                    arguments=argument_format,
                    flags=flag_format,
                    short_help=short_help,
                    long_help=long_help)

                arguments = docopt(
                    usage,
                    argv=argv,
                    program="mesos " + self.PLUGIN_NAME + " " + cmd,
                    version=self.VERSION,
                    options_first=True)

            self.__setup__(cmd, argv)
            getattr(self, cmd.replace("-", "_"))(arguments)
        else:
            self.main(["--help"])
