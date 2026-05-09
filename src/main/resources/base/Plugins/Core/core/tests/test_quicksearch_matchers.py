from core.quicksearch_matchers import contains_chars_after_separator, \
	contains_chars, contains_substring
from unittest import TestCase

class ContainsCharsAfterSeparatorTest(TestCase):
	def test_simple(self):
		self.assertEqual(
			[0, 5], self.find_chars_after_space('copy paths', 'cp')
		)
	def test_chars_in_first_and_second_part(self):
		self.assertEqual(
			[0, 1, 2], self.find_chars_after_space('copy paths', 'cop')
		)
	def test_no_match(self):
		self.assertIsNone(self.find_chars_after_space('copy paths', 'cd'))
	def test_full_word_match(self):
		self.assertEqual(
			[0, 1, 2, 3, 5],
			self.find_chars_after_space('copy paths', 'copyp')
		)
	def test_prefix_match(self):
		self.assertEqual(
			[0, 1],
			self.find_chars_after_space('column count', 'co')
		)
	def setUp(self):
		super().setUp()
		self.find_chars_after_space = contains_chars_after_separator(' ')

class ContainsCharsTest(TestCase):
	def test_simple_match(self):
		self.assertEqual([0, 1, 2], contains_chars('abc', 'abc'))
	def test_sparse_match(self):
		self.assertEqual([0, 2], contains_chars('abc', 'ac'))
	def test_no_match(self):
		self.assertIsNone(contains_chars('abc', 'z'))
	def test_case_insensitive(self):
		self.assertEqual([0, 1, 2], contains_chars('ABC', 'abc'))
	def test_case_insensitive_query_upper(self):
		self.assertEqual([0, 1, 2], contains_chars('abc', 'ABC'))
	def test_case_insensitive_mixed(self):
		self.assertEqual([0, 2], contains_chars('AbC', 'ac'))
	def test_empty_query(self):
		self.assertEqual([], contains_chars('abc', ''))

class ContainsSubstringTest(TestCase):
	def test_simple_match(self):
		self.assertEqual([1, 2, 3], contains_substring('abcd', 'bcd'))
	def test_no_match(self):
		self.assertIsNone(contains_substring('abc', 'xyz'))
	def test_case_insensitive(self):
		self.assertEqual([0, 1, 2], contains_substring('ABC', 'abc'))
	def test_case_insensitive_query_upper(self):
		self.assertEqual([0, 1, 2], contains_substring('abc', 'ABC'))
	def test_case_insensitive_mixed(self):
		self.assertEqual([1, 2], contains_substring('aBc', 'BC'))
	def test_empty_query(self):
		self.assertEqual([], contains_substring('abc', ''))