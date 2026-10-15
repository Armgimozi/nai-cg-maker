# 새 몹 20종 + 소환물 1 — 복셀 모델 작업 안내 (src/mobvox)

새 몸 형태 단계에서 추가한 몹이다. 지금은 예전 상자 방식(`src/mobs.py`)으로 나오며, 다음 단계에서 모델 담당 2명이 복셀로 만든다.
등록 규칙·도구·예산은 `README.md` 그대로. **YAML(mobs.yml)의 부위 이름·pivot·anim·scale 은 고치지 않는다** — 플러그인 애니메이션이 이 값에 묶여 있다.

## 나눠 맡기 (제안 — 파일을 새로 만들어 남의 파일과 겹치지 않게)
| 담당 | 파일 | 몹 |
|---|---|---|
| A (드래곤·용인족) | `src/mobvox/new_dragons.py` | moss_drakeling · bog_drake · ember_drake · frost_wyvern · clockwork_wyvern · void_drake · thorn_kobold · kobold_sapper · forge_dragonkin · crystal_dragonkin · abyss_dragonkin |
| B (그 밖) | `src/mobvox/new_hybrids.py` | tunnel_wyrm · spore_harpy · myconid_centaur · tide_naga · barrow_lich · barrow_thrall · prism_centaur · ink_naga · quill_harpy · brass_minotaur |

빠른 반복: `/opt/packvenv/bin/python resourcepack/generate.py --out /tmp/mobvox/<라벨>/ --only-mobs void_drake,frost_wyvern --compare`

## 새 form · anim (지오메트리가 지켜야 할 것)
좌표는 README 와 같다: 단위 px(16 = 1블록), 원점 = 그 부위 pivot, **정면 = 모델 −Z**, 모델 −X = 몹의 왼쪽, `ctx.out` = 몸 바깥쪽 모델 X 부호.

| form | 원점(pivot)이 있어야 할 곳 | 뻗는 방향 | 플러그인이 하는 움직임 |
|---|---|---|---|
| `wing` | **날개 뿌리(어깨 관절)** | `ctx.out` 쪽(몸 바깥)으로 폭 w, 앞뒤 너비 d(앞전 = −Z), 두께 h | `wings_flap`: 뿌리를 축으로 Z축 회전(위아래 퍼덕 ±36°), 급강하 때 Y축으로 뒤로 55° 접음, 땅 위에선 뒤로 50° + 위로 28° 접어 둠, 브레스·포효 때 펼침 |
| `neck` | **목 뿌리(몸과 닿는 곳)** | 앞(−Z)으로 d, 위로 h — 끝이 머리 뒤에 닿는다 | `neck`: 뿌리를 축으로 yaw(머리 회전의 절반)·pitch(공격 때 앞으로 18°). 머리·턱·뿔이 목 끝에 붙어 같이 옮겨 간다 |
| `segment` | **마디 앞면 중심** | 뒤(+Z)로 d (굵기 일정) | `tail_chain`: 앞 마디 끝에 붙어 Y축으로 휜다 |
| `tail` (기존) | 앞면 중심 | 뒤(+Z)로 | `tail_chain` 이면 위와 같음(마디마다 따로 휨) |

- **사슬 이음매**: 마디 k 의 끝(뒤 끝)이 다음 마디 pivot 이다(YAML pivot 차 = 앞 마디 길이). 마디가 ±25° 까지 휘므로 **앞뒤 끝을 둥글게**(뭉툭한 원통·캡슐)
  만들면 틈이 안 보인다. 목도 같다(머리 뒤통수가 목 끝을 덮게).
- **머리 무리**: `head` 와 같은 회전으로 도는 파트 — anim `head` 인 뿔·볏·고글·후드·렌즈·코뚜레 — 는 머리 pivot 을 중심으로 돈다. 그러니 머리에 붙는
  장식은 그 파트 자신의 pivot 기준으로 만들되, 머리에서 떨어져 보이지 않게 맞닿는 면을 두껍게. `jaw` 는 머리 회전 + 벌림(−30°, 브레스 내내 벌어짐).
- **날개**: 접힌 모양(뒤로 50°, 위로 28°)과 편 모양 둘 다 어색하지 않아야 한다. 막은 얇게(h 1~2px), 뼈대(앞전 팔뼈 + 손가락뼈 3개)는 두껍게.
  뿌리 쪽 1~2px 은 몸 안으로 파묻혀도 된다(회전해도 어깨가 비지 않게).
- **급강하(dive)**: 몸 전체가 32° 앞으로 숙인다(머리 아래). **솟구침(burrow)**: 0.4초 동안 모델 전체가 바닥 아래에서 올라온다.
- 손에 쥔 무기 이름 규칙(예전 방식): `spear`/`lance`/`pike` = 자루 ⅓ 지점을 쥔 창, `bow` = 세워 쥔 활(시위가 몸 쪽), 그 밖은 README·GDD §14.6.

