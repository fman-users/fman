from fbs_runtime import application_context as fbs_appctxt
from fbs_runtime.application_context import cached_property
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from fbs_runtime.excepthook import StderrExceptionHandler
from fbs_runtime.excepthook.sentry import SentryExceptionHandler
from fbs_runtime.platform import is_mac
from fman import PLATFORM, DATA_DIRECTORY, Window
from fman.impl.controller import Controller
from fman.impl.font_database import FontDatabase
from fman.impl.licensing import User
from fman.impl.metrics import Metrics, ServerBackend, AsynchronousMetrics, \
	LoggingBackend
from fman.impl.model.icon_provider import GnomeFileIconProvider, \
	GnomeNotAvailable, IconProvider
from fman.impl.nonexistent_shortcut_handler import NonexistentShortcutHandler
from fman.impl.plugins import PluginSupport, CommandCallback, PluginFactory
from fman.impl.plugins.builtin import BuiltinPlugin, NullFileSystem
from fman.impl.plugins.command_registry import PaneCommandRegistry, \
	ApplicationCommandRegistry
from fman.impl.plugins.config import Config
from fman.impl.plugins.context_menu import ContextMenuProvider
from fman.impl.plugins.discover import find_plugin_dirs
from fman.impl.plugins.error import PluginErrorHandler
from fman.impl.plugins.key_bindings import KeyBindings
from fman.impl.plugins.mother_fs import MotherFileSystem
from fman.impl.session import SessionManager
from fman.impl.theme import Theme
from fman.impl.onboarding import TourController
from fman.impl.onboarding.cleanup_guide import CleanupGuide
from fman.impl.onboarding.tutorial import Tutorial
from fman.impl.updater import MacUpdater
from fman.impl.usage_helper import UsageHelper
from fman.impl.util import os_
from fman.impl.util.qt import connect_once
from fman.impl.util.settings import Settings
from fman.impl.view import ProxyStyle
from fman.impl.widgets import MainWindow, SplashScreen, Application
from os import makedirs
from os.path import dirname, join
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QStyleFactory, QFileIconProvider

import fman
import json
import logging
import os
import sys

def get_application_context():
	return fbs_appctxt.get_application_context(
		DevelopmentApplicationContext, FrozenApplicationContext
	)

