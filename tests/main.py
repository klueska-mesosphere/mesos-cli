#!.virtualenv/bin/python
import unittest

from mesos.plugins.container.tests import Test_ContainerPlugin
from mesos.plugins.cluster.tests import Test_ClusterPlugin
from mesos.plugins.agent.tests import Test_AgentPlugin

if __name__ == '__main__':
    unittest.main(verbosity=2)
