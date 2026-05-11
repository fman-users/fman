from fman.impl.view.thumbnails import format_human_size
from unittest import TestCase


class FormatHumanSizeTest(TestCase):

	def test_bytes(self):
		self.assertEqual('0 B', format_human_size(0))
		self.assertEqual('512 B', format_human_size(512))

	def test_kilobytes(self):
		self.assertEqual('1.0 KB', format_human_size(1024))
		self.assertEqual('1.5 KB', format_human_size(1536))

	def test_megabytes(self):
		self.assertEqual('4.2 MB', format_human_size(4_404_019))  # 4.2 * 1024^2

	def test_gigabytes(self):
		self.assertEqual('2.3 GB', format_human_size(2_469_606_195))

	def test_rounds_to_one_decimal(self):
		self.assertEqual('1.0 MB', format_human_size(1024 * 1024))


from fman.impl.view.thumbnails import (
	cache_key, pick_size_bucket, SIZE_BUCKETS
)


class CacheKeyTest(TestCase):

	def test_returns_hex_sha1(self):
		key = cache_key('/tmp/img.jpg', 1234567890, 256)
		self.assertEqual(40, len(key))   # SHA1 hex = 40 chars
		self.assertTrue(all(c in '0123456789abcdef' for c in key))

	def test_same_inputs_same_key(self):
		k1 = cache_key('/tmp/img.jpg', 1234567890, 256)
		k2 = cache_key('/tmp/img.jpg', 1234567890, 256)
		self.assertEqual(k1, k2)

	def test_mtime_invalidates(self):
		k1 = cache_key('/tmp/img.jpg', 1, 256)
		k2 = cache_key('/tmp/img.jpg', 2, 256)
		self.assertNotEqual(k1, k2)

	def test_path_changes_key(self):
		k1 = cache_key('/tmp/img1.jpg', 1, 256)
		k2 = cache_key('/tmp/img2.jpg', 1, 256)
		self.assertNotEqual(k1, k2)

	def test_bucket_changes_key(self):
		k1 = cache_key('/tmp/img.jpg', 1, 128)
		k2 = cache_key('/tmp/img.jpg', 1, 256)
		self.assertNotEqual(k1, k2)


class PickSizeBucketTest(TestCase):

	def test_buckets_are_128_256_512(self):
		self.assertEqual((128, 256, 512), SIZE_BUCKETS)

	def test_smallest_request_uses_128(self):
		self.assertEqual(128, pick_size_bucket(80))
		self.assertEqual(128, pick_size_bucket(128))

	def test_picks_nearest_larger_bucket(self):
		self.assertEqual(256, pick_size_bucket(129))
		self.assertEqual(256, pick_size_bucket(200))
		self.assertEqual(256, pick_size_bucket(256))

	def test_above_max_uses_max(self):
		self.assertEqual(512, pick_size_bucket(513))
		self.assertEqual(512, pick_size_bucket(2048))
