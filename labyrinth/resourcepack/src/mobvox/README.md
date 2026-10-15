# 몹·보스 복셀 설계 (src/mobvox)

몹 부위를 작은 정육면체(복셀)로 쌓아 만든다. 도구는 `src/voxel/mob_kit.py`, 셰이딩·병합·예산은 `src/voxel/mob_build.py`.
설계 함수가 없는 몹·부위는 예전 상자 방식(`src/mobs.py`) 그대로 나온다.

## 등록 규칙
- 파일마다 `DESIGNS = {mob_id: 설계함수}`. 담당: `f01_03.py` `f04_06.py` `f07_08.py` `f09_10.py` `bosses.py` (자기 파일만 고친다).
  이 폴더의 파일은 자동 import — import 가 깨지면 경고만 내고 그 파일만 건너뛴다(남의 작업을 막지 않음).
- `설계함수(look, part_name, part_def, ctx) -> MobGrid | None` — 부위마다 한 번 불린다. `None` = 그 부위는 예전 방식.
  `g = ctx.grid(vs)` 로 만들고(vs = 복셀 1개의 px, 기본 `ctx.vs`), 칠해서 돌려준다. 예외가 나면 그 부위만 예전 방식 + 경고.
- `ctx`: `name form anim size(w,h,d px) pivot out(몸 바깥쪽 모델 X 부호) hang hand(손에 쥔 부위의 손 위치) features
  floor theme rank boss rng shared(몹 전체 공유 dict)`, `ctx.offset_to('head')` = 다른 부위 pivot 까지의 모델 px 벡터.
- YAML(mobs.yml·bosses.yml)의 parts 이름·pivot·anim·scale·히트박스는 **고치지 않는다**. 모델 id·출력 형식은 생성기가 지킨다.

## 좌표 (플러그인과의 약속)
- 단위 = 부위 px(16 = 1블록, YAML `size` 와 같음), 원점 = 그 부위의 pivot, **정면 = 모델 −Z**, 모델 −X = 몹의 왼쪽.
- 머리·몸·고리·수정 등 = pivot 이 부피 중심. 팔(`arm`/`tentacle_cluster` + arm_left/right) = pivot(어깨)에서 **아래로** y 0 → −h.
  다리 `leg_pair`(legs_walk) = 엉덩이 pivot 에서 아래로 매달림(발바닥 = y −h). `leg_six/eight/quad` = pivot 중심(땅 = 몸 아래).
  꼬리 = pivot 에서 뒤(**+Z**)로. 손에 쥔 부위(팔과 pivot·anim 같음) = `ctx.hand` 에서 앞(−Z)으로 뻗기(방패는 ±X).
  새 몸 형태(드래곤·용인족·나가·켄타우로스 …): `wing` = 어깨 pivot 에서 `ctx.out` 쪽으로, `neck` = 목 뿌리 pivot 에서 앞·위로,
  `segment` = 앞면 pivot 에서 뒤로. 목·꼬리 사슬·머리 무리·날개 퍼덕임 규칙과 새 몹 21종의 부위 표 = **`NEW_MOBS.md`**.
- 모든 요소가 pivot 기준 ±23.5px 를 넘으면 생성기가 자동으로 줄이고 `display.fixed.scale = 1/s` 로 복원(최대 4배).

## 도구 (MobGrid, 전부 px 단위)
- 부피: `blob`(타원체, lump=울퉁불퉁) `rbox`(모서리 깎은 상자) `capsule`(둥근 끝) `cylinder`(평평한 끝) `sweep`(스플라인 관) `limb`(관절 팔다리)
  `cone` `ring` `slab2d`(2D 윤곽 돌출)
- 표면: `paint` `carve` `carve_blob` `mottle`(덩어리 얼룩) `gradient` `bands` `streaks`(녹물·잉크 흘러내림) `cracks`(균열/발광 맥) `hit`
- 생물: `eye`/`eyes`(발광 눈+눈구멍) `teeth` `mouth` `horn` `spikes` `plates`(겹친 갑각판) `scales` `fur` `moss`(쿠션)
  `moss_paint`(표면을 이끼로 — 싸다) `clumps` `sprinkle`(고사리·꽃·발광 봉오리·늘어진 가닥) `vine` `vine_wrap` `branch`(뿔·뿌리·산호)
  `mushroom` `crystals` `wing`(뼈대+막, 해진 가장자리) `tentacle`(빨판) `cloth`(해진 천 자락) `plate`(+리벳) `rivets` `gear` `runes` `chain` `strands`(거미줄)
- 재질 = `voxel/palette.py` 의 램프 이름: 무기 재질 전부(metal blade orn wood crystal scale bone leaf vine flame ice ink paper …) +
  `skin skin2 alt chitin fur moss lichen stone flesh mouth tooth claw horn rust iron brass membrane web cap gill water bark frost void`.
  발광(alpha 252, 애니메이션 맥동): `glow eye core rune lava` 또는 `glow=True`. 값 `val` 0..1 = 램프 위치(0 = 가장 어두움).
- 색 바꾸기: `ctx.set_ramp('chitin', [어두움 … 밝음])`(몹 전체) / `g.set_ramp(...)`(그 부위만). 새 재질 이름도 램프만 주면 된다.

## 성능 예산 (요소 = 합쳐진 상자 수)
- 일반 ≤ 900, 정예(elite) ≤ 1400, 소환(add) ≤ 600, 보스 ≤ 3000, 부위 하나 ≤ 720 (예전 방식 부위도 합계에 포함).
- 넘으면 자동으로 색 잡음 → 색 단계(램프 절반)를 줄이고, 그래도 넘으면 **더 큰 복셀로 다시 만든다(경고)** — 경고가 나오면 vs·디테일로 직접 맞출 것.
- 비용 감각: 대각선으로 가는 가는 관(다리)·곡면 = 비쌈, 축에 맞춘 면 = 쌈. 표면 무늬(streaks·scales·cracks)는 상자를 쪼갠다.
  `moss` 쿠션보다 `moss_paint`+`clumps` 가 훨씬 싸다. 큰 부위는 vs 0.65~1.0, 얼굴·작은 부위는 0.5.

## 빠른 반복 (출력은 꼭 자기 폴더로)
```
/opt/packvenv/bin/python resourcepack/generate.py --out /tmp/mobvox/<라벨>/ --only-mobs moss_crawler,rusted_miner --compare
```
`--only-mobs` = 그 몹만 + 몹 검사만(zip 없음), `preview_mobs.png` 칸에 요소 수(V = 복셀). `--compare` = `compare_mobs.png`
(예전/새 방식 정면 3/4 + 새 방식 뒤·옆). PNG 는 Read 로 직접 보고 고친다.

## 좋은 예 (시범 3종)
- `f01_03.py` **moss_crawler**: 갑각판 `plates` + `moss_paint`·`clumps`·`sprinkle`, 앰버 눈, 큰 뒷다리(점프), 900 요소.
- `f01_03.py` **rusted_miner**: 7부위 사람형, 녹 반점·녹물 `streaks`, 리벳 판, 손에 쥔 곡괭이(`ctx.hand`), 880 요소.
- `bosses.py` **floor01_moss_warden**: 석조 `_masonry` 무늬, 청동띠+룬, 수정 심장과 발광 뿌리맥, 이끼 망토, 나뭇가지 뿔, 2979 요소.
