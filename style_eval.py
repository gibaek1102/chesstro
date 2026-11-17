#!/usr/bin/env python3
"""스타일 측정: style_eval.py ENGINE --a "Style=Aggressive" --b "Style=Defensive" --games 200 --nodes 20000
A·B 의 점수와 함께 A 쪽의 성향 지표(무승부율, 평균 길이, 체크/잡기 횟수, 40수 전 퀸 교환 비율)를 낸다."""
import argparse, os, sys, random, queue, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chess
import numpy as np
import match as M

W = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}
def zone_units(board, attacker_color):
    """attacker_color 편 기물이 상대 킹 구역(킹 주변 8칸+킹)을 누르는 정도 (엔진 kingZoneAttack 과 같은 가중치)"""
    ksq = board.king(not attacker_color)
    if ksq is None: return 0
    zone = chess.SquareSet(chess.BB_KING_ATTACKS[ksq] | chess.BB_SQUARES[ksq]); u = 0
    for sq, pc in board.piece_map().items():
        if pc.color == attacker_color and pc.piece_type in W:
            u += W[pc.piece_type] * len(board.attacks(sq) & zone)
    return u

def play(a, b, fen, nodes, a_white, nodesB=None):
    board = chess.Board(fen); a.send("ucinewgame"); b.send("ucinewgame"); moves = []
    st = {"checks": 0, "caps": 0, "ply": 0, "press": [], "expo": []}; win = 0
    res = None
    while res is None:
        if board.is_game_over(claim_draw=True) or len(moves) > 300:
            r = board.result(claim_draw=True); res = (1.0 if a_white else 0.0) if r == "1-0" else (0.0 if a_white else 1.0) if r == "0-1" else 0.5; break
        a_turn = (board.turn == chess.WHITE) == a_white
        mv, sc = (a if a_turn else b).go(moves, fen, nodes if a_turn else (nodesB or nodes))
        if mv in ("0000", "(none)"): res = 0.5; break
        m = chess.Move.from_uci(mv)
        if a_turn:
            st["caps"] += board.is_capture(m)
        board.push(m); moves.append(mv)
        if a_turn and board.is_check(): st["checks"] += 1
        if a_turn and len(moves) > 10:
            st["press"].append(zone_units(board, a_white)); st["expo"].append(zone_units(board, not a_white))
        sw = sc if board.turn == chess.BLACK else -sc
        win = win + 1 if abs(sw) >= 700 else 0
        if win >= 8: res = 1.0 if (sw > 0) == a_white else 0.0
    st["ply"] = len(moves)
    st["queens_off_40"] = int(len(moves) >= 80 and not any(p.piece_type == chess.QUEEN for p in board.piece_map().values())) if len(moves) >= 80 else -1
    return res, st

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("engine")
    ap.add_argument("--a", action="append", default=[]); ap.add_argument("--b", action="append", default=[])
    ap.add_argument("--games", type=int, default=200); ap.add_argument("--nodes", type=int, default=20000); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--nodesB", type=int, default=0, help="nodes per move for B (default = same as A)")
    g = ap.parse_args()
    ops = [l.split(";")[0].strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "openings.epd")) if l.strip()] if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "openings.epd")) else [l.split(";")[0].strip() for l in open("/home/claude/lw/server/openings.epd")]
    ops = [o if len(o.split()) > 4 else o + " 0 1" for o in ops]; random.Random(g.seed).shuffle(ops)
    q = queue.Queue()
    for i in range(g.games // 2): q.put((ops[i % len(ops)], True)); q.put((ops[i % len(ops)], False))
    out = []
    def w():
        a, b = M.Eng(g.engine, g.a), M.Eng(g.engine, g.b)
        while True:
            try: fen, aw = q.get_nowait()
            except queue.Empty: break
            out.append(play(a, b, fen, g.nodes, aw, g.nodesB or None))
        a.close(); b.close()
    ts = [threading.Thread(target=w) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
    n = len(out); sc = sum(r for r, _ in out) / n
    import math
    s2 = min(max(sc, 1e-3), 1 - 1e-3); elo = -400 * math.log10(1 / s2 - 1)
    dr = sum(1 for r, _ in out if r == 0.5) / n
    print(f"A[{','.join(g.a) or 'default'}] vs B[{','.join(g.b) or 'default'}]  {n}판  A점수 {sc:.3f} (Elo {elo:+.0f})  무승부 {dr:.0%}  "
          f"평균 {sum(s['ply'] for _, s in out) / n / 2:.0f}수  A→상대킹 압박 {np.mean([x for _, s in out for x in s['press']]):.2f}  상대→A킹 압박 {np.mean([x for _, s in out for x in s['expo']]):.2f}  A 체크 {sum(s['checks'] for _, s in out) / n:.1f}/판  A 잡기 {sum(s['caps'] for _, s in out) / n:.1f}/판")
main()
