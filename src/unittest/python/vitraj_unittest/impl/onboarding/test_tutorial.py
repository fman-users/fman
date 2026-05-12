from fbs_runtime.platform import is_windows
from vitraj.impl.onboarding.tutorial import _get_navigation_steps
from vitraj.url import as_url, basename, dirname, as_human_readable, join
from pathlib import PurePath
from unittest import skipIf, TestCase

class GetNavigationStepsTest(TestCase):
	def test_self(self):
		self._expect([], self._root, self._root)
	def test_sub_dir(self):
		self._expect(
			[('open', basename(dirname(self._root))),
			 ('open', basename(self._root))],
			self._root, dirname(dirname(self._root))
		)
	def test_go_up(self):
		self._expect(
			[('go up', ''), ('open', 'util')],
			join(dirname(self._root), 'util'), self._root
		)
	def test_wrong_scheme(self):
		if is_windows():
			root_drive = PurePath(as_human_readable(self._root)).anchor
		else:
			root_drive = '/'

		self._expect(
			[('go to', root_drive), ('open', 'test')],
			join(as_url(root_drive), 'test'), 'null://'
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_switch_drives(self):
		self._expect(
			[('show drives', ''), ('open', 'D:'), ('open', '64Bit')],
			as_url(r'D:\64Bit'), as_url(r'C:\Users\Michael')
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_start_from_drives(self):
		self._expect(
			[('open', 'D:'), ('open', '64Bit')],
			as_url(r'D:\64Bit'), 'drives://'
		)
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_network_share(self):
		from core.fs.local.windows.drives import DrivesFileSystem
		self._expect(
			[('show drives', ''), ('open', DrivesFileSystem.NETWORK),
			 ('open', 'SERVER'), ('open', 'Folder')],
			as_url(r'\\SERVER\Folder'), as_url(r'C:\Users\Michael')
		)
		self._expect(
			[('open', 'SERVER'), ('open', 'Folder')],
			as_url(r'\\SERVER\Folder'), 'network://'
		)
		# Say the user accidentally opened the wrong server:
		self._expect(
			[('go up', ''), ('open', 'B'), ('open', 'Folder')],
			as_url(r'\\B\Folder'), 'network://A'
		)
	def test_hidden_directory(self):
		dst_url = self._root
		src_url = dirname(dst_url)
		dir_name = basename(dst_url)
		self._expect(
			[('toggle hidden files', dir_name), ('open', dir_name)],
			dst_url, src_url,
			is_hidden=lambda url: True, showing_hidden_files=False
		)
	def setUp(self):
		super().setUp()
		self._root = dirname(as_url(__file__))
	def _expect(self, result, dst_url, src_url, **kwargs):
		actual = _get_navigation_steps(dst_url, src_url, **kwargs)
		self.assertEqual(result, actual)