from vitraj_integrationtest.plugin_tests import PluginTest
from time import time, sleep

class KeyBindingsTest(PluginTest):
	def test_key_bindings(self, timeout_secs=1):
		key_bindings = self._plugin_support.get_sanitized_key_bindings()
		self.assertEqual(2, len(key_bindings))
		first, second = key_bindings
		self.assertEqual({
			'keys': ['Enter'],
			'command': 'test_command',
			'args': {
				'success': True
			}
		}, first)
		# Can do this because sys.path has been extended by `Plugin#load()`:
		from simple_plugin import TestCommand
		self.assertFalse(TestCommand.RAN, 'Sanity check')
		try:
			self._plugin_support.run_application_command(
				'test_command', {'ran': True}
			)
			end_time = time() + timeout_secs
			while time() < end_time:
				if TestCommand.RAN:
					# Success.
					break
				else:
					sleep(.1)
			else:
				self.fail("TestCommand didn't run.")
		finally:
			TestCommand.RAN = False
		self.assertEqual({
			'keys': ['Space'],
			'command': 'command_raising_error'
		}, second)
		# Should not raise an exception:
		self._left_pane.run_command('command_raising_error')
		self.assertEqual(
			["Command 'CommandRaisingError' raised error."],
			self._error_handler.error_messages
		)