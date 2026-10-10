package kr.souls.combat;

import kr.souls.Config;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.FoodLevelChangeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import java.util.Map;
import java.util.TreeMap;

/**
 * 스태미나 (3.2). 달리기는 틱마다 쓰고, 구르기·공격 같은 행동은 끝난 틱에서 regen-delay 틱 뒤부터 다시 찬다.
 * 0 이 되면 탈진: 회복 지연이 길어지고, 일정량이 찰 때까지 달리지 못한다.
 * 달리기 금지는 허기를 6 으로 내려서 한다. 클라이언트는 허기가 6 이하이면 달리기를 시작하지도 이어가지도 않는다 [확인 (클라)].
 * 허기는 이 체계만 바꾼다 (FoodLevelChangeEvent 는 늘 취소, 평소 20). 장비가 너무 무거울 때 (5.8) 도 여기서 허기 6 으로 둔다
 * (허기를 쓰는 곳은 여기 한 곳, 검토 T13).
 * 최대치는 기력 (5.2, combat.stamina.curve), 회복은 regen-per-tick × 기력 배율 (stats.endurance.regen-scale) × 장비 무게 배율 (load.*.regen)
 * × 낀 반지의 회복 배율 (9.4, item/RingSlots: 반지 칸에 낀 동안만).
 * 화면은 Hud 가 왼쪽 위 스태미나 막대 (HUD 보스 막대의 그림 글자) 로 그린다. 여기서는 값만 바꾼다.
 */
public final class Stamina implements Listener {
    public static final int FOOD_NORMAL = 20, FOOD_EXHAUSTED = 6;

    private final Souls plugin;

    public Stamina(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.StaminaCfg cfg() {
        return plugin.cfg().stamina;
    }

    /** 기력 → 최대 스태미나. 표 사이는 직선으로 잇고, 표 밖은 끝값. */
    public static double maxFor(TreeMap<Integer, Double> curve, int endurance) {
        if (curve.isEmpty()) return 100;
        Map.Entry<Integer, Double> lo = curve.floorEntry(endurance), hi = curve.ceilingEntry(endurance);
        if (lo == null) return hi.getValue();
        if (hi == null) return lo.getValue();
        if (lo.getKey().equals(hi.getKey())) return lo.getValue();
        double t = (endurance - lo.getKey()) / (double) (hi.getKey() - lo.getKey());
        return lo.getValue() + (hi.getValue() - lo.getValue()) * t;
    }

    /** 이 플레이어의 기력 (프로필, 5.2. 출신을 고르기 전에는 10). */
    public int endurance(Player p) {
        return plugin.stats().of(p).end();
    }

    /** 이 플레이어의 최대 스태미나. */
    public double max(Player p) {
        return maxFor(cfg().curve(), endurance(p));
    }

    /** 최대치가 늘었으면 (레벨업) 늘어난 몫만큼 채운다. before 는 바꾸기 전의 최대치. */
    public void grow(Player p, double before) {
        CombatState st = CombatState.of(p);
        double after = max(p);
        st.stamina.setMax(after);
        if (after > before) st.stamina.set(Math.min(after, st.stamina.cur() + (after - before)));
    }

    /** 전투 규칙이 도는 사람인가 (창작·관전 모드는 쓰지도 닳지도 않는다). */
    public static boolean fighting(Player p) {
        GameMode g = p.getGameMode();
        return (g == GameMode.SURVIVAL || g == GameMode.ADVENTURE) && !p.isDead();
    }

    /**
     * 행동 하나에 스태미나를 쓴다. 1 이상일 때만 시작할 수 있고 (모자라면 0 에서 멈춘다), 회복은 그 행동이 끝나는 틱
     * actionEnd 에서 regen-delay (0 이 되었으면 exhausted-delay) 틱 뒤부터.
     * @return 행동을 해도 되면 true (이미 쓴 뒤)
     */
    public boolean spend(Player p, double cost, long actionEnd) {
        CombatState st = CombatState.of(p);
        if (!fighting(p)) return true;
        if (!st.stamina.canAct()) return false;
        boolean zero = st.stamina.spend(cost);
        Config.StaminaCfg c = cfg();
        if (zero) st.exhausted = true;
        st.stamina.holdUntil(actionEnd + (zero ? c.exhaustedDelay() : c.regenDelay()));
        return true;
    }

    /** 가득 채우고 탈진을 푼다 (접속, 부활, 쉬기). */
    public void refill(Player p) {
        CombatState st = CombatState.of(p);
        st.stamina.setMax(maxFor(cfg().curve(), endurance(p)));
        st.stamina.fill();
        st.stamina.resetHold();
        st.exhausted = false;
        if (p.getFoodLevel() != FOOD_NORMAL) p.setFoodLevel(FOOD_NORMAL);
    }

    /** Ticker 가 틱마다 부른다. */
    public void tick(long now) {
        Config.StaminaCfg c = cfg();
        for (Player p : Bukkit.getOnlinePlayers()) {
            CombatState st = CombatState.of(p);
            Pool pool = st.stamina;
            double max = maxFor(c.curve(), endurance(p));
            if (Math.abs(pool.max() - max) > 1e-6) pool.setMax(max);
            if (!fighting(p)) {
                st.wasSprinting = false;
                continue;
            }
            boolean sprint = p.isSprinting();
            if (sprint) {
                boolean zero = pool.spend(c.sprintPerTick());
                if (zero) st.exhausted = true;
                // 달리는 동안은 회복 없음. 멈춘 틱이 행동이 끝난 틱이다
                pool.holdUntil(now + 1 + (zero ? c.exhaustedDelay() : c.regenDelay()));
            } else {
                double rate = c.regenPerTick() * plugin.cfg().stats.regenScale.at(endurance(p)) * plugin.load().regen(p)
                        * plugin.ringSlots().staminaRegen(p);
                if (p.isBlocking()) rate *= c.guardRegenScale();
                pool.regen(now, rate);
            }
            st.wasSprinting = sprint;
            if (st.exhausted && pool.cur() >= c.exhaustedSprintUntil()) st.exhausted = false;

            // 탈진했거나 장비가 너무 무거우면 (5.8) 달리지 못한다
            boolean noSprint = st.exhausted || plugin.load().noSprint(p);
            int food = noSprint ? FOOD_EXHAUSTED : FOOD_NORMAL;
            if (p.getFoodLevel() != food) p.setFoodLevel(food);
            // 허기 6 은 클라이언트가 달리기를 멈추게 한다. 서버 쪽 상태도 함께 내린다
            if (noSprint && sprint) p.setSprinting(false);
            if (p.getSaturation() != 0) p.setSaturation(0);
        }
    }

    /** 허기는 이 체계만 바꾼다. 달리기·점프로 닳지도, 음식으로 차지도 않는다. */
    @EventHandler(priority = EventPriority.LOW)
    public void onFood(FoodLevelChangeEvent e) {
        if (e.getEntity() instanceof Player) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOW)
    public void onJoin(PlayerJoinEvent e) {
        refill(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        CombatState.drop(e.getPlayer().getUniqueId());
        plugin.titles().forget(e.getPlayer().getUniqueId());
    }
}
