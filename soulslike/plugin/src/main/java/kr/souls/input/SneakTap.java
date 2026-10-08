package kr.souls.input;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import io.papermc.paper.event.player.PlayerArmSwingEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Config;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.Stamina;
import org.bukkit.Input;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInputEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 웅크리기 키를 짧게 눌렀다 떼면 구른다 (2.3 의 11, 3.3, 2026-10-08 사용자 결정 "구르기는 기존 웅크리기 키를 대체하는게 어때 f가 아니라").
 * 사람마다 웅크리기의 누름·뗌을 PlayerInputEvent 로 본다 (이벤트의 getInput() 이 새 입력, 플레이어의 getCurrentInput() 은 아직 지난 입력
 * [확인 (서버 코드): handlePlayerInput 이 이벤트 뒤에 입력을 적는다]).
 * <ul>
 *   <li>누름 틱 P 를 적는다. 그때 탈것 위·죽음·출신 없음·우리 창을 띄운 지 2틱 안이면 그 누름은 구르기가 될 수 없다.</li>
 *   <li>누르는 동안 새로 들어온 좌클릭 (휘두름·공격·LEFT_*), 우클릭 (RIGHT_*, 물체), F, Q 는 조합 키로 쓴 것이라 구르기를 버린다
 *       (웅크리기 키 + 좌클릭 = 강공격, 웅크리기 키 + Q = 다음 표적). 이미 누르고 있던 우클릭 (막기·마시기) 은 새 입력이 아니다.</li>
 *   <li>뗌 틱 R 에 R − P ≤ max-ticks (핑이 lag-ping 을 넘으면 + lag-extra-ticks) 이면 그 틱에 Roll.tryRoll. 같은 틱에 둘 다 오면 R = P.</li>
 *   <li>창이 열려 키가 모두 떼어진 것 (뗌과 함께 방향키·점프·달리기가 사라졌다), 누름과 뗌 사이에 우리 창을 띄웠거나 상자 따위가
 *       열렸으면 구르지 않는다. 남는 구멍: 가만히 서서 누르고 0.25초 안에 E (인벤토리) 나 T (채팅) 를 열면 서버는 그 화면을 알 수 없어
 *       뒷걸음이 한 번 나갈 수 있다.</li>
 *   <li>회복 중 (다음 구르기를 받기 전) 에 뗀 짧은 누름은 buffer 틱 동안 기억했다가 되는 첫 틱에 구른다. 공중에서 뗀 것은 기억하지 않는다.</li>
 * </ul>
 * controls.roll-key: f 면 아무것도 하지 않는다 (F 가 구른다, Roll.onSwap). both 면 둘 다.
 * 시험 줄: ROLL_TAP held=&lt;R−P&gt; press=&lt;P&gt; t=&lt;R&gt;, ROLL_TAP_SKIP why=hold|attack|use|swap|drop|screen|dialog|vehicle|dead|unborn held= t=.
 */
public final class SneakTap implements Listener {
    /** 뗌 하나의 판정. roll 이 거짓이면 why 가 까닭. */
    public record Decision(boolean roll, String why, int held) {
        static final Decision NONE = new Decision(false, null, 0);
    }

    /**
     * 순수한 판정 (13.1 의 SneakTapJudgeTest, 가짜 시계). 한 사람의 누름·뗌 상태.
     */
    public static final class Judge {
        private boolean pressed;
        private long pressTick;
        private String blocked;
        private String combo;

        /** 누름. blocked 가 있으면 이 누름은 구르기가 될 수 없다 (까닭). */
        public void press(long t, String blockedWhy) {
            pressed = true;
            pressTick = t;
            blocked = blockedWhy;
            combo = null;
        }

        /** 누르는 동안 새 입력 (attack, use, swap, drop). 처음 것만 적는다. */
        public void combo(String why) {
            if (pressed && combo == null) combo = why;
        }

        public boolean pressed() {
            return pressed;
        }

        public long pressTick() {
            return pressTick;
        }

        /**
         * 뗌. window = 짧은 누름으로 치는 가장 긴 틱. screen: 창이 열려 키가 모두 떼어졌다. dialog: 누름과 뗌 사이에 우리 창이 떴다.
         * 누르지 않았는데 뗐으면 NONE.
         */
        public Decision release(long t, int window, boolean screen, boolean dialog) {
            if (!pressed) return Decision.NONE;
            pressed = false;
            int held = (int) Math.max(0, t - pressTick);
            if (blocked != null) return new Decision(false, blocked, held);
            if (combo != null) return new Decision(false, combo, held);
            if (screen) return new Decision(false, "screen", held);
            if (dialog) return new Decision(false, "dialog", held);
            if (held > window) return new Decision(false, "hold", held);
            return new Decision(true, null, held);
        }
    }

    private final Souls plugin;
    private final Map<UUID, Judge> judges = new HashMap<>();
    /** 회복 중에 뗀 짧은 누름: 이 틱까지 기다린다 */
    private final Map<UUID, Long> buffered = new HashMap<>();
    /** 서버가 연 창 (상자 따위) 의 틱 */
    private final Map<UUID, Long> invOpen = new HashMap<>();
    /** 마지막 판정 (/soulstest tap) */
    private final Map<UUID, String> last = new HashMap<>();

