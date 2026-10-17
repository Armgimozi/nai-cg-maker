package kr.labyrinth.village;

/**
 * 구역 상태 기계 (0.3.6.1 광산 마을, CONTRACT §2.13 5·6 · 0.3.7 집 구역 차례·지우기 R8·R9) — 순수 로직 (시험: DistrictPolicyTest·DistrictRemoveRuleTest).
 * <ul>
 *   <li>시작할 때 ({@link #onStart}): 기록 파일이 없고 그 구역 auto_build ({@code mine.district} · {@code homes.district}) 이고 배포 월드(지문이 있는 마을)면 한 번 짓는다.
 *       구역이 여럿이면 차례대로 ({@link #plan} — 광산 → 집).
 *       {@code building} 으로 꺼졌으면 먼저 백업으로 되돌린다 — 그다음은 파일이 없을 때와 같다 (처음부터 다시).
 *       {@code built}·{@code removed} 는 아무것도 하지 않는다 (지운 구역을 저절로 다시 짓지 않는다).</li>
 *   <li>배포 월드가 아니면(시드·마을이 다름) 저절로 짓지 않고 관리자에게 미리보기를 권한다 — 사람이 만든 것을 지문 없이 다 알아볼 수 없으니.</li>
 *   <li>관리자 안내는 하루에 한 번 ({@link #notifyToday}).</li>
 * </ul>
 */
public final class DistrictPolicy {

    private DistrictPolicy() {}

    public enum Startup {
        /** 할 일 없음 (지어짐 · 지움 · 자동 짓기 끔). */
        NONE,
        /** 마을이 없는 월드 — 구역은 마을 큰길 끝에 붙으므로 짓지 않는다 (광산은 관리소로 그대로). */
        NO_VILLAGE,
        /** 배포 월드가 아님 — 저절로 짓지 않고 관리자에게 미리보기를 권한다. */
        UNKNOWN_WORLD,
        /** 짓다가 꺼짐 — 백업으로 되돌린 뒤 처음부터. */
        RECOVER,
        /** 저절로 짓기 (자리 후보 차례로). */
        AUTO_BUILD
    }

    /**
     * @param state 구역 기록 상태 (파일이 없으면 null)
     * @param villagePresent 주 월드에 마을 메타데이터가 있는가
     * @param autoBuild config mine.district.auto_build
     * @param shippedWorld 마을 build_id 의 지문이 jar 에 있는가 (배포 월드)
     */
    public static Startup onStart(DistrictMeta.State state, boolean villagePresent, boolean autoBuild, boolean shippedWorld) {
        if (state == DistrictMeta.State.BUILDING) return Startup.RECOVER;
        if (state != null) return Startup.NONE;
        if (!villagePresent) return Startup.NO_VILLAGE;
        if (!autoBuild) return Startup.NONE;
        if (!shippedWorld) return Startup.UNKNOWN_WORLD;
        return Startup.AUTO_BUILD;
    }

    /** 관리자 짓기 명령을 받을 수 있나 (null = 됨, 아니면 이유). */
    public static String canBuild(DistrictMeta.State state, boolean villagePresent) {
        if (!villagePresent) return "이 월드에는 마을이 없습니다 — 구역은 마을 길에 붙여 짓습니다";
        if (state == DistrictMeta.State.BUILT) return "이미 지어져 있습니다 (다시 지으려면 먼저 remove)";
        if (state == DistrictMeta.State.BUILDING) return "짓다가 멈춘 기록이 있습니다 — remove 로 먼저 되돌리세요 (백업이 없으면 remove <id> force)";
        return null;
    }

    /** 되돌리기 명령을 받을 수 있나 (null = 됨). */
    public static String canRemove(DistrictMeta.State state, boolean backupExists) {
        if (state == null) return "지은 기록이 없습니다";
        if (state == DistrictMeta.State.REMOVED) return "이미 지웠습니다";
        if (!backupExists) return "되돌리기 백업 파일이 없습니다 — 블록을 그대로 두고 기록만 지우려면 remove <id> force (남은 블록은 손으로 치움)";
        return null;
    }

