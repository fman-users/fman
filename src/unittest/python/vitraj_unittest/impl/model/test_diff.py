from vitraj.impl.model.diff import DiffEntry, ComputeDiff
from itertools import chain, combinations
from unittest import TestCase

class ComputeDiffTest(TestCase):
	def test_empty(self):
		self._check_diff([], [], [])
	def test_same(self):
		rows = [self._a, self._b, self._c]
		self._check_diff(rows, rows, [])
	def test_add_into_empty(self):
		rows = [self._a, self._b]
		self._check_diff([], rows, [(-1, -1, 0, rows)])
	def test_insert_before(self):
		base = [self._c]
		extra = [self._a, self._b]
		self._check_diff(base, extra + base, [(-1, -1, 0, extra)])
	def test_insert_after(self):
		base = [self._a]
		extra = [self._b, self._c]
		self._check_diff(base, base + extra, [(-1, -1, 1, extra)])
	def test_insert_between(self):
		self._check_diff(
			[self._a, self._c],
			[self._a, self._b, self._c],
			[(-1, -1, 1, [self._b])]
		)
	def test_update_single_row(self):
		self._check_diff(
			[self._a],
			[self._b],
			[(0, 1, 0, [self._b])]
		)
	def test_reorder_rows(self):
		self._check_diff(
			[self._a, self._b],
			[self._b, self._a],
			[(1, 2, 0, [])]
		)
	def test_powerset_combinations(self, max_num_rows=5):
		for old in _powerset(range(max_num_rows)):
			for new in _powerset(range(max_num_rows)):
				pathify = lambda s: [(str(i), i) for i in s]
				self._check_diff(pathify(old), pathify(new))
	def test_clear(self):
		self._check_diff([self._a, self._b], [], [(0, 2, -1, [])])
	def test_change(self):
		self._check_diff(
			[('a', 0)],
			[('a', 1)],
			[(0, 1, 0, [('a', 1)])]
		)
	def test_move_and_change(self):
		self._check_diff(
			[('a', 1), ('b', 2)],
			[('b', 0), ('a', 1)],
			[(1, 2, 0, []), (0, 1, 0, [('b', 0)])]
		)
	def test_complex(self):
		before = [(0, 0), (1, 1), (2, 2), (3, 3)]
		after = [(3, 3), (1, 4), (0, 5), (2, 6)]
		self._check_diff(before, after)
	def setUp(self):
		super().setUp()
		self._a = ('a', 1)
		self._b = ('b', 2)
		self._c = ('c', 3)
	def _check_diff(self, old, new, expected_diff_tpls=None):
		diff = ComputeDiff(old, new, key_fn=lambda tpl: tpl[0])()
		old_patched = self._apply_diff(diff, old)
		self.assertEqual(
			new, old_patched,
			'Diff %r for %r -> %r is incorrect!' % (diff, old, new)
		)
		if expected_diff_tpls is not None:
			expected_diff = [DiffEntry(*entry) for entry in expected_diff_tpls]
			self.assertEqual(expected_diff, diff)
	def _apply_diff(self, diff, old):
		result = list(old)
		def insert(rows, start):
			for i, row in enumerate(rows):
				result.insert(start + i, row)
		def move(start, end, insert_pt):
			rows = result[start:end]
			remove(start, end)
			insert(rows, insert_pt)
		def update(rows, index):
			result[index : index+len(rows)] = rows
		def remove(start, end):
			del result[start:end]
		for entry in diff:
			entry.apply(insert, move, update, remove)
		return result

class DiffEntryExtendByTest(TestCase):
	def test_insert(self):
		self._check(
			(-1, -1, 0, [1, 2]), (-1, -1, 2, [3]), (-1, -1, 0, [1, 2, 3])
		)
	def test_move_before(self):
		self._check((1, 3, 11, []), (0, 1, 10, []), (0, 3, 10, []))
	def test_move_after(self):
		self._check((5, 7, 1, []), (7, 8, 3, []), (5, 8, 1, []))
	def test_move_before_unjoinable(self):
		self._check((1, 3, 11, []), (0, 1, 5, []))
	def test_move_after_unjoinable(self):
		self._check((5, 7, 1, []), (7, 8, 4, []))
	def test_move_before_affects_second(self):
		self._check((0, 1, 10, []), (1, 2, 11, []))
	def test_second_move_affects_first(self):
		self._check((10, 11, 5, []), (9, 10, 6, []))
	def test_update(self):
		self._check((0, 2, 0, [1, 2]), (2, 3, 2, [3]), (0, 3, 0, [1, 2, 3]))
	def test_remove(self):
		self._check((1, 2, -1, []), (0, 1, -1, []), (0, 2, -1, []))
	def test_remove_followed_by_insert(self):
		self._check((0, 1, -1, []), (-1, -1, 0, [1]), (0, 1, 0, [1]))
	def test_consecutive_moves(self):
		self._check((4, 5, 2, []), (3, 4, 1, []))
	def _check(self, first, second, expected=None):
		first_entry = DiffEntry(*first)
		second_entry = DiffEntry(*second)
		result = first_entry.extend_by(second_entry)
		self.assertEqual(expected is not None, result)
		if expected is not None:
			self.assertEqual(DiffEntry(*expected), first_entry)

def _powerset(iterable):
	s = list(iterable)
	return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))