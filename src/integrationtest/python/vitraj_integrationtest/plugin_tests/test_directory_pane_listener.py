from vitraj_integrationtest.plugin_tests import PluginTest

class DirectoryPaneListenerTest(PluginTest):
	def test_on_path_changed_error(self):
		self._left_pane._broadcast('on_path_changed')
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_doubleclicked_error(self):
		self._left_pane._broadcast('on_doubleclicked', self._settings_plugin)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)
	def test_on_name_edited_error(self):
		self._left_pane._broadcast(
			'on_name_edited', self._settings_plugin, 'New name'
		)
		self.assertEqual(
			["DirectoryPaneListener 'ListenerRaisingError' raised error."],
			self._error_handler.error_messages
		)