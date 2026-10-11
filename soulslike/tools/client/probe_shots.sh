#!/bin/bash
# 입력 탐침 스파이크 (M1 PS, M1_PLAN 2절의 S1~S6·S9~S13) 를 실제 바닐라 1.21.11 클라이언트로 돌리고 찍는다:
#   probe_shots.sh <포트> <서버폴더> [장면...]
# 서버는 devserver.sh 로 켜 둔 시험 서버 (op Tester), 클라이언트는 켜서 들어와 있어야 한다 (run_client.sh --start <포트> <찍을폴더>,
# --do <포트> join). 시험 줄이 그림을 가리지 않게 MC_OPTIONS="chatScale:0.0" 로 켠다 (줄은 서버 기록에 남는다).
# 실제 클라이언트는 한 번에 하나: flock <client.lock> 으로 감싸 부른다.
# 플러그인의 입력 탐침 (/soulstest probe, input/InputProbe) 을 켜고, 장면마다 [T] PROBE_MARK label=<장면> 을 남긴 뒤 키·마우스를 누른다.
# 끝에 서버 기록의 [T] 줄을 장면별로 나눠 잰다 (analyze).
# 장면 (없으면 모두. analyze 만 주면 지난번 기록으로 다시 잰다):
#   s1   주손 직검·왼손 패링 단검 (쓰기 성분 없는 부싯돌): 하늘에 우클릭 한 번 / 누르고 있기 2초, 바닥에 한 번 / 누르고 있기.
#        use_item 손 0 다음 손 1 이 오는가, 누르고 있으면 몇 틱마다, RIGHT_CLICK_BLOCK 과 RIGHT_CLICK_AIR 가 겹치는가
#   s2   F 를 1.5초·3초 누르고 있기: swap 이 몇 번, 첫 반복까지 ms, 반복 간격 ms (이 가상 화면의 키 반복 = X 기본값)
#   s3   /tick rate 5. fswing off (F 에 서버가 swingOffHand). F 만 / 좌클릭 뒤 0.1초에 F / 좌클릭 뒤 0.8초에 F / F 뒤 0.1초에 좌클릭.
#        1인칭 연속 그림에서 왼손·오른손 자리의 움직임을 잰다 (반쯤 휘두른 동안 새 휘두름은 무시되는가)
#   s3x  /tick rate 5. F 만 (서버 휘두름 없음), 콘솔의 swingOffHand, swingMainHand 를 찍고, 20틱에서 서버 휘두름 뒤 클라이언트가 자기
#        휘두름 패킷 (swing 과 LEFT_CLICK_AIR) 을 다시 보내는지 (메아리) 세 번씩
#   s13  /tick rate 5. 왼손 휘두름 (F) 의 길이와 꼴이 주손 swing_animation 을 따르는가: 주손 기본·whack 20·stab 20·빈손, 왼손 stab 20
#   s4   이동 속도 수정자 (바닐라 /attribute): 없음·−25%·−50%·뿌리 (이동 −100% + 점프 −100%)·느림 II, 그리고 걷기 속도
#        (probe walkspeed 0.1 / 0 + 점프 −100%). 시야 (FOV) 그림과 1초 걸음, 뛰기
#   s5   막는 중 (왼손 방패를 우클릭으로) 과 바닐라 물약을 마시는 중의 웅크리기 짧게 누르기
#   s6   attack_range {max_reach:4.2} 부싯돌로 4.0 칸 (눈에서 상자까지) 허스크를 좌클릭 / 대조: 그냥 부싯돌 / 4.3 칸
#   s9   몹의 왼손 방패 startUsingItem(OFF_HAND): 허스크 쥐기만·쓰기·쓰기+공격 자세, 스켈레톤, 바닐라 방패
#   s10  머리 칸에 화면에만 있는 막힘 (probe crawl): 1인칭, F5 등·앞
#   s11  웅크리기 키를 누른 채 인벤토리 (E) / 채팅 (T) 을 열고 닫기
#   s12  달리며 허스크를 좌클릭 (취소 안 함 / probe cancel attack), /tick rate 5 의 떨어지며 치기 (치명타 입자)
# 결과: OUT (기본 dist/screenshots/m1) 에 ps_<장면>_*.png (그림·연속 그림 띠), ps_probe.log (장면별 [T] 줄), ps_spikes.json (잰 값).
# 연속 그림 원본은 RAW (기본 $TMPDIR/probe_raw, 저장소 밖).
set -u
R=$(cd "$(dirname "$0")/../.." && pwd)
[ $# -ge 2 ] || { sed -n '2,24p' "$0"; exit 2; }
PORT=$1; SRV=$(cd "$2" && pwd); shift 2
ALL="s1 s2 s3 s3x s13 s4 s5 s6 s9 s10 s11 s12"
SCENES=${*:-$ALL}
OUT=${OUT:-$R/dist/screenshots/m1}
RAW=${RAW:-${TMPDIR:-/tmp}/probe_raw}
mkdir -p "$OUT" "$RAW"
cd "$R" || exit 1
LOG="$SRV/console.log"
SESS=${SOULS_CLIENT_HOME:-$HOME/.cache/souls-client}/run/$PORT/session.json

analyze() {
  python3 - "$LOG" "$(cat "$RAW/start.offset" 2>/dev/null || echo 0)" "$RAW" "$OUT" <<'PY'
import glob, json, os, re, statistics, sys
import numpy as np
from PIL import Image
log, off, raw, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
with open(log, "rb") as f:
    f.seek(off)
    text = f.read().decode("utf-8", "replace")
lines = [m.group(1) for m in re.finditer(r"\[T\] Tester (.*)", text)]
# 서버를 다시 켜면 기록이 새로 시작한다: 그 전 줄은 RAW/archive_T.log 에 모아 둔다 (같은 장면은 나중 것이 이긴다)
arch = os.path.join(raw, "archive_T.log")
if os.path.exists(arch):
    lines = [l.rstrip("\n") for l in open(arch) if l.strip()] + lines
open(os.path.join(out, "ps_probe.log"), "w").write("\n".join(lines) + "\n")
def kv(s):
    d = {"_": s.split(" ", 1)[0]}
    for tok in s.split(" ")[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1); d[k] = v
    return d
seg, cur = {}, None
for s in lines:
    d = kv(s)
    if d["_"] == "PROBE_MARK":
        cur = d["label"]; seg[cur] = []; continue
    if cur: seg[cur].append(d)
R = {}
def ev(label, e=None):
    return [d for d in seg.get(label, []) if d["_"] == "PROBE" and (e is None or d.get("ev") == e)]
def other(label, prefix):
    return [d for d in seg.get(label, []) if d["_"].startswith(prefix)]
# ── S1 ──
for lab in ("s1_air_click", "s1_air_hold", "s1_floor_click", "s1_floor_hold"):
    if lab not in seg: continue
    it = [d for d in ev(lab, "interact") if d["action"].startswith("RIGHT")]
    seq = [f'{d["hand"]}/{d["action"]}@{d["t"]}' for d in it]
    mains = [int(d["t"]) for d in it if d["hand"] == "HAND"]
    gaps = [b - a for a, b in zip(mains, mains[1:])]
    R[lab] = {"n": len(it), "pairs_main_then_off": sum(1 for a, b in zip(it, it[1:]) if a["hand"] == "HAND" and b["hand"] == "OFF_HAND" and a["t"] == b["t"]),
              "main_tick_gaps": sorted(set(gaps)), "main_gap_median": statistics.median(gaps) if gaps else None,
              "actions": sorted({f'{d["hand"]}/{d["action"]}' for d in it}), "first": seq[:6],
              "cancelled": sorted({d["cancelled"] for d in it}), "useItem": sorted({d["useItem"] for d in it}),
              "swings": len(ev(lab, "swing"))}
# ── S2 ──
for lab in ("s2_hold15", "s2_hold30"):
    if lab not in seg: continue
    ms = [int(d["ms"]) for d in ev(lab, "swap")]
    gaps = [b - a for a, b in zip(ms, ms[1:])]
    # 반복 간격: 첫 반복부터 마지막까지를 고르게 나눈 값 (클라이언트는 그림마다 키를 읽어 한 틱에 둘이 오기도 한다: 낱 간격은 0~100ms 로 흔들린다)
    R[lab] = {"swaps": len(ms), "first_gap_ms": gaps[0] if gaps else None,
              "repeat_gap_ms_mean": round((ms[-1] - ms[1]) / (len(ms) - 2), 1) if len(ms) > 2 else None,
              "repeat_gap_ms_minmax": [min(gaps[1:]), max(gaps[1:])] if len(gaps) > 1 else None,
              "first_repeat_ticks": int(ev(lab, "swap")[1]["t"]) - int(ev(lab, "swap")[0]["t"]) if len(ms) > 1 else None,
              "parry_lines": len(other(lab, "PARRY")), "ticks": sorted({int(d["t"]) for d in ev(lab, "swap")})[:3]}
# ── S3x: 서버 휘두름 (srvswing) 뒤에 클라이언트가 보낸 swing·LEFT_CLICK_AIR (메아리) ──
for lab in sorted(k for k in seg if k.startswith("s3x_")):
    rows = [d for d in seg[lab] if d["_"] == "PROBE"]
    srv = next((d for d in rows if d.get("ev") == "srvswing"), None)
    if not srv: continue
    after = [d for d in rows if int(d["seq"]) > int(srv["seq"]) and d.get("ev") in ("swing", "interact")]
    R[lab + "_echo"] = {"server_hand": srv["hand"], "echo": [f'{d["ev"]}:{d["hand"]}/{d["action"]}@+{int(d["t"]) - int(srv["t"])}t,{int(d["ms"]) - int(srv["ms"])}ms' for d in after]}
# ── 연속 그림 (s3, s13, s12): 왼손 자리 (화면 왼쪽 아래) 와 주손 자리 (오른쪽 아래) 의 움직임 ──
def regions(w, h):
    # 왼손 자리 (왼쪽 아래에서 가운데까지) 와 주손 자리 (오른쪽 아래에서 가운데까지). 위 HUD·하늘 (구름이 움직인다) 과 아래 단축바는 뺀다
    return {"off": (0, int(h * 0.21), int(w * 0.60), int(h * 0.89)), "main": (int(w * 0.50), int(h * 0.21), w, int(h * 0.89))}
LABEL = (0.27, 0.55, 0.73, 0.65)  # 든 아이템 이름 (단축바 위, 틱 속도가 느리면 오래 남는다): 셈에서 뺀다
def burst(name, tick_rate, px=250):
    files = sorted(glob.glob(os.path.join(raw, name + "_[0-9][0-9].png")))
    tj = os.path.join(raw, name + "_times.json")
    if not files or not os.path.exists(tj): return None
    times = json.load(open(tj))
    t0 = times["t0"]; ts = times["shots"]
    ims = [np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in files]
    h, w = ims[0].shape
    mask = np.ones((h, w), bool)
    mask[int(h * LABEL[1]):int(h * LABEL[3]), int(w * LABEL[0]):int(w * LABEL[2])] = False
    res = {"frames": len(ims), "span_s": round(ts[-1] - ts[0], 2), "tick_rate": tick_rate}
    bgf = os.path.join(raw, name + ".bg")
    if os.path.exists(bgf):
        res["inputs"] = [(l.split()[1], round(float(l.split()[2]) - t0, 3)) for l in open(bgf) if l.startswith("BG ") and not l.split()[1].startswith("sleep")]
    # 앞 장과 달라진 화소 수 (바뀐 몫만: 순간이동 뒤 손 흔들림이 천천히 가라앉는 것은 장마다 작다)
    for k, (x0, y0, x1, y1) in regions(w, h).items():
        m = mask[y0:y1, x0:x1]
        d = [0] + [int(((np.abs(b[y0:y1, x0:x1] - a[y0:y1, x0:x1]) > 24) & m).sum()) for a, b in zip(ims, ims[1:])]
        mov = [i for i, v in enumerate(d) if v > px]
        runs = []
        for i in mov:
            if runs and i - runs[-1][1] <= 3: runs[-1][1] = i
            else: runs.append([i, i])
        # 길이: 움직인 첫 장 바로 앞 장부터 마지막 움직인 장 바로 뒤 장까지의 가운데 (장 사이 간격 몫을 반씩 더한다)
        def span(a, b):  # 장 a 는 a-1 과 a 사이에 움직였다: 움직임은 ts[a-1] 과 ts[a] 사이에 시작해 ts[b] 와 ts[b+1] 사이에 끝난다 (가운데를 쓴다)
            lo = (ts[a] + ts[a - 1]) / 2 if a > 0 else ts[a]
            hi = (ts[b] + ts[b + 1]) / 2 if b + 1 < len(ts) else ts[b]
            return lo, hi
        res[k] = [{"from_s": round(span(a, b)[0], 2), "to_s": round(span(a, b)[1], 2), "ticks": round((span(a, b)[1] - span(a, b)[0]) * tick_rate, 1),
                   "peak_px": max(d[a:b + 1])} for a, b in runs]
        res[k + "_px"] = d
    # 띠: 고른 장 (최대 12, 6 장씩 두 줄) 을 반으로 줄여서, 장마다 찍은 때 (초) 를 왼쪽 위에
    from PIL import ImageDraw
    pick = np.linspace(0, len(files) - 1, min(12, len(files))).round().astype(int)
    tw, th = w // 2, h // 2
    sheet = Image.new("RGB", (tw * 6, th * ((len(pick) + 5) // 6)))
    dr = ImageDraw.Draw(sheet)
    for n, i in enumerate(pick):
        t = Image.open(files[i]).convert("RGB").resize((tw, th))
        x, y = (n % 6) * tw, (n // 6) * th
        sheet.paste(t, (x, y))
        dr.rectangle((x, y, x + 74, y + 16), fill=(0, 0, 0))
        dr.text((x + 3, y + 2), "%.2fs #%d" % (ts[i], i), fill=(255, 255, 0))
    sheet.save(os.path.join(out, "ps_" + name + ".png"))
    res["sheet_frames_s"] = [round(ts[i], 2) for i in pick]
    # 떨어지며 치기: 좌클릭 바로 앞부터 10 장을 화면 가운데만 크게 (맞은 붉은 빛·치명타 별 입자가 보이는가)
    clicks = [t for a, t in res.get("inputs", []) if a == "click"]
    if name.startswith("s12_crit") and clicks:
        idx = [i for i in range(len(ts)) if ts[i] >= clicks[0] - 0.1][:10]
        cw, ch = w * 3 // 5, h * 3 // 5
        close = Image.new("RGB", ((cw // 2) * 5, (ch // 2) * 2))
        dc = ImageDraw.Draw(close)
        for n, i in enumerate(idx):
            t = Image.open(files[i]).convert("RGB").crop((w // 5, h // 10, w // 5 + cw, h // 10 + ch)).resize((cw // 2, ch // 2))
            x, y = (n % 5) * (cw // 2), (n // 5) * (ch // 2)
            close.paste(t, (x, y))
            dc.rectangle((x, y, x + 150, y + 16), fill=(0, 0, 0))
            dc.text((x + 3, y + 2), "%.2fs #%d click %.2fs" % (ts[i], i, clicks[0]), fill=(255, 255, 0))
        close.save(os.path.join(out, "ps_" + name + "_close.png"))
    return res
for name in sorted({os.path.basename(p)[:-11] for p in glob.glob(os.path.join(raw, "*_times.json"))}):
    tr = 5 if name.startswith(("s3_", "s3x_", "s13_", "s12_crit")) else 20
    b = burst(name, tr)
    if b: R["burst_" + name] = b
# ── S4 ──
def pos(d): return float(d["x"]), float(d["y"]), float(d["z"])
for lab in sorted(k for k in seg if k.startswith("s4_")):
    ps = [pos(d) for d in other(lab, "POS")]
    r = {"pos": ps}
    if len(ps) >= 2:
        r["walk_blocks"] = round(((ps[1][0] - ps[0][0]) ** 2 + (ps[1][2] - ps[0][2]) ** 2) ** 0.5, 3)
    if len(ps) >= 3: r["jump_dy_after"] = round(ps[2][1] - ps[1][1], 3)
    R[lab] = r
fov = {}
basep = os.path.join(out, "ps_s4_fov_none.png")
def zoom(img, s):
    W, H = img.size
    cw, ch = W / s, H / s
    return img.crop((round(W / 2 - cw / 2), round(H / 2 - ch / 2), round(W / 2 + cw / 2), round(H / 2 + ch / 2))).resize((W, H))
def mid(img):
    a = np.asarray(img, dtype=np.float32); h, w = a.shape
    return a[h // 4: h * 3 // 4, w // 4: w * 3 // 4]
if os.path.exists(basep):
    A = Image.open(basep).convert("L")
    for p in sorted(glob.glob(os.path.join(out, "ps_s4_fov_*.png"))):
        B = Image.open(p).convert("L")
        best = None
        for s in np.arange(1.0, 2.41, 0.01):
            # 좁아진 시야 (B 가 A 를 s 배 키운 꼴) 와 넓어진 시야 (A 가 B 를 s 배 키운 꼴) 를 둘 다 견준다
            for z, e in ((s, float(np.abs(mid(B) - mid(zoom(A, s))).mean())), (1 / s, float(np.abs(mid(A) - mid(zoom(B, s))).mean()))):
                if best is None or e < best[1]: best = (round(float(z), 3), round(e, 2))
        fov[os.path.basename(p)[10:-4]] = {"zoom_vs_none": best[0], "err": best[1]}
    R["s4_fov_zoom"] = fov
# ── S5, S11, S12: 줄 요약 ──
def brief(d):
    keep = ("ev", "type", "mode", "after", "hand", "action", "cancelled", "using", "raised", "aggressive", "off", "blocking", "in", "placed", "pose", "swimming",
            "t", "ms", "ticks", "dist", "sprinting", "target", "dmg", "crit", "why", "held", "reason", "walk", "base", "value")
    return d["_"] + " " + " ".join(f"{k}={d[k]}" for k in keep if k in d)
for lab in sorted(k for k in seg if k.startswith(("s5_", "s11_", "s12_", "s6_", "s9_", "s10_"))):
    R[lab] = [brief(d) for d in seg[lab] if not (d["_"] == "PROBE" and d.get("ev") in ("input", "move") and d.get("action") in ("none", "MOVE"))][:40]
# S12: 달리며 친 틱 앞뒤의 수평 이동량 (ev=move, 블록/틱)
for lab in ("s12_sprint_plain", "s12_sprint_cancel"):
    rows = seg.get(lab, [])
    at = next((int(d["t"]) for d in rows if d["_"] == "PROBE" and d.get("ev") == "attack"), None)
    mv = {int(d["t"]): float(d["v"]) for d in rows if d["_"] == "PROBE" and d.get("ev") == "move"}
    if at is not None and mv:
        R[lab + "_speed"] = {"attack_t": at, "v_by_offset": {str(k - at): round(v, 3) for k, v in sorted(mv.items()) if -4 <= k - at <= 6},
                             "sprint_toggles": [f'{d["action"]}@{int(d["t"]) - at}' for d in rows if d["_"] == "PROBE" and d.get("ev") == "sprint"]}
json.dump(R, open(os.path.join(out, "ps_spikes.json"), "w"), indent=1, ensure_ascii=False)
for k, v in R.items():
    if isinstance(v, dict): v = {a: b for a, b in v.items() if not a.endswith("_px")}
    print(k, json.dumps(v, ensure_ascii=False)[:900])
PY
}

if [ "$SCENES" = analyze ]; then analyze; exit 0; fi

DISP=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['display'])" "$SESS") || { echo "probe_shots: 켜 둔 클라이언트가 없다 ($SESS)"; exit 1; }
do_() { tools/client/run_client.sh --do "$PORT" "$@" 2>&1 | grep -E "SHOT|실패|찍은 간격" ; }
con() { tools/client/devserver.sh --cmd "$SRV" "$@"; sleep 0.3; }
inw() { con execute in minecraft:souls_world run "$@"; }
tst() { con execute as Tester run soulstest "$@"; }
mk() { tst probe mark "$1"; sleep 0.2; }
xdo() { DISPLAY=:$DISP xdotool "$@"; }
# bg <이름> <먼저 쉴 초> <동작...>: 연속 그림을 찍는 동안 뒤에서 누른다 (click = 왼쪽, key:<키>, sleep:<초>, tst:<soulstest 인수>
# = 서버 콘솔에서). 누른 때는 RAW/<이름>.bg
bg() {
  local name=$1 d=$2; shift 2
  : > "$RAW/$name.bg"
  ( sleep "$d"; for a in "$@"; do
      case $a in
        click) xdo mousedown 1; sleep 0.06; xdo mouseup 1 ;;
        key:*) xdo keydown "${a#key:}"; sleep 0.06; xdo keyup "${a#key:}" ;;
        sleep:*) sleep "${a#sleep:}" ;;
        tst:*) tst ${a#tst:} ;;
      esac
      echo "BG ${a// /_} $(date +%s.%N)" >> "$RAW/$name.bg"
    done ) &
}
# shot_burst <이름> <장수> <간격> [bg 인수...]: 앞 장 몇 개는 가만히 (bg 의 첫 쉼), 그 뒤 누름
shot_burst() {
  local name=$1 n=$2 gap=$3; shift 3
  rm -f "$RAW/${name}"_[0-9][0-9].png
  [ $# -gt 0 ] && bg "$name" "$@"
  do_ "burst:$RAW/$name:$n::1:$gap" | tail -1
  wait
}
want() { [[ " $SCENES " == *" $1 "* ]]; }
HOME_TP="200.5 101 -189.5"
home() { inw tp Tester $HOME_TP "${1:-180}" "${2:-0}"; }
gear() { tst give redin_guard_sword main; tst give parrying_dagger off; }

# 기록을 어디서부터 읽나: 처음 한 번 (FRESH=1 이면 새로). 장면을 다시 돌리면 같은 이름의 나중 것을 쓴다
{ [ "${FRESH:-0}" = 1 ] || [ ! -s "$RAW/start.offset" ]; } && wc -c < "$LOG" > "$RAW/start.offset"
# 서버를 다시 켜 기록이 짧아졌으면: 지난 줄을 archive_T.log 에 옮겨 두고 새 기록의 처음부터 읽는다
if [ "$(wc -c < "$LOG")" -lt "$(cat "$RAW/start.offset")" ]; then
  [ -s "$OUT/ps_probe.log" ] && cp "$OUT/ps_probe.log" "$RAW/archive_T.log"
  echo 0 > "$RAW/start.offset"
fi
con gamemode adventure Tester
con effect clear Tester
inw time set 6000
inw gamerule advance_time false 2>/dev/null
inw weather clear
con clear Tester
con tick rate 20
tst probe on
tst probe cancel none
tst probe fswing none
tst probe mob clear

if want s1; then
  gear; home 180 -90; do_ wait:1
  mk s1_air_click;  do_ mouse:right wait:1
  mk s1_air_hold;   do_ mdown:right wait:2 mup:right wait:0.6
  home 180 90; do_ wait:0.8
  mk s1_floor_click; do_ mouse:right wait:1
  mk s1_floor_hold;  do_ mdown:right wait:2 mup:right wait:0.6
  home
fi

if want s2; then
  gear; home; do_ wait:0.8
  mk s2_hold15; do_ hold:f:1.5 wait:0.6
  mk s2_hold30; do_ hold:f:3 wait:0.6
fi

if want s3; then
  gear; home; con tick rate 5; tst probe fswing off; do_ wait:2
  mk s3_f_only;          shot_burst s3_f_only 36 0.07 0.4 key:f
  do_ wait:1.5
  mk s3_click_f_fast;    shot_burst s3_click_f_fast 36 0.07 0.4 click sleep:0.1 key:f
  do_ wait:1.5
  mk s3_click_f_slow;    shot_burst s3_click_f_slow 40 0.07 0.4 click sleep:0.8 key:f
  do_ wait:1.5
  mk s3_f_click_fast;    shot_burst s3_f_click_fast 36 0.07 0.4 key:f sleep:0.1 click
  do_ wait:1.5
  mk s3_click_only;      shot_burst s3_click_only 30 0.07 0.4 click
  tst probe fswing none; con tick rate 20
fi

if want s3x; then
  # 주손 무기가 F 뒤에 화면 밑으로 내려가는 까닭 가르기, 서버 휘두름의 메아리: F 만 (서버 휘두름 없음) / 콘솔의 swingOffHand /
  # 콘솔의 swingMainHand (클라이언트가 자기 휘두름 패킷을 다시 보내는가)
  gear; home; con tick rate 5; tst probe fswing none; do_ wait:2
  mk s3x_f_noswing;  shot_burst s3x_f_noswing 36 0.07 0.4 key:f
  do_ wait:2
  mk s3x_srv_off;    shot_burst s3x_srv_off 36 0.07 0.4 "tst:probe swing off"
  do_ wait:2
  mk s3x_srv_main;   shot_burst s3x_srv_main 36 0.07 0.4 "tst:probe swing main"
  con tick rate 20; do_ wait:1
  # 20틱에서 메아리가 몇 틱 뒤에 오는가 (세 번)
  for i in 1 2 3; do mk "s3x_echo_main_$i"; tst probe swing main; do_ wait:0.8; mk "s3x_echo_off_$i"; tst probe swing off; do_ wait:0.8; done
fi

if want s13; then
  home; con tick rate 5; tst probe fswing off; tst give parrying_dagger off; do_ wait:1.5
  # 주손 바꾸기 (콘솔 /item: 바닐라 성분 그대로). 각 꾸밈에서 F (왼손) 와 좌클릭 (주손) 을 따로 찍는다
  for v in whack20 stab20 empty offstab20; do
    case $v in
      whack20) con item replace entity Tester weapon.mainhand with "minecraft:flint[minecraft:swing_animation={type:'whack',duration:20}]" ;;
      stab20) con item replace entity Tester weapon.mainhand with "minecraft:flint[minecraft:swing_animation={type:'stab',duration:20}]" ;;
      empty) con item replace entity Tester weapon.mainhand with minecraft:air ;;
      offstab20) tst give redin_guard_sword main
                 con item replace entity Tester weapon.offhand with "minecraft:flint[minecraft:swing_animation={type:'stab',duration:20}]" ;;
    esac
    do_ wait:1.2
    mk "s13_${v}_f";     shot_burst "s13_${v}_f" 60 0.08 0.4 key:f
    do_ wait:1
    if [ "$v" != empty ]; then
      mk "s13_${v}_click"; shot_burst "s13_${v}_click" 60 0.08 0.4 click
      do_ wait:1
    fi
  done
  tst probe fswing none; con tick rate 20
fi

if want s4; then
  gear
  LANE="190.5 101 -192.5"
  for v in none slow25 slow50 root slowness2 walk50 walkroot; do
    con attribute Tester minecraft:movement_speed modifier remove souls:probe
    con attribute Tester minecraft:jump_strength modifier remove souls:probe
    con effect clear Tester
    inw tp Tester $LANE -90 0
    case $v in
      slow25) con attribute Tester minecraft:movement_speed modifier add souls:probe -0.25 add_multiplied_total ;;
      slow50) con attribute Tester minecraft:movement_speed modifier add souls:probe -0.5 add_multiplied_total ;;
      root) con attribute Tester minecraft:movement_speed modifier add souls:probe -1 add_multiplied_total
            con attribute Tester minecraft:jump_strength modifier add souls:probe -1 add_multiplied_total ;;
      slowness2) con effect give Tester minecraft:slowness 30 1 true ;;
      # Player.setWalkSpeed: 걷기 속도와 속성 바탕값을 함께 (시야 셈은 속성 ÷ 걷기 속도)
      walk50) tst probe walkspeed 0.1 ;;
      walkroot) tst probe walkspeed 0
                con attribute Tester minecraft:jump_strength modifier add souls:probe -1 add_multiplied_total ;;
    esac
    do_ wait:1.5 shot:$OUT/ps_s4_fov_$v
    mk "s4_$v"
    tst pos
    do_ walk:1.0 wait:0.6
    tst pos
    do_ key:space wait:0.15
    tst pos
    do_ wait:0.8
  done
  tst probe walkspeed 0.2
  con attribute Tester minecraft:movement_speed modifier add souls:probe -0.5 add_multiplied_total
  inw tp Tester $LANE -90 0
  do_ wait:1 down:w
  shot_burst s4_walk50 24 0.05
  do_ up:w
  con attribute Tester minecraft:movement_speed modifier remove souls:probe
  con attribute Tester minecraft:jump_strength modifier remove souls:probe
  con effect clear Tester
