# Terranion NNUE — 넷 개선 파이프라인 (v2 / v3)

탐색 개선(+튜닝)은 이 번들에 이미 들어 있습니다. 여기서부터는 **넷**을 키우는 단계이고, 학습은 Eric 노트북에서 돌립니다.

## 무엇이 새로운가
1. **v2 구조**: 입력을 `768` → `8 king bucket × 768`(킹이 a~d 파일이 되도록 좌우 미러). 킹 위치별로 다른 평가를 배울 수 있다. 엔진은 파일 크기로 v1/v2 를 자동 구분한다(`EvalFile`).
2. **재라벨링(증류)**: `terranion relabel` 이 모아 둔 모든 국면을 더 깊은 탐색(예: 20k 노드)으로 다시 평가한다. 얕게 만든 라벨 → 깊게 다시 단 라벨이라 넷이 "깊은 탐색의 판단"을 흉내 내게 된다.
3. **자기 개선 루프**: 새 넷으로 다시 데이터를 만들고(`TERRANION_NET=...`) 재라벨 → 학습 → 대국 검증을 반복. 이기면 채택.
4. **워밍 스타트**: `--warm lunaris512.nnue` 로 기존 512 넷의 지식을 모든 king bucket 에 복사해 시작.

## 순서
```
python3 tools/nnue/extract_net.py engine/net_data.h lunaris512.nnue      # 기존 넷 꺼내기(1회)
WARM=lunaris512.nnue bash tools/nnue/pipeline.sh r1 12 1000 2000         # 노트북A (12스레드)
bash tools/nnue/pipeline.sh r1b 16 5000 2000                              # 노트북B (16스레드, 시드 겹치지 않게)
# 두 노트북의 labeled.txt 를 합쳐 pack → 한 번에 학습해도 됨
python3 tools/match.py bin/terranion bin/terranion --games 400 --nodes 20000 --optA EvalFile=$PWD/rounds/r1/net_e8.nnue
```
이기면 `TERRANION_NET=rounds/r1/net_e8.nnue` 로 다음 라운드(r2)를 돌린다.

## 현재 검증된 것 / 아닌 것
- 검증됨: v2 증분 갱신(king bucket 재계산 포함)이 처음부터 계산한 값과 일치(`nnuecheck`, 불일치 0), 특징 인덱스·양자화·파일 포맷이 엔진 출력과 ±1cp 일치(`verify_export.py`), `pack`/`relabel` 동작.
- **미검증**: `train_v2.py` 의 PyTorch 학습 루프(만든 환경에 PyTorch 가 없었음). 처음엔 `--epochs 1` + 작은 데이터로 돌려 loss 가 내려가는지 확인하세요.
- 워밍 스타트만 한 v2 넷은 학습 전에는 기존보다 **약함**(대국 −127 Elo). 기존 넷이 좌우 반사된 킹 위치를 학습한 적이 없기 때문이며, 학습을 거치면 사라지는 것이 정상입니다.
- 학습량 가늠: 수천만 국면 이상이 있어야 v2 가 v1 을 확실히 넘습니다(노트북 두 대로 자가대국 며칠 분).

## v3 (현대형 구조) — 쌍곱 + 밀집층 + 위협 특징
- 구조: 16 king bucket(미러) + **위협 특징**(싼 기물에게 공격받거나, 공격받는데 방어 없는 기물) → 768 → **쌍곱**(384) → 밀집 16 → 32 → 1, 출력 버킷 16(기물 수 8단계 × 퀸 유무).
- 위협 특징은 증분 갱신이 아니라 평가 시점에 국면에서 계산(엔진 `threatMask`), 학습 데이터에는 `pack` 이 마스크를 같이 저장(80바이트 레코드).
- 파일: 엔진은 크기로 v1/v2/v3 를 구분. `train_v3.py` → `*.nnue` → `EvalFile`.
- 검증됨: numpy 기준 구현과 엔진 출력이 0.5cp 이내(`verify_export3.py`), 증분 갱신 일치(`nnuecheck`, `randnet 3`). **미검증**: PyTorch 학습 루프, v3 의 실제 대국력(넷이 아직 없음).
- 지금 밀집층은 float 로 계산합니다(정확성 우선). int8/VNNI 양자화는 학습된 넷으로 효과를 확인한 뒤 다음 단계입니다.
- 순서: `pipeline.sh` 의 마지막 학습 단계에서 `train_v2.py` 대신 `train_v3.py` 를 쓰면 됩니다 (`ARCH=v3 bash tools/nnue/pipeline.sh ...`).
