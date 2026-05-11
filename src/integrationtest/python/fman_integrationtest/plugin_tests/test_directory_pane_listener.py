from fman.impl.plugins.plugin import ListenerWrapper
from fman_integrationtest.plugin_tests import PluginTest

class DirectoryPaneListenerTest(PluginTest):
	def _broadcast_and_wait(self, *args):
		self._left_pane._broadcast(*args)
		ListenerWrapper._POOL.submit(lambda: None).result()
	def test_on_path_changed_error(self):
		self._broadcast_and_wait('on_path_changed')
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_doubleclicked_error(self):
		self._broadcast_and_wait('on_doubleclicked', self._settings_plugin)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_name_edited_error(self):
		self._broadcast_and_wait(
			'on_name_edited', self._settings_plugin, 'New name'
		)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)