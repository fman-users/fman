from vitraj.impl.plugins.error import format_traceback
from vitraj_integrationtest import get_resource
from os.path import dirname
from unittest import TestCase

import sys

class FormatTracebackTest(TestCase):
	def test_format_traceback(self):
		import fman_
		import plugin.module
		try:
			fman_.run_plugins()
		except ValueError as e:
			exc = e
		exclude_from_tb = [dirname(__file__), dirname(fman_.__file__)]
		traceback_ = format_traceback(exc, exclude_from_tb)
		self.assertEqual(
			'Traceback (most recent call last):\n'
			'  File "' + plugin.module.__file__ + '", line 4, in run_plugin\n'
			'    raise_error()\n'
			'ValueError\n',
			traceback_
		)
	def setUp(self):
		sys.path.append(get_resource('FormatTracebackTest'))
		self.maxDiff = None
	def tearDown(self):
		sys.path.pop()