class DevelopmentApplicationContext(ApplicationContext):
	def __init__(self):
		super().__init__()
		self._main_window = None
	def run(self):
		self.init_logging()
		self._start_metrics()
		self._load_plugins()
		self.session_manager.show_main_window(self.window)
		return self.app.exec_()
	def init_logging(self):
		logging.basicConfig()
	def _start_metrics(self):
		self.metrics.initialize(callback=self._on_metrics_initialised)
		self.metrics.track('StartedFman')
	def _on_metrics_initialised(self):
		# Overwritten by FrozenApplicationContext below.
		pass
	def _load_plugins(self):
		fman.FMAN_VERSION = self.fman_version
		plugin_dirs = find_plugin_dirs(
			self.get_resource('Plugins'),
			join(DATA_DIRECTORY, 'Plugins', 'Third-party'),
			join(DATA_DIRECTORY, 'Plugins', 'User')
		)
		settings_plugin = plugin_dirs[-1]
		makedirs(settings_plugin, exist_ok=True)
		# Ensure main_window is instantiated before plugin_support, or else
		# plugin_support gets instantiated twice:
		_ = self.main_window
		for plugin_dir in plugin_dirs:
			self.plugin_support.load_plugin(plugin_dir)
		self.theme.enable_updates()
	@property
	def fman_version(self):
		return self.build_settings['version']
	def on_main_window_shown(self):
		if self.updater:
			self.updater.start()
		if self.is_licensed:
			if not self.session_manager.was_licensed_on_last_run:
				self.metrics.track('InstalledLicenseKey')
				self.metrics.update_user(
					is_licensed=True, email=self.user.email
				)
		else:
			if self.session_manager.is_first_run:
				pane = self.plugin_support.get_panes()[0]
				tutorial = self.tutorial_factory(pane)
				self.tour_controller.start(tutorial)
			else:
				self.splash_screen.exec()
	def on_main_window_close(self):
		self.session_manager.on_close(self.main_window)
	def on_quit(self):
		self.config.on_quit()
		if self.metrics_logging_enabled:
			log_dir = dirname(self._get_metrics_json_path())
			log_file_path = join(log_dir, 'Metrics.log')
			self.metrics_backend.flush(log_file_path)
	@cached_property
	def app(self):
		result = Application([sys.argv[0]])
		result.setOrganizationName('fman.io')
		result.setOrganizationDomain('fman.io')
		result.setApplicationName('fman')
		result.setStyle(self.style)
		result.setPalette(self.palette)
		result.aboutToQuit.connect(self.on_quit)
		# We need to instantiate this somewhere. So why not here:
		_ = self.mac_clipboard_fix
		return result
	@cached_property
	def mac_clipboard_fix(self):
		if is_mac():
			from fman.impl.mac_clipboard_fix import MacClipboardFix
			return MacClipboardFix()
	@cached_property
	def command_callback(self):
		return CommandCallback(self.metrics)
	@cached_property
	def exception_handlers(self):
		return [self.plugin_error_handler, StderrExceptionHandler()]
	@property
	def main_window(self):
		if self._main_window is None:
			self._main_window = MainWindow(
				self.app, self.help_menu_actions, self.theme,
				self.progress_bar_palette, self.mother_fs, NullFileSystem.scheme
			)
			# Resolve the cyclic dependency main_window <-> controller
			self._main_window.set_controller(self.controller)
			self._main_window.setWindowTitle(self._get_main_window_title())
			self._main_window.setPalette(self.main_window_palette)
			connect_once(self._main_window.shown, self.on_main_window_shown)
			connect_once(
				self._main_window.shown,
				lambda: self.plugin_error_handler.on_main_window_shown(
					self.main_window
				)
			)
			self._main_window.closed.connect(self.on_main_window_close)
			self.app.set_main_window(self._main_window)
		return self._main_window
	def _get_main_window_title(self):
		return 'fman' if self.is_licensed else 'fman – NOT REGISTERED'
	@cached_property
	def help_menu_actions(self):
		if is_mac():
			def app_command(name):
				return lambda _: \
					self.plugin_support.run_application_command(name)
			def directory_pane_command(name):
				def result(_):
					active_pane = self.plugin_support.get_active_pane()
					if active_pane:
						active_pane.run_command(name)
				return result
			return [
				('Keyboard shortcuts', 'F1', app_command('help')),
				(
					'Command Palette', 'Ctrl+Shift+P',
					directory_pane_command('command_palette')
				),
				('Tutorial', '', directory_pane_command('tutorial'))
			]
		else:
			return []
	@cached_property
	def font_database(self):
		return FontDatabase()
	@cached_property
	def key_bindings(self):
		return KeyBindings()
	@cached_property
	def builtin_plugin(self):
		return BuiltinPlugin(
			self.tour_controller, self.tutorial_factory,
			self.cleanupguide_factory, self.plugin_error_handler,
			self.application_command_registry, self.pane_command_registry,
			self.key_bindings, self.mother_fs, self.window
		)
	@cached_property
	def mother_fs(self):
		# Resolve the cyclic dependency MotherFileSystem <-> IconProvider:
		result = MotherFileSystem(None)
		result._icon_provider = self._get_icon_provider(result)
		return result
	def _get_icon_provider(self, fs):
		try:
			qt_icon_provider = GnomeFileIconProvider()
		except GnomeNotAvailable:
			qt_icon_provider = QFileIconProvider()
		icons_dir = self._get_local_data_file('Cache', 'Icons')
		makedirs(icons_dir, exist_ok=True)
		return IconProvider(qt_icon_provider, fs, icons_dir)
	@cached_property
	def config(self):
		return Config(PLATFORM)
	@cached_property
	def splash_screen(self):
		user = self.user
		license_expired = user.has_license() and \
						  not user.license_is_valid_for_curr_version(
							  self.fman_version
						  )
		return SplashScreen(
			self.main_window, self.app, license_expired, user.email
		)
	@cached_property
	def tour_controller(self):
		return TourController()
	@cached_property
	def tutorial_factory(self):
		return lambda pane: Tutorial(
			self.session_manager.is_first_run, self.main_window, pane, self.app,
			self.command_callback, self.metrics
		)
	@cached_property
	def cleanupguide_factory(self):
		return lambda pane: CleanupGuide(
			self.main_window, pane, self.app, self.command_callback,
			self.metrics
		)
	@cached_property
	def plugin_support(self):
		return PluginSupport(
			self.plugin_factory, self.application_command_registry,
			self.key_bindings, self.context_menu_provider, self.config,
			self.builtin_plugin
		)
	@cached_property
	def plugin_factory(self):
		return PluginFactory(
			self.config, self.theme, self.font_database,
			self.plugin_error_handler, self.application_command_registry,
			self.pane_command_registry, self.key_bindings,
			self.context_menu_provider, self.mother_fs, self.window
		)
	@cached_property
	def application_command_registry(self):
		return ApplicationCommandRegistry(
			self.window, self.plugin_error_handler, self.command_callback
		)
	@cached_property
	def pane_command_registry(self):
		return PaneCommandRegistry(
			self.plugin_error_handler, self.command_callback
		)
	@cached_property
	def context_menu_provider(self):
		return ContextMenuProvider(
			self.pane_command_registry, self.application_command_registry,
			self.key_bindings
		)
	@cached_property
	def plugin_error_handler(self):
		return PluginErrorHandler(self.app)
	@cached_property
	def controller(self):
		return Controller(
			self.plugin_support, self.nonexistent_shortcut_handler,
			self.usage_helper, self.metrics
		)
	@cached_property
	def nonexistent_shortcut_handler(self):
		settings = Settings(self._get_local_data_file('Dialogs.json'))
		return NonexistentShortcutHandler(
			self.main_window, settings, self.metrics
		)
	@cached_property
	def usage_helper(self):
		return UsageHelper(self.session_manager.is_first_run)
	@cached_property
	def metrics(self):
		json_path = self._get_metrics_json_path()
		metrics = Metrics(
			json_path, self.metrics_backend, PLATFORM, self.fman_version
		)
		return AsynchronousMetrics(metrics)
	def _get_metrics_json_path(self):
		return self._get_local_data_file('Metrics.json')
	@cached_property
	def metrics_logging_enabled(self):
		return self._read_metrics_logging_enabled()
	def _read_metrics_logging_enabled(self):
		json_path = self._get_metrics_json_path()
		try:
			with open(json_path, 'r') as f:
				data = json.load(f)
		except (FileNotFoundError, ValueError):
			return False
		else:
			try:
				return data.get('logging_enabled', False)
			except AttributeError:
				return False
	@cached_property
	def metrics_backend(self):
		metrics_url = self.build_settings['server_url'] + '/metrics'
		backend = ServerBackend(metrics_url + '/users', metrics_url + '/events')
		if self.metrics_logging_enabled:
			backend = LoggingBackend(backend)
		return backend
	@cached_property
	def palette(self):
		result = QPalette()
		result.setColor(QPalette.Window, QColor(43, 43, 43))
		result.setColor(QPalette.WindowText, Qt.white)
		result.setColor(QPalette.Base, QColor(19, 19, 19))
		result.setColor(QPalette.AlternateBase, QColor(66, 64, 59))
		result.setColor(QPalette.ToolTipBase, QColor(19, 19, 19))
		result.setColor(QPalette.ToolTipText, Qt.white)
		result.setColor(QPalette.Light, QColor(0x49, 0x48, 0x3E))
		result.setColor(QPalette.Midlight, QColor(0x33, 0x33, 0x33))
		result.setColor(QPalette.Button, QColor(0x29, 0x29, 0x29))
		result.setColor(QPalette.Mid, QColor(0x25, 0x25, 0x25))
		result.setColor(QPalette.Dark, QColor(0x20, 0x20, 0x20))
		result.setColor(QPalette.Shadow, QColor(0x1d, 0x1d, 0x1d))
		result.setColor(QPalette.Text, Qt.white)
		result.setColor(
			QPalette.ButtonText, QColor(0xb6, 0xb3, 0xab)
		)
		result.setColor(QPalette.Link, Qt.white)
		result.setColor(QPalette.LinkVisited, Qt.white)
		# Prevent blue highlight around buttons when the window (/dialog) is in
		# the background and thus inactive:
		result.setColor(
			QPalette.Inactive, QPalette.Highlight,
			result.color(QPalette.Midlight)
		)
		return result
	@cached_property
	def user(self):
		json_path = self._get_local_data_file('User.json')
		try:
			with open(json_path, 'r') as f:
				data = json.load(f)
		except (IOError, ValueError):
			data = {}
		if not isinstance(data, dict):
			# Malformed User.json file:
			data = {}
		email = data.get('email', '')
		key = data.get('key', '')
		return User(email, key)
	@cached_property
	def is_licensed(self):
		return self.user.is_licensed(self.fman_version)
	@cached_property
	def main_window_palette(self):
		result = QPalette(self.palette)
		result.setColor(QPalette.Window, QColor(0x44, 0x44, 0x44))
		return result
	@cached_property
	def progress_bar_palette(self):
		result = QPalette(self.main_window_palette)
		# On Windows, when the progress bar (/the progress dialog) is in the
		# background, ie. not the active window, its color changes from blue to
		# white. Avoid this:
		result.setColor(
			QPalette.Inactive, QPalette.Highlight,
			result.color(QPalette.Active, QPalette.Highlight)
		)
		return result
	@cached_property
	def session_manager(self):
		settings = Settings(self._get_local_data_file('Session.json'))
		return SessionManager(
			settings, self.mother_fs, self.plugin_error_handler,
			self.fman_version, self.is_licensed
		)
	@cached_property
	def theme(self):
		qss_files = [self.get_resource('styles.qss')]
		try:
			os_styles = self.get_resource('os_styles.qss')
		except FileNotFoundError:
			pass
		else:
			qss_files.append(os_styles)
		return Theme(self.app, qss_files)
	@cached_property
	def style(self):
		base_style = None
		base_style_name = os.environ.get('QT_QPA_PLATFORMTHEME')
		if base_style_name:
			base_style = QStyleFactory.create(base_style_name)
		if not base_style:
			base_style = QStyleFactory.create('Fusion')
		return ProxyStyle(base_style)
	@cached_property
	def updater(self):
		return None
	@cached_property
	def window(self):
		return Window(self.main_window, self.pane_command_registry)
	def _get_local_data_file(self, *rel_path):
		return join(DATA_DIRECTORY, 'Local', *rel_path)

