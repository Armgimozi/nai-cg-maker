package kr.souls.combat;

import kr.souls.Config.RollKind;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 플레이어 한 명의 전투 상태 (3.1). M0 에는 스태미나와 구르기, 패링을 누른 틱 (판정은 M1) 만 있다.
 * 상태(공격, 막기, 마시기, 경직, 넘어짐, 치명타 중, 휴식)와 깃발(버팀, 치명타 기회, 고정 표적, 입력 기억)은 M1 에 더한다.
 * 접속 중인 동안만 메모리에 있다 (나가면 지운다). 저장할 값은 프로필(M2)에 둔다.
 */
public final class CombatState {
    private static final Map<UUID, CombatState> ALL = new HashMap<>();

    public final UUID id;
    public final Pool stamina;
    /** 마나(FP) 자리. 마법이 들어오면 채운다 (지금은 null). */
    public Pool mana;

    /** 탈진: 0 이 된 뒤 exhausted-sprint-until 까지 찰 때까지 달리지 못한다 (허기 6) */
    public boolean exhausted;
    public boolean wasSprinting;

    // 구르기 (틱은 Ticker.now 기준)
    public long rollStart = Long.MIN_VALUE / 2;
    /** 마지막 구르기의 종류 (설정을 다시 읽어도 구르던 값은 그대로). null 이면 아직 구른 적 없음 */
    public RollKind roll;
    public Location rollFrom;
    /** 구르는 쪽 (수평, 길이 1). glide 틱 동안 이쪽으로 민다 */
    public Vector rollDir;
    public boolean rollReported = true;
    /** /soulstest rollhit: 다음 구르기 시작 뒤 이 틱(1 이상)에 시험 피해를 넣는다 (-1: 없음) */
    public int armedRollHit = -1;
    public double armedRollHitAmount;
    /** 걸어 둔 시험 피해가 묶인 구르기의 시작 틱 (걸어 둔 뒤 처음 구른 것. 그 전이면 Long.MIN_VALUE) */
    public long armedRollStart = Long.MIN_VALUE;

    // 패링 (3.5, combat/Parry). F 를 눌러 창을 연 틱과 그 창의 몫 (바탕 = 왼손 물건의 분류, 반지). 난이도 덧셈은 판정 때 (PvP 는 더하지 않는다)
    public long parryAt = Long.MIN_VALUE / 2;
    public int parryBase;
    public int parryRing;
    /** 마지막 패링이 무엇을 쳐냈나 (연타 잠금이 lock-hit 으로 짧아진다) */
    public boolean parryHit;
    /** 치명타 (리포스트) 기회: 쳐낸 적과 끝 틱 (M1 의 주무기 공격 입력이 Parry.riposte 로 본다) */
    public UUID riposteFoe;
    public long riposteUntil = Long.MIN_VALUE / 2;

    // ── M1 P1-0 계약 (P1a·P1b 가 함께 쓰는 칸, R31) ──
    /** "아직 없음" 틱 (빼도 넘치지 않는 아주 작은 값) */
    public static final long NEVER = Long.MIN_VALUE / 2;
    /** 마지막으로 싸운 틱: 적을 때렸거나 적에게 맞았다 (Foes.hit 과 대기열이 한 곳에서 찍는다, R23. 쉬기 거절·왼손 잠금·화살이 본다) */
    public long lastCombatTick = NEVER;
    /** 마지막으로 맞은 틱 (대기열이 찍는다, R23) */
    public long lastHurtTick = NEVER;
    /** 서버가 이 사람의 주손·왼손을 마지막으로 휘두른 틱 (combat/Swings, S3 의 되돌아오는 휘두르기 거르기) */
    public long srvSwingMain = NEVER;
    public long srvSwingOff = NEVER;
    // ── M1 P1a ── (동작·입력 기억·민첩 몫)
    /** 지금 하는 공격 동작 (없으면 null). MoveRunner 만 바꾼다 */
    public MoveRunner.Run move;
    /** 마지막 동작이 끝난 틱 (약공격 단을 잇는지 본다, combat.moves.combo-grace) */
    public long moveEnd = NEVER;
    /** 다음 약공격의 단 (0 부터). 강공격·달리기 공격 뒤와 쉰 뒤에는 0 */
    public int combo;
    /** 민첩으로 나눈 회복의 모아 둔 몫 (MoveTiming, 0..1) */
    public double dexCarry;
    /** 입력 기억 (3.6: 회복 − 6 부터 받고 6틱 산다) */
    public final kr.souls.input.InputBuffer buffer = new kr.souls.input.InputBuffer();
    /**
     * 구르기가 지금 동작을 끊을 수 있는 첫 틱 (회복의 마지막 cancel-at 몫, P1c 의 Roll·SneakTap 이 본다). 동작이 없으면 NEVER.
     * 준비·판정 중에는 구르지 못한다 (P1c 의 ROLL_DENY why=attack)
     */
    public long rollReadyAt = NEVER;
    // ── M1 P2a ── (막기 반격·막기 깨짐·경직·무적 창)
    // ── M1 P3 ── (치명타 중)
    // ── M1 P4 ── (강인도·넘어짐)
    // ── M1 P6 ── (모은 강공격·낙하)

    private CombatState(UUID id, double maxStamina) {
        this.id = id;
        this.stamina = new Pool(maxStamina);
    }

    public static CombatState of(Player p) {
        return ALL.computeIfAbsent(p.getUniqueId(), k -> new CombatState(k, 100));
    }

    public static CombatState peek(UUID id) {
        return ALL.get(id);
    }

    public static void drop(UUID id) {
        ALL.remove(id);
    }

    public static void clear() {
        ALL.clear();
    }

    /** 지금 무적 틱인가 (구르기 시작 다음 틱부터 iframes 틱 동안). */
    public boolean invulnerable(long now) {
        if (roll == null) return false;
        long t = now - rollStart;
        return t >= 1 && t <= roll.iframes();
    }

    /** 구르는 중인가 (끝 틱 전). */
    public boolean rolling(long now) {
        return roll != null && now - rollStart < roll.end();
    }

    /** 다음 구르기를 받는가 (회복을 끊고 다시 구른다). */
    public boolean canRollAgain(long now) {
        return roll == null || now - rollStart >= roll.next();
    }
}
