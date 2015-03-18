import unittest

from bridge_oids import Network, asip, int2id


class TestNetwork(unittest.TestCase):
    def setUp(self):
        self.network = Network()

    def test_get_next_ip(self):
        ''' get_next_ip() returns localhost first '''
        self.assertEquals(
            self.network.get_next_ip(),
            '127.0.0.1'
        )

    def test_get_next_ip_twice(self):
        ''' get_next_ip() returns next ip second time '''
        self.network.get_next_ip()
        self.assertEquals(
            self.network.get_next_ip(),
            '127.0.0.2'
        )


class TestUtils(unittest.TestCase):
    def test_int2id(self):
        self.assertEquals(asip(int2id(0, 4)), '0.0.0.0')


if __name__ == '__main__':
    unittest.main()
