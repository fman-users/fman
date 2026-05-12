from vitraj.impl.plugins.util import describe_type

class KeyBindings:
	def __init__(self):
		self._sanitized_bindings = []
		self._available_commands = []
	def register_command(self, command):
		self._available_commands.append(command)
	def unregister_command(self, command):
		self._available_commands.remove(command)
	def load(self, bindings):
		sanitized, errors = \
			sanitize_key_bindings(bindings, self._available_commands)
		self._sanitized_bindings = sanitized + self._sanitized_bindings
		return errors
	def unload(self, bindings):
		try:
			for binding in bindings:
				try:
					self._sanitized_bindings.remove(binding)
				except ValueError as not_in_list:
					pass
		except TypeError as not_iterable:
			pass
	def get_sanitized_bindings(self):
		return self._sanitized_bindings

def sanitize_key_bindings(bindings, available_commands):
	if not isinstance(bindings, list):
		return [], [('Error: Key bindings should be a list [...], not %s.' %
					 describe_type(bindings))]
	result, errors = [], []
	for binding in bindings:
		this_binding_errors = []
		try:
			command = binding['command']
		except KeyError:
			this_binding_errors.append(
				'Error: Each key binding must specify a "command".'
			)
		else:
			if not isinstance(command, str):
				this_binding_errors.append(
					'Error: A key binding\'s "command" must be a string "...", '
					'not %s.' % describe_type(command)
				)
			else:
				if command not in available_commands:
					this_binding_errors.append(
						'Error in key bindings: Command %r does not exist.'
						% command
					)
		try:
			keys = binding['keys']
		except KeyError:
			this_binding_errors.append(
				'Error: Each key binding must specify "keys": [...].'
			)
		else:
			if not isinstance(keys, list):
				this_binding_errors.append(
					'Error: A key binding\'s "keys" must be a list ["..."], '
					'not %s.' % describe_type(keys)
				)
			if not keys:
				this_binding_errors.append(
					'Error: A key binding\'s "keys" must be a non-empty list '
					'["..."], not [].'
				)
		if this_binding_errors:
			errors.extend(this_binding_errors)
		else:
			result.append(binding)
	return result, errors