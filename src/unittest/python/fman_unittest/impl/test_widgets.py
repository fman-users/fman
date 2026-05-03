from unittest import TestCase

import struct

class SaveRestoreStateTest(TestCase):
	def test_roundtrip_small_state(self):
		self_state = b'\x01\x02\x03'
		splitter_state = b'\x04\x05'
		combined = self_state + splitter_state + struct.pack('<I', len(self_state))
		self_state_len = struct.unpack('<I', combined[-4:])[0]
		self.assertEqual(3, self_state_len)
		self.assertEqual(self_state, combined[0:self_state_len])
		self.assertEqual(splitter_state, combined[self_state_len:-4])
	def test_roundtrip_large_state(self):
		self_state = bytes(range(256)) * 4
		splitter_state = b'\xff' * 100
		combined = self_state + splitter_state + struct.pack('<I', len(self_state))
		self_state_len = struct.unpack('<I', combined[-4:])[0]
		self.assertEqual(1024, self_state_len)
		self.assertEqual(self_state, combined[0:self_state_len])
		self.assertEqual(splitter_state, combined[self_state_len:-4])
	def test_state_over_255_bytes(self):
		self_state = b'\xab' * 300
		packed = struct.pack('<I', len(self_state))
		self.assertEqual(4, len(packed))
		self.assertEqual(300, struct.unpack('<I', packed)[0])
	def test_empty_splitter_state(self):
		self_state = b'\x01\x02'
		splitter_state = b''
		combined = self_state + splitter_state + struct.pack('<I', len(self_state))
		self_state_len = struct.unpack('<I', combined[-4:])[0]
		self.assertEqual(self_state, combined[0:self_state_len])
		self.assertEqual(b'', combined[self_state_len:-4])
