import sys
import StringIO
import unittest

import main


class TestCommands(unittest.TestCase):

    def test_echo(self):
        stdout = sys.stdout
        sys.stdout = StringIO.StringIO()

        argv = {
            "<args>" : ["arg1", "arg2", "arg3"]
        }
        example = main.Example(None)
        example.echo(argv)

        sys.stdout.seek(0)
        output = sys.stdout.read().strip()

        self.assertEqual(" ".join(argv["<args>"]), output)

        sys.stdout = stdout

