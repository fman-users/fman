from fbs_runtime.platform import is_windows
from vitraj.impl.util.qt import as_qurl, from_qurl
from unittest import TestCase

class AsFromQurlTest(TestCase):
	def test_file_url(self):
		url = 'file://C:/test' if is_windows() else 'file:///test'
		self._check(url)
	def test_zip_url(self):
		url = 'zip://C:/test.zip' if is_windows() else 'zip:///test.zip'
		self._check(url)
	def test_ftp(self):
		self._check('ftp://user:pass@123.45.67.89/dir')
	def test_space_in_file_url(self):
		root = 'file://C:/test' if is_windows() else 'file:///test'
		self._check(root + '/a and b.txt')
	def test_space_in_ftp_url(self):
		self._check('ftp:///a and b.txt')
	def test_space_in_other_url(self):
		self._check('other:///a and b.txt')
	def _check(self, url):
		self.assertEqual(url, from_qurl(as_qurl(url)))