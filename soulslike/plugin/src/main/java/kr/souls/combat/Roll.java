package kr.souls.combat;

import com.destroystokyo.paper.event.entity.EntityKnockbackByEntityEvent;
import kr.souls.Config;
import kr.souls.Souls;
import kr.souls.util.Fx;
import org.bukkit.Bukkit;
import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.SoundGroup;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 구르기 시제품 (3.3). F(손 바꾸기)를 누르면 누르고 있는 WASD 쪽으로 구른다. 방향키가 없으면 뒷걸음.
 * 공중·물속·사다리·탈것 위에서는 안 된다. 막다가 F 를 누르면 막기를 풀고 구른다 (2.3.7).
 * 무적이 막는 것: 원인 물체가 있는 피해(적이 일으킨 피해), 바닐라 밀림. 막지 않는 것: 낙하, 용암, 공허, 불붙음.
 * M1 에서 적 공격은 IncomingHitQueue 가 무적 구간과 판정 틱을 맞대어 본다 (핑 보정). 지금은 서버 틱 그대로다.
 * 웅크리기 + F 는 무기 기술 자리라 (M3) 지금은 아무것도 하지 않는다.
 *
 * 돌진처럼 보이지 않게: 한 번 튕기는 대신 glide 틱 동안 같은 빠르기로 밀다가 끝 두 틱에 줄여 멈추고,
 * 구르는 동안 머리 위 칸에 그 사람 화면에만 보이는 방벽을 깔아 클라이언트가 스스로 기어가기 자세로 바꾸게 한다
 * (1인칭은 시야가 바닥까지 내려갔다 올라오고, 3인칭은 몸이 눕는다). 방벽은 진짜 블록이 아니라 다른 사람과 서버는 모른다.
 */
public final class Roll implements Listener {
    private final Souls plugin;
    /** 사람마다 화면에만 깔아 둔 방벽 자리 */
    private final Map<UUID, Set<Pos>> fakes = new HashMap<>();

    private record Pos(int x, int y, int z) {
        Block in(org.bukkit.World w) {
            return w.getBlockAt(x, y, z);
        }
    }

    public Roll(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.RollCfg cfg() {
        return plugin.cfg().roll;
    }

    @EventHandler(priority = EventPriority.LOW)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        if (!plugin.worlds().ours(p.getWorld())) return;
        // F 는 손 바꾸기가 아니다 (왼손 방패는 인벤토리에서 든다)
        e.setCancelled(true);
        if (!Stamina.fighting(p) || p.isSneaking()) return;
        tryRoll(p);
    }

    /** 구른다. 구르지 못하면 false (이유는 시험 줄로). */
    public boolean tryRoll(Player p) {
        long now = plugin.ticker().now();
        CombatState st = CombatState.of(p);
        String why = blocked(p, st, now);
        if (why != null) {
            plugin.test(p, "ROLL_DENY why=" + why + " t=" + now);
            return false;
        }
        Input in = p.getCurrentInput();
        double f = (in.isForward() ? 1 : 0) - (in.isBackward() ? 1 : 0);
        double r = (in.isRight() ? 1 : 0) - (in.isLeft() ? 1 : 0);
        double yaw = Math.toRadians(p.getYaw());
        Vector fwd = new Vector(-Math.sin(yaw), 0, Math.cos(yaw));
        Vector right = new Vector(-Math.cos(yaw), 0, -Math.sin(yaw));
        Vector dir = fwd.clone().multiply(f).add(right.multiply(r));
        boolean back = dir.lengthSquared() < 1e-4;
        Config.RollKind kind = back ? cfg().kind("backstep") : cfg().kind(cfg().load());
        if (back) dir = fwd.clone().multiply(-1);

        if (!plugin.stamina().spend(p, kind.cost(), now + kind.end())) {
            plugin.test(p, "ROLL_DENY why=stamina t=" + now);
            return false;
        }
        // 막기·마시기를 풀고 구른다 (마시다 멈추면 횟수를 쓰지 않는다)
        if (p.hasActiveItem()) p.clearActiveItem();

        st.rollStart = now;
        st.roll = kind;
        st.rollFrom = p.getLocation();
        st.rollReported = false;
        st.rollDir = dir.normalize();
        push(p, st, kind, 0);
        if (cfg().spinVisual() && !back) p.startRiptideAttack(7, 0f, null);
        if (cfg().crawl() && !back) crawl(p);
        visual(p, true);
        plugin.test(p, String.format(Locale.ROOT, "ROLL kind=%s dir=%s cost=%.0f st=%.1f t=%d",
                kind.id(), dirName(f, r), kind.cost(), st.stamina.cur(), now));
        return true;
    }

