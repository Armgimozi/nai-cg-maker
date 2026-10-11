package kr.souls.combat;

import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlot;

/**
 * 서버가 플레이어의 손을 휘두르는 곳 (M1 P1-0 계약, PS 의 S3 를 받아 바꾼 곳). 패링 몸짓 (P3), 치명타의 한 대 (P3), 왼손 공격·낙하
 * (P6) 는 {@code p.swingMainHand()} / {@code swingOffHand()} 를 바로 부르지 않고 여기를 부른다. 왼클릭 동작 (P1a) 은 서버가 다시
 * 휘두르지 않는다 (R3).
 * <ul>
 *   <li>S3: 서버가 휘두르면 진짜 클라이언트가 0~1틱 (+ 왕복) 뒤에 같은 손의 휘두르기 패킷과 LEFT_CLICK_AIR(HAND) 를 되돌려 보낸다.
 *       되돌아온 주손 휘두르기는 진짜 왼클릭처럼 읽힌다. 그래서 여기서 휘두른 틱을 CombatState 에 적어 두고, P1a 의 가짜 휘두르기 거르개
 *       (FakeSwingFilter) 가 {@link #since} 로 왕복 + 2틱 안의 HAND 휘두르기와 LEFT_CLICK_AIR 를 버린다.</li>
 *   <li>S3: 서버가 휘두른 뒤 1인칭 주무기가 그 무기의 공격 대기 동안 화면 밑으로 내려간다 (F 만으로는 내려가지 않는다). 바닐라
 *       attack_speed 를 높게 (4 이상) 두면 피한다: P1a·P3 가 정한다.</li>
 * </ul>
 */
public final class Swings {
    private Swings() {}

    /** 서버가 주손을 휘두른다 (모두에게, 그 사람에게도). now 는 Ticker.now. */
    public static void main(Player p, long now) {
        if (p == null) return;
        CombatState.of(p).srvSwingMain = now;
        p.swingMainHand();
    }

    /** 서버가 왼손을 휘두른다. */
    public static void off(Player p, long now) {
        if (p == null) return;
        CombatState.of(p).srvSwingOff = now;
        p.swingOffHand();
    }

    /** 그 손 (HAND | OFF_HAND) 을 서버가 마지막으로 휘두른 틱 (없으면 아주 작은 값). */
    public static long last(Player p, EquipmentSlot hand) {
        CombatState st = p == null ? null : CombatState.peek(p.getUniqueId());
        if (st == null) return CombatState.NEVER;
        return hand == EquipmentSlot.OFF_HAND ? st.srvSwingOff : st.srvSwingMain;
    }

    /** 어느 손이든 서버가 마지막으로 휘두른 뒤 지난 틱 (휘두른 적이 없으면 Long.MAX_VALUE). */
    public static long since(Player p, long now) {
        CombatState st = p == null ? null : CombatState.peek(p.getUniqueId());
        if (st == null) return Long.MAX_VALUE;
        long last = Math.max(st.srvSwingMain, st.srvSwingOff);
        return last <= CombatState.NEVER ? Long.MAX_VALUE : now - last;
    }
}
