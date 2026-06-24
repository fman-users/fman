from fman.impl.view.resize_cols_to_contents import _get_ideal_column_widths, \
	_resize_column, _distribute_evenly, _distribute_exponentially
from unittest import TestCase

class GetIdealColumnWidthsTest(TestCase):
	def test_one_column_no_change(self):
		self._expect([1], [1], [1], 1)
	def test_one_column_truncated(self):
		self._expect([2], [1], [2], 2)
	def test_one_column_too_large(self):
		self._expect([1], [2], [1], 1)
	def test_two_cols(self):
		self._expect([2, 1], [1, 2], [2, 1], 3)
	def test_truncate_first_col(self):
		self._expect([400, 100], [500, 100], [500, 100], 500, delta_percent=3)
	def test_maximize_window(self):
		self._expect([2, 1], [1, 1], [1, 1], 3)
	def _expect(
		self, result, widths, min_widths, available_width, delta_percent=0
	):
		actual = \
			_get_ideal_column_widths(widths, min_widths, available_width)
		self.assertEqual(len(result), len(actual))
		if delta_percent:
			for r, a in zip(result, actual):
				if delta_percent:
					delta = int(r * delta_percent / 100)
					self.assertLessEqual(r - delta, a)
					self.assertGreaterEqual(r + delta, a)
		else:
			self.assertEqual(result, actual)

class ResizeColumnTest(TestCase):
	def test_enlarge(self):
		self._expect([2, 1, 1], 0, 2, [1, 2, 1], [1, 1, 1])
	def test_shrink(self):
		self._expect([1, 2, 1], 0, 1, [2, 1, 1], [1, 1, 1])
	def test_shrink_below_available_width(self):
		self._expect([1, 1, 2], 0, 1, [2, 1, 2], [1, 1, 2], 4)
	def test_shrink_last_but_one(self):
		self._expect([1, 1, 2], 1, 1, [1, 2, 1], [2, 1, 2])
	def test_enlarge_trims_last_col(self):
		self._expect([2, 1], 0, 2, [1, 2], [1, 1], 3)
	def test_rightalign_last_col(self):
		self._expect([1, 2, 1], 0, 1, [2, 1, 1], [1, 1, 1])
	def test_shrink_respects_available_width_cap(self):
		result = _resize_column(0, 3, [3, 1, 1], [1, 1, 1], 6)
		self.assertLessEqual(sum(result), 6)
	def test_shrink_expansion_does_not_exceed_available(self):
		result = _resize_column(0, 4, [4, 1], [1, 1], 5)
		self.assertLessEqual(sum(result), 5)
	def _expect(
		self, result, col, old_size, widths, min_widths, available_width=None
	):
		if available_width is None:
			available_width = sum(widths)
		actual = _resize_column(
			col, old_size, widths, min_widths, available_width
		)
		self.assertEqual(result, actual)

class DistributeEvenlyTest(TestCase):
	def test_exact_division(self):
		self.assertEqual([5, 5], _distribute_evenly(10, [1, 1]))
	def test_zero_total(self):
		self.assertEqual([0, 0], _distribute_evenly(10, [0, 0]))
	def test_single_proportion(self):
		self.assertEqual([7], _distribute_evenly(7, [3]))
	def test_weighted(self):
		result = _distribute_evenly(100, [3, 1])
		self.assertEqual(100, sum(result))
		self.assertGreater(result[0], result[1])
	def test_zero_width(self):
		self.assertEqual([0, 0], _distribute_evenly(0, [1, 1]))

class DistributeExponentiallyTest(TestCase):
	def test_exact_division(self):
		result = _distribute_exponentially(100, [10, 10])
		self.assertEqual(100, sum(result))
	def test_zero_total(self):
		self.assertEqual([0, 0], _distribute_exponentially(10, [0, 0]))
	def test_larger_proportion_gets_more(self):
		result = _distribute_exponentially(100, [10, 1])
		self.assertGreater(result[0], result[1])
	def test_zero_width(self):
		self.assertEqual([0, 0], _distribute_exponentially(0, [5, 5]))