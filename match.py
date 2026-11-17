#!/usr/bin/env python3
"""고정 노드 UCI 대국 하네스: match.py ENG_A ENG_B --games 200 --nodes 20000 [--optA "Name=val" ...]
A가 새 엔진(테라니온), B가 기준(루나리스). 오프닝 한 개당 색을 바꿔 2판씩 둔다."""
import argparse, random, subprocess, sys, math, threading, queue
import chess

class Eng:
    def __init__(s, path, opts):
        s.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        s.send("uci"); s.wait("uciok")
        for o in opts:
            k, v = o.split("=", 1); s.send(f"setoption name {k} value {v}")
        s.send("setoption name Hash value 16"); s.send("isready"); s.wait("readyok")
    def send(s, c): s.p.stdin.write(c + "\n"); s.p.stdin.flush()
    def wait(s, t):
        while True:
            l = s.p.stdout.readline()
            if not l: raise RuntimeError("engine died")
            if l.startswith(t): return l
    def go(s, moves, fen, nodes):
        s.send(f"position fen {fen} moves " + " ".join(moves)); s.send(f"go movetime {-nodes}" if nodes < 0 else f"go nodes {nodes}")
        sc = 0
        while True:
            l = s.p.stdout.readline()
            if not l: raise RuntimeError("engine died")
            if l.startswith("info") and " score cp " in l:
                sc = int(l.split(" score cp ")[1].split()[0])
            elif l.startswith("info") and " score mate " in l:
                m = int(l.split(" score mate ")[1].split()[0]); sc = 30000 if m > 0 else -30000
            elif l.startswith("bestmove"): return l.split()[1], sc
    def close(s):
        try: s.send("quit"); s.p.wait(timeout=2)
        except Exception: s.p.kill()

def play(a, b, fen, nodes, a_white):
    board = chess.Board(fen); moves = []; win_cnt = 0; draw_cnt = 0
    a.send("ucinewgame"); b.send("ucinewgame")
    while True:
        if board.is_game_over(claim_draw=True) or len(moves) > 400:
            r = board.result(claim_draw=True)
            if r == "1-0": return 1.0 if a_white else 0.0
            if r == "0-1": return 0.0 if a_white else 1.0
            return 0.5
        a_turn = (board.turn == chess.WHITE) == a_white
        mv, sc = (a if a_turn else b).go(moves, fen, nodes)
        if mv in ("0000", "(none)"): return 0.5
        board.push_uci(mv); moves.append(mv)
        # 판정: 연속 8수 이상 |점수|>=700 이면 승, 60수 이후 연속 20수 |점수|<=8 이면 무
        s_white = sc if board.turn == chess.BLACK else -sc   # 방금 둔 쪽 시점 -> 백 시점
        if abs(s_white) >= 700: win_cnt += 1
        else: win_cnt = 0
        if win_cnt >= 8:
            w = s_white > 0
            return (1.0 if w == a_white else 0.0)
        draw_cnt = draw_cnt + 1 if abs(sc) <= 8 and len(moves) > 60 else 0
        if draw_cnt >= 20: return 0.5

def worker(q, res, pa, pb, oa, ob, nodes):
    a, b = Eng(pa, oa), Eng(pb, ob)
    while True:
        try: fen, a_white = q.get_nowait()
        except queue.Empty: break
        r = play(a, b, fen, nodes, a_white); res.append(r)
        w = sum(x == 1 for x in res); d = sum(x == .5 for x in res); l = sum(x == 0 for x in res)
        print(f"\r{len(res)} games +{w} ={d} -{l}", end="", file=sys.stderr, flush=True)
    a.close(); b.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--games", type=int, default=100); ap.add_argument("--nodes", type=int, default=20000)
    ap.add_argument("--optA", action="append", default=[]); ap.add_argument("--optB", action="append", default=[])
    ap.add_argument("--conc", type=int, default=2); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--epd", default=__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "server", "openings.epd"))
    g = ap.parse_args()
    ops = [l.strip() for l in open(g.epd) if l.strip()]
    random.Random(g.seed).shuffle(ops)
    q = queue.Queue()
    for i in range(g.games // 2):
        fen = ops[i % len(ops)].split(";")[0].strip()
        if len(fen.split()) == 4: fen += " 0 1"
        q.put((fen, True)); q.put((fen, False))
    res = []
    ts = [threading.Thread(target=worker, args=(q, res, g.a, g.b, g.optA, g.optB, g.nodes)) for _ in range(g.conc)]
    [t.start() for t in ts]; [t.join() for t in ts]
    n = len(res); w = sum(x == 1 for x in res); d = sum(x == .5 for x in res); l = sum(x == 0 for x in res)
    sc = (w + d / 2) / n; sc = min(max(sc, 1e-3), 1 - 1e-3)
    elo = -400 * math.log10(1 / sc - 1)
    var = (w * (1 - sc) ** 2 + d * (.5 - sc) ** 2 + l * sc ** 2) / n
    err = 400 / math.log(10) * math.sqrt(var / n) / (sc * (1 - sc))
    print(f"\nA vs B: +{w} ={d} -{l}  score {sc:.3f}  Elo {elo:+.0f} ± {1.96 * err:.0f}")

if __name__ == "__main__":
    main()