fi

if want s5; then
  tst give redin_guard_sword main; tst give redin_guard_shield off; home; do_ wait:1
  mk s5_guard_tap;  do_ mdown:right wait:0.7 shot:$OUT/ps_s5_guard hold:Shift_L:0.1 wait:0.8 mup:right wait:0.8
  mk s5_guard_hold; do_ mdown:right wait:0.5 hold:Shift_L:0.6 wait:0.4 mup:right wait:0.8
  con item replace entity Tester weapon.offhand with minecraft:air
  con item replace entity Tester weapon.mainhand with "minecraft:potion[minecraft:potion_contents={potion:'minecraft:water'}]"
  do_ wait:1
  mk s5_drink_tap;  do_ mdown:right wait:0.5 shot:$OUT/ps_s5_drink hold:Shift_L:0.1 wait:1.8 mup:right wait:1
  con item replace entity Tester weapon.mainhand with "minecraft:potion[minecraft:potion_contents={potion:'minecraft:water'}]"
  do_ wait:0.8
  mk s5_drink_release; do_ mdown:right wait:0.5 hold:Shift_L:0.1 mup:right wait:1
  home
fi

if want s6; then
  inw kill @e[tag=souls_probe]
  inw tp Tester 192.5 101 -195.5 -90 0
  inw summon minecraft:husk 196.8 101 -195.5 "{NoAI:1b,Silent:1b,Tags:[\"souls_ent\",\"souls_probe\"],Rotation:[90f,0f]}"
  con item replace entity Tester weapon.offhand with minecraft:air
  con item replace entity Tester weapon.mainhand with minecraft:flint
  do_ wait:1.2 shot:$OUT/ps_s6_aim_40
  mk s6_plain_40;  do_ mouse:left wait:0.9
  con item replace entity Tester weapon.mainhand with "minecraft:flint[minecraft:attack_range={max_reach:4.2}]"
  do_ wait:0.6
  mk s6_range_40;  do_ mouse:left wait:0.9
  tst give redin_guard_sword main
  do_ wait:0.6
  mk s6_sword_40;  do_ mouse:left wait:0.9
  con item replace entity Tester weapon.mainhand with "minecraft:flint[minecraft:attack_range={max_reach:4.2}]"
  inw tp @e[tag=souls_probe,type=minecraft:husk] 197.1 101 -195.5 90 0
  do_ wait:0.8
  mk s6_range_43;  do_ mouse:left wait:0.9
  inw tp @e[tag=souls_probe,type=minecraft:husk] 196.6 101 -195.5 90 0
  do_ wait:0.8
  mk s6_range_38;  do_ mouse:left wait:0.9
  inw tp @e[tag=souls_probe,type=minecraft:husk] 195.6 101 -195.5 90 0
  con item replace entity Tester weapon.mainhand with minecraft:flint
  do_ wait:0.8
  mk s6_plain_28;  do_ mouse:left wait:0.9
  inw kill @e[tag=souls_probe]
  home
