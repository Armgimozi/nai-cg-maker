#!/usr/bin/env python3
"""
스퀘어 소울 리소스팩 생성기 (DESIGN.md 10.6). augment-skyblock pack/gen_pack.py 에서 읽기·쓰기 틀만 옮겼다.

  python3 pack/gen_pack.py            그림 생성 → artlint → zip
  python3 pack/gen_pack.py --no-dist  dist/packs/ 에 쓰지 않는다 (시험용)
  python3 pack/gen_pack.py --death-title screen|plugin
                                      사망 화면 제목을 정한다. 주지 않으면 플러그인 설정
                                      (plugin/src/main/resources/config.yml 의 death.title) 을 따른다: false 면 screen
                                      (사망 화면 제목이 YOU DIED), true 면 plugin (사망 화면 제목을 비우고 플러그인이 화면
                                      제목으로 띄운다, 5.6 과 16절 질문 4). 설정 한 곳만 바꾸면 팩과 jar 가 함께 맞는다

결과
  pack/resourcepack/                          팩 폴더 (zip 에 들어가는 그대로)
  plugin/src/main/resources/pack.zip          플러그인 jar 에 들어갈 팩
  plugin/src/main/resources/glyphs.yml        HUD·사망 화면 그림 글자 표 (플러그인 hud/Glyphs 가 읽는다)
  dist/packs/<sha1>.zip                       배포할 팩 (주소 틀의 {sha1}, 10.10). 예전 것은 지운다
  pack/preview/*.png                          사람이 볼 미리보기

순서
  1. 팩 폴더를 비우고 pack.mcmeta (형식 75), pack.png
  2. fonts.build: 게임 글꼴 (FreeType 으로 미리 그린 명조·가라몽·비문 대문자 bitmap, 제목 밑 금실, OFL 사용 허락 글).
     hud.build: 투명한 허기, 사망 화면 글자, 글꼴 (다크 소울 HUD 막대·소울 상자·보스 막대 그림 글자).
     shaders.build: 글꼴 셰이더 (HUD 덩이 + 글자 넓이 평균), GUI 셰이더 (비네트·그림 넓이 평균), 메뉴 뒤 흐림.
     gui_skin.build: 숨기는 HUD (하트·방어·경험치 막대)·보스 막대·단축 슬롯·창·단추·설명 칸·Dialog 경고 단추 (고딕 촛불).
     icons.build: 아이템 그림과 모형 (M0 은 시험 도구 souls:test_guard 하나), 입자 (poof)
  3. 언어 파일 (langpack.py): 게임 문구 assets/souls/lang/ko_kr.json·en_us.json (lang/ko.yml·en.yml 에서),
     바닐라 덮어쓰기 assets/minecraft/lang/<언어>.json (사망 화면 다섯 키와 창 제목. 제목은 그림 글자로 모든 언어가 같고, 단추 글은
     ko_kr 이 한국어, 나머지 모든 언어가 영어). ko.yml 과 en.yml 의 짝이 틀리면 (열쇠·자리·꼴) 여기서 멈춘다.
     typeset.py 가 막 쓴 팩 글꼴로 창 제목을 제목 글자로, 제목 밑 금실, 무기 수치 이름의 열 맞춤 빈칸을 짠다
  3b. 블록: blocks_grade.build (1층, 바닐라 블록 그림 전부의 색을 옮긴다. 클라이언트 jar 가 있어야 한다) 뒤에
     blocks_core.build (2층, 맵의 핵심 블록을 새로 그려 덮는다)
  4. artlint: 오류가 하나라도 있으면 여기서 멈추고 zip 을 만들지 않는다
  5. 정렬 zip: 경로 순서, 날짜, 권한을 고정해 같은 입력이면 SHA-1 이 같다
  6. glyphs.yml, 미리보기

셰이더는 shaders.ALLOWED 뿐이다 (글꼴·GUI 셰이더와 구르기 대역의 아이템 셰이더, 10.8). 무기·보스·갑옷 그림(wkit, mc3d, art/vboss_*)은 M1 부터 이 파일에 다시 붙인다
(M0 에는 wkit 을 쓰는 그림이 없다. 구르기 대역 roll_figure.py 는 플레이어 비례의 상자 모형을 직접 쓴다).
아이템 그림은 모두 textures/item/ 아래에 둔다. 1.21.11 은 items 아틀라스가 textures/item 폴더를
이름공간과 상관없이 모두 읽으므로 skyblock 의 write_atlas_sources 는 필요 없다 (icons.py 의 souls:item/test_guard 로 확인).
"""
import hashlib
import io
import json
import os
import subprocess
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import artlint  # noqa: E402
import blocks_core  # noqa: E402
import blocks_grade  # noqa: E402
import fonts  # noqa: E402
import gui_skin  # noqa: E402
import hud  # noqa: E402
import icons  # noqa: E402
import langpack  # noqa: E402
import previews  # noqa: E402
import roll_figure  # noqa: E402
import shaders  # noqa: E402
import typeset  # noqa: E402
try:
    from weapons import set_b as weapons_b  # 무기 B 묶음 (자루 무기·판자 방패·손종, weapons/SPEC.md 4절)
