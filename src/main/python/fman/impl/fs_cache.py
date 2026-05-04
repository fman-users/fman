from collections import defaultdict
from threading import Lock, RLock

class Cache:
	def __init__(self):
		self._lock = Lock()
		self._root = CacheItem()
	def put(self, path, attr, value):
		with self._lock:
			self._root.update_child(path).put(attr, value)
	def get(self, path, attr):
		with self._lock:
			return self._root.get_child(path).get(attr)
	def query(self, path, attr, compute_value):
		with self._lock:
			item = self._root.update_child(path)
		return item.query(attr, compute_value)
	def clear(self, path):
		with self._lock:
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
		self._attrs = {}
		self._attr_locks = {}
		self._attr_locks_lock = Lock()
	def put(self, attr, value):
		self._attrs[attr] = value
	def get(self, attr):
		return self._attrs[attr]
	def clear_attr(self, attr):
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
