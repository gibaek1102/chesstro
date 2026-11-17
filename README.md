# Terranion Web (Lunaris 후속, 개선판)

Terranion(NNUE UCI 엔진)를 브라우저에서 체험하고, 서버에서 자가대국이 계속 돌아가는 사이트.

## 구성
- `engine/` Terranion 1.0 소스(Lunaris 1.2.1의 512 넷 내장) → `build.sh` 로 `bin/terranion` 빌드
- `server/server.js` 정적 파일 + WebSocket(`/ws`) + 엔진 슬롯 관리, 자가대국 워커를 자식 프로세스로 실행
- `server/play.js` 사람 대국 세션(합법수 검증은 chess.js, 엔진 응답도 검증)
- `server/selfplay.js` 자가대국 루프 (nice 19, 판정 종료, PGN/JSONL 저장)
- `public/` 프론트엔드 (의존성 없는 SVG 보드, chess.js는 `public/vendor/`)

## 로컬 실행
```
npm install
./build.sh
npm start            # http://localhost:3000
```

## 배포 0: GitHub Pages (무료, 서버 없음) ← 브라우저에서 엔진이 직접 돌아감
엔진을 WebAssembly로 컴파일해서 방문자 브라우저에서 실행합니다. 자가대국은 라이브 탭을 보는 동안만 그 브라우저에서 돌아갑니다.
1. GitHub에 새 저장소를 만들고 이 폴더를 `main` 브랜치로 push
2. 저장소 Settings → Pages → Source 를 **GitHub Actions** 로 설정
3. Actions 탭에서 "Deploy to GitHub Pages" 가 초록색으로 끝나면 `https://<계정>.github.io/<저장소>/` 에서 열림
4. 도메인 연결: Settings → Pages → Custom domain 에 `chess.ericlee.dev` 입력, DNS 에는 `chess` CNAME → `<계정>.github.io`

(WASM 파일은 Actions 빌드에서만 만들어지므로, 내 컴퓨터에서 `?local` 로는 엔진이 뜨지 않습니다.)

## 배포 A: Ubuntu 서버에 한 줄 설치 (Docker 없이, 권장)
1. DNS에서 `chess` A 레코드를 서버 IP로 지정
2. 이 폴더를 서버로 올리고(예: `scp -r` 또는 git clone) 그 폴더에서:
   `sudo bash install.sh chess.ericlee.dev`
3. 업데이트할 때는 파일을 덮어쓴 뒤 같은 명령을 다시 실행

## 배포 B: Docker
1. DNS: `chess` A 레코드를 서버 IP로 (ericlee.dev 의 DNS 설정에서)
2. 서버에서 이 폴더를 올린 뒤 `docker compose up -d --build`
3. 처음 접속 때 Caddy가 HTTPS 인증서를 자동 발급합니다.

엔진은 `-march=native`로 **배포할 서버에서** 빌드됩니다(Dockerfile이 서버에서 빌드하므로 자동).
다른 CPU로 이미지를 옮길 때는 `--build-arg MARCH=x86-64-v3`.

## 설정(환경변수)
| 이름 | 기본 | 설명 |
|---|---|---|
| `SELFPLAY` | 1 | 0 이면 자가대국 끔 |
| `SELFPLAY_MOVETIME` | 250 | 자가대국 수당 ms |
| `SELFPLAY_THREADS` / `SELFPLAY_HASH` | 1 / 64 | 자가대국 엔진 스레드·해시(MB) |
| `SELFPLAY_NET_B` | – | 흑 엔진만 다른 `.nnue` 파일 사용 (넷 비교용) |
| `PLAY_MAX_ENGINES` | 4 | 사람 대국 동시 엔진 수 (꽉 차면 "자리 없음") |
| `PLAY_MAX_PER_IP` | 2 | IP당 동시 대국 |
| `PLAY_IDLE_MIN` | 20 | 무입력 시 연결 종료(분) |
| `ALLOWED_ORIGINS` | https://chess.ericlee.dev | WebSocket 허용 출처 (localhost는 항상 허용) |

## 데이터
`/data`(Docker 볼륨)에 `games.pgn`(수마다 `+0.35/12` 평가·깊이 주석), `games.jsonl`, `stats.json`.
사람 대국은 서버에 저장하지 않습니다.


## 요약 (1.4, 최종 측정)
- 원본 Lunaris 대비 **+72 Elo (±28)** — 같은 시간(판당 50ms), 400판, `-O3 -march=native` 빌드. (최적화 없이 빌드하면 속도가 절반이라 오히려 약해 보이니 반드시 `-O3 -march=native` 로 빌드)
- 탐색 기능(ProbCut·다중 보정·이중 특이 확장 등)을 끄고 켜도 ±25 Elo 안에서 차이가 없어 기본값을 유지.
- 스타일: Aggressive / Balanced / Defensive(=잘 비기기, 더 강한 상대에게 무승부율 13~17% → 약 25%, 같은 세기 상대로는 약 −43 Elo).
- NNUE v3 학습 파이프라인은 윈도우에서 끝까지 검증됨(데이터 생성 → 재라벨 → 학습 → 대국). 다만 직접 학습한 v3 넷(약 1000만 국면)은 기본 넷에 −400 Elo 라 아직 쓸 수 없고, 더 많은 데이터(큰 컴퓨터)가 필요.
- 윈도우: `tools\nnue\overnight.ps1`(청크 단위 생성, 이어하기 가능), `train_big.ps1`(`-Threads`, `-Resume`), `diag_net.py`. PowerShell 5.1 이므로 스크립트는 ASCII 만 사용.

