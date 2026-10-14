# 마을 설계 도구 (tools/village)

계약은 `VILLAGE.md` (특히 §0 지형 존중, §2 청사진, §3 layout). 파이썬: `/opt/packvenv/bin/python`.

| 파일 | 하는 일 |
|---|---|
| `vlib.py` | 조각 캔버스 + 블록·모양 도우미 + 연결 상태 계산 + 검증 + JSON 내보내기 |
| `render.py` | 등각 PNG (조각 / 마을 전체 / 서버 덤프) |
| `build_all.py` | `pieces_*.py` 전부 → `plugin/src/main/resources/village/` + 검증 (+ `--render`) |
| `layout.py` | 마을 배치 `LAYOUT` (조립 담당) — 조각 기준 자리·방향·길. `pieces_signs.py` = 배치에 맞춘 표지판 글 |
| `blockdata.json` | 26.x 블록 상태 표·색 (생성물, `gen_blockdata.py` 로만 다시 만듦) |

**조각 하나 만들기** — `pieces_<주제>.py` 에 `Piece` 를 돌려주는 인자 없는 함수를 쓰고 끝에 `PIECES = [함수, ...]`.
- 좌표: 정면(문)은 **z=0 줄, 북쪽**을 본다. x+ = 동, z+ = 남, y+ = 위. `floor_y` 층이 바닥(사람은 floor_y+1 에 섬), 그 아래는 땅속 기초.
- 칸 값: `' '` = 원래 지형 그대로(건물 윤곽 밖은 비워 둘 것 — 지형을 덮지 않게), `'.'` = 공기여야 함(**실내·통로는 반드시** `clear()`),
  그 밖 = 블록. 블록 이름은 `'stone_bricks'` 처럼 줄여 써도 된다. 없는 블록·속성은 그 자리에서 예외 (예: `chain` → `iron_chain`).
- 칸: `set get fill clear hollow_box replace`, 섞기: `mix(("stone_bricks",4),("mossy_stone_bricks",1))` 를 블록 자리에 넣으면 칸마다 고름.
- 블록: `stairs(mat, facing, half)` `slab` `log(mat, axis)` `leaves`(persistent 강제) `fence` `wall` `pane(color)` `bars` `trapdoor`
  `lantern(soul, hanging)` `candle(color, n)` `chain` `campfire` `torch` `flower_pot` `B(id, **속성)` — 재료는 `'oak'`, `'deepslate_tiles'` 등.
- 두 칸·글: `p.door(mat,x,y,z,facing)` `p.bed(color,x,y,z,facing)` `p.tall_plant` `p.sign(x,y,z,lines,...)` `p.banner(x,y,z,color,patterns)`.
- 모양: `gable_roof` `hip_roof` `spire` `arch` `disc` `cylinder` `timber_wall` `window` `chimney` `column` `staircase` — 인자는 docstring.
  지붕은 벽 바깥 테두리를 넘겨 처마를 낸다(`overhang`). 굴뚝·지붕 장식은 **지붕 다음에** 그린다.
- 마커: `p.npc(id,x,y,z,face)` `p.entrance` `p.spawn` `p.interact(action,[pos])` `p.ambient(x,y,z,fx)` `p.light`. face = front/back/left/right.
- 계단 모양(inner/outer)·울타리/판유리/담장 연결·빠진 속성 기본값은 `finalize()` 가 이웃을 보고 채운다 — 직접 쓰지 말 것.

**검증·렌더**
```
/opt/packvenv/bin/python tools/village/build_all.py                      # 생성 + 검증 (오류면 아무것도 안 씀)
/opt/packvenv/bin/python tools/village/build_all.py --render --only forge --rotations   # /tmp/village_renders/forge_ne.png …
/opt/packvenv/bin/python tools/village/render.py --piece <json> --out /tmp/x.png --view all --top
/opt/packvenv/bin/python tools/village/render.py --dump dump.txt --out /tmp/world.png --top   # village dump 결과
```
검증이 잡는 것: 블록 문자열·26.x 속성, 금지 블록, 잎 persistent, 문·침대·큰 꽃 짝, 받침 없는 매단 등불·벽 표지판·떨어지는 모래,
닫힌 실내의 `' '`, 웅덩이 밖 물, 마커 위치·종류, anchor; layout 은 조각끼리·길과 1칸 여유(Java 와 같은 규칙), 정문 앞 막힘, 반경, spawn/entrance 1개, npc id.
렌더는 ne(북동에서: 정면=오른쪽 면) · sw 두 장이 기본. 렌더를 직접 보고 고친다 — 밋밋한 상자·한 가지 블록 넓은 면은 실패(§5).
