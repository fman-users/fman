from vitraj import ApplicationCommand, DirectoryPaneCommand, DirectoryPaneListener
from vitraj.fs import FileSystem, Column

class TestCommand(ApplicationCommand):
	RAN = False
	def __call__(self, ran):
		self.__class__.RAN = ran

class CommandRaisingError(DirectoryPaneCommand):
	def __call__(self):
		raise ValueError()

class ListenerRaisingError(DirectoryPaneListener):
	def on_path_changed(self):
		raise ValueError()
	def on_doubleclicked(self, file_url):
		raise ValueError()
	def on_name_edited(self, file_url, new_name):
		raise ValueError()

class TestFileSystem(FileSystem):

	scheme = 'test://'

class TestColumn(Column):

	display_name = 'Test'

class NonexistentColumnFileSystem(FileSystem):

	scheme = 'nonexistent-col://'

	def get_default_columns(self, path):
		return 'Nonexistent',

class NoIterdirFileSystem(FileSystem):

	scheme = 'noiterdir://'

	def get_default_columns(self, path):
		return 'simple_plugin.TestColumn',