class FrozenApplicationContext(DevelopmentApplicationContext):
	def init_logging(self):
		logging.basicConfig(level=logging.CRITICAL)
	def on_main_window_shown(self):
		if PLATFORM == 'Linux':
			"""
			PyInstaller sets LD_LIBRARY_PATH to /opt/fman. Processes we spawn,
			be it via Popen(...) or QDesktopServices.openUrl(...), inherit this
			value. This leads to problems, especially when the app we launch is
			based on Qt. The reason is that the OS then attempts to load our 
			libraries, which are most likely incompatible with those of the app.
			An example where this happens is VLC, which errors out with 'This 
			application failed to start because it could not find or load the Qt
			platform plugin "xcb"'. Plugin developers have also encountered this
			unexpected behaviour when trying to launch apps.
			
			To fix the problem, we restore LD_LIBRARY_PATH to its original value
			here. According to the docs [1], PyInstaller stores this value in a
			separate environment variable.
			
			A drawback of unsetting the environment variable here is that
			libraries from PyInstaller's search path cannot be loaded after this
			method was called. In other words, we assume that all required
			libraries have been loaded once we reach here. This assumption may
			turn out to be wrong in the future.
			
			[1]: http://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
			"""
			lp_orig = os.environ.pop('LD_LIBRARY_PATH_ORIG', None)
			if lp_orig is not None:
				os.environ['LD_LIBRARY_PATH'] = lp_orig
			else:
				os.environ.pop('LD_LIBRARY_PATH', None)
		# Similarly to above, PyInstaller sets various QT_... environment
		# variables. This can confuse Qt-based apps which we launch via
		# Popen(...) or QDesktopServices.openUrl(...). An example of this is
		# XnViewMP [1]. Unset the variables here to avoid this. Again, this
		# assumes that by the time we reach here, all required Qt libraries have
		# been loaded.
		# 1: https://github.com/fman-users/fman/issues/570
		delete = [var for var in os.environ if var.startswith('QT_')]
		for var in delete:
			del os.environ[var]
		super().on_main_window_shown()
	@cached_property
	def updater(self):
		if self._should_auto_update():
			return MacUpdater(self.app)
	@cached_property
	def exception_handlers(self):
		result = super().exception_handlers
		result.append(self.sentry_exception_handler)
		return result
	@cached_property
	def sentry_exception_handler(self):
		return SentryExceptionHandler(
			self.build_settings['sentry_dsn'],
			self.fman_version,
			self.build_settings['environment'],
			callback=self._on_sentry_init
		)
	def _on_sentry_init(self):
		scope = self.sentry_exception_handler.scope
		scope.set_extra('os_name', os_.name())
		scope.set_extra('os_version', os_.version())
		scope.set_extra('os_distribution', os_.distribution())
	def _on_metrics_initialised(self):
		self.sentry_exception_handler.scope.user = {
			'id': self.metrics.get_user()
		}
	def _should_auto_update(self):
		if not is_mac():
			# On Windows and Linux, auto-updates are handled by external
			# technologies. No need for fman itself to update:
			return False
		if not self.user.is_entitled_to_updates():
			return False
		try:
			with open(join(DATA_DIRECTORY, 'Local', 'Updates.json'), 'r') as f:
				data = json.load(f)
		except (FileNotFoundError, ValueError):
			return True
		else:
			return data.get('enabled', True)