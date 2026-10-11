package kr.souls.input;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import io.papermc.paper.event.player.PlayerStopUsingItemEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Souls;
import kr.souls.item.Weapons;
import org.bukkit.Input;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInputEvent;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemConsumeEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerToggleSprintEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * 입력 탐침 (M1 PS, M1_PLAN 2절의 S1~S13). 시험 모드에서 {@code /soulstest probe on} 으로 켠 사람의 입력 이벤트를 받은 그대로 한 줄씩 낸다.
 * 듣기만 한다 (MONITOR, ignoreCancelled=false: 공중 클릭은 이미 취소된 채 온다, 검토 R1). 바꾸는 것은 아직 없는 패키지를 흉내 내는 둘뿐이다:
 * {@code cancel attack} (P1a 가 엔터티 공격을 취소하는 것, S12) 과 {@code fswing} (P3 의 패링 몸짓: F 에 서버가 팔을 휘두른다, S3).
 *
 * <p>줄 꼴 (ASCII, 봇과 tools/client/probe_shots.sh 가 읽는다): 모든 줄에 같은 칸이 있고, 해당 없는 칸은 {@code -}.
 * <pre>
 * [T] PROBE ev=&lt;interact|swing|attack|damage|swap|input|drop|shoot|sprint|stopuse|consume|open|close|srvswing|move&gt;
 *           hand= action= cancelled= useItem= will= t= ms= seq= item= using= blocking= [더: in= block= target= dist= force= ticks=]
 * </pre>
 * <ul>
 *   <li>hand: HAND | OFF_HAND. action: PlayerInteractEvent 의 Action (ENTITY·ENTITY_AT 은 우클릭 엔터티), input 은 바뀐 키 (+sneak,-fwd).</li>
 *   <li>useItem: useItemInHand() (interact), will: willAttack() (attack). cancelled: MONITOR 에서 본 최종 값.</li>
 *   <li>t: 우리 틱 (Ticker), ms: 탐침을 켠 뒤 ms (같은 틱 안의 차례와 키 반복 간격, S2), seq: 켠 뒤 줄 번호.</li>
 *   <li>using: 쓰는 중인 손 (getActiveItemHand, 없으면 -), blocking: isBlocking().</li>
 * </ul>
 */
public final class InputProbe implements Listener {
    /** 한 사람의 탐침 설정 */
    private static final class Opts {
        final long t0 = System.nanoTime();
        long seq;
        boolean cancelAttack;
        /** F (손 바꾸기) 에 서버가 휘두를 손. null 이면 휘두르지 않는다 */
        EquipmentSlot fSwing;
        /** 틱마다 수평 이동량 줄 (move on, S12) */
        boolean move;
        org.bukkit.Location last;
    }

    private final Souls plugin;
    private final Map<UUID, Opts> on = new HashMap<>();

    public InputProbe(Souls plugin) {
        this.plugin = plugin;
    }

    // ------------------------------------------------------------------ 켜고 끄기 (cmd/test/ProbeTestCommands)

    public void enable(Player p, boolean yes) {
        if (yes) on.putIfAbsent(p.getUniqueId(), new Opts());
        else on.remove(p.getUniqueId());
    }

    public boolean enabled(Player p) {
        return on.containsKey(p.getUniqueId());
    }

    /** cancel attack|none. 켜지 않았으면 false. */
    public boolean cancelAttack(Player p, boolean yes) {
        Opts o = on.get(p.getUniqueId());
        if (o == null) return false;
        o.cancelAttack = yes;
        return true;
    }

    /** fswing main|off|none: F 를 받으면 서버가 그 손을 휘두른다 (P3 의 패링 몸짓 흉내). 켜지 않았으면 false. */
    public boolean fSwing(Player p, EquipmentSlot hand) {
        Opts o = on.get(p.getUniqueId());
        if (o == null) return false;
        o.fSwing = hand;
        return true;
    }

    /** 서버가 그 손을 지금 휘두른다 (swingMainHand / swingOffHand, S3·S13). 켰으면 srvswing 줄. */
    public void serverSwing(Player p, EquipmentSlot hand, String why) {
        p.swingHand(hand);
        Opts o = opts(p);
        if (o != null) line(p, o, "srvswing", hand.name(), why, null, null, null, p.getInventory().getItem(hand), "");
    }

    /** move on|off: 틱마다 클라이언트가 보낸 위치의 수평 이동량을 ev=move 줄로 (S12: 공격 뒤 ×0.6 이 클라이언트에서 일어나는지). */
    public boolean move(Player p, boolean yes) {
        Opts o = on.get(p.getUniqueId());
        if (o == null) return false;
        o.move = yes;
        o.last = null;
        return true;
    }

