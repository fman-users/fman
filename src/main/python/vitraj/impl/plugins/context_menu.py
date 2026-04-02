from collections import OrderedDict
from fbs_runtime.platform import is_mac
from vitraj.impl.plugins.util import describe_type, ordered_set

import json

class ContextMenuProvider:

	FILE_CONTEXT = 'file'
	FOLDER_CONTEXT = 'folder'

	def __init__(self, panecmd_registry, appcmd_registry, key_bindings):
		self._panecmd_registry = panecmd_registry
		self._appcmd_registry = appcmd_registry
		self._key_bindings = key_bindings
		self._sanitized_config = {}
	def load(self, config, file_name, context):
		available_commands = self._panecmd_registry.get_commands() | \
							 self._appcmd_registry.get_commands()
		sanitized, errors = \
			sanitize_context_menu(config, file_name, available_commands)
		self._sanitized_config[context] = \
			sanitized + self._sanitized_config.get(context, [])
		return errors
	# The extra `file_name` parameter is there so unload(...) has the same
	# signature as load(...). This is required so ContextMenuProvider can be
	# used with ExternalPlugin#_configure_component_from_json(...).
	def unload(self, config, file_name, context):
		try:
			for elt in config:
				try:
					self._sanitized_config[context].remove(elt)
				except ValueError as not_in_list:
					pass
		except TypeError as not_iterable:
			pass
	def get_context_menu(self, pane, file_under_mouse=None):
		context = self.FOLDER_CONTEXT if file_under_mouse is None \
			else self.FILE_CONTEXT
		entries = self._sanitized_config.get(context, [])
		entries_per_id = self._group_by_id(entries)
		result_tpls = []
		for id_ in self._get_group_order(entries):
			group = entries_per_id[id_]
			group_tpls = []
			for entry in group:
				tpl = self._parse_entry(entry, pane, file_under_mouse)
				if tpl:
					group_tpls.append(tpl)
			if group_tpls:
				result_tpls.append(group_tpls)
		return self._join_iterables(('-', '', None), result_tpls)
	def _group_by_id(self, entries):
		groups = []
		id_ = None
		group = []
		def end_group():
			if group:
				groups.append((id_, list(group)))
				group.clear()
		for entry in entries:
			if 'id' in entry:
				end_group()
				id_ = entry['id']
			if entry.get('caption') != '-':
				group.append(entry)
		end_group()
		result = OrderedDict()
		for id_, group in groups:
			result[id_] = group + result.get(id_, [])
		return result
	def _get_group_order(self, entries):
		"""
		Suppose the default context menu is
		 * a
		 * b
		 * c1.
		Further suppose that the user wants to add an entry c2 to group "c".
		He does this by adding c2 to Context Menu.json. Due to the way JSON
		files are loaded by fman, this results in the following order:
		 * c2
		 * a
		 * b
		 * c1
		At this point, #_group_by_id(...) below has turned this into:
		 * [c1, c2]
		 * a
		 * b
		But we want the c's to appear at the end of the context menu.
		The following lines achieve this by preserving the original order:
		"""
		ids = [e['id'] for e in entries if 'id' in e]
		has_none = entries and 'id' not in entries[0]
		if has_none:
			ids.insert(0, None)
		return reversed(ordered_set(reversed(ids)))
	def _parse_entry(self, entry, pane, file_under_mouse):
		caption = entry.get('caption')
		cmd_name = entry['command']
		if cmd_name in pane.get_commands():
			if not self._panecmd_registry.is_command_visible(
				cmd_name, pane, file_under_mouse
			):
				return None
			def run_command(cmd_name, args):
				self._panecmd_registry.execute_command(
					cmd_name, args, pane, file_under_mouse
				)
			caption = caption or pane.get_command_aliases(cmd_name)[0]
		else:
			run_command = self._appcmd_registry.execute_command
			caption = caption or \
					  self._appcmd_registry \
						  .get_command_aliases(cmd_name)[0]
		args = entry.get('args', {})
		# Need `r=run_command,...` to create one lambda per loop:
		callback = lambda r=run_command, c=cmd_name, a=args: r(c, a)
		all_shortcuts = self._get_shortcuts_for_command(cmd_name)
		try:
			shortcut = next(iter(all_shortcuts))
		except StopIteration:
			shortcut = ''
		return caption, shortcut, callback
	def _get_shortcuts_for_command(self, command):
		for binding in self._key_bindings.get_sanitized_bindings():
			if binding['command'] != command:
				continue
			shortcut = binding['keys'][0]
			if is_mac():
				shortcut = _insert_mac_key_symbols(shortcut)
			yield shortcut
	def _join_iterables(self, separator, iterables):
		is_first = True
		for arr in iterables:
			if not is_first:
				yield separator
			yield from arr
			is_first = False

def sanitize_context_menu(cm, file_name, available_commands):
	if not isinstance(cm, list):
		return [], [(
			'Error: %s should be a list [...], not %s.'
			% (file_name, describe_type(cm))
		)]
	result, errors = [], []
	for item in cm:
		if not isinstance(item, dict):
			errors.append(
				'Error in %s: Element %s should be a dict {...}, not %s.' %
				(file_name, json.dumps(item), describe_type(item))
			)
			continue
		caption = item.get('caption')
		command = item.get('command')
		if command:
			if caption == '-':
				errors.append(
					'Error in %s, element %s: "command" cannot be used when '
					'the caption is "-".' % (file_name, json.dumps(item))
				)
				continue
			if command not in available_commands:
				errors.append(
					'Error in %s: Command %s referenced in element %s does not '
					'exist.' %
					(file_name, json.dumps(command), json.dumps(item))
				)
				continue
			args = item.get('args')
			if args is not None and not isinstance(args, dict):
				errors.append(
					'Error in %s: "args" must be a dict {...}, not %s.'
					% (file_name, describe_type(args))
				)
				continue
		else:
			if not caption:
				errors.append(
					'Error in %s: Element %s should specify at least a '
					'"command" or a "caption".' % (file_name, json.dumps(item))
				)
				continue
			if caption != '-':
				errors.append(
					'Error in %s, element %s: Unless the caption is "-", you '
					'must specify a "command".' % (file_name, json.dumps(item))
				)
				continue
		result.append(item)
	return result, errors

# Copied from the Core plugin:
def _insert_mac_key_symbols(shortcut):
	keys = shortcut.split('+')
	return ''.join(_KEY_SYMBOLS_MAC.get(key, key) for key in keys)

# Copied from the Core plugin:
_KEY_SYMBOLS_MAC = {
	'Cmd': '⌘', 'Alt': '⌥', 'Ctrl': '⌃', 'Shift': '⇧', 'Backspace': '⌫',
	'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→', 'Enter': '↩'
}