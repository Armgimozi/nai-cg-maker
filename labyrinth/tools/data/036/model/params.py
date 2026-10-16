"""0.3.6 계약 — 설계 숫자의 한 곳 (Q0).

이 파일만 고치고 다음을 돌린다 (labyrinth/ 에서):
    python3 -B tools/data/036/model/run_all.py          # 청사진 시안 → 콘텐츠 시제품 → 경제 표 → 계약 JSON
    python3 -B tools/data/036/check_contract.py          # 계약 검사

주인 결정(최종, 명세·검토보다 앞섬)은 OWNER 에 그대로 적고 check_contract.py 가 지켜본다.
게임 글(이름·설명)에는 'Lv'·층 번호·단계 같은 표지를 쓰지 않는다 (주인 결정 4).
"""

# ───────────────────────── 주인 결정 (최종) ─────────────────────────
OWNER = {
    'levels': 6,
    'metal_order': ['copper', 'iron', 'silver', 'gold', 'mithril', 'orichalcum'],
    'gem_order': ['quartz', 'garnet', 'moonstone', 'topaz', 'sapphire', 'dragonblood_stone'],
    'level_binding': False,          # 곡괭이·승강기·광산 층 어디에도 플레이어 레벨 조건 없음
    'all_levels_open': True,         # 승강기는 처음부터 모든 층으로
    'tier_rule': 'ore_tier <= pickaxe_tier',
    'too_weak_actionbar': '곡괭이가 약해 캘 수 없습니다',
    'ing_share': 0.20,
    'mixed_levels': True,
    'smelter_npc_name': '제련공 이그나',
    'miner_npc_name': '광부 브론',
}

# ───────────────────────── 금속 6 (희귀한 순) ─────────────────────────
# rank = 광물 등급 = 광석 단단함 등급 = 곡괭이 등급 (같은 숫자). 화면에는 숫자를 쓰지 않는다.
METALS = [
    {'rank': 1, 'key': 'copper', 'ko': '구리', 'smelt_gold': 2, 'color': '#E8843F',
     'ore_rarity': 'common', 'ingot_rarity': 'uncommon', 'pick_rarity': 'common',
     'ore_lore': '광산 얕은 곳 어디서나 보이는 붉은 광석. 제련소에서 녹이면 구리 주괴가 된다.',
     'ingot_lore': '구리 광석을 녹여 부은 주괴. 무르지만 다루기 쉬워 처음 벼리는 장비에 두루 쓴다.',
     'pick_lore': '광부 브론이 처음 오는 이에게 쥐여 주는 곡괭이. 구리 광석과 석영만 캘 수 있다.'},
    {'rank': 2, 'key': 'iron', 'ko': '철', 'smelt_gold': 4, 'color': '#C9CED6',
     'ore_rarity': 'common', 'ingot_rarity': 'uncommon', 'pick_rarity': 'uncommon',
     'ore_lore': '갱도 벽의 검붉은 광석. 무겁고 단단하다. 녹이면 철 주괴가 된다.',
     'ingot_lore': '철 광석을 녹여 부은 주괴. 두드릴수록 질겨진다.',
     'pick_lore': '구리 날을 철로 덧댄 곡괭이. 손에 묵직하게 감긴다.'},
    {'rank': 3, 'key': 'silver', 'ko': '은', 'smelt_gold': 8, 'color': '#EEF3FF',
     'ore_rarity': 'common', 'ingot_rarity': 'uncommon', 'pick_rarity': 'rare',
     'ore_lore': '어두운 벽을 따라 하얗게 뻗은 은맥. 녹이면 은 주괴가 된다.',
     'ingot_lore': '은 광석을 녹여 부은 주괴. 마력을 잘 받아들인다.',
     'pick_lore': '은을 입힌 곡괭이. 날이 닿는 곳마다 희미한 빛이 남는다.'},
    {'rank': 4, 'key': 'gold', 'ko': '금', 'smelt_gold': 12, 'color': '#F2C14E',
     'ore_rarity': 'uncommon', 'ingot_rarity': 'rare', 'pick_rarity': 'rare',
     'ore_lore': '황토빛 단층 사이에 박힌 금 알갱이. 녹이면 금 주괴가 된다.',
     'ingot_lore': '금 광석을 녹여 부은 주괴. 무겁고 녹슬지 않아 귀한 장비의 이음새에 쓴다.',
     'pick_lore': '금으로 테를 두른 곡괭이. 단단한 돌도 결을 따라 갈라진다.'},
    {'rank': 5, 'key': 'mithril', 'ko': '미스릴', 'smelt_gold': 18, 'color': '#7FF2FF',
     'ore_rarity': 'uncommon', 'ingot_rarity': 'rare', 'pick_rarity': 'epic',
     'ore_lore': '푸른 정동 깊이 자라는 가벼운 광석. 녹이면 미스릴 주괴가 된다.',
     'ingot_lore': '미스릴 광석을 녹여 부은 주괴. 깃털처럼 가볍고 강철보다 단단하다.',
     'pick_lore': '가볍고 질긴 미스릴 곡괭이. 날끝에 새긴 룬이 은은히 빛난다.'},
    {'rank': 6, 'key': 'orichalcum', 'ko': '오리하르콘', 'smelt_gold': 25, 'color': '#FF8A5C',
     'ore_rarity': 'rare', 'ingot_rarity': 'epic', 'pick_rarity': 'legendary',
     'ore_lore': '가장 깊은 곳의 붉은 금빛 광석. 쥐면 손바닥이 따뜻해진다. 녹이면 오리하르콘 주괴가 된다.',
     'ingot_lore': '오리하르콘 광석을 녹여 부은 주괴. 전설 속 장비만이 이 금속을 견딘다.',
     'pick_lore': '오리하르콘으로 벼린 곡괭이. 휘두를 때마다 붉은 불티가 흩날린다.'},
]
for _m in METALS:
    _m['ore'] = _m['key'] + '_ore'
    _m['ingot'] = _m['key'] + '_ingot'
    _m['pickaxe'] = _m['key'] + '_pickaxe'
    _m['ore_name'] = _m['ko'] + ' 광석'
    _m['ingot_name'] = _m['ko'] + ' 주괴'
    _m['pick_name'] = _m['ko'] + ' 곡괭이'
