from vitraj.impl.view.gallery import truncate_filename
from unittest import TestCase


class TruncateFilenameTest(TestCase):
	# `truncate_filename(name, max_chars)` — both args drop the extension
	# externally; this function works on a pre-stripped name.
	# Rule: first 3 chars always visible. Last 5 preferred when room.

	def test_short_name_fits_unchanged(self):
		self.assertEqual('report', truncate_filename('report', 10))

	def test_exact_fit(self):
		self.assertEqual('report', truncate_filename('report', 6))

	def test_empty_name(self):
		self.assertEqual('', truncate_filename('', 10))

	def test_name_shorter_than_three(self):
		self.assertEqual('ab', truncate_filename('ab', 10))

	def test_name_shorter_than_three_with_tight_budget(self):
		self.assertEqual('ab', truncate_filename('ab', 2))

	def test_truncates_to_first3_ellipsis_last5(self):
		self.assertEqual(
			'IMG…final',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 9
			)
		)

	def test_drops_suffix_when_first3_plus_ellipsis_plus_last5_too_wide(self):
		self.assertEqual(
			'IMG…',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 4
			)
		)

	def test_first3_always_wins_even_with_zero_budget(self):
		self.assertEqual(
			'IMG…',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 0
			)
		)

	def test_just_over_threshold(self):
		self.assertEqual('abc…ghijk', truncate_filename('abcdefghijk', 9))

	def test_eight_char_name_fits_at_eight(self):
		self.assertEqual('abcdefgh', truncate_filename('abcdefgh', 8))
