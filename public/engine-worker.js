// WASM 엔진 워커 (클래식 워커). engine: 'terranion' | 'lunaris'. 탐색은 이 워커 안에서 동기적으로 실행된다.
let mod = null;
let name = 'terranion';
self.onmessage = async (e) => {
  const d = e.data;
  try {
    if (d.init) {
      name = d.engine === 'lunaris' ? 'lunaris' : 'terranion';
      importScripts(d.base + 'wasm/' + name + '.js');
      const factory = name === 'lunaris' ? createLunaris : createTerranion;
      mod = await factory({
        print: (l) => postMessage({ line: l }),
        printErr: () => {},
        locateFile: (f) => d.base + 'wasm/' + f,
      });
      mod.ccall(name + '_init', null, ['number'], [d.hash || 16]);
      postMessage({ ready: true });
    } else if (d.cmd !== undefined && mod) {
      mod.ccall(name + '_command', null, ['string'], [d.cmd]);
    }
  } catch (err) {
    postMessage({ error: String(err && err.message || err) });
  }
};
