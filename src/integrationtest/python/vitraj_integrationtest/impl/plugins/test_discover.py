from vitraj.impl.plugins import SETTINGS_PLUGIN_NAME
from vitraj.impl.plugins.discover import find_plugin_dirs
from os import mkdir
from os.path import join, basename
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

class FindPluginDirsTest(TestCase):
	def test_find_plugins(self):
		plugin_dirs = \
			[self.shipped_plugin, self.thirdparty_plugin, self.settings_plugin]
		for plugin_dir in plugin_dirs:
			mkdir(plugin_dir)
		self.assertEqual(
			plugin_dirs,
			find_plugin_dirs(
				self.shipped_plugins, self.thirdparty_plugins, self.user_plugins
			)
		)
	def test_find_plugins_no_settings_plugin(self):
		mkdir(self.shipped_plugin)
		mkdir(self.thirdparty_plugin)
		self.assertEqual(
			[self.shipped_plugin, self.thirdparty_plugin, self.settings_plugin],
			find_plugin_dirs(
				self.shipped_plugins, self.thirdparty_plugins, self.user_plugins
			)
		)
	def setUp(self):
		self.shipped_plugins = mkdtemp()
		self.thirdparty_plugins = mkdtemp()
		self.user_plugins = mkdtemp()
		self.shipped_plugin = join(self.shipped_plugins, 'Shipped')
		thirdparty_plugin = 'Very Simple Plugin'
		assert basename(thirdparty_plugin)[0] > SETTINGS_PLUGIN_NAME[0], \
			"Please ensure that the name of the third-party plugin appears in" \
			"listdir(...) _after_ the Settings plugin. This lets us test that" \
			"find_plugins(...) does not simply return plugins in the same " \
			"order as listdir(...) but ensures that the Settings plugin " \
			"appears last."
		self.thirdparty_plugin = \
			join(self.thirdparty_plugins, thirdparty_plugin)
		self.settings_plugin = join(self.user_plugins, SETTINGS_PLUGIN_NAME)
	def tearDown(self):
		rmtree(self.shipped_plugins)
		rmtree(self.thirdparty_plugins)
		rmtree(self.user_plugins)