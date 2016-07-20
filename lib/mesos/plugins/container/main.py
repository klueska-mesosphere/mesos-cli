import ctypes
import curses
import os
import subprocess
import sys
import time

from curses.ascii import isprint
from multiprocessing import Process, Manager
from socket import error as socket_error

import mesos.config as config
import mesos.util

from mesos.exceptions import CLIException
from mesos.plugins import PluginBase
from mesos.util import Table


PLUGIN_CLASS = "Container"
PLUGIN_NAME = "container"

VERSION = "Mesos CLI Container Plugin 1.0"

SHORT_HELP = "Container specific commands for the Mesos CLI"


class Container(PluginBase):
    COMMANDS = {
        "ps" : {
            "arguments" : [],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "List all running containers on an agent",
            "long_help"  : """\
                Lists all running containers on an agent.
                """
        },
        "execute" : {
            "arguments" : ["<container-id>", "<command>..."],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Execute a command within the specified container",
            "long_help"  : """\
                Runs the provided command within the container specified
                by <container-id>. Only supports the Mesos Containerizer.
                """
        },
        "logs" : {
            "arguments" : ["<container-id>"],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT),
                "--no-stdout" : "Do not print stdout",
                "--no-stderr" : "Do not print stderr"
            },
            "short_help" : "Show logs",
            "long_help"  : """\
                Show stdout/stderr logs of a container
                Note: To view logs the --work_dir flag in the agent
                must be an absolute path.
                """
        },
        "top" : {
            "arguments" : ["<container-id>"],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Show running processes of a container",
            "long_help"  : """\
                Show the processes running inside of a container.
                """
        },
        "stats" : {
            "arguments" : ["<container-id>..."],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Show status for one or more Containers",
            "long_help"  : """\
                Show various statistics of running containers.
                Inputting multiple ID's will output the container
                statistics for all those containers.
                """
        },
        "images" : {
            "arguments" : [],
            "flags" : {
                "--addr=<addr>" : "IP and port of agent [default: {ip}:{port}]"
                                  .format(ip=config.AGENT_IP,
                                          port=config.AGENT_PORT)
            },
            "short_help" : "Lists container images",
            "long_help"  : """\
                List images present in the Docker/Appc image store on
                the agent.
                """
        }
    }

    def __setup__(self, cmd, argv):
        self.__verify_linux()

    # Verify that this command is being executed by the root user.
    def __verify_root(self):
        if os.geteuid() != 0:
            raise CLIException("Unable to run command as non-root user:"
                               " Consider running with 'sudo'")

    # Verify that this command is being executed on a Linux machine.
    def __verify_linux(self):
       if sys.platform != "linux2":
            raise CLIException("Unable to run command on non-linux system")

    # Enter a process namespace.
    def __nsenter(self, pid):
        libc = ctypes.CDLL("libc.so.6")
        namespaces = ["ipc", "uts", "net", "pid", "mnt"]

        for namespace in namespaces:
            path = ("/proc/{pid}/ns/{namespace}"
                   .format(pid=pid, namespace=namespace))
            try:
                fd = open(path)
            except Exception as exception:
                raise CLIException("Unable to open file '{path}': {error}"
                                   .format(path=path, error=str(exception)))

            if libc.setns(fd.fileno(), 0) != 0:
                raise CLIException("Failed to mount '{namespace}' namespace"
                                   .format(namespace=namespace))

    # Retreives the full container id from a partial container id.
    def __get_container(self, addr, container_id):
        try:
            containers = mesos.util.hit_endpoint(addr, "/containers")
        except Exception as exception:
            raise CLIException("Could not read from '/containers'"
                               " endpoint: {error}"
                               .format(error=str(exception)))

        try:
            containers = [container for container in containers
                          if container["container_id"].startswith(container_id)]
        except Exception as exception:
            raise CLIException("Unable to index into container matched"
                               " from the '/containers' endpoint: {error}"
                               .format(error=str(exception)))

        if len(containers) == 0:
            raise CLIException("Container ID '{id}' not found"
                               .format(id=container_id))

        if len(containers) > 1:
            raise CLIException("Container ID '{id}' not unique enough"
                               .format(id=container_id))

        return containers[0]

    # Retrieves the PID of a container matched at the `/containers` endpoint.
    def __get_pid(self, container):
        try:
            pid = str(container["status"]["executor_pid"])
        except Exception as exception:
            raise CLIException("Unable to index into container matched"
                               " from the '/containers' endpoint: {error}"
                               .format(error=str(exception)))

        return pid

    # Parse container images from the `storedImages` file.
    # The current implementation of this function parses a binary file
    # as a text file to extract the names of the images from it!
    #
    # TODO(haris): Reimplement this function to parse the
    # `storedImages` file properly.
    def __parse_images_file(self, path):
        try:
            with open(path) as f:
                contents = f.read()
        except Exception as exeption:
            raise CLIException("Error opening file '{path}': {error}"
                               .format(path=path, error=str(exception)))

        result = ""
        previous = False
        lines = contents.split('\n')
        for line in lines:
            line = "".join(c for c in line if isprint(c))
            if '@' in line and not previous:
                result += line.split('@')[0] + "\n"
                previous = True
            else:
                previous = False

        return result

    def ps(self,argv):
        try:
            containers = mesos.util.hit_endpoint(argv["--addr"], "/containers")
        except Exception as exception:
            raise CLIException("Could not read from '/containers'"
                               " endpoint: {error}"
                               .format(error=str(exception)))

        if len(containers) == 0:
            print("There are no containers running on this Agent")
            return

        try:
            table = Table(["Container ID", "Framework ID", "Executor"])
            for container in containers:
                table.add_row([container["container_id"],
                               container["framework_id"],
                               container["executor_id"]])
        except Exception as exception:
            raise CLIException("Unable to build table of containers: {error}"
                               .format(error=str(exception)))

        print(str(table))

    def execute(self, argv, record=False):
        self.__verify_root()

        try:
            container = self.__get_container(argv["--addr"],
                                             argv["<container-id>"])
        except Exception as exception:
            raise CLIException("Could not retrieve container"
                               " '{container}': {error}"
                               .format(container=argv["<container-id>"],
                                       error=str(exception)))

        try:
            pid = self.__get_pid(container)
        except Exception as exception:
            raise CLIException("Could not read the pid of container"
                               " '{container}': {error}"
                               .format(container=container["container_id"],
                                       error=str(exception)))

        try:
            self.__nsenter(pid)
        except Exception as exception:
            raise CLIException("Unable to nsenter on pid '{pid}' for"
                               " container '{container}': {error}"
                               .format(container=container["container_id"],
                                       pid=pid,
                                       error=str(exception)))

        try:
            if record:
                output = subprocess.check_output(argv["<command>"])
                return output
            else:
                subprocess.call(argv["<command>"])
        except Exception as exception:
            raise CLIException("Unable to execute command '{command}' for"
                               " container '{container}': {error}"
                               .format(command=" ".join(argv["<command>"]),
                                       container=container["container_id"],
                                       error=str(exception)))

        # We ignore cases where it is normal
        # to exit a program via <ctrl-C>.
        except KeyboardInterrupt:
            pass

    def logs(self, argv):
        try:
            state = mesos.util.hit_endpoint(argv["--addr"], "/state")
        except Exception as exception:
            raise CLIException("Unable to read from '/state' endpoint: {error}"
                               .format(error=str(exception)))

        try:
            executors = [executor
                         for framework in state["frameworks"]
                         for executor in framework["executors"]
                         if (executor["container"]
                             .startswith(argv["<container-id>"]))]
        except Exception as exception:
            raise CLIException("Unable to index into state matched"
                               " from the '/state' endpoint: {error}"
                               .format(error=str(exception)))

        if len(executors) == 0:
            raise CLIException("Container ID '{id}' not found"
                               .format(id=argv["<container-id>"]))

        if len(executors) > 1:
            raise CLIException("Container ID '{id}' not unique enough"
                               .format(id=argv["<container-id>"]))

        if not argv["--no-stdout"]:
            try:
                stdout_file = os.path.join(executors[0]["directory"], "stdout")
            except Exception as exception:
                raise CLIException("Unable to construct path to"
                                   " 'stdout' file: {error}"
                                   .format(error=str(exception)))
            try:
                for line in mesos.util.read_file(argv["--addr"], stdout_file):
                    print(line)
            except Exception as exception:
                raise CLIException("Unable to read from 'stdout' file: {error}"
                                   .format(error=str(exception)))

        if not argv["--no-stderr"]:
            print("=" * 20)
            try:
                stderr_file = os.path.join(executors[0]["directory"], "stderr")
            except Exception as exception:
                raise CLIException("Unable to construct path to"
                                   " 'stderr' file: {error}"
                                   .format(error=str(exception)))
            try:
                for line in mesos.util.read_file(argv["--addr"], stderr_file):
                    print(line)
            except Exception as exception:
                raise CLIException("Unable to read from 'stderr' file: {error}"
                                   .format(error=str(exception)))

    def top(self, argv):
        argv["<command>"] = ["ps", "-ax"]

        try:
            self.execute(argv)
        except Exception as exception:
            raise CLIException("Unable to execute: {error}"
                               .format(error=str(exception)))

    def stats(self, argv):
        self.__verify_root()

        containers = argv["<container-id>"]

        pids = {}
        for container in containers:
            try:
                container = self.__get_container(argv["--addr"], container)
            except Exception as exception:
                raise CLIException("Could not retrieve container"
                                   " '{container}': {error}"
                                   .format(container=container,
                                           error=str(exception)))

            try:
                pid = self.__get_pid(container)
            except Exception as exception:
                raise CLIException("Unable to get pid of container"
                                   " '{container}': {error}"
                                   .format(container=container["container_id"],
                                           error=str(exception)))

            pids[container["container_id"]] = pid

        manager = Manager()
        process_data = manager.dict()

        # We spawn a new subprocess inside our container `pid`
        # namespace and run `top` to gather system statistics and
        # print the information to the user. We continuously run this
        # process once every second until the user hits <ctrl-C>.
        def get_container_status(process_data):
            try:
                self.__nsenter(process_data["pid"])
            except Exception as exception:
                sys.exit("Error in subprocess:"
                         " Unable to nsenter: {error}"
                         .format(error=str(exception)))
            except KeyboardInterrupt:
                pass

            command = ["top", "-b", "-d1", "-n1"]

            try:
                process_data["output"] = subprocess.check_output(command)
            except Exception as exception:
                sys.exit("Error in subprocess:"
                         " Unable to run 'top': {error}"
                         .format(error=str(exception)))
            except KeyboardInterrupt:
                pass

        try:
            # We use `curses` to display the container statistics.
            try:
                stdscr = curses.initscr()
            except Exception as exception:
                raise CLIException("Unable to initialize curses screen: {error}"
                                   .format(error=str(exception)))

            # Loop until <Ctrl-C> is pressed.
            last_output = ""

            while True:
                output = ""

                for container, pid in pids.iteritems():
                    try:
                        process_data['container'] = container
                        process_data['pid'] = pid
                        process_data["output"] = ""

                        process = Process(target=get_container_status,
                                          args=(process_data,))

                        process.start()
                        process.join()
                    except Exception as exception:
                        raise CLIException("Unable to run subprocess"
                                           " inside container '{container}'"
                                           " for pid '{pid}: {error}"
                                           .format(container=container,
                                                   pid=pid,
                                                   error=str(exception)))

                    if not process_data["output"]:
                        raise CLIException("Unable to obtain output from"
                                           " running subprocess inside"
                                           " container '{container}'"
                                           " for pid '{pid}'"
                                           .format(container=container,
                                                   pid=pid))

                    # Parse relevant information from the top output
                    output += ("====== Container stats for {container} ======\n"
                               .format(container=container))
                    lines = process_data['output'].split('\n')
                    lines.pop(0)
                    for line in lines:
                        if line == '':
                            break
                        else:
                            output += line + "\n"
                    output += "\n\n"

                # Print the output to the `curses` screen.
                try:
                    stdscr.addstr(0, 0, output)
                except Exception as exception:
                    raise CLIException("Unable to add output to the"
                                       " curses screen: {error}"
                                       .format(error=str(exception)))

                try:
                    stdscr.refresh()
                except Exception as exception:
                    raise CLIException("Unable to refresh the"
                                       " curses screen: {error}"
                                       .format(error=str(exception)))

                last_output = output

                # Sleep for 1 second.
                try:
                    time.sleep(1)
                except Exception as exception:
                    raise CLIException("Unable to sleep: {error}"
                                       .format(error=str(exception)))
        except KeyboardInterrupt:
            try:
                curses.endwin()
                os.system("clear")
            except:
                pass

        print(last_output)

    def images(self, argv):
        self.__verify_root()

        try:
            flags = mesos.util.hit_endpoint(argv["--addr"], "/flags")
        except Exception as exception:
            raise CLIException("Unable to read from '/flags' endpoint: {error}"
                               .format(error=str(exception)))

        # List the images in the Docker image store.
        try:
            docker_store = os.path.join(flags["flags"]["docker_store_dir"],
                                        "storedImages")
        except Exception as exception:
            raise CLIException("Unable to construct path to Docker"
                               " 'storedImages' file: {error}"
                               .format(error=str(exception)))

        if os.path.exists(docker_store):
            try:
                output = self.__parse_images_file(docker_store)
            except Exception as exception:
                raise CLIException("Unable to parse 'storedImages' file: "
                                   .format(error=str(exception)))
            print("Docker Image Store:")
            print(output if output else "No images found!")
        else:
            print("No Images present in Docker Store!")

        # List the images in the Appc image store.
        try:
            docker_store = os.path.join(flags["flags"]["appc_store_dir"],
                                        "storedImages")
        except Exception as exception:
            raise CLIException("Unable to construct path to Appc"
                               " 'storedImages' file: {error}"
                               .format(error=str(exception)))

        if os.path.exists(docker_store):
            try:
                output = self.__parse_images_file(docker_store)
            except Exception as exception:
                raise CLIException("Unable to parse 'storedImages' file: "
                                   .format(error=str(exception)))
            print("Appc Image Store:")
            print(output if output else "No images found!")
        else:
            print("No Images present in Appc Store!")
