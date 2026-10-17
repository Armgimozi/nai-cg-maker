package kr.labyrinth.homes.rules;

import java.util.Locale;
import kr.labyrinth.homes.HomesApi;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.village.Nature;

/**
 * 주 월드 지형 잠금 판단 (0.3.7, plan §9·§10) — 순수. 소유: 묶음 B.
 * <ul>
 *   <li>켜짐 = homes.enabled && homes.terrain_lock && (lock on || (lock auto && 집 구역 built)). lock off 면 늘 꺼짐.
 *       convert 집만 있는 서버는 관리자가 {@code /labadmin plot lock on} 해야 켜진다 (한 명만 집이 있는데 모두가 못 짓는 서버를 막음).</li>
 *   <li>어디: zone &gt; 0 → 그 집에서의 자리 (OWN · GUEST · STRANGER) · 0 → 보호 상자 · −1 → 잠금에 따라 WILD_LOCKED / WILD_OPEN.</li>
 *   <li>이사 기간에 부술 수 있는 것: Nature UNNATURAL (판자·유리·상자·횃불 …) · 지속 잎. 돌·흙·원목·광석은 잠김 (R2).</li>
 * </ul>
 */
public final class TerrainLock {

    private TerrainLock() {}

    /** labyrinth-plots.yml lock.state. */
    public enum State {
        AUTO, ON, OFF;

        public static State of(String s) {
            if (s == null) return AUTO;
            return switch (s.trim().toLowerCase(Locale.ROOT)) {
                case "on", "true", "켬" -> ON;
                case "off", "false", "끔" -> OFF;
                default -> AUTO;
            };
        }

        public String id() { return name().toLowerCase(Locale.ROOT); }
    }

    public static boolean locked(boolean enabled, boolean configLock, State state, boolean districtBuilt) {
        if (!enabled || !configLock || state == State.OFF) return false;
        return state == State.ON || districtBuilt;
    }

    /** zone 과 그 집에서의 자리 → 어디. role 은 zone &gt; 0 일 때만 본다 (null = NONE). */
    public static PlotRules.Where where(int zone, PlotRole role, boolean locked) {
        if (zone > 0) {
            PlotRole r = role == null ? PlotRole.NONE : role;
            if (r.builds()) return PlotRules.Where.OWN;
            return r == PlotRole.GUEST ? PlotRules.Where.GUEST : PlotRules.Where.STRANGER;
        }
        if (zone == HomesApi.ZONE_PROTECTED) return PlotRules.Where.PROTECTED;
        return locked ? PlotRules.Where.WILD_LOCKED : PlotRules.Where.WILD_OPEN;
    }

    /** 이사 기간에 그 밖에서 부술 수 있는 블록인가 (persistentLeaves = 잎이면 persistent 값). */
    public static boolean graceBreakable(String block, boolean persistentLeaves) {
        Nature.Kind k = Nature.kind(block);
        return k == Nature.Kind.UNNATURAL || (k == Nature.Kind.LEAVES && persistentLeaves);
    }

    /** 막을 때 글을 보내지 않는 블록 (풀·꽃 — 걷다가 친 것). */
    public static boolean silent(String block) { return Nature.kind(block) == Nature.Kind.PLANT; }
}
