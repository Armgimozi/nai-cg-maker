"""10채 배치 (owner: '10채만 해') — design036/plots/plots_spec.json 에서 3번(마을이 다듬은 칸 위, review R1)과
9번(광장에서 가장 먼 집)을 빼고 1..10 으로 다시 번호를 매긴다. 우물길은 서쪽 끝(옛 9번 앞)을 줄인다.
옛 3번 자리는 '골목 마당'(벤치·화단·등불, 땅은 그대로)이 된다.
usage: python3 -I make_spec10.py <plots_spec.json> <out plots10_spec.json>"""
import sys, json, copy
src, out = sys.argv[1:3]
S = json.load(open(src))
D = copy.deepcopy(S)
DROP = {3, 9}
keep = [p for p in S["plots"] if p["id"] not in DROP]
plots = []
for n, p in enumerate(keep, 1):
    q = copy.deepcopy(p)
    q["old_id"] = p["id"]
    q["id"] = n
    plots.append(q)
D["plots"] = plots
site = D["site"]
# 우물길: 옛 9번 앞(x -179..-165)을 뺀다 — 8번(옛 10) 서쪽 생울타리 x -164 부터
for st in site["streets"]:
    if st["name"] == "우물길":
        st["box"] = [-164, 99, -115, 103]
site["district_box"] = [-179, 47, -115, 103]
site["safe_boxes_2d"] = [[-179, 47, -115, 108], [-145, 26, -138, 46]]
# 골목 마당 (옛 3번 자리): 땅은 그대로, 장식만 (마을이 다듬은 칸 z 47..49 를 피해 z 52 이후)
site["yard"] = {"name": "골목 마당", "box": [-144, 48, -131, 61], "keep_ground": True,
                "decos": [{"piece": "bench", "box": [-141, 58, -139, 58], "front": "south"},
                          {"piece": "flower_bed", "box": [-137, 55, -135, 57], "front": "south"},
                          {"piece": "lamp_post_small", "box": [-133, 60, -133, 60], "front": "south"}]}
for d in site["decos"]:
    if d["piece"] == "signpost_home":
        d["note"] = "광장 남쪽 끝 골목 어귀: '등불 골목 — 집 1~10번지 · 관리인'"
    if d["piece"] == "lamp_post_small" and d["box"][:2] == [-130, 62]:
        d["note"] = "골목 마당·3번지 사이"
    if d["piece"] == "lamp_post_small" and d["box"][:2] == [-164, 98]:
        d["note"] = "8번지 서쪽 모서리 (우물길 서쪽 끝)"
D["version"] = "0.3.7-plots10"
D["note10"] = "3번(R1: 마을이 다듬은 칸 위)·9번(광장에서 가장 멂, 깎기 179칸) 뺌 → 1..10 다시 번호. 옛 번호 = old_id"
json.dump(D, open(out, "w"), ensure_ascii=False, indent=1)
for p in plots:
    print(p["id"], "old", p["old_id"], p["box"], "pad", p["pad_y"], "gate", p["gate"], p["front"])