    /** 하루 한 번 안내: 마지막 안내 날(epoch day, 없으면 Long.MIN_VALUE)보다 오늘이 뒤면. */
    public static boolean notifyToday(long lastDay, long today) { return today > lastDay; }

    // ── 여러 구역 차례 (0.3.7 — review R8) ─────────────────────────────────

    /**
     * 시작할 때 본 구역 하나 (짓는 차례 = 구역 order).
     * @param state 기록 상태 (파일이 없으면 null) · auto = 그 구역 모듈이 켜졌고 auto_build · shipped = 지문이 있는 배포 월드
     * @param tried 이번 시작에 이미 짓기·되돌리기를 해 봄 (끝났거나 막힘 — 같은 시작에서 다시 하지 않음)
     */
    public record Item(String id, DistrictMeta.State state, boolean villagePresent, boolean auto, boolean shipped, boolean tried) {}

    public record Step(String id, Startup action) {}

    /**
     * 이번에 할 일 (review R8): 구역을 차례대로 보며, 할 일 없는 구역(지어짐·지움·꺼짐·마을 없음·배포 월드 아님)은 지나가고,
     * 짓기·되돌리기가 필요한 첫 구역에서 멈춘다 — 그 작업이 끝나면(지어짐·막힘) 다시 불러 다음 구역으로. 앞 구역(광산)이
     * 끝남·막힘·꺼짐(모듈 없음·mine.enabled false·auto_build false) 이면 다음 구역(집)을 본다.
     */
    public static java.util.List<Step> plan(java.util.List<Item> items) {
        java.util.List<Step> out = new java.util.ArrayList<>();
        for (Item it : items) {
            if (it.tried()) continue;
            Startup s = onStart(it.state(), it.villagePresent(), it.auto(), it.shipped());
            out.add(new Step(it.id(), s));
            if (s == Startup.RECOVER || s == Startup.AUTO_BUILD) break;
        }
        return out;
    }

    // ── 지우기 (0.3.7 — review R9) ─────────────────────────────────────────

    public enum Remove {
        /** 못 함 (기록 없음·이미 지움·백업 없음 — 이유는 {@link #canRemove}). */
        REFUSE,
        /** 집 구역에 주인이 있음 — force 로만 (모두 맡긴 짐으로 돌린 뒤 지움). */
        REFUSE_OWNERS,
        /** 백업으로 우리가 놓은 칸만 되돌림. */
        RESTORE,
        /** 블록은 그대로 두고 기록만 지움 (백업이 없을 때). */
        FORGET,
        /** 모든 집을 회수(맡긴 짐)한 뒤 되돌림. */
        RECLAIM_THEN_RESTORE,
        /** 모든 집을 회수(맡긴 짐)한 뒤 기록만 지움. */
        RECLAIM_THEN_FORGET
    }

    /**
     * {@code /labadmin village district remove <id> [force]} 가 할 일.
     * <ul>
     *   <li>광산 등: force 없으면 백업으로 되돌리기 (백업이 없으면 거절), force = 기록만 지우기 (0.3.6.1 그대로).</li>
     *   <li>집 구역 (homes): 주인이 있으면 force 없이는 거절. force = 모든 집 회수 → 백업이 있으면 되돌리기, 없으면 기록만 지우기.
     *       주인이 없으면 광산과 같되 force 에 백업이 있으면 되돌린다.</li>
     * </ul>
     */
    public static Remove removeAction(String id, DistrictMeta.State state, boolean backupExists, int owners, boolean force) {
        if (state == null || state == DistrictMeta.State.REMOVED) return Remove.REFUSE;
        if (!"homes".equals(id)) {
            if (force) return Remove.FORGET;
            return backupExists ? Remove.RESTORE : Remove.REFUSE;
        }
        if (owners > 0 && !force) return Remove.REFUSE_OWNERS;
        if (owners > 0) return backupExists ? Remove.RECLAIM_THEN_RESTORE : Remove.RECLAIM_THEN_FORGET;
        if (backupExists) return Remove.RESTORE;
        return force ? Remove.FORGET : Remove.REFUSE;
    }
}