METAL = {m['key']: m for m in METALS}
BY_RANK = {m['rank']: m for m in METALS}

GEMS = [
    {'rank': 1, 'id': 'quartz', 'ko': '석영', 'rarity': 'rare', 'color': '#F6F2EA',
     'lore': '맑은 결정. 하급 강화석을 새기거나 곡괭이를 벼릴 때 쓴다.'},
    {'rank': 2, 'id': 'garnet', 'ko': '석류석', 'rarity': 'rare', 'color': '#C8102E',
     'lore': '광맥 사이에 박힌 짙은 붉은 보석. 하급 강화석을 새기거나 곡괭이를 벼릴 때 쓴다.'},
    {'rank': 3, 'id': 'moonstone', 'ko': '월장석', 'rarity': 'rare', 'color': '#9CCAFF',
     'lore': '달빛을 머금은 듯 은은한 젖빛 보석. 상급 강화석을 새기거나 곡괭이를 벼릴 때 쓴다.'},
    {'rank': 4, 'id': 'topaz', 'ko': '황옥', 'rarity': 'epic', 'color': '#FFC23A',
     'lore': '햇빛을 굳힌 듯한 노란 보석. 상급 강화석을 새기거나 곡괭이를 벼릴 때 쓴다.'},
    {'rank': 5, 'id': 'sapphire', 'ko': '청옥', 'rarity': 'epic', 'color': '#4A7CFF',
     'lore': '깊은 바다빛 보석. 최상급 강화석을 새기거나 곡괭이를 벼릴 때 쓴다.'},
    {'rank': 6, 'id': 'dragonblood_stone', 'ko': '용혈석', 'rarity': 'legendary', 'color': '#FF3B2F',
     'lore': '잠든 용의 피가 굳었다는 붉은 돌. 안쪽에서 불씨가 맥박친다. 최상급 강화석을 새길 때 쓴다.'},
]
GEM = {g['id']: g for g in GEMS}
GEM_BY_RANK = {g['rank']: g for g in GEMS}

