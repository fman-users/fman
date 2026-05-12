from vitraj import PLATFORM
from vitraj_integrationtest.plugin_tests import PluginTest
from os.path import join

import json

class LoadSaveJsonTest(PluginTest):
	def test_load_json_default(self):
		d = {}
		self.assertIs(d, self._plugin_support.load_json('Nonexistent.json', d))
		self.assertIs(d, self._plugin_support.load_json('Nonexistent.json'))
	def test_load_json_dict(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2, 'c': 3}, f)
		with open(join(self._thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump({'b': 'overwritten', 'installed': 1}, f)
		with open(join(self._settings_plugin, 'Test.json'), 'w') as f:
			json.dump({'c': 'overwritten', 'user': 1}, f)
		self.assertEqual(
			{
				'a': 1, 'b': 'overwritten', 'c': 'overwritten',
				'installed': 1, 'user': 1
			},
			self._plugin_support.load_json('Test.json'),
			'Settings plugin should overwrite installed should overwrite '
			'shipped.'
		)
	def test_load_json_list(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump(['shipped'], f)
		with open(join(self._thirdparty_plugin, 'Test.json'), 'w') as f:
			json.dump(['installed'], f)
		with open(join(self._settings_plugin, 'Test.json'), 'w') as f:
			json.dump(['user'], f)
		self.assertEqual(
			['user', 'installed', 'shipped'],
			self._plugin_support.load_json('Test.json')
		)
	def test_load_json_platform_overwrites(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1, 'b': 2}, f)
		json_platform = 'Test (%s).json' % PLATFORM
		with open(join(self._shipped_plugin, json_platform), 'w') as f:
			json.dump({'b': 'overwritten'}, f)
		self.assertEqual(
			{'a': 1, 'b': 'overwritten'},
			self._plugin_support.load_json('Test.json')
		)
	def test_load_json_caches(self):
		with open(join(self._shipped_plugin, 'Test.json'), 'w') as f:
			json.dump({'a': 1}, f)
		d = self._plugin_support.load_json('Test.json')
		self.assertIs(d, self._plugin_support.load_json('Test.json'))
	def test_save_json(self):
		d = {'test_save_json': 1}
		self._plugin_support.save_json('Test.json', d)
		json_platform = join(self._settings_plugin, 'Test (%s).json' % PLATFORM)
		with open(json_platform, 'r') as f:
			self.assertEqual(d, json.load(f))