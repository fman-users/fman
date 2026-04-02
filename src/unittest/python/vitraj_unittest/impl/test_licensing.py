from base64 import b64encode
from vitraj.impl.licensing import User, _negate, decrypt
from rsa import PrivateKey
from unittest import TestCase

import json
import rsa

class UserTest(TestCase):
	def test_no_email(self):
		user = User()
		self.assertFalse(user.is_licensed('0.2.9'))
		self.assertTrue(user.is_entitled_to_updates())
	def test_no_key(self):
		user = User('michael@herrmann.io')
		self.assertFalse(user.is_licensed('0.2.9'))
		self.assertTrue(user.is_entitled_to_updates())
	def test_licensed(self):
		user = self._create_licensed_user('michael@herrmann.io')
		self.assertTrue(user.is_licensed('0.2.9'))
		self.assertTrue(user.is_entitled_to_updates())
		self.assertTrue(user.is_entitled_to_updates())
	def test_licensed_max_version(self):
		user = self._create_licensed_user('michael@herrmann.io', '0.2.9')
		self.assertTrue(user.is_licensed('0.2.9'))
		self.assertFalse(user.is_licensed('0.3.0'))
		self.assertFalse(user.is_entitled_to_updates())
	def _create_licensed_user(self, email, max_version=None):
		key_kwargs = {'email': email}
		if max_version:
			key_kwargs['max_version'] = max_version
		return User(email, generate_key(**key_kwargs))

class EncryptionTest(TestCase):
	def test_simple(self):
		text = '{"email": "michael@herrmann.io"}' * 1000
		self.assertEqual(text, decrypt(encrypt(text)))

def generate_key(**kwargs):
	return pack_key(kwargs)

def pack_key(data):
	return encrypt(json.dumps(
		data,
		# Ensure the output is deterministic:
		sort_keys=True
	))

def encrypt(text):
	bytes_ = text.encode('utf-8')
	bytes_negated = _negate(bytes_)
	signature = rsa.sign(bytes_negated, _SIGN_PRIV_KEY, 'SHA-1')
	return b64encode(signature + bytes_negated).decode('ascii')

_SIGN_PRIV_KEY = PrivateKey(146142096601994918206700648259140200952100463274320504063611160294570078501586995967016070398912575192277695142590132973263670517442427130500485732664894774182275447661818963467005949739008288209651168713547437071057019064692363086596546730713984877667901498460512867391678806498712503463981815559532208736523, 65537, 106496395158735879025826778149137398981802858309885997727542331711065166380499439299826868640787139570514337925443941140685816814501967360398586982170748237192314350435576220165300696469415364990182400579393918168894154764719809140330404245768708165575118557585084513541133385899426977724563946441819272561953, 53814768570805402343382108978014344824260175208379647909206093545673396247171146482415406423611088539769948553707220783902125888028734883241844600109457389608612643, 2715650377827272462961221898973150292742268179788405438319789816103372507158845181548791073053845916750266308833132757067659526868002609335207161)