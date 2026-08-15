/* sales-viz-secure · 浏览器端解密（纯 JS，file:// 亦可用，不依赖 Web Crypto） */
var SVS = (function () {
  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];
  /* 复用缓冲区，避免 12 万次派生产生大量临时对象 */
  var W = new Uint32Array(64);
  var H = new Uint32Array(8);
  var BLK = new Uint8Array(64);
  var BDV = new DataView(BLK.buffer);

  function block(dv, off) {
    var t, x, y, s0, s1;
    for (t = 0; t < 16; t++) W[t] = dv.getUint32(off + (t << 2));
    for (t = 16; t < 64; t++) {
      x = W[t - 15]; y = W[t - 2];
      s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
      s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) >>> 0;
    }
    var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
    for (t = 0; t < 64; t++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[t] + W[t]) >>> 0;
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0; H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0; H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
  }

  /* 计算 SHA-256，结果写入 out（Uint8Array(32)） */
  function sha256Into(msg, out) {
    H[0] = 0x6a09e667; H[1] = 0xbb67ae85; H[2] = 0x3c6ef372; H[3] = 0xa54ff53a;
    H[4] = 0x510e527f; H[5] = 0x9b05688c; H[6] = 0x1f83d9ab; H[7] = 0x5be0cd19;
    var l = msg.length, i;
    if (l <= 55) {                       // 单块快路径（本项目所有调用都走这里）
      for (i = 0; i < 64; i++) BLK[i] = 0;
      BLK.set(msg);
      BLK[l] = 0x80;
      BDV.setUint32(56, 0);
      BDV.setUint32(60, l * 8);
      block(BDV, 0);
    } else {                             // 通用多块路径
      var blocks = ((l + 9 + 63) / 64) | 0, total = blocks * 64;
      var m = new Uint8Array(total);
      m.set(msg); m[l] = 0x80;
      var dv = new DataView(m.buffer);
      var bits = l * 8;
      dv.setUint32(total - 8, Math.floor(bits / 4294967296));
      dv.setUint32(total - 4, bits >>> 0);
      for (i = 0; i < blocks; i++) block(dv, i << 6);
    }
    for (i = 0; i < 8; i++) {
      var v = H[i], j = i << 2;
      out[j] = v >>> 24; out[j + 1] = (v >>> 16) & 255; out[j + 2] = (v >>> 8) & 255; out[j + 3] = v & 255;
    }
    return out;
  }
  function sha256(msg) { return sha256Into(msg, new Uint8Array(32)); }

  function utf8Bytes(str) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str);
    var esc = unescape(encodeURIComponent(str)), a = new Uint8Array(esc.length);
    for (var i = 0; i < esc.length; i++) a[i] = esc.charCodeAt(i);
    return a;
  }
  function utf8Str(bytes) {
    if (typeof TextDecoder !== 'undefined') return new TextDecoder('utf-8').decode(bytes);
    var s = '';
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return decodeURIComponent(escape(s));
  }
  function hexBytes(hex) {
    var a = new Uint8Array(hex.length / 2);
    for (var i = 0; i < a.length; i++) a[i] = parseInt(hex.substr(i * 2, 2), 16);
    return a;
  }
  function toHex(bytes) {
    var s = '';
    for (var i = 0; i < bytes.length; i++) s += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    return s;
  }
  function concat(a, b) {
    var c = new Uint8Array(a.length + b.length);
    c.set(a); c.set(b, a.length);
    return c;
  }
  function b64Bytes(b64) {
    var bin = atob(b64), a = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
    return a;
  }

  /* 分片派生，避免长时间阻塞 UI；onProgress(0..1) */
  function deriveKey(password, saltHex, iterations, onProgress) {
    return new Promise(function (resolve) {
      var salt = hexBytes(saltHex);
      var buf = new Uint8Array(32 + salt.length);
      buf.set(salt, 32);
      var cur = new Uint8Array(32), nxt = new Uint8Array(32);
      sha256Into(concat(utf8Bytes(password), salt), cur);
      var i = 1, CHUNK = 6000;
      function step() {
        var end = Math.min(i + CHUNK, iterations);
        for (; i < end; i++) {
          buf.set(cur, 0);
          sha256Into(buf, nxt);
          var t = cur; cur = nxt; nxt = t;
        }
        if (onProgress) onProgress(i / iterations);
        if (i < iterations) setTimeout(step, 0);
        else resolve(new Uint8Array(cur));
      }
      setTimeout(step, 0);
    });
  }

  function verify(key, expect) {
    return toHex(sha256(concat(key, utf8Bytes('verify')))).substr(0, 16) === expect;
  }

  function decrypt(key, ctB64) {
    var cipher = b64Bytes(ctB64);
    var out = new Uint8Array(cipher.length);
    var buf = new Uint8Array(36), ks = new Uint8Array(32);
    buf.set(key, 0);
    var j = 0, pos = 0;
    while (pos < cipher.length) {
      buf[32] = (j >>> 24) & 255; buf[33] = (j >>> 16) & 255; buf[34] = (j >>> 8) & 255; buf[35] = j & 255;
      sha256Into(buf, ks);
      for (var k = 0; k < 32 && pos < cipher.length; k++, pos++) out[pos] = cipher[pos] ^ ks[k];
      j++;
    }
    return utf8Str(out);
  }

  /* 主入口：Promise<明文>，密码错误 reject('BADPW') */
  function unlock(payload, password, onProgress) {
    return deriveKey(password, payload.salt, payload.iter, onProgress).then(function (key) {
      if (!verify(key, payload.verify)) throw 'BADPW';
      return decrypt(key, payload.ct);
    });
  }

  return { sha256: sha256, unlock: unlock };
})();
