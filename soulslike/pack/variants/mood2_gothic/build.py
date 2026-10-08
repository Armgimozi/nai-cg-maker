#!/usr/bin/env python3
"""
UI 분위기 2차 시안 "gothic" (촛불 아래의 고딕): 더 깊은 검정과 비네트, 판의 윗날에 떨어지는 촛불 빛, 막대 끝과 테의 무거운
단조 장식, 다크 소울 3 식 아이템 설명, 어디나 명조·가라몽·로마 비문 대문자. 글자는 우리가 미리 그린 bitmap 글꼴 (fonts.py).

  python3 pack/variants/mood2_gothic/build.py <작업폴더> [--rev <git 판>] [--no-java] [--no-art]

저장소의 git 판 (기본 HEAD) 에서 plugin/ 을 <작업폴더>/snap 에 꺼내 (다른 작업이 고치는 중인 파일을 섞지 않으려고) 그 안의
pack.zip 을 <작업폴더>/pack/ 에 풀고 덧입힌다. 결과
  <작업폴더>/pack.zip          시안 팩
  <작업폴더>/Soulslike.jar     시안 플러그인 (사본을 고쳐 만든 jar 에 시안 팩과 그 glyphs.yml)
  <작업폴더>/preview_*.png     그림 미리보기
저장소의 공용 파일 (gen_pack·gui_skin·hud, pack/resourcepack, plugin/) 은 건드리지 않는다. 켜는 법은 README 대신 이
머리말과 shots.sh: 이 시안은 기본 꺼짐이고, 이 스크립트로 만든 jar 를 쓸 때만 켜진다.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(PACK_DIR)
for p in (HERE, PACK_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import fonts  # noqa: E402
import shaders  # noqa: E402
import style as st  # noqa: E402
import typeset  # noqa: E402

ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def zip_bytes(folder):
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
    return buf.getvalue()


def replace_in_jar(src, dst, entries):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst + ".part", "w") as zout:
        seen = set()
        for info in zin.infolist():
            if info.filename in entries:
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, entries[info.filename])
                seen.add(info.filename)
            else:
                zout.writestr(info, zin.read(info.filename))
        for name, data in entries.items():
            if name not in seen:
                zi = zipfile.ZipInfo(name, date_time=ZIP_DATE)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, data)
    os.replace(dst + ".part", dst)


def snapshot(work, rev):
    """git 판 rev 의 plugin/ 을 work/snap/plugin 에 꺼낸다."""
    snap = os.path.join(work, "snap")
    if os.path.exists(snap):
        shutil.rmtree(snap)
    os.makedirs(snap)
    arc = subprocess.run(["git", "archive", rev, "plugin"], cwd=ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", snap], input=arc, check=True)
    return os.path.join(snap, "plugin")


def client_jar():
    home = os.environ.get("SOULS_CLIENT_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "souls-client")
    return os.path.join(home, "versions", "1.21.11.jar")


def write_licences(pack, keys):
    lic = os.path.join(pack, "assets", "souls", "font", "gothic", "licenses")
    os.makedirs(lic, exist_ok=True)
    notice = ["Square Soul resource pack, UI mood variant \"mood2_gothic\" - fonts", "",
              "The glyph images assets/souls/textures/font/gothic_*.png were rendered (FreeType) from these fonts,",
              "licensed under the SIL Open Font License, Version 1.1 (full text in assets/souls/font/gothic/licenses/).",
              "No font software is included in this pack; only pre-rendered glyph bitmaps.", ""]
    for key in keys:
        text = fonts.licence_text(key)
        name = fonts.SOURCES[key][2]
        with open(os.path.join(lic, "ofl-" + name.lower().replace(" ", "-") + ".txt"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(text)
        notice.append(f"  {name}: {text.splitlines()[0].strip()}")
    with open(os.path.join(pack, "FONTS-OFL.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(notice) + "\n")


def build_fonts(pack, title_kr_text, window_title_syllables):
    """그림 글자 아틀라스와 글꼴 정의. 돌려주는 값: (roles, measure 묶음, 바이트)."""
    t = time.time()
    roles = typeset.make_roles(st, sorted(set(ch for ch in title_kr_text if 0xAC00 <= ord(ch) <= 0xD7A3)))
    pua_la, pua_kr, la_map, kr_map = typeset.pua_roles(st, window_title_syllables)
    sizes = {}
    provs = {}
    for name, role in list(roles.items()) + [("pua_la", pua_la), ("pua_kr", pua_kr)]:
        provs[name], sizes[name] = typeset.write_atlas(pack, role, "gothic_" + name)
    print(f"  글자 그림: " + ", ".join(f"{k} {len(r.glyphs)}자 {sizes[k] // 1024}KB" for k, r in
                                    list(roles.items()) + [("pua_la", pua_la), ("pua_kr", pua_kr)])
          + f" ({time.time() - t:.1f}초)")
    spaces = typeset.Spaces(st.PUA_SPACE)
    body_space = {" ": st.BODY_SPACE, " ": st.BODY_SPACE, "　": 8, chr(st.PUA_TITLE_LA): st.TITLE_SPACE}
    fdir = os.path.join(pack, "assets", "minecraft", "font")
    base = typeset.read_json(os.path.join(fdir, "default.json"))
    default = [{"type": "space", "advances": body_space}, provs["body_la"], provs["body_kr"], provs["pua_la"],
               provs["pua_kr"]]
    sdir = os.path.join(pack, "assets", "souls", "font")
    title = [{"type": "space", "advances": {" ": st.TITLE_SPACE, " ": st.TITLE_SPACE}}, provs["title_la"],
             provs["title_kr"]]
    meas = {
        "body": typeset.Measure([roles["body_la"], roles["body_kr"]], {" ": st.BODY_SPACE}),
        "title": typeset.Measure([roles["title_la"], roles["title_kr"], roles["body_la"], roles["body_kr"]],
                                 {" ": st.TITLE_SPACE}),
        "pua": typeset.Measure([pua_la, pua_kr, roles["body_la"], roles["body_kr"]], {chr(st.PUA_TITLE_LA): st.TITLE_SPACE}),
        "la_map": la_map, "kr_map": kr_map, "spaces": spaces,
    }

    def finish(extra_default=(), extra_title=()):
        sp = {"type": "space", "advances": spaces.advances()} if spaces.by_adv else None
        d = default + list(extra_default) + ([sp] if sp else [])
        typeset.write_json(os.path.join(fdir, "default.json"), {"providers": d + base["providers"]})
        typeset.write_json(os.path.join(sdir, "gothic_title.json"),
                           {"providers": title + list(extra_title) + ([sp] if sp else [])
                            + [{"type": "reference", "id": "minecraft:default"}]})

    return roles, meas, sum(sizes.values()), finish


def check_fonts(pack):
    """글꼴 정의의 bitmap 공급자: ascent <= height (클라이언트가 글꼴 전체를 버린다), 그림이 있고 칸이 나누어 떨어진다."""
    import json
    from PIL import Image
    for ns in ("minecraft", "souls"):
        d = os.path.join(pack, "assets", ns, "font")
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if not n.endswith(".json"):
                continue
            with open(os.path.join(d, n), encoding="utf-8") as f:
                provs = json.load(f).get("providers", [])
            for p in provs:
                if p.get("type") != "bitmap":
                    continue
                assert p["ascent"] <= p["height"], f"{ns}:{n} {p['file']}: ascent {p['ascent']} > height {p['height']}"
                fns, fp = p["file"].split(":", 1)
                img = Image.open(os.path.join(pack, "assets", fns, "textures", fp))
                rows = p["chars"]
                assert img.height % len(rows) == 0 and all(len(r) == len(rows[0]) for r in rows), f"{p['file']}: 칸"
                assert img.width % len(rows[0]) == 0, f"{p['file']}: 칸 폭"
                cw, ch = img.width // len(rows[0]), img.height // len(rows)
                assert cw <= 256 and ch <= 256, f"{p['file']}: 칸 {cw}×{ch} 텍셀 (글꼴 아틀라스 256×256 을 넘는다)"


def lint(pack):
    """시안 팩의 그림을 artlint 로 본다 (글자 그림 gothic_* 는 덮임 자료라 뺀다: 색이 아니라 R 에 덮임, B 에 표식)."""
    import artlint
    files = []
    for base, _, names in os.walk(pack):
        for n in names:
            if not n.endswith(".png"):
                continue
            rel = os.path.relpath(os.path.join(base, n), pack).replace(os.sep, "/")
            if "/textures/font/gothic_" in "/" + rel and not rel.endswith(("gothic_divider.png",)) and "_rule_" not in rel:
                continue
            if rel.endswith("misc/vignette.png"):
                continue   # 셰이더가 읽는 세기 지도 (회색, 바닐라도 그렇다)
            if "/textures/block/" in "/" + rel or "/textures/item/" in "/" + rel or "/textures/colormap/" in "/" + rel:
                continue   # 기본 팩 그대로 (gen_pack 이 이미 본다)
            files.append(os.path.join(base, n))
    rep = artlint.Report()
    for f in sorted(files):
        artlint.check_image(f, rep, os.path.relpath(f, pack))
    errs = rep.errors
    print(f"  artlint (시안 UI 그림 {len(files)}장): 오류 {len(errs)}, 경고 {len(rep.warnings)}")
    for level, path, rule, msg in errs[:20]:
        print(f"    [{level}] {os.path.relpath(path, pack)}: {rule} — {msg}")
    return rep


def main(argv):
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    work = os.path.abspath(argv[0])
    rev = argv[argv.index("--rev") + 1] if "--rev" in argv else "HEAD"
    os.makedirs(work, exist_ok=True)
    src = snapshot(work, rev)
    base_zip = os.path.join(src, "src", "main", "resources", "pack.zip")
    pack = os.path.join(work, "pack")
    if os.path.exists(pack):
        shutil.rmtree(pack)
    with zipfile.ZipFile(base_zip) as z:
        z.extractall(pack)
    base_size = os.path.getsize(base_zip)
    print(f"기본 팩 {base_size:,} 바이트 (git {rev})")

    import art_gui
    import art_hud
    import lang
    title_kr_text = lang.title_text(src)
    roles, meas, font_bytes, finish = build_fonts(pack, title_kr_text, lang.window_title_syllables())
    write_licences(pack, sorted({st.BODY_LA[0], st.BODY_KR[0], st.TITLE_LA[0], st.TITLE_KR[0]}))
    shaders.build_text(pack, st)
    with zipfile.ZipFile(client_jar()) as z:
        vanilla_blur = z.read("assets/minecraft/post_effect/blur.json").decode("utf-8")
    shaders.build_gui(pack, vanilla_blur)
    layout, extra_default, extra_title = lang.build(pack, st, meas)
    finish(extra_default, extra_title)
    glyphs_yml = None
    if "--no-art" not in argv:
        t = time.time()
        gui_files = art_gui.write_all(pack)
        art_gui.death_band().image().save(os.path.join(pack, "assets", "souls", "textures", "font", "hud_death_band.png"))
        digit_role = fonts.Role("digits", [fonts.Face(*st.DIGITS)])
        digit_role.add("0123456789")
        providers, hud_glyphs = art_hud.build(pack, digit_role)
        art_hud.write_font(pack, providers)
        with open(os.path.join(src, "src", "main", "resources", "glyphs.yml"), encoding="utf-8") as f:
            glyphs_yml = art_hud.glyphs_yml(f.read(), hud_glyphs)
        print(f"  그림: 창·단추 {len(gui_files)}장, HUD 그림 글자 {len(hud_glyphs)}자 ({time.time() - t:.1f}초)")
        lint(pack)

    check_fonts(pack)
    data = zip_bytes(pack)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(os.path.join(work, "pack.zip"), "wb") as f:
        f.write(data)
    out_jar = os.path.join(work, "Soulslike.jar")
    if "--no-java" in argv:
        plugin_jar = os.path.join(ROOT, "plugin", "build", "libs", "Soulslike.jar")
    else:
        import java_hook
        plugin_jar = java_hook.build(work, src, st, layout, glyphs_yml)
    replace_in_jar(plugin_jar, out_jar, {"pack.zip": data})
    print(f"시안 팩 {len(data):,} 바이트 (기본보다 {len(data) - base_size:+,}; 글자 그림 {font_bytes:,}), sha1 {sha1}")
    print(f"  → {os.path.join(work, 'pack.zip')}, {out_jar}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
