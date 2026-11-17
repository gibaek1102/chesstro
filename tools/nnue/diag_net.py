"""Static-eval sanity check of a net against labels: diag_net.py ENGINE NET|none LABELED.txt [N]
Labels are white-relative; engine 'eval' is side-to-move, so it is converted. Prints correlation."""
import subprocess, sys, random, numpy as np
eng, net, lab = sys.argv[1], sys.argv[2], sys.argv[3]; n = int(sys.argv[4]) if len(sys.argv) > 4 else 1500
lines = [l for l in open(lab, encoding="utf-8")]; random.seed(3); sel = random.sample(lines, min(n, len(lines)))
e = subprocess.Popen([eng], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
def send(c, until=None):
    e.stdin.write(c + "\n"); e.stdin.flush()
    if until:
        while True:
            l = e.stdout.readline()
            if l.startswith(until): return l
send("uci", "uciok")
if net != "none": send("setoption name EvalFile value " + net)
send("isready", "readyok")
xs, ys, sd = [], [], []
for l in sel:
    f, s, _ = [t.strip() for t in l.split("|")]
    send("position fen " + f); xs.append(int(send("eval", "eval").split()[1])); ys.append(int(s)); sd.append(1 if f.split()[1] == "w" else -1)
xs = np.array(xs) * np.array(sd); ys = np.array(ys); m = np.abs(ys) < 1500
print("n", len(sel), "corr(|label|<1500) %.3f" % np.corrcoef(xs[m], ys[m])[0, 1], "corr(all) %.3f" % np.corrcoef(xs, ys)[0, 1])
e.stdin.write("quit\n")