# 새 몬스터 재료 (T §2 — 5·7·9층 몬스터 칸 광물의 자리)
MONSTER_NEW = {
    'cinder_hide': {'name': '잿불 가죽', 'rarity': 'uncommon', 'floor': 5, 'old': 'ember_shard',
                    'lore': '잿불 드레이크와 풀무 사냥개의 그을린 가죽. 불길 속에서도 타지 않는다.'},
    'resonant_sinew': {'name': '공명 힘줄', 'rarity': 'uncommon', 'floor': 7, 'old': 'prism_dust',
                       'lore': '정동 거한과 수정 용인의 몸속에서 떨던 힘줄. 퉁기면 맑은 음이 난다.'},
    'clock_oil': {'name': '태엽 기름', 'rarity': 'uncommon', 'floor': 9, 'old': 'mainspring',
                  'lore': '태엽 짐승들의 관절에서 흘러나온 검은 기름. 식어도 굳지 않는다.'},
}

# 옛 광물 재료 8 (T §1). slot: ingot = 주괴가 그 칸을 맡음 (가진 것은 광석 1:1) · monster = 새 몬스터 재료 1:1
RETIRED = {
    'rusted_iron': {'floor': 2, 'slot': 'ingot'},
    'slag_ingot': {'floor': 5, 'slot': 'ingot'},
    'ember_shard': {'floor': 5, 'slot': 'monster', 'to': 'cinder_hide'},
    'rime_crystal': {'floor': 6, 'slot': 'ingot'},
    'amethyst_shard': {'floor': 7, 'slot': 'ingot'},
    'prism_dust': {'floor': 7, 'slot': 'monster', 'to': 'resonant_sinew'},
    'brass_gear': {'floor': 9, 'slot': 'ingot'},
    'mainspring': {'floor': 9, 'slot': 'monster', 'to': 'clock_oil'},
}
# ingot 칸 옛 재료의 바꿀 광석 = 그 층 장비 레시피가 가장 많이 쓰는 금속의 광석 (proto036 이 계산해 계약에 고정)

# ───────────────────────── 캐기 (곡괭이 × 광석 단단함) ─────────────────────────
ORE_BASE_SECONDS = {1: 2.5, 2: 2.9, 3: 3.3, 4: 3.7, 5: 4.1, 6: 4.5}   # 곡괭이 속도 ×1.0 으로 한 블록 캐는 초
PICK_SPEED = {1: 1.0, 2: 1.2, 3: 1.4, 4: 1.6, 5: 1.8, 6: 2.0}          # 곡괭이 등급 → 모든 광석에 같은 배율 (좋을수록 빠름)
PICK_BONUS = {1: 0.0, 2: 0.02, 3: 0.04, 4: 0.06, 5: 0.08, 6: 0.10}     # 광석 1개 더 나올 확률
GEM_NODE_FACTOR = 1.5          # 보석 노드는 같은 등급 광석의 1.5배 시간
GEM_CHANCE = 0.022             # 광석 블록마다 같은 등급 보석이 덤으로 나올 확률
RICH = {'chance': 0.04, 'multiplier': 3}   # 다시 찰 때 그 사람에게만 풍부한 광맥 (×3)
MIN_SECONDS = 1.0              # 어떤 조합도 이보다 빨리 캐지지 않는다 (검사)

# 곡괭이 레시피 (제련소 station: smelter, category: tool — 마을 대장간 없이 광산 관리소에서도 된다). 레벨 조건 없음.
PICK_RECIPES = {
    'iron_pickaxe': {'prev': 'copper_pickaxe', 'ingot': ('copper_ingot', 12), 'gem': ('quartz', 2), 'essence': ('dim_essence', 2), 'gold': 300},
    'silver_pickaxe': {'prev': 'iron_pickaxe', 'ingot': ('iron_ingot', 16), 'gem': ('garnet', 2), 'essence': ('dim_essence', 4), 'gold': 1000},
    'gold_pickaxe': {'prev': 'silver_pickaxe', 'ingot': ('silver_ingot', 20), 'gem': ('moonstone', 3), 'essence': ('labyrinth_essence', 2), 'gold': 2500},
    'mithril_pickaxe': {'prev': 'gold_pickaxe', 'ingot': ('gold_ingot', 24), 'gem': ('topaz', 3), 'essence': ('labyrinth_essence', 4), 'gold': 5000},
    'orichalcum_pickaxe': {'prev': 'mithril_pickaxe', 'ingot': ('mithril_ingot', 28), 'gem': ('sapphire', 4), 'essence': ('radiant_essence', 3), 'gold': 10000},
}
COPPER_PICKAXE_PRICE = 50      # 잃어버렸을 때 (광부·관리소). 첫 1개는 무료 (ext mine.free_pickaxe) + 시작 꾸러미

