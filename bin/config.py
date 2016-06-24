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

# Default IPs for Master / Agent.
MASTER_IP = "127.0.0.1:5050"
AGENT_IP = "127.0.0.1:5051"

# A dictionary from IP's to SSH keys to assist with remote commands
SSH_KEYS = {}

# The builtin plugins.
PLUGINS = [
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "example")
]

# Allow all configuration variables to be updated from a config file.
if os.environ.get('MESOS_CLI_CONFIG_FILE'):
    try:
        with open(os.environ['MESOS_CLI_CONFIG_FILE']) as data_file:
            with json.load(data_file) as config_data:
                if "master_ip" in config_data:
                    if not isinstance(config_data["master_ip"], str):
                        raise CLIException("'master_ip' field must be a string")

                    MASTER_IP = config_data["master_ip"]

                if "agent_ip" in config_data:
                    if not isinstance(config_data["agent_ip"], str):
                        raise CLIException("'agent_ip' field must be a string")

                    AGENT_IP = config_data["agent_ip"]

                if "ssh_keys" in config_data:
                    if not isinstance(config_data["ssh_keys"], dict):
                        raise CLIException("'ssh_keys' field must be an object")

                    SSH_KEYS = config_data["ssh_keys"]

                if "plugins" in config_data:
                    if not isinstance(config_data["plugins"], list):
                        raise CLIException("'plugins' field must be a list")

                    PLUGINS.extend(config_data["plugins"])

    except Exception as exception:
        sys.exit("Unable to parse configuration file '{config}': {error}"
                 .format(config=os.environ.get('MESOS_CLI_CONFIG_FILE'),
                         error=str(exception)))

# Pull in extra plugins from the environment. The `MESOS_CLI_PLUGINS`
# environment variable is a ":" separated list of paths to each
# plugin. All paths must be absolute.
if os.environ.get('MESOS_CLI_PLUGINS'):
    PLUGINS += filter(None, os.environ.get('MESOS_CLI_PLUGINS').split(":"))

# Update the master / agent IPs from the environment.
if os.environ.get('MESOS_CLI_MASTER_IP'):
    MASTER_IP = os.environ.get('MESOS_CLI_MASTER_IP')

if os.environ.get('MESOS_CLI_AGENT_IP'):
    AGENT_IP = os.environ.get('MESOS_CLI_AGENT_IP')

# Update ssh keys from the environment.
if os.environ.get('MESOS_CLI_SSH_KEYS'):
    try:
        SSH_KEYS = json.loads(os.environ.get('MESOS_CLI_SSH_KEYS'))

        if not isinstance(SSH_KEYS, dict):
            raise CLIException("'ssh_keys' field must be an object")

    except Exception as exception:
        sys.exit("Unable to parse 'MESOS_CLI_SSH_KEYS'"
                 " environment variable: {error}"
                 .format(error=str(exception)))
