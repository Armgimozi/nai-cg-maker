package kr.souls.combat;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.SwingAnimation;
import kr.souls.input.FakeSwingFilter;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.util.function.BooleanSupplier;
import java.util.function.IntSupplier;

/**
 * 서버가 플레이어의 손을 휘두르는 곳 (M1 P1-0 계약, PS 의 S3 를 받아 바꾼 곳). 공격 동작 (P1a), 패링 몸짓 (P3), 치명타의 한 대 (P3),
 * 왼손 공격·낙하 (P6) 는 {@code p.swingMainHand()} / {@code swingOffHand()} 를 바로 부르지 않고 여기를 부른다.
 * 2026-10-11 휘두름 잠금 (M1_PLAN R3 를 바꿨다): 서버는 공격 동작을 시작할 때마다 (곧바로 낸 것도, 기억했다가 낸 것도) 주손을 휘두른다
 * (MoveRunner.start). 우리 세계에서는 클라이언트의 휘두르기 패킷이 서버 쪽 휘두름을 다시 시작하지 않는다 (InputRouter 가
 * PlayerArmSwingEvent 를 취소한다). 그래서 서버 쪽 휘두름은 여기서만 다시 시작하고, 휘둘렀는지 (패킷이 나갔는지) 를 정확히 안다.
 * <ul>
 *   <li>휘두름 규칙 ({@link #free}): 서버 (LivingEntity.swing) 는 휘두르는 중이면 반 (D/2) 이 지나야 다시 휘두른다. 휘두름 시계는 손이
 *       하나다 (주손·왼손이 같은 시계, 길이 D 는 주손 아이템의 swing_animation, 없으면 6). 우리 틱으로는 지난 서버 휘두름에서 D/2 + 1 틱이
 *       지나야 한다. 막히면 아무것도 하지 않고 (적지도 않고) false.</li>
 *   <li>S3: 서버가 휘두르면 진짜 클라이언트가 같은 손의 휘두르기 패킷 하나를 왕복 시간 + 0~1틱 뒤에 되돌려 보낸다 (LocalPlayer.swing 은
 *       팔이 다시 휘둘러지지 않아도 늘 보낸다). 휘둘렀으면 그 손의 되돌림 장부 (CombatState.echoMain·echoOff) 에 하나를 더한다: 핑 틱 +
 *       combat.input.echo-window 안에 온 그 손의 휘두르기 하나를 InputRouter 가 공격으로 치지 않는다. 한 왕복 (핑 틱 − 2) 이 지나기 전에
 *       온 것은 되돌림일 수 없어 진짜로 본다 (FakeSwingFilter.Ledger).</li>
 *   <li>S3: 서버가 휘두른 뒤 1인칭 주무기가 그 무기의 공격 대기 동안 화면 밑으로 내려간다 (F 만으로는 내려가지 않는다). 바닐라
 *       attack_speed 를 높게 (4 이상) 두면 피한다: P1a·P3 가 정한다.</li>
 * </ul>
 * 차례: Ticker 안 (input·moves 자리) 에서 휘두른 것은 그 틱의 플레이어 틱 (연결 틱) 전이고, 패킷·명령 (Ticker 밖) 에서 휘두른 것은 다음
 * 틱의 플레이어 틱 전이라 서버 쪽 휘두름 시계로는 한 틱 늦다. 그래서 규칙은 Ticker 밖이면 now + 1 로 센다 ({@link #configure}).
 */
public final class Swings {
    /** 지금 Ticker 안인가 (Souls 가 Ticker.running 을 끼운다. 시험 (JUnit) 에서는 늘 안) */
    private static volatile BooleanSupplier inTick = () -> true;
    /** combat.input.echo-window (Souls 가 끼운다) */
    private static volatile IntSupplier echoWindow = () -> 6;

    private Swings() {}

    /** Ticker 의 차례와 되돌림 창을 끼운다 (Souls.onEnable). */
    public static void configure(BooleanSupplier ticking, IntSupplier window) {
        inTick = ticking == null ? () -> true : ticking;
        echoWindow = window == null ? () -> 6 : window;
    }

    /**
     * 서버 쪽 휘두름 규칙 (순수 함수, SwingsTest): 마지막 서버 휘두름의 시계 틱 last (없으면 NEVER) 뒤 at 에 길이 d 로 다시 휘두를 수 있나.
     * at − last ≥ d/2 + 1 (정수 나눗셈, 서버와 같다).
     */
    public static boolean free(long at, long last, int d) {
        return last <= CombatState.NEVER || at - last >= d / 2 + 1;
    }

    /** 서버가 주손을 휘두른다 (모두에게, 그 사람에게도). 휘둘렀으면 true, 서버의 휘두름 규칙에 막혔으면 아무것도 하지 않고 false. now 는 Ticker.now. */
    public static boolean main(Player p, long now) {
        return swing(p, now, false);
    }

    /** 서버가 왼손을 휘두른다 (주손과 같은 휘두름 시계). 휘둘렀으면 true. */
    public static boolean off(Player p, long now) {
        return swing(p, now, true);
    }

    private static boolean swing(Player p, long now, boolean off) {
        if (p == null) return false;
        CombatState st = CombatState.of(p);
        long at = inTick.getAsBoolean() ? now : now + 1;
        if (!free(at, st.srvSwingClock, duration(p))) return false;
        st.srvSwingClock = at;
        int ping = FakeSwingFilter.pingTicks(p.getPing());
        if (off) {
            st.srvSwingOff = now;
            st.echoOff.sent(now, ping, echoWindow.getAsInt());
            p.swingOffHand();
        } else {
            st.srvSwingMain = now;
            st.echoMain.sent(now, ping, echoWindow.getAsInt());
            p.swingMainHand();
        }
        return true;
    }

    /**
     * 서버가 보는 휘두름 길이 (LivingEntity.getCurrentSwingDuration): 주손 아이템의 swing_animation 길이 (없으면 6) − (1 + 성급함·전달체의
     * 힘 단계), 그것이 없고 채굴 피로가 있으면 + (1 + 단계) × 2.
     */
    @SuppressWarnings("UnstableApiUsage")
    static int duration(Player p) {
        SwingAnimation sa = p.getInventory().getItemInMainHand().getData(DataComponentTypes.SWING_ANIMATION);
        int d = sa == null ? 6 : sa.duration();
        int dig = Math.max(amp(p, PotionEffectType.HASTE), amp(p, PotionEffectType.CONDUIT_POWER));
        if (dig >= 0) return d - (1 + dig);
        int fatigue = amp(p, PotionEffectType.MINING_FATIGUE);
        return fatigue >= 0 ? d + (1 + fatigue) * 2 : d;
    }

    /** 효과의 단계 (없으면 −1). */
    private static int amp(Player p, PotionEffectType t) {
        PotionEffect e = p.getPotionEffect(t);
        return e == null ? -1 : e.getAmplifier();
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
