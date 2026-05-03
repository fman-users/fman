from fman.impl.model import SortedFileSystemModel
from unittest import TestCase

class MaxVisitedCapTest(TestCase):
	def test_cap_value(self):
		self.assertEqual(512, SortedFileSystemModel._MAX_VISITED)
	def test_set_clears_when_over_cap(self):
		visited = set()
		for i in range(513):
			visited.add('url://%d' % i)
			if len(visited) > 512:
				visited.clear()
				visited.add('url://%d' % i)
		self.assertEqual(1, len(visited))
		self.assertIn('url://512', visited)