## 몸 형태별 부위 이름 (공통 규칙)
| shape | 부위 |
|---|---|
| `drake` (네 발 + 날개) | body · neck(또는 neck_1·neck_2) · head · jaw · horns · wing_left · wing_right · tail_1…n · legs(leg_quad) |
| `wyvern` (두 발 + 날개) | body · neck · head · jaw · horns(또는 lens) · wing_left · wing_right · tail_1…3 · legs(leg_pair) |
| `dragonkin` (용인족) | torso · head · jaw · horns(crest) · arm_left · arm_right · 무기(spear·hammer·lance·greatsword·bomb) · shield · tail(또는 tail_1·tail_2) · legs · (apron·cape·goggles·satchel·wing_left/right) |
| `naga` | coil · waist · torso · head · hood · arm_left · arm_right · 손 물건(staff·book·quill) · tail_1…3 |
| `centaur` | horse_body · legs(leg_quad) · torso · head · cap/crest · arm_left · arm_right · 무기(scythe·bow) · quiver · tail |
| `harpy` | torso · head · crest · wing_left · wing_right · tail_feathers · legs |
| `minotaur` | torso · head · horns · nose_ring · arm_left · arm_right · axe · tail · legs |
| `lich` | robe · ribcage · head(skull) · crown · arm_left · arm_right · staff · phylactery · runes |
| `worm` | head · jaw · seg_1…3 · tail |

## 몹별 부위 표 + 디자인 메모
YAML 에서 뽑은 값(scale 1 기준, 실제 크기 = × scale). 발광이 필요한 곳은 `glow`/`eye`/`core` 재질을 쓰면 아틀라스 맥동이 자동으로 붙는다.

### 1층 · 이끼 새끼용 `moss_drakeling`
base WOLF · scale 1.0 · shape `drake` · palette #16220f #2f4a1e #5f8a33 #a6c96a #ffc24a · features moss_tufts, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | rounded | [8, 7, 12] | [0, 0.5, 0] | body |
| `neck` | neck | [4, 5, 5] | [0, 0.62, 0.3] | neck |
| `head` | rounded | [6, 5, 7] | [0, 0.92, 0.78] | head |
| `jaw` | claw | [5, 2, 4] | [0, 0.8, 0.9] | jaw |
| `horns` | horn_pair | [5, 3, 2] | [0, 1.06, 0.66] | head |
| `wing_left` | wing | [11, 1, 7] | [0.2, 0.7, 0.05] | wings_flap |
| `wing_right` | wing | [11, 1, 7] | [-0.2, 0.7, 0.05] | wings_flap |
| `tail_1` | tail | [4, 4, 6] | [0, 0.52, -0.35] | tail_chain |
| `tail_2` | tail | [3, 3, 6] | [0, 0.5, -0.72] | tail_chain |
| `legs` | leg_quad | [9, 8, 10] | [0, 0.25, 0] | legs_walk |

디자인 메모: 갓 깬 새끼용 — 머리가 몸에 비해 크고 눈이 크다(호박색 발광). 등에 이끼 쿠션, 작은 날개막은 얇고 반투명한 연두. 날개는 땅에서 등 위로 반쯤 접혀 있다가 `leap` 때 퍼덕인다. 짧은 뿔 2개, 꼬리 끝에 이끼 술.

### 1층 · 가시덩굴 코볼트 `thorn_kobold`
base HUSK · scale 0.75 · shape `dragonkin` · palette #1a2410 #3a4f1e #6b8a34 #b5c97a #e8a23a · features root_tendrils, moss_tufts, glowing_eyes, leather_straps

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [8, 10, 5] | [0, 1.1, 0] | body |
| `head` | rounded | [7, 6, 9] | [0, 1.62, 0.08] | head |
| `jaw` | claw | [5, 2, 4] | [0, 1.48, 0.32] | jaw |
| `horns` | horn_pair | [6, 4, 2] | [0, 1.86, -0.05] | head |
| `arm_left` | arm | [3, 11, 3] | [0.32, 1.42, 0] | arm_left |
| `arm_right` | arm | [3, 11, 3] | [-0.32, 1.42, 0] | arm_right |
| `spear` | blade | [3, 26, 3] | [-0.32, 1.42, 0] | arm_right |
| `tail` | tail | [3, 3, 9] | [0, 0.85, -0.15] | tail |
| `legs` | leg_pair | [7, 11, 4] | [0, 0.72, 0] | legs_walk |

디자인 메모: 작은 도마뱀 머리의 비늘족 창병. 주둥이가 길고(head d 9) 턱이 따로 벌어진다. 어깨·팔뚝에 가시덩굴이 감겨 있고 가죽끈 갑옷. 창(`spear`)은 뿌리를 깎은 나무 자루 + 돌 촉. 꼬리는 가늘고 길게.

