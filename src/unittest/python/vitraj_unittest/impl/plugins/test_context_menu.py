from vitraj import DirectoryPane
from vitraj.impl.plugins.command_registry import PaneCommandRegistry, \
	ApplicationCommandRegistry
from vitraj.impl.plugins.context_menu import sanitize_context_menu, \
	ContextMenuProvider
from vitraj.impl.plugins.key_bindings import KeyBindings
from unittest import TestCase

class GetContextMenuTest(TestCase):
	def test_id_handling(self):
		for cmd in ('about', 'delete', 'open', 'copy', 'rename'):
			self._app_cmd_registry.register_command(cmd, lambda *_, **__: None)
		self._cm.load(
			[
				{ 'command': 'about', 'caption': 'About' },
				{ 'caption': '-', 'id': 'file_operations' },
				{ 'command': 'delete', 'caption': 'Delete' },
				{ 'caption': '-', 'id': 'open' },
				{ 'command': 'open', 'caption': 'Open' },
				{ 'caption': '-', 'id': 'clipboard' },
				{ 'command': 'copy', 'caption': 'Copy' },
				{'caption': '-', 'id': 'file_operations'},
				{'command': 'rename', 'caption': 'Rename'}
			], '', self._cm.FOLDER_CONTEXT
		)
		self.assertEqual(
			['About', '-', 'Open', '-', 'Copy', '-', 'Rename', 'Delete'],
			[entry[0] for entry in self._cm.get_context_menu(self._pane)]
		)
	def setUp(self):
		super().setUp()
		self._pane_cmd_registry = PaneCommandRegistry(None, None)
		self._app_cmd_registry = ApplicationCommandRegistry(None, None, None)
		self._key_bindings = KeyBindings()
		self._cm = ContextMenuProvider(
			self._pane_cmd_registry, self._app_cmd_registry, self._key_bindings
		)
		self._pane = DirectoryPane(None, None, self._pane_cmd_registry)

class SanitizeContextMenuTest(TestCase):
	def test_non_list(self):
		self.assertEqual(
			([], [
				'Error: Context Menu.json should be a list [...], not {...}.'
			]), self._sanitize_context_menu({})
		)
	def test_entry_non_dict(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Element [] should be a dict '
				'{...}, not [...].'
			]), self._sanitize_context_menu([[]])
		)
	def test_no_command_no_caption(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Element {} should specify at '
				'least a "command" or a "caption".'
			]), self._sanitize_context_menu([{}])
		)
	def test_arg_non_dict(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: "args" must be a dict {...}, not '
				'[...].'
			]), self._sanitize_context_menu(
				[{'command': 'foo', 'args': []}], ['foo']
			)
		)
	def test_separator_with_command(self):
		result = self._sanitize_context_menu(
			[{'caption': '-', 'command': 'foo'}], ['foo']
		)
		self.assertEqual([], result[0])
		self.assertIsInstance(result[1], list)
		self.assertEqual(1, len(result[1]))
		actual_error, = result[1]
		elt_reprs = {
			'{"caption": "-", "command": "foo"}',
			'{"command": "foo", "caption": "-"}'
		}
		possible_errors = {
			'Error in Context Menu.json, element %s: "command" '
			'cannot be used when the caption is "-".' % r
			for r in elt_reprs
		}
		self.assertIn(actual_error, possible_errors)
	def test_no_command(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json, element {"caption": "Hello"}: '
				'Unless the caption is "-", you must specify a "command".'
			]), self._sanitize_context_menu([{'caption': 'Hello'}])
		)
	def test_nonexistent_command(self):
		self.assertEqual(
			([], [
				'Error in Context Menu.json: Command "foo" referenced in '
				'element {"command": "foo"} does not exist.'
			]), self._sanitize_context_menu([{'command': 'foo'}])
		)
	def test_valid(self):
		data = [
			{ 'command': 'cut' },
			{ 'command': 'copy_to_clipboard', 'caption': 'cut' },
			{ 'caption': '-' },
			{ 'command': 'paste' }
		]
		self.assertEqual(
			(data, []),
			self._sanitize_context_menu(
				data, ['cut', 'copy_to_clipboard', 'paste']
			)
		)
	def _sanitize_context_menu(self, cm, available_commands=None):
		if available_commands is None:
			available_commands = []
		return sanitize_context_menu(
			cm, 'Context Menu.json', available_commands
		)