except ImportError:
    weapons_b = None
try:
    from weapons import set_a as weapons_a  # 무기 A 묶음 (칼·방패·활·쇠단지, weapons/SPEC.md 4절)
except ImportError:
    weapons_a = None

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
OUT = os.path.join(HERE, "resourcepack")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(HERE, "preview")
NS = hud.NS

PACK_FORMAT = 75                     # 1.21.11 클라이언트 version.json 의 resource_major
# 팩 설명 (팩 목록에 보인다). 언어 열쇠라 클라이언트 언어로 보이고, 팩 언어를 싣기 전에는 영어 대체 글
PACK_DESCRIPTION_KEY = "pack.description"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)

# 사망 화면 언어 (5.6). 제목은 hud 가 만든 그림 글자 문자열로 채우고 (모든 언어가 같다), 나머지 넷 (단추 글·점수 줄·
# 확인 문구) 은 lang/ko.yml·en.yml 의 vanilla.deathScreen.* 에서 온다 (langpack.build).
# 클라이언트는 en_us 를 읽고 고른 언어를 그 위에 읽는다. 고른 언어의 바닐라 파일이 팩의 en_us 를 덮으므로
# (en_gb 면 "You Died!") 바닐라의 모든 언어에 다섯 키를 쓴다: ko_kr 은 한국어, 나머지는 영어 (11절 손님 포함).
# 단추 글 앞의 §7 (YAML 의 <gray>) 은 바닐라 흰 글씨를 회색으로 낮춘다 (사망 화면 단추는 색을 고를 길이 이것뿐이다)
# 1.21.11 클라이언트의 언어 전부: jar 안 en_us + 에셋 목록(assets/indexes/29.json)의 minecraft/lang/*.json 142개
LANGS = tuple(sorted("""
en_us af_za ar_sa ast_es az_az ba_ru bar be_by be_latn bg_bg br_fr brb bs_ba ca_es cs_cz cv_cu cy_gb da_dk de_at de_ch
de_de el_gr en_au en_ca en_gb en_nz en_pt en_ud enp enws eo_uy es_ar es_cl es_ec es_es es_mx es_uy es_ve esan et_ee
eu_es fa_ir fi_fi fil_ph fo_fo fr_ca fr_ch fr_fr fra_de fur_it fy_nl ga_ie gd_gb gl_es go_fr got_de hal_ua haw_us he_il
hi_in hn_no hr_hr hu_hu hy_am id_id ig_ng io_en is_is isv it_it ja_jp jbo_en ka_ge kk_kz kn_in ko_kr ksh kw_gb ky_kg
la_la lb_lu li_li lmo lo_la lol_us lt_lt lv_lv lzh mk_mk mn_mn ms_my mt_mt nah nds_de nl_be nl_nl nn_no no_no oc_fr
ovd pl_pl pls pt_br pt_pt qcb_es qid qya_aa ro_ro rpr ru_ru ry_ua sah_sah se_no sk_sk sl_si so_so sq_al sr_cs sr_sp
sv_se sxu szl ta_in th_th tl_ph tlh_aa tok tr_tr tt_ru tzo_mx uk_ua uz_uz val_es vec_it vi_vn vp_vl vro yi_de yo_ng
zh_cn zh_hk zh_tw zlm_arab
""".split()))
PLUGIN_CONFIG = os.path.join(RES, "config.yml")