### 2층 · 코볼트 폭파병 `kobold_sapper`
base HUSK · scale 0.7 · shape `dragonkin` · palette #24160e #4f3220 #8a5a34 #c9925a #ff7a2a · features leather_straps, glowing_eyes, rust_streaks

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [8, 9, 5] | [0, 1.08, 0] | body |
| `head` | rounded | [7, 6, 9] | [0, 1.56, 0.08] | head |
| `jaw` | claw | [5, 2, 4] | [0, 1.42, 0.32] | jaw |
| `goggles` | slab | [7, 2, 1] | [0, 1.66, 0.48] | head |
| `satchel` | cylinder | [6, 7, 4] | [0, 1.12, -0.3] | body |
| `arm_left` | arm | [3, 10, 3] | [0.31, 1.36, 0] | arm_left |
| `bomb` | sphere | [5, 5, 5] | [0.31, 1.36, 0] | arm_left |
| `arm_right` | arm | [3, 10, 3] | [-0.31, 1.36, 0] | arm_right |
| `tail` | tail | [3, 3, 8] | [0, 0.8, -0.15] | tail |
| `legs` | leg_pair | [7, 10, 4] | [0, 0.66, 0] | legs_walk |

디자인 메모: 코볼트와 같은 머리, 이마에 고글(`goggles`, 머리에 붙음). 등의 화약 주머니(`satchel`)는 도화선이 삐져나온 원통, 왼손의 폭탄(`bomb`)은 둥근 쇠공 + 불붙은 심지(발광). 그을음·녹 얼룩.

### 2층 · 갱도 땅굴웜 `tunnel_wyrm`
base SPIDER · scale 0.85 · shape `worm` · palette #1e1a1a #463c38 #7a6a5e #b8a48e #d7e3ef · features teeth_ring, ore_flecks, cracked_stone

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `head` | rounded | [10, 10, 8] | [0, 0.52, 0.5] | head |
| `jaw` | claw | [9, 4, 5] | [0, 0.46, 0.82] | jaw |
| `seg_1` | segment | [10, 9, 8] | [0, 0.5, 0.25] | tail_chain |
| `seg_2` | segment | [9, 8, 8] | [0, 0.47, -0.25] | tail_chain |
| `seg_3` | segment | [8, 7, 8] | [0, 0.44, -0.75] | tail_chain |
| `tail` | tail | [6, 5, 9] | [0, 0.4, -1.25] | tail_chain |

디자인 메모: 원통형 마디 몸(갑각 띠, 광석 박힘)과 둥근 아가리. 머리 앞면 전체가 이빨 고리(`teeth_ring`)로 둘러싼 입, `jaw` 는 아래턱 집게 2쌍. 마디 사이 이음 고리는 어둡게. 눈은 퇴화(작은 점 2개 정도).

### 3층 · 포자 하피 `spore_harpy`
base BLAZE · scale 1.0 · 비행 · shape `harpy` · palette #1e1420 #432a46 #7a5276 #c49ab8 #5ee0c0 · features cap_spots, spore_glow, wing_eyespots

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | rounded | [7, 9, 5] | [0, 1.15, 0] | body |
| `head` | rounded | [6, 6, 6] | [0, 1.6, 0.02] | head |
| `crest` | cap | [8, 3, 8] | [0, 1.88, -0.02] | head |
| `wing_left` | wing | [14, 1, 8] | [0.22, 1.4, -0.02] | wings_flap |
| `wing_right` | wing | [14, 1, 8] | [-0.22, 1.4, -0.02] | wings_flap |
| `tail_feathers` | fin | [6, 2, 7] | [0, 0.82, -0.2] | tail |
| `legs` | leg_pair | [6, 10, 4] | [0, 0.86, 0] | legs_walk |

디자인 메모: 사람 상반신 + 팔 대신 날개. 머리 위 포자 버섯 갓(`crest`, cap). 날개막 끝·깃에 청록 발광 포자 점(`wing_eyespots`), 다리는 새 다리 + 발톱. 날개는 공중에서 계속 퍼덕이므로 뿌리(어깨) 쪽을 두껍게.

### 3층 · 균사 켄타우로스 `myconid_centaur`
base IRON_GOLEM · scale 0.85 · shape `centaur` · palette #231814 #4f3a2a #8c6c4c #d8c4a0 #e0443a · features cap_spots, hyphae_web, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `horse_body` | rounded | [10, 9, 18] | [0, 0.95, -0.15] | body |
| `legs` | leg_quad | [10, 13, 16] | [0, 0.41, -0.15] | legs_walk |
| `torso` | box | [9, 11, 5] | [0, 1.62, 0.32] | body |
| `head` | rounded | [6, 6, 6] | [0, 2.15, 0.34] | head |
| `cap` | cap | [13, 5, 13] | [0, 2.44, 0.34] | head |
| `arm_left` | arm | [4, 11, 4] | [0.34, 1.98, 0.32] | arm_left |
| `arm_right` | arm | [4, 11, 4] | [-0.34, 1.98, 0.32] | arm_right |
| `scythe` | blade | [10, 24, 2] | [-0.34, 1.98, 0.32] | arm_right |
| `tail` | tail | [4, 3, 10] | [0, 1.1, -0.72] | tail |

