import json
import sys
import urllib

import mesos

from mesos.plugins import PluginBase


PLUGIN_CLASS = "Example"
PLUGIN_NAME = "example"

VERSION = "Mesos CLI Example Plugin 1.0"

SHORT_HELP = "Example commands for the mesos CLI"


class Example(PluginBase):
    """ The Example Plugin """

    COMMANDS = {
        "echo" : {
            "arguments" : ["[<args>...]"],
            "flags" : {},
            "short_help" : "Echo back all arguments passed to this command.",
            "long_help"  : """\
                This command mimics the basic functionality provided by 'echo'
                on standard Unix systems. It will take all arguments passed to
                it and echo them to stdout.
            """
        }
    }

    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    def echo(self, argv):
        print " ".join(argv["<args>"])