def write_json(path, data):
    """팩 안의 json 은 ASCII 로만 쓴다 (개인 영역 문자도 \\uE000 처럼 보이게, 줄바꿈과 순서 고정)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def pack_icon():
    """art/pack_icon.txt (32×32 손으로 찍은 그림). 키우지 않고 그대로 쓴다 (팩 목록에 32×32 로 보인다)."""
    ink = {".": "ash0", ",": "ash1", ":": "ash2", ";": "ash3", "r": "rust0", "R": "rust1", "s": "rust2", "S": "rust3",
           "b": "bronze0", "B": "bronze1", "n": "bronze2", "k": "blood0", "e": "ember0"}
    rows = hud.load_grids(os.path.join(HERE, "art", "pack_icon.txt"))["icon"]
    return hud.grid_image(rows, ink, clear=None)


def zip_bytes(folder):
    """
    folder 를 정렬 zip 으로 묶는다. 폴더 항목은 넣지 않고, 파일 경로 순서·날짜·권한·만든 시스템을 고정한다.
    같은 입력이면 어느 날 몇 번을 돌려도 같은 바이트가 나온다 (T8).
    """
    files = []
    for base, dirs, names in os.walk(folder):
        dirs.sort()
        for n in names:
            full = os.path.join(base, n)
            files.append((os.path.relpath(full, folder).replace(os.sep, "/"), full))
    files.sort()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for arc, full in files:
            zi = zipfile.ZipInfo(arc, date_time=ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 0
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                z.writestr(zi, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue(), [a for a, _ in files]


def yaml_str(s):
    """glyphs.yml 용 큰따옴표 문자열. ASCII 밖은 \\uXXXX 로 적어 파일이 눈에 보이게 한다."""
    out = []
    for ch in s:
        if ch in ('"', "\\"):
            out.append("\\" + ch)
        elif 0x20 <= ord(ch) < 0x7f:
            out.append(ch)
        else:
            out.append(f"\\u{ord(ch):04x}")
    return '"' + "".join(out) + '"'


def write_glyphs(path, glyphs, title, plugin_title, value_widths):
    lines = [
        "# HUD·사망 화면 그림 글자 표 (pack/gen_pack.py 가 만든다. 직접 고치지 말 것)",
        "# 이름: {char: 문자, width: 진행 폭 (글꼴 픽셀, 음수는 왼쪽으로 민다), font: 글꼴}",
        "# 플러그인은 이 표로 Component.text(char).font(font) 를 만든다. 문자 번호를 코드에 적지 않는다.",
        "# you_died 는 사망 화면 제목 한 줄 전체 (deathScreen.title 과 같은 문자열). 언어 문자열은 글꼴을 고를 수 없어",
        "#   minecraft:default 에 있다 (10.9). you_died_title 은 플러그인 화면 제목용 (death.title: true) 한 줄 전체로",
        "#   souls:hud 에 있다. 글꼴은 줄마다 font 를 따른다. 나머지는 한 글자씩.",
        "# text_space_* 는 기본 글꼴의 빈칸 (pack/typeset.py), lore_rule 은 무기 설명 칸의 실선 (item/StatTable).",
        "# stats 는 무기 설명 칸 수치 표의 열 (GUI 픽셀) 과 값 글자의 진행 폭 (기본 글꼴, pack/typeset.py 가 팩에서 잰 것).",
    ]
    adv = {(g.font, g.char): g.width for g in glyphs}
    rows = [("you_died", title, sum(adv[(hud.DEFAULT_FONT, ch)] for ch in title), hud.DEFAULT_FONT),
            ("you_died_title", plugin_title, sum(adv[(hud.HUD_FONT, ch)] for ch in plugin_title), hud.HUD_FONT)]
    rows += [(g.name, g.char, g.width, g.font) for g in glyphs]
    rows += [(n, ch, w, typeset.DEFAULT_FONT) for n, ch, w in typeset.space_chars()]
    for name, ch, width, font in rows:
        lines.append(f"{name}: {{char: {yaml_str(ch)}, width: {width}, font: {yaml_str(font)}}}")
    # HUD 자리 값 (hud.layout, 글꼴 셰이더와 같은 값). 플러그인 Glyphs 가 그림 글자와 따로 읽는다
    lines.append("layout: {" + ", ".join(f"{k}: {yaml_str(str(v)) if isinstance(v, str) else v}"
                                         for k, v in hud.layout().items()) + "}")
    chars = "".join(value_widths)
    lines.append(f"stats: {{value_col: {typeset.VALUE_COL}, col_gap: {typeset.COL_GAP}, chars: {yaml_str(chars)}, "
                 f"widths: [{', '.join(str(value_widths[ch]) for ch in chars)}]}}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def pack_fallback(ko, en):
    """팩 설명의 대체 글 (팩 언어를 싣기 전): 영어 글을 언어 파일과 같은 꼴로 (꼴 태그를 떼고, %% 와 %1$s)."""
    order = langpack.slots(langpack.split_style(ko[PACK_DESCRIPTION_KEY])[1])
    return langpack.mc_format(langpack.split_style(en[PACK_DESCRIPTION_KEY])[1], order)


def config_death_title():
    """플러그인 config.yml 의 death.title (true 면 플러그인이 화면 제목으로 띄운다). 못 읽으면 False."""
    try:
        import yaml
        with open(PLUGIN_CONFIG, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("death") or {}).get("title") is True
    except (OSError, ImportError, ValueError) as ex:
        print("config.yml 의 death.title 을 읽지 못해 screen 으로 만든다:", ex)
        return False


def death_title_mode(argv):
    """--death-title screen|plugin. 없으면 config.yml 의 death.title 을 따른다. 모르는 값이면 None."""
    mode = "plugin" if config_death_title() else "screen"
    for i, a in enumerate(argv):
        if a == "--death-title" and i + 1 < len(argv):
            mode = argv[i + 1]
        elif a.startswith("--death-title="):
            mode = a.split("=", 1)[1]
    if mode not in ("screen", "plugin"):
        print("--death-title 은 screen 또는 plugin 이다:", mode)
        return None
    return mode


def main(argv):
    mode = death_title_mode(argv)
    if mode is None:
        return 2
    # 문구 원본 (lang/ko.yml, en.yml). 짝이 틀리면 팩을 만들지 않는다 (tools/langcheck.py 가 더 많이 본다)
    tables = langpack.load_all()
    bad = langpack.problems(tables)
    if bad:
        for key, why in bad:
            print(f"  lang {key}: {why}")
        print(f"lang/ko.yml 과 en.yml 이 {len(bad)}곳 어긋나 팩을 묶지 않는다.")
        return 1
    en = langpack.lines(tables["en"])
    ko = langpack.lines(tables["ko"])
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 1. pack.mcmeta, pack.png
    write_json(os.path.join(OUT, "pack.mcmeta"), {
        "pack": {"description": {"translate": langpack.PREFIX + PACK_DESCRIPTION_KEY, "fallback": pack_fallback(ko, en)},
                 "min_format": PACK_FORMAT, "max_format": PACK_FORMAT},
    })
    icon = pack_icon()
    icon.save(os.path.join(OUT, "pack.png"))

    # 2. 글꼴 (본문·제목 글자 그림, 금실, 빈칸) 과 HUD 그림 글자, 셰이더, 창 그림
    fontset = fonts.build(OUT, langpack.lines(tables["ko"]))
    glyphs, font_json, hud_providers = hud.build(OUT, fonts.digit_role())
    font_json[("minecraft", "default")]["providers"][:0] = fontset.default
    font_json[("minecraft", "uniform")]["providers"][:0] = fontset.uniform
    font_json[(NS, "title")] = {"providers": fontset.title}
    for (ns, name), data in font_json.items():
        write_json(os.path.join(OUT, "assets", ns, "font", name + ".json"), data)
    bad = fonts.check(OUT)
    if bad:
        print("글꼴 정의가 틀려 팩을 묶지 않는다:", *bad, sep="\n  ")
        return 1
    shaders.build(OUT)    # 글꼴 셰이더 (HUD 덩이 + 글자 넓이 평균), GUI 셰이더, 메뉴 뒤 흐림 (10.8)
    gui_skin.build(OUT)   # 숨기는 HUD (하트·방어·경험치 막대)·보스 막대·단축 슬롯·창·단추·설명 칸·Dialog 경고 단추
    icons.build(OUT)      # 아이템 그림·모형·정의 (items 아틀라스), 입자
    if weapons_b:
        weapons_b.build(OUT)  # 무기 B: 3D 모형·16px 그림·아이템 정의 (roll_figure 의 손 감추기가 감싸기 전에)
    if weapons_a:
        weapons_a.build(OUT)  # 무기 A: 3D 모형·16px 그림·아이템 정의 (roll_figure 의 손 감추기가 감싸기 전에)
    roll_figure.build(OUT)   # 구르기 대역 (관절 부위·머리·투구 모형, 물들일 재료), 급류 회전 소용돌이 감추기 (3.3)
    # 대역의 열쇠 자세 표 (플러그인 Tumble 이 읽는다. 팩의 부위 모형과 같은 뼈대에서 셈한다)
    roll_figure.anim_table(os.path.join(RES, "roll_anim.yml"))
    # 대역 색: 바닐라 기본 스킨 18 개의 표 (클라이언트 jar 가 있을 때만 다시 뽑는다. 없으면 커밋된 표를 그대로 쓴다)
    roll_figure.skin_table(roll_figure.client_jar(), os.path.join(RES, "roll_skins.yml"))
    title = hud.death_title(glyphs)

    # 3. 언어 파일: 게임 문구 (assets/souls/lang) 와 바닐라 덮어쓰기 (assets/minecraft/lang, 사망 화면)
    # YOU DIED 는 한 번만 보인다 (5.6). 기본은 사망 화면 제목 자리 (플러그인 death.title: false).
    # plugin 이면 이 제목을 비우고 플러그인이 화면 제목으로 띄운다 (둘을 함께 쓰면 겹쳐 보였다)
    packfonts = typeset.PackFonts.open(OUT)
    lang_files = langpack.build(tables, LANGS, typeset=typeset.Typeset(packfonts))
    for rel, data in lang_files.items():
        if rel.startswith("assets/minecraft/lang/"):
            data["deathScreen.title"] = title if mode == "screen" else ""
            data = dict(sorted(data.items()))
        write_json(os.path.join(OUT, *rel.split("/")), data)
    lang = dict(sorted(lang_files["assets/minecraft/lang/ko_kr.json"].items()))

    # 구르는 동안 손에 든 souls 아이템을 3인칭에서 비우는 깃발 (아이템 정의를 모두 쓴 뒤에 감싼다, 3.3)
    roll_figure.wrap_item_definitions(OUT)

    # 블록 1층: 바닐라 블록 그림 전부 (+ .mcmeta, 풀빛·잎빛 색 지도) 의 색을 다크소울 쪽으로 옮긴다 (blocks_grade.py,
    # 클라이언트 jar 에서 읽는다)
    print("블록 그림 (1층):", blocks_grade.build(OUT))

    # 블록 2층: 맵·시험 방의 핵심 블록을 손 규칙으로 다시 그린다 (blocks_core.py). 1층 (blocks_grade) 이 옮긴
    # 같은 이름의 그림을 덮어야 하므로 블록 그림을 쓰는 단계 가운데 마지막이다
    blocks_core.build(OUT)
    # 바닐라가 바탕 돌·흙·판자를 그대로 깐 그림 (광석, 풀 블록 옆면, 작업대 …) 을 최종 바탕 그림 위에 다시 맞춘다
    print("블록 그림 바탕 맞춤:", blocks_grade.finish(OUT))

    # 4. artlint (오류가 있으면 zip 을 만들지 않는다)
    report = artlint.lint([OUT], OUT)
    if report.errors:
        print("artlint 오류가 있어 팩을 묶지 않는다.")
        return 1

    # 5. 정렬 zip
    data, names = zip_bytes(OUT)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(RES, "pack.zip"), "wb") as f:
        f.write(data)
    if "--no-dist" not in argv:
        packs = os.path.join(DIST, "packs")
        os.makedirs(packs, exist_ok=True)
        # 한 번 커밋한 팩은 지우지 않는다: 그 판의 jar 를 받은 서버가 아직 그 주소로 팩을 보낸다 (지우면 "다운로드 실패").
        # 커밋하지 않은 중간 팩만 지운다.
        try:
            kept = set(os.path.basename(x) for x in subprocess.run(
                ["git", "ls-files", "--", packs], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split())
        except (OSError, subprocess.CalledProcessError):
            kept = None   # git 이 없으면 아무것도 지우지 않는다
        for old in sorted(os.listdir(packs)):
            if old.endswith(".zip") and old != sha1 + ".zip" and kept is not None and old not in kept:
                os.remove(os.path.join(packs, old))
                print("커밋하지 않은 지난 팩을 지웠다:", old)
        with open(os.path.join(packs, sha1 + ".zip"), "wb") as f:
            f.write(data)

    # 6. 글자 표, 미리보기
    write_glyphs(os.path.join(RES, "glyphs.yml"), glyphs, title, hud.plugin_title(glyphs),
                 typeset.Typeset(packfonts).value_widths())
    sheet, cell_w, _ = hud.you_died_sheet()
    previews.write_all(PREVIEW, {
        "sheet": sheet, "cell_w": cell_w, "glyphs": glyphs, "title": title, "height": hud.YOU_DIED_HEIGHT,
        "ascent": hud.YOU_DIED_ASCENT, "lang": lang, "icon": icon,
    })
    gui_skin.write_previews(OUT, PREVIEW)
    hud.preview_hud(OUT, os.path.join(PREVIEW, "hud.png"), glyphs, hud_providers)
    roll_figure.preview_default(os.path.join(PREVIEW, "roll_figure.png"))
    print(f"팩 파일 {len(names)}개, {len(data):,} 바이트, sha1 {sha1}")
    print(f"  → {os.path.relpath(os.path.join(RES, 'pack.zip'), ROOT)}"
          + ("" if "--no-dist" in argv else f", dist/packs/{sha1}.zip"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
