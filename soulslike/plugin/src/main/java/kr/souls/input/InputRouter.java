package kr.souls.input;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.MoveRunner;
import kr.souls.combat.Stamina;
import kr.souls.combat.Swings;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 좌클릭 입력의 한 곳 (2.3, 3.6, M1 P1a). 이벤트 처리기는 적기만 하고, 정하는 것은 Ticker 의 input 자리 ({@link #tick}) 다 (M1_PLAN 0.6).
 * <ul>
 *   <li>PrePlayerAttackEntityEvent (HIGH, 취소된 것도): 우리 세계에서는 늘 취소한다 (바닐라 근접 공격은 없다). 겨눈 대상과 틱은 조준
 *       힌트로만 적는다. 입력은 만들지 않는다 (R2: 바닐라는 공격 → 휘두르기, mineflayer 는 휘두르기 → 공격 차례로 보낸다).
 *       PvpGuard (LOW) 가 먼저 PVP_BLOCK path=melee 를 낸다.</li>
 *   <li>PlayerArmSwingEvent (주손만, MONITOR, 취소된 것도): 약공격·강공격·달리기 공격의 유일한 입력. 클라이언트는 좌클릭마다 휘두른다
 *       (적·허공·블록·우리 물체). 그때의 웅크리기 (getCurrentInput) 와 달리기를 적는다: 웅크리기 + 휘두르기 = 강공격, 달리며 휘두르기 =
 *       달리기 공격.</li>
 *   <li>휘두름 잠금 (2026-10-11): 우리 세계에서는 PlayerArmSwingEvent 를 늘 취소한다 (HIGH, 두 손). 클라이언트의 휘두르기 패킷이 서버 쪽
 *       휘두름 (다른 사람에게 보이는 팔, 서버의 휘두름 시계) 을 다시 시작하지 않아, 서버 휘두름은 combat/Swings 만 다시 시작하고 휘둘렀는지
 *       정확히 안다. 입력은 그대로 적힌다 (MONITOR 는 취소된 것도 받는다). 곁효과: 다른 사람에게 우클릭 (문 따위) 의 팔 휘두름이 보이지 않는다.
 *       지금 다른 사람에게 보이는 팔 휘두름은 공격 동작의 시작 하나뿐이다 (MoveRunner.start 의 Swings.main). 패링 몸짓 (P3) 과 왼손 공격
 *       (P6) 은 아직 휘두르지 않는다 (들어오면 Swings 로 휘두른다).</li>
 *   <li>되돌림 장부 (2026-10-11, LOWEST, 두 손): 휘두르기를 받은 그때 그 손의 장부 (CombatState.echoMain·echoOff) 에서 하나를 쓰면
 *       되돌아온 것이다 (FakeSwingFilter.Ledger, CombatState.lastSwingEcho: 같은 이벤트의 SneakTap 도 본다). 표시 뒤의 가짜는 장부를 쓰지
 *       않는다. 공격 패킷 바로 뒤의 주손 휘두르기 (바닐라는 적을 누르면 공격 → 휘두르기 차례로 보낸다) 는 진짜 클릭이라 장부를 쓰지 않는다.
 *       서버가 휘두른 뒤 한 왕복이 지나기 전에 온 주손 휘두르기 (이른 휘두르기: 되돌림이 닿기 전에 누른 클릭) 는 진짜로 치되, 장부가 정할
 *       때까지 묶어 둔다 (input 자리에서 그 뒤의 휘두르기도 차례를 지켜 기다린다): 되돌림이 오면 받은 틱과 그때의 웅크리기·달리기로 입력이
 *       되고 (MOVE_HELD), 끝 틱이 지나도록 되돌림이 오지 않으면 그것이 되돌림이었다 (MOVE_FAKE why=echo early=1). 그 사이의 지연은 공격 동작
 *       중이라 입력 기억에 든다.</li>
 *   <li>가짜 휘두르기 표시 (MONITOR, 취소된 것도, R1): PlayerDropItemEvent, PlayerInteractEvent RIGHT_*, PlayerInteractEntityEvent.
 *       그 뒤 fake-swing-window 틱 안의 휘두르기는 버린다 (FakeSwingFilter.mark). 되돌아온 휘두르기도 버린다.</li>
 *   <li>input 자리: 우리 세계, 출신을 고름, 싸우는 모드 (Stamina.fighting), 살아 있음을 보고 (R18) MoveRunner.input. 같은 틱이나 앞
 *       틱의 공격 패킷이 겨눈 대상을 조준 힌트로 붙인다.</li>
 *   <li>준비·판정 중에 마시기·술 (CONSUMABLE 이 있는 아이템) 을 시작하려 하면 사용을 막는다 (setUseItemInHand DENY, R17. 쓰지 않으니 횟수·
 *       마나가 그대로). 회복 중에는 된다 ("빨리 마시기").</li>
 * </ul>
 * 시험 줄: MOVE_FAKE why=mark|echo [early=1] t=, MOVE_HELD swing= t=, USE_DENY why=attack item= hand= t=.
 */
public final class InputRouter implements Listener {
    /**
     * 휘두르기 하나 (받은 틱, 그때 웅크렸나·달렸나, 되돌아온 것인가, 묶어 둔 이른 휘두르기인가와 그때의 받는 끝 틱).
     */
    private record Swing(long tick, boolean sneak, boolean sprint, boolean echo, boolean held, long deadline) {}

    /** 겨눈 대상 (조준 힌트) */
    private record Aim(UUID target, long tick) {}

    private final Souls plugin;
    private final MoveRunner moves;
    /** 사람마다 정하지 않은 휘두르기 (받은 차례대로. 묶어 둔 이른 휘두르기가 앞에 있으면 뒤의 것도 기다린다) */
    private final Map<UUID, ArrayDeque<Swing>> pending = new LinkedHashMap<>();
    private final Map<UUID, Aim> aims = new HashMap<>();
    private final Map<UUID, Long> marks = new HashMap<>();

    public InputRouter(Souls plugin, MoveRunner moves) {
        this.plugin = plugin;
        this.moves = moves;
    }

    private long now() {
        return plugin.ticker().now();
    }

    // ── 적기 ──

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = false)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        Player p = e.getPlayer();
        if (!plugin.worlds().ours(p.getWorld())) return;
        e.setCancelled(true);
        long now = now();
        aims.put(p.getUniqueId(), new Aim(e.getAttacked().getUniqueId(), now));
        // 바닐라는 이 공격 패킷 바로 뒤에 휘두르기를 보낸다: 그 휘두르기는 진짜 클릭이다 (classify, 2026-10-11)
        CombatState.of(p).attackAt = now;
    }

    /** 되돌림 장부 (LOWEST: 같은 이벤트의 다른 처리기보다 먼저 정한다). 두 손 모두. */
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void classify(PlayerArmSwingEvent e) {
        Player p = e.getPlayer();
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st == null) return;
        st.lastSwingEcho = false;
        st.lastSwingHeld = false;
        if (!plugin.worlds().ours(p.getWorld())) return;
        long now = now();
        // 표시 뒤의 가짜 (Q·우클릭·물체 클릭이 덧붙인 휘두르기) 는 표시 규칙이 버린다: 장부를 쓰면 뒤에 온 진짜 되돌림이 공격이 된다
        if (FakeSwingFilter.mark(now, markOf(p), plugin.cfg().tuning.input.fakeSwingWindow())) return;
        boolean off = e.getHand() == EquipmentSlot.OFF_HAND;
        // 같은 틱의 공격 패킷 바로 뒤에 온 주손 휘두르기는 적을 누른 진짜 클릭이다 (되돌림은 공격 패킷 없이 온다)
        if (!off && st.attackAt == now) {
            st.attackAt = CombatState.NEVER;
            return;
        }
        FakeSwingFilter.Verdict v = (off ? st.echoOff : st.echoMain).take(now, !off);
        st.lastSwingEcho = v == FakeSwingFilter.Verdict.ECHO;
        st.lastSwingHeld = !off && v == FakeSwingFilter.Verdict.EARLY;
    }

    /** 휘두름 잠금: 우리 세계에서는 클라이언트의 휘두르기가 서버 쪽 휘두름을 다시 시작하지 않는다 (두 손). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = false)
    public void onSwingLock(PlayerArmSwingEvent e) {
        if (plugin.worlds().ours(e.getPlayer().getWorld())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = false)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        if (!plugin.worlds().ours(p.getWorld())) return;
        CombatState st = CombatState.peek(p.getUniqueId());
        boolean held = st != null && st.lastSwingHeld;
        pending.computeIfAbsent(p.getUniqueId(), k -> new ArrayDeque<>())
                .add(new Swing(now(), p.getCurrentInput().isSneak(), p.isSprinting(), st != null && st.lastSwingEcho, held,
                        held ? st.echoMain.until() : CombatState.NEVER));
    }

    private void mark(Player p) {
        marks.put(p.getUniqueId(), now());
    }

    private long markOf(Player p) {
        Long mk = marks.get(p.getUniqueId());
        return mk == null ? FakeSwingFilter.NEVER : mk;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = false)
    public void onDrop(PlayerDropItemEvent e) {
        mark(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = false)
    public void onInteract(PlayerInteractEvent e) {
        switch (e.getAction()) {
            case RIGHT_CLICK_AIR, RIGHT_CLICK_BLOCK -> mark(e.getPlayer());
            default -> {
            }
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = false)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        mark(e.getPlayer());
    }

    /** R17: 준비·판정 중의 마시기·술 시작을 막는다 (HIGH: 다른 처리기가 보기 전에 정한다). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = false)
    public void onUse(PlayerInteractEvent e) {
        switch (e.getAction()) {
            case RIGHT_CLICK_AIR, RIGHT_CLICK_BLOCK -> {
            }
            default -> {
                return;
            }
        }
        Player p = e.getPlayer();
        ItemStack it = e.getItem();
        if (!MoveRunner.consumable(it) || !moves.attacking(p, now())) return;
        e.setUseItemInHand(Event.Result.DENY);
        plugin.test(p, "USE_DENY why=attack item=" + it.getType().getKey().getKey() + " hand=" + e.getHand() + " t=" + now());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        pending.remove(id);
        aims.remove(id);
        marks.remove(id);
    }

    // ── 정하기 (input 자리) ──

    /**
     * Ticker 의 input 자리: 지난 틱까지 적은 휘두르기를 받은 차례대로 입력으로. 묶어 둔 이른 휘두르기는 장부가 정할 때까지 (되돌림이 오거나
     * 받는 끝 틱이 지날 때까지) 그 자리에서 기다리고, 뒤의 것도 차례를 지켜 기다린다 (입력 기억은 나중 것이 앞의 것을 바꾼다).
     */
    public void tick(long now) {
        if (pending.isEmpty()) return;
        kr.souls.combat.CombatTuning.Input cfg = plugin.cfg().tuning.input;
        for (UUID id : new ArrayList<>(pending.keySet())) {
            ArrayDeque<Swing> q = pending.get(id);
            Player p = Bukkit.getPlayer(id);
            if (p == null || q == null) {
                pending.remove(id);
                continue;
            }
            CombatState st = CombatState.peek(id);
            long mark = markOf(p);
            while (!q.isEmpty()) {
                Swing s = q.peekFirst();
                if (s.held()) {
                    FakeSwingFilter.Verdict v = st == null ? FakeSwingFilter.Verdict.REAL : st.echoMain.settle(now, s.deadline());
                    if (v == null) break;
                    q.pollFirst();
                    if (v == FakeSwingFilter.Verdict.ECHO) {
                        plugin.test(p, "MOVE_FAKE why=echo early=1 swing=" + s.tick() + " mark=" + Swings.last(p, EquipmentSlot.HAND) + " t=" + now);
                        continue;
                    }
                    plugin.test(p, "MOVE_HELD swing=" + s.tick() + " sneak=" + s.sneak() + " t=" + now);
                } else {
                    q.pollFirst();
                }
                // 되돌아온 휘두르기 (휘두르기를 받은 그때 장부로 정했다): mark= 는 서버가 주손을 마지막으로 휘두른 틱
                if (s.echo()) {
                    plugin.test(p, "MOVE_FAKE why=echo swing=" + s.tick() + " mark=" + Swings.last(p, EquipmentSlot.HAND) + " t=" + now);
                    continue;
                }
                String fake = FakeSwingFilter.why(s.tick(), mark, cfg.fakeSwingWindow());
                if (fake != null) {
                    plugin.test(p, "MOVE_FAKE why=" + fake + " swing=" + s.tick() + " mark=" + mark + " t=" + now);
                    continue;
                }
                if (!gate(p)) continue;
                InputBuffer.Kind kind = s.sneak() ? InputBuffer.Kind.HEAVY : s.sprint() ? InputBuffer.Kind.RUNNING : InputBuffer.Kind.LIGHT;
                Aim a = aims.get(p.getUniqueId());
                UUID target = a != null && a.tick() >= s.tick() - 1 && a.tick() <= s.tick() ? a.target() : null;
                moves.input(p, kind, target, now);
            }
            if (q.isEmpty()) pending.remove(id);
        }
    }

    /** 입력을 받는 사람인가 (R18): 우리 세계, 출신을 고름, 싸우는 모드, 살아 있음. */
    private boolean gate(Player p) {
        return plugin.worlds().ours(p.getWorld()) && !plugin.start().unborn(p) && Stamina.fighting(p) && !p.isDead();
    }
}
