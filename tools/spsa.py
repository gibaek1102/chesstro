#!/usr/bin/env python3
"""SPSA 자동 튜닝 (재개 가능): spsa.py ENGINE --iters 100 [--state spsa.json]
매 반복: theta±c*delta 두 설정으로 고정 노드 대국(오프닝 색 교대) → 결과 차이로 theta 갱신."""
import argparse, json, os, random, queue, threading, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import match as M

# name, default, lo, hi, c(섭동폭)
PARAMS = [("RfpMargin",80,30,160,8),("NmpDiv",6,3,10,1),("FutMargin",120,60,240,12),("LmpBase",4,2,8,1),
          ("LmpMul",3,1,6,1),("SeeQuiet",50,20,100,8),("SeeCap",25,10,60,5),("AspDelta",25,10,50,4),
          ("LmrBase",75,20,150,10),("LmrDiv",225,150,320,15),("SingDepth",8,5,12,1),("SingMargin",2,1,4,1),
          ("LmrHistDiv",8000,3000,16000,1200),("CapHistW",8,2,24,2),("QDelta",200,80,400,30),("HpMargin",2500,800,6000,500)]

def game_pair(pa, pb, oa, ob, fen, nodes):
    a, b = M.Eng(pa, oa), M.Eng(pb, ob)
    try:
        return M.play(a, b, fen, nodes, True) + M.play(a, b, fen, nodes, False)   # a 점수 합(0~2)
    finally:
        a.close(); b.close()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("engine"); ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--state", default="spsa.json"); ap.add_argument("--nodes", type=int, default=8000)
    ap.add_argument("--pairs", type=int, default=8); ap.add_argument("--seed", type=int, default=5)
    g = ap.parse_args()
    ops = [l.split(";")[0].strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "openings.epd")) if l.strip()]
    ops = [o if len(o.split()) > 4 else o + " 0 1" for o in ops]
    st = json.load(open(g.state)) if os.path.exists(g.state) else {"k": 0, "theta": {p[0]: float(p[1]) for p in PARAMS}}
    rng = random.Random(g.seed + st["k"])
    A_, alpha, gamma, R = 20.0, 0.602, 0.101, 0.02
    t0 = time.time()
    for _ in range(g.iters):
        st["k"] += 1; k = st["k"]
        ck = lambda c: max(1.0, c / (k ** gamma))
        delta = {p[0]: rng.choice([-1, 1]) for p in PARAMS}
        def cfg(sign):
            return [f"{n}={int(round(min(hi, max(lo, st['theta'][n] + sign * delta[n] * ck(c)))))}" for n, d, lo, hi, c in PARAMS]
        plus, minus = cfg(+1), cfg(-1)
        q = queue.Queue()
        for _i in range(g.pairs): q.put(rng.choice(ops))
        out = []
        def w():
            while True:
                try: fen = q.get_nowait()
                except queue.Empty: return
                out.append(game_pair(g.engine, g.engine, plus, minus, fen, g.nodes))
        ts = [threading.Thread(target=w) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
        res = (sum(out) - g.pairs) / (2 * g.pairs)       # plus 쪽 기대 점수 - 0.5, 범위 [-.5,.5]
        for n, d, lo, hi, c in PARAMS:
            a_k = R * c * c / ((k + A_) ** alpha) * 400      # 파라미터별 스케일
            grad = res / (delta[n] * ck(c))
            st["theta"][n] = min(hi, max(lo, st["theta"][n] + a_k * grad * 4))
        json.dump(st, open(g.state, "w"))
        if k % 10 == 0: print(f"k={k} {time.time()-t0:.0f}s", {n: round(v) for n, v in st["theta"].items()}, flush=True)
    print("FINAL", " ".join(f"--optA {n}={int(round(v))}" for n, v in st["theta"].items()))

if __name__ == "__main__":
    main()
