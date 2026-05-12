from PyQt5.QtWidgets import QTableView, QStyledItemDelegate

class MultipleDelegates(QTableView):
	""" Let a QTableView have multiple ItemDelegates. """
	def __init__(self, parent=None):
		super().__init__(parent)
		self._composite_delegate = CompositeItemDelegate(self)
		self.setItemDelegate(self._composite_delegate)
	def add_delegate(self, delegate):
		self._composite_delegate.add(delegate)
	def remove_delegate(self, delegate):
		self._composite_delegate.remove(delegate)

class CompositeItemDelegate(QStyledItemDelegate):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._items = []
	def add(self, item):
		self._items.append(item)
	def remove(self, item):
		self._items.remove(item)
	def initStyleOption(self, option, index):
		super().initStyleOption(option, index)
		if not index.isValid():
			return
		for item in self._items:
			# Unlike the other methods in this class, we don't call
			# `item.initStyleOption(...)` here, for the following reason:
			# It would have to call `super().initStyleOption(...)`. This is
			# an expensive operation. To avoid having to call it for every
			# `item`, we therefore call it only once - above this for loop -
			# then use `item#adapt_style_option(...)` to make the necessary
			# changes. When 350 files are displayed, this saves about 700ms.
			item.adapt_style_option(option, index)
	def eventFilter(self, editor, event):
		for item in self._items:
			# eventFilter(...) is protected. We can only call it if we
			# reimplemented it ourselves in Python:
			if self._is_python_method(item.eventFilter):
				result = item.eventFilter(editor, event)
				if result:
					return result
		return super().eventFilter(editor, event)
	def helpEvent(self, event, view, option, index):
		for item in self._items:
			result = item.helpEvent(event, view, option, index)
			if result:
				return result
		return super().helpEvent(event, view, option, index)
	def createEditor(self, parent, option, index):
		for item in self._items:
			result = item.createEditor(parent, option, index)
			if result:
				return result
		return super().createEditor(parent, option, index)
	def _is_python_method(self, method):
		return hasattr(method, '__func__')