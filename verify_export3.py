import subprocess, sys, numpy as np
import nnue3 as N
engine, recs_path = sys.argv[1], sys.argv[2]
recs = N.load_records(recs_path)
sel = recs[np.random.default_rng(1).choice(len(recs), 300, replace=False)]
P = N.init_params(5); w1, b1, Q = N.quantize(P)
N.export(P, "/tmp/check3.nnue")
PC = "PNBRQKpnbrqk"
def fen(r):
    b = [None] * 64
    for j in range(r["n"]):
        v = int(r["pcs"][j]); b[v & 63] = PC[v >> 6]
    rows = []
    for rk in range(7, -1, -1):
        s, e = "", 0
        for f in range(8):
            c = b[rk * 8 + f]
            if c is None: e += 1
            else: s += (str(e) if e else "") + c; e = 0
        rows.append(s + (str(e) if e else ""))
    return "/".join(rows) + (" w" if r["stm"] == 0 else " b") + " - - 0 1"
eng = subprocess.Popen([engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
def cmd(c, until=None):
    eng.stdin.write(c + "\n"); eng.stdin.flush()
    if until:
        while True:
            l = eng.stdout.readline()
            if l.startswith(until): return l
cmd("uci", "uciok"); cmd("setoption name EvalFile value /tmp/check3.nnue"); cmd("isready", "readyok")
ref = N.forward(Q, sel["pcs"], sel["n"], sel["stm"], sel["thr"])
got = []
for r in sel:
    cmd("position fen " + fen(r)); got.append(int(cmd("eval", "eval").split()[1]))
got = np.array(got); d = np.abs(got - ref)
print(f"v3: n={len(sel)} max|engine-numpy|={d.max():.2f} mean={d.mean():.3f} (engine range {got.min()}..{got.max()}, threatened-pieces avg {np.mean([bin(int(t)).count('1') for t in sel['thr']]):.2f})")
eng.stdin.write("quit\n"); eng.stdin.flush()