# 강화석 새기기 (제련소, 결과 2개) — 정수가 들어가 광산만으로는 못 만든다
STONE_RECIPES = [
    {'id': 'lesser_enhance_stone', 'result': 'lesser_enhance_stone', 'gem': 'quartz', 'essence': 'dim_essence', 'gold': 20},
    {'id': 'lesser_enhance_stone_garnet', 'result': 'lesser_enhance_stone', 'gem': 'garnet', 'essence': 'dim_essence', 'gold': 20},
    {'id': 'greater_enhance_stone', 'result': 'greater_enhance_stone', 'gem': 'moonstone', 'essence': 'labyrinth_essence', 'gold': 120},
    {'id': 'greater_enhance_stone_topaz', 'result': 'greater_enhance_stone', 'gem': 'topaz', 'essence': 'labyrinth_essence', 'gold': 120},
    {'id': 'supreme_enhance_stone', 'result': 'supreme_enhance_stone', 'gem': 'sapphire', 'essence': 'radiant_essence', 'gold': 400},
    {'id': 'supreme_enhance_stone_dragonblood', 'result': 'supreme_enhance_stone', 'gem': 'dragonblood_stone', 'essence': 'radiant_essence', 'gold': 400},
]
STONE_YIELD = 2
ORE_PER_INGOT = 2

# ───────────────────────── 블록 (바닐라, 광석·보석 종류마다 하나씩 — 12개 모두 다름) ─────────────────────────
# V 규칙: 레드스톤 광석 안 됨(lit), 떨어지는 블록·블록 엔티티·정육면체 아님 안 됨, 자연스러움, 잘 읽힘, 종류마다 하나.
ORE_BLOCK = {'copper_ore': 'minecraft:copper_ore', 'iron_ore': 'minecraft:iron_ore', 'silver_ore': 'minecraft:calcite',
             'gold_ore': 'minecraft:gold_ore', 'mithril_ore': 'minecraft:deepslate_diamond_ore',
             'orichalcum_ore': 'minecraft:ancient_debris'}
GEM_BLOCK = {'quartz': 'minecraft:nether_quartz_ore', 'garnet': 'minecraft:cinnabar', 'moonstone': 'minecraft:sea_lantern',
             'topaz': 'minecraft:glowstone', 'sapphire': 'minecraft:deepslate_lapis_ore', 'dragonblood_stone': 'minecraft:magma_block'}
BLOCK_WHY = {
    'copper_ore': '바닐라 구리 광석 그대로 — 누구나 구리로 읽음',
    'iron_ore': '바닐라 철 광석 그대로',
    'silver_ore': '방해석: 어두운 벽에 하얀 줄 (V 비교 4개 중 가장 잘 보임, 바닐라에 은빛 점 광석 없음)',
    'gold_ore': '바닐라 금 광석 (돌 바탕) — 심층암 금 광석은 오리하르콘·용혈석 쪽 어두운 블록과 헷갈려 뺌',
    'mithril_ore': '심층암 다이아 광석: 어두운 바탕에 청록 점 (V)',
    'orichalcum_ore': '고대 잔해: 바닐라에서 가장 귀하고 단단한 광석으로 읽힘. 붉은 갈색 결 (별 주제가 없어져 V 의 반대 이유가 사라짐)',
    'quartz': '네더 석영 광석 + 석영 결정 모델 (V)',
    'garnet': '진사(26.x): 자연스러운 붉은 돌, 자기 소리 (V)',
    'moonstone': '바다 랜턴: 희뿌옇게 빛남, 캐면 그 사람 화면에서 빛이 꺼짐 (V)',
    'topaz': '발광석: 노란 결정 덩이가 빛남 — 자연 블록, 노랑은 이것뿐(금 광석과 바탕·밝기가 다름)',
    'sapphire': '심층암 청금석 광석 + 청옥 결정 모델 (V)',
    'dragonblood_stone': '마그마 블록: 붉게 맥박치는 돌 = 용의 피. 광산 안은 피해가 없어 밟아도 안전, 물이 없어 거품 기둥 없음',
}
FORBIDDEN_BLOCKS = ['minecraft:redstone_ore', 'minecraft:deepslate_redstone_ore', 'minecraft:gravel', 'minecraft:sand',
                    'minecraft:suspicious_gravel', 'minecraft:potent_sulfur', 'minecraft:budding_amethyst']