디자인 메모: 말 몸통 + 사람 상반신, 머리는 눈 없는 균사 덩어리 위에 큰 붉은 버섯 갓(`cap`, 흰 점). 몸 곳곳에 균사망. 버섯 낫(`scythe`): 휜 균사 자루 + 갓 모양 날.

### 4층 · 늪 드레이크 `bog_drake`
base SPIDER · scale 1.0 · shape `drake` · palette #0e1a14 #1f3a2c #3f6a4a #86a86a #b6e04a · features barnacles, dripping, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | rounded | [12, 10, 18] | [0, 0.62, 0] | body |
| `neck` | neck | [6, 6, 7] | [0, 0.8, 0.48] | neck |
| `head` | rounded | [8, 7, 10] | [0, 1.17, 1.2] | head |
| `jaw` | claw | [7, 3, 6] | [0, 1.0, 1.36] | jaw |
| `horns` | horn_pair | [8, 4, 2] | [0, 1.38, 1.02] | head |
| `wing_left` | wing | [14, 1, 9] | [0.3, 0.9, 0.1] | wings_flap |
| `wing_right` | wing | [14, 1, 9] | [-0.3, 0.9, 0.1] | wings_flap |
| `tail_1` | tail | [6, 6, 9] | [0, 0.66, -0.55] | tail_chain |
| `tail_2` | tail | [5, 5, 9] | [0, 0.62, -1.1] | tail_chain |
| `tail_3` | tail | [3, 3, 8] | [0, 0.58, -1.66] | tail_chain |
| `legs` | leg_quad | [13, 10, 15] | [0, 0.31, 0] | legs_walk |

디자인 메모: 낮고 넓은 네 발 드레이크, 늪 이끼와 따개비. 목이 짧고 굵음, 머리는 납작한 악어형. 턱 아래로 산성 침이 맺힘(`dripping`, 연두 발광). 날개는 작고 찢어진 막.

### 4층 · 조류의 나가 `tide_naga`
base HUSK · scale 1.1 · shape `naga` · palette #0a1a22 #1a3a48 #2f6a78 #8ac8c0 #ffd56a · features barnacles, dripping, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `coil` | rounded | [12, 7, 12] | [0, 0.24, 0.05] | body |
| `waist` | cylinder | [7, 9, 6] | [0, 0.74, 0.1] | body |
| `torso` | box | [9, 11, 5] | [0, 1.36, 0.1] | body |
| `head` | rounded | [7, 7, 7] | [0, 1.92, 0.12] | head |
| `hood` | slab | [12, 10, 1] | [0, 1.95, -0.12] | head |
| `arm_left` | arm | [3, 11, 3] | [0.33, 1.7, 0.1] | arm_left |
| `arm_right` | arm | [3, 11, 3] | [-0.33, 1.7, 0.1] | arm_right |
| `staff` | blade | [4, 26, 4] | [-0.33, 1.7, 0.1] | arm_right |
| `tail_1` | segment | [8, 6, 9] | [0, 0.22, -0.4] | tail_chain |
| `tail_2` | segment | [6, 5, 9] | [0, 0.2, -0.96] | tail_chain |
| `tail_3` | tail | [4, 3, 9] | [0, 0.18, -1.52] | tail_chain |

디자인 메모: 뱀 하반신이 바닥에 똬리(`coil`) → 허리(`waist`) → 상반신. 머리 뒤 코브라 후드(`hood`, 얇은 판, 머리에 붙어 같이 돎) 안쪽에 금빛 무늬. 지팡이(`staff`) 끝에 물방울 구슬(발광). 꼬리 3마디는 바닥을 따라 뒤로.

### 5층 · 잿불 드레이크 `ember_drake`
base RAVAGER · scale 0.75 · shape `drake` · palette #120806 #2e1410 #5a2a1a #a0522a #ff8a2a · features molten_cracks, ember_glow, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | rounded | [16, 13, 24] | [0, 0.85, 0] | body |
| `neck` | neck | [8, 8, 9] | [0, 1.12, 0.66] | neck |
| `head` | rounded | [10, 9, 13] | [0, 1.64, 1.58] | head |
| `jaw` | claw | [9, 4, 8] | [0, 1.4, 1.78] | jaw |
| `horns` | horn_pair | [12, 6, 3] | [0, 1.94, 1.34] | head |
| `wing_left` | wing | [20, 2, 12] | [0.38, 1.25, 0.15] | wings_flap |
| `wing_right` | wing | [20, 2, 12] | [-0.38, 1.25, 0.15] | wings_flap |
| `tail_1` | tail | [8, 8, 12] | [0, 0.9, -0.72] | tail_chain |
| `tail_2` | tail | [6, 6, 12] | [0, 0.85, -1.47] | tail_chain |
| `tail_3` | tail | [4, 4, 10] | [0, 0.8, -2.22] | tail_chain |
| `legs` | leg_quad | [17, 14, 20] | [0, 0.44, 0] | legs_walk |