    /** 땅 위인지는 클라이언트가 알려 준 값을 믿는다 (혼자 하는 서버라 속일 사람이 없다). */
    @SuppressWarnings("deprecation")
    private String blocked(Player p, CombatState st, long now) {
        if (!p.isOnGround()) return "air";
        if (p.isInWater() || p.isSwimming()) return "water";
        if (p.isClimbing()) return "climbing";
        if (p.isInsideVehicle()) return "vehicle";
        if (p.isGliding() || p.isFlying()) return "flying";
        if (!st.canRollAgain(now)) return "recovering";
        if (!st.stamina.canAct()) return "stamina";
        return null;
    }

    private static String dirName(double f, double r) {
        if (f == 0 && r == 0) return "back";
        StringBuilder sb = new StringBuilder();
        if (f > 0) sb.append("fwd");
        if (f < 0) sb.append("bwd");
        if (r > 0) sb.append(sb.isEmpty() ? "right" : "+right");
        if (r < 0) sb.append(sb.isEmpty() ? "left" : "+left");
        return sb.toString();
    }

    /** t 틱째에 미는 힘. 끝 두 틱은 줄여서 미끄러지지 않고 멈춰 선다. 위아래는 첫 틱만 (뒷걸음의 작은 뜀). */
    private void push(Player p, CombatState st, Config.RollKind kind, long t) {
        double speed = kind.horizontal();
        if (t >= kind.glide() - 2) speed *= t == kind.glide() - 1 ? 0.35 : 0.65;
        Vector v = st.rollDir.clone().multiply(speed);
        v.setY(t == 0 ? kind.vertical() : Math.min(p.getVelocity().getY(), 0));
        p.setVelocity(v);
    }

    /** 발밑 먼지와 땅을 구르는 소리. start 가 아니면 일어서며 땅을 짚는 소리. */
    private void visual(Player p, boolean start) {
        Location feet = p.getLocation();
        Block below = feet.clone().subtract(0, 0.2, 0).getBlock();
        Material m = below.getType().isSolid() ? below.getType() : Material.DEEPSLATE;
        BlockData bd = m.createBlockData();
        p.getWorld().spawnParticle(Particle.BLOCK, feet.clone().add(0, 0.1, 0), start ? 10 : 6, 0.25, 0.02, 0.25, 0, bd);
        SoundGroup g = bd.getSoundGroup();
        if (start) {
            Fx.sound(feet, cfg().sound(), cfg().volume(), cfg().pitch());
            p.getWorld().playSound(feet, g.getStepSound(), g.getVolume() * 0.8f, g.getPitch() * 0.75f);
        } else {
            p.getWorld().playSound(feet, g.getFallSound(), g.getVolume() * 0.7f, g.getPitch() * 0.8f);
        }
    }

