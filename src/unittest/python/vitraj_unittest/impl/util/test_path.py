from fbs_runtime.platform import is_windows
from vitraj.impl.util.path import make_absolute, normalize
from os.path import join, expanduser
from unittest import TestCase, skipUnless

class MakeAbsoluteTest(TestCase):
	def test_dot(self):
		self.assertEqual(self.cwd, self._make_absolute('.'))
	def test_home_dir(self, sep='/'):
		self.assertEqual(
			join(expanduser('~'), 'foo', 'test.txt'),
			self._make_absolute(sep.join(['~', 'foo', 'test.txt']))
		)
	@skipUnless(is_windows(), 'Only run this test on Windows')
	def test_home_dir_backslash(self):
		self.test_home_dir(sep='\\')
	@skipUnless(is_windows(), 'Only run this test on Windows')
	def test_c_drive_no_backslash(self):
		self.assertEqual('C:\\', self._make_absolute('C:'))
	def setUp(self):
		super().setUp()
		self.cwd = self._make_path('foo/bar')
	def _make_absolute(self, path):
		return make_absolute(path, self.cwd)
	def _make_path(self, path):
		return join(self._get_root_dir(), *path.split('/'))
	def _get_root_dir(self):
		return 'C:\\' if is_windows() else '/'

class NormalizeTest(TestCase):
	def test_fine(self):
		path = '/home/a/b'
		self.assertEqual(path, normalize(path))
	def test_trailing_dot(self):
		self.assertEqual('a', normalize('a/.'))
	def test_single_dot_between(self):
		self.assertEqual('a/b', normalize('a/./b'))
	def test_trailing_double_dot(self):
		self.assertEqual('', normalize('a/..'))
	def test_single_dot_only(self):
		self.assertEqual('', normalize('.'))
	def test_pardir_of_subdir(self):
		self.assertEqual('a', normalize('a/b/..'))