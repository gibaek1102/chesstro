"""engine/net_data.h 의 내장 넷을 .nnue 파일로 꺼낸다: python3 extract_net.py ../../engine/net_data.h lunaris512.nnue"""
import re, sys
txt = open(sys.argv[1]).read()
body = txt[txt.index("{", txt.index("NET_DATA")) + 1: txt.rindex("}")]
data = bytes(int(x) for x in re.findall(r"\d+", body))
open(sys.argv[2], "wb").write(data); print(len(data), "bytes")