디자인 메모: 현무암 비늘 + 갈라진 틈의 쇳물 발광(`molten_cracks`). 목을 길게 뽑아 브레스 → 목·머리 이음매가 잘 보이게. 뿔은 뒤로 휜 흑요석, 날개막 가장자리 불씨. 꼬리 끝은 잿불 덩어리.

### 5층 · 용인 대장장이 `forge_dragonkin`
base VINDICATOR · scale 1.15 · shape `dragonkin` · palette #160a08 #3a1612 #6e2a1c #b0583a #ff9a3a · features ember_glow, leather_straps, molten_cracks, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [12, 13, 7] | [0, 1.25, 0] | body |
| `apron` | slab | [10, 11, 1] | [0, 1.0, 0.26] | body |
| `head` | rounded | [8, 8, 11] | [0, 1.9, 0.1] | head |
| `jaw` | claw | [6, 3, 5] | [0, 1.72, 0.42] | jaw |
| `horns` | horn_pair | [10, 6, 3] | [0, 2.16, -0.05] | head |
| `arm_left` | arm | [5, 13, 5] | [0.47, 1.62, 0] | arm_left |
| `arm_right` | arm | [5, 13, 5] | [-0.47, 1.62, 0] | arm_right |
| `hammer` | blade | [12, 20, 8] | [-0.47, 1.62, 0] | arm_right |
| `tail_1` | tail | [5, 5, 10] | [0, 0.92, -0.24] | tail_chain |
| `tail_2` | tail | [3, 3, 9] | [0, 0.86, -0.86] | tail_chain |
| `legs` | leg_pair | [10, 13, 5] | [0, 0.82, 0] | legs_walk |

디자인 메모: 덩치 큰 용인 대장장이: 가죽 앞치마(`apron`), 그을린 팔 토시, 망치(`hammer`)는 모루 같은 쇠머리. 목덜미 비늘 사이로 불빛(`ember_glow`). 꼬리 2마디.

### 6층 · 서리 와이번 `frost_wyvern`
base BAT · scale 1.9 · 비행 · shape `wyvern` · palette #16202e #2e4a66 #6a9ac0 #cfe8f8 #8af0ff · features frost_rime, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | rounded | [7, 6, 10] | [0, 0.62, 0] | body |
| `neck` | neck | [3, 4, 5] | [0, 0.7, 0.28] | neck |
| `head` | rounded | [5, 4, 6] | [0, 0.95, 0.76] | head |
| `jaw` | claw | [4, 2, 3] | [0, 0.86, 0.86] | jaw |
| `horns` | horn_pair | [5, 3, 2] | [0, 1.06, 0.66] | head |
| `wing_left` | wing | [16, 1, 9] | [0.18, 0.76, 0.05] | wings_flap |
| `wing_right` | wing | [16, 1, 9] | [-0.18, 0.76, 0.05] | wings_flap |
| `tail_1` | tail | [3, 3, 6] | [0, 0.62, -0.3] | tail_chain |
| `tail_2` | tail | [2, 2, 6] | [0, 0.6, -0.67] | tail_chain |
| `tail_3` | tail | [2, 2, 5] | [0, 0.58, -1.04] | tail_chain |
| `legs` | leg_pair | [5, 6, 3] | [0, 0.4, 0] | legs_walk |

디자인 메모: 두 발 + 날개 와이번. 날개가 몸의 3배 — 얼음 막(반투명 하늘색) + 서리 낀 뼈. 꼬리 끝은 얼음 송곳(`tail_3`). 급강하 때 날개가 뒤로 접히므로 접혔을 때 몸과 겹치지 않게 뿌리를 몸 옆에.

### 6층 · 고분의 리치 `barrow_lich`
base HUSK · scale 1.05 · shape `lich` · palette #0e1018 #262a3a #4a5268 #c8d4e0 #7ad8ff · features frost_rime, hollow_eyes, tattered_cloth, bone_ribs

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `robe` | cloak | [10, 14, 7] | [0, 1.05, 0] | body |
| `ribcage` | box | [8, 8, 5] | [0, 1.62, 0] | body |
| `head` | skull | [7, 7, 7] | [0, 2.08, 0.02] | head |
| `crown` | crystal_cluster | [7, 4, 7] | [0, 2.42, 0.02] | head |
| `arm_left` | arm | [3, 12, 3] | [0.34, 1.9, 0] | arm_left |
| `arm_right` | arm | [3, 12, 3] | [-0.34, 1.9, 0] | arm_right |
| `staff` | blade | [4, 28, 4] | [-0.34, 1.9, 0] | arm_right |
| `phylactery` | lantern | [4, 5, 4] | [0.3, 1.2, 0.2] | float |
| `runes` | ring | [18, 2, 18] | [0, 1.4, 0] | orbit |

