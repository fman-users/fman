from vitraj.impl.plugins.key_bindings import sanitize_key_bindings
from unittest import TestCase

class SanitizeKeyBindingsTest(TestCase):
	def test_non_list(self):
		self.assertEqual(
			([], ['Error: Key bindings should be a list [...], not {...}.']),
			sanitize_key_bindings({}, [])
		)
	def test_command_not_specified(self):
		self.assertEqual(
			([], ['Error: Each key binding must specify a "command".']),
			sanitize_key_bindings([{'keys': ['F3']}], [])
		)
	def test_command_non_str(self):
		self.assertEqual(
			([], [
				'Error: A key binding\'s "command" must be a string "...", not '
				'int.'
			]),
			sanitize_key_bindings([{'keys': ['F3'], 'command': 3}], [])
		)
	def test_keys_not_specified(self):
		self.assertEqual(
			([], ['Error: Each key binding must specify "keys": [...].']),
			sanitize_key_bindings([{'command': 'foo'}], ['foo'])
		)
	def test_keys_non_list(self):
		self.assertEqual(
			([], [
				'Error: A key binding\'s "keys" must be a list ["..."], not '
				'"...".'
			]),
			sanitize_key_bindings([{'command': 'foo', 'keys': 'F3'}], ['foo'])
		)
	def test_keys_empty_list(self):
		self.assertEqual(
			([], [
				'Error: A key binding\'s "keys" must be a non-empty list '
				'["..."], not [].'
			]),
			sanitize_key_bindings([{'command': 'foo', 'keys': []}], ['foo'])
		)
	def test_nonexistent_command(self):
		self.assertEqual(
			([], ["Error in key bindings: Command 'foo' does not exist."]),
			sanitize_key_bindings([{'command': 'foo', 'keys': ['F3']}], [])
		)