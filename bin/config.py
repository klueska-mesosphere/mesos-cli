"""
This file defines the default configuration of the mesos-cli. It also
takes care of updating the default configuration from reading
environment variables or parsing a configuration file.
"""

import os
import sys
import json
import subprocess

from mesos.exceptions import CLIException

# The top-level directory of this project.
PROJECT_DIR = os.path.join(os.path.dirname(__file__), os.pardir)

# Default IP for the agent.
AGENT_IP = "127.0.0.1"
AGENT_PORT = "5051"

# The builtin plugins.
PLUGINS = [
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "example")
]

# Allow all configuration variables to be updated from a config file.
if os.environ.get("MESOS_CLI_CONFIG_FILE"):
    try:
        with open(os.environ["MESOS_CLI_CONFIG_FILE"]) as data_file:
            try:
                config_data = json.load(data_file)
            except Exception as exception:
                raise CLIException("Error loading config file as json: {error}"
                                                    .format(error=exception))

            if "agent_ip" in config_data:
                if not isinstance(config_data["agent_ip"], basestring):
                    raise CLIException("'agent_ip' field must be a string")

                AGENT_IP = config_data["agent_ip"]

            if "agent_port" in config_data:
                if not isinstance(config_data["agent_port"], basestring):
                    raise CLIException("'agent_port' "
                                       "field must be a string")

                AGENT_PORT = config_data["agent_port"]

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

# Override the agent IP and port from the environment. We use the
# standard Mesos environment variables for `MESOS_IP`,
# `MESOS_IP_DISCOVERY_COMMAND` and `MESOS_PORT` to get the agent IP
# and port. We also provide our own `MESOS_CLI_AGENT_IP` and
# `MESOS_CLI_AGENT_PORT` environment variables as a way of overriding
# the others.
if os.environ.get("MESOS_IP_DISCOVERY_COMMAND"):
    try:
        AGENT_IP = subprocess.check_output(
            os.environ.get("MESOS_IP_DISCOVERY_COMMAND"),
            shell=True).strip()
    except Exception as exception:
        sys.exit("Unable to run MESOS_IP_DISCOVERY_COMMAND: {error}"
                 .format(error=str(exception)))

if os.environ.get("MESOS_IP"):
    AGENT_IP = os.environ.get("MESOS_IP").strip()

if os.environ.get("MESOS_CLI_AGENT_IP"):
    AGENT_IP = os.environ.get("MESOS_CLI_AGENT_IP").strip()

if os.environ.get("MESOS_PORT"):
    AGENT_PORT = os.environ.get("MESOS_PORT").strip()

if os.environ.get("MESOS_CLI_AGENT_PORT"):
    AGENT_PORT = os.environ.get("MESOS_CLI_AGENT_PORT").strip()