디자인 메모: 땅에서 떠 있는 해골 마법사: 해진 로브 자락(바닥에 안 닿음), 갈비뼈가 드러난 가슴, 해골에 얼음 수정 왕관(`crown`). 허리 앞 영혼 등불(`phylactery`, 발광), 허리를 도는 룬 고리(`runes`, orbit). 지팡이 끝 냉기 수정.

### 6층 · 고분 해골병 `barrow_thrall`
base HUSK · scale 0.95 · shape `humanoid` · palette #2a2620 #5a5244 #a89c84 #e8e0cc #7ad8ff · features bone_ribs, hollow_eyes, frost_rime

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [8, 11, 4] | [0, 1.15, 0] | body |
| `head` | skull | [7, 7, 7] | [0, 1.62, 0] | head |
| `arm_left` | arm | [3, 12, 3] | [0.34, 1.45, 0] | arm_left |
| `arm_right` | arm | [3, 12, 3] | [-0.34, 1.45, 0] | arm_right |
| `sword` | blade | [3, 16, 2] | [-0.34, 1.45, 0] | arm_right |
| `legs` | leg_pair | [7, 12, 3] | [0, 0.75, 0] | legs_walk |

디자인 메모: 리치가 부르는 소환물. 녹슨 투구 조각이 남은 해골 근위병, 짧은 칼. 작고 값싸게(소환물 예산 ≤ 600).

### 7층 · 수정 용인 창기사 `crystal_dragonkin`
base HUSK · scale 1.15 · shape `dragonkin` · palette #160e24 #34205a #6a4aa8 #c8a8ff #f4ecff · features crystal_growth, prism_glint, plate_armor, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [11, 13, 6] | [0, 1.28, 0] | body |
| `head` | rounded | [7, 8, 10] | [0, 1.9, 0.08] | head |
| `jaw` | claw | [5, 3, 4] | [0, 1.72, 0.38] | jaw |
| `crest` | crystal_cluster | [8, 6, 5] | [0, 2.2, -0.05] | head |
| `arm_left` | arm | [4, 13, 4] | [0.43, 1.64, 0] | arm_left |
| `shield` | slab | [12, 16, 2] | [0.43, 1.64, 0] | arm_left |
| `arm_right` | arm | [4, 13, 4] | [-0.43, 1.64, 0] | arm_right |
| `lance` | blade | [4, 34, 4] | [-0.43, 1.64, 0] | arm_right |
| `tail_1` | tail | [5, 5, 9] | [0, 0.95, -0.2] | tail_chain |
| `tail_2` | tail | [3, 3, 9] | [0, 0.89, -0.76] | tail_chain |
| `legs` | leg_pair | [9, 13, 5] | [0, 0.84, 0] | legs_walk |

디자인 메모: 자수정 비늘 판갑을 두른 용인 기사. 머리 볏이 수정 다발(`crest`). 왼손 수정 방패(`shield`, 바깥을 봄)는 큰 육각 수정판, 오른손 긴 창(`lance`)은 수정 촉. 꼬리 2마디 끝에 수정.

### 7층 · 프리즘 켄타우로스 `prism_centaur`
base IRON_GOLEM · scale 0.85 · shape `centaur` · palette #1a1a2e #3a3a6a #8a8ad0 #e8f0ff #ff7ae0 · features crystal_growth, prism_glint, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `horse_body` | rounded | [10, 9, 18] | [0, 0.95, -0.15] | body |
| `legs` | leg_quad | [10, 13, 16] | [0, 0.41, -0.15] | legs_walk |
| `torso` | box | [9, 11, 5] | [0, 1.62, 0.32] | body |
| `head` | rounded | [7, 7, 7] | [0, 2.17, 0.34] | head |
| `crest` | crystal_cluster | [6, 5, 5] | [0, 2.48, 0.3] | head |
| `arm_left` | arm | [3, 11, 3] | [0.34, 1.98, 0.32] | arm_left |
| `bow` | blade | [3, 22, 8] | [0.34, 1.98, 0.32] | arm_left |
| `arm_right` | arm | [3, 11, 3] | [-0.34, 1.98, 0.32] | arm_right |
| `quiver` | cylinder | [3, 9, 3] | [-0.18, 1.72, 0.08] | body |
| `tail` | tail | [4, 3, 10] | [0, 1.1, -0.72] | tail |

디자인 메모: 하얀 수정 말 몸 + 궁수 상반신. 왼손 활(`bow`, 손에 세워 쥠 — 시위가 몸 쪽), 등 뒤 화살통(`quiver`). 갈기 대신 프리즘 결정, 무지개 하이라이트(`prism_glint`).

