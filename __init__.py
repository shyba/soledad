# License?

"""A U1DB implementation for using Object Stores as its persistence layer."""

import os
import string
import random
import cStringIO
from soledad.util import GPGWrapper

class Soledad(object):

    PREFIX        = os.environ['HOME']  + '/.config/leap/soledad'
    SECRET_PATH   = PREFIX + '/secret.gpg'
    GNUPG_HOME    = PREFIX + '/gnupg'
    SECRET_LENGTH = 50

    def __init__(self, user_email, gpghome=None):
        self._user_email = user_email
        if not os.path.isdir(self.PREFIX):
            os.makedirs(self.PREFIX)
        if not gpghome:
            gpghome = self.GNUPG_HOME
        self._gpg = GPGWrapper(gpghome=gpghome)
        # load OpenPGP keypair
        if not self._has_openpgp_keypair():
            self._gen_openpgp_keypair()
        self._load_openpgp_keypair()
        # load secret
        if not self._has_secret():
            self._gen_secret()
        self._load_secret()

    def _has_secret(self):
        if os.path.isfile(self.SECRET_PATH):
            return True
        return False

    def _load_secret(self):
        try:
            with open(self.SECRET_PATH) as f:
               self._secret = self._gpg.decrypt(f.read())
        except IOError as e:
           raise IOError('Failed to open secret file %s.' % self.SECRET_PATH)

    def _gen_secret(self):
        self._secret = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(self.SECRET_LENGTH))
        cyphertext = self._gpg.encrypt(self._secret, self._fingerprint, self._fingerprint)
        f = open(self.SECRET_PATH, 'w')
        f.write(str(cyphertext))
        f.close()


    def _has_openpgp_keypair(self):
        if self._gpg.find_key(self._user_email):
            return True
        return False

    def _gen_openpgp_keypair(self):
        params = self._gpg.gen_key_input(
          key_type='RSA',
          key_length=4096,
          name_real=self._user_email,
          name_email=self._user_email,
          name_comment='Generated by LEAP Soledad.')
        self._gpg.gen_key(params)

    def _load_openpgp_keypair(self):
        self._fingerprint = self._gpg.find_key(self._user_email)['fingerprint']

    def encrypt(self, data, sign=None, passphrase=None, symmetric=False):
        return str(self._gpg.encrypt(data, self._fingerprint, sign=sign,
                                     passphrase=passphrase, symmetric=symmetric))

    def encrypt_symmetric(self, data, sign=None):
        return self.encrypt(data, sign=sign, passphrase=self._secret,
                            symmetric=True)

    def decrypt(self, data, passphrase=None, symmetric=False):
        return str(self._gpg.decrypt(data, passphrase=passphrase))

    def decrypt_symmetric(self, data):
        return self.decrypt(data, passphrase=self._secret)