    public SneakTap(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.ControlsCfg cfg() {
        return plugin.cfg().controls;
    }

    private Judge judge(Player p) {
        return judges.computeIfAbsent(p.getUniqueId(), k -> new Judge());
    }

    public String lastLine(Player p) {
        return last.getOrDefault(p.getUniqueId(), "ROLL_TAP none");
    }

    /** 짧은 누름으로 치는 가장 긴 틱 (핑이 lag-ping 을 넘으면 + lag-extra-ticks). */
    public int window(Player p) {
        Config.ControlsCfg c = cfg();
        return c.tapMaxTicks() + (p.getPing() > c.lagPing() ? c.lagExtraTicks() : 0);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInput(PlayerInputEvent e) {
        Player p = e.getPlayer();
        if (!cfg().sneakRolls() || !plugin.worlds().ours(p.getWorld())) return;
        Input now = e.getInput(), before = p.getCurrentInput();
        boolean was = before.isSneak(), is = now.isSneak();
        if (was == is) return;
        long t = plugin.ticker().now();
        Judge j = judge(p);
        if (is) {
            String why = null;
            if (p.isDead()) why = "dead";
            else if (p.isInsideVehicle()) why = "vehicle";
            else if (plugin.start().unborn(p)) why = "unborn";
            else if (plugin.ui().open(p) || t - plugin.ui().shownAt(p) <= 2) why = "dialog";
            j.press(t, why);
            return;
        }
        long pressAt = j.pressTick();
        // 창이 열리면 클라이언트가 키를 모두 뗀다 (KeyMapping.releaseAll): 방향키·점프·달리기가 웅크리기와 함께 사라졌다
        boolean screen = (before.isForward() || before.isBackward() || before.isLeft() || before.isRight() || before.isJump() || before.isSprint())
                && !(now.isForward() || now.isBackward() || now.isLeft() || now.isRight() || now.isJump() || now.isSprint());
        Long inv = invOpen.get(p.getUniqueId());
        if (inv != null && inv >= pressAt - 1 && inv <= t + 1) screen = true;
        long shown = plugin.ui().shownAt(p);
        boolean dialog = plugin.ui().open(p) || (shown >= pressAt - 1 && shown <= t + 1);
        Decision d = j.release(t, window(p), screen, dialog);
        if (d.why() == null && !d.roll()) return;
        if (!d.roll()) {
            skip(p, d.why(), d.held(), t);
            if ("unborn".equals(d.why())) plugin.start().reopen(p, "roll");
            return;
        }
        String line = "ROLL_TAP held=" + d.held() + " press=" + pressAt + " t=" + t + " window=" + window(p) + " ping=" + p.getPing();
        last.put(p.getUniqueId(), line);
        plugin.test(p, line);
        roll(p, t);
    }

    private void skip(Player p, String why, int held, long t) {
        String line = "ROLL_TAP_SKIP why=" + why + " held=" + held + " t=" + t;
        last.put(p.getUniqueId(), line);
        plugin.test(p, line);
    }

    /** 짧은 누름이 판정되었다: 회복 중이면 기억해 두고, 아니면 곧바로 구른다 (막힌 까닭은 Roll 의 ROLL_DENY). */
    private void roll(Player p, long t) {
        if (!Stamina.fighting(p)) return;
        CombatState st = CombatState.of(p);
        if (!st.canRollAgain(t) && cfg().buffer() > 0) {
            buffered.put(p.getUniqueId(), t + cfg().buffer());
            plugin.test(p, "ROLL_TAP_BUFFER until=" + (t + cfg().buffer()) + " t=" + t);
            return;
        }
        plugin.roll().tryRoll(p);
    }

    /** Ticker: 기억한 짧은 누름을 되는 첫 틱에. */
    public void tick(long now) {
        if (buffered.isEmpty()) return;
        buffered.entrySet().removeIf(en -> {
            Player p = plugin.getServer().getPlayer(en.getKey());
            if (p == null) return true;
            CombatState st = CombatState.of(p);
            if (st.canRollAgain(now)) {
                plugin.test(p, "ROLL_TAP_BUFFERED t=" + now);
                plugin.roll().tryRoll(p);
                return true;
            }
            if (now > en.getValue()) {
                skip(p, "buffer", 0, now);
                return true;
            }
            return false;
        });
    }

    // ------------------------------------------------------------------ 누르는 동안의 조합 입력

    private void combo(Player p, String why) {
        Judge j = judges.get(p.getUniqueId());
        if (j != null) j.combo(why);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PlayerArmSwingEvent e) {
        combo(e.getPlayer(), "attack");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        combo(e.getPlayer(), "attack");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        switch (e.getAction()) {
            case LEFT_CLICK_AIR, LEFT_CLICK_BLOCK -> combo(e.getPlayer(), "attack");
            case RIGHT_CLICK_AIR, RIGHT_CLICK_BLOCK -> combo(e.getPlayer(), "use");
            default -> {
            }
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        combo(e.getPlayer(), "use");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        combo(e.getPlayer(), "swap");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDrop(PlayerDropItemEvent e) {
        combo(e.getPlayer(), "drop");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInventory(InventoryOpenEvent e) {
        if (e.getPlayer() instanceof Player p) invOpen.put(p.getUniqueId(), plugin.ticker().now());
    }

    /** Q 가 맨손이거나 표적 고정이면 버리기 이벤트가 없다: 표적 고정 (M1) 이 이것을 부른다. */
    public void comboFromTargetLock(Player p) {
        combo(p, "drop");
    }

    @EventHandler
    public void onRespawn(PlayerPostRespawnEvent e) {
        judges.remove(e.getPlayer().getUniqueId());
        buffered.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        judges.remove(id);
        buffered.remove(id);
        invOpen.remove(id);
        last.remove(id);
    }
}