# ───────────────────────── 광산 층 6 (같은 x,z 에 위아래로) ─────────────────────────
# ore_w / gem_w = 섞임 무게 (합 100). veins = 광맥 블록 수 (무더기 3~5칸). regen = 개인 재생 분 (config 손잡이 기본값).
# 바이옴 띠 = 4칸 단위 경계를 층 상자 사이 틈에 둠. 상자 = [바닥 y − 4, 바닥 y + 15].
LEVELS = [
    {'n': 1, 'id': 'shallow_drift', 'name': '얕은 갱도', 'depth_m': 40, 'floor_y': 135, 'biome': 'minecraft:dripstone_caves',
     'biome_y': [128, 319], 'color': '#E8843F', 'depleted': 'minecraft:cobblestone', 'regen': 8, 'veins': 56,
     'ore_w': {'copper': 62, 'iron': 30, 'silver': 8},
     'gem_nodes': 3, 'gem_w': {'quartz': 70, 'garnet': 30},
     'light': ['lantern', 'waxed_copper_lantern'], 'regen_fx': 'WAX_ON',
     'palette': {'wall': ['stone', 'andesite', 'tuff'], 'floor': ['coarse_dirt', 'packed_mud', 'stone'], 'post': 'stripped_oak_log',
                 'beam': 'oak_log', 'decor': ['rail', 'barrel', 'oak_fence', 'iron_chain']},
     'mood': '나무 받침 갱도, 레일과 통, 따뜻한 등불. 가장 밝고 아늑하다.'},
    {'n': 2, 'id': 'dripstone_drift', 'name': '종유 갱도', 'depth_m': 90, 'floor_y': 110, 'biome': 'minecraft:dripstone_caves',
     'biome_y': [104, 127], 'color': '#C9CED6', 'depleted': 'minecraft:mossy_cobblestone', 'regen': 9, 'veins': 58,
     'ore_w': {'copper': 34, 'iron': 46, 'silver': 15, 'gold': 5},
     'gem_nodes': 3, 'gem_w': {'quartz': 30, 'garnet': 55, 'moonstone': 15},
     'light': ['lantern'], 'regen_fx': 'ELECTRIC_SPARK',
     'palette': {'wall': ['stone', 'deepslate', 'dripstone_block', 'andesite'], 'floor': ['stone', 'tuff'],
                 'post': 'stripped_dark_oak_log', 'beam': 'dark_oak_log', 'decor': ['pointed_dripstone', 'iron_chain']},
     'mood': '돌과 심층암이 섞인 벽, 천장에 종유석, 쇠사슬에 매단 등불.'},
    {'n': 3, 'id': 'moss_vein', 'name': '이끼빛 수맥', 'depth_m': 140, 'floor_y': 85, 'biome': 'minecraft:lush_caves',
     'biome_y': [80, 103], 'color': '#EEF3FF', 'depleted': 'minecraft:cobbled_deepslate', 'regen': 9, 'veins': 60,
     'ore_w': {'copper': 14, 'iron': 30, 'silver': 41, 'gold': 12, 'mithril': 3},
     'gem_nodes': 3, 'gem_w': {'garnet': 25, 'moonstone': 55, 'topaz': 20},
     'light': ['soul_lantern', 'glow_lichen'], 'regen_fx': 'WAX_OFF',
     'palette': {'wall': ['deepslate', 'tuff'], 'floor': ['polished_deepslate', 'tuff', 'deepslate_tiles'],
                 'post': 'stripped_spruce_log', 'beam': 'spruce_log', 'decor': ['tuff_bricks', 'moss_carpet', 'glow_lichen']},
     'mood': '심층암과 응회암, 이끼와 발광 이끼, 차가운 영혼 등불. 조용하다.'},
    {'n': 4, 'id': 'ochre_fault', 'name': '황토 단층', 'depth_m': 200, 'floor_y': 60, 'biome': 'minecraft:badlands',
     'biome_y': [52, 79], 'color': '#F2C14E', 'depleted': 'minecraft:cobblestone', 'regen': 10, 'veins': 60,
     'ore_w': {'copper': 9, 'iron': 14, 'silver': 23, 'gold': 39, 'mithril': 12, 'orichalcum': 3},
     'gem_nodes': 3, 'gem_w': {'moonstone': 25, 'topaz': 55, 'sapphire': 20},
     'light': ['ochre_froglight', 'lantern'], 'regen_fx': 'CRIT',
     'palette': {'wall': ['granite', 'terracotta', 'orange_terracotta', 'tuff'], 'floor': ['packed_mud', 'terracotta', 'coarse_dirt'],
                 'post': 'stripped_acacia_log', 'beam': 'acacia_log', 'decor': ['brown_terracotta', 'iron_chain', 'barrel']},
     'mood': '붉고 노란 흙층이 비스듬히 갈라진 단층. 황토빛 개구리불이 따뜻하게 비춘다.'},
    {'n': 5, 'id': 'geode_hollow', 'name': '청록 정동', 'depth_m': 260, 'floor_y': 35, 'biome': 'minecraft:warped_forest',
     'biome_y': [28, 51], 'color': '#7FF2FF', 'depleted': 'minecraft:cobbled_deepslate', 'regen': 10, 'veins': 62,
     'ore_w': {'copper': 4, 'iron': 8, 'silver': 12, 'gold': 22, 'mithril': 41, 'orichalcum': 13},
     'gem_nodes': 3, 'gem_w': {'topaz': 25, 'sapphire': 55, 'dragonblood_stone': 20},
     'light': ['pearlescent_froglight', 'small_amethyst_bud', 'glow_lichen'], 'regen_fx': 'GLOW',
     'palette': {'wall': ['deepslate', 'smooth_basalt', 'amethyst_block'], 'floor': ['basalt', 'deepslate'],
                 'post': 'polished_basalt', 'beam': 'polished_basalt', 'decor': ['amethyst_block', 'amethyst_cluster', 'small_amethyst_bud']},
     'mood': '둥근 정동, 자수정 군락(캐지 않음), 청록 포자가 떠다니는 푸른 빛.'},
    {'n': 6, 'id': 'dragon_abyss', 'name': '용의 심연', 'depth_m': 330, 'floor_y': 10, 'biome': 'minecraft:basalt_deltas',
     'biome_y': [-64, 27], 'color': '#FF8A5C', 'depleted': 'minecraft:blackstone', 'regen': 10, 'veins': 66,
     'ore_w': {'copper': 5, 'iron': 7, 'silver': 9, 'gold': 13, 'mithril': 23, 'orichalcum': 43},
     'gem_nodes': 3, 'gem_w': {'topaz': 15, 'sapphire': 30, 'dragonblood_stone': 55},
     'light': ['end_rod', 'verdant_froglight'], 'regen_fx': 'END_ROD',
     'palette': {'wall': ['basalt', 'polished_basalt', 'smooth_basalt'], 'floor': ['polished_blackstone', 'smooth_basalt'],
                 'post': 'chiseled_polished_blackstone', 'beam': 'polished_blackstone_bricks', 'decor': ['chiseled_polished_blackstone', 'end_rod']},
     'mood': '검은 현무암 동굴, 하얀 재가 별가루처럼 내리고 붉은 돌이 맥박친다. 가장 깊고 어둡다.'},
]
LEVEL_BOX = (-4, 15)            # 바닥 y 기준 상자 (아래, 위)
LEVEL_XZ = (-30, 30)
GEM_NODE_REGEN = 30            # 분 (config 손잡이)
LIFT_SECONDS = 2.0

