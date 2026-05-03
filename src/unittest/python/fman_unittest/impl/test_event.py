from fman.impl.util import Event
from unittest import TestCase

class EventTest(TestCase):
	def test_trigger_calls_callbacks(self):
		event = Event()
		results = []
		event.add_callback(lambda x: results.append(x))
		event.trigger('a')
		self.assertEqual(['a'], results)
	def test_trigger_multiple_callbacks(self):
		event = Event()
		results = []
		event.add_callback(lambda: results.append(1))
		event.add_callback(lambda: results.append(2))
		event.trigger()
		self.assertEqual([1, 2], results)
	def test_remove_callback_during_trigger(self):
		event = Event()
		results = []
		def remove_self():
			event.remove_callback(remove_self)
			results.append('removed')
		event.add_callback(remove_self)
		event.add_callback(lambda: results.append('second'))
		event.trigger()
		self.assertEqual(['removed', 'second'], results)
	def test_add_callback_during_trigger(self):
		event = Event()
		results = []
		def add_new():
			event.add_callback(lambda: results.append('new'))
			results.append('first')
		event.add_callback(add_new)
		event.trigger()
		self.assertEqual(['first'], results)
		results.clear()
		event.trigger()
		self.assertEqual(['first', 'new'], results)
	def test_remove_callback(self):
		event = Event()
		results = []
		cb = lambda: results.append(1)
		event.add_callback(cb)
		event.remove_callback(cb)
		event.trigger()
		self.assertEqual([], results)
