"""게임 콘텐츠 정의 — 캐릭터·속성·배너·상점·스테이지.

여기 있는 값이 게임 밸런스의 단일 출처(single source of truth)다.
서버가 이 표만 보고 계산하므로, 클라이언트가 보낸 수치는 절대 믿지 않는다.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────── 속성 상성
# 화염 > 질풍 > 해류 > 화염  (삼각), 광휘 <-> 심연 (상호 특효)
ELEMENTS = {
    "화염": {"color": "#ff6b57", "beats": "질풍"},
    "질풍": {"color": "#5fd6a6", "beats": "해류"},
    "해류": {"color": "#5aa8ff", "beats": "화염"},
    "광휘": {"color": "#ffd257", "beats": "심연"},
    "심연": {"color": "#b47cff", "beats": "광휘"},
}
ADVANTAGE = 1.35   # 상성 우위 피해 배율
DISADVANTAGE = 0.75  # 상성 열세 피해 배율

RARITY_NAMES = {3: "R", 4: "SR", 5: "SSR"}
LEVEL_CAP = {3: 40, 4: 50, 5: 60}
# 중복 획득 시 성흔(별자국) 최대치와 단계당 능력치 보너스
MAX_ASCEND = 5
ASCEND_BONUS = 0.08
# 중복이 성흔 최대치를 넘으면 조각으로 환원
DUPE_SHARDS = {3: 10, 4: 30, 5: 120}


def _c(cid, name, title, rarity, element, role, hp, atk, dfn, spd,
       skill, kind, power, desc, prompt, palette, quote):
    return {
        "id": cid, "name": name, "title": title, "rarity": rarity,
        "element": element, "role": role,
        "base": {"hp": hp, "atk": atk, "def": dfn, "spd": spd},
        "skill": {"name": skill, "kind": kind, "power": power, "desc": desc},
        "prompt": prompt, "palette": palette, "quote": quote,
    }


# skill kind: nuke(단일 대타격) / aoe(전체) / heal(회복) / buff(공격력 증가) / shield(피해 감소)
CHARACTERS: list[dict] = [
    # ───────────────────────────────── 5★ SSR
    _c("seraphine", "세라핀", "새벽의 검성", 5, "광휘", "딜러",
       1280, 162, 88, 112,
       "여명 일섬", "nuke", 2.6,
       "단일 대상에게 공격력 260% 피해. 처치 시 즉시 한 번 더 행동한다.",
       "1girl, solo, long blonde hair, golden eyes, white and gold knight armor, "
       "holding greatsword, glowing sword, cape, sunrise backlight, cinematic lighting, "
       "detailed face, masterpiece, best quality",
       ("#ffe9a8", "#f0a93c"),
       "어둠이 짙을수록, 첫 빛은 날카롭다."),
    _c("linette", "리네트", "심해의 노래", 5, "해류", "힐러",
       1420, 118, 96, 98,
       "만조의 자장가", "heal", 1.9,
       "아군 전체를 공격력 190%만큼 회복시키고 2턴간 받는 피해를 12% 줄인다.",
       "1girl, solo, long wavy aqua hair, blue eyes, mermaid princess dress, "
       "pearl ornaments, underwater light rays, bubbles, flowing fabric, "
       "serene expression, masterpiece, best quality",
       ("#a8e4ff", "#2f7fd1"),
       "바다는 아무도 두고 가지 않아요."),
    _c("kaguya", "카구야", "달그림자 암살자", 5, "심연", "딜러",
       1150, 175, 72, 128,
       "월영 난무", "nuke", 2.35,
       "가장 체력이 낮은 적에게 공격력 235% 피해. 치명타 시 피해가 1.5배가 된다.",
       "1girl, solo, long black hair, purple eyes, dark kunoichi outfit, "
       "crescent moon background, holding kunai, night, floating hair, "
       "sharp gaze, masterpiece, best quality",
       ("#d9c6ff", "#6b3fbf"),
       "달이 보고 있어. 그거면 충분해."),
    _c("ignis", "이그니스", "홍련의 무희", 5, "화염", "광역",
       1210, 155, 78, 104,
       "화무십일홍", "aoe", 1.55,
       "적 전체에게 공격력 155% 화염 피해를 주고 2턴간 화상을 남긴다.",
       "1girl, solo, long red hair, orange eyes, dancer outfit, bare shoulders, "
       "fire particles, dancing pose, flame ribbons, dramatic lighting, "
       "masterpiece, best quality",
       ("#ffc2a8", "#e2472c"),
       "타오르지 않는 춤은 춤이 아니야."),
    _c("sylphid", "실피드", "질풍의 저격수", 5, "질풍", "딜러",
       1120, 168, 70, 135,
       "관통하는 바람", "nuke", 2.45,
       "단일 대상에게 공격력 245% 피해. 적의 방어력 30%를 무시한다.",
       "1girl, solo, short green hair, twin braids, green eyes, ranger outfit, "
       "holding longbow, wind swirl, floating leaves, sky background, "
       "confident smile, masterpiece, best quality",
       ("#c4f2dc", "#2f9b73"),
       "바람보다 빠른 건 내 화살뿐."),
    _c("arte", "아르테", "강철 성녀", 5, "광휘", "탱커",
       1720, 118, 132, 84,
       "불굴의 성벽", "shield", 0.9,
       "아군 전체에 최대 체력 90%에 비례한 보호막을 씌우고 도발한다.",
       "1girl, solo, silver hair, blue eyes, heavy holy armor, large tower shield, "
       "white cape, cathedral background, stained glass light, determined expression, "
       "masterpiece, best quality",
       ("#e6eeff", "#7a89b8"),
       "제 뒤로 오세요. 여기서부턴 제 몫입니다."),

    # ───────────────────────────────── 4★ SR
    _c("miyu", "미유", "불꽃 정비공", 4, "화염", "딜러",
       980, 122, 62, 101,
       "과열 펀치", "nuke", 2.1,
       "단일 대상에게 공격력 210% 피해. 자신의 공격력이 10% 오른다.",
       "1girl, solo, short orange hair, goggles on head, mechanic overalls, "
       "oil stains, wrench, workshop background, sparks, cheerful grin, "
       "masterpiece, best quality",
       ("#ffd8b0", "#d96a2b"),
       "고장 난 건 다 내가 고쳐. 적도 포함해서."),
    _c("yuki", "유키", "설원의 궁수", 4, "해류", "딜러",
       930, 118, 58, 108,
       "고드름 화살", "nuke", 2.0,
       "단일 대상에게 공격력 200% 피해를 주고 1턴간 속도를 20% 낮춘다.",
       "1girl, solo, long white hair, pale blue eyes, winter fur coat, "
       "holding bow, snowfall, frozen forest, breath fog, calm expression, "
       "masterpiece, best quality",
       ("#dff1ff", "#4a86b8"),
       "숨 쉬는 소리까지 얼려줄게."),
    _c("rabi", "라비", "토끼 마술사", 4, "질풍", "광역",
       900, 115, 55, 115,
       "모자 속 폭풍", "aoe", 1.25,
       "적 전체에게 공격력 125% 피해. 30% 확률로 한 번 더 발동한다.",
       "1girl, solo, pink hair, rabbit ears headband, magician outfit, top hat, "
       "playing cards flying, stage lights, wink, dynamic pose, "
       "masterpiece, best quality",
       ("#ffd6ec", "#c8478f"),
       "짠! 놀랐지? 아직 안 끝났어."),
    _c("noelle", "노엘", "수도원의 종지기", 4, "광휘", "힐러",
       1080, 96, 76, 92,
       "새벽 종소리", "heal", 1.6,
       "아군 전체를 공격력 160%만큼 회복시킨다. 체력이 가장 낮은 아군은 두 배로 회복.",
       "1girl, solo, light brown hair, braided, nun habit, white veil, "
       "holding bell, chapel interior, warm morning light, gentle smile, "
       "masterpiece, best quality",
       ("#fff0cc", "#c9a34a"),
       "종이 울리면, 다들 무사한 거예요."),
    _c("hazel", "헤이즐", "그림자 도둑", 4, "심연", "딜러",
       890, 126, 52, 122,
       "뒷골목 기습", "nuke", 2.15,
       "단일 대상에게 공격력 215% 피해. 적 체력이 절반 이하면 30% 추가 피해.",
       "1girl, solo, short purple hair, yellow eyes, thief outfit, hood, "
       "holding dagger, rooftop at night, city lights, smirk, crouching pose, "
       "masterpiece, best quality",
       ("#e0ccff", "#5d3b9e"),
       "네 지갑이랑 목숨 중에 하나만 고르라니까?"),
    _c("sora", "소라", "하늘색 검사", 4, "질풍", "딜러",
       1010, 116, 66, 106,
       "창공 삼연격", "nuke", 2.05,
       "단일 대상에게 공격력 205% 피해를 3연타로 나눠 넣는다.",
       "1girl, solo, blue short hair, blue eyes, school uniform with sword, "
       "wind blowing, cherry blossom petals, rooftop, serious expression, "
       "dynamic sword pose, masterpiece, best quality",
       ("#cfe8ff", "#3f7fc4"),
       "한 번에 안 되면, 세 번 하면 되지."),
    _c("mariel", "마리엘", "장미 기사", 4, "화염", "탱커",
       1400, 92, 108, 80,
       "가시 방벽", "shield", 0.7,
       "아군 전체에 최대 체력 70% 보호막. 보호막이 남아있는 동안 반격 피해를 준다.",
       "1girl, solo, long crimson hair, red eyes, rose knight armor, "
       "holding rapier, rose petals, garden background, noble expression, "
       "masterpiece, best quality",
       ("#ffd0d0", "#a83248"),
       "장미에 손대려면 가시부터 각오해."),
    _c("tsuki", "츠키", "달빛 무녀", 4, "심연", "보조",
       960, 104, 64, 110,
       "월광 축복", "buff", 0.45,
       "아군 전체의 공격력을 3턴간 45% 올린다.",
       "1girl, solo, long dark blue hair, red hair ribbon, miko outfit, "
       "holding ofuda, night shrine, paper lanterns, moonlight, "
       "mysterious smile, masterpiece, best quality",
       ("#d5d9ff", "#4a4f9e"),
       "달이 힘을 빌려준대요. 오늘만."),

    # ───────────────────────────────── 3★ R
    _c("ari", "아리", "견습 마법사", 3, "화염", "딜러",
       790, 92, 46, 94,
       "작은 불꽃", "nuke", 1.75,
       "단일 대상에게 공격력 175% 피해.",
       "1girl, solo, orange twintails, green eyes, apprentice witch outfit, "
       "oversized hat, holding small staff, tiny flame, library background, "
       "nervous smile, masterpiece, best quality",
       ("#ffe0c0", "#d97a3a"),
       "이, 이번엔 진짜 성공할 거예요!"),
    _c("coco", "코코", "종군 간호사", 3, "광휘", "힐러",
       860, 74, 58, 88,
       "응급 처치", "heal", 1.35,
       "아군 전체를 공격력 135%만큼 회복시킨다.",
       "1girl, solo, short pink hair, nurse uniform, red cross armband, "
       "medical bag, field tent background, kind smile, "
       "masterpiece, best quality",
       ("#ffe6ec", "#cf6f88"),
       "다치면 바로 말해요, 알았죠?"),
    _c("shion", "시온", "학생회 검사", 3, "해류", "딜러",
       820, 88, 50, 96,
       "규율의 일격", "nuke", 1.8,
       "단일 대상에게 공격력 180% 피해.",
       "1girl, solo, long black hair, glasses, student council armband, "
       "school uniform, holding bokken, classroom, stern expression, "
       "masterpiece, best quality",
       ("#d6e8f5", "#3a6f9e"),
       "규칙 위반입니다. 처분하겠습니다."),
    _c("mina", "미나", "바람 정찰병", 3, "질풍", "딜러",
       770, 90, 44, 104,
       "속사", "nuke", 1.7,
       "단일 대상에게 공격력 170% 피해. 속도가 높을수록 명중이 안정적이다.",
       "1girl, solo, short green hair, scout uniform, shortbow, "
       "forest background, alert expression, running pose, "
       "masterpiece, best quality",
       ("#d6f5e4", "#3f8f6c"),
       "적 위치 확인! 지금이야!"),
    _c("lulu", "루루", "밤의 점술사", 3, "심연", "보조",
       800, 82, 48, 98,
       "예언의 속삭임", "buff", 0.28,
       "아군 전체의 공격력을 3턴간 28% 올린다.",
       "1girl, solo, purple bob hair, fortune teller outfit, crystal ball, "
       "tarot cards, candlelit tent, mysterious eyes, "
       "masterpiece, best quality",
       ("#e4d6ff", "#6b4a9e"),
       "오늘 운세… 나쁘진 않네."),
    _c("hana", "하나", "꽃집 소녀", 3, "광휘", "힐러",
       840, 76, 54, 90,
       "꽃잎 위로", "heal", 1.3,
       "아군 전체를 공격력 130%만큼 회복시킨다.",
       "1girl, solo, light green hair, flower crown, apron, holding bouquet, "
       "flower shop background, sunlight, soft smile, "
       "masterpiece, best quality",
       ("#e8f7cc", "#82a83c"),
       "꽃 좋아하세요? 한 송이 드릴게요."),
    _c("nagi", "나기", "항구의 어부", 3, "해류", "탱커",
       1050, 70, 76, 78,
       "그물 방패", "shield", 0.5,
       "아군 전체에 최대 체력 50% 보호막을 씌운다.",
       "1girl, solo, dark blue ponytail, fisherman coat, holding net, "
       "harbor background, seagulls, sunset, easygoing grin, "
       "masterpiece, best quality",
       ("#cfe4ee", "#3d6d85"),
       "파도도 막았는데 이쯤이야."),
    _c("ren", "렌", "도장 사범대리", 3, "화염", "딜러",
       880, 86, 56, 92,
       "정권 지르기", "nuke", 1.72,
       "단일 대상에게 공격력 172% 피해.",
       "1girl, solo, black ponytail, karate gi, black belt, bandaged fists, "
       "dojo background, focused expression, fighting stance, "
       "masterpiece, best quality",
       ("#ffdcd0", "#b0503a"),
       "자세부터 다시. 백 번."),
    _c("yui", "유이", "도서관 사서", 3, "질풍", "보조",
       810, 80, 50, 95,
       "책장 정리", "buff", 0.26,
       "아군 전체의 공격력을 3턴간 26% 올린다.",
       "1girl, solo, brown long hair, glasses, cardigan, holding stack of books, "
       "library background, dust motes in sunlight, quiet smile, "
       "masterpiece, best quality",
       ("#e2ecd8", "#5f8a5a"),
       "조용히… 하지만 확실하게 도와줄게요."),
    _c("sophie", "소피", "시계탑 인형사", 3, "심연", "광역",
       780, 88, 46, 92,
       "태엽 인형극", "aoe", 1.05,
       "적 전체에게 공격력 105% 피해.",
       "1girl, solo, silver twin braids, gothic lolita dress, holding marionette, "
       "clock tower interior, gears, dim light, doll-like expression, "
       "masterpiece, best quality",
       ("#dcd6e8", "#5a4a75"),
       "다들 제 실을 따라 움직여요."),
]

BY_ID = {c["id"]: c for c in CHARACTERS}
BY_RARITY = {r: [c["id"] for c in CHARACTERS if c["rarity"] == r] for r in (3, 4, 5)}

NAI_NEGATIVE = ("lowres, bad anatomy, bad hands, text, error, missing fingers, "
                "extra digit, fewer digits, cropped, worst quality, low quality, "
                "jpeg artifacts, signature, watermark, username, blurry, "
                "multiple girls, nsfw, nude")
