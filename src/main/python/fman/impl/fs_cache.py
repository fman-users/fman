# Lock ordering (acquire top-to-bottom, never invert):
#   Cache._lock
#     CacheItem._children_lock (per-node, parent before child)
#       CacheItem._attr_locks_lock (per-node)
#         CacheItem attr RLock (per-attr)
# Cache._lock must NOT be held when calling compute_value in query(),
# because compute_value may trigger nested cache operations.
from threading import Lock, RLock

class Cache:
	def __init__(self):
		self._lock = Lock()
		self._root = CacheItem()
		self._generation = 0
	def put(self, path, attr, value):
		with self._lock:
			self._root.update_child(path).put(attr, value)
	def get(self, path, attr):
		with self._lock:
			return self._root.get_child(path).get(attr)
	def query(self, path, attr, compute_value):
		while True:
			with self._lock:
				gen = self._generation
				item = self._root.update_child(path)
			result = item.query(attr, compute_value)
			with self._lock:
				if self._generation == gen:
					return result
			item.clear_attr(attr)
	def mutate(self, path, attr, fn):
		with self._lock:
			try:
				item = self._root.get_child(path)
				value = item.get(attr)
			except KeyError:
				return
			fn(value)
	def clear(self, path):
		with self._lock:
			self._generation += 1
			if not path:
				self._root = CacheItem()
			else:
				try:
					self._root.delete_child(path)
				except KeyError:
					pass
	def clear_attr(self, path, attr):
		with self._lock:
			try:
				item = self._root.get_child(path)
			except KeyError:
				return
			item.clear_attr(attr)

class CacheItem:
	def __init__(self):
		self._children = {}
		self._children_lock = Lock()
		self._attrs = {}
		self._attr_locks_lock = Lock()
		self._attr_locks = {}
	def put(self, attr, value):
		with self._attr_locks_lock:
			if attr not in self._attr_locks:
				self._attr_locks[attr] = RLock()
			lock = self._attr_locks[attr]
		with lock:
			self._attrs[attr] = value
	def get(self, attr):
		return self._attrs[attr]
	def clear_attr(self, attr):
		with self._attr_locks_lock:
			lock = self._attr_locks.pop(attr, None)
		if lock:
			with lock:
				self._attrs.pop(attr, None)
		else:
			self._attrs.pop(attr, None)
	def query(self, attr, compute_value):
		with self._attr_locks_lock:
			if attr not in self._attr_locks:
				self._attr_locks[attr] = RLock()
			lock = self._attr_locks[attr]
		with lock:
			try:
				return self._attrs[attr]
			except KeyError:
				result = self._attrs[attr] = compute_value()
				return result
	def get_child(self, path):
		children = self._children
		for part in path.split('/'):
			child = children[part]
			children = child._children
		return child
	def update_child(self, path):
		children = self._children
		for part in path.split('/'):
			try:
				child = children[part]
			except KeyError:
				child = children[part] = CacheItem()
			children = child._children
		return child
	def delete_child(self, path):
		parts = path.split('/', 1)
		if len(parts) == 1:
			del self._children[parts[0]]
		else:
			self._children[parts[0]].delete_child(parts[1])
