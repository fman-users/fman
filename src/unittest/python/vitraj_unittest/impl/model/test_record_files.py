from vitraj.impl.model.record_files import Lvl1SortValues, \
	get_moves_for_transforming
from itertools import permutations
from unittest import TestCase

import re

class Lvl1SortValuesTest(TestCase):
	def test_first_removed(self):
		s = Lvl1SortValues(None, None, [0])
		self.assertEqual(1, s._get_original_index(0))
		self.assertEqual(2, s._get_original_index(1))

class GetMovesForTransformingTest(TestCase):
	def test_permutations(self):
		max_str = 'ABCDEF'
		for prefix_len in range(len(max_str) + 1):
			str_ = max_str[:prefix_len]
			for perm in permutations(str_):
				self._test(str_, ''.join(perm))
	def test_space(self):
		self._test('A*BC', 'BA*C')
	def test_move_space(self):
		self._test('*AB', 'AB*')
	def test_complex(self):
		self._test(
			'***F*****D***E***H*B*AC****G**',
			'*A****B***C**DE*****F*G******H'
		)
	def _test(self, curr, goal):
		moves = get_moves_for_transforming(self._parse(curr), self._parse(goal))
		result = self._apply(moves, curr)
		self.assertEqual(goal, result)
	def _parse(self, str_):
		return [(m.start(), m.group(0)) for m in re.finditer('[A-Z]', str_)]
	def _apply(self, moves, to_str):
		result = to_str
		for src, dst in moves:
			cut = result[src]
			result = result[:src] + result[src+1:]
			result = result[:dst] + cut + result[dst:]
		return result