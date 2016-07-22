import os
import subprocess
import time
import unittest

import config
from mesos.exceptions import CLIException
from mesos.util import hit_endpoint


class PluginTestBase(unittest.TestCase):

    agent_dir = '/tmp/cli-test-agent'
    sudo_agent_dir = '/tmp/sudo-cli-test-agent'
    master_dir = '/tmp/cli-master-test'
    master_proc = None
    agent_proc = None
    exec_proc = None
    setup_success = True
    error_log = ''

    @staticmethod
    def launch_master():
        if PluginTestBase.master_proc is not None:
            raise CLIException("Master node already spawned")

        if not PluginTestBase.setup_success:
            raise CLIException("Previous setup failed, abort...")

        flags = ["--ip=127.0.0.1",
                "--work_dir={_dir}".format(_dir=PluginTestBase.master_dir)]
        try:
            master_proc = subprocess.Popen(("exec {path}mesos-master"
                                            " {flags} > /dev/null 2>&1 ")
                                            .format(flags=' '.join(flags),
                                            path=config.EXECUTABLE_DIR),
                                            shell=True)
        except Exception as exception:
            PluginTestBase.setup_success = False
            raise CLIException("Could not start master node: {error}"
                                                    .format(error=exception))

        PluginTestBase.master_proc = master_proc

    @staticmethod
    def launch_agent():
        if PluginTestBase.agent_proc is not None:
            raise CLIException("Agent node already spawned")

        if not PluginTestBase.setup_success:
            raise CLIException("Previous setup failed, abort...")

        if os.geteuid() == 0:
            work_dir = PluginTestBase.sudo_agent_dir
        else:
            work_dir = PluginTestBase.agent_dir

        flags = ["--master=127.0.0.1:5050",
                "--work_dir={_dir}".format(_dir=work_dir)]
        # If we run test as root we need namespace isolation enabled
        if os.geteuid() == 0:
            flags.append("--isolation=namespaces/pid")
        try:
            agent_proc = subprocess.Popen(("exec {path}mesos-agent"
                                            " {flags} > /dev/null 2>&1 ")
                                            .format(flags=' '.join(flags),
                                            path=config.EXECUTABLE_DIR),
                                            shell=True)
        except Exception as exception:
            PluginTestBase.setup_success = False
            raise CLIException("Could not start agent node: {error}"
                                                    .format(error=exception))

        PluginTestBase.agent_proc = agent_proc

    @staticmethod
    def launch_exec():
        flags = ["--master=127.0.0.1:5050","--name=cluster-test",
                                         "--command='/bin/bash'"]

        try:
            exec_proc = subprocess.Popen(("exec {path}mesos-execute"
                                          " {flags} > /dev/null 2>&1 ")
                                          .format(flags=' '.join(flags),
                                          path=config.EXECUTABLE_DIR),
                                          shell=True)
        except Exception as exception:
            PluginTestBase.setup_success = False
            raise CLIException("Could not execute task on cluster: {error}"
                                                  .format(error=exception))

        PluginTestBase.exec_proc = exec_proc
        time.sleep(1)

    @staticmethod
    def check_stable():
        if PluginTestBase.master_proc is None:
            raise CLIException("No master in cluster!")

        if PluginTestBase.agent_proc is None:
            raise CLIException("No agent in cluster!")

        agent_connected = False
        agents = None
        # We keep a track of time so we dont loop indefinitely
        start_time = time.time()
        timeout = 5
        while not agent_connected:
            time.sleep(0.05)
            try:
                agents = hit_endpoint('127.0.0.1:5050','/slaves')
            except Exception as exception:
                pass

            if agents is not None:
                if len(agents['slaves']) == 1:
                    agent_connected = True
                    continue
            # We've been probing till timeout, things are probably wrong
            if time.time() - start_time > timeout:
                PluginTestBase.setup_success = False
                raise CLIException("Cluster could not stabilize within {sec}"
                                   " seconds".format(sec=str(timeout)))

    @staticmethod
    def check_exec_down():
        container_gone = False
        containers = None
        # We keep a track of time so we dont loop indefinitely
        start_time = time.time()
        timeout = 5
        while not container_gone:
            time.sleep(0.05)
            try:
                containers = hit_endpoint('127.0.0.1:5051','/containers')
            except Exception as exception:
                raise CLIException("Could not get containers: {error}"
                                             .format(error=exception))

            if containers is not None:
                if len(containers) == 0:
                    container_gone = True
                    continue
            # We've been probing till timeout, things are probably wrong
            if time.time() - start_time > timeout:
                raise CLIException("Container did not go down within {sec}"
                                   " seconds".format(sec=str(timeout)))

    @staticmethod
    def kill_master():
        if PluginTestBase.master_proc is None:
            return

        try:
            PluginTestBase.master_proc.kill()
            PluginTestBase.master_proc.wait()
            PluginTestBase.master_proc = None
        except Exception as exception:
            raise CLIException("Could not terminate master node: {error}"
                                                .format(error=exception))

    @staticmethod
    def kill_agent():
        if PluginTestBase.agent_proc is None:
            return

        try:
            PluginTestBase.agent_proc.kill()
            PluginTestBase.agent_proc.wait()
            PluginTestBase.agent_proc = None
        except Exception as exception:
            raise CLIException("Could not terminate agent node: {error}"
                                                .format(error=exception))
    @staticmethod
    def kill_exec():
        if PluginTestBase.exec_proc is None:
            return

        try:
            PluginTestBase.exec_proc.kill()
            PluginTestBase.exec_proc.wait()
            PluginTestBase.exec_proc = None
        except Exception as exception:
            raise CLIException("Could not terminate execute process: {error}"
                                                    .format(error=exception))

    @classmethod
    def setUpClass(cls):
        try:
            cls.launch_master()
        except Exception as exception:
            cls.error_log += (":Failed to set up master node: {error}"
                                           .format(error=exception))

        try:
            cls.launch_agent()
        except Exception as exception:
            cls.error_log += (":Failed to set up agent node: {error}"
                                           .format(error=exception))

        try:
            cls.check_stable()
        except Exception as exception:
            cls.error_log += (":Failed to stabilize cluster: {error}"
                                           .format(error=exception))

        try:
            cls.launch_exec()
        except Exception as exception:
            cls.error_log += (":Failed to launch task on cluster: {error}"
                                                .format(error=exception))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.kill_master()
        except Exception as exception:
            raise CLIException("Failed to tear down master node: {error}"
                                                .format(error=exception))

        try:
            cls.kill_agent()
        except Exception as exception:
            raise CLIException("Failed to tear down agent node: {error}"
                                                .format(error=exception))

        try:
            cls.kill_exec()
        except Exception as exception:
            raise CLIException("Failed to tear down exec proc: {error}"
                                                .format(error=exception))