### 8층 · 먹물 나가 `ink_naga`
base HUSK · scale 1.15 · shape `naga` · palette #06060c #141a2e #2a3a6a #8a96c0 #e8e0c8 · features ink_drips, ink_scribbles, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `coil` | rounded | [12, 7, 12] | [0, 0.24, 0.05] | body |
| `waist` | cylinder | [7, 9, 6] | [0, 0.74, 0.1] | body |
| `torso` | box | [9, 11, 5] | [0, 1.36, 0.1] | body |
| `head` | rounded | [7, 7, 7] | [0, 1.92, 0.12] | head |
| `hood` | slab | [12, 10, 1] | [0, 1.95, -0.12] | head |
| `arm_left` | arm | [3, 11, 3] | [0.33, 1.7, 0.1] | arm_left |
| `book` | book | [6, 7, 2] | [0.33, 1.7, 0.1] | arm_left |
| `arm_right` | arm | [3, 11, 3] | [-0.33, 1.7, 0.1] | arm_right |
| `quill` | blade | [6, 22, 2] | [-0.33, 1.7, 0.1] | arm_right |
| `tail_1` | segment | [8, 6, 9] | [0, 0.22, -0.4] | tail_chain |
| `tail_2` | segment | [6, 5, 9] | [0, 0.2, -0.96] | tail_chain |
| `tail_3` | tail | [4, 3, 9] | [0, 0.18, -1.52] | tail_chain |

디자인 메모: 먹물 웅덩이 같은 검푸른 뱀 하반신, 후드 안쪽에 잉크 글씨(`ink_scribbles`). 왼손 펼친 책(`book`), 오른손 커다란 깃펜(`quill`). 몸에서 먹물이 흘러내림.

### 8층 · 깃펜 하피 `quill_harpy`
base BLAZE · scale 1.05 · 비행 · shape `harpy` · palette #0a0a12 #1e2236 #3a4468 #e8e0c8 #5a7ab0 · features paper_scraps, ink_drips, wing_eyespots

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | rounded | [7, 9, 5] | [0, 1.15, 0] | body |
| `head` | rounded | [6, 6, 6] | [0, 1.6, 0.02] | head |
| `crest` | fin | [2, 5, 7] | [0, 1.9, -0.06] | head |
| `wing_left` | wing | [15, 1, 9] | [0.22, 1.4, -0.02] | wings_flap |
| `wing_right` | wing | [15, 1, 9] | [-0.22, 1.4, -0.02] | wings_flap |
| `tail_feathers` | fin | [6, 2, 8] | [0, 0.82, -0.2] | tail |
| `legs` | leg_pair | [6, 10, 4] | [0, 0.86, 0] | legs_walk |

디자인 메모: 날개깃이 전부 깃펜(양피지색 깃 + 검은 펜촉). 머리 볏은 깃펜 다발(`crest`, fin). 날개막 대신 겹친 종이 깃, 잉크 방울.

### 9층 · 태엽 와이번 `clockwork_wyvern`
base BAT · scale 2.0 · 비행 · shape `wyvern` · palette #1a120a #4a3018 #8a5a2a #d8a85a #5ae0d0 · features brass_trim, rivets, clockface_wings, electric_veins

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | box | [7, 6, 10] | [0, 0.62, 0] | body |
| `mainspring` | gear | [6, 1, 6] | [0, 0.83, -0.05] | spin |
| `neck` | neck | [3, 4, 5] | [0, 0.7, 0.28] | neck |
| `head` | box | [5, 4, 6] | [0, 0.95, 0.76] | head |
| `jaw` | claw | [4, 2, 3] | [0, 0.86, 0.86] | jaw |
| `lens` | eye | [3, 3, 2] | [0, 0.98, 1.06] | head |
| `wing_left` | wing | [17, 1, 9] | [0.18, 0.76, 0.05] | wings_flap |
| `wing_right` | wing | [17, 1, 9] | [-0.18, 0.76, 0.05] | wings_flap |
| `tail_1` | tail | [3, 3, 6] | [0, 0.62, -0.3] | tail_chain |
| `tail_2` | tail | [2, 2, 6] | [0, 0.6, -0.67] | tail_chain |
| `tail_3` | tail | [2, 2, 5] | [0, 0.58, -1.04] | tail_chain |
| `legs` | leg_pair | [5, 6, 3] | [0, 0.4, 0] | legs_walk |

디자인 메모: 놋쇠 판 + 리벳의 기계 와이번. 등에 수평 태엽 톱니(`mainspring`, spin), 머리 앞 렌즈 눈(`lens`, 발광·광선 발사구), 날개는 시계판 무늬 금속 날개(`clockface_wings`). 꼬리 마디는 체인처럼.

