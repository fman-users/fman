from vitraj.impl.util.css import parse_css, Rule, Declaration
from unittest import TestCase

class ParseCSSTest(TestCase):
	def test_parse_css(self):
		self.maxDiff = None
		self.assertEqual([
			Rule(['*'], [Declaration('font-size', '1pt')]),
			Rule(['.a'], [Declaration('font-size', '2pt')]),
			Rule(['.a', '.b'], [Declaration('font-size', '3pt')]),
		], parse_css(_TEST_CSS))

_TEST_CSS = \
b"""* {
	font-size: 1pt;
}

.a {
	font-size: 2pt;
}

.a, .b {
	font-size: 3pt;
}"""