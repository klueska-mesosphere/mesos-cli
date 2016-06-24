"""
This file defines the default configuration of the mesos-cli. It also
takes care of updating the default configuration from reading
environment variables or parsing a configuration file.
"""

import os
import sys
import json

from mesos.exceptions import CLIException

# The top-level directory of this project.
PROJECT_DIR = os.path.join(os.path.dirname(__file__), os.pardir)

# The builtin plugins.
PLUGINS = [
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "example")
]

# Allow all configuration variables to be updated from a config file.
if os.environ.get("MESOS_CLI_CONFIG_FILE"):
    try:
        with open(os.environ["MESOS_CLI_CONFIG_FILE"]) as data_file:
            with json.load(data_file) as config_data:
                if "plugins" in config_data:
                    if not isinstance(config_data["plugins"], list):
                        raise CLIException("'plugins' field must be a list")

                    PLUGINS.extend(config_data["plugins"])

    except Exception as exception:
        sys.exit("Unable to parse configuration file '{config}': {error}"
                 .format(config=os.environ.get("MESOS_CLI_CONFIG_FILE"),
                         error=str(exception)))

# Pull in extra plugins from the environment. The `MESOS_CLI_PLUGINS`
# environment variable is a ":" separated list of paths to each
# plugin. All paths must be absolute.
if os.environ.get("MESOS_CLI_PLUGINS"):
    PLUGINS += filter(None, os.environ.get("MESOS_CLI_PLUGINS").split(":"))
