#!/usr/bin/env python3
"""
식은 가마 리소스팩 생성기 (DESIGN.md 10.6). augment-skyblock pack/gen_pack.py 에서 읽기·쓰기 틀만 옮겼다.

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
  2. hud.build: 투명한 허기, 사망 화면 글자, 글꼴. gui_skin.build: 하트·스태미나 막대·단축 슬롯·창·단추·설명 칸·
     Dialog 경고 단추. icons.build: 아이템 그림과 모형 (M0 은 시험 도구 souls:test_guard 하나), 입자 (poof)
  3. 사망 화면 언어 다섯 키 (바닐라의 모든 언어. 클라이언트 언어와 상관없이 같게)
  4. artlint: 오류가 하나라도 있으면 여기서 멈추고 zip 을 만들지 않는다
  5. 정렬 zip: 경로 순서, 날짜, 권한을 고정해 같은 입력이면 SHA-1 이 같다
  6. glyphs.yml, 미리보기

M0 에는 셰이더가 없다 (10.8). 무기·보스·갑옷 그림(wkit, mc3d, art/vboss_*)은 M1 부터 이 파일에 다시 붙인다
(wkit.py, mc3d.py 는 옮겨 두었지만 M0 에서는 부르지 않는다).
아이템 그림은 모두 textures/item/ 아래에 둔다. 1.21.11 은 items 아틀라스가 textures/item 폴더를
이름공간과 상관없이 모두 읽으므로 skyblock 의 write_atlas_sources 는 필요 없다 (icons.py 의 souls:item/test_guard 로 확인).
"""
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import artlint  # noqa: E402
import gui_skin  # noqa: E402
import hud  # noqa: E402
import icons  # noqa: E402
import previews  # noqa: E402

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
OUT = os.path.join(HERE, "resourcepack")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(HERE, "preview")
NS = hud.NS

PACK_FORMAT = 75                     # 1.21.11 클라이언트 version.json 의 resource_major
PACK_DESCRIPTION = "식은 가마"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)

# 사망 화면 언어 (5.6). 제목은 hud 가 만든 그림 글자 문자열로 채운다.
# 클라이언트는 en_us 를 읽고 고른 언어를 그 위에 읽는다. 고른 언어의 바닐라 파일이 팩의 en_us 를 덮으므로
# (en_gb 면 "You Died!") 바닐라의 모든 언어에 같은 다섯 키를 쓴다. 그래야 어떤 언어로 들어와도 같다 (11절 손님 포함).
# 단추 글 앞의 §7 은 바닐라 흰 글씨를 회색으로 낮춘다 (사망 화면 단추는 색을 고를 길이 이것뿐이다). 붉은 제목보다 튀지 않게
DEATH_LANG = {
    "deathScreen.respawn": "\u00a77일어선다",
    "deathScreen.score.value": "",
    "deathScreen.titleScreen": "\u00a77그만둔다",
    "deathScreen.quit.confirm": "여기서 그만두겠나",
}
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


def write_glyphs(path, glyphs, title, plugin_title):
    lines = [
        "# HUD·사망 화면 그림 글자 표 (pack/gen_pack.py 가 만든다. 직접 고치지 말 것)",
        "# 이름: {char: 문자, width: 진행 폭 (글꼴 픽셀, 음수는 왼쪽으로 민다), font: 글꼴}",
        "# 플러그인은 이 표로 Component.text(char).font(font) 를 만든다. 문자 번호를 코드에 적지 않는다.",
        "# you_died 는 사망 화면 제목 한 줄 전체 (deathScreen.title 과 같은 문자열). 언어 문자열은 글꼴을 고를 수 없어",
        "#   minecraft:default 에 있다 (10.9). you_died_title 은 플러그인 화면 제목용 (death.title: true) 한 줄 전체로",
        "#   souls:hud 에 있다. 글꼴은 줄마다 font 를 따른다. 나머지는 한 글자씩.",
    ]
    adv = {(g.font, g.char): g.width for g in glyphs}
    rows = [("you_died", title, sum(adv[(hud.DEFAULT_FONT, ch)] for ch in title), hud.DEFAULT_FONT),
            ("you_died_title", plugin_title, sum(adv[(hud.HUD_FONT, ch)] for ch in plugin_title), hud.HUD_FONT)]
    rows += [(g.name, g.char, g.width, g.font) for g in glyphs]
    for name, ch, width, font in rows:
        lines.append(f"{name}: {{char: {yaml_str(ch)}, width: {width}, font: {yaml_str(font)}}}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


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
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 1. pack.mcmeta, pack.png
    write_json(os.path.join(OUT, "pack.mcmeta"), {
        "pack": {"description": PACK_DESCRIPTION, "min_format": PACK_FORMAT, "max_format": PACK_FORMAT},
    })
    icon = pack_icon()
    icon.save(os.path.join(OUT, "pack.png"))

    # 2. HUD 그림과 글꼴
    glyphs, fonts = hud.build(OUT)
    for (ns, name), data in fonts.items():
        write_json(os.path.join(OUT, "assets", ns, "font", name + ".json"), data)
    gui_skin.build(OUT)   # 하트·스태미나 막대·단축 슬롯·창·단추·설명 칸·Dialog 경고 단추
    icons.build(OUT)      # 아이템 그림·모형·정의 (items 아틀라스), 입자
    title = hud.death_title(glyphs)

    # 3. 사망 화면 언어
    # YOU DIED 는 한 번만 보인다 (5.6). 기본은 사망 화면 제목 자리 (플러그인 death.title: false).
    # plugin 이면 이 제목을 비우고 플러그인이 화면 제목으로 띄운다 (둘을 함께 쓰면 겹쳐 보였다)
    lang = dict(DEATH_LANG)
    lang["deathScreen.title"] = title if mode == "screen" else ""
    lang = dict(sorted(lang.items()))
    for code in LANGS:
        write_json(os.path.join(OUT, "assets", "minecraft", "lang", code + ".json"), lang)

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
        for old in sorted(os.listdir(packs)):
            if old.endswith(".zip") and old != sha1 + ".zip":
                os.remove(os.path.join(packs, old))
                print("지난 팩을 지웠다:", old)
        with open(os.path.join(packs, sha1 + ".zip"), "wb") as f:
            f.write(data)

    # 6. 글자 표, 미리보기
    write_glyphs(os.path.join(RES, "glyphs.yml"), glyphs, title, hud.plugin_title(glyphs))
    sheet, cell_w, _ = hud.you_died_sheet()
    bar_bg, bar_fill = gui_skin.stamina_bar()
    previews.write_all(PREVIEW, {
        "sheet": sheet, "cell_w": cell_w, "glyphs": glyphs, "title": title, "height": hud.YOU_DIED_HEIGHT,
        "ascent": hud.YOU_DIED_ASCENT, "lang": lang, "bar_bg": bar_bg, "bar_fill": bar_fill, "icon": icon,
    })
    gui_skin.write_previews(OUT, PREVIEW)
    print(f"팩 파일 {len(names)}개, {len(data):,} 바이트, sha1 {sha1}")
    print(f"  → {os.path.relpath(os.path.join(RES, 'pack.zip'), ROOT)}"
          + ("" if "--no-dist" in argv else f", dist/packs/{sha1}.zip"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
