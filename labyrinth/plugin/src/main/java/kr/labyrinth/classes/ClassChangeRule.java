package kr.labyrinth.classes;

import kr.labyrinth.core.Settings;

/**
 * 직업 변경 규칙 (config.yml class_change) — 순수 판정, Bukkit 없음. 모든 진입점(/직업 선택·직업 메뉴·전직관 NPC)은
 * {@link ClassChangeGate} 를 거쳐 이 판정 하나를 쓴다.
 * <ul>
 *   <li>첫 직업 선택(지금 직업 없음)은 무료 — 두루마리도 대기 시간도 보지 않는다.</li>
 *   <li>그 뒤로 바꿀 때는 {@code require_item} 이면 전직의 두루마리 1장이 사라진다.</li>
 *   <li>직업을 정한(바꾼) 뒤 {@code cooldown_hours} 동안은 다시 바꿀 수 없다 — 첫 선택부터 센다.</li>
 *   <li>미궁 공략 중에는 언제나 막는다 (첫 선택도).</li>
 * </ul>
 * 막는 이유가 여럿이면 같은 직업 → 미궁 공략 중 → 대기 시간 → 두루마리 순으로 하나를 고르고, 두루마리가 모자란지는 따로 알려 준다.
 */
public final class ClassChangeRule {

    private ClassChangeRule() {}

    /** 막는 이유. */
    public enum Block { SAME_CLASS, IN_RUN, COOLDOWN, NO_ITEM }

    /**
     * 판정 결과.
     *
     * @param block          막는 이유 (null = 바꿀 수 있음)
     * @param first          첫 직업 선택인가 (무료)
     * @param needsItem      이번 변경에 두루마리가 필요한가 (첫 선택·require_item false 면 false)
     * @param missingItem    필요한데 가진 게 없는가 (막는 이유가 대기 시간이어도 함께 알려 주려고 따로 둔다)
     * @param cooldownLeftMs 다음 변경까지 남은 시간(ms, 0 = 대기 없음)
     */
    public record Verdict(Block block, boolean first, boolean needsItem, boolean missingItem, long cooldownLeftMs) {
        public boolean allowed() { return block == null; }

        /** 바꾸면 두루마리 1장이 사라지는가. */
        public boolean consumesItem() { return allowed() && needsItem; }
    }

    /**
     * @param current      지금 직업 id (null = 없음 → 첫 선택)
     * @param target       바꿀 직업 id (존재 확인은 부르는 쪽)
     * @param inRun        미궁 공략 중인가
     * @param hasItem      두루마리를 1장 이상 가졌는가
     * @param lastChangeMs 마지막으로 직업을 정한 시각 (epoch ms, 0 이하 = 기록 없음)
     */
    public static Verdict check(Settings.ClassChange rule, String current, String target, boolean inRun, boolean hasItem,
                                long lastChangeMs, long nowMs) {
        boolean first = current == null;
        boolean needsItem = !first && rule.requireItem();
        boolean missing = needsItem && !hasItem;
        long left = first ? 0 : cooldownLeft(rule, lastChangeMs, nowMs);
        Block block;
        if (current != null && current.equals(target)) block = Block.SAME_CLASS;
        else if (inRun) block = Block.IN_RUN;
        else if (left > 0) block = Block.COOLDOWN;
        else if (missing) block = Block.NO_ITEM;
        else block = null;
        return new Verdict(block, first, needsItem, missing, left);
    }

    /**
     * 다음 변경까지 남은 시간(ms). 대기 시간 0·기록 없음이면 0. 시계가 거꾸로 가도(기록이 미래) 대기 시간보다 길어지지 않는다.
     */
    public static long cooldownLeft(Settings.ClassChange rule, long lastChangeMs, long nowMs) {
        long cd = rule.cooldownMs();
        if (cd <= 0 || lastChangeMs <= 0) return 0;
        long left = lastChangeMs + cd - nowMs;
        return Math.max(0, Math.min(cd, left));
    }

    /** 남은 시간 표기 — 분 단위 올림: "12시간 30분", "3시간", "45분" (1분 미만도 "1분"). 0 이하는 "0분". */
    public static String duration(long ms) {
        if (ms <= 0) return "0분";
        long minutes = (ms + 59_999) / 60_000;
        long h = minutes / 60, m = minutes % 60;
        if (h <= 0) return m + "분";
        return m == 0 ? h + "시간" : h + "시간 " + m + "분";
    }

    /** 대기 시간 설정 표기 — 24 → "24시간", 1.5 → "1시간 30분", 0 → "없음". */
    public static String hours(double cooldownHours) {
        return cooldownHours <= 0 ? "없음" : duration(Math.round(cooldownHours * 3_600_000d));
    }
}
