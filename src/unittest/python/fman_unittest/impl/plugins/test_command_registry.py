from fman.impl.plugins.command_registry import ApplicationCommandRegistry
from fman_unittest.impl.plugins import StubErrorHandler
from unittest import TestCase

class StubCallback:
	def __init__(self):
		self.before_commands = []
		self.after_commands = []
	def before_command(self, name):
		self.before_commands.append(name)
	def after_command(self, name):
		self.after_commands.append(name)

class StubWindow:
	pass

class ApplicationCommandRegistryTest(TestCase):
	def test_after_command_not_called_on_error(self):
		error_handler = StubErrorHandler()
		error_handler.handle_system_exit = lambda code: None
		callback = StubCallback()
		registry = ApplicationCommandRegistry(
			StubWindow(), error_handler, callback
		)
		class FailingCommand:
			def __init__(self, window):
				pass
			def __call__(self, **kwargs):
				raise RuntimeError('boom')
			def is_visible(self):
				return True
			aliases = ()
		registry.register_command('fail', FailingCommand)
		registry._execute_command(registry._commands['fail'], {})
		self.assertEqual(['FailingCommand'], callback.before_commands)
		self.assertEqual([], callback.after_commands)
	def test_after_command_called_on_success(self):
		error_handler = StubErrorHandler()
		error_handler.handle_system_exit = lambda code: None
		callback = StubCallback()
		registry = ApplicationCommandRegistry(
			StubWindow(), error_handler, callback
		)
		class SuccessCommand:
			def __init__(self, window):
				pass
			def __call__(self, **kwargs):
				pass
			def is_visible(self):
				return True
			aliases = ()
		registry.register_command('success', SuccessCommand)
		registry._execute_command(registry._commands['success'], {})
		self.assertEqual(['SuccessCommand'], callback.before_commands)
		self.assertEqual(['SuccessCommand'], callback.after_commands)
