from vitraj.impl.view.uniform_row_heights import UniformRowHeights
from math import ceil

class ResizeColumnsToContents(UniformRowHeights):
	def __init__(self, parent):
		super().__init__(parent)
		self.horizontalHeader().sectionResized.connect(self._on_col_resized)
		self._old_col_widths = None
		self._handle_col_resize = True
	def resizeColumnsToContents(self):
		self._resize_cols_to_contents()
	def resizeEvent(self, event):
		super().resizeEvent(event)
		num_rows_visible = self._get_num_visible_rows()
		self.model().set_num_rows_to_preload(num_rows_visible)
		# Performance improvement: We call sizeHintForColumn(...). By default,
		# this considers 1000 rows. So what Qt does is that it "loads" the 1000
		# rows and then computes their size. This can be expensive. We therefore
		# reduce 1000 to the number of rows that are actually visible (typically
		# ~50).
		self.horizontalHeader().setResizeContentsPrecision(num_rows_visible)
		self._resize_cols_to_contents(self._old_col_widths)
		self._old_col_widths = self._get_column_widths()
	def _get_num_visible_rows(self):
		row_height = self.get_row_height()
		if row_height == -1:
			# This for instance happens when the model has 0 rows.
			return 0
		content_height = self.height() - self.horizontalHeader().height()
		# Assumes all rows have the same height:
		return ceil(content_height / row_height)
	def setModel(self, model):
		old_model = self.model()
		if old_model:
			old_model.modelReset.disconnect(self._on_model_reset)
		super().setModel(model)
		model.modelReset.connect(self._on_model_reset)
	def _on_model_reset(self):
		self._old_col_widths = None
	def _resize_cols_to_contents(self, curr_widths=None):
		if self._get_rows_visible_but_not_loaded():
			return
		if curr_widths is None:
			curr_widths = self._get_column_widths()
		min_widths = self._get_min_col_widths()
		width = self._get_width_excl_scrollbar()
		ideal_widths = _get_ideal_column_widths(curr_widths, min_widths, width)
		self._apply_column_widths(ideal_widths)
	def _get_rows_visible_but_not_loaded(self):
		model = self.model()
		return [
			i for i in self.get_visible_row_range()
			if not model.row_is_loaded(i)
		]
	def _get_width_excl_scrollbar(self):
		return self.width() - self._get_vertical_scrollbar_width()
	def _get_vertical_scrollbar_width(self):
		scrollbar = self.verticalScrollBar()
		if scrollbar.isVisible():
			return scrollbar.width()
		required_height = self.viewportSizeHint().height()
		will_scrollbar_be_visible = required_height > self.height()
		if will_scrollbar_be_visible:
			# This for instance happens when fman is just starting up. In this
			# case, scrollbar.isVisible() is False even though it is visible on
			# the screen. One theory that could explain this is that in the
			# initial paint event, Qt gives us the entire viewport to paint on.
			# It then realizes that we used more than the available height and
			# draws the vertical scrollbar on top of the viewport - without
			# setting isVisible() to True. But this is just a theory.
			return scrollbar.sizeHint().width()
		return 0
	def _get_column_widths(self):
		return [self.columnWidth(i) for i in range(self._num_columns)]
	def _get_min_col_widths(self):
		header = self.horizontalHeader()
		return [
			max(self.sizeHintForColumn(c), header.sectionSizeHint(c))
			for c in range(self._num_columns)
		]
	def _apply_column_widths(self, widths):
		for col, width in enumerate(widths):
			self.setColumnWidth(col, width)
	@property
	def _num_columns(self):
		return self.horizontalHeader().count()
	def _on_col_resized(self, col, old_size, size):
		if old_size == size:
			return
		# Prevent infinite recursion:
		if not self._handle_col_resize:
			return
		self._handle_col_resize = False
		try:
			widths = self._get_column_widths()
			widths[col] = old_size
			min_widths = self._get_min_col_widths()
			width = self._get_width_excl_scrollbar()
			new_widths = _resize_column(col, size, widths, min_widths, width)
			self._apply_column_widths(new_widths)
		finally:
			self._handle_col_resize = True

def _get_ideal_column_widths(curr_widths, min_widths, available_width):
	if not min_widths:
		raise ValueError(repr(min_widths))
	if len(curr_widths) != len(min_widths):
		curr_widths = [0] * len(min_widths)
	result = list(curr_widths)
	width = sum(curr_widths)
	min_width = sum(min_widths)
	truncated_columns = [
		c for c, (w, m_w) in enumerate(zip(curr_widths, min_widths))
		if w < m_w
	]
	if truncated_columns:
		if min_width <= available_width:
			# Simply enlarge the truncated columns.
			for c in truncated_columns:
				result[c] = min_widths[c]
			width = sum(result)
	if width > available_width:
		trim_required = width - available_width
		trimmable_cols = [
			c for c, (w, m_w) in enumerate(zip(result, min_widths))
			if w > m_w
		]
		trimmable_widths = [result[c] - min_widths[c] for c in trimmable_cols]
		trimmable_width = sum(trimmable_widths)
		to_trim = min(trim_required, trimmable_width)
		col_trims = _distribute_evenly(to_trim, trimmable_widths)
		for c, trim in zip(trimmable_cols, col_trims):
			result[c] -= trim
		trim_required -= to_trim
		if trim_required > 0:
			col_trims = _distribute_exponentially(trim_required, result)
			for c, trim in enumerate(col_trims):
				result[c] -= trim
	elif width < available_width:
		result[0] += available_width - width
	last_col_excess = result[-1] - min_widths[-1]
	if last_col_excess > 0:
		result[-1] -= last_col_excess
		result[0] += last_col_excess
	return result

def _distribute_evenly(width, proportions):
	total = sum(proportions)
	if not total:
		return [0] * len(proportions)
	return [int(p / total * width) for p in proportions]

def _distribute_exponentially(width, proportions):
	total = sum(p * p for p in proportions)
	if not total:
		return [0] * len(proportions)
	return [int(p * p / total * width) for p in proportions]

def _resize_column(col, new_size, widths, min_widths, available_width):
	old_size = widths[col]
	result = list(widths)
	result[col] = new_size
	if old_size <= 0 or col == len(widths) - 1:
		return result
	delta = new_size - old_size
	if delta > 0:
		for c in range(col + 1, len(widths)):
			width = widths[c]
			trimmable = width - min_widths[c]
			if trimmable > 0:
				trim = min(delta, trimmable)
				result[c] = width - trim
				delta -= trim
				if not delta:
					break
	else:
		next_col = col + 1
		if sum(result) < available_width:
			result[next_col] -= delta
	to_distribute = available_width - sum(result)
	if to_distribute > 0:
		for c, (w, m_w) in enumerate(zip(widths, min_widths)):
			room = m_w - w
			if room > 0:
				expand = min(to_distribute, room)
				result[c] += expand
				to_distribute -= expand
				if not to_distribute:
					break
	return result