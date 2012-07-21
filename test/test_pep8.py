import os
import pep8
import unittest
from collections import defaultdict

from testutils import setup_test_env
setup_test_env()

# Only test these two packages for now:
import softwarecenter

class PackagePep8TestCase(unittest.TestCase):
    maxDiff = None
    packages = [softwarecenter]
    exclude = []

    def message(self, text):
        self.errors.append(text)

    def setUp(self):
        self.errors = []

        class Options(object):
            exclude = self.exclude
            filename = ['*.py']
            testsuite = ''
            doctest = ''
            counters = defaultdict(int)
            messages = {}
            verbose = 0
            quiet = 0
            repeat = True
            show_source = False
            show_pep8 = False
            select = []
            ignore = []
        pep8.options = Options()
        pep8.message = self.message
        Options.physical_checks = pep8.find_checks('physical_line')
        Options.logical_checks = pep8.find_checks('logical_line')

    def test_all_code(self):
        for package in self.packages:
            pep8.input_dir(os.path.dirname(package.__file__))
        self.assertEqual([], self.errors)

if __name__ == "__main__":
    unittest.main()
