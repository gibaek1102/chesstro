#!/usr/bin/env python3
"""Terranion NNUE v2 학습기 (PyTorch, CPU/GPU 모두 가능).
  python3 train_v2.py data.bin --warm lunaris512.nnue --epochs 8 --out nets/t2
입력: `terranion pack` 이 만든 72바이트 레코드 .bin.  출력: 에폭마다 <out>_eN.nnue (엔진 EvalFile 로 바로 사용).
구조: (8 king bucket × 768 -> 512) ×2 관점, SCReLU, 출력 8버킷(기물 수) — nnue_common.py 와 동일 규칙.
※ 이 스크립트는 PyTorch 가 없는 환경에서 작성되어 학습 루프 자체는 아직 실행해 보지 못했다 (특징/양자화/내보내기는 verify_export.py 로 엔진과 대조 검증됨)."""
import argparse, os, queue, threading, time
import numpy as np, torch, torch.nn as nn
import nnue_common as C

class Net(nn.Module):
    def __init__(s):
        super().__init__()
        s.emb = nn.EmbeddingBag(C.KB * 768, C.HID, mode="sum")
        nn.init.normal_(s.emb.weight, 0, 0.05)
        s.b1 = nn.Parameter(torch.zeros(C.HID))
        s.w2 = nn.Parameter(torch.randn(C.OUT_B, 2 * C.HID) * 0.1)
        s.b2 = nn.Parameter(torch.zeros(C.OUT_B))
    def forward(s, iu, ou, it, ot, ob):
        a = s.emb(iu, ou) + s.b1; t = s.emb(it, ot) + s.b1
        h = torch.cat([a.clamp(0, 1) ** 2, t.clamp(0, 1) ** 2], 1)
        return (h * s.w2[ob]).sum(1) + s.b2[ob]          # 출력 단위: centipawn / 400

def flat(idx):
    m = idx >= 0; cnt = m.sum(1)
    return torch.from_numpy(idx[m]), torch.from_numpy(np.cumsum(cnt) - cnt)

def make_batch(r, lam):
    i0 = C.side_features(r["pcs"], r["n"], 0); i1 = C.side_features(r["pcs"], r["n"], 1)
    w = (r["stm"] == 0)[:, None]
    us = np.where(w, i0, i1); them = np.where(w, i1, i0)
    iu, ou = flat(us); it, ot = flat(them)
    s = r["score"].astype(np.float32); res = r["res"].astype(np.float32) / 2
    s = np.where(r["stm"] == 0, s, -s); res = np.where(r["stm"] == 0, res, 1 - res)
    target = lam * (1 / (1 + np.exp(-s / C.SCALE))) + (1 - lam) * res
    return iu, ou, it, ot, torch.from_numpy(C.out_bucket(r["n"])), torch.from_numpy(target.astype(np.float32))

def batches(path, bs, chunk, lam, seed, skip_val):
    total = os.path.getsize(path) // C.REC.itemsize
    rng = np.random.default_rng(seed)
    starts = list(range(skip_val, total, chunk)); rng.shuffle(starts)
    for st in starts:
        r = np.fromfile(path, C.REC, count=min(chunk, total - st), offset=st * C.REC.itemsize)
        r = r[rng.permutation(len(r))]
        for b in range(0, len(r) - bs + 1, bs):
            yield make_batch(r[b:b + bs], lam)

def prefetch(gen, n=6):
    q = queue.Queue(n)
    def run():
        for x in gen: q.put(x)
        q.put(None)
    threading.Thread(target=run, daemon=True).start()
    while (x := q.get()) is not None: yield x

def to_params(m):
    return {"w1": m.emb.weight.detach().cpu().numpy(), "b1": m.b1.detach().cpu().numpy(),
            "w2": m.w2.detach().cpu().numpy(), "b2": m.b2.detach().cpu().numpy()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("--out", default="nets/t2"); ap.add_argument("--warm", default="")
    ap.add_argument("--epochs", type=int, default=8); ap.add_argument("--bs", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--lam", type=float, default=0.75, help="점수 비중(나머지는 대국 결과)")
    ap.add_argument("--chunk", type=int, default=2_000_000); ap.add_argument("--val", type=int, default=200_000)
    g = ap.parse_args()
    torch.set_num_threads(os.cpu_count()); os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
    m = Net()
    if g.warm:
        P = C.load_v1(g.warm)
        with torch.no_grad():
            m.emb.weight.copy_(torch.from_numpy(P["w1"])); m.b1.copy_(torch.from_numpy(P["b1"]))
            m.w2.copy_(torch.from_numpy(P["w2"])); m.b2.copy_(torch.from_numpy(P["b2"]))
        print("워밍 스타트:", g.warm)
    total = os.path.getsize(g.data) // C.REC.itemsize
    steps = g.epochs * ((total - g.val) // g.bs)
    opt = torch.optim.AdamW(m.parameters(), lr=g.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps, eta_min=g.lr / 100)
    val = C.load_records(g.data)[:g.val] if g.val else None
    step, t0 = 0, time.time()
    for ep in range(1, g.epochs + 1):
        run = 0.0; nb = 0
        for iu, ou, it, ot, ob, tg in prefetch(batches(g.data, g.bs, g.chunk, g.lam, ep, g.val)):
            pred = torch.sigmoid(m(iu, ou, it, ot, ob))
            loss = ((pred - tg) ** 2).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
            with torch.no_grad():                         # int16 / int8 양자화 범위 안에 가두기
                m.emb.weight.clamp_(-1.98, 1.98); m.w2.clamp_(-1.98, 1.98)
            run += loss.item(); nb += 1; step += 1
            if step % 200 == 0: print(f"ep {ep} step {step}/{steps} loss {run / nb:.5f}  {step * g.bs / (time.time() - t0):.0f} pos/s", flush=True)
        vl = ""
        if val is not None:
            with torch.no_grad():
                vs = []
                for b in range(0, len(val) - g.bs + 1, g.bs):
                    iu, ou, it, ot, ob, tg = make_batch(val[b:b + g.bs], g.lam)
                    vs.append(((torch.sigmoid(m(iu, ou, it, ot, ob)) - tg) ** 2).mean().item())
                vl = f" val {np.mean(vs):.5f}"
        path = f"{g.out}_e{ep}.nnue"; C.export(to_params(m), path)
        print(f"== epoch {ep} train {run / max(nb, 1):.5f}{vl} -> {path}", flush=True)
if __name__ == "__main__":
    main()
