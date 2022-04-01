"""
This file is from https://github.com/Dr-Bluemond/BuaaBykcCrawler.
"""

from urllib import parse as _parse
import re as _re
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, padding, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
import random

b64encode = base64.b64encode
b64decode = base64.b64decode

encodeURIComponent = _parse.quote
decodeURIComponent = _parse.unquote

def escape(s : str):
    chars = []
    for c in s:
        _c = ord(c)
        if _c > 255:
            _cs = []
            while _c:
                _cs.append(_c & 255)
                _c >>= 8
            cs = '%u' + ''.join(map(lambda x: hex(x)[2:].upper(), reversed(_cs)))
            chars.append(cs)
        else:
            chars.append(_parse.quote(c, encoding='latin1'))
    return ''.join(chars)

def unescape(s : str):
    matches = _re.finditer(r'%u([A-Fa-f0-9]{4})', s)
    start_index = 0
    indexes = []
    for match in matches:
        indexes.append((start_index, match.start(0), chr(int(match.group(1), base=16))))
        start_index = match.end(0)
    _s = []
    for start, end, c in indexes:
        _s.append(s[start : end])
        _s.append(c)
    _s.append(s[start_index :])
    return _parse.unquote(''.join(_s), encoding='latin1')

RSA_PUBLIC_KEY = b"MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDlHMQ3B5GsWnCe7Nlo1YiG/YmHdlOiKOST5aRm4iaqYSvhvWmwcigoyWTM+8bv2+sf6nQBRDWTY4KmNV7DBk1eDnTIQo6ENA31k5/tYCLEXgjPbEjCK9spiyB62fCT6cqOhbamJB0lcDJRO6Vo1m3dy+fD0jbxfDVBBNtyltIsDQIDAQAB"

public_key = serialization.load_der_public_key(base64.b64decode(RSA_PUBLIC_KEY), backend=default_backend())

def generate_aes_key() -> bytes:
    return "".join(
        [random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(16)]
    ).encode()

def aes_encrypt(message: bytes, key: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    padded_message = padder.update(message) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()

    encrypted_message = encryptor.update(padded_message) + encryptor.finalize()
    return encrypted_message

def aes_decrypt(message: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()

    decrypted_message = decryptor.update(message) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    unpadded_message = unpadder.update(decrypted_message) + unpadder.finalize()
    return unpadded_message

def sign(message: bytes) -> bytes:
    digist = hashes.Hash(hashes.SHA1(), backend=default_backend())
    digist.update(message)
    return base64.b16encode(digist.finalize()).lower()

def rsa_encrypt(message: bytes) -> bytes:
    encrypted = public_key.encrypt(message, asymmetric_padding.PKCS1v15())
    return base64.b64encode(encrypted)