### 9층 · 황동 미노타우로스 `brass_minotaur`
base IRON_GOLEM · scale 0.95 · shape `minotaur` · palette #140c06 #3a2410 #7a5020 #d8a048 #ff6a2a · features brass_trim, rivets, coil_spring, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [14, 14, 8] | [0, 1.62, 0] | body |
| `head` | box | [9, 9, 10] | [0, 2.32, 0.14] | head |
| `horns` | horn_pair | [18, 6, 4] | [0, 2.62, 0.06] | head |
| `nose_ring` | ring | [4, 4, 1] | [0, 2.16, 0.46] | head |
| `arm_left` | arm | [6, 15, 6] | [0.56, 2.0, 0] | arm_left |
| `arm_right` | arm | [6, 15, 6] | [-0.56, 2.0, 0] | arm_right |
| `axe` | blade | [14, 30, 4] | [-0.56, 2.0, 0] | arm_right |
| `tail` | tail | [3, 12, 3] | [0, 1.25, -0.28] | tail |
| `legs` | leg_pair | [12, 18, 6] | [0, 1.18, 0] | legs_walk |

디자인 메모: 황동으로 다시 빚은 소머리 거인: 큰 뿔(`horns`), 코뚜레(`nose_ring`), 가슴의 태엽 용수철(`coil_spring`), 굽 달린 다리. 양날 도끼(`axe`). 콧김(증기)은 입자로 처리되므로 콧구멍만.

### 10층 · 심연 고룡 `void_drake`
base RAVAGER · scale 1.05 · shape `drake` · palette #020306 #08121a #123842 #2a6a72 #2fe0d0 · features sculk_veins, glowing_eyes

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `body` | rounded | [20, 16, 26] | [0, 1.1, 0] | body |
| `neck_1` | neck | [10, 9, 10] | [0, 1.42, 0.74] | neck |
| `neck_2` | neck | [8, 8, 9] | [0, 1.98, 1.36] | neck |
| `head` | rounded | [12, 10, 16] | [0, 2.5, 2.38] | head |
| `jaw` | claw | [11, 4, 10] | [0, 2.24, 2.62] | jaw |
| `horns` | horn_pair | [16, 8, 4] | [0, 2.86, 2.0] | head |
| `wing_left` | wing | [30, 2, 18] | [0.5, 1.62, 0.2] | wings_flap |
| `wing_right` | wing | [30, 2, 18] | [-0.5, 1.62, 0.2] | wings_flap |
| `tail_1` | tail | [10, 10, 12] | [0, 1.15, -0.8] | tail_chain |
| `tail_2` | tail | [8, 8, 12] | [0, 1.08, -1.55] | tail_chain |
| `tail_3` | tail | [6, 6, 10] | [0, 1.0, -2.3] | tail_chain |
| `tail_4` | tail | [4, 4, 10] | [0, 0.94, -2.92] | tail_chain |
| `legs` | leg_quad | [22, 18, 22] | [0, 0.56, 0] | legs_walk |

디자인 메모: 가장 큰 네 발 고룡(전체 길이 ≈ 6.5블록). 목 2마디(`neck_1`→`neck_2`)가 길게 휘고, 꼬리 4마디가 꼬리 휩쓸기 때 크게 휜다 — 마디 끝마다 등가시. 검은 비늘에 청록 스컬크 맥(`sculk_veins`) 발광, 날개막은 별빛 점.

### 10층 · 심연 용인 기사 `abyss_dragonkin`
base VINDICATOR · scale 1.25 · shape `dragonkin` · palette #030308 #0e1020 #1e2a44 #3a5a7a #2fe0d0 · features sculk_veins, plate_armor, glowing_eyes, tattered_cloth

| 부위 | form | size(px) | pivot(블록) | anim |
|---|---|---|---|---|
| `torso` | box | [12, 14, 7] | [0, 1.32, 0] | body |
| `cape` | cloak | [12, 16, 3] | [0, 1.15, -0.26] | body |
| `head` | rounded | [8, 8, 11] | [0, 1.98, 0.1] | head |
| `jaw` | claw | [6, 3, 5] | [0, 1.8, 0.42] | jaw |
| `horns` | horn_pair | [12, 7, 3] | [0, 2.26, -0.05] | head |
| `wing_left` | wing | [16, 1, 9] | [0.3, 1.78, -0.22] | wings_flap |
| `wing_right` | wing | [16, 1, 9] | [-0.3, 1.78, -0.22] | wings_flap |
| `arm_left` | arm | [5, 14, 5] | [0.47, 1.72, 0] | arm_left |
| `arm_right` | arm | [5, 14, 5] | [-0.47, 1.72, 0] | arm_right |
| `greatsword` | blade | [5, 30, 3] | [-0.47, 1.72, 0] | arm_right |
| `tail_1` | tail | [5, 5, 10] | [0, 0.98, -0.26] | tail_chain |
| `tail_2` | tail | [3, 3, 9] | [0, 0.92, -0.88] | tail_chain |
| `legs` | leg_pair | [10, 14, 5] | [0, 0.88, 0] | legs_walk |

디자인 메모: 심연 판갑의 용인 기사. 등에 접힌 날개(땅 위에선 접힘, 브레스 때 펼침), 뒤에 해진 망토(`cape`). 대검(`greatsword`)에 청록 룬. 투구형 머리 + 뿔.
