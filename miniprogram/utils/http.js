const { BASE_URL } = require('./config');

/** 流式 UTF-8 解码：处理分块把中文字符切成两半的情况 */
function createUtf8Decoder() {
  let pending = new Uint8Array(0);

  function decode(bytes) {
    let out = '';
    let i = 0;
    while (i < bytes.length) {
      const b = bytes[i++];
      if (b < 0x80) {
        out += String.fromCharCode(b);
      } else if (b < 0xe0) {
        out += String.fromCharCode(((b & 0x1f) << 6) | (bytes[i++] & 0x3f));
      } else if (b < 0xf0) {
        out += String.fromCharCode(
          ((b & 0x0f) << 12) | ((bytes[i++] & 0x3f) << 6) | (bytes[i++] & 0x3f)
        );
      } else {
        const cp =
          ((b & 0x07) << 18) |
          ((bytes[i++] & 0x3f) << 12) |
          ((bytes[i++] & 0x3f) << 6) |
          (bytes[i++] & 0x3f);
        const v = cp - 0x10000;
        out += String.fromCharCode(0xd800 + (v >> 10), 0xdc00 + (v & 0x3ff));
      }
    }
    return out;
  }

  return function push(arrayBuffer) {
    const incoming = new Uint8Array(arrayBuffer);
    const buf = new Uint8Array(pending.length + incoming.length);
    buf.set(pending);
    buf.set(incoming, pending.length);

    let cut = buf.length;
    let i = buf.length - 1;
    while (i >= 0 && (buf[i] & 0xc0) === 0x80) i -= 1;
    if (i >= 0) {
      const lead = buf[i];
      const need = lead < 0x80 ? 1 : lead < 0xe0 ? 2 : lead < 0xf0 ? 3 : 4;
      if (buf.length - i < need) cut = i;
    }

    pending = buf.slice(cut);
    return decode(buf.subarray(0, cut));
  };
}

/** SSE 增量解析：按 \n\n 切事件块，取 data: 行 */
function createSseParser(onEvent) {
  let buffer = '';
  return function push(text) {
    buffer += text;
    let idx = buffer.indexOf('\n\n');
    while (idx >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = block.split('\n').filter((l) => l.indexOf('data:') === 0)[0];
      if (line) {
        const payload = line.slice(5).trim();
        if (payload) {
          try {
            onEvent(JSON.parse(payload));
          } catch (e) {
            // 半包忽略
          }
        }
      }
      idx = buffer.indexOf('\n\n');
    }
  };
}

function requestJSON(method, path, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header: { 'content-type': 'application/json' },
      timeout: 20000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(new Error((res.data && res.data.detail) || 'HTTP ' + res.statusCode));
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络异常'));
      },
    });
  });
}

function uploadFile(filePath, name, sessionId) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE_URL + '/api/upload',
      filePath,
      name: 'file',
      header: { 'x-session-id': sessionId || '' },
      timeout: 120000,
      success(res) {
        let body = {};
        try {
          body = JSON.parse(res.data);
        } catch (e) {
          reject(new Error('上传返回解析失败'));
          return;
        }
        if (res.statusCode >= 400) {
          reject(new Error(body.detail || '上传失败'));
          return;
        }
        resolve(body);
      },
      fail(err) {
        reject(new Error(err.errMsg || '上传失败'));
      },
    });
  });
}

/**
 * 语音转文字：把录音文件传给后端 /api/asr。
 */
function uploadAudio(filePath) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: BASE_URL + '/api/asr',
      filePath,
      name: 'file',
      timeout: 60000,
      success(res) {
        let body = {};
        try {
          body = JSON.parse(res.data);
        } catch (e) {
          reject(new Error('识别返回解析失败'));
          return;
        }
        resolve(body);
      },
      fail(err) {
        reject(new Error(err.errMsg || '语音上传失败'));
      },
    });
  });
}

/**
 * 流式对话。小程序没有 fetch，用 wx.request 的分块接收（基础库 2.20.2+）。
 * 不支持分块的环境会退化成「一次性返回」，文字仍然正确，只是没有逐字效果。
 */
function streamChat(options) {
  const { message, imageText, fileName, sessionId, onEvent, onComplete, onError } = options;
  const pushText = createSseParser(onEvent);
  const decode = createUtf8Decoder();

  let chunkSupported = false;
  let completed = false;

  const task = wx.request({
    url: BASE_URL + '/api/chat/stream',
    method: 'POST',
    header: { 'content-type': 'application/json' },
    data: {
      sessionId: sessionId || undefined,
      message: message || '',
      imageText: imageText || undefined,
      fileName: fileName || undefined,
    },
    timeout: 90000,
    enableChunked: true,
    success(res) {
      if (!chunkSupported && typeof res.data === 'string') {
        pushText(res.data);
      }
      if (!completed) {
        completed = true;
        onComplete && onComplete();
      }
    },
    fail(err) {
      if (!completed) {
        completed = true;
        onError && onError(new Error((err && err.errMsg) || '连接失败'));
      }
    },
  });

  chunkSupported = typeof task.onChunkReceived === 'function';
  if (chunkSupported) {
    task.onChunkReceived((res) => {
      const text = decode(res.data);
      if (text) pushText(text);
    });
  }

  return task;
}

module.exports = { requestJSON, uploadFile, uploadAudio, streamChat, BASE_URL };
