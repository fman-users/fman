from vitraj import ApplicationCommand, DirectoryPaneCommand
from vitraj.fs import FileSystem, Column
from vitraj.impl.plugins.plugin import Plugin
from vitraj.impl.util import filenotfounderror
from vitraj.impl.util.qt.thread import run_in_main_thread
from PyQt5.QtCore import Qt

class BuiltinPlugin(Plugin):
	def __init__(
		self, tour_controller, tutorial_factory, cleanupguide_factory,
		*super_args
	):
		super().__init__(*super_args)

		# We need to define the command classes here so we get access to the
		# scoped variables tour_controller, *_factory. Creating a factory via
		# lambda: ... would not work because fman's current implementation of
		# commands requires them to be actual classes, not lambdas.

		class Tutorial(TourCommand):
			def __init__(self, pane):
				super().__init__(pane, tour_controller, tutorial_factory)

		class CleanupGuide(TourCommand):
			def __init__(self, pane):
				super().__init__(pane, tour_controller, cleanupguide_factory)

		self._register_directory_pane_command(Tutorial)
		self._register_directory_pane_command(CleanupGuide)
		self._register_application_command(ToggleFullscreen)
		self._register_file_system(NullFileSystem)
		self._register_column(NullColumn)
	@property
	def name(self):
		return 'Builtin'

class TourCommand(DirectoryPaneCommand):
	def __init__(self, pane, controller, tour_factory):
		super().__init__(pane)
		self._controller = controller
		self._tour_factory = tour_factory
	def __call__(self, step=0):
		self._controller.start(self._tour_factory(self.pane), step)

class ToggleFullscreen(ApplicationCommand):
	@run_in_main_thread
	def __call__(self):
		w = self.window._widget
		w.setWindowState(w.windowState() ^ Qt.WindowFullScreen)

class NullFileSystem(FileSystem):

	scheme = 'null://'

	def get_default_columns(self, path):
		return NullColumn.get_qualified_name(),
	def iterdir(self, path):
		return []
	def is_dir(self, existing_path):
		if not existing_path:
			return True
		raise filenotfounderror(self.scheme + existing_path)
	def exists(self, path):
		return not path

class NullColumn(Column):

	display_name = 'null'

	def get_str(self, url):
		return ''
	def get_sort_value(self, url, is_ascending):
		return None