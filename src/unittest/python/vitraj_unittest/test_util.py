from fbs_runtime.platform import is_windows
from vitraj.impl.util import is_below_dir
from os.path import join
from unittest import TestCase, skipIf

class IsBelowDirTest(TestCase):
	def test_direct_subdir(self):
		self.assertTrue(is_below_dir(join(self.root, 'subdir'), self.root))
	def test_self(self):
		self.assertFalse(is_below_dir(self.root, self.root))
	def test_nested_subdir(self):
		nested = join(self.root, 'subdir', 'nested')
		self.assertTrue(is_below_dir(nested, self.root))
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_different_drive_windows(self):
		self.assertFalse(is_below_dir(r'c:\Dir\Subdir', r'D:\Dir'))
	def setUp(self):
		self.root = r'C:\Dir' if is_windows() else '/Dir'