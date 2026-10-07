package kr.souls.combat;

import kr.souls.Config.RollKind;
import org.bukkit.Location;
import org.bukkit.entity.Player;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 플레이어 한 명의 전투 상태 (3.1). M0 에는 스태미나와 구르기만 있다.
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
    public boolean rollReported = true;
    /** /soulstest rollhit: 다음 구르기 시작 뒤 이 틱에 시험 피해를 넣는다 (-1: 없음) */
    public int armedRollHit = -1;
    public double armedRollHitAmount;

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
