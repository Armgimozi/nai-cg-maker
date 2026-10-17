package kr.labyrinth.village;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 구역 배치 {@code village/districts/<id>.json} (0.3.6 광산 마을 — tools/village/district_mine.py 를 build_all.py 가 씀). 순수 데이터.
 * <p>
 * 좌표는 마을 좌표다 (layout.json 과 같은 틀: 마을 중심 (0, 0), 앞 = 북). 그래서 시드·회전이 다른 마을에도 큰길 끝에 같은 모양으로
 * 붙는다. {@link #place} 가 자리(site) 하나를 월드에 펼친 배치({@link Placement}: 월드 방향으로 돌린 Layout + 원점)를 만든다 —
 * 계획기는 그것을 마스크 모드({@link Planner.Mask})·회전 0 으로 계획한다.
 */
public final class DistrictLayout {

    /** 자리: 마을 좌표로 옮기는 양, 바꿀 길(마을 좌표, 옮기지 않음), 뺄 조각 순번. */
    public record Site(String id, int dx, int dz, Map<Integer, List<int[]>> replacePaths, Set<Integer> drop) {}

    /** 월드에 펼친 배치. layout 좌표 = 월드 − (ox, oz), 회전 0 (조각 정면 = 월드 방향). turns = 마을 회전(+ here 방향). */
    public record Placement(String site, int ox, int oz, int turns, Layout layout, int[] junction) {}

    public final String id, name;
    public final int order;
    public final int r, b;
    public final int maxFill, foundationDepth, smallWater, safeMargin;
    public final List<Blueprint.Weighted> foundationMix;
    public final Map<String, String> npcNames;
    public final String fingerprint;
    /** 배포 월드 마을 build_id 들 (지문을 쓰는 월드). */
    public final List<String> shippedBuilds;
    public final List<Layout.Entry> pieces;
    public final List<Layout.PathDef> paths;
    public final Map<String, List<Blueprint.Weighted>> pathStyles;
    public final List<Site> sites;

    private DistrictLayout(String id, String name, int order, int r, int b, int maxFill, int foundationDepth, int smallWater,
                           int safeMargin, List<Blueprint.Weighted> foundationMix, Map<String, String> npcNames, String fingerprint,
                           List<String> shippedBuilds, List<Layout.Entry> pieces, List<Layout.PathDef> paths,
                           Map<String, List<Blueprint.Weighted>> styles, List<Site> sites) {
        this.id = id;
        this.name = name;
        this.order = order;
        this.r = r;
        this.b = b;
        this.maxFill = maxFill;
        this.foundationDepth = foundationDepth;
        this.smallWater = smallWater;
        this.safeMargin = safeMargin;
        this.foundationMix = List.copyOf(foundationMix);
        this.npcNames = Collections.unmodifiableMap(npcNames);
        this.fingerprint = fingerprint;
        this.shippedBuilds = List.copyOf(shippedBuilds);
        this.pieces = List.copyOf(pieces);
        this.paths = List.copyOf(paths);
        this.pathStyles = Collections.unmodifiableMap(styles);
        this.sites = List.copyOf(sites);
    }

    public Site site(String siteId) {
        for (Site s : sites) if (s.id().equals(siteId)) return s;
        return null;
    }

    public List<String> siteIds() {
        List<String> out = new ArrayList<>();
        for (Site s : sites) out.add(s.id());
        return out;
    }

    public static DistrictLayout parse(String json) {
        JsonObject o;
        try {
            o = JsonParser.parseString(json).getAsJsonObject();
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("구역 json 형식 오류: " + e.getMessage());
        }
        List<String> problems = new ArrayList<>();
        String id = Blueprint.str(o, "id", null);
        if (id == null || !id.matches("[a-z0-9_]+")) throw new IllegalArgumentException("구역 id 없음/형식 오류: " + id);
        if (!"village".equals(Blueprint.str(o, "frame", "village"))) problems.add("frame 은 village 만");
        JsonObject mask = o.has("mask") && o.get("mask").isJsonObject() ? o.getAsJsonObject("mask") : new JsonObject();
        JsonObject opt = o.has("options") && o.get("options").isJsonObject() ? o.getAsJsonObject("options") : new JsonObject();
        int r = intOr(mask, "R", 4), b = intOr(mask, "B", 6);
        if (r < 1 || r > 16 || b < 1 || b > 24) problems.add("mask R " + r + " · B " + b + " (1..16 · 1..24)");
        Map<String, String> npcNames = new LinkedHashMap<>();
        if (o.has("npcs") && o.get("npcs").isJsonObject()) {
            for (Map.Entry<String, JsonElement> e : o.getAsJsonObject("npcs").entrySet()) npcNames.put(e.getKey(), e.getValue().getAsString());
        }
        List<String> builds = new ArrayList<>();
        if (o.has("shipped") && o.get("shipped").isJsonObject()) {
            JsonArray ba = Blueprint.arr(o.getAsJsonObject("shipped"), "build_ids");
            if (ba != null) for (JsonElement e : ba) builds.add(e.getAsString());
        }
        List<Layout.Entry> pieces = new ArrayList<>();
        JsonArray pa = Blueprint.arr(o, "pieces");
        if (pa == null || pa.isEmpty()) problems.add("pieces 없음");
        else for (JsonElement e : pa) {
            JsonObject p = e.getAsJsonObject();
            String piece = Blueprint.str(p, "piece", null);
            JsonArray at = Blueprint.arr(p, "at");
            Dir front = Dir.parse(Blueprint.str(p, "front", "north"));
            if (piece == null || at == null || at.size() != 2 || front == null) {
                problems.add("pieces[" + pieces.size() + "] piece/at/front 오류");
                continue;
            }
            Layout.Opts opts = Layout.Opts.NONE;
            Integer mf = p.has("max_fill") ? Integer.valueOf(p.get("max_fill").getAsInt()) : null;
            List<Integer> fr = new ArrayList<>();
            JsonArray fra = Blueprint.arr(p, "floor_ref");
            if (fra != null) for (JsonElement fe : fra) fr.add(fe.getAsInt());
            JsonArray fn = Blueprint.arr(p, "floor_near");
            String tag = Blueprint.str(p, "tag", null);
            int idx = pieces.size();
            for (int fv : fr) if (fv < 0 || fv >= idx) problems.add("pieces[" + idx + "] floor_ref " + fv + " 는 앞 조각 순번이어야 함");
            int nearRef = -1, nearDelta = 0;
            if (fn != null) {
                if (fn.size() != 2) problems.add("pieces[" + idx + "] floor_near 는 [조각, 차]");
                else {
                    nearRef = fn.get(0).getAsInt();
                    nearDelta = fn.get(1).getAsInt();
                    if (nearRef < 0 || nearRef >= idx || nearDelta < 0) problems.add("pieces[" + idx + "] floor_near " + fn + " 오류");
                }
            }
            if (mf != null && (mf < 1 || mf > 16)) problems.add("pieces[" + idx + "] max_fill " + mf + " (1..16)");
            if (mf != null || !fr.isEmpty() || nearRef >= 0 || tag != null) opts = new Layout.Opts(mf, fr, nearRef, nearDelta, tag);
            pieces.add(new Layout.Entry(idx, piece, at.get(0).getAsInt(), at.get(1).getAsInt(), front,
                    p.has("dy") ? p.get("dy").getAsInt() : null, p.has("slack") ? p.get("slack").getAsInt() : null, opts));
        }
        List<Layout.PathDef> paths = new ArrayList<>();
        JsonArray ps = Blueprint.arr(o, "paths");
        if (ps != null) for (JsonElement e : ps) {
            JsonObject p = e.getAsJsonObject();
            List<int[]> pts = points(Blueprint.arr(p, "points"));
            if (pts.size() < 2) {
                problems.add("paths[" + paths.size() + "] 점이 2개 미만");
                continue;
            }
            int width = p.has("width") ? p.get("width").getAsInt() : 3;
            int follow = p.has("follow") ? Math.max(0, Math.min(Planner.PATH_FOLLOW_MAX, p.get("follow").getAsInt())) : Planner.PATH_FOLLOW;
            paths.add(new Layout.PathDef(paths.size(), pts, Math.max(1, Math.min(9, width)), Blueprint.str(p, "style", "main"), follow));
        }
        Map<String, List<Blueprint.Weighted>> styles = new LinkedHashMap<>();
        if (o.has("path_styles") && o.get("path_styles").isJsonObject()) {
            for (Map.Entry<String, JsonElement> e : o.getAsJsonObject("path_styles").entrySet()) {
                styles.put(e.getKey(), Blueprint.weighted(e.getValue().getAsJsonArray()));
            }
        }
        List<Site> sites = new ArrayList<>();
        JsonArray sa = Blueprint.arr(o, "sites");
        if (sa == null || sa.isEmpty()) problems.add("sites 없음");
        else for (JsonElement e : sa) {
            JsonObject so = e.getAsJsonObject();
            String sid = Blueprint.str(so, "id", null);
            JsonArray sh = Blueprint.arr(so, "shift");
            if (sid == null || !sid.matches("[a-z0-9_]+")) {
                problems.add("sites[" + sites.size() + "] id 오류");
                continue;
            }
            Map<Integer, List<int[]>> rep = new LinkedHashMap<>();
            if (so.has("replace_paths") && so.get("replace_paths").isJsonObject()) {
                for (Map.Entry<String, JsonElement> re : so.getAsJsonObject("replace_paths").entrySet()) {
                    List<int[]> pts = points(re.getValue().getAsJsonArray());
                    int idx;
                    try {
                        idx = Integer.parseInt(re.getKey());
                    } catch (NumberFormatException ex) {
                        problems.add("sites." + sid + ".replace_paths 키 " + re.getKey());
                        continue;
                    }
                    if (idx < 0 || idx >= paths.size() || pts.size() < 2) problems.add("sites." + sid + ".replace_paths." + idx + " 오류");
                    else rep.put(idx, pts);
                }
            }
            Set<Integer> drop = new LinkedHashSet<>();
            JsonArray da = Blueprint.arr(so, "drop");
            if (da != null) for (JsonElement d : da) drop.add(d.getAsInt());
            sites.add(new Site(sid, sh != null && sh.size() == 2 ? sh.get(0).getAsInt() : 0, sh != null && sh.size() == 2 ? sh.get(1).getAsInt() : 0,
                    rep, drop));
        }
        List<Blueprint.Weighted> fmix = Blueprint.weighted(Blueprint.arr(o, "foundation_mix"));
        if (!problems.isEmpty()) throw new IllegalArgumentException("구역 " + id + ": " + String.join(" · ", problems));
        return new DistrictLayout(id, Blueprint.str(o, "name", id), intOr(o, "order", 100), r, b,
                intOr(opt, "max_fill", Planner.PAD_LIMIT), intOr(opt, "foundation_depth", Planner.CAVE_DEPTH), intOr(opt, "fill_small_water_max", 0),
                intOr(o, "safe_margin", 8), fmix, npcNames, Blueprint.str(o, "fingerprint", id + ".fp"), builds, pieces, paths, styles, sites);
    }

    private static int intOr(JsonObject o, String k, int def) {
        return o.has(k) && o.get(k).isJsonPrimitive() ? o.get(k).getAsInt() : def;
    }

    private static List<int[]> points(JsonArray a) {
        List<int[]> out = new ArrayList<>();
        if (a != null) for (JsonElement q : a) {
            int[] v = Blueprint.ints(q.getAsJsonArray());
            if (v.length == 2) out.add(v);
        }
        return out;
    }

    // ── 펼치기 ───────────────────────────────────────────────────────────

    /** 길 0 의 첫 점 (마을 좌표) — 마을 큰길 끝에 붙는 자리. here 명령의 기준. */
    public int[] junctionVillage() { return paths.isEmpty() ? new int[] {0, 0} : paths.get(0).points().get(0).clone(); }

    /**
     * 자리 하나를 마을 중심 (vx, vz) · 마을 회전 turns 로 월드에 펼친다.
     * @param styles 마을 길 스타일 (구역 스타일이 덮어씀)
     */
    public Placement place(Site site, int vx, int vz, int turns, Map<String, List<Blueprint.Weighted>> styles, Map<String, Blueprint> bps) {
        int t = Math.floorMod(turns, 4);
        // 조각: 마을 좌표 → 월드 상자 (Planner 와 같은 공식) → 월드 방향
        record W(Layout.Entry e, int x0, int z0, int w2, int d2, Dir front) {}
        List<W> ws = new ArrayList<>();
        int bx0 = Integer.MAX_VALUE, bz0 = Integer.MAX_VALUE, bx1 = Integer.MIN_VALUE, bz1 = Integer.MIN_VALUE;
        for (Layout.Entry e : pieces) {
            if (site.drop().contains(e.index())) continue;
            Blueprint bp = bps.get(e.piece());
            if (bp == null) throw new IllegalArgumentException("구역 " + id + ": 조각 " + e.piece() + " 청사진 없음");
            int[] vd = Rot.dims(bp.w, bp.d, e.front().turns());
            int ax = e.atX() + site.dx(), az = e.atZ() + site.dz();
            int lx0 = ax - vd[0] / 2, lz0 = az - vd[1] / 2;
            int[] a = Rot.around(lx0, lz0, t), c = Rot.around(lx0 + vd[0] - 1, lz0 + vd[1] - 1, t);
            int x0 = vx + Math.min(a[0], c[0]), z0 = vz + Math.min(a[1], c[1]);
            int[] wd = Rot.dims(bp.w, bp.d, e.front().turns() + t);
            ws.add(new W(e, x0, z0, wd[0], wd[1], e.front().rotate(t)));
            bx0 = Math.min(bx0, x0);
            bz0 = Math.min(bz0, z0);
            bx1 = Math.max(bx1, x0 + wd[0] - 1);
            bz1 = Math.max(bz1, z0 + wd[1] - 1);
        }
        List<List<int[]>> wpaths = new ArrayList<>();
        for (Layout.PathDef p : paths) {
            List<int[]> src = site.replacePaths().get(p.index());
            List<int[]> out = new ArrayList<>();
            for (int[] q : src != null ? src : p.points()) {
                int qx = q[0] + (src != null ? 0 : site.dx()), qz = q[1] + (src != null ? 0 : site.dz());
                int[] rr = Rot.around(qx, qz, t);
                out.add(new int[] {vx + rr[0], vz + rr[1]});
                bx0 = Math.min(bx0, vx + rr[0]);
                bz0 = Math.min(bz0, vz + rr[1]);
                bx1 = Math.max(bx1, vx + rr[0]);
                bz1 = Math.max(bz1, vz + rr[1]);
            }
            wpaths.add(out);
        }
        int ox = Math.floorDiv(bx0 + bx1, 2), oz = Math.floorDiv(bz0 + bz1, 2);
        // 자리마다 뺀 조각이 있으면 순번이 당겨진다 → floor_ref·floor_near 도 새 순번으로 (없어진 조각은 뺌)
        Map<Integer, Integer> renum = new java.util.HashMap<>();
        for (int i = 0; i < ws.size(); i++) renum.put(ws.get(i).e().index(), i);
        List<Layout.Entry> le = new ArrayList<>();
        for (W w : ws) {
            Layout.Opts o = w.e().opts().remap(r -> renum.getOrDefault(r, -1));
            le.add(new Layout.Entry(le.size(), w.e().piece(), w.x0() - ox + w.w2() / 2, w.z0() - oz + w.d2() / 2, w.front(), w.e().dy(), w.e().slack(), o));
        }
        List<Layout.PathDef> lp = new ArrayList<>();
        for (int i = 0; i < wpaths.size(); i++) {
            List<int[]> pts = new ArrayList<>();
            for (int[] q : wpaths.get(i)) pts.add(new int[] {q[0] - ox, q[1] - oz});
            Layout.PathDef def = paths.get(i);
            lp.add(new Layout.PathDef(i, pts, def.width(), def.style(), def.follow()));
        }
        Map<String, List<Blueprint.Weighted>> st = new LinkedHashMap<>(styles == null ? Map.of() : styles);
        st.putAll(pathStyles);
        Layout layout = Layout.of(name, 8, b, le, lp, st);
        int[] j = wpaths.isEmpty() ? new int[] {ox, oz} : wpaths.get(0).get(0).clone();
        return new Placement(site.id(), ox, oz, t, layout, j);
    }

    /**
     * 관리자가 고른 자리 (/labadmin village district build mine here [방향]): 길 0 첫 점이 (jx, jz), 구역이 dir 쪽으로 펼쳐진다.
     * 배포 월드의 east 는 dir = 동쪽 (마을 좌표 남쪽 = 마을 회전으로 돌린 쪽).
     */
    public Placement placeHere(int jx, int jz, Dir dir, Map<String, List<Blueprint.Weighted>> styles, Map<String, Blueprint> bps) {
        int t = Math.floorMod(dir.turns() - Dir.SOUTH.turns(), 4);
        int[] jv = junctionVillage();
        int[] rr = Rot.around(jv[0], jv[1], t);
        Site here = new Site("here", 0, 0, Map.of(), Set.of());
        Placement p = place(here, jx - rr[0], jz - rr[1], t, styles, bps);
        return p;
    }
}
