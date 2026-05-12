from base64 import b64decode
from vitraj.impl.util import parse_version
from rsa import PublicKey, VerificationError
from rsa.common import byte_size as get_byte_size

import json
import rsa

DEACTIVATED_KEYS = ('3amunyk@gmail.com',)

class User:
	def __init__(self, email='', key=''):
		self.email = email
		self.key = key
	def is_licensed(self, fman_version):
		return self.has_license() and \
			   self.license_is_valid_for_curr_version(fman_version)
	def has_license(self):
		if self.email in DEACTIVATED_KEYS:
			return False
		if 'email' not in self._key_data:
			return False
		if self._key_data['email'] != self.email:
			return False
		return True
	def license_is_valid_for_curr_version(self, fman_version):
		max_version = self._key_data.get('max_version', fman_version)
		return parse_version(fman_version) <= parse_version(max_version)
	def is_entitled_to_updates(self):
		return 'max_version' not in self._key_data
	@property
	def _key_data(self):
		try:
			return unpack_key(self.key)
		except ValueError:
			return {}

def unpack_key(key):
	return json.loads(decrypt(key))

def decrypt(data_b64str):
	data = b64decode(data_b64str.encode('ascii'))
	signature_length = get_byte_size(_SIGN_PUB_KEY.n)
	signature, bytes_negated = data[:signature_length], data[signature_length:]
	try:
		rsa.verify(bytes_negated, signature, _SIGN_PUB_KEY)
	except VerificationError:
		raise ValueError('Signature verification failed')
	return _negate(bytes_negated).decode('utf-8')

def _negate(bytes_):
	return bytes(~b % 256 for b in bytes_)

_SIGN_PUB_KEY = PublicKey(146142096601994918206700648259140200952100463274320504063611160294570078501586995967016070398912575192277695142590132973263670517442427130500485732664894774182275447661818963467005949739008288209651168713547437071057019064692363086596546730713984877667901498460512867391678806498712503463981815559532208736523, 65537)