from vitraj.impl.util import ConstructorMixin, EqMixin, ReprMixin

class ComputeDiff:
	"""
	N.B.: This implementation requires that there be no duplicate rows!
	"""
	def __init__(self, old_rows, new_rows, key_fn=lambda x: x):
		self._old_rows = list(old_rows)
		self._new_rows = new_rows
		self._key_fn = key_fn
		self._old_keys = list(map(key_fn, old_rows))
		if len(self._old_keys) != len(set(self._old_keys)):
			raise ValueError('Duplicate rows are not supported')
		self._new_keys = list(map(key_fn, new_rows))
		if len(self._new_keys) != len(set(self._new_keys)):
			raise ValueError('Duplicate rows are not supported')
		self._result = []
	def __call__(self):
		# Using a set for the "contains" check below improves performance 40x:
		new_keys = set(self._new_keys)
		for i in range(len(self._old_keys) - 1, -1, -1):
			if self._old_keys[i] not in new_keys:
				self._remove_row(i)
		# Using a set for the "contains" check below improves performance 40x:
		old_keys = set(self._old_keys)
		for i, new_key in enumerate(self._new_keys):
			if new_key not in old_keys:
				self._insert_row(i, self._new_rows[i])
		for i, new_key in enumerate(self._new_keys):
			if new_key != self._old_keys[i]:
				old_row_index = self._old_keys.index(new_key, i)
				if old_row_index != i:
					self._move_row(old_row_index, i)
			old_row = self._old_rows[i]
			new_row = self._new_rows[i]
			if old_row != new_row:
				self._update_row(i, new_row)
		if self._old_keys != self._new_keys:
			raise AssertionError('%r != %r' % (self._old_keys, self._new_keys))
		return join(self._result)
	def _remove_row(self, i):
		self._result.append(DiffEntry(i, i + 1, -1, []))
		self._old_rows.pop(i)
		self._old_keys.pop(i)
	def _insert_row(self, i, row):
		self._result.append(DiffEntry(-1, -1, i, [row]))
		self._old_rows.insert(i, row)
		self._old_keys.insert(i, self._key_fn(row))
	def _move_row(self, src, dest):
		self._result.append(DiffEntry(src, src + 1, dest, []))
		self._old_rows.insert(dest, self._old_rows.pop(src))
		self._old_keys.insert(dest, self._old_keys.pop(src))
	def _update_row(self, i, row):
		self._result.append(DiffEntry(i, i + 1, i, [row]))
		self._old_rows[i] = row
		assert self._key_fn(row) == self._old_keys[i]

def join(diff_entries):
	if not diff_entries:
		return []
	result = [diff_entries[0]]
	for entry in diff_entries[1:]:
		if not result[-1].extend_by(entry):
			result.append(entry)
	return result

class DiffEntry(ConstructorMixin, EqMixin, ReprMixin):

	_FIELDS = ('cut_start', 'cut_end', 'insert_start', 'rows')

	@classmethod
	def insert(cls, insert_start, rows):
		return cls(-1, -1, insert_start, rows)
	@classmethod
	def update(cls, rownum_start, rows):
		return cls(rownum_start, rownum_start + len(rows), rownum_start, rows)
	@classmethod
	def move(cls, src, dst):
		return cls(src, src + 1, dst, [])
	@classmethod
	def remove(cls, start, end=None):
		if end is None:
			end = start + 1
		return cls(start, end, -1, [])

	def extend_by(self, other):
		type_ = self._type
		other_type = other._type
		if type_ == other_type == 'insert':
			if other.insert_start == self.insert_start + len(self.rows):
				self.rows += other.rows
				return True
		elif type_ == other_type == 'move':
			# Other cut before this one:
			if other.cut_end == self.cut_start \
				and other.insert_start + len(other) == self.insert_start \
				and self.insert_start > other.cut_end:
				self.cut_start = other.cut_start
				self.insert_start = other.insert_start
				return True
			# This cut before other one:
			if self.cut_end == other.cut_start \
				and self.insert_start + len(self) == other.insert_start \
				and self.insert_start < self.cut_start:
				self.cut_end = other.cut_end
				return True
		elif type_ == other_type == 'update':
			if other.cut_start == self.cut_end:
				self.cut_end = other.cut_end
				self.rows += other.rows
				return True
		elif type_ == other_type == 'remove':
			if other.cut_end == self.cut_start:
				self.cut_start = other.cut_start
				return True
		elif type_ == 'remove' and other_type == 'insert':
			if self.cut_start == other.insert_start and \
					self.cut_end == other._insert_end:
				self.insert_start = self.cut_start
				self.rows = other.rows
				return True
		return False
	def apply(self, insert, move, update, remove):
		if self._type == 'insert':
			insert(self.rows, self.insert_start)
		elif self._type == 'move':
			move(self.cut_start, self.cut_end, self.insert_start)
		elif self._type == 'update':
			update(self.rows, self.cut_start)
		elif self._type == 'remove':
			remove(self.cut_start, self.cut_end)
		else:
			raise AssertionError('Unexpected type %r' % self._type)
	@property
	def _type(self):
		if self._does_cut:
			if self.rows:
				assert len(self.rows) == self.cut_end - self.cut_start
				assert self.cut_start == self.insert_start
				return 'update'
			else:
				if self.insert_start != -1:
					return 'move'
				else:
					return 'remove'
		else:
			assert self.rows
			assert self.insert_start != -1
			return 'insert'
	@property
	def _does_cut(self):
		return self.cut_end > self.cut_start
	@property
	def _insert_end(self):
		return self.insert_start + len(self.rows)
	def __len__(self):
		return (self.cut_end - self.cut_start) or len(self.rows)
	def __str__(self):
		t = self._type
		if t == 'update':
			return 'update %d rows, starting at %d' % \
				   (len(self), self.insert_start)
		if t == 'move':
			return 'move %d rows from %d to %d' % \
				   (len(self), self.cut_start, self.insert_start)
		if t == 'remove':
			return 'remove %d rows, starting at %d' % \
				   (len(self), self.cut_start)
		if t == 'insert':
			return 'insert %d rows at %s' % (len(self), self.insert_start)