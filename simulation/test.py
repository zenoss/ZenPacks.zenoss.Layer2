import unittest

from bridge_oids import Network, asip, int2id
from snmpwalk_parser import parse_snmpwalklines


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

class TestParser(unittest.TestCase):
    def test_mac_hex(self):
        lines = [
            '.1 '
            '= Hex-STRING: 00 00 0C 07 AC 74 '
        ]
        self.assertEquals(
            len(parse_snmpwalklines(lines)['.1']), 6
        )
    def test_two_line_hex(self):
        lines = [
            '.1.3.6.1.4.1.9.9.683.1.5.0 = Hex-STRING: '
            '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00',

            '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'
        ]
        self.assertEquals(
             parse_snmpwalklines(lines),
             {'.1.3.6.1.4.1.9.9.683.1.5.0': '\x00' * 32}
        )



if __name__ == '__main__':
    unittest.main()
