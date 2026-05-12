from PyQt5.QtCore import Qt, QRect, QItemSelectionModel as QISM
from PyQt5.QtWidgets import QTableView

class CursorMovement(QTableView):
	def move_cursor_down(self, toggle_selection=False):
		if toggle_selection:
			self._toggle_current_index()
		self._move_cursor(self.MoveDown)
	def move_cursor_up(self, toggle_selection=False):
		if toggle_selection:
			self._toggle_current_index()
		self._move_cursor(self.MoveUp)
	def move_cursor_page_up(self, toggle_selection=False):
		self._move_cursor(self.MovePageUp, toggle_selection)
		self.move_cursor_up()
	def move_cursor_page_down(self, toggle_selection=False):
		self._move_cursor(self.MovePageDown, toggle_selection)
		self.move_cursor_down()
	def move_cursor_home(self, toggle_selection=False):
		self._move_cursor(self.MoveHome, toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._move_cursor(self.MoveEnd, toggle_selection)
	def _toggle_current_index(self):
		index = self.currentIndex()
		if index.isValid():
			self.selectionModel().select(index, QISM.Toggle | QISM.Rows)
	def _move_cursor(self, cursor_action, toggle_selection=False):
		modifiers = self._get_modifiers(cursor_action)
		new_current = self.moveCursor(cursor_action, modifiers)
		old_current = self.currentIndex()
		if new_current != old_current and new_current.isValid():
			self.setCurrentIndex(new_current)
			if toggle_selection:
				rect = QRect(self.visualRect(old_current).center(),
							 self.visualRect(new_current).center())
				command = self._get_toggle_selection_command()
				self.setSelection(rect, command)
		return
	def _get_modifiers(self, cursor_action):
		""" Can be overwritten by subclasses. """
		return Qt.NoModifier
	def _get_toggle_selection_command(self):
		""" Can be overwritten by subclasses. """
		return QISM.Toggle