package kr.labyrinth.village;

/**
 * 구역 상태 기계 (0.3.6.1 광산 마을, CONTRACT §2.13 5·6) — 순수 로직 (시험: DistrictPolicyTest).
 * <ul>
 *   <li>시작할 때 ({@link #onStart}): 기록 파일이 없고 {@code mine.district.auto_build: true} 이고 배포 월드(지문이 있는 마을)면 한 번 짓는다.
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
        if (!villagePresent) return "이 월드에는 마을이 없습니다 — 광산 마을은 마을 큰길 끝에 붙여 짓습니다";
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
}
