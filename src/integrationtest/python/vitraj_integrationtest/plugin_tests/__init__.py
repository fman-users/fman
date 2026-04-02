from vitraj import PLATFORM, Window, DirectoryPane
from vitraj.impl.plugins import PluginSupport, SETTINGS_PLUGIN_NAME, PluginFactory
from vitraj.impl.plugins.command_registry import PaneCommandRegistry, \
	ApplicationCommandRegistry
from vitraj.impl.plugins.config import Config
from vitraj.impl.plugins.context_menu import ContextMenuProvider
from vitraj.impl.plugins.key_bindings import KeyBindings
from vitraj.impl.plugins.mother_fs import MotherFileSystem
from vitraj_integrationtest import get_resource
from vitraj_integrationtest.impl.plugins import StubCommandCallback, StubTheme, \
	StubFontDatabase, StubDirectoryPaneWidget
from vitraj_unittest.impl.plugins import StubErrorHandler
from os import mkdir
from os.path import join
from shutil import rmtree, copytree
from tempfile import mkdtemp
from unittest import TestCase

class PluginTest(TestCase):
	def setUp(self):
		self._shipped_plugins = mkdtemp()
		self._thirdparty_plugins = mkdtemp()
		self._user_plugins = mkdtemp()
		self._settings_plugin = join(self._user_plugins, SETTINGS_PLUGIN_NAME)
		mkdir(self._settings_plugin)
		self._shipped_plugin = join(self._shipped_plugins, 'Shipped')
		mkdir(self._shipped_plugin)
		self._thirdparty_plugin = \
			join(self._thirdparty_plugins, 'Simple Plugin')
		src_dir = get_resource('Simple Plugin')
		copytree(src_dir, self._thirdparty_plugin)
		config = Config(PLATFORM)
		self._error_handler = StubErrorHandler()
		self._command_callback = StubCommandCallback()
		key_bindings = KeyBindings()
		self._mother_fs = MotherFileSystem(None)
		self._panecmd_registry = \
			PaneCommandRegistry(self._error_handler, self._command_callback)
		self._window = Window(None, self._panecmd_registry)
		self._appcmd_registry = ApplicationCommandRegistry(
			self._window, self._error_handler, self._command_callback
		)
		theme = StubTheme()
		font_db = StubFontDatabase()
		cm_provider = ContextMenuProvider(
			self._panecmd_registry, self._appcmd_registry, key_bindings
		)
		plugin_factory = PluginFactory(
			config, theme, font_db, self._error_handler, self._appcmd_registry,
			self._panecmd_registry, key_bindings, cm_provider, self._mother_fs,
			self._window
		)
		self._plugin_support = PluginSupport(
			plugin_factory, self._appcmd_registry, key_bindings, cm_provider,
			config
		)
		self._plugin_support.load_plugin(self._shipped_plugin)
		self._plugin_support.load_plugin(self._thirdparty_plugin)
		self._plugin_support.load_plugin(self._settings_plugin)
		left_pane = StubDirectoryPaneWidget(self._mother_fs)
		self._left_pane = \
			DirectoryPane(self._window, left_pane, self._panecmd_registry)
		right_pane = StubDirectoryPaneWidget(self._mother_fs)
		self._right_pane = \
			DirectoryPane(self._window, right_pane, self._panecmd_registry)
		self._plugin_support.register_pane(self._left_pane)
		self._plugin_support.register_pane(self._right_pane)
	def tearDown(self):
		rmtree(self._shipped_plugins)
		rmtree(self._thirdparty_plugins)
		rmtree(self._user_plugins)