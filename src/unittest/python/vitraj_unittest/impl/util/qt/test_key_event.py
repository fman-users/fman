from fbs_runtime.platform import is_mac
from vitraj.impl.util.qt.key_event import QtKeyEvent
from PyQt5.QtCore import Qt
from unittest import TestCase

class QtKeyEventTest(TestCase):
	def test_tab(self):
		self.assertTrue(QtKeyEvent(Qt.Key_Tab, 0).matches('Tab'))
	def test_ctrl_a(self):
		modifier = Qt.MetaModifier if is_mac() else Qt.ControlModifier
		self.assertTrue(QtKeyEvent(Qt.Key_A, modifier).matches('Ctrl+A'))
	def test_empty(self):
		self.assertFalse(QtKeyEvent(0, 0).matches('a'))