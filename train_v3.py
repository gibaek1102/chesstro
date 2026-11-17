#!/usr/bin/env python3
"""Terranion NNUE v3 학습기 (PyTorch): 16 king bucket + 위협 특징 -> 768 -> 쌍곱 -> 16 -> 32 -> 1 (출력 버킷 16).
  python3 train_v3.py data.bin --epochs 10 --out nets/v3
입력은 `terranion pack` 이 만든 80바이트 레코드(.bin; 위협 마스크 포함). 출력: <out>_eN.nnue (엔진 EvalFile 로 바로 사용).
※ PyTorch 가 없는 환경에서 작성되어 학습 루프는 아직 실행해 보지 못했다. 특징·양자화·내보내기·엔진 정합은 verify_export3.py 로 검증됨."""
import argparse, os, queue, threading, time
import numpy as np, torch, torch.nn as nn
import nnue3 as N

class Net3(nn.Module):
    def __init__(s):
        super().__init__()
        s.emb = nn.EmbeddingBag(N.ROWS, N.H, mode="sum"); nn.init.normal_(s.emb.weight, 0, 0.05)
        s.b1 = nn.Parameter(torch.full((N.H,), 0.1))
        s.l1w = nn.Parameter(torch.randn(N.OUTB, N.L1N, N.H) * 0.05); s.l1b = nn.Parameter(torch.zeros(N.OUTB, N.L1N))
        s.l2w = nn.Parameter(torch.randn(N.OUTB, N.L2N, N.L1N) * 0.3); s.l2b = nn.Parameter(torch.zeros(N.OUTB, N.L2N))
        s.l3w = nn.Parameter(torch.randn(N.OUTB, N.L2N) * 0.3); s.l3b = nn.Parameter(torch.zeros(N.OUTB))
    def forward(s, iu, ou, it, ot, ob):
        a = s.emb(iu, ou) + s.b1; t = s.emb(it, ot) + s.b1
        def pw(x): c = x.clamp(0, 1); return c[:, :N.HP] * c[:, N.HP:]
        x = torch.cat([pw(a), pw(t)], 1); B = x.shape[0]; ar = torch.arange(B)
        y1 = (x @ s.l1w.reshape(N.OUTB * N.L1N, N.H).T).view(B, N.OUTB, N.L1N)[ar, ob] + s.l1b[ob]
        h1 = y1.clamp(0, 1)
        h2 = (torch.einsum("bj,boj->bo", h1, s.l2w[ob]) + s.l2b[ob]).clamp(0, 1)
        return (h2 * s.l3w[ob]).sum(1) + s.l3b[ob]          # 출력 단위: centipawn / 400

def flat(idx):
    m = idx >= 0; cnt = m.sum(1)
    return torch.from_numpy(idx[m]), torch.from_numpy(np.cumsum(cnt) - cnt)

def make_batch(r, lam):
    i0 = N.side_features3(r["pcs"], r["n"], r["thr"], 0); i1 = N.side_features3(r["pcs"], r["n"], r["thr"], 1)
    w = (r["stm"] == 0)[:, None]
    iu, ou = flat(np.where(w, i0, i1)); it, ot = flat(np.where(w, i1, i0))
    s = r["score"].astype(np.float32); res = r["res"].astype(np.float32) / 2
    s = np.where(r["stm"] == 0, s, -s); res = np.where(r["stm"] == 0, res, 1 - res)
    tg = lam * (1 / (1 + np.exp(-s / N.SCALE))) + (1 - lam) * res
    return iu, ou, it, ot, torch.from_numpy(N.out_bucket3(r["pcs"], r["n"])), torch.from_numpy(tg.astype(np.float32))

def batches(path, bs, chunk, lam, seed, skip):
    total = os.path.getsize(path) // N.REC.itemsize; rng = np.random.default_rng(seed)
    starts = list(range(skip, total, chunk)); rng.shuffle(starts)
    for st in starts:
        r = np.fromfile(path, N.REC, count=min(chunk, total - st), offset=st * N.REC.itemsize); r = r[rng.permutation(len(r))]
        for b in range(0, len(r) - bs + 1, bs): yield make_batch(r[b:b + bs], lam)

def prefetch(gen, n=6):
    q = queue.Queue(n)
    def run():
        for x in gen: q.put(x)
        q.put(None)
    threading.Thread(target=run, daemon=True).start()
    while (x := q.get()) is not None: yield x

def to_params(m):
    g = lambda t: t.detach().cpu().numpy()
    return {"w1": g(m.emb.weight), "b1": g(m.b1), "l1w": g(m.l1w), "l1b": g(m.l1b), "l2w": g(m.l2w), "l2b": g(m.l2b), "l3w": g(m.l3w), "l3b": g(m.l3b)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("data"); ap.add_argument("--out", default="nets/v3")
    ap.add_argument("--epochs", type=int, default=10); ap.add_argument("--bs", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--lam", type=float, default=0.75)
    ap.add_argument("--chunk", type=int, default=2_000_000); ap.add_argument("--val", type=int, default=200_000)
    ap.add_argument("--threads", type=int, default=0, help="CPU threads (0 = half of the cores)"); ap.add_argument("--resume", action="store_true", help="continue from <out>_ckpt.pt")
    g = ap.parse_args()
    torch.set_num_threads(g.threads or max(1, (os.cpu_count() or 2) // 2)); os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
    m = Net3(); total = os.path.getsize(g.data) // N.REC.itemsize; steps = g.epochs * ((total - g.val) // g.bs)
    opt = torch.optim.AdamW(m.parameters(), lr=g.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps, eta_min=g.lr / 100)
    val = N.load_records(g.data)[:g.val] if g.val else None; step, t0 = 0, time.time()
    start, ck = 1, g.out + "_ckpt.pt"
    if g.resume and os.path.exists(ck):
        c = torch.load(ck, weights_only=False); m.load_state_dict(c["m"]); opt.load_state_dict(c["o"]); sched.load_state_dict(c["s"]); step, start = c["step"], c["ep"] + 1
        print(f"resumed after epoch {c['ep']}", flush=True)
    for ep in range(start, g.epochs + 1):
        run, nb = 0.0, 0
        for iu, ou, it, ot, ob, tg in prefetch(batches(g.data, g.bs, g.chunk, g.lam, ep, g.val)):
            loss = ((torch.sigmoid(m(iu, ou, it, ot, ob)) - tg) ** 2).mean()
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
            with torch.no_grad(): m.emb.weight.clamp_(-3, 3)      # int16 양자화(×255) 범위 안
            run += loss.item(); nb += 1; step += 1
            if step % 200 == 0: print(f"ep {ep} step {step}/{steps} loss {run / nb:.5f} {step * g.bs / (time.time() - t0):.0f} pos/s", flush=True)
        vl = ""
        if val is not None:
            with torch.no_grad():
                vs = [((torch.sigmoid(m(*make_batch(val[b:b + g.bs], g.lam)[:5])) - make_batch(val[b:b + g.bs], g.lam)[5]) ** 2).mean().item()
                      for b in range(0, len(val) - g.bs + 1, g.bs)]
                vl = f" val {np.mean(vs):.5f}"
        path = f"{g.out}_e{ep}.nnue"; N.export(to_params(m), path)
        torch.save({"m": m.state_dict(), "o": opt.state_dict(), "s": sched.state_dict(), "ep": ep, "step": step}, ck)
        print(f"== epoch {ep} train {run / max(nb, 1):.5f}{vl} -> {path}", flush=True)
if __name__ == "__main__":
    main()
