from collections import defaultdict
from threading import Lock

class Cache:
	def __init__(self):
		self._root = CacheItem()
	def put(self, path, attr, value):
		self._root.update_child(path).put(attr, value)
	def get(self, path, attr):
		return self._root.get_child(path).get(attr)
	def query(self, path, attr, compute_value):
		return self._root.update_child(path).query(attr, compute_value)
	def clear(self, path):
		if not path:
			self._root = CacheItem()
		else:
			try:
				self._root.delete_child(path)
			except KeyError:
				pass

class CacheItem:
	def __init__(self):
		self._children = {}
		self._attrs = {}
		self._attr_locks = defaultdict(Lock)
	def put(self, attr, value):
		self._attrs[attr] = value
	def get(self, attr):
		return self._attrs[attr]
	def query(self, attr, compute_value):
		# Because `defaultdict` and `Lock` are implemented in C, they do not
		# release the GIL and the dict access is atomic:
		with self._attr_locks[attr]:
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