    /** 머리 위 칸(발 블록 + 1)과 그 둘레 8칸 중 빈 칸에 이 사람 화면에만 방벽을 깐다. 구르며 움직이므로 틱마다 다시 깐다. */
    private void crawl(Player p) {
        Set<Pos> want = new HashSet<>();
        Location l = p.getLocation();
        int bx = l.getBlockX(), by = l.getBlockY() + 1, bz = l.getBlockZ();
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                Block b = p.getWorld().getBlockAt(bx + dx, by, bz + dz);
                if (b.getType().isAir()) want.add(new Pos(b.getX(), b.getY(), b.getZ()));
            }
        }
        Set<Pos> have = fakes.computeIfAbsent(p.getUniqueId(), k -> new HashSet<>());
        for (Iterator<Pos> it = have.iterator(); it.hasNext(); ) {
            Pos k = it.next();
            if (want.contains(k)) continue;
            Block b = k.in(p.getWorld());
            p.sendBlockChange(b.getLocation(), b.getBlockData());
            it.remove();
        }
        BlockData barrier = Material.BARRIER.createBlockData();
        for (Pos k : want) {
            if (have.add(k)) p.sendBlockChange(k.in(p.getWorld()).getLocation(), barrier);
        }
    }

    /** 깔아 둔 방벽을 거둔다 (진짜 블록 모양으로 다시 보낸다). */
    private void uncrawl(Player p) {
        Set<Pos> have = fakes.remove(p.getUniqueId());
        if (have == null || !p.isOnline()) return;
        for (Pos k : have) {
            Block b = k.in(p.getWorld());
            p.sendBlockChange(b.getLocation(), b.getBlockData());
        }
    }

    /** 플러그인을 끌 때: 깔린 방벽을 모두 거둔다. */
    public void shutdown() {
        for (Player p : Bukkit.getOnlinePlayers()) uncrawl(p);
        fakes.clear();
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        fakes.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent e) {
        uncrawl(e.getPlayer());
    }

    @EventHandler
    public void onTeleport(PlayerTeleportEvent e) {
        uncrawl(e.getPlayer());
    }

    @EventHandler
    public void onWorld(PlayerChangedWorldEvent e) {
        fakes.remove(e.getPlayer().getUniqueId());
    }

    /** Ticker: 구르기가 끝난 틱에 시험 줄 (서버에서 잰 거리), 걸어 둔 시험 피해. */
    public void tick(long now) {
        for (Player p : Bukkit.getOnlinePlayers()) {
            CombatState st = CombatState.peek(p.getUniqueId());
            if (st == null || st.roll == null) continue;
            long t = now - st.rollStart;
            if (t > 0 && t < st.roll.glide() && st.rollDir != null) push(p, st, st.roll, t);
            if (fakes.containsKey(p.getUniqueId())) {
                if (t < st.roll.glide() + 1) crawl(p);
                else uncrawl(p);
            }
            if (t == st.roll.glide()) visual(p, false);
            if (st.armedRollHit >= 0 && t == st.armedRollHit) {
                int off = st.armedRollHit;
                st.armedRollHit = -1;
                TestHits.Result res = plugin.testHits().hit(p, st.armedRollHitAmount, "generic", false);
                plugin.test(p, "ROLLHIT off=" + off + " iframes=" + st.roll.iframes() + " dodged=" + (res.dealt() <= 1e-6) + " " + res.line());
            }
            if (!st.rollReported && t >= st.roll.end()) {
                st.rollReported = true;
                Location a = st.rollFrom, b = p.getLocation();
                double dist = a == null || !a.getWorld().equals(b.getWorld()) ? -1
                        : Math.hypot(b.getX() - a.getX(), b.getZ() - a.getZ());
                plugin.test(p, String.format(Locale.ROOT, "ROLLEND kind=%s dist=%.2f st=%.1f t=%d", st.roll.id(), dist, st.stamina.cur(), now));
            }
        }
    }

    /** 무적: 원인 물체가 있는 피해만 피한다. 낙하·용암·공허·불붙음은 원인 물체가 없어 그대로 들어온다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st == null || !st.invulnerable(plugin.ticker().now())) return;
        Entity cause = e.getDamageSource().getCausingEntity();
        if (cause == null || cause == p) return;
        e.setCancelled(true);
        plugin.test(p, String.format(Locale.ROOT, "DODGE amount=%.2f t=%d", e.getDamage(), plugin.ticker().now()));
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onKnockback(EntityKnockbackByEntityEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st != null && st.invulnerable(plugin.ticker().now())) e.setCancelled(true);
    }
}
