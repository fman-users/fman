from collections import namedtuple
from vitraj.impl.model.table import _get_move_destination, TableModel
from unittest import TestCase

class GetMoveDestinationTest(TestCase):
	def test_move_one_row_up(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(0, _get_move_destination(2, 3, 0))
	def test_move_one_row_one_step_down(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(4, _get_move_destination(2, 3, 3))
	def test_move_multiple_rows_down_overlapping(self):
		self.assertEqual(4, _get_move_destination(1, 3, 2))
	def test_move_multiple_rows_down_adjacent(self):
		self.assertEqual(5, _get_move_destination(1, 3, 3))
	def test_move_multiple_rows_far_down(self):
		self.assertEqual(6, _get_move_destination(1, 3, 4))
	def test_move_multiple_rows_one_up(self):
		self.assertEqual(1, _get_move_destination(2, 101, 1))
	def test_move_multiple_rows_two_up(self):
		self.assertEqual(0, _get_move_destination(2, 101, 0))
	def test_move_multiple_rows_far_up(self):
		self.assertEqual(2, _get_move_destination(5, 7, 2))

class TableModelTest(TestCase):
	def test_empty(self):
		# Sanity check
		self._expect_rows([])
	def test_insert_first_row(self):
		row = Row('a')
		self._model.insert_rows([row])
		self._expect_rows([row])
	def test_insert_second_row(self):
		a = Row('a')
		self._model.insert_rows([a])
		b = Row('b')
		self._model.insert_rows([b])
		self._expect_rows([a, b])
		return a, b
	def test_insert_at_start(self):
		a, b = self.test_insert_second_row()
		c = Row('c')
		self._model.insert_rows([c], 0)
		self._expect_rows([c, a, b])
	def test_insert_between(self):
		a, b = self.test_insert_second_row()
		c = Row('c')
		self._model.insert_rows([c], 0)
		self._expect_rows([c, a, b])
	def test_move_row_forward(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.insert_rows([a, b, c])
		self._model.move_rows(0, 1, 1)
		self._expect_rows([b, a, c])
	def test_move_row_end(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.insert_rows([a, b, c])
		self._model.move_rows(0, 1, 2)
		self._expect_rows([b, c, a])
	def test_move_row_back(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.insert_rows([a, b, c])
		self._model.move_rows(1, 2, 0)
		self._expect_rows([b, a, c])
	def test_move_multiple_rows(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.insert_rows([a, b, c])
		self._model.move_rows(0, 2, 1)
		self._expect_rows([c, a, b])
	def test_update(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.update_rows([a, b], 0)
		self._expect_rows([a, b])
		self._model.update_rows([c], 0)
		self._expect_rows([c, b])
		self._model.update_rows([a], 1)
		self._expect_rows([c, a])
	def test_remove(self):
		a, b, c = Row('a'), Row('b'), Row('c')
		self._model.insert_rows([a, b, c])
		self._model.remove_rows(2)
		self._expect_rows([a, b])
		self._model.remove_rows(0, 1)
		self._expect_rows([b])
		self._model.remove_rows(0, 1)
		self._expect_rows([])
	def setUp(self):
		super().setUp()
		self._model = StubTableModel(['Column 1'])
	def _expect_rows(self, rows):
		self.assertEqual(rows, self._model.get_rows())

class StubSignal:
	def emit(self, *args):
		pass

class StubTableModel(TableModel):

	dataChanged = StubSignal()

	def get_rows(self):
		return list(self._rows)
	def beginInsertRows(self, *args, **kwargs):
		pass
	def endInsertRows(self):
		pass
	def beginMoveRows(self, *args, **kwargs):
		return True
	def endMoveRows(self):
		pass
	def beginRemoveRows(self, *args, **kwargs):
		pass
	def endRemoveRows(self):
		pass
	def index(self, row, column):
		pass

class Row(namedtuple('Row', ('key', 'value'))):
	def __new__(cls, key, value=None):
		return super(Row, cls).__new__(cls, key, value)