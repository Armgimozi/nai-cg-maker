# 미궁 라비린스 0.3.5 — 회의적 검토 2판 (review2)

검토한 것: `combat_spec` · `unique_spec`(+ `unique_assign_all/new`) · `look_spec` · `gear_spec` · `pvp_spec`.
대조한 것: 0.3.4.2 코드(`claude/bold-darwin-nwa5vk`, 읽기만) · content/*.yml · 리소스팩 · Paper 26.3 API jar.
저장소는 건드리지 않았다. 검토 도구와 결과는 모두 `design2/tools/rv_*.py`, `rv2_*.py` 와 같은 이름의 `.json` 이다(§7).

## 0. 한눈에

- **방향은 맞다.** 다섯 명세가 주인 결정(종류 없음, 게이지 없음, STR 물리·INT 마법, AND 요구, 층 이름표 없음)을 모두 따른다.
- **그대로 합치면 안 된다.** 명세끼리 어긋나는 곳이 14군데다(§1.A). 어느 쪽이 이기는지 정했다.
- **가장 큰 문제는 "직업마다 고를 것이 있는가"다.** 띠 전체로는 무기가 22~25개지만, 한 직업이 알맞게 낄 수 있는 것만 보면 60칸(직업 6 × 띠 10) 중 **20칸만** 통과한다. 17칸은 대장간·보스 무기가 모든 상황에서 이긴다. 주인 바람 (1)·(3)에 바로 걸린다(§1.B).
  - 데이터 고침 23개로 43칸, 무기 8개를 더 바꾸거나 넣으면 55칸이 된다.
- **그림자가 깊은 층에서 약해진다.** 10층 숙련 솔로 클리어 50% → 22%(300판). 직업 값 두 개로 44% 까지 되돌린다(§1.G).
- **공격 속도 상한이 민첩 직업에게 이미 꽉 찬다.** Lv40 넘으면 민첩만으로 +60% 에 닿아 가죽·가속 효과가 죽는다. 상한을 나눠 고친다(§1.C).
- 나머지(코드 자리, API, PvP 규칙, 획득처, 그림 자원)는 작은 고침만 있으면 된다.
- 끝에 합친 구현 계획(P0 ~ P6)을 파일 주인·순서와 함께 적었다(§5).

## 1. 꼭 고칠 것

번호 앞 표시: **[막음]** = 고치지 않으면 구현을 시작하면 안 됨 · **[중요]** = 주인 바람·규칙이 깨짐 · **[작음]** = 구현하며 고치면 됨.

### 1.A 명세끼리 어긋남 — 어느 쪽이 이기나

| # | 무엇 | 어긋남 | 정함 |
|---|---|---|---|
| A1 **[막음]** | 방어구 요구치 | gear_spec §3.3 과 look_spec §3.2 가 119부위 중 **92부위**에서 다르다. gear 는 50/30/20 셋 나눔이 많고 앞 능력치가 겉모습과 안 맞는 세트도 있다(불씨 단조 = 힘 32 · 체력 19 · 지능 13). | **look_spec 표 + 아래 고침 3개**. gear_spec §3.3 표는 버린다. |
| A2 **[막음]** | look_spec 표 그대로의 구멍 | 비전술사 21–25 · 26–30 에서 알맞은 무기가 2개 · 1개, 사냥꾼·그림자 46–50 에서 제 겉모습(가죽)으로 알맞은 무기 0개 (`rv_reqmerge.json`). | 심연 보행자 `abyss_walker` 민첩/**힘**(행운 줄 → 힘), 별 없는 성가대 `starless_choir` **지능**/체력(정신 줄 → 체력), 잿불 성가자 `cinder_cantor` 지능/**체력**(정신 줄 → 체력). 고친 뒤 모든 칸 ≥ 3 (`rv_lookfix.json`). |
| A3 **[막음]** | 요구 합 공식 | 무기 T = ceil(2.75(L−1)), 방어구 T = ceil(1.1 × ceil(2.5(L−1))). 12개 레벨에서 1 다르다. 두 명세의 데이터 테스트가 서로를 깬다. | **하나로: T = ceil(2.75(L−1))**, 두 개 60/40, 세 개 50/30/20(L ≥ 12). 방어구는 앞 능력치 = 겉모습(판금·방패 VIT, 가죽 DEX, 천 INT 또는 WIS), 두 능력치만. |
| A4 **[중요]** | 장비 `classes` | gear 는 삭제(드롭 편향 = 요구 능력치), look §8 은 "요구 짝으로 다시 채움". | **삭제**. 드롭 편향은 `own_build_bias` 하나. look §8 그 줄을 지운다. |
| A5 **[작음]** | 시작 옷·이끼 투구 겉모습 | gear §3.3 은 수련생 = 가죽, 이끼 투구 = 모두. | look 대로: 수련생·길잡이 = 평상복(`look_effects: false`), 이끼 투구 = 판금. |
| A6 **[막음]** | 새 무기 `unique` 블록 | gear_spec.json 새 무기 106개 중 **30개**의 효과·수치가 TASK D 결과와 다르다(균사 단도 hemorrhage → rend 등). | **`unique_assign_all.json` 이 이긴다.** 생성기는 unique 를 거기서만 읽는다. |
| A7 **[작음]** | 한 방 피해 6개 | gear 가 ±5% 규칙에 맞춰 1점씩 다시 반올림(ore_kris 등). | gear 값 채택. combat_spec.json `per_hit` 도 같은 값으로. |
| A8 **[작음]** | 지능 활·지능 근접 8개의 피해 종류 | gear_spec.json 은 `kind: magic`, 그런데 계산 도구(g2_core·ud_*)는 physical 로 읽었다. | 데이터는 magic 이 맞다. 다시 세면 비전술사 26–30 알맞은 무기 3 → 4 (`rv2_kindfix.json`). D 의 공정성 표 8줄은 다시 만든다. |
| A9 **[중요]** | PvP 규칙 세 곳 | combat_spec §8.1 "0.7 · 35% 그대로", unique_spec §2·§7 "기절 → 느려짐, ×0.7·35%". | **pvp_spec 이 이긴다**(상한 없음, 기절 그대로). pvp_spec §9.5 상태이상 표는 D 의 새 값(방패 강타 N번째 3~5, 기절 시간)으로 다시 만든다. |
| A10 **[작음]** | 툴팁 보기 | combat_spec §7.1 보기에 "영웅 무기 · 지하 4층" 이 남아 있다. | 층 글자 없음. 무기 첫 줄 "영웅 무기 · ✦ 아우라", 방어구 첫 줄 "영웅 판금 흉갑". |
| A11 **[작음]** | 1판의 종류 기준 글 | unique_spec §4 종류별 표, §7 `ranged_only = 활·지팡이`, UniqueDiversityTest "같은 weapon_type". | 방식(`attack.style`: 원거리·시전) 기준으로. §4 표는 문서에서 뺀다. |
| A12 **[작음]** | 이름 겹침 | 고유 효과 id `shield_bash` 가 수호기사 직업 스킬 id 와 같다. PvP 배율·로그·테스트에서 헷갈린다. | 고유 효과 id 를 `bash_stun` 으로(툴팁 이름은 무기마다 따로라 그대로). |
| A13 **[막음]** | 강화 재료 생성기 | `tools/gen_enhance.py` 가 `floor`·`weapon_type`·`gear_fNN_common` 을 읽는다. 0.3.5 데이터(tier·attack·PICK·시련/특별/금고 표)를 못 읽는다. gear_spec 에 이 일이 없다. | P3 에 넣는다: `gear_floor` → tier, `kind_of` → 방식(근접 = 단단한 재료, 원거리·시전 = 부드러운 재료), `expand_items`·`expect` 가 `pick` 을 따라감, `floor_roots` 에 `special_trial_fNN`(1회 0.26)·`hoard_fNN`(1회 2.4~3.4) 추가. 새 130개가 같은 층 재료 조합 겹침 0 을 지키는지 `--report` 로 확인. |
| A14 **[작음]** | 어깨·등 3D 장식 | 0.3.4.2 에서 런타임 서비스가 빠졌다(ItemsModule 에서 끔, 명령 삭제). | 새 세트는 **장비 텍스처 + 투구만 필수**. `armor_pieces.py` 는 look 만 맞으면 자동 생성되고 `validate.py` 검사만 통과하면 된다(게임에는 안 보임). |

### 1.B 선택의 다양성 — 직업마다 고를 것이 있는가 (주인 바람 1·3)

검사(`rv2_choice.py`): 칭호 없음, 스탯 초기화 뒤, 세금 ≤ 15%(gear_spec 과 같은 규칙), 피해 종류가 직업과 맞음. 사냥꾼은 원거리만 센다 — 매의 눈 +30% 가 끝까지 당긴 화살에만 붙어, 근접 사냥꾼은 방 초당 피해가 활의 58~65% 다(`rv_interval_c2.json`). 가치 = TASK D 의 무기 힘 Q × (1 + 상황 이득), 상황은 무리 · 정예 · 보스 혼자 · 보스 파티. 칸 통과 = 쓸 만함(어느 상황이든 칸 최고의 90% 이상) 3개 이상 · 모든 상황을 이기는 무기 없음 · 보스·대장간이 아닌 강한 것(95% 이상) 1개 이상.

| 띠 | 수호기사 | 광전사 | 사냥꾼 | 비전술사 | 사제 | 그림자 |
|---|---|---|---|---|---|---|
| 1–5 | ✘ 지배 | ✘ 지배 | ✔ | ✔ | ✘ 지배 | ✔ |
| 6–10 | ✔ | ✔ | ✘ | ✘ 지배 | ✘ | ✔ |
| 11–15 | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ |
| 16–20 | ✘ 지배 | ✘ 지배 | ✘ | ✘ 지배 | ✘ 지배 | ✔ |
| 21–25 | ✘ | ✘ 지배 | ✘ | ✘ | ✘ | ✘ 지배 |
| 26–30 | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ |
| 31–35 | ✔ | ✔ | ✘ | ✘ | ✘ | ✔ |
| 36–40 | ✔ | ✔ | ✘ 지배 | ✘ | ✘ | ✘ 지배 |
| 41–45 | ✘ | ✘ | ✘ 지배 | ✔ | ✘ | ✘ 지배 |
| 46–50 | ✘ 지배 | ✘ 지배 | ✘ 지배 | ✘ | ✘ | ✘ |

지금 **20/60**. "지배"(한 무기가 네 상황을 다 이김) 17칸 — 수문 부수개(대장간)·소금물 구슬 지팡이(대장간)·잿불 대검(보스)·풀무 복합궁(대장간)·용수철 연발궁(대장간)·심연 파수검(보스)·종말시계 단두도끼(보스) 들.

까닭은 셋이다.
1. 같은 띠에서 대장간 무기는 영웅·무기 스킬 1~2개, 상자·시련·금고 무기는 희귀·스킬 0개인 띠가 많다(1–20, 31–35). 효과 강도 상한(B 0.28)으로는 못 메운다. D 가 띠 전체로 본 검사는 통과했지만, 직업이 낄 수 있는 무기만 보면 대장간이 남는다.
2. 요구 짝을 고루 퍼뜨린 탓에 직업마다 알맞은 무기가 적다. 사냥꾼은 원거리 2~4개, 비전술사 3~5개, 사제 3~6개, 수호기사·광전사 5~8개(그림자만 13~17개).
3. 사냥꾼은 사실상 활 직업이다. 그런데 띠마다 원거리 무기가 3~5개뿐이고 그중 하나는 지능 활이다.

**B1 [중요] 데이터 고침 23개** (보스·대장간이 아닌 무기만, 모두 0.3.5 새 데이터 안에서 하는 일):

| 고침 | 무기 | 내용 | 돕는 칸 |
|---|---|---|---|
| 요구 짝 (8) | 뿌리 갉는 탄토 · 광부의 등불 향로 · 거미줄 장궁 · 은실 풍경 홀 · 단조 참마도 · 슬래그 날활 · 서리 잔 홀 · 먹물 만곡궁 | 같은 방향 틀(`g2_req.TPL`) 안에서 순서만 바꿈 (예: 단조 참마도 힘/체력, 먹물 만곡궁 지능/체력, 거미줄 장궁 민첩/힘) | 1–5 수호·광전·사제, 6–10 사냥·비전, 21–25 수호, 26–30 사제, 36–40 비전 |
| 무기 스킬 +1 (8) | 광부의 등롱 지팡이 · 포자 향로봉 · 풀무 뼈 활 · 용광로 풍경 홀 · 슬래그 날활 · 묘역 풍경 홀 · 봉인 대형 망치 · 심연 대형 망치 | 희귀면 영웅으로. 스킬은 gear_spec 새 스킬 틀 12종에서 | 6–10 · 11–15 · 21–25 · 26–30 · 36–40 · 46–50 |
| 근접 → 활 (7) | 감독관의 창(정예) · 빛갓 레이피어(상인) · 수문 모닝스타(금고) · 잿불 탄토(금고) · 먹물 플랑베르주(금고) · 톱니 주먹칼(금고) · 공허 탄토(금고) | 새 무기라 아직 없다. **그 자리(같은 띠·같은 획득처·같은 방향)를 새 활로** — 이름·모양(`bone_bow`·`twin_bow`)·간격·한 방 다시. 요구는 민첩/힘(+행운·체력). 띠마다 원거리 ≥ 4 | 사냥꾼 6–10 · 11–15 · 16–20 · 21–25 · 36–40 · 41–45 · 46–50 |

→ **43/60**, 지배 칸 5. 표는 `rv2_choice.json` (전·후 칸, 고침 목록).

**B2 [중요] 무기 8개 더** (또는 같은 띠의 남는 근접 무기 8개를 바꿔 237개 유지 — 권함):

| 띠 | 무엇 | 요구 | 돕는 칸 |
|---|---|---|---|
| 6–10 | 시전 1 (방벽·지원 방향) | 정신/체력 | 사제 |
| 11–15 | 근접 1 (지원·방벽) | 체력/힘 | 수호기사·광전사 |
| 16–20 | 근접 1 · 시전 1 (기습·상태이상) | 체력/힘 · 지능/체력 | 수호·광전·비전 (대장간 지배를 깸) |
| 41–45 | 근접 1 · 시전 1 (상태이상) | 체력/힘 · 정신/체력 | 수호·광전·사제 |
| 46–50 | 시전 2 (마나순환) | 지능/체력 · 정신/체력 | 비전·사제 |

모두 영웅 · 무기 스킬 1개 · 시련방/특별 시련/금고/정예 중 하나. → **55/60** (`rv2_choice_add.json`).
함께: D 의 안대로 **31–35 새 희귀 8개 → 영웅 + 무기 스킬 1개**(31–35 사냥·비전·사제 칸).

**B3 [결정] 남는 2칸.** 사제 36–40(먹물 서고 지팡이, 보스 전설)·그림자 41–45(종말시계 단두도끼, 보스 전설). 보스 전설이 모든 상황에서 이긴다. (가) 그대로 — 보스 전설은 "쫓을 목표"로 남긴다, (나) 두 무기의 고유 효과 강도 0.8 → 0.6. 권함: (가).

**B4 [중요] 새 데이터 테스트 `ClassBandChoiceTest`** — 위 검사를 데이터로. 통과 칸 ≥ 55/60, 지배 칸은 표에 적은 보스 전설만 허용. gear_spec 의 `everyClassHasAKitEveryBand`(알맞은 무기 ≥ 3)는 "고를 수 있는가"를 못 잡는다 — 이 테스트가 대신 잡는다.

**B5 [작음] 겉모습 선택지는 직업마다 둘이다.** 세금 ≤ 15% 로 보면 물리 직업 = 판금(+그림자·사냥꾼 가죽), 마법 직업 = 판금·천. 물리 직업의 천, 마법 직업의 가죽은 세금이 15~25% 다. look_spec 의 결론(엄격히 지는 겉모습은 그것뿐)과 같다.

### 1.C 효과 구현 (코드 자리 · 새 기반 · 폭주 · PvP · 툴팁)

코드 자리는 모두 맞다(줄 번호까지): `DamageService.deal` 은 회피면 훅 없이 돌아간다(174행) → `Hook.evaded` 필요 · 방어 요소 계산 직후(150~163행)가 방어 깎기 자리 · `LabWeaponSkillService.handle` 202행 `impl.cast` · `LabyrinthClassService` 367행 `useMana` · `LabyrinthStatusEffectService` venom 중첩 방식(205·506행) · `CombatListener.onShoot`(85행) · `GimmickRoom.succeed`(189행) · `FloorState.createRoom`(115행) · `Treasures` 의 `tamed[]`.
Paper 26.3 API 도 있다: `PrePlayerAttackEntityEvent`(취소 가능) · `LivingEntity#getActiveItemUsedTime` · `Player#getCurrentInput` · `AbstractArrow#setPierceLevel`. 명세의 "없으면 대신" 경로는 필요 없다.

새로 만드는 기반(모두 지금 구조 안): `AttackClock`/`AttackTiming` · `DamageKind` + `DamageContext` 의 SKILL 기준 · `CombatMath.K` · `Hook.evaded` · 방어 깎기 한 줄 · 출혈 중첩 · `onSkill` 콜백 · `UniqueEffectService` · `PvpMath`/`PvpCc`/`PvpState`/`HealKind` · `ArmorLook`/`ArmorLookService`(구르기·마나 보호막) · `LootTable` PICK · `SpecialTrial`.

| # | 무엇 | 고침 |
|---|---|---|
| C1 **[중요]** | 공격 속도 상한이 민첩 직업에게 꽉 찬다 | Lv45 사냥꾼·그림자는 민첩 134 → +67%, 상한 +60%. 가죽 공속 +6%, 가속(`momentum`) +15%, 장비 공속 줄이 0 이 된다 — 속공 방향 무기가 그 직업에게 쓸모없다. **민첩 몫은 +45% 까지, 합계는 +75% 까지**(간격 하한 0.25초 그대로). 기대값 모델에서 Lv45 공속은 0.60 그대로(민첩 0.45 + 장비·가죽 0.15), 가속·가죽만 15%p 여유가 생긴다. Lv25 이하는 바뀌지 않는다(민첩 76 → +38%). |
| C2 **[작음]** | 빠른 무기의 K 기울기 | 0.45초 근접은 설계 초당 피해가 −9%(K 1.367). 한 대마다 켜지는 효과가 메우는 몫인데, 0.5초 이하 근접 40개 중 25개는 등 찌르기·약점 파고들기 같은 곱하기 효과다. 효과 없이 재면 그림자 10층에서 대검 100% · 단검 85%. 새 배정 때 0.5초 이하 무기에는 한 대 기준·g 보정 효과(rend·flurry·first_strike·counterstep·leech)를 먼저 준다. |
| C3 **[작음]** | 마나 보호막 자리 | look 은 `Hook.absorb` 로 둔다. 그러면 무기 스킬 무적·자동 부활(`DamageInterceptor`)보다 먼저 MP 를 쓴다(무적이어도 MP 가 빠진다). **마지막 `DamageInterceptor` 로** 둔다. |
| C4 **[작음]** | 구르기 회피 × 흘려치기 | 구르는 0.4초 동안 회피가 여러 번 나도 흘려치기는 "전체 2초" 재발동이 막는다(폭주 없음). 지속 피해 틱은 `canEvade=false` 라 구르기로 안 피한다 — 테스트에 넣는다. |
| C5 **[작음]** | 이동 속도 | 상한 −60% ~ +30% 는 장비·겉모습 합에만 걸리고, 추격(+10%)·흘려치기(+15%) 같은 상태 효과는 그 위에 곱한다. 가죽 4부위 + 장화 + 효과면 +40% 안팎까지 간다. 보기에는 괜찮다 — 툴팁 숫자와 실제가 다를 수 있다는 점만 GDD 에 적는다. |
| C6 **[작음]** | 툴팁 줄 | "공격 속도 초당 N회" 한 줄을 더해 237개 다시 세면 넘치는 것 0, 가장 긴 것 공허의 심장 지팡이 20줄(`rv_tooltip.json`). 단 unique_spec 이 말한 접기 순서 바꿈(보스 장비: 스킬 설명 줄이기를 획득처 빼기보다 먼저)이 꼭 들어가야 한다. |

폭주 방지 규칙(고유 효과 피해는 다른 고유 효과를 안 켬, 대상·중첩 상한, 같은 적 기절 6초 면역)은 충분하다. 연쇄 번개 재발동 0.3초 · 축성 0.25초로 줄여도 대상 상한 3명이라 초당 타격 수가 폭주하지 않는다.

### 1.D 겉모습 장단점

- 숫자는 말이 된다. 판금 = 버팀, 가죽 = 빠름·회피, 천 = 스킬·마나. 효과가 부위마다 같은 값이라 읽기 쉽다.
- **D1 [결정] 판금이 그림자의 깊은 층 정답이 된다.** 10층 숙련 솔로: 가죽 53% · 판금 100%. 보통 실력: 0% · 38%. 판금 세트의 HP 줄(같은 레벨 +300~500) 탓이다. 겉모습 손잡이로 시험했다(`rv2_looktune.json`, 판 60번):

| 변형 | 그림자 6층 가죽 (보통 실력·숙련·숙련 어려움) | 그림자 10층 가죽 | 그림자 10층 판금 |
|---|---|---|---|
| look_spec 그대로 | 27·100·5% | 0·53·0% | 38·100·22% |
| 가죽 회피 +2.5%p/부위 | 37·100·18% | 3·55·0% | 32·100·22% |
| 구르기 8초 → 5초 | 37·100·22% | 2·65·0% | 43·100·23% |

  가죽을 올려도 판금을 못 따라간다. 판금 기본 줄은 주인이 고르지 않은 "기본 스탯 손보기"라 그대로 둔다. 권함: 그림자 직업 값 고침(§1.G1)과 **구르기 5초**만. 판금 그림자는 "느리지만 안전한" 길로 남는다. 1~6층에서는 두 겉모습이 다 된다.
- 수호기사·광전사는 판금·가죽 모두 100% 라 겉모습이 피해·버팀의 고름이 된다(가죽 피해 +30~60%).
- 비전술사 천은 마나 보호막 덕에 10층 보통 실력 88% (0.3.4 30%). 손잡이 `absorb` 0.20 → 0.15 는 테스트 서버 뒤에.
- 회피 쌓임: 민첩 0.1%p/점 + 가죽 6%p + 장비 + 연막(+50%)이어도 회피 상한 40% 가 막는다. 구르기만 상한 밖(0.4초 완전 회피)이고 8초(→ 5초)에 한 번이다. 문제없다.

### 1.E 장비 · 획득처

| # | 무엇 | 판정 |
|---|---|---|
| E1 | 영웅 이상 "획득처 종류 하나" | 지킨다. 다만 몬스터·상자(`drop` + `chest` 두 태그, 영웅 21개)를 **한 종류**로 센다는 것을 테스트와 문서에 적는다(0.3.4 의 `gear_fNN_common` 과 같은 뜻). |
| E2 | 새 id | 무기 106 · 방어구 24 · 세트 6 — 지금 items.yml 과 겹침 0, 이름 겹침 0, 새 모양 15개가 기존 30개와 안 겹침(`rv_consist.json`). |
| E3 | 숫자 띠 | 상자·시련·금고·정예 새 무기는 띠 대장간 기준 ±5% (gear §5). combat_spec 공식(TP′ × K × 간격)과 맞다. |
| E4 | 회차 | 대장간 0.4~1.1회 · 몬스터·상자 2.5~3.5 · 시련방·금고·정예 약 5 · 특별 시련 3~7 · 보스 1.4~9. 솔로 보통으로 무리 없다. 대장간이 싼 바닥값인 것은 괜찮다 — 문제는 값이 아니라 B 의 "늘 이긴다"였다. |
| E5 **[작음]** | LootHomesTest | gear §12 의 새 목록에서 지금 있는 `bossCoresForgeOnlyTheirOwnBossGear` · `floorOneBossAlwaysGivesOneUniquePiece` · `starterKitNeverDropsOrCrafts` · `noRarityPoolLeft` 가 빠졌다. 남긴다(층 → tier). |
| E6 **[작음]** | `Content.poolCandidates(floor, …)` | 지금 표에서 안 쓰지만 tier 로 이름을 바꾼다(코덱스 펼침이 부른다). |
| E7 | 특별 시련 | 기믹은 그대로, 조건 넷, 성공 상자 하나 더. 코드 자리 확인. 문구는 "무엇을 하지 마라"뿐이라 공략을 안 흘린다. 30% + 3번 보장 = 방문의 39%. 좋다. |
| E8 **[작음]** | 무기 스탯 줄 | 기존 활·단검 43개의 민첩 줄, 정신 줄이 있는 무기 22개는 줄 이름을 안 바꾼다(gear `stats_rename` 0). 이제 민첩 줄은 공속·치명이고 피해는 c(L) 로 메웠다. combat_spec §10.2 의 "줄 이름 바뀐 무기" 문장은 방어구 세트에만 해당한다고 고친다. |

### 1.F PvP

pvp_spec 을 숫자로 다시 확인했다(`rv2_pvpshadow.py`, 같은 빌드·같은 설정, 판 24번).
- 한 방 상한 없음(`max_hit_ratio` 1.0) ✔ · 상태이상은 바꾸지 않고 짧게(빙결 4 → 1.5초, 기절 1 → 0.8초, 같은 분류 50% → 25% → 면역, 끝나면 2초 면역) ✔.
- 유리 대포의 한 바퀴가 유리를 쓰러뜨림(치명 기대 112·109·124%) ✔ · 수비는 43·54·56% 남음 ✔(Lv35·50 은 목표 30~50% 위쪽 끝을 조금 넘음 — 규칙 "한 바퀴로 수비는 안 쓰러짐"은 지킴).

| # | 무엇 | 고침 |
|---|---|---|
| F1 **[중요]** | 직업 승률이 레벨마다 출렁인다 | 평균만 보면 36~61% 지만 레벨별로 25~80% 다. 수호기사 Lv20 67% → Lv35 26% → Lv50 74%, 사냥꾼 Lv35 80%, 비전술사 Lv35·50 26·29%. 직업 보정 한 줄로는 못 맞춘다(그 레벨의 장비 표본 탓일 수 있음). 출시 조건은 "한 바퀴·남는 HP·묶인 시간" 셋으로 두고, 직업 보정은 테스트 서버에서 레벨대별로(20·35·50) 따로 둘 수 있게 `class_damage` 를 `{class: {low, mid, high}}` 도 받게 한다. |
| F2 **[작음]** | Lv5·10 은 체력 쪽이 이긴다 | 유리가 수비를 이기는 비율 10·29%. 스킬이 적은 때라 받아들일 만하다. 강인함 `per_level` 을 Lv15 아래에서 12 로(수비 강인함 ↓) 두는 손잡이를 남긴다. |
| F3 **[작음]** | 표 다시 만들기 | §9.5 고유 효과 상태이상 표(D 의 새 N번째·기절 시간), §6 `pvp_mult`(P3 뒤 바뀐·새 무기 스킬 — B1 의 +8, B2 의 +8). `pv_sim.skill_mults` 를 P3 데이터로 다시 돌리고 `PvpSkillMultDataTest` 가 어긋남을 잡는다. |
| F4 | 그림자 PvE 고침(§1.G1)의 PvP 영향 | 그림자 평균 승률 Lv20·35·50: 37·36·49% → 45·40·54%. 가운데로 온다. 직업 보정 1.2 는 그대로(1.1 로 내리면 34·29·46% 로 다시 처진다). |
| F5 **[작음]** | 구르기·마나 보호막 | PvP 에서 그대로 든다(pv_duel 이 넣고 잼). 구르기 5초로 바꾸면(§1.D) 1:1 을 한 번 다시 돌린다. |

### 1.G 전투 · 난이도 — 시뮬레이터를 다시 돌림

설계자와 다른 시드로 다시 돌렸다(`rv_sim.py`, 판 40번 · 파티 20번): 직업 6 솔로 × 보통(초보·보통 실력·숙련)·어려움·악몽(보통 실력·숙련) × 1·5·10층, 3인 파티 A(수호·사냥·사제)·B(광전·비전·그림자), 0.3.4 와 새 모델. 그리고 의심 가는 곳만 판을 늘렸다.

**솔로 클리어율, 직업 평균 [수호 광전 사냥 비전 사제 그림자]**

| 난이도·실력 | 층 | 0.3.4 | 새 모델 |
|---|---|---|---|
| 보통·보통 실력 | 1 | 92% [100 100 98 92 100 62] | 97% [100 100 100 92 100 90] |
| 보통·보통 실력 | 5 | 91% [100 100 100 78 100 70] | 93% [100 100 100 85 100 72] |
| 보통·보통 실력 | 10 | 56% [85 100 50 0 100 0] | 59% [92 100 62 0 100 0] |
| 보통·숙련 | 10 | 83% [100 100 100 55 100 42] | 79% [100 100 100 60 100 **12**] |
| 어려움·숙련 (새 = HP 1.45) | 1 | 92% | 96% |
| 악몽·숙련 | 1 | 50% [50 57 92 0 100 0] | 51% [45 60 100 2 100 0] |
| 악몽·숙련 | 10 | 20% | 18% |

- 목표는 지켜진다: 악몽 1층 숙련 약 50%, 보통 1층 보통 실력 ≥ 90%, 어려움 HP 1.45 가 0.3.4 자리로 되돌린다.
- **G1 [중요] 그림자 회귀.** 판 300번(시드 셋)으로 다시: 10층 숙련 50% → **22%**, 5층 보통 실력 69% → 54% (`rv2_shadow10.json`, `rv2_shadowtune.json`). combat_spec 의 기대값(DPS −1~−5%, EHP −6~−7%)은 ±10% 안이지만 클리어율은 문턱을 넘어 반으로 준다.
  **고침: 그림자 `skill_scale` 0.62 → 0.70, 급소 찌르기 치명 피해 +0.40 → +0.50.** → 5층 보통 실력 74%, 10층 숙련 44%. 기대값 DPS Lv10 +1% · Lv25 0% · Lv45 +4% (±10% 안). PvP 는 §1.F F4.
- **G2 [작음] 시뮬레이터의 파티 모델이 틀렸다.** `ce_sim.party_floor` 는 파티원마다 몹 1/3 을 3인 배율(HP ×2.2) 그대로 혼자 상대하게 한다. 그래서 파티 B 가 보통 1층 5% (솔로는 97%). 같이 치는 근사(`rv_party.py`, 판 30번)로 다시 돌렸다:

| 파티 | 보통·보통 실력 1 · 5 · 10층 (0.3.4 → 새) | 보통·숙련 | 악몽·숙련 |
|---|---|---|---|
| A 수호·사냥·사제 | 100 · 100 · 100% → 같음 | 100% 모두 | 100 · 100 · 100% → 100 · 100 · 93% |
| B 광전·비전·그림자 | 67 · 100 · 7% → 83 · 100 · 20% | 100% 모두 | 0 · 43 · 0% → 0 · 30 · 0% |

  전후 차이가 없다 — 이번 바꿈 탓이 아니다. 다만 파티 A 10층 보스가 16분(0.3.4 17분, 목표 2~6분)이다. 시뮬레이터 보스 HP 파티 배율(1 + 0.6 × 2)과 낮은 DPS 조합 탓으로 보인다. 테스트 서버에서 한 번 잰다. combat_spec §9.3 표는 이 근사로 바꾼다.
- **G3 [작음] 보통 10층 보통 실력의 비전술사·그림자 0%** 는 0.3.4 와 같다(겉모습 넣으면 비전술사 88%, 그림자 판금 38%). "솔로 보통이 편함" 규칙의 남은 구멍으로 적어 둔다.
- **G4 간격 지배 없음.** 같은 단계 무기를 직업마다 바꿔 들려 봤다(`rv_interval_c2.json`, 효과 없음). 수호기사 87~100% · 광전사 80~100% · 비전·사제 82~100% · 그림자 83~100%(10층 대검 100 · 단검 85 · 활 83). 어느 간격도 모든 직업에서 이기지 않는다. 활은 사냥꾼에게만 크게 이긴다(§1.B).
- 고유 효과는 이 시뮬레이터에 없다. D 가 비보스 무기 효과를 1판보다 세게(희귀 평균 s 1.91 → 2.57) 했으니, P1 뒤 테스트 서버 보통·솔로 1·5·10층을 한 번 잰다.

### 1.H 그림 자원

| 무엇 | 수 | 메모 |
|---|---|---|
| 새 무기 모델 | 106 (+ B2 8) | 74개가 새 실루엣 15종, 32개가 기존 모양 새 색 |
| 활 당김 모델 | (14 + B1 활 7) × 3 = 63 | 새 활 모양 `bone_bow`·`twin_bow` 는 `VW.bow(kind)` 휨 표에 더함 |
| 새 voxel 함수 | 13 (+ 활 2종) | gear §9.3 이 부품·색 역할·손 위치까지 적었다. 하나 40~80줄 |
| 방어구 | 24 부위 · 6세트 | 장비 텍스처 = `equipment.paint_set(look)` + style, 투구 = 기존 투구 모양 5종 재사용, 어깨·등 = 자동(§1.A14) |

- **H1 [작음] 손 잡는 목록이 두 곳이다.** `src/voxel/weapons.py` 의 `BOWS`·`TWO_HANDED`·`HOLD` 와 `tools/hold_preview.py` 의 `BOWS`(764행 복사본)·`HEAD_SHAPES`. 둘 다 고친다. gear 가 말한 `shapes_weapons.py` `TWO_HANDED`(2D 아이콘 경로)는 새 모양이 모두 voxel 이라 고칠 필요 없다.
- **H2 [작음]** 테마 키(`THEME_KEYS`)는 새 id 가 모두 품는다. B1 의 활 7개를 새로 이름 지을 때도 같은 키(sluice·ember·ink·clock·void…)를 넣는다.
- 절차 생성 팩이라 양은 감당된다. 손이 가는 일은 13개 함수와 `hold_preview` 시트 확인이다.

## 2. 직업별 빌드 선택지 (§1.B 고침 23개 뒤)

칸 = 쓸 만한 무기(어느 상황이든 90% 이상): 고유 효과 · 입을 수 있는 겉모습(세금 ≤ 15%) · 획득처 · 95% 이상인 상황. `*` = §1.B1 에서 고친 무기. 전체 목록은 `rv2_options.json`.

### 2.1 Lv15–25 (띠 16–20 · 21–25)

| 직업 | 띠 | 선택지 | 판정 |
|---|---|---|---|
| 수호기사 | 16–20 | 수문 부수개(가시 반격·판금/가죽·대장간·모든 상황) · 오스릭의 익사 닻도끼(갑옷 부수기·보스·보스 파티) · 수문 모닝스타*(포식·금고) | ✘ 대장간 지배 → B2 판금 근접 1 |
| 수호기사 | 21–25 | 단조 참마도*(휩쓸기·판금·**정예**·무리) · 여명을 맹세한 검(축성·보스·정예/보스) · 잿불 대검(포식·보스) | ✔ |
| 광전사 | 16–20 | 수호기사와 같음 | ✘ → B2 |
| 광전사 | 21–25 | 단조 참마도*(휩쓸기·**정예**·무리) · 잿불 대검(보스) · 모루 서약 넓은검(굳건함·대장간) | ✔ |
| 사냥꾼 | 16–20 | 장어 쌍현 활(관통 사격·판금/가죽·**특별 시련**·무리·보스 파티) · 조수 부르는 활(원소 부여·보스) · 금고 새 활* | ✔ |
| 사냥꾼 | 21–25 | 풀무 복합궁(연타·대장간) · 금고 새 활*(등 찌르기·보스 파티) · 풀무 뼈 활*(피 냄새·**특별 시련**) | ✔ |
| 비전술사 | 16–20 | 소금물 구슬 지팡이(과부하·판금/천·대장간·모든 상황) · 조수종 향로(마력 흡수·대장간) | ✘ 대장간 지배 → B2 시전 1 |
| 비전술사 | 21–25 | 도가니 성배(약점 파고들기·천·**몬스터·상자**·정예/보스) · 슬래그 날활*(과부하·**몬스터·상자**·모든 상황) · 불씨노래 홀(과부하·대장간) | ✔ |
| 사제 | 16–20 | 비전술사와 같음 | ✘ → B2 |
| 사제 | 21–25 | 슬래그 날활*(과부하·**몬스터·상자**) · 불씨노래 홀(대장간) · 용광로 풍경 홀*(수호 기운·**금고**·파티) | ✔ |
| 그림자 | 16–20 | 익사한 닻날(광기·대장간) · 장어 쌍현 활(**특별 시련**) · 수문 부수개(대장간) · 조수 부르는 활(보스) · 수문 모닝스타*(금고) 외 | ✔ |
| 그림자 | 21–25 | 단조 참마도*(휩쓸기·**정예**·무리) · 잿불 대검(보스) · 잿불 탄토*(등 찌르기·금고) · 풀무 복합궁 · 모루 서약 넓은검 | ✔ |

### 2.2 Lv35–45 (띠 36–40 · 41–45)

| 직업 | 띠 | 선택지 | 판정 |
|---|---|---|---|
| 수호기사 | 36–40 | 색인 창(가시 반격·판금·**정예**·무리/정예) · 봉인 대형 망치*(갑옷 부수기·**몬스터·상자**·보스) · 먹물 모닝스타(굳건함·**시련방**) | ✔ |
| 수호기사 | 41–45 | 놋쇠 넓은검(방패 강타·**금고**·모든 상황) · 톱니 대검(갑옷 부수기·**특별 시련**·보스 파티) | ✘ 2개 → B2 판금 근접 1 |
| 광전사 | 36–40 | 수호기사와 같음 | ✔ |
| 광전사 | 41–45 | 수호기사와 같음 | ✘ → B2 |
| 사냥꾼 | 36–40 | 금고 새 활*(포식·모든 상황) · 먹물 뼈 활(생명 흡수·**특별 시련**·정예/보스) · 깃펜 각궁(찢는 치명·대장간·정예/보스) | ✔ |
| 사냥꾼 | 41–45 | 용수철 연발궁(연타·대장간) · 금고 새 활*(등 찌르기·보스 파티) · 태엽 날활(선제·**몬스터·상자**) | ✔ |
| 비전술사 | 36–40 | 먹물 만곡궁*(연쇄 번개·**몬스터·상자**·무리) · 먹물 소용돌이 지팡이(약점 파고들기·대장간) · 먹물 서고 지팡이(시체 폭발·보스) | ✔ |
| 비전술사 | 41–45 | 태엽 천구 지팡이(과부하·대장간) · 전격 코일 지팡이(연쇄 번개·보스) · 놋쇠 가지 지팡이(약점 파고들기·**금고**·정예/보스) | ✔ |
| 사제 | 36–40 | 먹물 서고 지팡이(보스, 모든 상황)뿐 | ✘ → B3 결정 |
| 사제 | 41–45 | 태엽 천구 지팡이(대장간) · 전격 코일 지팡이(보스) | ✘ → B2 시전 1 |
| 그림자 | 36–40 | 봉인 대형 망치*(**몬스터·상자**·보스 파티) · 색인 수호자의 넓은검(보스) · 야음 단검(보스·무리) · 먹물 스틸레토(등 찌르기·**금고**·보스 파티) · 색인 창(**정예**) | ✔ |
| 그림자 | 41–45 | 종말시계 단두도끼(보스, 모든 상황) · 놋쇠 넓은검(**금고**·무리/정예) · 조율기 대검(대장간) · 톱니 대검(**특별 시련**) 외 | ✘ 보스 지배 → B3 결정 |

읽는 법: 고침 뒤에도 "대장간이나 보스가 아닌 강한 무기"가 띠마다 있다(굵게). 겉모습은 물리 직업 판금(+그림자·사냥꾼 가죽), 마법 직업 판금·천 두 갈래다.

## 3. 무기 종류 없애기 — 따로 묶은 일 (P0b)

| 자리 | 지금 | 바꿈 |
|---|---|---|
| `content/WeaponTypes` | 종류 이름·피해 배율·직업 스킬 환산·추천 재사용 −10%·시작 무기 고르기 | **삭제.** `effective()`(요구 못 채우면 맨손)는 `EquipRules` 로 옮김. 시작 무기 = classes.yml `starter_weapon` |
| `classes.yml` | `weapon_types` | 삭제. `skill_scale`(수호 1.00 · 광전 1.55 · 사냥 1.55 · 비전 1.05 · 사제 0.90 · 그림자 **0.70**), 모든 스킬 재사용 ×0.9, 매의 눈 0.30, 급소 찌르기 치명 피해 **0.50**, 은총 마법 피해 0.10, 설명 글에서 종류 이름 빼기 |
| 직업 스킬 피해 | `SkillContext.weaponScale()` = 추천 무기 배율 ÷ 든 무기 배율 | **스킬 위력 SP** = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격) × (시전 1.05) × (1 + 0.5 × 공속). K = 근접 1.47 − 0.143 × max(0, 1/간격 − 1.5) · 원거리 1.413 · 시전 1.22. 같은 띠에서 한 방은 3~3.7배 벌어지지만 SP 는 1.2~1.6배 — 무거운 무기가 스킬을 독차지하지 않는다 |
| 무기 스킬 피해 | 공격력 × 배율 | SP × 새 배율 (옛 배율 × weapon_skill_factor, combat_spec JSON) |
| 직업 메뉴 · ClassesModule 안내 | "추천 무기 활 (재사용 −10%)" | 삭제. 대신 "주로 쓰는 능력치" 한 줄 |
| 툴팁 · 도감 · 대장간 | "영웅 대검 · 지하 4층", 분류 거르개 | "영웅 무기", 거르개 = 방식(근접·원거리·시전)·피해 종류·"지금 낄 수 있는 것" — 분류 이름 없음 |
| `ContentValidator` · `GearRequirementsDataTest` | 종류 → 요구 능력치 규칙 | 무기마다 `requires` 자유(2~3 능력치, AND). 규칙은 합·나눔·"물리 무기는 STR 또는 DEX, 마법 무기는 INT 또는 WIS 하나 이상" |
| `items.yml` | `weapon_type` | `attack: {style, interval, kind}` (P0b 가 131개에 넣음) |
| `config.yml` | `weapon_attack_speed` 종류표 | `none`(맨손) 만 읽음 |

## 4. 툴팁 줄 계획 (무기)

```
영웅 무기 · ✦ 아우라                           ← 분류·층 없음
요구 민첩 32 · 힘 21 · 행운 13                    ← AND, 큰 순, 능력치마다 충족 초록/미달 빨강
⚔ 공격력 23 (21–24) · 물리                       ← 한 방 피해(강화 보너스 표시는 지금처럼), 시전·지능 무기는 '· 마법'
공격 속도 초당 1.5회                              ← 1 ÷ attack.interval, 소수 한 자리, 민첩 넣기 전
(부가 스탯 줄)
✧ 고유 {이름} (재발동 N초)                        ← unique_spec §6, 2줄 (넘치면 1줄로 접기)
  {설명 34자 이하}
(무기 스킬 · 이야기 · 획득처: 보스 테오라 / 몬스터·상자 / 시련방 / 특별 시련 / 금고·미믹 / 정예 / 대장간)
```

- 활: 공격력 = 끝까지 당긴 한 발, 초당 = 1 ÷ 한 발 주기(당김 + 0.15초).
- 떠오르는 피해 숫자 = 방어까지 깎인 최종 피해(지금과 같음), 마법은 하늘색, 0.5초 묶어 띄움.
- 민첩이 간격을 줄이는 식: 간격 = max(0.25, interval ÷ (1 + 공속)), **공속 = min(0.45, 0.005 × 민첩) + 장비·겉모습·버프, 합계 ≤ +75%** (§1.C1). /스탯 에는 지금 실제 초당 횟수.
- 강화는 W(한 방)를 키운다 → 공격력·스킬 위력이 같이 오른다. 고유 효과 수치는 강화로 안 바뀐다.

## 5. 합친 구현 계획

### 5.1 순서와 의존

```
P0 전투 모델·스탯 역할·난이도 ──► P0b 무기 종류 없애기 ──► P0c PvP ──► P1 고유 효과 ──► P2 겉모습
                                                                              │
                                     P3 데이터(요구·층 없는 루팅·새 장비) ◄────────┘ (P2 뒤)
                                         ├──► P4 특별 시련
                                         └──► P5 팩 (모양 함수는 P0 부터 따로 만들 수 있음, 합치기는 P3 뒤)
                                                    └──► P6 툴팁·도감·문서 (마지막, 한 번에)
```

**같은 파일을 여러 묶음이 고칠 때 순서** (앞 묶음이 합쳐진 뒤 다음 묶음이 시작):
- `combat/DamageService` P0 → P0c → P1 → P2
- `classes/LabyrinthStatusEffectService` P0c → P1 → P2
- `stats/StatCalculator`·`DerivedStats` P0 → P2
- `classes/LabyrinthClassService` · `items/weaponskills/LabWeaponSkillService` P0b → P1 → P2
- `combat/CombatListener` P0 → P1
- `content/ContentParser`·`core/ContentValidator` P0b → P0c → P1 → P2 → P3
- `items/ItemTooltip`·`ui/menus/CodexMenu`·대장간 목록 **P6 만** (앞 묶음은 데이터 접근자만 더하고 줄은 안 건드림. 툴팁 테스트 고침도 P6)
- `content/items.yml` P0b(attack 블록·피해 범위·무기 스킬 배율) → P0c(pvp_mult) → P3(나머지 전부, 생성기로 한 번에)
- `content/classes.yml` P0b → P0c · `config.yml` P0 → P0c → P2 → P4

### 5.2 묶음

**P0 — 전투 모델 · 스탯 역할 · 난이도** (combat_spec §2·§3·§7.2·§8.2·§9·§10 + 이 검토 C1)
- 파일: `stats/StatCalculator`(primaryMix 삭제, STR/INT 1%/점, 민첩 공속 0.5%·몫 상한 0.45·합 0.75, 치명 0.25%p, 회피 0.1%p) · `stats/DerivedStats`(physicalPower·magicPower·power(kind)·weaponDamage·skillPower·attackInterval) · `stats/StatService.applyAttributes`(ATTACK_SPEED 1024) · `combat/AttackClock`·`AttackTiming`(새) · `combat/CombatListener`(onPreAttack 취소·기억 클릭 1틱 넣기·meleeMult = 점프 치명만·활 서버 당김 세기·×1.25 삭제) · `combat/DamageKind`(새) · `DamageContext`(kind, PER_HIT|SKILL) · `combat/CombatMath`(K) · `DamageService`(원피해 = 기준 × power(kind), `applyVanilla` 뒤 `setNoDamageTicks(0)`, 숫자 묶음·마법 색) · `core/Settings`(combat 키)·`core/Difficulty`(legacy034 → 어려움 HP 1.45) · `stats/LevelService.ensureRoleReset`(`stats.role_reset_035`) · `items/GearItemService.baseRolls`(굴림 위치 옮기기, `ITEM_COMBAT_VER` 35) · `ui/menus/StatsMenu`(스탯 글·요약 칸) · `config.yml`.
- 테스트: AttackTimingTest · StatCalculatorTest(공속 몫 상한 포함) · CombatMathTest · ItemRollsTest · RequirementResetTest · ScalingTest/BossScalingTest · DamageFormulaTest.
- 끝 조건: 게이지가 안 보이고, 마구 눌러도 무기 간격마다 한 번 온전히 맞는다. 접속 안내 한 줄 + 무료 초기화 1회.

**P0b — 무기 종류 없애기** (§3)
- 파일: `content/WeaponTypes` 삭제 · `items/EquipRules` · `classes/skills/SkillContext`(weaponScale → skill_scale × SP) · `items/weaponskills/*`(SkillCast.hit·MechanicsEngine → `DamageContext.skill(…, kind)`) · `classes/LabyrinthClassService`(추천 −10% 삭제, 시작 무기) · `classes/ClassesModule` · `ui/menus/ClassMenu` · `content/ItemDef`·`ContentParser`(attack 읽기, `weapon_type` 있으면 경고) · `core/ContentValidator` · `classes.yml` · `items.yml`(131개: weapon_type → attack, stats.damage 새 범위, 무기 스킬 피해 × weapon_skill_factor — combat_spec JSON 에서 생성).
- 테스트: WeaponTypeGoneTest · WeaponIntervalDataTest · SkillKindTagsTest · WeaponFreedomTest(어떤 무기든 직업 스킬 = SP × skill_scale) · EarlySoloDataTest.
- 끝 조건: `WeaponTypes` 사용처 0, 화면 어디에도 "대검/한손검/활/지팡이/홀/단검" 없음.

**P0c — PvP** (pvp_spec 전부 + F1·F3)
- 파일: `pvp/PvpConfig`(옮기기: 0.35 → 1.0, 0.7 → 1.0, 고친 값 ÷ 0.7; `class_damage` 레벨대 받기) · `pvp/PvpMath`·`PvpCc`(새) · `pvp/PvpModule`(before·absorb·전투 중) · `pvp/PvpListener` · `TargetFilter`+`PvpState` · `DamageContext`(defenseScale·critDamageScale) · `DamageService.heal(…, HealKind)` + 부르는 곳(SkillContext·SkillCast·MechanicsEngine·AreaSkills·ConsumableListener·StatService 재생) · `LabyrinthStatusEffectService.apply`·`addShield` · `ContentParser`(pvp_mult) · classes.yml·items.yml(pvp_mult 38개) · `ui/menus/MainMenu`·`StatsMenu` 글 · `config.yml` pvp 블록.
- 테스트: PvpConfigTest · PvpMathTest · PvpCcTest · PvpDamageHookTest · PvpHealTest · PvpSkillMultDataTest · PvpRulesTest.
- 끝 조건: 상한 없음, 같은 분류 상태이상 50% → 25% → 면역, 기절 뒤 2초 면역.

**P1 — 고유 효과 엔진** (unique_spec §7 + §9, A6·A11·A12·C2·C4)
- 파일: `content/ItemDef`(UniqueDef)·`ContentParser`·`ContentValidator`(닫힌 목록 26, 무기만, 원거리·시전 전용 효과 검사는 style 로) · `items/unique/UniqueEffectService`(새, Hook + Listener) + 순수 `UniqueProcs` · `DamageService`(Hook.evaded, 방어 깎기 한 줄) · `LabyrinthStatusEffectService`(출혈 중첩, 서리 5중첩 → 빙결 1초, 보스는 취약) · `LabWeaponSkillService.handle`·`LabyrinthClassService`(onSkill) · `CombatListener.onShoot`(관통) · `items/EquipmentListener`(손 무기 unique 캐시).
- 데이터: items.yml 의 `unique` 는 P3 생성기가 `unique_assign_all.json` 에서 넣는다(P1 은 기존 131개를 그 파일로 시험 데이터 삼아 테스트).
- 테스트: UniqueEffectCatalogTest · UniqueProcTest(N번째·첫 타 창·재발동·중첩 상한·PvP 3중첩·구르기 중 지속 피해 안 피함) · UniqueDiversityTest(같은 띠·같은 방식).

**P2 — 겉모습 장단점** (look_spec + A2·A5·C3·D1)
- 파일: `content/ArmorLook`(새) · `ItemDef.look`·`ItemSetDef.lookEffects` · `ContentParser`·`ContentValidator`(앞 능력치 = 겉모습, 합 = T(L)) · `core/Settings.ArmorLooks` · `items/EquipmentListener.contribute` · `StatCalculator`(겉모습 합) · `DerivedStats`(fullLook·cooldownMult·ccResist) · `StatService`(MOVEMENT_SPEED·KNOCKBACK, disable 때 되돌림) · `DamageService`(구르기 회피·밀려남 저항) · `LabyrinthStatusEffectService`(cc_resist) · `mobs/MobSkills.push` · `LabyrinthClassService`·`LabWeaponSkillService`(cooldownMult) · `items/ArmorLookService`(새: 구르기 **5초**, 마나 보호막 = **마지막 DamageInterceptor**) · `GearItemService.applyEquippable`(소리) · `data/PlayerData`(look.tumble_off) · `StatsMenu`(요약·구르기 단추) · `config.yml` armor_looks.
- 테스트: ArmorLookTest · ManaShieldTest · TumbleInputTest · CrowdControlTest · ArmorLookDataTest · ArmorRequirementsDataTest.

**P3 — 데이터: 요구 능력치 다시 쓰기 · 층 없는 루팅 · 새 장비** (gear_spec + A1~A8·A13·B1·B2·E1·E5·E6)
- 생성기 하나(`labyrinth/tools/gen_035_content.py`, 새): 입력 = 이 폴더의 JSON(넣을 때 저장소 `tools/data/035/` 로 복사) → items.yml · loot.yml · recipes.yml · npcs.yml · dungeon.yml 블록. 손으로 고치지 않는다.
  - items.yml: 356개 요구(무기 = gear_spec + B1 요구 짝 8, 방어구 = look_spec 표 + A2 고침 3), `requires_any` 삭제, `floor` → `tier`, `classes` 삭제, `sources` 에 trial·special·hoard, 새 무기 106(+ B1 활 7 은 새 이름·모양, B2 8), 방어구 24 + 세트 6, 스탯 줄 이름 바꿈 10세트(+A2 3세트), `unique` = unique_assign_all, B1·B2 의 무기 스킬 16개, 31–35 승격 8.
  - loot.yml: 206표(band_tNN_* · mix_fNN_drop · special_trial_fNN · hoard_fNN · 다시 씀), `own_build_bias`.
  - recipes.yml: 무기 레시피 골드 ×1.5, 방어구 12개 새로.
  - enhance.yml: `tools/gen_enhance.py` 0.3.5 판(A13)으로 다시 생성.
- 코드: `content/StatRequirement`(any 삭제) · `ContentParser`(requires_any → 문제, pick, tier, floor 별칭 경고) · `ContentValidator`(요구 규칙, pick 순환) · `content/LootTable`(PICK) · `items/loot/LootRoller`(PICK, own_build_bias) · `content/Content.poolCandidates`(tier) · `dungeon/treasure/Treasures.open`(금고 안 상자·길들인 미믹 → `hoard_fNN`).
- 테스트: GearRequirementsDataTest(다시 씀: AND·합·나눔·영웅 이상 획득처 종류 하나 — 몬스터·상자 = 한 종류) · ArmorRequirementsDataTest · LootHomesTest(다시 씀 + E5 의 넷 남김) · PickEntryTest · DropRateWindowTest · BandDiversityTest · SidegradeBandTest · **ClassBandChoiceTest(B4)** · TierMigrationTest · StatRequirementTest · `gen_enhance.py --check`.
- 끝 조건: 직업 × 띠 고를 수 있는 칸 ≥ 55/60, 어느 직업도 한 띠를 통째로 못 입는 일 없음(rv_lookfix 규칙), 영웅 이상 획득처 종류 하나.

**P4 — 특별 시련** (gear_spec §6)
- 파일: `dungeon/rooms/SpecialTrial`(새, 순수) · `dungeon/DungeonConfig`·`dungeon.yml` · `content/FloorDef`·`ContentParser`(floors.yml 덮어쓰기) · `dungeon/FloorState.createRoom` · `dungeon/rooms/GimmickRoom`(조건·보스바·성공 상자·경험치 ×1.5) · `gimmicks/LeverSequence·ResonanceTune·BookCipher·GearTiming`(noteMistake 한 줄) · 몹→플레이어 피해 경로(onPlayerHurt) · `items/ConsumableListener.onConsume` · `data/PlayerData`(층별 special_miss) · `dungeon/SelfTest`.
- 테스트: SpecialTrialTest. 끝 조건: 자가 진단이 층마다 조건 4종 판정·special_trial_fNN 지급을 확인.

**P5 — 팩** (gear_spec §9·§10 + H1·H2)
- 파일: `resourcepack/src/voxel/weapons.py`(13 함수, `BOWS` +2 · `bow()` 휨 표, `TWO_HANDED` +4, `HOLD` 사브르 fp_yaw 100) · `resourcepack/tools/hold_preview.py`(`BOWS` 복사본·`HEAD_SHAPES` +5) · `resourcepack/src/validate.py`(새 모양 목록 검사) · `equipment.py`·`voxel/armor.py`(새 6세트는 look·style·테마만 맞으면 자동).
- 확인: `python tools/hold_preview.py --shapes <새 15종>` 시트·metrics 를 같은 무게 기존 모양과(1인칭 덮는 비율 ±25%), `check_assets.py`, `validate.py`.
- 모양 함수는 P0 와 함께 시작해도 된다(입력 = gear_spec.json). 팩에 넣는 것은 P3 뒤.

**P6 — 툴팁 · 도감 · 대장간 · 문서** (§4 + A10 + gear §4.5 + look §6 + unique §6)
- 파일: `items/ItemTooltip`(첫 줄, 요구 줄, 공격력·공격 속도, 고유 2줄·접기 순서, 겉모습 줄, 획득처 줄 층 없음) · `ui/menus/CodexMenu`(정렬 tier, 공용 묶음 삭제, SOURCE_GROUPS 시련방·특별 시련·금고·미믹, 방어구 겉모습 거르개, 자세히 보기 스킬 위력) · 대장간 목록 · GDD.md(§3 스탯 · §4 스킬 위력 · §11 장비 · §11.7 상한 · §15.4 피해 종류 · §16.4 · §18 PvP) · ARCHITECTURE.md · README 0.3.5 바뀐 것.
- 테스트: TooltipFitTest(고침: 층 글자·"또는" 없음, 공격 속도 줄 포함 20줄·330px, 보스 획득처 유지) · CodexSourceTextTest.

### 5.3 옮기기 (0.3.4 → 0.3.5) 한 곳에 모음

| 무엇 | 언제 | 어떻게 |
|---|---|---|
| 스탯 무료 초기화 1회 | P0 | `stats.role_reset_035`, 0.3.4 `grantRequirementReset` 와 같은 모양 |
| 가진 무기 피해 굴림 | P0 | 같은 위치 t 로 새 범위에, `ITEM_COMBAT_VER` 35 |
| 방어구 스탯 줄 이름 (look_spec 10세트 + A2 3세트) | P2 | 같은 깃발 35, 값·강화·시드 그대로 |
| 바뀐 요구 능력치 | P3 | 낀 장비는 안 벗김(효과만 꺼짐), 접속 안내 한 줄에 "장비 요구가 바뀜" |
| config | P0·P0c·P2 | 안 고친 값만 새 기본값(어려움 HP 1.45, pvp 0.35 → 1.0, 0.7 → 1.0) |
| items.yml `floor` | P3 | 파서가 tier 로 읽고 경고 (옮기는 동안) |

## 6. 주인이 정할 것

1. **B3** 보스 전설 2개(먹물 서고 지팡이·종말시계 단두도끼)가 그 띠에서 늘 이기는 것 — (가) 쫓는 목표로 둔다(권함) / (나) 효과 강도 0.6.
2. **B2** 무기 8개 — 새로 넣어 245개 / 같은 띠 남는 근접 무기를 바꿔 237개 유지(권함).
3. **D1** 깊은 층 그림자는 판금이 안전한 답이다. 판금 기본 줄은 그대로 둔다(권함). 바꾸려면 "방어구 기본 스탯 손보기"를 새로 골라야 한다.
4. **C1** 공격 속도 상한 문장이 바뀐다: "공격 속도 합계 +75%, 그중 민첩 몫 +45% 까지".

## 7. 검토에 쓴 도구 (`design2/tools/`)

| 도구 | 한 일 |
|---|---|
| `rv_consist.py` | 명세끼리·데이터와 어긋남(id·unique·간격·한 방·요구·예산·획득처 태그·모양) |
| `rv_reqmerge.py` · `rv_lookfix.py` | 방어구 요구 두 표 비교, 고침 3개 |
| `rv2_kindfix.py` | 지능 활 8개 피해 종류 고쳐 다시 셈 |
| `rv_builds.py` · `rv2_choice.py` · `rv2_choice_add.py` · `rv2_options.py` | 직업 × 띠 선택지, 최소 고침, 무기 추가, §2 표 |
| `rv_sim.py` · `rv2_shadow10.py` · `rv2_shadowtune.py` | 솔로·파티 시뮬레이션 다시, 그림자 회귀와 고침 |
| `rv_party.py` | 같이 치는 파티 근사 |
| `rv_interval.py` | 직업 × 간격 지배 |
| `rv_looksim.py` · `rv2_looktune.py` | 겉모습 시뮬레이션(요구 표 바꿔), 가죽 손잡이 |
| `rv2_pvpshadow.py` | PvP 레벨별 직업 승률, 그림자 고침 영향 |
| `rv_tooltip.py` | 공격 속도 줄 넣은 툴팁 줄 수 |