# 활동 모델 (economy.py): 블록마다 조준 1초 + 무더기 사이 2초 + 층 한 바퀴 걷기 + 승강기
AIM_S = 1.0
CLUSTER_S = 2.0
CLUSTER_SIZE = 4.0
LOOP_S = 45.0
LIFT_TRIP_S = 12.0             # 승강기 2초 + 내려서 걷기
STAMINA = {'max': 1200, 'regen_per_min': 1.0, 'cost_per_block': 0.75, 'tired_yield': 0.3, 'bar_below': 0.25, 'boss_refill': 0}

# ───────────────────────── 재료·생성기 규칙 ─────────────────────────
ING_SHARE = OWNER['ing_share']  # 장비 레시피 주괴 = 반올림(옛 일반 재료 합 × 0.20), 최소 2
MIN_ING = 2
INGOT_UNIT = 0.5               # 강화 S(주괴) 개수 배율
# 금속 고르기 (주인 결정 4): 힘 P = 단계 + 희귀도 걸음 + 보스 장비 걸음 → 자리 pos = 1 + (P − 1)/2 (1..6)
RARITY_STEP = {'common': 0.0, 'uncommon': 0.25, 'rare': 0.5, 'epic': 1.0, 'legendary': 1.5, 'mythic': 2.0}
BOSS_STEP = 0.5
MIX_BAND = (0.375, 0.625)      # pos 의 소수부가 이 안(양끝 포함)이면 이웃 두 금속을 섞는다 (윗 금속 몫 = 소수부)
# 던전 광석 (R §3-10, 모든 층): 옛 광물 칸은 지우고, 층마다 1회(솔로) 기대 광석이 아래 값이 되게 루팅에 광석 항목을 더한다
DUNGEON_ORE_SPLIT = {'mob': 0.45, 'elite': 0.05, 'boss': 0.15, 'chest': 0.35}
DUNGEON_ORE_SHARE = 0.25       # 목표 = 그 층 대표 한 벌 광석 수요 ÷ 던전 횟수 × 0.25 (proto036 이 계산, 계약에 고정)