    /** Ticker 나 스케줄러가 틱마다 부른다: move 를 켠 사람의 수평 이동량 (움직일 때만). */
    public void tick() {
        if (on.isEmpty()) return;
        for (Map.Entry<UUID, Opts> en : on.entrySet()) {
            Opts o = en.getValue();
            if (!o.move) continue;
            Player p = plugin.getServer().getPlayer(en.getKey());
            if (p == null) continue;
            org.bukkit.Location l = p.getLocation();
            if (o.last != null && o.last.getWorld() == l.getWorld()) {
                double dx = l.getX() - o.last.getX(), dz = l.getZ() - o.last.getZ();
                double v = Math.sqrt(dx * dx + dz * dz);
                if (v > 1e-4) line(p, o, "move", null, "MOVE", null, null, null, null,
                        String.format(Locale.ROOT, " v=%.4f y=%.3f sprinting=%s", v, l.getY(), p.isSprinting())); // lang-machine
            }
            o.last = l;
        }
    }

    /** 지금 설정 한 줄 (PROBE_SET). */
    public String state(Player p) {
        Opts o = on.get(p.getUniqueId());
        return "PROBE_SET on=" + (o != null) + " cancel=" + (o != null && o.cancelAttack ? "attack" : "none") // lang-machine: 시험 줄
                + " fswing=" + (o == null || o.fSwing == null ? "none" : o.fSwing == EquipmentSlot.HAND ? "main" : "off")
                + " move=" + (o != null && o.move)
                + " t=" + plugin.ticker().now();
    }

    // ------------------------------------------------------------------ 줄

    private Opts opts(Player p) {
        if (!plugin.cfg().testMode) return null;
        return on.get(p.getUniqueId());
    }

    /** 공통 칸을 채운 줄을 낸다. extra 는 빈칸으로 시작하는 꼬리 (없으면 ""). */
    private void line(Player p, Opts o, String ev, String hand, String action, Object cancelled, Object useItem, Object will,
                      ItemStack item, String extra) {
        long ms = (System.nanoTime() - o.t0) / 1_000_000L;
        EquipmentSlot using = p.hasActiveItem() ? p.getActiveItemHand() : null;
        String s = "PROBE ev=" + ev + " hand=" + dash(hand) + " action=" + dash(action) // lang-machine: 시험 줄
                + " cancelled=" + dash(cancelled) + " useItem=" + dash(useItem) + " will=" + dash(will)
                + " t=" + plugin.ticker().now() + " ms=" + ms + " seq=" + (++o.seq)
                + " item=" + itemName(item) + " using=" + (using == null ? "-" : using.name()) + " blocking=" + p.isBlocking()
                + extra;
        plugin.test(p, s);
    }

    private static String dash(Object v) {
        if (v == null) return "-";
        String s = String.valueOf(v);
        return s.isEmpty() ? "-" : s;
    }

    /** 아이템 이름: 바닐라 종류 (소문자), souls 무기면 :id 를 붙인다. 비었으면 -. */
    private String itemName(ItemStack it) {
        if (it == null || it.isEmpty()) return "-";
        String m = it.getType().getKey().getKey();
        Weapons.Def d = plugin.weapons().of(it);
        return d == null ? m : m + ":" + d.id();
    }

    private static String hand(EquipmentSlot s) {
        return s == null ? null : s.name();
    }

    // ------------------------------------------------------------------ 이벤트

