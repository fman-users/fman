"""Integration test: legacy fman plugins load via the sys.modules shim."""

from vitraj import PLATFORM, ApplicationCommand, DirectoryPaneCommand, \
    DirectoryPaneListener, DirectoryPane, Window
from vitraj.fs import FileSystem, Column
from vitraj.impl.plugins import ExternalPlugin
from vitraj.impl.plugins.command_registry import PaneCommandRegistry, \
    ApplicationCommandRegistry
from vitraj.impl.plugins.config import Config
from vitraj.impl.plugins.context_menu import ContextMenuProvider
from vitraj.impl.plugins.key_bindings import KeyBindings
from vitraj.impl.plugins.mother_fs import MotherFileSystem
from vitraj_integrationtest import get_resource
from vitraj_integrationtest.impl.plugins import StubCommandCallback, StubTheme, \
    StubFontDatabase
from vitraj_unittest.impl.plugins import StubErrorHandler
from unittest import TestCase

import sys


class FmanCompatPluginTest(TestCase):
    """Test that a plugin using `from fman import ...` loads correctly."""

    def test_load_fman_compat_plugin(self):
        """Plugin using legacy fman imports loads without errors."""
        if not self._plugin.load():
            self.fail(
                'Plugin failed to load: ' +
                str(self._error_handler.error_messages)
            )
        # Verify the plugin's command was registered
        self.assertIn(
            'fman_compat_command',
            self._appcmd_registry.get_commands()
        )
        self.assertIn(
            'fman_compat_dpc',
            self._panecmd_registry.get_commands()
        )

    def test_fman_plugin_classes_are_vitraj_subclasses(self):
        """Classes from fman imports are the same as vitraj classes."""
        self._plugin.load()
        from fman_compat_plugin import (
            FmanCompatCommand, FmanCompatDPC, FmanCompatListener,
            FmanCompatFS, FmanCompatColumn
        )
        self.assertTrue(issubclass(FmanCompatCommand, ApplicationCommand))
        self.assertTrue(issubclass(FmanCompatDPC, DirectoryPaneCommand))
        self.assertTrue(issubclass(FmanCompatListener, DirectoryPaneListener))
        self.assertTrue(issubclass(FmanCompatFS, FileSystem))
        self.assertTrue(issubclass(FmanCompatColumn, Column))

    def test_fman_plugin_fs_registered(self):
        """FileSystem from fman-import plugin registers in MotherFileSystem."""
        self._plugin.load()
        from fman_compat_plugin import FmanCompatFS
        fs_wrapper = self._mother_fs._children[FmanCompatFS.scheme]
        self.assertIsInstance(fs_wrapper.unwrap(), FmanCompatFS)

    def test_unload_fman_compat_plugin(self):
        """Plugin using legacy fman imports unloads cleanly."""
        self._plugin.load()
        self._plugin.unload()
        self.assertEqual(set(), self._appcmd_registry.get_commands())
        self.assertEqual(set(), self._panecmd_registry.get_commands())

    def setUp(self):
        super().setUp()
        # Install the fman compatibility shim (mirrors application_context.py)
        import vitraj
        import vitraj.fs
        import vitraj.url
        import vitraj.clipboard
        sys.modules.setdefault('fman', vitraj)
        sys.modules.setdefault('fman.fs', vitraj.fs)
        sys.modules.setdefault('fman.url', vitraj.url)
        sys.modules.setdefault('fman.clipboard', vitraj.clipboard)

        self._sys_path_before = list(sys.path)
        self._plugin_dir = get_resource('Fman Compat Plugin')
        self._config = Config(PLATFORM)
        self._theme = StubTheme()
        self._font_database = StubFontDatabase()
        self._error_handler = StubErrorHandler()
        self._command_callback = StubCommandCallback()
        self._panecmd_registry = \
            PaneCommandRegistry(self._error_handler, self._command_callback)
        self._window = Window(None, self._panecmd_registry)
        self._appcmd_registry = ApplicationCommandRegistry(
            self._window, self._error_handler, self._command_callback
        )
        self._key_bindings = KeyBindings()
        cm_provider = ContextMenuProvider(
            self._panecmd_registry, self._appcmd_registry, self._key_bindings
        )
        self._mother_fs = MotherFileSystem(None)
        self._plugin = ExternalPlugin(
            self._plugin_dir, self._config, self._theme, self._font_database,
            cm_provider, self._error_handler, self._appcmd_registry,
            self._panecmd_registry, self._key_bindings, self._mother_fs,
            self._window
        )

    def tearDown(self):
        sys.path = self._sys_path_before
        # Clean up fman_compat_plugin from sys.modules if loaded
        for key in list(sys.modules):
            if key.startswith('fman_compat_plugin'):
                del sys.modules[key]
        super().tearDown()
