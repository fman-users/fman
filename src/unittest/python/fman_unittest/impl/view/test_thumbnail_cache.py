from fman.impl.view.thumbnails import format_human_size
from unittest import TestCase


class FormatHumanSizeTest(TestCase):

	def test_bytes(self):
		self.assertEqual('0 B', format_human_size(0))
		self.assertEqual('512 B', format_human_size(512))

	def test_kilobytes(self):
		self.assertEqual('1.0 KB', format_human_size(1024))
		self.assertEqual('1.5 KB', format_human_size(1536))

	def test_megabytes(self):
		self.assertEqual('4.2 MB', format_human_size(4_404_019))  # 4.2 * 1024^2

	def test_gigabytes(self):
		self.assertEqual('2.3 GB', format_human_size(2_469_606_195))

	def test_rounds_to_one_decimal(self):
		self.assertEqual('1.0 MB', format_human_size(1024 * 1024))
