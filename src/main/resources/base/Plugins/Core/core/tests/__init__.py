from core import LocalFileSystem
from vitraj import Task
from vitraj.fs import FileSystem
from vitraj.url import splitscheme, basename

class StubUI:
	def __init__(self, test_case):
		self._expected_alerts = []
		self._expected_prompts = []
		self._test_case = test_case
	def expect_alert(self, args, answer):
		self._expected_alerts.append((args, answer))
	def expect_prompt(self, args, answer):
		self._expected_prompts.append((args, answer))
	def verify_expected_dialogs_were_shown(self):
		self._test_case.assertEqual(
			[], self._expected_alerts, 'Did not receive all expected alerts.'
		)
		self._test_case.assertEqual(
			[], self._expected_prompts, 'Did not receive all expected prompts.'
		)
	def show_alert(self, *args, **_):
		if not self._expected_alerts:
			self._test_case.fail('Unexpected alert: %r' % args[0])
			return
		expected_args, answer = self._expected_alerts.pop(0)
		self._test_case.assertEqual(expected_args, args, "Wrong alert")
		return answer
	def show_prompt(self, *args, **_):
		if not self._expected_prompts:
			self._test_case.fail('Unexpected prompt: %r' % args[0])
			return
		expected_args, answer = self._expected_prompts.pop(0)
		self._test_case.assertEqual(expected_args, args, "Wrong prompt")
		return answer
	def show_status_message(self, _):
		pass
	def clear_status_message(self):
		pass

class StubFS(FileSystem):
	def __init__(self, backend=None):
		if backend is None:
			backend = LocalFileSystem()
		super().__init__()
		self._backends = {backend.scheme: backend}
	def add_child(self, backend):
		self._backends[backend.scheme] = backend
	def is_dir(self, url):
		scheme, path = splitscheme(url)
		return self._backends[scheme].is_dir(path)
	def exists(self, url):
		scheme, path = splitscheme(url)
		return self._backends[scheme].exists(path)
	def samefile(self, url1, url2):
		scheme1, path1 = splitscheme(url1)
		scheme2, path2 = splitscheme(url2)
		if scheme1 != scheme2:
			return False
		return self._backends[scheme1].samefile(path1, path2)
	def iterdir(self, url):
		scheme, path = splitscheme(url)
		return self._backends[scheme].iterdir(path)
	def makedirs(self, url, exist_ok=False):
		scheme, path = splitscheme(url)
		self._backends[scheme].makedirs(path, exist_ok=exist_ok)
	def copy(self, src_url, dst_url):
		scheme = splitscheme(src_url)[0]
		self._backends[scheme].copy(src_url, dst_url)
	def delete(self, url):
		scheme, path = splitscheme(url)
		self._backends[scheme].delete(path)
	def move(self, src_url, dst_url):
		scheme = splitscheme(src_url)[0]
		self._backends[scheme].move(src_url, dst_url)
	def touch(self, url):
		scheme, path = splitscheme(url)
		self._backends[scheme].touch(path)
	def mkdir(self, url):
		scheme, path = splitscheme(url)
		self._backends[scheme].mkdir(path)
	def query(self, url, fs_method_name):
		scheme, path = splitscheme(url)
		return getattr(self._backends[scheme], fs_method_name)(path)