## 스타일(공격성) 조절 — Terranion 1.4
`setoption name Style value Aggressive|Balanced|Defensive` (웹 UI 에서는 새 게임 옆 「스타일」 선택). 연속 조절은 `Aggression` (−100…+100, 0 = 중간).
넷과 무관한 평가 층에서 동작하므로 넷을 키워도/바꿔도 그대로 쓸 수 있습니다.
- 상대 킹 구역을 누르는 공격 압박에 보너스(공격적) / 상대가 내 킹을 누르는 압박에 감점(수비적)
- 교환 선호: 공격적은 기물을 남기려 하고, 수비적은 교환을 환영
- 무승부 회피(contempt): 공격적일수록 반복·스테일메이트 무승부를 낮게 평가
- 세부 조절: `StyleAttackW`(압박 가중), `StyleKeepPieces`(교환 선호), `StyleContempt`(무승부 회피, cp)

측정(`tools/style_eval.py`, 고정 20k 노드, 각 160판, 중간 설정 상대):
| 설정 | 내가 상대 킹 누르는 압박 | 상대가 내 킹 누르는 압박 | 무승부율 | 세기(Elo, ±35) |
|---|---|---|---|---|
| 중간 | 4.2 | 4.1 | 41% | 0 |
| 공격적(+70) | **5.8** | 4.3 | **27%** | ≈0 |
| 공격적(+100) | 5.8 | 4.2 | 20% | −22 |
| 수비적(−70) | 4.0 | **3.1** | 36% | −41 |
| 수비적(−100) | 4.0 | **2.5** | 31% | −24 |
공격적(+70)은 성향이 뚜렷하게 바뀌면서 세기 손실이 없고, 수비적은 약 −30 Elo 의 대가가 있습니다.


### 1.4 — 수비적 = 잘 비기기
`Style=Defensive` 는 이제 Aggression −100 + `StyleDrawValue`(무승부를 +|A|×값/100 cp 로 평가, 기본 300). 불리할 때 반복·50수 무승부로 가는 쪽을 택합니다.
측정(300판, 4000노드 vs **3배 노드의 중간 설정**, `style_eval.py --nodesB 12000`): 무승부율 13~17% → 약 25%, 점수 0.127 → 0.15 안팎.
같은 세기(6000노드) 상대로는 약 −43 Elo (±35). 오차가 큰 측정이라 방향만 믿으세요.

## Terranion 1.2 — Lunaris 1.2.1 대비 바뀐 것
같은 512 NNUE 넷으로 탐색만 바꾼 결과: 고정 20k 노드 300판 **+97 Elo (±32)**, 시간제 40ms/수 160판 **+59 (±45)**. (v1.1 대비는 20k 노드 +37, 40ms −11 — 오차 안이라 "비슷하거나 약간 나음" 정도로만 보세요.)

**탐색 (모두 UCI 옵션 `F...` 로 켜고 끌 수 있음; SPSA 로 27개 상수 재튜닝)**
- 싱귤러 확장(이중·삼중·음수) + multi-cut, ProbCut, 컷 노드 구분(LMR/IIR), 캡처 히스토리, 히스토리 malus, 1·2·4수 continuation history, LMR(개선 여부·히스토리), LMP
- **다중 보정 히스토리**: 폰 구조 + 비폰 기물 + 마이너 기물 + 직전 수 + **킹존(내 킹·상대 킹 위치, Terranion 고유)** 로 정적 평가를 보정
- **경험 학습 (Terranion 고유)**: `setoption name ExperienceFile value exp.txt`, 대국이 끝나면 `result win|draw|loss`. 같은 국면에서 이겨 본 수는 반복하고(승률 75%↑·2판↑), 2패 이상 0승인 수는 제외하고 다시 탐색해 피합니다. (두 번 지자 세 번째 대국부터 e2e4→d2d4 로 바뀌는 것 확인)
- Lazy SMP 스레드 투표 `FVote`(기본 꺼짐: 2코어 환경에서 효과를 판별 못 함)

**넷 (학습 필요 — `tools/nnue/PIPELINE.md`)**
- v2: 8 king bucket(미러), v3: 16 king bucket + **위협 특징** + 768 → **쌍곱** → 밀집 16 → 32 → 1, 출력 버킷 16. 엔진은 파일 크기로 자동 구분, `pack`/`relabel` 도구와 `train_v2.py`/`train_v3.py` 포함
- 검증됨: 증분 갱신 일치(`nnuecheck`), numpy 기준 구현 ↔ 엔진 출력 ≤0.5cp. **미검증**: PyTorch 학습 루프, 학습된 v2/v3 넷의 실제 대국력

테스트 도구: `tools/match.py`(고정 노드/시간 UCI 대국, 색 교대), `tools/spsa.py`(SPSA 튜닝, 재개 가능)
`python3 tools/match.py bin/terranion bin/old --games 400 --nodes 20000 --optA FProbCut=0`   (시간제는 `--nodes -40` = 40ms/수)
