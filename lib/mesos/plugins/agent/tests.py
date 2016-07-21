import sys
import StringIO
import unittest

import main
from mesos.util import hit_endpoint
from mesos.exceptions import CLIException

from mesos.PluginTestBase import PluginTestBase

class Test_AgentPlugin(PluginTestBase):

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

    # Returns stdout output of a given function
    def __get_output(self, run, argv):
        stdout = sys.stdout
        sys.stdout = StringIO.StringIO()
        try:
            run(argv)
        except Exception as exception:
            # Need to make sure we fix stdout in case something goes wrong
            sys.stdout = stdout
            raise Exception(str(exception))

        sys.stdout.seek(0)
        output = sys.stdout.read().strip()
        sys.stdout = stdout
        return output

    def test_ping(self):
        if not self.setup_success:
            raise unittest.SkipTest("Error setting up cluster in test setup:"
                                    " {log}".format(log=self.error_log))

        agent_plugin = main.Agent(None)
        ping_argv = {"--addr" : "127.0.0.1:5051"}
        output = ""
        try:
            output = self.__get_output(agent_plugin.ping, ping_argv)
        except Exception as exception:
            raise CLIException("Could not get command output: {error}"
                                            .format(error=exception))

        self.assertEqual("Agent Healthy!", output)

    def test_state(self):
        if not self.setup_success:
            raise unittest.SkipTest("Error setting up cluster in test setup:"
                                    " {log}".format(log=self.error_log))

        # We get the entire agent state info to check out parsing againt
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get state from agent node: {error}"
                                    .format(error=exception))

        agent_plugin = main.Agent(None)
        # Now we proced to check if the fields parsed are correct
        agent_argv = {"--addr" : "127.0.0.1:5051",
                      "<field>" : ["master_hostname"]}
        test_response = ""
        try:
            test_response = self.__get_output(agent_plugin.state,agent_argv)
        except Exception as exception:
            self.fail("Could not get master_hostname from agent node: {error}"
                                    .format(error=exception))

        self.assertEqual(test_response[1:-1],agent_state["master_hostname"])
        agent_argv["<field>"] = ["flags.port"]
        try:
            test_response = self.__get_output(agent_plugin.state,agent_argv)
        except Exception as exception:
            self.fail("Could not get flags.port from agent node: {error}"
                                    .format(error=exception))

        self.assertEqual(test_response[1:-1],agent_state["flags"]["port"])

