import imp
import importlib
import json
import os
import textwrap
import urllib2

from mesos.exceptions import CLIException


def import_modules(package_paths, module_type):
    """
    Looks for python packages under `package_paths` and imports
    them as modules. Returns a dictionary of the basename of the
    `package_paths` to the imported modules.
    """
    modules = {}
    for package_path in package_paths:
        # We put the imported module into the namespace of
        # "mesos.<module_type>.<>" to keep it from cluttering up
        # the import namespace elsewhere.
        package_name = os.path.basename(package_path)
        package_dir = os.path.dirname(package_path)
        module_name = "mesos." + module_type + "." + package_name
        try:
            module = importlib.import_module(module_name)
        except:
            (file, filename, data) = imp.find_module(package_name, \
                                                        [package_dir])
            module = imp.load_module(module_name, file, filename, data)
        modules[package_name] = module

    return modules


def get_module(modules, import_path):
    """
    Given a modules dictionary returned by `import_modules()`,
    return a reference to the module at `import_path` relative
    to the base module. For example, get_module(modules, "example.stuff")
    will return a reference to the "stuff" module inside the
    imported "example" plugin.
    """
    import_path = import_path.split('.')
    module = modules[import_path[0]]
    if len(import_path) > 1:
        module = getattr(module, ".".join(import_path[1:]))
    return module


def completions(comp_words, current_word, argv):
    comp_words += ["-h", "--help", "--version"]

    if len(argv) == 0:
        return comp_words

    if len(argv) == 1:
        if argv[0] not in comp_words and current_word:
            return comp_words

        if argv[0] in comp_words and current_word:
            return comp_words

        if argv[0] not in comp_words and not current_word:
            return []

        if argv[0] in comp_words and not current_word:
            return None

    if len(argv) > 1 and argv[0] not in comp_words:
        return []

    if len(argv) > 1 and argv[0] in comp_words:
        return None

    raise CLIException("Unreachable")


def format_commands_help(cmds):
    longest_cmd_name = max(cmds.keys(), key=len)

    help_string = ""
    for cmd in sorted(cmds.keys()):
        # For mesos, the `cmds` is a single-level dictionary with `short_help`
        # as the values.  For plugins, the `cmds` is a two-level dictionary,
        # where `short_help` is a field in each sub-dictionary.
        short_help = cmds[cmd]
        if isinstance(short_help, dict):
            short_help = short_help["short_help"]

        num_spaces = len(longest_cmd_name) - len(cmd) + 2
        help_string += "  %s%s%s\n" % (cmd, " " * num_spaces, short_help)

    return help_string


def format_subcommands_help(cmd):
    arguments = " ".join(cmd["arguments"])
    short_help = cmd["short_help"]
    long_help = textwrap.dedent(cmd["long_help"].rstrip())
    long_help = "  " + "\n  ".join(long_help.split('\n'))
    flags = cmd["flags"]
    flags["-h --help"] = "Show this screen."
    flag_string = ""

    if len(flags.keys()) != 0:
        longest_flag_name = max(flags.keys(), key=len)
        for flag in sorted(flags.keys()):
            num_spaces = len(longest_flag_name) - len(flag) + 2
            flag_string += "  %s%s%s\n" % (flag, " " * num_spaces, flags[flag])

    return (arguments, short_help, long_help, flag_string)

# Hit the specified endpoint and return the results as JSON.
def hit_endpoint(addr, endpoint):
    try:
        url = "http://{addr}/{endpoint}".format(
              addr=addr, endpoint=endpoint)

        http_response = urllib2.urlopen(url).read().decode("utf-8")
    except Exception as exception:
        raise CLIException("Could not open '{url}': {error}"
                           .format(url=url, error=str(exception)))

    try:
        return json.loads(http_response)
    except Exception as exception:
        raise CLIException("Could load JSON from '{url}': {error}"
                           .format(url=url, error=str(exception)))

# Read a file from a master / agent node's sandbox.
def read_file(addr, path):
    # It is undocumented, but calling the `/files/read` endpoint
    # and setting `offset=-1` returns the length of the file. We
    # leverage this here to first get the length of the file
    # before reading it. Unfortunately, there is no way to just
    # read the file without first getting its length.
    try:
        endpoint = "files/read?path={path}&offset=-1".format(path=path)
        data = hit_endpoint(addr, endpoint)
    except Exception as exception:
        raise CLIException("Could not read file length '{path}': {error}"
                           .format(path=path, error=str(exception)))

    length = data['offset']
    if length == 0:
        return

    # Read the file in 1024 byte chunks and yield the results to
    # the caller. Reading this way allows us to get real-time
    # updates of the data instead of waiting for the whole file to
    # be downloaded.
    offset = 0
    chunk_size = 1024
    if (length - offset) < chunk_size:
        chunk_size = length - offset

    while True:
        try:
            endpoint = ("files/read?"
                        "path={path}&"
                        "offset={offset}"
                        "&length={length}"
                        .format(path=path,
                                offset=offset,
                                length=chunk_size))

            data = hit_endpoint(addr, endpoint)
        except Exception as exception:
            raise CLIException("Could not read from file '{path}'"
                               " at offset '{offset}: {error}"
                               .format(path=path,
                                       offset=offset,
                                       error=str(exception)))

        yield data['data']

        offset += len(data['data'])
        if offset == length:
            break

        if (length - offset) < chunk_size:
            chunk_size = length - offset

class Table:
    """ Defines a custom table structure for printing to the terminal. """

    # Takes a list of column names
    def __init__(self, columns):
        self.padding = []
        self.table = [columns]
        for column in columns:
            self.padding.append(len(column))

    # Takes a row entry for every column
    def add_row(self, row):
        # Number of entries and columns do not match
        if len(row) != len(self.table[0]):
            return

        # Adjust padding for each column
        for index in range(len(row)):
            if len(row[index]) > self.padding[index]:
                self.padding[index] = len(row[index])

        self.table.append(row)

    def __str__(self):
        table_string = ""
        for r, row in enumerate(self.table):
            for index in range(len(row)):
                entry = row[index]
                table_string += "%s%s" % \
                        (entry, " " * (self.padding[index] - len(entry) + 2))

            if r != len(self.table) - 1:
                table_string += "\n"

        return table_string
