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

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 좌클릭 입력의 한 곳 (2.3, 3.6, M1 P1a). 이벤트 처리기는 적기만 하고, 정하는 것은 Ticker 의 input 자리 ({@link #tick}) 다 (M1_PLAN 0.6).
 * <ul>
 *   <li>PrePlayerAttackEntityEvent (HIGH, 취소된 것도): 우리 세계에서는 늘 취소한다 (바닐라 근접 공격은 없다). 겨눈 대상과 틱은 조준
 *       힌트로만 적는다. 입력은 만들지 않는다 (R2: 바닐라는 공격 → 휘두르기, mineflayer 는 휘두르기 → 공격 차례로 보낸다).
 *       PvpGuard (LOW) 가 먼저 PVP_BLOCK path=melee 를 낸다.</li>
 *   <li>PlayerArmSwingEvent (주손만): 약공격·강공격·달리기 공격의 유일한 입력. 클라이언트는 좌클릭마다 휘두른다 (적·허공·블록·우리 물체).
 *       그때의 웅크리기 (getCurrentInput) 와 달리기를 적는다: 웅크리기 + 휘두르기 = 강공격, 달리며 휘두르기 = 달리기 공격.</li>
 *   <li>가짜 휘두르기 표시 (MONITOR, 취소된 것도, R1): PlayerDropItemEvent, PlayerInteractEvent RIGHT_*, PlayerInteractEntityEvent.
 *       그 뒤 fake-swing-window 틱 안의 휘두르기, 서버가 주손을 휘두른 뒤 왕복 + echo-window 틱 안의 휘두르기는 버린다 (FakeSwingFilter).</li>
 *   <li>input 자리: 우리 세계, 출신을 고름, 싸우는 모드 (Stamina.fighting), 살아 있음을 보고 (R18) MoveRunner.input. 같은 틱이나 앞
 *       틱의 공격 패킷이 겨눈 대상을 조준 힌트로 붙인다.</li>
 *   <li>준비·판정 중에 마시기·술 (CONSUMABLE 이 있는 아이템) 을 시작하려 하면 사용을 막는다 (setUseItemInHand DENY, R17. 쓰지 않으니 횟수·
 *       마나가 그대로). 회복 중에는 된다 ("빨리 마시기").</li>
 * </ul>
 * 시험 줄: MOVE_FAKE why=mark|echo t=, USE_DENY why=attack item= hand= t=.
 */
public final class InputRouter implements Listener {
    /** 휘두르기 하나 (받은 틱, 그때 웅크렸나·달렸나) */
    private record Swing(long tick, boolean sneak, boolean sprint) {}

    /** 겨눈 대상 (조준 힌트) */
    private record Aim(UUID target, long tick) {}

    private final Souls plugin;
    private final MoveRunner moves;
    private final Map<UUID, List<Swing>> pending = new LinkedHashMap<>();
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
        aims.put(p.getUniqueId(), new Aim(e.getAttacked().getUniqueId(), now()));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = false)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        if (!plugin.worlds().ours(p.getWorld())) return;
        pending.computeIfAbsent(p.getUniqueId(), k -> new ArrayList<>()).add(new Swing(now(), p.getCurrentInput().isSneak(), p.isSprinting()));
    }

    private void mark(Player p) {
        marks.put(p.getUniqueId(), now());
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

    /** Ticker 의 input 자리: 지난 틱까지 적은 휘두르기를 입력으로. */
    public void tick(long now) {
        if (pending.isEmpty()) return;
        Map<UUID, List<Swing>> got = new LinkedHashMap<>(pending);
        pending.clear();
        kr.souls.combat.CombatTuning.Input cfg = plugin.cfg().tuning.input;
        for (Map.Entry<UUID, List<Swing>> en : got.entrySet()) {
            Player p = Bukkit.getPlayer(en.getKey());
            if (p == null) continue;
            Long mk = marks.get(p.getUniqueId());
            long mark = mk == null ? FakeSwingFilter.NEVER : mk;
            long srv = Swings.last(p, EquipmentSlot.HAND);
            int echo = FakeSwingFilter.pingTicks(p.getPing()) + cfg.echoWindow();
            for (Swing s : en.getValue()) {
                String fake = FakeSwingFilter.why(s.tick(), mark, cfg.fakeSwingWindow(), srv <= CombatState.NEVER ? FakeSwingFilter.NEVER : srv, echo);
                if (fake != null) {
                    plugin.test(p, "MOVE_FAKE why=" + fake + " swing=" + s.tick() + " mark=" + (fake.equals("mark") ? mark : srv) + " t=" + now);
                    continue;
                }
                if (!gate(p)) continue;
                InputBuffer.Kind kind = s.sneak() ? InputBuffer.Kind.HEAVY : s.sprint() ? InputBuffer.Kind.RUNNING : InputBuffer.Kind.LIGHT;
                Aim a = aims.get(p.getUniqueId());
                UUID target = a != null && a.tick() >= s.tick() - 1 && a.tick() <= s.tick() ? a.target() : null;
                moves.input(p, kind, target, now);
            }
        }
    }

    /** 입력을 받는 사람인가 (R18): 우리 세계, 출신을 고름, 싸우는 모드, 살아 있음. */
    private boolean gate(Player p) {
        return plugin.worlds().ours(p.getWorld()) && !plugin.start().unborn(p) && Stamina.fighting(p) && !p.isDead();
    }
}
