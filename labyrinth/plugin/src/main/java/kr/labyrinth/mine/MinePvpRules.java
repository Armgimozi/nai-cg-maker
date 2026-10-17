package kr.labyrinth.mine;

import java.util.EnumSet;
import java.util.Set;
import kr.labyrinth.core.DeathPenaltyRules;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.QuitVerdict;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;

/**
 * 광산 PvP 규칙 (0.3.7) — 순수 (서버 없이 시험). 런타임은 {@link MinePvp}.
 * <ul>
 *   <li>바닐라 피해 문: 광산 월드의 바닐라 {@code EntityDamageEvent} 는 모두 막고, 다른 플레이어가 준 근접·화살·피해 물약·가시·쇠뇌 폭죽
 *       ({@link #VANILLA_PVP_CAUSES}) 만 PvP 규칙(isEnemy)을 거쳐 통과시킨다. 떨어짐·불·용암·익사·독·시듦·공허·{@code /kill} 은 그대로 없다.</li>
 *   <li>쓰러짐: {@code mine.pvp.penalty} 면 미궁 쓰러짐과 같은 {@link Where#MINE_PVP}, 아니면 경험치만 ({@link Where#OUTSIDE}).</li>
 *   <li>나가기 시전 · 싸우는 중 끊김: PvP 구역에 서 있고 10초 안에 때리거나 맞았을 때만 (안전 구역에서는 쓰러질 수 없으므로).</li>
 * </ul>
 */
public final class MinePvpRules {

    private MinePvpRules() {}

    /** 광산에서 통과시키는 바닐라 피해 원인 (다른 플레이어가 준 것일 때만). 근접 · 휩쓸기 · 투사체 · 즉시 피해 물약 · 가시 · 쇠뇌 폭죽. */
    public static final Set<DamageCause> VANILLA_PVP_CAUSES = EnumSet.of(DamageCause.ENTITY_ATTACK, DamageCause.ENTITY_SWEEP_ATTACK,
            DamageCause.PROJECTILE, DamageCause.MAGIC, DamageCause.THORNS, DamageCause.ENTITY_EXPLOSION);

    /** 이 원인의 바닐라 피해가 플레이어끼리의 PvP 일 수 있나 (나머지는 광산에서 언제나 0). */
    public static boolean vanillaPvpCause(DamageCause c) { return c != null && VANILLA_PVP_CAUSES.contains(c); }

    /**
     * 광산 월드의 바닐라 {@code EntityDamageEvent} 를 통과시킬지 (MineListener 가 나머지는 모두 취소 — "떨어짐·몹·환경 피해 없음").
     *
     * @param minePvp         광산 PvP 켜짐 (pvp.enabled 포함)
     * @param victimPlayer    맞는 쪽이 플레이어
     * @param applyingVanilla 미궁 피해 처리(DamageService)가 판정을 마친 막타를 바닐라 길로 넣는 중 — 막으면 0 HP 근처에서 죽지 않는다
     * @param cause           피해 원인
     * @param enemyPlayer     원인 뒤의 플레이어(쏜 사람·던진 사람 포함)가 있고 {@code MineApi.pvpAllows} (다른 파티 · 두 사람 PvP 구역)
     */
    public static boolean vanillaGate(boolean minePvp, boolean victimPlayer, boolean applyingVanilla, DamageCause cause, boolean enemyPlayer) {
        if (!minePvp || !victimPlayer) return false;
        if (applyingVanilla) return true;
        return vanillaPvpCause(cause) && enemyPlayer;
    }

    /** 광산 PvP 쓰러짐에 쓸 곳: penalty = {@code mine.pvp.penalty}. */
    public static Where where(boolean penalty) { return penalty ? Where.MINE_PVP : Where.OUTSIDE; }

    /**
     * 광산을 나갈 때(/미궁 마을 · 메인 메뉴 "마을" · PvP 구역에서 연 승강기) 기다릴 초. 0 = 바로.
     *
     * @param live          광산 PvP 가 지금 켜져 있고 광산 월드 안
     * @param onGround      PvP 구역에 서 있음 (안전 구역 · 층 사이면 false)
     * @param alive         살아 있고 서바이벌·어드벤처
     * @param sinceCombatMs 마지막 PvP (때림·맞음) 에서 지난 ms (없으면 음수)
     */
    public static double exitCastSeconds(Config c, boolean minePenalty, boolean live, boolean onGround, boolean alive, long sinceCombatMs) {
        if (!live || !onGround) return 0;
        return DeathPenaltyRules.exitCastSeconds(c, where(minePenalty), alive, sinceCombatMs);
    }

