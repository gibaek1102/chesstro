"""Terranion NNUE v3 (numpy 기준 구현): 16 king bucket(좌우 미러) + 위협 특징 → 768 → 쌍곱(384) → 16 → 32 → 1, 출력 버킷 16.
엔진(terranion.cpp: kInfo / threatMask / nnueEval3)과 같은 규칙. verify_export3.py 가 엔진과 대조한다."""
import numpy as np
from nnue_common import REC, load_records, QA

KB, H, HP, THR_ROWS, OUTB, L1N, L2N, SCALE = 16, 768, 384, 768, 16, 16, 32, 400
ROWS = KB * 768 + THR_ROWS
KBMAP3 = np.array([0,1,2,3, 4,5,6,7, 8,9,10,11, 8,9,10,11, 12,12,13,13, 12,12,13,13, 14,14,15,15, 14,14,15,15], dtype=np.int64)

def side_features3(pcs, n, thr, persp):
    """[B,64] 인덱스 (앞 32: 기물 특징, 뒤 32: 위협 특징), 무효는 -1."""
    pcs = pcs.astype(np.int64); piece = pcs >> 6; sq = pcs & 63
    valid = np.arange(32)[None, :] < n[:, None]
    color, typ = piece // 6, piece % 6
    ksq = np.where(valid & (typ == 5) & (color == persp), sq, 0).sum(1)
    if persp == 1: ksq = ksq ^ 56
    f, r = ksq & 7, ksq >> 3
    mir = f >= 4
    f = np.where(mir, 7 - f, f)
    base = KBMAP3[r * 4 + f] * 768
    rel = (color != persp).astype(np.int64) * 6 + typ
    sqr = (sq ^ (56 if persp == 1 else 0)) ^ np.where(mir, 7, 0)[:, None]
    idx = np.where(valid, base[:, None] + rel * 64 + sqr, -1)
    tmask = valid & (((thr.astype(np.uint64)[:, None] >> sq.astype(np.uint64)) & np.uint64(1)) == 1)
    tidx = np.where(tmask, KB * 768 + rel * 64 + sqr, -1)
    return np.concatenate([idx, tidx], 1)

def out_bucket3(pcs, n):
    typ = (pcs.astype(np.int64) >> 6) % 6
    valid = np.arange(32)[None, :] < n[:, None]
    q = (valid & (typ == 4)).any(1).astype(np.int64)
    return np.clip((n.astype(np.int64) - 2) // 4, 0, 7) * 2 + q

def init_params(seed=0):
    g = np.random.default_rng(seed)
    return {"w1": g.normal(0, 0.05, (ROWS, H)).astype(np.float32), "b1": g.normal(0.1, 0.1, H).astype(np.float32),
            "l1w": g.normal(0, 0.08, (OUTB, L1N, H)).astype(np.float32), "l1b": g.normal(0, 0.3, (OUTB, L1N)).astype(np.float32),
            "l2w": g.normal(0, 0.4, (OUTB, L2N, L1N)).astype(np.float32), "l2b": g.normal(0, 0.3, (OUTB, L2N)).astype(np.float32),
            "l3w": g.normal(0, 0.4, (OUTB, L2N)).astype(np.float32), "l3b": g.normal(0, 0.2, OUTB).astype(np.float32)}

def forward(P, pcs, n, stm, thr):
    B = len(n); acc = []
    for persp in (0, 1):
        idx = side_features3(pcs, n, thr, persp)
        a = np.tile(P["b1"], (B, 1))
        for j in range(idx.shape[1]):
            m = idx[:, j] >= 0
            a[m] += P["w1"][idx[m, j]]
        acc.append(a)
    us = np.where((stm == 0)[:, None], acc[0], acc[1]); them = np.where((stm == 0)[:, None], acc[1], acc[0])
    def pw(x): c = np.clip(x, 0, 1); return c[:, :HP] * c[:, HP:]
    x = np.concatenate([pw(us), pw(them)], 1)
    b = out_bucket3(pcs, n)
    h1 = np.clip(np.einsum("bj,boj->bo", x, P["l1w"][b]) + P["l1b"][b], 0, 1)
    h2 = np.clip(np.einsum("bj,boj->bo", h1, P["l2w"][b]) + P["l2b"][b], 0, 1)
    return ((h2 * P["l3w"][b]).sum(1) + P["l3b"][b]) * SCALE

def quantize(P):
    """w1/b1 은 int16(×255), 밀집층은 float32 그대로. 양자화 후 파라미터(dequantized)도 돌려준다."""
    w1 = np.clip(np.rint(P["w1"] * QA), -32768, 32767).astype("<i2"); b1 = np.clip(np.rint(P["b1"] * QA), -32768, 32767).astype("<i2")
    Q = dict(P); Q["w1"] = w1.astype(np.float32) / QA; Q["b1"] = b1.astype(np.float32) / QA
    return w1, b1, Q

def export(P, path):
    w1, b1, _ = quantize(P)
    with open(path, "wb") as f:
        f.write(w1.tobytes()); f.write(b1.tobytes())
        for k in ("l1w", "l1b", "l2w", "l2b", "l3w", "l3b"): f.write(P[k].astype("<f4").tobytes())