    /** cancelled 는 isCancelled() (= useInteractedBlock DENY, 공중 클릭은 늘 참, R1) 를 그대로 적는다. */
    @SuppressWarnings("deprecation")
    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        Block b = e.getClickedBlock();
        line(e.getPlayer(), o, "interact", hand(e.getHand()), e.getAction().name(), e.isCancelled(), e.useItemInHand(), null, e.getItem(),
                " useBlock=" + e.useInteractedBlock() + " block=" + (b == null ? "-" : b.getType().getKey().getKey())); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        Player p = e.getPlayer();
        String action = e instanceof PlayerInteractAtEntityEvent ? "ENTITY_AT" : "ENTITY";
        line(p, o, "interact", hand(e.getHand()), action, e.isCancelled(), null, null, p.getInventory().getItem(e.getHand()),
                target(p, e.getRightClicked()));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PlayerArmSwingEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        Player p = e.getPlayer();
        line(p, o, "swing", hand(e.getHand()), e.getAnimationType().name(), e.isCancelled(), null, null, p.getInventory().getItem(e.getHand()), "");
    }

    /** cancel attack: P1a 처럼 엔터티 공격을 취소한다 (기록은 MONITOR 에서 최종 값으로). */
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onAttackCancel(PrePlayerAttackEntityEvent e) {
        Opts o = opts(e.getPlayer());
        if (o != null && o.cancelAttack) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        Player p = e.getPlayer();
        line(p, o, "attack", "HAND", "ATTACK", e.isCancelled(), null, e.willAttack(), p.getInventory().getItemInMainHand(),
                target(p, e.getAttacked()) + " sprinting=" + p.isSprinting()); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player p)) return;
        Opts o = opts(p);
        if (o == null) return;
        line(p, o, "damage", "HAND", e.getCause().name(), e.isCancelled(), null, null, p.getInventory().getItemInMainHand(),
                target(p, e.getEntity()) + String.format(Locale.ROOT, " dmg=%.2f crit=%s", e.getFinalDamage(), e.isCritical())); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        Opts o = opts(p);
        if (o == null) return;
        line(p, o, "swap", null, "F", e.isCancelled(), null, null, p.getInventory().getItemInOffHand(),
                " main=" + itemName(p.getInventory().getItemInMainHand())); // lang-machine
        if (o.fSwing != null) serverSwing(p, o.fSwing, "F");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInput(PlayerInputEvent e) {
        Player p = e.getPlayer();
        Opts o = opts(p);
        if (o == null) return;
        Input now = e.getInput(), was = p.getCurrentInput();
        line(p, o, "input", null, changes(was, now), null, null, null, p.getInventory().getItemInMainHand(),
                " in=" + keys(now)); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDrop(PlayerDropItemEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        line(e.getPlayer(), o, "drop", null, "Q", e.isCancelled(), null, null, e.getItemDrop().getItemStack(), "");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onShoot(EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        Opts o = opts(p);
        if (o == null) return;
        line(p, o, "shoot", hand(e.getHand()), "SHOOT", e.isCancelled(), null, null, e.getBow(),
                String.format(Locale.ROOT, " force=%.3f", e.getForce())); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSprint(PlayerToggleSprintEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        line(e.getPlayer(), o, "sprint", null, e.isSprinting() ? "on" : "off", e.isCancelled(), null, null, null, "");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onStopUsing(PlayerStopUsingItemEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        line(e.getPlayer(), o, "stopuse", null, "STOP", null, null, null, e.getItem(), " ticks=" + e.getTicksHeldFor()); // lang-machine
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onConsume(PlayerItemConsumeEvent e) {
        Opts o = opts(e.getPlayer());
        if (o == null) return;
        line(e.getPlayer(), o, "consume", hand(e.getHand()), "CONSUME", e.isCancelled(), null, null, e.getItem(), "");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onOpen(InventoryOpenEvent e) {
        if (!(e.getPlayer() instanceof Player p)) return;
        Opts o = opts(p);
        if (o == null) return;
        line(p, o, "open", null, e.getInventory().getType().name(), e.isCancelled(), null, null, null, "");
    }

    /** 클라이언트가 자기 인벤토리 (E) 를 닫을 때도 온다 (열 때는 서버가 모른다, S11). */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof Player p)) return;
        Opts o = opts(p);
        if (o == null) return;
        line(p, o, "close", null, e.getInventory().getType().name(), null, null, null, null, " reason=" + e.getReason()); // lang-machine
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        on.remove(e.getPlayer().getUniqueId());
    }

    // ------------------------------------------------------------------ 도움

    /** 눈에서 그 엔터티 상자의 가장 가까운 점까지 (클라이언트의 공격 사거리는 이 거리로 잰다). */
    static double reach(Vector eye, BoundingBox box) {
        double x = Math.max(box.getMinX(), Math.min(eye.getX(), box.getMaxX()));
        double y = Math.max(box.getMinY(), Math.min(eye.getY(), box.getMaxY()));
        double z = Math.max(box.getMinZ(), Math.min(eye.getZ(), box.getMaxZ()));
        return eye.distance(new Vector(x, y, z));
    }

    private static String target(Player p, Entity e) {
        if (e == null) return " target=-";
        return String.format(Locale.ROOT, " target=%s dist=%.3f", e.getType().getKey().getKey(), // lang-machine
                reach(p.getEyeLocation().toVector(), e.getBoundingBox()));
    }

    /** 바뀐 키: +sneak,-fwd 꼴. 바뀐 것이 없으면 none. */
    static String changes(Input was, Input now) {
        StringBuilder b = new StringBuilder();
        flag(b, "fwd", was.isForward(), now.isForward());
        flag(b, "back", was.isBackward(), now.isBackward());
        flag(b, "left", was.isLeft(), now.isLeft());
        flag(b, "right", was.isRight(), now.isRight());
        flag(b, "jump", was.isJump(), now.isJump());
        flag(b, "sneak", was.isSneak(), now.isSneak());
        flag(b, "sprint", was.isSprint(), now.isSprint());
        return b.length() == 0 ? "none" : b.toString();
    }

    private static void flag(StringBuilder b, String name, boolean was, boolean now) {
        if (was == now) return;
        if (b.length() > 0) b.append(',');
        b.append(now ? '+' : '-').append(name);
    }

    /** 누른 키 모두: fwd,sneak 꼴. 없으면 none. */
    static String keys(Input in) {
        StringBuilder b = new StringBuilder();
        if (in.isForward()) b.append("fwd,");
        if (in.isBackward()) b.append("back,");
        if (in.isLeft()) b.append("left,");
        if (in.isRight()) b.append("right,");
        if (in.isJump()) b.append("jump,");
        if (in.isSneak()) b.append("sneak,");
        if (in.isSprint()) b.append("sprint,");
        return b.length() == 0 ? "none" : b.substring(0, b.length() - 1);
    }
}