    /**
     * 접속을 끊은 순간의 형편 ({@link MinePvp#onQuit} 가 채움).
     *
     * @param minePvp       광산 PvP 켜짐 (pvp.enabled 포함)
     * @param inMineWorld   광산 월드에 있음
     * @param onGround      PvP 구역에 서 있음
     * @param alive         살아 있고 서바이벌·어드벤처 (크리에이티브·관전 = false)
     * @param sinceCombatMs 마지막 PvP 에서 지난 ms (없으면 음수)
     * @param casting       싸우는 중이라 시작한 나가기 시전(/미궁 마을 5초 · 싸우는 중 승강기) 중
     * @param serverSide    서버 종료 · 재시작 · 플러그인 끄기 · 관리자가 내보냄 (/kick · /ban · 화이트리스트)
     * @param downing       막타를 맞고 쓰러짐 처리(다음 틱)를 기다리는 중
     */
    public record MineQuit(boolean minePvp, boolean inMineWorld, boolean onGround, boolean alive, long sinceCombatMs, boolean casting,
                           boolean serverSide, boolean downing) {}

    /**
     * 광산 PvP 구역에서 싸우는 중에 끊으면 쓰러진 것으로 친다 (미궁과 같은 0.3.6.2 규칙 — 주인 결정 "던전과 같게").
     * 막타를 맞고 쓰러짐 처리를 기다리는 중이면 (서버가 내보낸 것이 아닌 한) 언제나. 그 밖에는 퇴장 시전과 같은 조건:
     * 광산 PvP 켜짐 · 광산 월드 · PvP 구역 · 살아 있음 · {@code combat_exit_seconds} &gt; 0 · 잃을 것이 하나라도 있음 ·
     * (10초 안에 때리거나 맞음 · 싸우는 중에 시작한 나가기 시전 중).
     */
    public static QuitVerdict combatQuit(Config c, boolean minePenalty, MineQuit q) {
        if (c == null || q == null || q.serverSide()) return QuitVerdict.NONE;
        if (q.downing()) return QuitVerdict.APPLY;
        if (!q.minePvp() || !q.inMineWorld() || !q.onGround() || !q.alive()) return QuitVerdict.NONE;
        if (c.combatExitSeconds() <= 0 || !DeathPenaltyRules.plan(c, where(minePenalty), false).any()) return QuitVerdict.NONE;
        return q.casting() || DeathPenaltyRules.inCombat(q.sinceCombatMs()) ? QuitVerdict.APPLY : QuitVerdict.NONE;
    }

    // ── 글 ──────────────────────────────────────────────────────────────

    /** 액션바: PvP 구역으로 들어감. */
    public static final String TO_PVP = "<#ff6b6b>⚔ PvP 구역</#ff6b6b> <gray>· 다른 플레이어가 공격할 수 있습니다";
    /** 액션바: 안전 구역으로 들어감. */
    public static final String TO_SAFE = "<#7fe07f>안전 구역</#7fe07f> <gray>· 승강기 홀에서는 싸울 수 없습니다";
    /** 쓰러짐 제목. */
    public static final String DOWN_TITLE = "<red><b>쓰러졌습니다</b></red>";
    /** 싸우는 중 승강기. */
    public static final String LIFT_CAST = "<gray>싸우는 중이라 승강기가 <white>%s초</white> 걸립니다. 움직이거나 맞으면 멈춥니다.";
    public static final String LIFT_HIT = "피해를 받아 승강기가 멈췄습니다.";
    public static final String EXIT_HIT = "피해를 받아 귀환이 끊겼습니다.";
    /** 다른 플러그인·/tp 로 광산 밖으로 가려 할 때 (싸우는 중). */
    public static final String TELEPORT_BLOCKED = "<red>싸우는 중에는 광산을 바로 나갈 수 없습니다.</red> <gray>승강기 홀로 가거나 10초 뒤에 다시 하세요.";
    /** 메뉴 줄. */
    public static final String LIFT_LORE = "<dark_gray>승강기 홀 밖은 PvP 구역";
    public static final String OFFICE_LORE = "<gray>승강기 홀 밖은 PvP 구역입니다.";
    public static final String MAIN_MENU_LORE = "<gray>광산은 승강기 홀 밖에서만 싸울 수 있습니다.";

    /** 같은 파티원에게: name 은 이미 이스케이프한 이름. */
    public static String partyDownText(String name) {
        return "<red>" + name + "</red><gray> 님이 광산에서 쓰러졌습니다.";
    }
}
