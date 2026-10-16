package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 마을 둘레 바닐라 월드 경계 (config wild.border · border_margin, 0.3.5.1) — 순수 함수 (테스트: WildBorderTest).
 * <p>
 * 경계 = (마을 중심 ± radius 상자) ∪ (모든 보호 상자) 를 감싸는 상자 + margin 칸, 그 상자의 가운데를 중심으로 긴 쪽에 맞춘 정사각형.
 * 블록 좌표 x0..x1 은 x0 ~ x1+1 의 땅을 덮는다 (블록 가운데가 아니라 모서리 기준). 보호 상자가 늘면(0.3.6 광산 구역 등) 경계도 저절로 넓어진다.
 * <p>
 * {@link #decide} — 지금 경계·우리가 정한 기록·켬/끔으로 할 일을 정한다. 관리자가 /worldborder 로 직접 정한 경계는 덮어쓰지 않는다.
 */
public final class WildBorder {

    private WildBorder() {}

    /** 바닐라 기본 경계 크기 (59,999,968). */
    public static final double VANILLA_SIZE = 5.9999968E7;
    /** 같은 경계로 보는 오차 (블록). */
    static final double EPS = 0.01;
    /** 우리가 정할 때 쓰는 경고 거리 (경계 몇 칸 앞부터 화면 가장자리가 붉어짐). */
    public static final int WARNING_DISTANCE = 6;
    /** 바닐라 기본 경고 거리. */
    public static final int VANILLA_WARNING = 5;

    /** 정사각형 경계: 중심 (x, z), 한 변 size, 경고 거리. */
    public record Square(double x, double z, double size, int warning) {
        public double half() { return size / 2; }

        public double minX() { return x - half(); }
        public double maxX() { return x + half(); }
        public double minZ() { return z - half(); }
        public double maxZ() { return z + half(); }

        /** 점 (x, z) 가 안인가 (경계 위 포함). */
        public boolean contains(double px, double pz) {
            return px >= minX() - EPS && px <= maxX() + EPS && pz >= minZ() - EPS && pz <= maxZ() + EPS;
        }

        /** 블록 상자 (x0..x1, z0..z1 블록) 가 통째로 안인가. */
        public boolean containsBlocks(int x0, int z0, int x1, int z1) {
            return contains(Math.min(x0, x1), Math.min(z0, z1)) && contains(Math.max(x0, x1) + 1, Math.max(z0, z1) + 1);
        }

        /** 중심·크기가 같은가 (경고 거리는 보지 않음). */
        public boolean same(Square o) {
            return o != null && Math.abs(x - o.x) < EPS && Math.abs(z - o.z) < EPS && Math.abs(size - o.size) < EPS;
        }

        /** 바닐라 기본 크기(또는 그만큼 큰) 경계 = 아무도 정하지 않은 경계. */
        public boolean vanillaDefault() { return size >= VANILLA_SIZE - 1; }

        public Square withWarning(int w) { return new Square(x, z, size, w); }
    }

    /**
     * 마을 경계 계산.
     * @param center 마을 중심 [x, y, z]
     * @param radius 마을 반경 (블록)
     * @param protect 보호 상자 (블록 좌표, 양끝 포함)
     * @param margin 가장자리에서 더 (블록)
     */
    public static Square compute(int[] center, int radius, List<VillageMeta.Box> protect, int margin) {
        int r = Math.max(0, radius);
        int x0 = center[0] - r, x1 = center[0] + r, z0 = center[2] - r, z1 = center[2] + r;
        if (protect != null) for (VillageMeta.Box b : protect) {
            x0 = Math.min(x0, Math.min(b.x0(), b.x1()));
            x1 = Math.max(x1, Math.max(b.x0(), b.x1()));
            z0 = Math.min(z0, Math.min(b.z0(), b.z1()));
            z1 = Math.max(z1, Math.max(b.z0(), b.z1()));
        }
        // 블록 x0..x1 = 땅 x0 ~ x1+1
        double minX = x0, maxX = x1 + 1, minZ = z0, maxZ = z1 + 1;
        double half = Math.max(maxX - minX, maxZ - minZ) / 2 + Math.max(0, margin);
        return new Square((minX + maxX) / 2, (minZ + maxZ) / 2, half * 2, WARNING_DISTANCE);
    }

    public static Square compute(VillageMeta m, int margin) {
        return compute(m.center, m.radius, m.protect, margin);
    }

    /** 마을 + 구역(0.3.6.1 광산 마을 — 지은 자리가 east 든 south_east 든 here 든) 보호 상자를 함께 감싼다. */
    public static Square compute(VillageMeta m, List<VillageMeta> districts, int margin) {
        List<VillageMeta.Box> all = new ArrayList<>(m.protect);
        if (districts != null) for (VillageMeta d : districts) if (d != null) all.addAll(d.protect);
        return compute(m.center, m.radius, all, margin);
    }

    /** 우리가 정한 경계 기록: 우리가 놓은 것(ours)과 그 전에 있던 것(previous — 끌 때 되돌림). */
    public record Record(Square ours, Square previous) {}

    public enum Action {
        /** 아무것도 안 함. */
        NONE,
        /** target 으로 정함. */
        APPLY,
        /** previous 로 되돌림. */
        RESTORE,
        /** 관리자가 따로 정한 경계 — 그대로 둠 (기록만 버림). */
        ADMIN,
        /** 끈 사이 관리자가 바꾼 경계 — 되돌리지 않고 기록만 버림. */
        FORGET
    }

    /** @param set 정할 경계 (APPLY·RESTORE), record 저장할 기록 (null = 지움) */
    public record Decision(Action action, Square set, Record record) {}

    /**
     * 할 일 정하기.
     * <ul>
     *   <li>켬: 기록이 있고 지금 경계가 우리 것 → target 과 다르면 다시 정함(이전 경계는 그대로 기억).
     *       기록이 없고 지금 경계가 바닐라 기본 → 정함(이전 = 지금). 지금이 이미 target → 기록만.
     *       그 밖(관리자가 직접 정한 경계, 우리가 정한 뒤 관리자가 바꾼 경계) → 그대로 둠.</li>
     *   <li>끔: 기록이 있고 지금 경계가 아직 우리 것 → 이전 경계로 되돌림. 관리자가 바꿨으면 그대로 두고 기록만 버림.</li>
     * </ul>
     */
    public static Decision decide(boolean enabled, Square current, Square target, Record rec) {
        if (!enabled || target == null) {
            if (rec == null) return new Decision(Action.NONE, null, null);
            if (current != null && current.same(rec.ours())) return new Decision(Action.RESTORE, rec.previous(), null);
            return new Decision(Action.FORGET, null, null);
        }
        if (rec != null) {
            if (current != null && current.same(rec.ours())) {
                if (current.same(target)) return new Decision(Action.NONE, null, new Record(target, rec.previous()));
                return new Decision(Action.APPLY, target, new Record(target, rec.previous()));
            }
            if (current != null && current.same(target)) return new Decision(Action.NONE, null, new Record(target, rec.previous()));
            // 바닐라 기본으로 돌아가 있으면(월드 데이터를 되돌림 등) 아무도 정하지 않은 것 — 다시 정한다 (다음 시작과 같은 결과)
            if (current == null || current.vanillaDefault()) {
                return new Decision(Action.APPLY, target, new Record(target, current == null ? vanilla(VANILLA_WARNING) : current));
            }
            return new Decision(Action.ADMIN, null, null);
        }
        if (current != null && current.same(target)) {
            return new Decision(Action.NONE, null, new Record(target, vanilla(current.warning())));
        }
        if (current == null || current.vanillaDefault()) {
            Square prev = current == null ? vanilla(VANILLA_WARNING) : current;
            return new Decision(Action.APPLY, target, new Record(target, prev));
        }
        return new Decision(Action.ADMIN, null, null);
    }

    /** 관리자 명령으로 덮어쓰기 (/labadmin wild border apply): 지금 경계를 '이전'으로 기억 (이미 우리 것이면 원래 이전 그대로). */
    public static Decision force(Square current, Square target, Record rec) {
        Square prev = rec != null && current != null && current.same(rec.ours()) ? rec.previous()
                : current == null ? vanilla(VANILLA_WARNING) : current;
        return new Decision(Action.APPLY, target, new Record(target, prev));
    }

    public static Square vanilla(int warning) { return new Square(0, 0, VANILLA_SIZE, warning); }

    /** 이름 붙은 점 중 경계 밖인 것 (자가 진단). */
    public static List<String> outside(Square s, Map<String, double[]> points) {
        List<String> out = new ArrayList<>();
        for (Map.Entry<String, double[]> e : points.entrySet()) {
            double[] p = e.getValue();
            if (p == null || !s.contains(p[0], p[1])) out.add(e.getKey());
        }
        return out;
    }

    /** 보호 상자 중 경계 밖으로 나간 것 (순번). */
    public static List<Integer> boxesOutside(Square s, List<VillageMeta.Box> boxes) {
        List<Integer> out = new ArrayList<>();
        for (int i = 0; i < boxes.size(); i++) {
            VillageMeta.Box b = boxes.get(i);
            if (!s.containsBlocks(b.x0(), b.z0(), b.x1(), b.z1())) out.add(i);
        }
        return out;
    }

    /** "중심 (-135.5, 16.5) · 한 변 135칸" */
    public static String describe(Square s) {
        if (s == null) return "-";
        if (s.vanillaDefault()) return "바닐라 기본 (한 변 " + fmt(s.size()) + ")";
        return "중심 (" + fmt(s.x()) + ", " + fmt(s.z()) + ") · 한 변 " + fmt(s.size()) + "칸";
    }

    static String fmt(double v) {
        if (Math.abs(v - Math.rint(v)) < 1e-9) return String.valueOf((long) Math.rint(v));
        return String.valueOf(Math.round(v * 10) / 10.0);
    }
}
