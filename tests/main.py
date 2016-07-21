#!.virtualenv/bin/python
import unittest

from mesos.plugins.container.tests import Test_ContainerPlugin
from mesos.plugins.cluster.tests import Test_ClusterPlugin

if __name__ == '__main__':
    unittest.main(verbosity=2)
