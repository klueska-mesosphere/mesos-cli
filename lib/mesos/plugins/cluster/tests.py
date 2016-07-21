import os
import sys
import subprocess
import StringIO
import time
import unittest

import main
import mesos.config as config
from mesos.util import hit_endpoint
from mesos.exceptions import CLIException

from mesos.PluginTestBase import PluginTestBase

class Test_ClusterPlugin(PluginTestBase):

    # Returns stdout output of a given function
    def __get_output(self, run, argv):
        stdout = sys.stdout
        sys.stdout = StringIO.StringIO()
        try:
            run(argv)
        except Exception as exception:
            # Need to make sure we fix stdout in case something goes wrong
            sys.stdout = stdout
            raise CLIException("Could not get command output: {error}"
                                            .format(error=exception))

        sys.stdout.seek(0)
        output = sys.stdout.read().strip()
        sys.stdout = stdout
        return output

    # Since this is passed to an external script, I assume the testing is
    # present in the mesos test cases. Is that the correct assumption to take?
    def test_execute(self):
        flags = ["--master=127.0.0.1:5050","--name=cluster-test",
                                         "--command='/bin/bash'"]

        try:
            exec_proc = subprocess.Popen(("exec {path}mesos-execute"
                                          " {flags} > /dev/null 2>&1 ")
                                          .format(flags=' '.join(flags),
                                          path=config.EXECUTABLE_DIR),
                                          shell=True)
        except Exception as exception:
            self.fail("Could not execute task on cluster: {error}"
                                           .format(error=exception))

        time.sleep(1)
        try:
            containers = hit_endpoint('127.0.0.1:5051','/containers')
        except Exception as exception:
            self.fail("Could not get container info: {error}"
                                    .format(error=exception))

        self.assertEquals(len(containers),2)
        exec_proc.kill()
        exec_proc.wait()

    def test_cat(self):
        if not self.setup_success:
            raise unittest.SkipTest("Error setting up cluster in test setup:"
                                    " {log}".format(log=self.error_log))

        cluster = main.Cluster(None)
        # We need the agent id from its /state id as its usefull for assertion
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get agent state info: {error}"
                                    .format(error=exception))

        # We read the stout file from the fs and compare with cat output
        try:
            exec_info = hit_endpoint('127.0.0.1:5051','/containers')
        except Exception as exception:
            self.fail("Could not get /containers from agent: {error}"
                                    .format(error=exception))

        if os.geteuid() == 0:
            work_dir = self.sudo_agent_dir
        else:
            work_dir = self.agent_dir

        file_path = ('{_dir}/slaves/{agent_id}/frameworks/{frame_id}/executors/'
                    '{exec_id}/runs/{cont_id}/{_file}')
        path_stdout = file_path.format(_dir=work_dir,
                                agent_id=agent_state["id"],
                                frame_id=exec_info[0]["framework_id"],
                                exec_id=exec_info[0]["executor_id"],
                                cont_id=exec_info[0]["container_id"],
                                _file='stdout')
        real_output = ""
        try:
            with open(path_stdout, 'r') as f:
                real_output = f.read()
        except Exception as exception:
            self.fail("Could not open stdout file: {error}"
                                  .format(error=exception))

        test_output = ""
        cluster_argv={"--addr" : "127.0.0.1:5050",
                      "<framework-ID>" : exec_info[0]["framework_id"],
                      "<task-ID>" : exec_info[0]["executor_id"],
                      "<file>" : "stdout"}

        try:
            test_output = self.__get_output(cluster.cat,cluster_argv)
        except Exception as exception:
            self.fail("Could not cat file with cluster cat: {error}"
                                            .format(error=exception))

        self.assertEqual(test_output, real_output.strip())

        # Try to cat wrong file name and expect an error
        cluster_argv["<file>"] = "wrongfile"
        with self.assertRaises(Exception) as exception:
            test_output = self.__get_output(cluster.cat,cluster_argv)

        # cat the wrong task id and expect an error
        cluster_argv["<file>"] = "stdout"
        cluster_argv["<task-ID>"] = "-123"
        with self.assertRaises(Exception) as exception:
            test_output = self.__get_output(cluster.cat,cluster_argv)

    def test_ps(self):
        if not self.setup_success:
            raise unittest.SkipTest("Error setting up cluster in test setup:"
                                    " {log}".format(log=self.error_log))

        cluster = main.Cluster(None)
        # We need the /state endpoint as its usefull for assertion
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get agent state info: {error}"
                                    .format(error=exception))

        test_output = ""
        cluster_argv={"--addr" : "127.0.0.1:5050" }
        try:
            test_output = self.__get_output(cluster.ps,cluster_argv)
        except Exception as exception:
            self.fail("Could not perform cluster ps: {error}"
                                        .format(error=exception))
        # Table should have only two entries: header and entry
        ps_table = test_output.split('\n')
        self.assertEqual(len(ps_table), 2)
        # We now check fields for correctness
        row =  ps_table[1].split()
        self.assertEqual(row[0], agent_state['frameworks'][0]['user'])
        self.assertEqual(row[1]+' '+row[2], 'mesos-execute instance')
        self.assertEqual(row[3],
                          agent_state['frameworks'][0]['executors'][0]['id'])
        self.assertEqual(row[4], agent_state['hostname'])
        # If we bring down a task, cluster ps must return empty
        try:
            self.kill_exec()
            self.check_exec_down()
        except Exception as exception:
            self.fail("Could not bring down task: {error}"
                                 .format(error=exception))

        test_output = ""
        cluster_argv={"--addr" : "127.0.0.1:5050" }
        try:
            test_output = self.__get_output(cluster.ps,cluster_argv)
        except Exception as exception:
            self.fail("Could not perform cluster ps: {error}"
                                        .format(error=exception))

        # Table should have only one entry: header
        ps_table = test_output.split('\n')
        self.assertEqual(len(ps_table), 1)
        # Bring back a task for further tests
        try:
            self.launch_exec()
        except Exception as exception:
            self.fail("Could not launch task: {error}"
                                 .format(error=exception))
