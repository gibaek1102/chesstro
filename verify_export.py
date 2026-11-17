"""내보낸 v2 넷을 엔진이 읽어 낸 eval 과, numpy forward 값을 대조한다 (특징 인덱스·양자화·파일 포맷 검증)."""
import subprocess, sys, numpy as np
import nnue_common as C
engine, recs_path = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "random"
recs = C.load_records(recs_path)
sel = recs[np.random.default_rng(1).choice(len(recs), 300, replace=False)]
if mode == "random":
    P = C.init_params(3, 0.06); P["b1"] = np.random.default_rng(4).normal(0.1, 0.1, C.HID).astype(np.float32)
else:
    P = C.load_v1(mode)
C.export(P, "/tmp/check.nnue")
# FEN 복원
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
cmd("uci", "uciok"); cmd("setoption name EvalFile value /tmp/check.nnue"); cmd("isready", "readyok")
w1, b1, w2, b2 = C.quantize(P)   # 양자화된 값을 되돌린 파라미터로 비교 → 남는 차이는 정수 반올림뿐이어야 한다
Q = {"w1": w1 / C.QA, "b1": b1 / C.QA, "w2": w2 / C.QB, "b2": b2 / (C.QA * C.QB)}
ref = C.forward(Q, sel["pcs"], sel["n"], sel["stm"])
got = []
for r in sel:
    cmd("position fen " + fen(r)); l = cmd("eval", "eval"); got.append(int(l.split()[1]))
got = np.array(got); d = np.abs(got - ref)
print(f"{mode}: n={len(sel)} max|engine-numpy|={d.max():.2f} mean={d.mean():.3f}  (engine range {got.min()}..{got.max()})")
eng.stdin.write("quit\n"); eng.stdin.flush()