# 판매 (config sell.mine) — 값 = 반올림(base × (1 + rank_bonus × (등급 − 1))), 최소 1
SELL_MINE = {'ore': 1, 'ingot': 3, 'gem': 6, 'rank_bonus': 0.35}

# 밸런스 가정 (T 와 같음 — 주인 서버 records.yml 로 맞추기 전까지)
RUN_MINUTES = {1: 15, 2: 16, 3: 18, 4: 20, 5: 21, 6: 23, 7: 24, 8: 26, 9: 27, 10: 30}
PARTY_TIME = 0.8
PARTY_BONUS = 0.15
GOLD_RATIO_MAX = 0.20          # 광산 G/분 ÷ 던전 G/분 (그 단계, 그 단계 곡괭이)


def half_up(x):
    return int(x + 0.5)


def sell_value(kind, rank):
    return max(1, half_up(SELL_MINE[kind] * (1 + SELL_MINE['rank_bonus'] * (rank - 1))))


def mine_seconds(ore_rank, pick_rank, node=False):
    """곡괭이 등급 p 로 등급 o 광석(또는 보석 노드) 한 블록 캐는 초. o > p 면 None (못 캠)."""
    if ore_rank > pick_rank:
        return None
    s = ORE_BASE_SECONDS[ore_rank] / PICK_SPEED[pick_rank]
    return s * (GEM_NODE_FACTOR if node else 1.0)


def power_pos(tier, rarity, boss):
    p = tier + RARITY_STEP[rarity] + (BOSS_STEP if boss else 0.0)
    return max(1.0, min(6.0, 1 + (p - 1) / 2))


def metals_for(tier, rarity, boss, n):
    """장비 하나의 주괴 n 개를 금속에 나눈다 → [(금속 key, 개수)] (윗 금속이 뒤). 섞음은 이웃 두 금속만."""
    pos = power_pos(tier, rarity, boss)
    lo = int(pos)
    f = pos - lo
    if lo >= 6:
        return [(BY_RANK[6]['key'], n)]
    if f < MIX_BAND[0] - 1e-9:
        return [(BY_RANK[lo]['key'], n)]
    if f > MIX_BAND[1] + 1e-9:
        return [(BY_RANK[lo + 1]['key'], n)]
    up = max(1, min(n - 1, half_up(n * f))) if n >= 2 else 0
    out = [(BY_RANK[lo]['key'], n - up)]
    if up:
        out.append((BY_RANK[lo + 1]['key'], up))
    return out


def primary_metal(tier, rarity, boss):
    """강화 S 칸·드롭 장비의 금속 = pos 를 반올림한 금속 (섞임이면 윗 금속)."""
    pos = power_pos(tier, rarity, boss)
    lo = int(pos)
    f = pos - lo
    r = lo + (1 if f >= MIX_BAND[0] - 1e-9 else 0)
    return BY_RANK[max(1, min(6, r))]['key']
