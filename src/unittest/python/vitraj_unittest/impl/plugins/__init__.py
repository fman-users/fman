class StubErrorHandler:
	def __init__(self):
		self.error_messages = []
		self.exceptions = []
	def add_dir(self, plugin_dir):
		pass
	def remove_dir(self, plugin_dir):
		pass
	def report(self, message, exc=None):
		self.error_messages.append(message)
		self.exceptions.append(exc)