fi

if want s9; then
  home; gear; do_ wait:0.5
  for v in "husk idle" "husk block" "husk aggr" "skeleton block" "zombie block shield"; do
    tst probe mob clear
    mk "s9_${v// /_}"
    tst probe mob $v
    do_ wait:1.4 shot:$OUT/ps_s9_${v// /_}
  done
  tst probe mob clear
fi

if want s10; then
  home; gear; do_ wait:0.5
  mk s10_crawl
  tst probe crawl 200
  do_ wait:1.2 shot:$OUT/ps_s10_fp key:F5 wait:1 shot:$OUT/ps_s10_back key:F5 wait:1 shot:$OUT/ps_s10_front key:F5 wait:0.5
  do_ wait:8
  home
fi

if want s11; then
  gear; home; do_ wait:0.6
  mk s11_inventory; do_ down:Shift_L wait:0.6 key:e wait:1 shot:$OUT/ps_s11_inventory key:Escape wait:0.6 up:Shift_L wait:0.6
  mk s11_chat;      do_ down:Shift_L wait:0.6 key:t wait:1 key:Escape wait:0.6 up:Shift_L wait:0.6
  mk s11_inv_release; do_ down:Shift_L wait:0.6 key:e wait:0.6 up:Shift_L wait:0.6 key:Escape wait:0.8
fi

if want s12; then
  gear
  LANE="190.5 101 -192.5"
  inw kill @e[tag=souls_probe]
  inw summon minecraft:husk 195.3 101 -192.5 "{NoAI:1b,Silent:1b,Tags:[\"souls_ent\",\"souls_probe\"],Rotation:[90f,0f]}"
  tst probe move on
  for v in plain cancel; do
    [ $v = cancel ] && tst probe cancel attack
    inw tp Tester $LANE -90 0
    do_ wait:1.2
    mk "s12_sprint_$v"
    do_ down:ctrl+w wait:0.42 mouse:left wait:0.7 up:ctrl+w wait:0.6
  done
  tst probe move off
  tst probe cancel none
  # 떨어지며 치기 (/tick rate 5): 허스크 2칸 앞에서 20° 내려다보며 뛰어, 내려오는 동안 좌클릭
  # 그냥 부싯돌 (공격 속도 4: 5틱이면 다 찬다. 공격 세기가 0.9 아래면 치명타가 아니다)
  con item replace entity Tester weapon.mainhand with minecraft:flint
  con tick rate 5
  for v in plain cancel; do
    [ $v = cancel ] && tst probe cancel attack
    inw tp Tester 192.9 101 -192.5 -90 20
    do_ wait:3.5
    mk "s12_crit_$v"
    shot_burst "s12_crit_$v" 50 0.06 0.3 key:space sleep:1.5 click
    do_ wait:1.5
  done
  tst probe cancel none
  con tick rate 20
  inw kill @e[tag=souls_probe]
  home
fi

con tick rate 20
tst probe off
analyze
