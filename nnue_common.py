"""Terranion NNUE v2 공통 코드 (numpy): 레코드 읽기, 특징 인덱스(king bucket + 좌우 미러), 양자화/내보내기, 기준 forward.
엔진(terranion.cpp)의 kInfo / wcol / nnueEval 과 같은 규칙이어야 한다 — verify_export.py 가 엔진과 대조해 검증한다."""
import numpy as np

HID, KB, OUT_B, QA, QB, SCALE = 512, 8, 8, 255, 64, 400
KBMAP = np.array([0,0,1,1, 2,2,3,3, 4,4,5,5, 4,4,5,5, 6,6,6,6, 6,6,6,6, 7,7,7,7, 7,7,7,7], dtype=np.int64)
REC = np.dtype([("score", "<i2"), ("res", "u1"), ("stm", "u1"), ("n", "u1"), ("pad", "u1", 3), ("pcs", "<u2", 32), ("thr", "<u8")])

def load_records(path):
    return np.fromfile(path, dtype=REC)

def side_features(pcs, n, persp):
    """pcs: [B,32] uint16, n: [B]. 반환 idx [B,32] (무효 칸은 -1)."""
    pcs = pcs.astype(np.int64); piece = pcs >> 6; sq = pcs & 63
    valid = np.arange(32)[None, :] < n[:, None]
    color, typ = piece // 6, piece % 6
    is_k = valid & (typ == 5) & (color == persp)
    ksq = np.where(is_k, sq, 0).sum(1)                       # 각 쪽 킹은 정확히 하나
    if persp == 1: ksq = ksq ^ 56
    f, r = ksq & 7, ksq >> 3
    mir = f >= 4
    f = np.where(mir, 7 - f, f)
    base = KBMAP[r * 4 + f] * 768
    rel = (color != persp).astype(np.int64) * 6 + typ
    sqr = sq ^ (56 if persp == 1 else 0)
    sqr = sqr ^ np.where(mir, 7, 0)[:, None]
    idx = base[:, None] + rel * 64 + sqr
    return np.where(valid, idx, -1)

def out_bucket(n):
    return np.clip((n.astype(np.int64) - 2) // 4, 0, OUT_B - 1)

def init_params(seed=0, scale=0.05):
    g = np.random.default_rng(seed)
    return {"w1": g.normal(0, scale, (KB * 768, HID)).astype(np.float32), "b1": np.zeros(HID, np.float32),
            "w2": g.normal(0, 0.1, (OUT_B, 2 * HID)).astype(np.float32), "b2": np.zeros(OUT_B, np.float32)}

def forward(params, pcs, n, stm):
    """float forward, 출력 = 수를 둘 차례 기준 centipawn (엔진 eval 과 같은 단위)."""
    B = len(n); acc = []
    for persp in (0, 1):
        idx = side_features(pcs, n, persp)
        a = np.tile(params["b1"], (B, 1))
        for j in range(32):
            m = idx[:, j] >= 0
            a[m] += params["w1"][idx[m, j]]
        acc.append(a)
    us = np.where((stm == 0)[:, None], acc[0], acc[1]); them = np.where((stm == 0)[:, None], acc[1], acc[0])
    h = np.concatenate([np.clip(us, 0, 1) ** 2, np.clip(them, 0, 1) ** 2], 1)
    ob = out_bucket(n)
    return ((h * params["w2"][ob]).sum(1) + params["b2"][ob]) * SCALE

def quantize(params):
    w1 = np.clip(np.rint(params["w1"] * QA), -32768, 32767).astype("<i2")
    b1 = np.clip(np.rint(params["b1"] * QA), -32768, 32767).astype("<i2")
    w2 = np.clip(np.rint(params["w2"] * QB), -127, 127).astype("<i2")
    b2 = np.rint(params["b2"] * QA * QB).astype("<i4")
    return w1, b1, w2, b2

def export(params, path):
    w1, b1, w2, b2 = quantize(params)
    with open(path, "wb") as f:
        for a in (w1, b1, w2, b2): f.write(a.tobytes())

def load_v1(path):
    """기존 Lunaris(768→512 단일 입력) 넷을 읽어 v2 파라미터로 변환: 모든 king bucket 에 같은 가중치를 복사(워밍 스타트)."""
    raw = open(path, "rb").read()
    n1 = 768 * HID * 2 + HID * 2 + OUT_B * 2 * HID * 2 + OUT_B * 4
    assert len(raw) == n1, (len(raw), n1)
    o = 0
    w1 = np.frombuffer(raw, "<i2", 768 * HID, o).reshape(768, HID); o += 768 * HID * 2
    b1 = np.frombuffer(raw, "<i2", HID, o); o += HID * 2
    w2 = np.frombuffer(raw, "<i2", OUT_B * 2 * HID, o).reshape(OUT_B, 2 * HID); o += OUT_B * 2 * HID * 2
    b2 = np.frombuffer(raw, "<i4", OUT_B, o)
    return {"w1": np.tile(w1.astype(np.float32) / QA, (KB, 1)), "b1": b1.astype(np.float32) / QA,
            "w2": w2.astype(np.float32) / QB, "b2": b2.astype(np.float32) / (QA * QB)}
