from json import JSONDecodeError
from os import makedirs
from os.path import dirname

import json

class Settings:
	def __init__(self, json_path):
		self._json_path = json_path
		try:
			with open(self._json_path, 'r') as f:
				self._json_dict = json.load(f)
		except (FileNotFoundError, JSONDecodeError):
			self._json_dict = {}
	def get(self, key, default):
		return self._json_dict.get(key, default)
	def __setitem__(self, key, value):
		self._json_dict[key] = value
	def setdefault(self, key, value):
		return self._json_dict.setdefault(key, value)
	def flush(self):
		makedirs(dirname(self._json_path), exist_ok=True)
		with open(self._json_path, 'w') as f:
			json.dump(self._json_dict, f)
	def __bool__(self):
		return bool(self._json_dict)