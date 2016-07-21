import datetime
import itertools
import os
import sys
import subprocess
from socket import error as socket_error

import mesos.config as config
import mesos.util

from mesos.exceptions import CLIException
from mesos.plugins import PluginBase
from mesos.util import Table

PLUGIN_CLASS = "Cluster"
PLUGIN_NAME = "cluster"

VERSION = "Mesos CLI Cluster Plugin 1.0"

SHORT_HELP = "Cluster specific commands for the Mesos CLI"


class Cluster(PluginBase):

    COMMANDS = {
        "execute" : {
            "external" : True,
            "short_help" : "Execute a task on the cluster.",
            "long_help"  :
                """
                Execute a task on the Mesos Cluster. A wrapper script over
                mesos-execute. Arguments and Flag information same as
                mesos-execute.
                """
        },
        "ps" : {
            "arguments" : [],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.MASTER_IP,
                                          port=config.MASTER_PORT)
            },
            "short_help" : "Display info for agents",
            "long_help"  :
                """
                Displays framework and task related statistics regarding the
                mesos cluster. Equivalent to mesos-ps.
                """
        },
        "cat" : {
            "arguments" : ["<framework-ID>", "<task-ID>", "<file>"],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.MASTER_IP,
                                          port=config.MASTER_PORT)
            },
            "short_help" : "Display file within task sandbox",
            "long_help"  :
                """
                Displays contents of a file within a task sandbox.
                Equivalent to mesos-cat
                """
        }
    }


    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    def execute(self,argv):
        exec_dir = "{path}mesos-execute".format(path=config.EXECUTABLE_DIR)
        try:
            subprocess.call([exec_dir] + argv["<args>"])
        except Exception as exception:
            raise CLIException("Could note call mesos-execute: {error}"
                                            .format(error=exception))

    # Helper for formatting the CPU column for a task.
    def __cpus(self, task, statistics):
        if statistics is None:
            return ""

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        cpus_limit = None
        for entry in statistics:
            if (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id):
                cpus_limit = entry['statistics'].get('cpus_limit', None)
                break

        if cpus_limit is not None:
            return str(cpus_limit)

        return ""

    # Helper for formatting the MEM column for a task.
    def __mem(self, task, statistics):
        if statistics is None:
            return ""

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        mem_rss_bytes = None
        mem_limit_bytes = None
        for entry in statistics:
            if (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id):
                mem_rss_bytes = entry['statistics'].get('mem_rss_bytes', None)
                mem_limit_bytes = entry['statistics'].get('mem_limit_bytes'
                        , None)
                break

        if mem_rss_bytes is not None and mem_limit_bytes is not None:
            MB = 1024.0 * 1024.0
            return ( '{usage}/{limit}'
                    .format(usage = self.__data_size(mem_rss_bytes, "%.1f"),
                            limit = self.__data_size(mem_limit_bytes, "%.1f")) )

        return ""

    def __data_size(self, bytes, format):
        # Ensure bytes is treated as floating point for the math below.
        bytes = float(bytes)
        if bytes < 1024:
            return (format % bytes) + ' B'
        elif bytes < (1024 * 1024):
            return (format % (bytes / 1024)) + ' KB'
        elif bytes < (1024 * 1024 * 1024):
            return (format % (bytes / (1024 * 1024))) + ' MB'
        else:
            return (format % (bytes / (1024 * 1024 * 1024))) + ' GB'

    # Helper for formatting the TIME column for a task.
    def __time(self, task, statistics):
        if statistics is None:
            return ""

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        cpus_time_secs = None
        cpus_system_time_secs = None
        cpus_user_time_secs = None
        for entry in statistics:
            if ( (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id) ):
                cpus_system_time_secs = ( entry['statistics']
                        .get('cpus_system_time_secs', None) )
                cpus_user_time_secs = ( entry['statistics']
                        .get('cpus_user_time_secs', None) )
                break

        if ( cpus_system_time_secs is not None
                and cpus_user_time_secs is not None ):
            return (datetime.datetime
                    .utcfromtimestamp(cpus_system_time_secs
                            + cpus_user_time_secs)
                    .strftime('%H:%M:%S.%f'))

        return ""

    def ps(self,argv):
        try:
            state = mesos.util.hit_endpoint(argv["--addr"], "/state")
        except Exception as exception:
            raise CLIException("Could not read from '/state'"
                               " endpoint: {error}"
                               .format(error=str(exception)))
        # Collect all the active frameworks and tasks by agent ID.
        active = {}
        for framework in state['frameworks']:
            for task in framework['tasks']:
                if task['slave_id'] not in active.keys():
                    active[task['slave_id']] = []
                active[task['slave_id']].append((framework, task))

        table = Table(['USER','FRAMEWORK','TASK','AGENT','MEM','TIME',
                        'CPU (allocated)'])

        # Grab all the agents with active tasks.
        agents = [agent for agent in state['slaves'] if agent['id'] in active]
        # Go through each agents and create the table
        # We use helper functions defined above for format help
        for agent in agents:
            try:
                statistics = mesos.util.hit_endpoint(agent["pid"].split("@")[1],
                                                "/monitor/statistics")
            except Exception as exception:
                print ("Could not read from '/statistics' endpoint from agent"
                        " at {ip}: {error}"
                        .format(error=str(exception),
                                ip=agent["pid"].split("@")[1]))
                continue
            try:
                for framework, task in active[agent['id']]:
                    row = [framework['user'], framework['name'], task['name'],
                            agent['hostname'],
                            self.__mem(task,statistics),
                            self.__time(task, statistics),
                            self.__cpus(task, statistics)]
                    table.add_row(row)
            except Exception as exception:
                raise CLIException("Unable to build table for stats: {error}"
                                   .format(error=str(exception)))

        print (str(table))

    def read(self, agent, task, file):
        framework_id = task['framework_id']
        executor_id = task['executor_id']
        agent_ip = agent['pid'].split('@')[1]
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        # Get 'state' json  to determine the executor directory.
        try:
            state = mesos.util.hit_endpoint(agent_ip,"/state")
        except Exception as exception:
            raise CLIException("Unable to read from '/state' endpoint: {error}"
                               .format(error=str(exception)))

        directory = None
        for framework in itertools.chain(state['frameworks'],
                                         state['completed_frameworks']):
            if framework['id'] == framework_id:
                for executor in itertools.chain(framework['executors'],
                                            framework['completed_executors']):
                    if executor['id'] == executor_id:
                        directory = executor['directory']
                        break

        if directory is None:
            raise CLIException("Could not get executor directory!")

        path = os.path.join(directory, file)
        try:
            for data in mesos.util.read_file(agent_ip, path):
                print (data)
        except Exception as exception:
            raise CLIException("Error retrieving file from agent: {error}"
                                                .format(error=exception))

    def cat(self,argv):
        # Get the master's state.
        try:
            state = mesos.util.hit_endpoint(argv["--addr"], "/state")
        except Exception as exception:
            raise CLIException("Could not read from '/state'"
                               " endpoint: {error}"
                               .format(error=str(exception)))

        # Build a dict from agent ID to agents.
        agents = {}
        for agent in state['slaves']:
            agents[agent['id']] = agent

        for framework in itertools.chain(state['frameworks'],
                                         state['completed_frameworks']):
            if framework['id'] == argv["<framework-ID>"]:
                for task in itertools.chain(framework['tasks'],
                                            framework['completed_tasks']):
                    if (task['id'] == argv["<task-ID>"]):
                        try:
                            self.read(agents[task['slave_id']], task,
                                      argv['<file>'])
                        except Exception as exception:
                            raise CLIException("Error in file cat: {error}"
                                                     .format(error=exception))
                        return

        raise CLIException("Task not found!")







