#!/bin/bash
# Terranion NNUE v2 한 바퀴: 데이터 생성 → 재라벨 → 변환 → 학습 → (대국 검증은 match.py 로)
# 사용: bash tools/nnue/pipeline.sh <라운드이름> <스레드수> <시드시작> [게임수/스레드=2000] [생성노드=5000] [재라벨노드=20000]
# 노트북이 두 대면 시드 구간을 겹치지 않게 주세요 (A: 1000.., B: 5000..). 결과 data.txt 들을 한 폴더로 모아 pack/학습.
set -e
ROUND=${1:?라운드 이름}; T=${2:?스레드수}; SEED=${3:?시드시작}; GAMES=${4:-2000}; GEN_NODES=${5:-5000}; REL_NODES=${6:-20000}
ENG=${ENG:-bin/terranion}; NET=${TERRANION_NET:-}   # TERRANION_NET=이전 넷(.nnue) 을 주면 그 넷으로 데이터를 만든다
D=rounds/$ROUND; mkdir -p $D/data
echo "[1/4] 자가대국 데이터 생성 (스레드 $T, 시드 $SEED.., 스레드당 $GAMES 판, $GEN_NODES 노드)"
TERRANION_NET=$NET $ENG gen $T $SEED $GAMES $GEN_NODES $D/data
cat $D/data/gen_*.txt > $D/raw.txt
echo "[2/4] 재라벨링: 같은 국면을 $REL_NODES 노드로 다시 탐색해 점수 교체 (더 깊은 탐색 = 더 좋은 정답)"
TERRANION_NET=$NET $ENG relabel $D/raw.txt $D/labeled.txt $REL_NODES $T
echo "[3/4] 학습용 바이너리로 변환"
$ENG pack $D/labeled.txt $D/train.bin
echo "[4/4] 학습 (PyTorch 필요)"
if [ "${ARCH:-v2}" = "v3" ]; then python3 tools/nnue/train_v3.py $D/train.bin --out $D/net --epochs ${EPOCHS:-10}
else python3 tools/nnue/train_v2.py $D/train.bin ${WARM:+--warm $WARM} --out $D/net --epochs ${EPOCHS:-8}; fi
echo "완료. 다음: python3 tools/match.py $ENG $ENG --games 400 --nodes 20000 --optA EvalFile=\$PWD/$D/net_e8.nnue"
