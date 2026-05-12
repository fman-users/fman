from vitraj import PLATFORM
from vitraj.impl.plugins.config import load_json, write_differential_json, Config
from vitraj_integrationtest import get_resource
from os.path import join, exists
from shutil import rmtree, copy
from tempfile import mkdtemp
from unittest import TestCase

import json

class ConfigTest(TestCase):
	def test_add_dir(self):
		self._config.add_dir(self._dir_1)
		self.assertEqual([1], self._config.load_json('Test.json'))
	def test_add_dir_updates_existing(self):
		self._config.add_dir(self._dir_1)
		value = self._config.load_json('Test.json')
		self.assertEqual([1], value)
		self._config.add_dir(self._dir_2)
		self.assertIs(value, self._config.load_json('Test.json'))
		self.assertEqual([2, 1], value)
	def test_remove_add_dir(self):
		self._config.add_dir(self._dir_1)
		self.assertEqual([1], self._config.load_json('Test.json'))
		self._config.remove_dir(self._dir_1)
		self.assertIsNone(self._config.load_json('Test.json'))
		self._config.add_dir(self._dir_2)
		self.assertEqual([2], self._config.load_json('Test.json'))
	def test_save_on_quit_nonexistent(self):
		value = self._config.load_json(
			'Nonexistent.json', default=[], save_on_quit=True
		)
		value.append(3)
		self._config.add_dir(self._dir_1)
		self._config.on_quit()
		config = Config(PLATFORM)
		config.add_dir(self._dir_1)
		self.assertEqual(value, config.load_json('Nonexistent.json'))
	def setUp(self):
		super().setUp()
		self._dir_1 = mkdtemp()
		copy(get_resource('ConfigTest/1/Test.json'), self._dir_1)
		self._dir_2 = mkdtemp()
		copy(get_resource('ConfigTest/2/Test.json'), self._dir_2)
		self._config = Config(PLATFORM)
	def tearDown(self):
		rmtree(self._dir_1)
		rmtree(self._dir_2)
		super().tearDown()

class LoadJsonTest(TestCase):
	def test_nonexistent_file(self):
		self.assertIsNone(load_json(['non-existent']))
	def test_dict(self):
		d = {'a': 1, 'b': 1}
		json_path = self._save_to_json(d)
		self.assertEqual(d, load_json([json_path]))
	def test_dict_multiple_files(self):
		d1 = {'a': 1, 'b': 1}
		d2 = {'b': 2, 'c': 2}
		json1 = self._save_to_json(d1)
		json2 = self._save_to_json(d2)
		self.assertEqual({'a': 1, 'b': 2, 'c': 2}, load_json([json1, json2]))
	def test_list(self):
		l = [1, 2]
		json_path = self._save_to_json(l)
		self.assertEqual(l, load_json([json_path]))
	def test_list_multiple_files(self):
		l1 = [1, 2]
		l2 = [3]
		json1 = self._save_to_json(l1)
		json2 = self._save_to_json(l2)
		self.assertEqual(l2 + l1, load_json([json1, json2]))
	def test_string(self):
		string = 'test'
		json_path = self._save_to_json(string)
		self.assertEqual(string, load_json([json_path]))
	def test_string_multiple_files(self):
		s1 = 'test1'
		s2 = 'test2'
		json1 = self._save_to_json(s1)
		json2 = self._save_to_json(s2)
		self.assertEqual(s2, load_json([json2, json1]))
	def test_multiple_files_first_does_not_exist(self):
		value = {'a': 1}
		json_path = self._save_to_json(value)
		self.assertEqual(value, load_json(['non-existent', json_path]))
	def setUp(self):
		self.temp_dir = mkdtemp()
		self.num_files = 0
	def tearDown(self):
		rmtree(self.temp_dir)
	def _save_to_json(self, value):
		json_path = join(self.temp_dir, '%d.json' % self.num_files)
		with open(json_path, 'w') as f:
			json.dump(value, f)
		self.num_files += 1
		return json_path

class WriteDifferentialJsonTest(TestCase):
	def test_dict(self):
		self._check_write({'a': 1})
	def test_list(self):
		self._check_write([1, 2])
	def test_string(self):
		self._check_write("hello!")
	def test_int(self):
		self._check_write(3)
	def test_bool(self):
		self._check_write(True)
	def test_float(self):
		self._check_write(4.5)
	def test_overwrite_dict_value(self):
		d = {'a': 1, 'b': 1}
		with open(self._json_file(), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		self._check_write(d)
	def test_dict_incremental_update(self):
		d = {'a': 1, 'b': 1}
		with open(self._json_file(0), 'w') as f:
			json.dump(d, f)
		d['b'] = 2
		d['c'] = 3
		write_differential_json(d, [self._json_file(0)], self._json_file(1))
		with open(self._json_file(1), 'r') as f:
			self.assertEqual({'b': 2, 'c': 3}, json.load(f))
	def test_extend_list(self):
		write_differential_json([1, 2], [], self._json_file())
		self._check_write([1, 2, 3])
	def test_update_list(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		with open(json1, 'w') as f:
			json.dump([2, 3], f)
		with open(json2, 'w') as f:
			json.dump([1], f)
		write_differential_json([0, 1, 2, 3], [json1], json2)
		with open(json2, 'r') as f:
			self.assertEqual([0, 1], json.load(f))
	def test_type_change_raises(self):
		write_differential_json(1, [], self._json_file())
		with self.assertRaises(ValueError):
			write_differential_json({'x': 1}, [], self._json_file())
	def test_update_unmodifiable_list_parts_raises(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		with open(json1, 'w') as f:
			json.dump([1], f)
		with open(json2, 'w') as f:
			json.dump([2], f)
		with self.assertRaises(ValueError):
			write_differential_json(json1, [], json2)
	def test_no_change(self):
		json1 = self._json_file(0)
		l = [0, 1]
		with open(json1, 'w') as f:
			json.dump(l, f)
		json2 = self._json_file(1)
		write_differential_json(l, [json1], json2)
		self.assertFalse(exists(json2))
	def test_delete_dict_key_same_file_ok(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		write_differential_json({'a': 1}, [], json1)
		write_differential_json({'a': 1, 'b': 2}, [json1], json2)
		write_differential_json({'a': 1}, [json1], json2)
	def test_delete_dict_key_different_file_raises(self):
		json1 = self._json_file(0)
		json2 = self._json_file(1)
		write_differential_json({'a': 1}, [], json1)
		write_differential_json({'a': 1, 'b': 2}, [json1], json2)
		with self.assertRaises(ValueError):
			write_differential_json({'b': 2}, [json1], json2)
	def setUp(self):
		self.temp_dir = mkdtemp()
	def tearDown(self):
		rmtree(self.temp_dir)
	def _check_write(self, obj):
		write_differential_json(obj, [], self._json_file())
		self.assertEqual(obj, load_json([self._json_file()]))
	def _json_file(self, i=0):
		return join(self.temp_dir, '%d.json' % i)