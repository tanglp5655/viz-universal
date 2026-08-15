# -*- coding: utf-8 -*-
"""
sales-viz-secure · 加密核心（Python 端）

算法：SHA256-KDF + SHA256-CTR 流加密
  salt      = 16 随机字节
  K0        = SHA256(utf8(password) || salt)
  Ki        = SHA256(K(i-1) || salt)          i = 1..N-1
  key       = K(N-1)                          （N = iterations，默认 120000）
  verifier  = SHA256(key || utf8("verify"))   取前 8 字节 hex，用于快速校验密码
  keystream = SHA256(key || u32be(j))         j = 0,1,2,...  每块 32 字节
  cipher[i] = plain[i] XOR keystream[i]

设计取舍：
  - 不用 AES-GCM/Web Crypto，因为浏览器在 file:// 协议下 crypto.subtle 不可用，
    双击打开本地 HTML 会直接失效。纯 SHA256 构造可用纯 JS 实现，本地/手机/网页全兼容。
  - 12 万次迭代派生使暴力破解成本约提高 10^5 倍，配合非弱密码足以防止
    "别人拿到 HTML 文件查看源码就看到全部数据"。
  - 这是"防偷看"级别的保护，不是国密/金融级加密。真正机密数据请勿外发。
"""
import base64
import hashlib
import os
import struct

DEFAULT_ITERATIONS = 120000


def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    """迭代 SHA256 派生 32 字节密钥"""
    h = hashlib.sha256(password.encode('utf-8') + salt).digest()
    for _ in range(iterations - 1):
        h = hashlib.sha256(h + salt).digest()
    return h


def make_verifier(key: bytes) -> str:
    """密码校验串（前 8 字节 hex）"""
    return hashlib.sha256(key + b'verify').hexdigest()[:16]


def keystream(key: bytes, nbytes: int) -> bytes:
    out = bytearray()
    j = 0
    while len(out) < nbytes:
        out += hashlib.sha256(key + struct.pack('>I', j)).digest()
        j += 1
    return bytes(out[:nbytes])


def encrypt_text(plain_text: str, password: str, iterations: int = DEFAULT_ITERATIONS) -> dict:
    """加密 UTF-8 文本，返回可直接嵌入 HTML 的字典"""
    salt = os.urandom(16)
    key = derive_key(password, salt, iterations)
    data = plain_text.encode('utf-8')
    ks = keystream(key, len(data))
    cipher = bytes(a ^ b for a, b in zip(data, ks))
    return {
        'v': 1,
        'salt': salt.hex(),
        'iter': iterations,
        'verify': make_verifier(key),
        'ct': base64.b64encode(cipher).decode('ascii'),
    }


def decrypt_payload(payload: dict, password: str) -> str:
    """解密（用于 Python 端自测）"""
    salt = bytes.fromhex(payload['salt'])
    key = derive_key(password, salt, payload['iter'])
    if make_verifier(key) != payload['verify']:
        raise ValueError('密码错误')
    cipher = base64.b64decode(payload['ct'])
    ks = keystream(key, len(cipher))
    return bytes(a ^ b for a, b in zip(cipher, ks)).decode('utf-8')


if __name__ == '__main__':
    p = encrypt_text('{"hello":"世界"}', 'test1234', iterations=1000)
    print(p['verify'], p['ct'][:32])
    print(decrypt_payload(p, 'test1234'))
