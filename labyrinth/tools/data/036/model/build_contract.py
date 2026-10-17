#!/usr/bin/env python3
"""계약 JSON 4개를 만든다 — tools/data/036/{mine,materials,visual,district}.json.

원본: params.py · district_data.py · out/layout.json (layout6) · out/proto036.json (proto036) · out/economy.json (economy).
  python3 -B build_contract.py            # 쓴다
  python3 -B build_contract.py --check    # 지금 파일과 같은지만 본다 (다르면 1)
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
DATA = HERE.parent
sys.path.insert(0, str(HERE))
import params as P  # noqa: E402
import district_data as D  # noqa: E402
import layout6  # noqa: E402

CONTRACT = '0.3.6'
NOTE = '계약 (Q0). 손으로 고치지 말고 tools/data/036/model/params.py 를 고친 뒤 run_all.py — check_contract.py 가 지킨다.'


def load(name):
    return json.loads((HERE / 'out' / name).read_text(encoding='utf-8'))


def ore_of(m):
    return m['ore']


# ───────────────────────── mine.json ─────────────────────────
def build_mine(lay, eco):
    levels = []
    for L in P.LEVELS:
        lv = lay[str(L['n'])]
        y = L['floor_y']
        levels.append({
            'n': L['n'], 'id': L['id'], 'name': L['name'], 'depth_m': L['depth_m'],
            'floor_y': y, 'box': [P.LEVEL_XZ[0], y + P.LEVEL_BOX[0], P.LEVEL_XZ[0], P.LEVEL_XZ[1], y + P.LEVEL_BOX[1], P.LEVEL_XZ[1]],
            'biome': L['biome'], 'biome_y': L['biome_y'],
            'lighting': {'sources': L['light'], 'vein_face_min': 8, 'floor_min': 6, 'lift_hall_min': 12, 'spacing_max': 8},
            'atmosphere': L['mood'], 'palette': L['palette'], 'title_color': L['color'], 'regen_fx': L['regen_fx'],
            'depleted_block': L['depleted'],
            'ore_weights': {P.METAL[k]['ore']: w for k, w in L['ore_w'].items()},
            'veins_total': L['veins'],
            'vein_blocks': {P.METAL[k]['ore']: n for k, n in sorted(lv['counts'].items(), key=lambda kv: P.METAL[kv[0]]['rank'])},
            'gem_weights': dict(L['gem_w']), 'gem_nodes': [g[3] for g in lv['gem_nodes']],
            'regen_minutes_default': L['regen'], 'gem_node_regen_minutes_default': P.GEM_NODE_REGEN,
            'lift': lv['lift'], 'landing': lv['landing'], 'office': L['n'] == 1,
            'prototype': {'shape': lv['shape'], 'reach_max': lv['reach_max'], 'reach_max_server': lv['reach_max_server'],
                          'loop_blocks': lv['loop_blocks'],
                          'ascii': f"tools/data/036/model/out/L{L['n']}.txt"},
        })
    ores = {}
    for m in P.METALS:
        ores[m['ore']] = {'metal': m['key'], 'name': m['ore_name'], 'tier': m['rank'], 'block': P.ORE_BLOCK[m['ore']],
                          'base_seconds': P.ORE_BASE_SECONDS[m['rank']], 'yield': 1, 'gem': P.GEM_BY_RANK[m['rank']]['id'],
                          'ingot': m['ingot'], 'color': m['color']}
    gems = {}
    for g in P.GEMS:
        gems[g['id']] = {'name': g['ko'], 'tier': g['rank'], 'block': P.GEM_BLOCK[g['id']],
                         'base_seconds': round(P.ORE_BASE_SECONDS[g['rank']] * P.GEM_NODE_FACTOR, 3), 'yield': 1, 'color': g['color']}
    picks = {}
    for m in P.METALS:
        r = m['rank']
        rec = None
        if m['pickaxe'] in P.PICK_RECIPES:
            d = P.PICK_RECIPES[m['pickaxe']]
            rec = {'id': m['pickaxe'], 'station': 'smelter', 'category': 'tool',
                   'materials': {d['prev']: 1, d['ingot'][0]: d['ingot'][1], d['gem'][0]: d['gem'][1], d['essence'][0]: d['essence'][1]},
                   'gold': d['gold']}
        picks[m['pickaxe']] = {
            'name': m['pick_name'], 'tier': r, 'speed': {str(o): v for o, v in P.pick_speed(r).items()},
            'bonus': P.PICK_BONUS[r],
            'mines': [x['ore'] for x in P.METALS if P.can_mine(x['rank'], r)] + [g['id'] for g in P.GEMS if P.can_mine(g['rank'], r)],
            'slow': [x['ore'] for x in P.METALS if P.can_mine(x['rank'], r) and x['rank'] > r] + [g['id'] for g in P.GEMS if P.can_mine(g['rank'], r) and g['rank'] > r],
            'seconds': {x['ore']: round(P.mine_seconds(x['rank'], r), 2) for x in P.METALS if P.can_mine(x['rank'], r)},
            'recipe': rec,
            'obtain': (['starter_kit', 'mine_office 첫 1개 무료 (ext mine.free_pickaxe)', f"mine_office·광부 {P.COPPER_PICKAXE_PRICE}G"]
                       if r == 1 else ['제련소·광산 관리소 곡괭이 탭 (앞 곡괭이를 재료로 넣어 다시 벼림)']),
            'level_req': None}
    eco_rates = {k: v['ore_per_min'] for k, v in eco['table_b_focused'].items()}
    return {
        'contract': CONTRACT, 'schema': 1, 'note': NOTE,
        'owner_decisions': {'levels': P.OWNER['levels'], 'level_binding': P.OWNER['level_binding'], 'all_levels_open': P.OWNER['all_levels_open'],
                            'tier_rule': P.OWNER['tier_rule'], 'mixed_levels': True},
        'world': {'name': 'labyrinth_mine', 'generator': 'void (dungeon/VoidGenerator 재사용)', 'persist': True,
                  'folder': 'world/dimensions/minecraft/labyrinth_mine (26.x — build_world.sh skip_dirs 에 넣는다)',
                  'xz': list(P.LEVEL_XZ), 'chunks': '층 6개가 같은 x,z (−30..30) 에 위아래로 → 청크 16개',
                  'rules': ['LabyrinthWorld.applyRules 와 같음 (몹 스폰 끔·스폰 한도 0·불 번짐 0·무작위 틱 0·시간 멈춤·keepInventory)',
                            'PvP 끔 (PvpModule.applyWorldRules 가 광산 월드는 늘 끔 — R §2-2)'],
                  'gamemode_rule': '기억 없이 규칙만 (R §2-3): 광산 월드 안 = ADVENTURE · 광산 밖인데 ADVENTURE = SURVIVAL · CREATIVE·SPECTATOR 는 건드리지 않음. '
                                   '접속·월드 이동·리스폰·텔레포트 때 같은 규칙. ext mine.prev_mode 는 없음',
                  'safety': ['피해 0: DamageService.applyToPlayer·상태 이상 진입점에서 광산 월드면 0 (EntityDamageEvent 취소만으로는 부족 — R §2-2) '
                             '+ 바닐라 피해 EntityDamageEvent(떨어짐·마그마 블록 = 용혈석 노드·질식·불 등)도 모두 취소',
                             'TargetFilter.inSafeZone(광산 월드) = true',
                             '스폰: EntitySpawnEvent 종류 화이트리스트 MANNEQUIN·ITEM_DISPLAY·BLOCK_DISPLAY·TEXT_DISPLAY·INTERACTION·ITEM 만, 30초마다 Mob 지움 (R §2-4)',
                             '배고픔 안 줄어듦 · 엔더 진주·후렴과 텔레포트·양동이 막음 · 바닥 아래로 떨어지면 그 층 승강장으로',
                             '들어올 때 HASTE·CONDUIT_POWER 지움 (속도 계약)'],
                  'build': 'jar 의 mine/levels/L1..L6.json 을 틱 분할로 붙임. <광산 월드>/labyrinth-mine.yml 에 층마다 청사진 해시 — 바뀐 층만 다시 지음 (그 층 사람은 승강장으로, 그 층 광맥 기록은 지움)'},
        'levels': levels,
        'ores': ores, 'gems': gems, 'pickaxes': picks,
        'rules': {
            'tier': f'광석·보석 tier ≤ 곡괭이 tier + {P.REACH_ABOVE} 일 때만 캔다 (0.3.6.1 주인 결정 — 한 단계 위는 그 광석 제 곡괭이 빠르기 × {P.STRETCH_FACTOR}). '
                    '아니면 진행 없음 + 액션바 한 줄 "' + P.OWNER['too_weak_actionbar'] + '" (1초에 1번). 레벨 조건은 어디에도 없다',
            'reach_above': P.REACH_ABOVE, 'stretch_factor': P.STRETCH_FACTOR,
            'too_weak_actionbar': P.OWNER['too_weak_actionbar'],
            'seconds': 'base_seconds(광석 tier) ÷ 곡괭이 speed[광석 tier] (보석 노드는 gems.base_seconds). 서버가 Tool 규칙 speed = 30·단단함(Material#getHardness) ÷ (20·초) 로 바꿈, correct_for_drops = TRUE',
            'min_seconds': P.MIN_SECONDS,
            'can_break': '곡괭이 CAN_BREAK = mines 의 블록들 (광산 블록 표에서). 블록 설정이 바뀌면 접속 때 곡괭이 구성요소를 다시 씀',
            'outside_mine': '광산 월드 밖(오버월드·네더·엔드·미궁 월드 모두)에서 그 곡괭이로 광산 블록 12종을 부수면 취소 + 안내 1초에 1번 (R §3-15). '
                            '미궁도 이 블록을 쓴다: 2층 벽 구리·철 광석 · 6·7층 방해석 (DungeonManager 가 이미 부수기를 막음 — 안내 글만 더함). '
                            '0.3.6.1 보석 블록 6개(좀벌레 돌)는 미궁·마을·구역 어디에도 없다',
            'server_recheck': 'BlockBreakEvent 는 늘 취소하고 서버가 다시 본다: 광산 월드 · 곡괭이 tier + 1 ≥ 광석 tier · 그 사람에게 고갈 아님 · '
                              f'눈 → 블록 상자 거리 ≤ {P.REACH_CLIENT} + {P.REACH_SERVER_SLACK} (바닐라 서버는 5.5 까지 받아 고친 클라이언트가 더 멀리 캠) · 가방 자리. 하나라도 아니면 수확 없음',
            'pickaxe_item': '바탕 아이템은 지금 방식 그대로 PAPER (ENCHANTABLE 없음 → 효율 마법·모루로 속도 계약이 깨지지 않음) + MAX_STACK_SIZE 1',
            'harvest': {'ore_per_block': 1, 'bonus': '곡괭이 bonus 확률로 +1', 'gem_chance': P.GEM_CHANCE,
                        'gem_rule': '광석 블록마다 gem_chance 로 같은 tier 보석 1개', 'gem_node': '1개, 노드 재생 gem_node_regen_minutes',
                        'rich': {'chance': P.RICH['chance'], 'multiplier': P.RICH['multiplier'], 'shown': '그 사람에게만 반짝임'},
                        'into_bag': '가방에 바로 — 가득 차면 캐지지도 비워지지도 않음 ("가방이 가득 찼습니다")', 'no_vanilla_drops': True, 'no_xp': True},
            'veins': {'shared': '진짜 블록이 모두에게 빈 광맥(depleted_block)이 되고 시간이 지나면 다시 찬다 (계약 §0-3)',
                      'regen': '다시 차는 시간 = regen_minutes ÷ min(광산 월드 사람 수, regen_players_cap). 재시작 때는 다 찬 상태',
                      'ids': '광맥 번호 = 청사진 마커를 (y, z, x) 순으로 정렬한 번호', 'reach_max': layout6.REACH_MAX,
                      'reach_metric': '발 = 바닥+1, 눈 = 바닥+2.62, 선 자리 아무 곳 (몸 폭 0.6), 눈 → 블록 상자 가장 가까운 점 ≤ 4.5 (R §2-8). '
                                      '밟고 설 수 있는 장식(통·울타리·계단 등) 위도 선 자리로 잰다',
                      'reach_server': P.REACH_CLIENT + P.REACH_SERVER_SLACK,
                      'reach_server_metric': '같은 방식, 거리만 4.75 (server_recheck 의 한도) — 여기서도 ≤ reach_max'},
            'lift': {'ride_seconds': P.LIFT_SECONDS, 'gate': None, 'menu': '6층 모두 (깊이 순) + 마을로 — 잠김 없음',
                     'effect': '어둠 2초 + 쇠사슬·수레 소리, 움직이면 취소', 'arrival': '부제목 <title_color>이름 (층 번호 글자 없음)'},
            'office': {'interact': 'mine_office', 'where': '얕은 갱도 승강기 홀 북쪽 벽감 (청사진 마커 office)', 'needs_district': False,
                       'tabs': ['곡괭이 (첫 1개 무료 · 이후 구리 곡괭이 %dG)' % P.COPPER_PICKAXE_PRICE, '제련 (×1·×8·전부)', '새기기', '곡괭이 벼리기',
                                '팔기 (SellMenu 그대로, 도구는 못 팜)', '광맥 현황'],
                       'note': '메뉴는 코드로 만든다 — npcs.yml 에 정의가 없어도 열린다 (R §2-1). 구역 NPC 광부·제련공은 같은 메뉴의 얼굴'},
            'teleport': '/미궁 광산 (/lab mine)·메인 메뉴 "광산": 구역이 있으면 승강장으로, 없으면 얕은 갱도 승강장으로. 미궁 안에서는 못 씀. '
                        'village.teleport_command: false 서버는 기본 끔 (R §3-17)',
        },
        'config_defaults': {'mine': {
            'enabled': True, 'world': 'labyrinth_mine', 'teleport_command': 'auto', 'lift_seconds': P.LIFT_SECONDS,
            'regen_minutes': [L['regen'] for L in P.LEVELS], 'gem_node_regen_minutes': P.GEM_NODE_REGEN, 'gem_chance': P.GEM_CHANCE,
            'rich': dict(P.RICH),
            'fx': {'pop': True}, 'no_hunger': True, 'safe': True,
            'district': {'auto_build': True, 'sites': ['east', 'south_east'], 'blocks_per_tick': 3000, 'notify_admins': True}},
            'note': 'config.yml 에는 손잡이만 (R §3-16). 층·광석·블록·바이옴·초는 content/mine.yml (자동 갱신). 키가 없으면 코드 기본값 = 이 값'},
        'content_mine_yml': {'file': 'content/mine.yml', 'from': 'tools/mine/gen_mine.py (Q1) 가 이 파일의 levels·ores·gems 를 옮김',
                             'parser': 'ContentParser → Content.mine() (MineDef)', 'coupled_with': 'items.yml (mine_level·mine_kind·tool 은 Q3 생성기가 이 파일에서 채우고 ContentValidator 가 맞대어 봄)'},
        'names': names(),
        'economy': {'focused_ore_per_min': eco_rates, 'source': 'tools/data/036/model/out/economy.json'},
    }


def names():
    return {
        'interact': {'mine_lift': '승강기 메뉴 (구역 승강장 · 광산 각 층 승강기)', 'mine_office': '광산 관리소 메뉴 (광산 안)',
                     'smelter': '제련소 메뉴 (구역 제련소)', 'mine_info': '광부 게시판 (광맥 현황)'},
        'npc_roles': {'miner': 'MineApi.openOffice', 'smelter': 'CraftingService.openSmelter'},
        'markers': {'mine_exit': '광산에서 올라올 때 도착 자리 (pos, face)', 'office': '광산 청사진: 관리소 칸', 'lift': '광산 청사진: 승강기',
                    'landing': '광산 청사진: 내리는 자리', 'vein': '광산 청사진: 광맥 (@vein)', 'gem': '광산 청사진: 보석 노드 (@gem)'},
        'ambient': {'dust': '승강장 갱구 먼지', 'embers': '제련소 화덕', 'smoke': '굴뚝'},
        'ext': {'mine.free_pickaxe': 'true = 첫 무료 구리 곡괭이를 받음', 'mat036.notice': 'true = 옛 재료 바꿈 안내를 봄'},
        'ext_removed': ['mine.prev_mode (R §2-3)', 'mine.depleted · mine.hash (광맥 공유, §0-3)', 'mine.stamina · mine.stamina_at (기력 없음, §0-1)'],
        'pdc': {'labyrinth:mine_node': '"L<n>:<i>" 0.3.6 보석 결정 ItemDisplay — 0.3.6.1 에서 없앰, 남은 것을 지울 때만 씀'},
        'stations': {'blacksmith': '대장간 (장비)', 'smelter': '제련소·광산 관리소 (제련·새기기·곡괭이)'},
        'recipe_categories': {'tool': '곡괭이'},
        'source_kinds': {'mine': '광산', 'smelt': '제련소'},
        'commands': ['/미궁 광산 (/lab mine)', '/labadmin mine selftest|stats <이름>|rebuild [층]', '/labadmin village district info|preview|build|remove mine'],
        'files': {'world_meta': '<광산 월드>/labyrinth-mine.yml', 'district_meta': '<주 월드>/labyrinth-district-mine.yml',
                  'district_backup': '<주 월드>/labyrinth-district-mine.backup.gz', 'district_blocked': 'plugins/Labyrinth/village/district-mine-blocked.txt',
                  'fingerprint': 'jar village/districts/mine.fp', 'blueprints': 'jar mine/levels/L1..L6.json', 'district_pieces': 'jar village/districts/mine.json'},
        'selftest': {'mine': '[광산 자가 진단] 결과: 예외 0 · levels=6/6 · mismatched=0 · veins=N · gems=18 · reach_max≤12 · unreachable=0 · lifts=6/6 · office=1 · tool_mismatch=0 · mobs=0',
                     'district': '[광산 마을 자가 진단] 결과: 예외 0 · checked=N mismatched=0 · overlaps=0 · floating=0 · tree_remnants=0 · blocked_doors=0 · path_steps=0 · junction=ok · npcs=2/2 · interact=a/a'},
    }


# ───────────────────────── materials.json ─────────────────────────
def build_materials(proto, eco):
    items = {}
    for m in P.METALS:
        r = m['rank']
        items[m['ore']] = {'name': m['ore_name'], 'type': 'material', 'kind': 'ore', 'mine_level': r, 'rarity': m['ore_rarity'],
                           'sell': P.sell_value('ore', r), 'sources': ['mine', 'drop', 'elite', 'boss', 'chest'],
                           'sources_text': '광산 (그 금속이 많은 층) · 던전 몬스터·상자에서 조금', 'lore': m['ore_lore']}
        items[m['ingot']] = {'name': m['ingot_name'], 'type': 'material', 'kind': 'ingot', 'mine_level': r, 'rarity': m['ingot_rarity'],
                             'sell': P.sell_value('ingot', r), 'sources': ['smelt'],
                             'sources_text': f"제련소 {m['ore_name']} ×{P.ORE_PER_INGOT}, {m['smelt_gold']}G", 'lore': m['ingot_lore']}
    for g in P.GEMS:
        items[g['id']] = {'name': g['ko'], 'type': 'material', 'kind': 'gem', 'mine_level': g['rank'], 'rarity': g['rarity'],
                          'sell': P.sell_value('gem', g['rank']), 'sources': ['mine'],
                          'sources_text': f"광산 · {P.BY_RANK[g['rank']]['ore_name']}을 캘 때 드물게 · 보석 광석", 'lore': g['lore']}
    for k, d in P.MONSTER_NEW.items():
        items[k] = {'name': d['name'], 'type': 'material', 'kind': 'monster', 'floor': d['floor'], 'rarity': d['rarity'],
                    'sell': 'SellPrices 재료 공식 (uncommon · 그 층)', 'sources': ['drop', 'elite', 'boss', 'chest'],
                    'sources_text': '던전 몬스터·정예·보스·상자 (옛 ' + d['old_ko'] + ' 자리)', 'lore': d['lore'], 'replaces': d['old']}
    for k, d in P.DROP_PARTS.items():
        items[k] = {'name': d['name'], 'type': 'material', 'kind': 'monster', 'floor': d['floor'], 'rarity': d['rarity'],
                    'sell': 'SellPrices 재료 공식 (희귀도 · 그 층)', 'sources': ['drop', 'chest'],
                    'sources_text': '그 몸을 가진 몬스터 · 그 층 상자 (몹 주제 드롭 — drops_spec)', 'lore': d['lore'],
                    'texture': {'style': d['style'], 'palette': d['palette']}}
        if d.get('pre_release'):
            items[k]['pre_release'] = d['pre_release']
    for m in P.METALS:
        r = m['rank']
        items[m['pickaxe']] = {'name': m['pick_name'], 'type': 'tool', 'kind': 'pickaxe', 'tier': r, 'rarity': m['pick_rarity'],
                               'sell': None, 'sellable': False, 'stack': 1, 'level_req': None,
                               'tool': {'kind': 'pickaxe', 'tier': r, 'speed': {str(o): v for o, v in P.pick_speed(r).items()}, 'bonus': P.PICK_BONUS[r]},
                               'sources': ['starter', 'shop'] if r == 1 else ['craft'],
                               'sources_text': (f'시작 꾸러미 · 광산 관리소·광부 (처음 1개 무료, 이후 {P.COPPER_PICKAXE_PRICE}G)' if r == 1
                                                else '제련소·광산 관리소 곡괭이 벼리기'),
                               'lore': m['pick_lore'], 'model': {'shape': 'pickaxe'}}
    smelting = [{'id': m['ingot'], 'result': m['ingot'], 'station': 'smelter', 'category': 'material',
                 'materials': {m['ore']: P.ORE_PER_INGOT}, 'gold': m['smelt_gold'], 'amount': 1} for m in P.METALS]
    carving = [{'id': s['id'], 'result': s['result'], 'station': 'smelter', 'category': 'material',
                'materials': {s['gem']: 1, s['essence']: 1}, 'gold': s['gold'], 'amount': P.STONE_YIELD} for s in P.STONE_RECIPES]
    pick_rec = []
    for pid, d in P.PICK_RECIPES.items():
        pick_rec.append({'id': pid, 'result': pid, 'station': 'smelter', 'category': 'tool',
                         'materials': {d['prev']: 1, d['ingot'][0]: d['ingot'][1], d['gem'][0]: d['gem'][1], d['essence'][0]: d['essence'][1]},
                         'gold': d['gold'], 'consumes_previous_pickaxe': True})
    retired = {}
    for old, r in P.RETIRED.items():
        retired[old] = {'floor': r['floor'], 'slot': r['slot'], 'to': proto['conversion'][old], 'ratio': '1:1'}
    ex = {}
    for (t, rar, boss) in [(1, 'common', False), (1, 'uncommon', False), (1, 'rare', True), (2, 'uncommon', False), (3, 'rare', False),
                           (3, 'epic', True), (4, 'rare', False), (4, 'epic', False), (5, 'rare', False), (5, 'epic', False), (6, 'epic', False),
                           (7, 'rare', False), (7, 'epic', False), (7, 'legendary', True), (8, 'epic', False), (8, 'legendary', True),
                           (9, 'epic', False), (9, 'legendary', False), (10, 'epic', False), (10, 'legendary', False)]:
        ex[f"{t}/{rar}{'/boss' if boss else ''}"] = {'pos': P.power_pos(t, rar, boss), 'split_of_10': P.metals_for(t, rar, boss, 10)}
    return {
        'contract': CONTRACT, 'schema': 1, 'note': NOTE,
        'items': items,
        'new_ids': list(items),
        'smelting': smelting, 'carving': carving, 'pickaxe_recipes': pick_rec,
        'retired': retired,
        'conversion': {
            'map': {o: v['to'] for o, v in retired.items()}, 'ratio': '1:1 그 자리에서 id 만 (칸·개수 그대로)',
            'rule': 'ingot 칸 옛 재료 → 그 층 장비 레시피가 가장 많이 쓰는 금속의 광석 · monster 칸 → 새 몬스터 재료 (T §5, 금속은 새 규칙으로 다시 정함)',
            'where': ['ItemMigration036 은 PDC 의 원래 item_id 를 먼저 본다 (defOf() 로 거르지 않음 — R §2-7)', '접속: 가방·엔더 상자',
                      '보관함(상자·통·셜커·수레·호퍼 등) 열 때', '줍기·손에 들기', '셜커 상자·꾸러미 안 (겹친 것까지)',
                      '액자·갑옷 거치대·바닥 아이템: EntitiesLoadEvent', '판매 바구니·대장간 창: 닫을 때 돌려받은 뒤 위 규칙'],
            'equal_to_fresh': '결과는 ItemService 로 새로 만든 아이템과 isSimilar (겹쳐짐) — 시험',
            'guard': '새 id 가 지금 content 에 없으면 바꾸지 않고 시작 때 경고 1줄 · 두 번 해도 같음 · 모르는 id 그대로',
            'pack_alias': '팩은 옛 8개 id 를 새 그림으로 가리키는 별칭을 두 판(0.3.6·0.3.7) 남긴다',
            'pre_release': {d['pre_release']: k for k, d in P.DROP_PARTS.items() if d.get('pre_release')},
            'pre_release_note': '배포 전 시험 서버에만 있던 id (Q0 계약 첫 판의 잿불 가죽) — ItemMigration036 이 같이 바꾼다',
            'notice': {'ext': 'mat036.notice', 'text': '<gray>광산이 열렸습니다. 녹슨 철괴·슬래그 주괴 같은 광물 재료는 광석으로, 불씨 조각·프리즘 가루·태엽 용수철은 새 몬스터 재료로 바뀌었습니다. 광석은 제련소나 광산 관리소에서 주괴로 녹이세요.</gray>'}},
        'generator_rules': {
            'owner': 'Q3 (tools/gen_036_materials.py — gen_035_content.generate() 안의 메모리 단계, R §3-18)',
            'metal_choice': {
                'rule': '장비의 힘 P = 단계(tier) + rarity_step[희귀도] + (보스 장비면 boss_step). 자리 pos = clamp(1 + (P − 1)/2, 1, 6). '
                        '소수부 f < mix_band[0] → 아래 금속만, f > mix_band[1] → 윗 금속만, 그 사이(양끝 포함) → 이웃 두 금속 섞음 (윗 금속 개수 = 반올림(n·f), 둘 다 1 이상). pos = 6 → 오리하르콘만',
                'rarity_step': P.RARITY_STEP, 'boss_step': P.BOSS_STEP, 'mix_band': list(P.MIX_BAND),
                'not_a_band_table': True, 'examples_n10': ex},
            'ing_share': P.ING_SHARE, 'min_ing': P.MIN_ING,
            'ingot_count': '반올림(옛 일반 재료 개수 합 × ing_share), 최소 min_ing — 옛 일반 재료 = 그 층 몬스터 재료 + 광물 재료',
            'placement': '주괴는 몬스터 재료 바로 뒤 (정예 재료·정수·핵 앞), 섞을 때 아래 금속 먼저. 몬스터 재료 개수·골드는 그대로. 레벨 조건을 새로 넣지 않음',
            'monster_slot': '몬스터 칸 옛 재료 → 새 몬스터 재료 (개수·확률 그대로)',
            'loot': ['주괴 칸 옛 재료의 {item} 항목은 지운다 (확정 항목 포함)', 'one_of 안의 주괴 칸 옛 재료는 목록에서 뺀다 (남은 재료가 몫을 나눔)',
                     '몬스터 칸 옛 재료 → 새 몬스터 재료로 이름만', '강화석 표·정수·장비 표는 그대로'],
            'dungeon_ore': {'rule': 'R §3-10 — 모든 층. 그 층 1회(솔로) 기대 광석 = per_run[층], 금속 비율 = metals[층] (그 단계 장비 레시피의 주괴 수요 비율, 15% 미만 뺌, 최대 2종), '
                                    '집 비율 split. 각 테이블의 guaranteed 에 {item: 광석, chance, amount} 확률 항목으로 넣는다 (기대 0.6 넘으면 amount 를 올림)',
                            'per_run': proto['dungeon_ore_target'], 'metals': proto['floor_metals'], 'split': P.DUNGEON_ORE_SPLIT,
                            'homes': {'mob': '그 층 일반 몹 drops', 'elite': '그 층 정예 drops', 'boss': '그 층 보스 drops', 'chest': 'treasure_floor_N · gimmick_floor_N'},
                            'share_of_kit': P.DUNGEON_ORE_SHARE, 'tolerance': 0.1},
            'enhance': {'owner': 'Q3 (tools/gen_enhance.py)',
                        'P': '그 장비의 몬스터 재료 (레시피에서 가장 많이 드는 몬스터 재료 / 드롭 장비는 HARD 표)',
                        'S': '그 장비의 주 금속 주괴 (레시피면 가장 많이 드는 주괴, 같으면 윗 금속 · 드롭 장비는 primary_metal(힘)). 개수 = 반올림(S_BASE × P 공급 배율 × ingot_unit), 최소 1',
                        'R_K': '그대로 — 정예 재료·정수·보스 핵 (던전 몫)',
                        'swap': '몬스터 재료가 둘인 층(1·3·4·8·10) = 다른 몬스터 재료를 P 로 / 하나인 층(2·5·6·7·9) = 주괴를 P 로 (P 주괴 개수 × ingot_unit, S 는 몬스터 재료)',
                        'hard': {2: 'spider_silk', 5: 'ember_soul', 6: 'grave_bone', 7: 'resonant_sinew', 9: 'clock_oil'},
                        'drops_stage': {'rule': '몹 주제 드롭 단계 뒤 (§0 결정 4 · drops_spec §8): 드롭 장비의 P = 단단한 장비 hard · 부드러운 장비 soft '
                                                '(방어구는 겉모습 — 판금·방패 단단, 천 부드러움, 가죽은 슬롯). 겹치면 레시피의 다른 부위 → 그 층 반대쪽 부위 → '
                                                '(부위 하나뿐인 7층만) 주괴를 P. R 은 지금 enhance.yml 의 것을 먼저. S 주괴 개수 = 반올림(S_BASE × ingot_s_scale[층]), '
                                                'p_scale 아래 한도 0.25',
                                        'hard': P.ENH_HARD, 'soft': P.ENH_SOFT,
                                        'ingot_s_scale': '0.5 × p_scale(재료 단계 뒤 그 층 몬스터 재료 1회 공급 중 큰 값)'},
                        'ingot_unit': P.INGOT_UNIT,
                        'ingot_supply': '주괴 1회 공급량(환산 비교·보스 장비 검사) = 그 금속 곡괭이로 그 금속만 노릴 때 1분당 광석 × 그 층 1회 클리어 분 ÷ 2'},
            'sources': {'kinds': {'mine': '광산', 'smelt': '제련소'}, 'source_order_after': 'hoard',
                        'compute': 'compute_sources 를 036 적용 뒤 최종 루팅으로 다시 돌림 (광석의 drop·elite·boss·chest 는 루팅에서)'},
            'items_yml': {'ore_ingot_gem': {'type': 'material', 'mine_level': '등급 1~6 (mine.json ores/gems tier 와 같아야 함)', 'mine_kind': 'ore | ingot | gem', 'floor': '비움'},
                          'tool': {'type': 'tool', 'tool': '{kind: pickaxe, tier, speed: {광석 tier: 배율}, bonus}', 'level_req': '적지 않음 (레벨 조건 없음)'}},
            'checks': ['NoRetiredIds', 'GearRecipeIngot (금속 = 힘 규칙, 이웃 두 금속까지)', 'MineLadder (제련 6 · 곡괭이 사다리 · 레벨 조건 없음)', 'SellMine',
                       'EnhanceIngot', 'DungeonOrePerRun (±10%)', 'NoLevelLabels (광석·주괴·곡괭이·광산 글에 Lv·층 번호·단계 없음)'],
            'verify_first': '0.3.5 verify 를 036 단계 앞에서 돌린다 (R §3-18)'},
        'sell': {'config': {'sell': {'mine': dict(P.SELL_MINE)}},
                 'formula': '값 = 반올림(base × (1 + rank_bonus × (mine_level − 1))), 최소 1 · mine_kind 로 종류 · 도구(type tool)는 못 팜 ("도구는 팔 수 없습니다.")',
                 'table': {str(m['rank']): {'ore': P.sell_value('ore', m['rank']), 'ingot': P.sell_value('ingot', m['rank']),
                                             'gem': P.sell_value('gem', m['rank']), 'smelt_gold': m['smelt_gold']} for m in P.METALS},
                 'rule': '녹여 팔면 언제나 손해: 주괴 값 < 광석 2개 값 + 제련 골드'},
        'starter_kit': {'add': {'item': 'copper_pickaxe', 'amount': 1}, 'config': 'config.yml starter_kit (Q3)'},
        'codex': {'groups_order': ['보스', '정예', '몬스터·상자', '보물 상자', '시련방', '특별 시련', '금고·미믹', '광산', '제련소', '대장간', '상인', '칭호 보상', '시작 지급', '몬스터'],
                  'colors': {'광산': '#d9a066', '제련소': '#ff9a5a'},
                  'mine_line': '광산 · 많이 나는 곳: <층 이름 둘> (mine.json 무게가 가장 큰 두 곳) — 층 번호·Lv·단계 글자 없음',
                  'smelt_line': '제련소 <재료 ×n>, <골드>G (레시피 amount 가 2 이상이면 끝에 "(n개)")',
                  'pickaxe_line': '캘 수 있는 것: <광석·보석 이름들> · 속도 ×<speed> · 광석 덤 <bonus%> (레벨 줄 없음)',
                  'enhance_source': '광석·보석 "광산", 주괴 "제련소"',
                  'dungeon_line': '광석의 던전 획득처 줄도 층 숫자 없이: CodexMenu 재료 경로가 붙이는 "(9층)"·"지하 9·10층" 을 mine_kind 아이템에는 쓰지 않는다 '
                                  '(장비처럼 종류 이름만 — "몬스터·상자에서 조금")'},
        'drops_reserved': {'spec_dir': 'design036/drops/ (따로 설계 — drops_spec.md·json 있음, 이 계약이 앞선다)', 'owner': 'Q3',
                           'applies': 'materials 규칙 다음 단계로 (gen_036_materials → drops) — 같은 generate() 안',
                           'may_add': ['몹 주제 드롭 재료 id', '상자 모양 미믹 관련 루팅'],
                           'must_keep': ['이 파일의 금속·보석·곡괭이 id 와 규칙', 'mine.json', 'ING_SHARE·던전 광석 per_run (바꾸려면 Q0 계약을 고친다)',
                                         '새 몬스터 재료 3개 id·이름 (ember_soul 불씨 혼 · resonant_sinew 공명 힘줄 · clock_oil 태엽 기름 — §0 결정 4)',
                                         '몹 몸에 맞는 새 부위 6 (drop_parts — §0 결정 4)',
                                         '옛 8개 바꿈 표 conversion.map (§0 결정 4 로 불씨 조각 → 불씨 혼)'],
                           'drop_parts': list(P.DROP_PARTS),
                           'known_conflicts': ['drops_spec 은 옛 T(5금속) 위에서 만들어짐: 거기 적힌 옛 금속 광석(T 의 가장 높은 금속 포함) → 그 층 dungeon_ore.metals 의 금속으로 읽는다',
                                               '§0 결정 4 (주인 늦은 결정): 드롭 명세가 재료 id 를 정한다 — 잿불 가죽(cinder_hide) → 잿불 비늘(cinder_scale), '
                                               '불씨 조각 → 불씨 혼(ember_soul) 을 이 계약에 넣었다',
                                               'LootRoller 는 guaranteed 의 chance 를 보지 않는다 (늘 지급) — 던전 광석 확률 항목은 entries 맨 끝에 둔다 '
                                               '(content_p3 loot_tweaks 번호 그대로)']},
        'derived': {'recipes_changed': proto['recipes_changed'], 'mixed_recipes': proto['mixed_recipes'],
                    'single_metal_recipes': proto['single_metal_recipes'],
                    'ingots_by_tier': {str(t): v['ingots'] for t, v in proto['by_tier'].items()},
                    'ingots_all_recipes_once': proto['ingots_all_recipes_once'],
                    'loot': proto['loot'], 'enhance': proto['enhance'], 'recipes_total_after': 187 + len(P.METALS) + len(P.STONE_RECIPES) + len(P.PICK_RECIPES)},
        'economy': {'source': 'tools/data/036/model/out/economy.json · CONTRACT.md §5'},
    }


# ───────────────────────── visual.json ─────────────────────────
ICONS = {
    'copper_ore': ('ore_patina', ['#1f1915', '#3d322a', '#62554a', '#8a7b6e', '#ea8a46'], False),
    'iron_ore': ('ore_nugget', ['#1c1c20', '#393a41', '#5e6069', '#8a8d96', '#e0b08c'], False),
    'silver_ore': ('ore_flake', ['#15161d', '#2c2e39', '#4c505e', '#727788', '#f2f6ff'], False),
    'gold_ore': ('ore_star', ['#1c1b1a', '#383632', '#5d5a54', '#8a867e', '#ffcf3a'], False),
    'mithril_ore': ('ore_crystal', ['#10151e', '#202b3b', '#38495f', '#5b7089', '#a6f2ff'], False),
    'orichalcum_ore': ('ore_ember', ['#120806', '#2a140e', '#4a2418', '#6e3622', '#ff8a5c'], True),
    'copper_ingot': ('ingot_patina', ['#3a190c', '#783818', '#bd6630', '#f2a462', '#3fb090'], False),
    'iron_ingot': ('ingot_bar', ['#1e2128', '#3c424d', '#646c79', '#9aa3b0', '#5a6270'], False),
    'silver_ingot': ('ingot_shine', ['#4a5060', '#8a92a4', '#d0d6e2', '#ffffff', '#9ccaff'], False),
    'gold_ingot': ('ingot_bar', ['#4a3208', '#8a6014', '#d9a52a', '#ffe07a', '#b07a10'], False),
    'mithril_ingot': ('ingot_rune', ['#1d3848', '#3e6f88', '#7ec4d8', '#dafcff', '#7ff2ff'], False),
    'orichalcum_ingot': ('ingot_star', ['#2a0e06', '#5a2010', '#a8442a', '#ff9a6a', '#3a1408', '#ffd86e'], False),
    'quartz': ('gem_prism', ['#7a756f', '#b5afa8', '#e7e3dd', '#ffffff', '#fffaf0'], False),
    'garnet': ('gem_round', ['#22040c', '#5a0a1c', '#a01830', '#f04a5e', '#c8102e'], False),
    'moonstone': ('gem_cabochon', ['#59607a', '#a0aac0', '#dfe6f2', '#ffffff', '#6f9cff'], False),
    'topaz': ('gem_shard', ['#3a2404', '#7a4e08', '#d9940f', '#ffd45a', '#ffb21a'], False),
    'sapphire': ('gem', ['#060c2e', '#122a78', '#2e5ad8', '#8fb4ff', '#4a7cff'], False),
    'dragonblood_stone': ('gem_drop', ['#1a0204', '#4a060c', '#a0121c', '#ff4a3a', '#ffb04a'], True),
    'ember_soul': ('shard', ['#1a0a06', '#5a1a0a', '#c43c12', '#ff9a2a', '#fff0a0'], False),   # 옛 불씨 조각 그림 (drops_spec 검토 §2-4)
    'resonant_sinew': ('sinew', ['#24162a', '#553858', '#956896', '#d8b2d8', '#c49cff'], False),
    'clock_oil': ('oil_flask', ['#050608', '#11161b', '#1d2731', '#2f3d4a', '#1a2028', '#7ae0c0'], False),
}
# 0.3.5 icons.py 에 이미 있는 모양 (새 모양 목록에서 뺀다)
OLD_ICON_STYLES = {'gem', 'shard', 'scale', 'fang', 'dust'}
PICKS = {
    'copper_pickaxe': ('copper', ['#3a190c', '#783818', '#bd6630', '#f2a462', '#3fb090'], False, None, 380,
                       '한쪽 뾰족·한쪽 끌, 녹청 점, 나무 자루'),
    'iron_pickaxe': ('steel', ['#1e2128', '#3c424d', '#646c79', '#9aa3b0', '#7a5a30', '#d9a54e'], False, None, 380,
                     '양날 대칭, 쇠띠·리벳, 가죽 손잡이'),
    'silver_pickaxe': ('silver', ['#4a5060', '#8a92a4', '#d0d6e2', '#ffffff', '#6f9cff'], False, None, 380,
                       '긴 양날, 은 테두리, 월장석 보석'),
    'gold_pickaxe': ('gold', ['#4a3208', '#8a6014', '#d9a52a', '#ffe07a', '#7a4a20', '#ffd24a'], False, None, 450,
                     '넓은 양날, 금 테두리, 황옥 보석, 짙은 나무 자루에 금 고리'),
    'mithril_pickaxe': ('crystal', ['#1d3848', '#3e6f88', '#7ec4d8', '#dafcff', '#4a7cff'], False, None, 520,
                        '결정 날끝·룬 띠(빛남), 쇠 자루'),
    'orichalcum_pickaxe': ('ember', ['#2a0e06', '#5a2010', '#a8442a', '#ff9a6a', '#3a1408', '#ffd86e'], True, 'ember_glow', 720,
                           '초승달 양날, 붉은 금 테, 용혈석 보석, 떠다니는 불티 조각, ember_glow 반짝임 + 날 오라 겹'),
}


def build_visual():
    lv = {}
    for L in P.LEVELS:
        lv[str(L['n'])] = {'id': L['id'], 'name': L['name'], 'title_color': L['color'], 'biome': L['biome'], 'biome_y': L['biome_y'],
                           'light': L['light'], 'palette': L['palette'], 'depleted_block': L['depleted'], 'regen_fx':
                           {'particle': L['regen_fx'], 'count': 6, 'spread': 0.25, 'sound': 'BLOCK_AMETHYST_BLOCK_CHIME', 'volume': 0.35,
                            'pitch': round(0.9 + 0.1 * L['n'], 2)}, 'mood': L['mood']}
    icons = {}
    for i, (style, pal, new) in ICONS.items():
        icons[i] = {'style': style, 'palette': pal, 'new_style': new, 'shape': 'icon', 'size': P.ICON_SIZE}
    for i, d in P.DROP_PARTS.items():   # 몹 주제 새 부위 (§0 결정 4) — 0.3.5 아이콘 모양 그대로
        icons[i] = {'style': d['style'], 'palette': d['palette'], 'new_style': False, 'shape': 'icon', 'size': P.ICON_SIZE}
    picks = {}
    for i, (style, pal, anim, eff, budget, look) in PICKS.items():
        picks[i] = {'template': 'pickaxe', 'style': style, 'palette': pal, 'animated': anim, 'effect': eff, 'element_budget': budget,
                    'look': look, 'display': 'displays.voxel_weapon'}
    return {
        'contract': CONTRACT, 'schema': 1, 'note': NOTE,
        'blocks': {
            'ores': {o: {'block': b, 'why': P.BLOCK_WHY[o]} for o, b in P.ORE_BLOCK.items()},
            'gems': {g: {'block': b, 'why': P.BLOCK_WHY[g], 'natural': P.GEM_BLOCK_NATURAL[b], 'look': P.GEM_BLOCK_LOOK[g],
                         'model': f'labyrinth:block/mine/gem_{g}', 'texture': f'labyrinth:block/mine/gem_{g}',
                         'was_036': P.GEM_BLOCK_036[g]} for g, b in P.GEM_BLOCK.items()},
            'depleted': {str(L['n']): L['depleted'] for L in P.LEVELS},
            'forbidden': P.FORBIDDEN_BLOCKS,
            'rules': ['광석·보석 블록 12개는 서로 모두 다름 (Tool 규칙이 블록 종류마다 하나 · 층이 섞여 종류마다 블록이 하나)',
                      'lit/powered 상태(레드스톤 광석)·떨어지는 블록·블록 엔티티·정육면체 아닌 블록 안 됨',
                      '광석·보석·빈 광맥 블록은 광산 어느 층 장식·벽·바닥에도 쓰지 않음 (캐지는 것처럼 보이면 헷갈림)',
                      '빈 광맥 블록은 그 층 벽·바닥 재료와 다름 (캔 자리가 길잡이)',
                      '청사진은 @vein:<광석 id> · @gem:<보석 id> 논리 글자 — 블록을 바꿔도 청사진은 그대로',
                      '0.3.6.1: 팩은 보석 블록 6개의 모습만 바꿈 — assets/minecraft/blockstates/<블록>.json 6개 → labyrinth:block/mine/gem_<보석> '
                      '(cube_all, 16×16 그림). 그 밖 blockstates·models/block·textures/block 0개, 바닐라 광석 그림은 하나도 안 바꿈',
                      '보석 블록 6개는 미궁 층(floors.yml)·마을 조각·광산 장식·구역 조각·배포 월드 지형 어디에도 없어야 함 (바꿔도 다른 곳 모습이 안 바뀜)',
                      '구역 건물의 구리는 모두 waxed_*'],
        },
        'levels': lv,
        'icons': icons,
        'new_icon_styles': sorted({v[0] for k, v in ICONS.items()} - OLD_ICON_STYLES),
        'icon_styles_new_in_q0': sorted(s for s, _, new in ICONS.values() if new),
        'icon_source': 'design036/tools/vis_new_styles.py draw_new (16 모양 — hide 는 §0 결정 4 로 빠짐) + Q0 가 더한 ore_ember·gem_drop (Q4 가 그림) · 몹 주제 새 부위 6 은 0.3.5 모양',
        'palette_rule': '0.3.5 Palette: 끝 강조색이 본 램프보다 밝으면 본 램프에 섞인다. 강조색만 쓰려면 그 앞에 어두운 색 하나를 끼운다',
        'pickaxes': picks,
        'gem_blocks': {'removed_036': '0.3.6 보석 결정 ItemDisplay (튀어나온 결정, labyrinth:mine_node PDC) — 0.3.6.1 에서 없앰. 남은 것은 시작·층 짓기·30초 정리 때 지움',
                       'asset_paths': ['assets/minecraft/blockstates/<블록>.json', 'assets/labyrinth/models/block/mine/gem_<보석>.json',
                                       'assets/labyrinth/textures/block/mine/gem_<보석>.png'],
                       'texture': {'size': 16, 'style': '바닐라 광석처럼: 광산 벽 돌 바탕(look.base) + 보석 색 알갱이·조각 (look.style · look.palette)',
                                   'bases': ['stone', 'tuff', 'deepslate', 'basalt']},
                       'migration': '청사진 지문에 블록이 들어 있어 jar 를 바꾸면 모든 층을 다시 짓는다 (옛 보석 블록 자리 = 새 블록)'},
        'feedback': {
            'too_weak': {'trigger': 'PlayerAnimationEvent ARM_SWING + 5칸 시선', 'actionbar': '<red>' + P.OWNER['too_weak_actionbar'] + '</red>', 'throttle_ms': 1000},
            'dig': 'vanilla (Tool 규칙 + CAN_BREAK) — 금 가는 10단계·그 블록 소리',
            'resend': '취소한 칸만 1틱 뒤 (R §2-13)',
            'harvest': {'actionbar': '<{ore_color}>+{n} {광석}</{ore_color}> <gray>(가방 {count})</gray>', 'sound': ['ENTITY_ITEM_PICKUP', 0.3, 1.4],
                        'bonus': '<gold>+{n}</gold>', 'rich': '<gold>풍부한 광맥! ×3</gold>', 'gem': '<{gem_color}>✦ {보석}!</{gem_color}>',
                        'pop': {'config': 'mine.fx.pop', 'default': True, 'scale': 0.4, 'ticks': 8, 'teleport_duration': 6, 'visible': 'miner_only'}},
            'bag_full': '<red>가방이 가득 찼습니다</red>',
            'lift': {'effect': 'BLINDNESS 40틱', 'sounds': [['ENTITY_MINECART_RIDING', 0.6, 0.8], ['BLOCK_CHAIN_PLACE', 0.5, 0.7]],
                     'arrival_subtitle': '<{title_color}>{이름}', 'no_level_number': True},
            'colors_by': '광석·보석 색 = mine.json ores/gems color (층 색이 아님 — 층이 섞여서)'},
        'npcs': {
            'rule': '기존 NPC 스킨과 같은 그림 수준: resourcepack/src/npc_skins.paint_skin 그대로, outfit·hair·accessories 는 GDD §14.5 닫힌 목록만. '
                    '눈 크게·잔무늬 많게 다시 그리지 않음 (주인이 거절함)',
            'miner': {'name': P.OWNER['miner_npc_name'], 'nameplate': '<gradient:#e8843f:#f0b050>[광부]</gradient>', 'skin': 'miner',
                      'skin_style': {'palette': ['#c98e6b', '#3a2a20', '#4a5866', '#8c6a44', '#f0b050', '#2a2a2a'], 'outfit': 'miner',
                                     'hair': 'short_beard', 'accessories': ['helmet_lamp', 'tool_belt', 'soot_marks']},
                      'differs_from': 'lore_floor2_miner 토브 (bandage_arm·갈색 옷) — 푸른 회색 작업복·연장 띠'},
            'smelter': {'name': P.OWNER['smelter_npc_name'], 'nameplate': '<gradient:#ff9a5a:#3fb090>[제련공]</gradient>', 'skin': 'smelter',
                        'skin_style': {'palette': ['#d9a882', '#2a3a3a', '#5a3121', '#8c5a34', '#ff9a5a', '#3fb090'], 'outfit': 'apron',
                                       'hair': 'bun', 'accessories': ['goggles_forehead', 'thick_gloves', 'tool_belt']},
                        'differs_from': '대장장이 두르간 (수염·짧은 머리) · 견습 미라 (쌍둥이 쪽머리) — 올림머리·녹청 눈·연장 띠'}},
        'menus': {'smelter': {'glyph': 'gui_smelter', 'rows': 6, 'motif': '대장간 틀 + 화덕 불빛 띠, 탭 제련/새기기/곡괭이, ×1·×8·전부 단추'},
                  'mine_lift': {'glyph': 'gui_mine_lift', 'rows': 6, 'motif': '세로 갱도 그림, 층 단추 6개(층 색) + 마을 — 잠김 쇠사슬 없음'},
                  'mine_office': {'glyph': 'gui_mine_office', 'rows': 6, 'motif': '갱도 나무 틀 + 등불, 탭 곡괭이/제련/새기기/벼리기/팔기/현황'},
                  'mine_shop': {'glyph': 'gui_merchant (재사용)'}},
        'district_style': {
            'theme': '마을 공통 재료(VILLAGE.md §5) + 구역 주제색 녹청 구리 #3FB090 · 구리 주황 #E8843F · 흑암, 따뜻한 등불',
            'mine_headframe': '석재·심층암 벽돌 아래층, 심층암 기와 박공 + 구리 용마루, 벗긴 짙은 참나무 탑 + 엇갈린 울타리 버팀, 권양 바퀴, 구리 창살 승강기 칸 + 쇠사슬',
            'smelter': '흑암 벽돌 작업장 + 짙은 참나무 뼈대·회반죽 2층 + 녹청 구리 지붕 + 벽돌 굴뚝(모닥불 연기). 크기 13×18×12 (V)',
            'miners_lodge': '가문비·짙은 참나무 뼈대 + 회반죽, 심층암 기와 + 녹슨 구리 테, 게시판, 곡괭이 걸이',
            'ore_yard': '레일, 원석 블록 더미, 울타리 기중기 + 쇠사슬 + 등불, 통 더미 (장식 — 광산 광석 블록은 쓰지 않음)',
            'street': '가로등 = 짙은 참나무 울타리 기둥 + 구리 등불(초록 불꽃), 광산 마당 길 = 조약돌·안산암·자갈·응회암 섞기',
            'banned': '구역 장식에 광산 광석·보석 블록 12종 쓰지 않음 (헷갈림) — 원석 블록(raw_*_block)은 됨'},
        'pack_rules': ['새 아이콘 21개 (광석 6·주괴 6·보석 6·새 몬스터 재료 3) + 곡괭이 3D 6개 + 보석 블록 그림 6개 (0.3.6.1, 결정 모델 없음)', '옛 8개 id 는 새 그림 별칭 두 판',
                       '곡괭이 요소 예산 380/380/380/450/520/720', 'blockstates 6개(보석 블록) + labyrinth models/block·textures/block mine/gem_* 6개씩, 그 밖 0개',
                       '메뉴 배경 gui_smelter·gui_mine_lift·gui_mine_office (glyphs.yml + ui.py)',
                       f'평면 아이콘 {P.ICON_SIZE}×{P.ICON_SIZE} 손그림 (resourcepack/src/pixel_icons, 0.3.6.2) — 곡괭이는 3D 복셀 그대로'],
    }


# ───────────────────────── district.json ─────────────────────────
def expand(b, k):
    return [b[0] - k, b[1] - k, b[2] + k, b[3] + k]


def path_box(p):
    (x0, z0), (x1, z1) = p['points'][0], p['points'][-1]
    h = p['width'] // 2
    return [min(x0, x1) - h, min(z0, z1) - h, max(x0, x1) + h, max(z0, z1) + h]


def build_district():
    boxes = [p[3] for p in D.PIECES] + [path_box(p) for p in D.PATHS]
    R, B = D.MASK['R'], D.MASK['B']
    bb = [min(b[0] for b in boxes) - R - B, min(b[1] for b in boxes) - R - B, max(b[2] for b in boxes) + R + B, max(b[3] for b in boxes) + R + B]
    pieces = [{'piece': pid, 'name': name, 'size': size, 'box': box, 'front': front, 'kind': kind, 'markers': marks}
              for pid, name, size, box, front, kind, marks in D.PIECES]
    sites = []
    for s in D.SITES:
        e = dict(s)
        if s['shift'] is not None:
            dx, dz = s['shift']
            e['protect_xz'] = [[b[0] + dx, b[1] + dz, b[2] + dx, b[3] + dz] for b in (p['box'] for p in pieces)]
            e['mask_bbox'] = [bb[0] + dx, bb[1] + dz, bb[2] + dx, bb[3] + dz]
            e['npc_spots'] = {k: [v['spot_east'][0] + dx, v['spot_east'][1] + dz] for k, v in D.NPCS.items()}
        sites.append(e)
    return {
        'contract': CONTRACT, 'schema': 1, 'note': NOTE,
        'name': '광산 마을', 'id': 'mine', 'world_shipped': D.WORLD,
        'pieces': pieces, 'paths': D.PATHS,
        'npcs': {k: {**v, 'name': P.OWNER['miner_npc_name'] if k == 'miner' else P.OWNER['smelter_npc_name']} for k, v in D.NPCS.items()},
        'interact': {'mine_lift': 'mine_headframe', 'smelter': 'smelter', 'mine_info': 'miners_lodge'},
        'markers_new': {'mine_exit': 'mine_headframe', 'ambient dust': 'mine_headframe', 'ambient embers': 'smelter'},
        'sites': sites,
        'mask': {**D.MASK, 'bbox_east': bb, 'cells_note': 'Q2 가 정확한 칸 수를 계산 (M 시안: 다듬는 칸 2,976)'},
        'protect': {'boxes': 'pieces[].box (x·z) × y [다듬은 바닥 − 3, 바닥 + 높이 + 2] — 계획기가 바닥을 정한 뒤 메타에 적음',
                    'include_paths': False, 'while_building': '짓는 동안 그 상자 놓기·부수기 취소, 들어오는 사람 밀어냄 (R §2-5)'},
        'zones': {'pvp_safe': 'VillageZone 원 + 구역 보호 상자 (각 상자 + 8칸) — 승강장·제련소 앞 PvP 안 됨 (R §2-2)',
                  'wild_border': 'WildBorder.compute 의 보호 상자에 구역 상자를 더함 (east·south_east 어느 쪽이든 지은 자리) — 경계가 저절로 넓어짐',
                  'hostile_spawn': '구역 중심 반경 R+8 안 적대 몹 스폰 막음'},
        'apply_existing_world': {
            'when': 'VillageService 가 마을 메타를 읽은 뒤, <월드>/labyrinth-district-mine.yml 이 없고 mine.district.auto_build: true 면 시작 5초 뒤 한 번',
            'steps': ['1 자리 후보 차례로 (east → south_east): ChunkSnapshot 비동기 조사, 마스크 안',
                      '2 지문 비교 (아래 fingerprint) + 비자연 블록(Nature.kind UNNATURAL, 땅 위 전부 + 땅속 10칸) + 지표 물·용암·얼음 + 깎기/메우기 4칸 넘음 → 막음',
                      '3 얼린 칸 (막지 않음, 높이·지형을 바꾸지 않음 — 깎기·메우기·나무 치우기 없음): 마을 보호 상자 · 마을 길 칸 · 마을이 다듬은 칸(meta.terrain) — R §2-5. '
                      '구역 길이 얼린 칸을 지나면(큰길 끝 x −103..−101) 겉 블록만 길 블록으로 깐다. 마을 길 칸·보호 상자 안은 겉 블록도 그대로',
                      '4 엔티티 (주 스레드): 갑옷 거치대·액자·그림·수레·보트·끈 매듭·이름표/길들인 동물·주민 → 막음. 그냥 다니는 동물은 조각 상자 밖으로',
                      '5 통과 → 바꿀 칸 원래 블록을 백업에 먼저 → state: building → 나무·지형·조각·길·표지판 (틱 분할) → state: built · NPC 2명',
                      '6 그 자리 플레이어는 짓기 전에 마을 광장으로 (메시지)',
                      '7 모든 후보 막힘 → 블록 0칸 바꿈, district-mine-blocked.txt 에 이유·좌표 20개, 관리자 접속 때 하루 한 번 안내. 광산은 관리소로 그대로'],
            'idempotent': 'state: built 면 다시 안 지음. building 으로 꺼졌으면 다음 시작 때 백업으로 되돌린 뒤 처음부터',
            'rollback': '/labadmin village district remove mine — 지금 블록 = 우리가 놓은 블록인 칸만 되돌리고 나머지 수 보고',
            'village_build_id': '마을 build_id 그대로 (오래 한 플레이어가 광장으로 다시 옮겨지지 않게). 구역 NPC 적용 열쇠는 village-applied.yml districts.mine',
            'selftest_after': '짓고 나서 마을·구역 자가 진단 두 줄이 모두 깨끗해야 함'},
        'fingerprint': {
            'file': 'jar village/districts/mine.fp (tools/village/district_fingerprint.py, 두 배포 world.zip 에서)',
            'per_column': ['땅 높이 h (움직임을 막는 잎 아닌 가장 높은 블록)', 'h−10 ~ h+30 블록 해시 (정규화: 잔디·흙·거친 흙·회백토 = 흙, 꽃·풀·고사리·눈 층 = 공기)',
                           '원목 자리 목록'],
            'columns': '모든 자리 후보(east·south_east)의 마스크 (R+B) 칸',
            'human_if': ['|지금 h − 지문 h| > 2', '땅속(h−10..h−1)에 지문에 없던 공기·물', '지문에 없던 원목·나무', 'Nature UNNATURAL 블록'],
            'allowed': ['잔디 ↔ 흙', '꽃·풀·고사리 생김/없어짐', '눈 층', '잎 (원목이 그대로면)'],
            'two_worlds': '먼저 두 배포 월드의 마스크 지형이 같은지 본다. 다르면 build_id 마다 지문을 따로 두고 어느 쪽이든 맞으면 통과',
            'unknown_world': '배포 월드가 아니면(시드·마을 메타가 다름) 지문 없이 M 의 비자연 검사만 + 관리자에게 미리보기 권함'},
        'backup': {'file': '<월드>/labyrinth-district-mine.backup.gz', 'first': True, 'format': 'Q2 가 정함 (칸 좌표 + BlockData 문자열)'},
        'meta': {'file': '<월드>/labyrinth-district-mine.yml', 'fields': 'VillageMeta 와 같은 것 (pieces·paths·protect·npcs·interact·ambient·terrain·build_id) + state·site·backup'},
        'world_zip': {'build': 'build_world.sh --base <예전 world.zip> → 서버 켜고 village district build mine east → village selftest → zip',
                      'rules': ['random_tick_speed 0 · 몹 스폰 끔 (R §3-19)', '마을 selftest mismatched=0', 'skip_dirs 에 dimensions/minecraft/labyrinth_mine',
                                'release.sh: labyrinth_mine 이 zip 에 있으면 실패']},
        'selftest_line': names()['selftest']['district'],
        'checks': ['조각 상자 + 1칸 겹침 0', '마을 보호 상자와 3칸 이상 (x ≥ −100)', '제련소 13×18×12 로 다시 계획 (R §3-20)', 'junction: 큰길 끝 칸과 구역 길 첫 칸 높이 차 ≤ 1'],
    }


def write_all(check):
    lay, proto, eco = load('layout.json'), load('proto036.json'), load('economy.json')
    out = {'mine.json': build_mine(lay, eco), 'materials.json': build_materials(proto, eco), 'visual.json': build_visual(),
           'district.json': build_district()}
    bad = 0
    for name, data in out.items():
        text = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
        p = DATA / name
        if check:
            if not p.exists() or p.read_text(encoding='utf-8') != text:
                print('다름:', p)
                bad += 1
        else:
            p.write_text(text, encoding='utf-8')
            print('썼음:', p, len(text), 'B')
    return bad


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    sys.exit(1 if write_all(a.check) else 0)
