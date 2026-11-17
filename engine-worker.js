// Terranion WASM 엔진 워커 (클래식 워커). 탐색은 이 워커 안에서 동기적으로 실행된다.
let mod = null;
self.onmessage = async (e) => {
  const d = e.data;
  try {
    if (d.init) {
      importScripts(d.base + 'wasm/terranion.js');
      mod = await createTerranion({
        print: (l) => postMessage({ line: l }),
        printErr: () => {},
        locateFile: (f) => d.base + 'wasm/' + f,
      });
      mod.ccall('terranion_init', null, ['number'], [d.hash || 16]);
      postMessage({ ready: true });
    } else if (d.cmd !== undefined && mod) {
      mod.ccall('terranion_command', null, ['string'], [d.cmd]);
    }
  } catch (err) {
    postMessage({ error: String(err && err.message || err) });
  }
};
