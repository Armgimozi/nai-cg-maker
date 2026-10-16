package kr.labyrinth.combat;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.FluidCollisionMode;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.ChunkUnloadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 시전 무기 마법탄 (0.3.6.1) — 지팡이·홀 같은 시전 무기({@link WeaponAttack.Style#CASTER})의 좌클릭 = 조준선으로 날아가는 마법탄.
 * <ul>
 *   <li>좌클릭 감지 = 주손 {@link PlayerArmSwingEvent} (Paper 26.3 의 좌클릭 패킷 하나에 한 번). 규칙은 {@link CasterBoltRules#punch}.
 *       몹을 직접 클릭하면 {@link AttackClock} 이 그 공격을 막고 같은 시계로 그 몹에게 바로 넣는다({@link #fire} 의 strike).</li>
 *   <li>공격 시계: 근접·활과 같은 {@link AttackTiming} (무기 간격 ÷ 민첩 공속, 하한 0.25초). 너무 빨리 누르면 아무것도 안 나간다
 *       (간격 끝 0.35초 안이면 한 번 기억했다가 그때 바라보는 쪽으로). MP 는 들지 않는다.</li>
 *   <li>피해 = 예전 휘두르기와 같은 한 방 (무기 W × 지능 배율 × 마법 피해, 치명타 그대로) — {@code DamageContext.basic(…, MAGIC)}
 *       + 쏜 순간의 W·피해 종류. 점프 치명(떨어지며 친 근접 ×1.2)은 없다 (화살처럼).</li>
 *   <li>비행: 엔티티를 만들지 않는다. 틱마다 한 걸음(기본 2.5칸, 16칸까지) — 블록 광선({@code rayTraceBlocks}, 통과 가능한 풀·횃불은 지나감)
 *       + 그 걸음 상자 안 살아 있는 적의 히트박스({@link BoltPath#firstHit}). 처음 닿는 적 하나만, 벽 뒤는 못 맞힘, 블록은 바꾸지 않는다.</li>
 *   <li>적 = {@code services.targets().isEnemy} (몹·보스의 실제 몸 엔티티, PvP 가 되는 상대). 모델 파트(ItemDisplay)·아군·NPC·주민·
 *       갑옷 거치대·액자는 그냥 지나간다. 맞는 순간 다시 확인 (파티·안전지대가 그사이 바뀌었으면 안 맞음).</li>
 *   <li>정리: 나간 사람·월드를 옮긴 사람·죽은 사람의 마법탄, 청크가 내려간 곳의 마법탄은 바로 지운다. 다음 걸음 청크가 안 올라와 있으면
 *       그 자리에서 사라진다 (청크를 불러오지 않음).</li>
 * </ul>
 */
final class CasterBolts implements Listener {

    /** 한 사람이 동시에 날릴 수 있는 마법탄 수 (간격 하한 0.25초 × 비행 7틱이면 2발이라 넉넉함). */
    static final int MAX_PER_PLAYER = 6;
    /** 서버 전체 동시 마법탄 상한. */
    static final int MAX_TOTAL = 256;
    /** 쏜 사람 시야를 가리지 않게 눈앞 이만큼은 입자를 안 그린다 (블록). */
    static final double TRAIL_SKIP = 0.9;
    /** 꼬리 입자 간격 (블록). */
    static final double TRAIL_STEP = 0.45;
    /** 시험·진단용 (서버를 -Dlabyrinth.debug.bolts=true 로 켜면 맞을 때마다 로그 한 줄). 설정 파일 키는 아님. */
    static final boolean DEBUG = Boolean.getBoolean("labyrinth.debug.bolts");

    private final Services services;
    private final DamageService damage;
    private AttackClock clock;
    private volatile CasterBoltConfig cfg = CasterBoltConfig.DEFAULT;
    private final List<Bolt> flying = new ArrayList<>();
    /** 이미 쓴 클릭의 틱 (몹 직접 클릭·버리기·우클릭·창 열기). */
    private final Map<UUID, Integer> consumedTick = new HashMap<>();
    /** 마지막으로 마법탄을 쏜 틱 — 같은 클릭의 다른 패킷(허공 휘두름이 먼저 오고 몹 클릭이 뒤따라도)이 두 번째 시도를 하지 않게. */
    private final Map<UUID, Integer> firedTick = new HashMap<>();
    private final Map<String, Color> colors = new ConcurrentHashMap<>();
    private BukkitTask task;

    /** 쏜 순간의 무기 (날아가는 사이 무기를 바꿔도 이 값). */
    record Shot(String weaponId, double perHit, DamageKind kind, Color color) {}

    /** 날아가는 마법탄 하나. */
    static final class Bolt {
        final UUID shooter;
        final World world;
        final BoltPath path;
        final Shot shot;
        int ticks;
        /** 목록에서 빠짐 (tick 이 사본을 돌 때 건너뛰게). */
        boolean removed;

        Bolt(UUID shooter, World world, BoltPath path, Shot shot) {
            this.shooter = shooter;
            this.world = world;
            this.path = path;
            this.shot = shot;
        }
    }

    CasterBolts(Services services, DamageService damage) {
        this.services = services;
        this.damage = damage;
    }

    void start(AttackClock clock) {
        this.clock = clock;
        configure();
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 1L, 1L);
    }

    void stop() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        flying.clear();
        consumedTick.clear();
        firedTick.clear();
    }

    /** config.yml combat.caster_bolt 다시 읽기 (켤 때·/labadmin reload). 툴팁·도감 글도 따른다. */
    void configure() {
        CasterBoltConfig c;
        try {
            c = CasterBoltConfig.from(services.plugin().getConfig().getConfigurationSection("combat"));
        } catch (Throwable t) {
            Log.error("combat.caster_bolt 읽기 오류 — 기본값을 씁니다", t);
            c = CasterBoltConfig.DEFAULT;
        }
        cfg = c;
        colors.clear();
        WeaponAttack.casterBolt(c.enabled());
        if (!c.enabled()) flying.clear();
    }

    CasterBoltConfig config() { return cfg; }

    // ── 누가 마법탄을 쓰나 ────────────────────────────────────────────────

    /**
     * 지금 좌클릭이 마법탄인가: 켜짐 + 주손에 시전 무기 + 요구 능력치 충족(못 맞추면 맨손 취급 — 능력치 계산의 무기와 같은 기준).
     */
    boolean ready(Player p) {
        if (!cfg.enabled() || p == null) return false;
        ItemDef def = services.items().heldWeapon(p);
        if (def == null || !WeaponAttack.of(def).caster()) return false;
        WeaponAttack derived = services.stats().get(p).weapon();
        return derived != null && derived.caster();
    }

    // ── 좌클릭 ────────────────────────────────────────────────────────────

    private static int tickNow() { return Bukkit.getCurrentTick(); }

    private void consume(Player p) { consumedTick.put(p.getUniqueId(), tickNow()); }

    private boolean consumed(Player p) {
        Integer t = consumedTick.get(p.getUniqueId());
        return t != null && CasterBoltRules.consumed(t, tickNow());
    }

    /** 이번 틱(또는 바로 앞 틱)에 이미 한 발 쐈는가 — 몹 직접 클릭 패킷이 허공 휘두름 뒤에 와도 같은 클릭으로 본다. */
    boolean firedThisClick(Player p) {
        Integer t = firedTick.get(p.getUniqueId());
        return t != null && CasterBoltRules.consumed(t, tickNow());
    }

    /**
     * 몹·엔티티를 직접 클릭 (취소됐든 아니든): 뒤따르는 휘두름은 이미 쓴 클릭. 실제 처리는 {@link AttackClock#onPreAttack}.
     * 다만 시전 무기로 손 닿는 아군·PvP 가 안 되는 플레이어를 가리키고 누른 클릭(다른 기능이 막지 않은 것)은 뒤따르는 휘두름이
     * 그대로 마법탄이 된다 — 마법탄은 그 플레이어를 지나 뒤의 적에게 간다 ({@link CasterBoltRules#throughPlayer}).
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPreAttack(PrePlayerAttackEntityEvent e) {
        Player p = e.getPlayer();
        boolean player = e.getAttacked() instanceof Player;
        if (CasterBoltRules.throughPlayer(player && ready(p), player, player && services.targets().isEnemy(p, e.getAttacked()), e.isCancelled())) {
            return;
        }
        consume(p);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDrop(PlayerDropItemEvent e) { consume(e.getPlayer()); }

    /**
     * 우클릭으로 블록·아이템을 씀 (상자 열기·무기 스킬 등), 또는 좌클릭한 블록을 다른 기능이 썼음 (미궁 금 간 벽·포자 주머니·퍼즐 블록·상자 —
     * 그 기능이 막아 둔 클릭, Paper 는 어드벤처 블록 좌클릭을 휘두름 바로 앞에 알린다) — 같은 틱의 휘두름은 그 동작의 것.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        Action a = e.getAction();
        if (a == Action.RIGHT_CLICK_AIR || a == Action.RIGHT_CLICK_BLOCK
                || a == Action.LEFT_CLICK_BLOCK && e.useInteractedBlock() == org.bukkit.event.Event.Result.DENY) {
            consume(e.getPlayer());
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteractEntity(PlayerInteractEntityEvent e) { consume(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onOpen(InventoryOpenEvent e) { if (e.getPlayer() instanceof Player p) consume(p); }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND || clock == null) return;
        Player p = e.getPlayer();
        boolean caster = ready(p);
        if (!caster) return;
        GameMode gm = p.getGameMode();
        boolean canBreak = gm == GameMode.SURVIVAL || gm == GameMode.CREATIVE;
        CasterBoltRules.Punch k = CasterBoltRules.punch(true, consumed(p), busy(p), canBreak, canBreak && blockInReach(p));
        if (k != CasterBoltRules.Punch.BOLT) return;
        clock.casterClick(p, null);
    }

    /** 지금은 쏠 수 없음: 관전·죽음·기절·잠·창이 열려 있음. */
    boolean busy(Player p) {
        if (p.isDead() || p.getGameMode() == GameMode.SPECTATOR || p.isSleeping()) return true;
        if (services.effects().isStunned(p)) return true;
        InventoryType open = p.getOpenInventory().getType();
        return open != InventoryType.CRAFTING && open != InventoryType.CREATIVE;
    }

    /** 조준선이 손 닿는 블록에 닿는가 (서바이벌에서 그 클릭은 캐기). */
    private static boolean blockInReach(Player p) {
        AttributeInstance a = p.getAttribute(Attribute.BLOCK_INTERACTION_RANGE);
        double reach = a == null ? 4.5 : a.getValue();
        Location eye = p.getEyeLocation();
        return p.getWorld().rayTraceBlocks(eye, eye.getDirection(), reach, FluidCollisionMode.NEVER, false) != null;
    }

    // ── 쏘기 ──────────────────────────────────────────────────────────────

    /** 쏜 순간의 무기 (한 방 W · 피해 종류 · 색). */
    private Shot shot(Player p) {
        DerivedStats s = services.stats().get(p);
        ItemDef def = services.items().heldWeapon(p);
        String id = def == null ? "" : def.id();
        return new Shot(id, s.weaponDamage(), s.weaponKind(), color(def));
    }

    Color color(ItemDef def) {
        if (def == null) return Color.fromRGB(CasterBoltRules.DEFAULT_COLOR);
        return colors.computeIfAbsent(def.id(), k -> {
            List<String> pal = def.texture() == null ? List.of() : def.texture().strings("palette");
            return Color.fromRGB(CasterBoltRules.trailColor(pal, CasterBoltRules.DEFAULT_COLOR));
        });
    }

    /**
     * 공격 시계가 통과시킨 마법탄 한 발 ({@link AttackClock} 이 부른다).
     * @param strike 직접 클릭한(또는 기억했다가 아직 손 닿는) 적 — 바로 맞는다. null = 조준선으로 날아간다.
     */
    void fire(Player p, LivingEntity strike) {
        if (p == null || !p.isOnline()) return;
        firedTick.put(p.getUniqueId(), tickNow());
        Shot shot = shot(p);
        Location eye = p.getEyeLocation();
        CasterBoltConfig c = cfg;
        if (c.sound()) {
            float pitch = (float) (1.65 + Math.random() * 0.2);
            p.getWorld().playSound(eye, Sound.BLOCK_AMETHYST_BLOCK_CHIME, SoundCategory.PLAYERS, 0.45f, pitch);
        }
        if (strike != null) {
            Vector to = strike.getBoundingBox().getCenter();
            if (c.trail()) trail(p.getWorld(), eye.toVector(), to, shot.color());
            hit(p, strike, shot, to);
            return;
        }
        BoltPath path = new BoltPath(eye.toVector(), eye.getDirection(), c.speed(), c.range());
        Bolt b = new Bolt(p.getUniqueId(), p.getWorld(), path, shot);
        if (step(b, p)) return; // 첫 걸음은 바로 (가까운 적은 지연 없이)
        int mine = 0;
        for (Bolt o : flying) if (o.shooter.equals(b.shooter)) mine++;
        if (mine >= MAX_PER_PLAYER || flying.size() >= MAX_TOTAL) return; // 넘치면 이 한 발은 첫 걸음에서 사라진 것으로
        flying.add(b);
    }

    // ── 비행 ──────────────────────────────────────────────────────────────

    private void tick() {
        if (flying.isEmpty()) return;
        int maxTicks = cfg.maxTicks();
        // 사본을 돈다: 걸음 안의 피해가 죽음·월드 이동·나가기를 부르면 drop() 이 그 자리에서 목록을 고친다
        // (PvP 에서 상대가 쏜 마법탄이 날던 중에 상대를 쓰러뜨리면 ConcurrentModificationException 이었음)
        for (Bolt b : List.copyOf(flying)) {
            if (b.removed) continue; // 이번 틱에 이미 지워짐 (쏜 사람이 쓰러짐 등)
            Player p = Bukkit.getPlayer(b.shooter);
            boolean gone;
            try {
                gone = p == null || !p.isOnline() || p.isDead() || !p.getWorld().equals(b.world) || ++b.ticks > maxTicks || step(b, p);
            } catch (Throwable t) {
                Log.error("마법탄 비행 오류", t);
                gone = true;
            }
            if (gone) {
                b.removed = true;
                flying.remove(b);
            }
        }
    }

    /** 한 걸음. @return 끝났으면 true (맞음·벽·다 감·청크 없음) */
    private boolean step(Bolt b, Player p) {
        BoltPath path = b.path;
        double len = path.nextStep();
        if (len <= 1e-6) return true;
        Vector from = path.position();
        Vector dir = path.direction();
        Vector to = path.ahead(len);
        if (!loaded(b.world, from, to)) return true;
        Location fromLoc = from.toLocation(b.world);
        RayTraceResult block = b.world.rayTraceBlocks(fromLoc, dir, len, FluidCollisionMode.NEVER, true);
        double blockDist = block == null ? Double.POSITIVE_INFINITY : block.getHitPosition().distance(from);
        double radius = cfg.radius();
        BoundingBox area = BoltPath.segmentBox(from, dir, Math.min(len, blockDist), radius);
        List<BoltPath.Candidate<LivingEntity>> cands = new ArrayList<>(4);
        for (Entity e : b.world.getNearbyEntities(area, e -> e instanceof LivingEntity && !e.equals(p))) {
            LivingEntity le = (LivingEntity) e;
            if (le.isDead() || !le.isValid() || !services.targets().isEnemy(p, le)) continue;
            cands.add(new BoltPath.Candidate<>(le, le.getBoundingBox()));
        }
        BoltPath.Hit<LivingEntity> hit = BoltPath.firstHit(from, dir, len, radius, blockDist, cands);
        CasterBoltConfig c = cfg;
        if (hit != null) {
            Vector at = from.clone().add(dir.clone().multiply(hit.distance()));
            if (c.trail()) trailSegment(b, from, at);
            hit(p, hit.target(), b.shot, at);
            return true;
        }
        if (block != null) {
            Vector at = block.getHitPosition();
            if (c.trail()) {
                trailSegment(b, from, at);
                b.world.spawnParticle(Particle.DUST, at.toLocation(b.world), 4, 0.08, 0.08, 0.08, 0,
                        new Particle.DustOptions(b.shot.color(), 0.9f), false);
            }
            return true;
        }
        if (c.trail()) trailSegment(b, from, to);
        path.advance(len);
        if (path.done()) {
            if (c.trail()) b.world.spawnParticle(Particle.DUST, to.toLocation(b.world), 2, 0.05, 0.05, 0.05, 0,
                    new Particle.DustOptions(b.shot.color(), 0.7f), false);
            return true;
        }
        return false;
    }

    /** 선분이 지나는 청크가 모두 올라와 있는가 (마법탄이 청크를 불러오지 않게). */
    private static boolean loaded(World w, Vector a, Vector b) {
        int x0 = (int) Math.floor(Math.min(a.getX(), b.getX())) >> 4, x1 = (int) Math.floor(Math.max(a.getX(), b.getX())) >> 4;
        int z0 = (int) Math.floor(Math.min(a.getZ(), b.getZ())) >> 4, z1 = (int) Math.floor(Math.max(a.getZ(), b.getZ())) >> 4;
        for (int x = x0; x <= x1; x++) for (int z = z0; z <= z1; z++) if (!w.isChunkLoaded(x, z)) return false;
        return true;
    }

    // ── 맞음 ──────────────────────────────────────────────────────────────

    /** 맞은 적에게 기본 공격 한 방 (마법). 맞는 순간 다시 적인지 본다. */
    private void hit(Player p, LivingEntity target, Shot shot, Vector at) {
        if (!target.isValid() || target.isDead() || !target.getWorld().equals(p.getWorld())) return;
        if (!services.targets().isEnemy(p, target)) return;
        DamageContext ctx = DamageContext.basic(p, target, 1.0, DamageType.MAGIC).kind(shot.kind()).weaponHit(shot.perHit()).casterBolt();
        CasterBoltConfig c = cfg;
        if (target instanceof Player && c.pvpKnockback() > 0) ctx.knockback(c.pvpKnockback());
        damage.deal(ctx);
        World w = target.getWorld();
        Location l = at.toLocation(w);
        if (c.trail()) w.spawnParticle(Particle.DUST, l, 6, 0.15, 0.15, 0.15, 0, new Particle.DustOptions(shot.color(), 1.1f), false);
        if (c.sound()) w.playSound(l, Sound.BLOCK_AMETHYST_BLOCK_HIT, SoundCategory.PLAYERS, 0.6f, 1.4f);
        if (DEBUG) {
            Log.info("[마법탄] " + p.getName() + " → " + target.getType() + " " + target.getUniqueId().toString().substring(0, 8)
                    + " 피해 " + String.format(java.util.Locale.ROOT, "%.1f", ctx.finalDamage())
                    + (ctx.cancelled() ? " (막힘)" : ctx.evaded() ? " (회피)" : ctx.crit() ? " (치명)" : ""));
        }
    }

    // ── 입자 ──────────────────────────────────────────────────────────────

    private void trailSegment(Bolt b, Vector from, Vector to) {
        Vector origin = b.path.position().subtract(b.path.direction().multiply(b.path.travelled())); // 쏜 자리 (눈)
        trail(b.world, from, to, b.shot.color(), origin);
    }

    private static void trail(World w, Vector from, Vector to, Color color) { trail(w, from, to, color, from); }

    /** from → to 에 입자 (쏜 자리 origin 에서 {@link #TRAIL_SKIP} 안쪽은 건너뜀 — 쏜 사람 시야). */
    private static void trail(World w, Vector from, Vector to, Color color, Vector origin) {
        Vector d = to.clone().subtract(from);
        double len = d.length();
        if (len < 1e-6) return;
        d.multiply(1.0 / len);
        Particle.DustOptions opt = new Particle.DustOptions(color, 0.9f);
        for (double t = 0; t <= len; t += TRAIL_STEP) {
            Vector pt = from.clone().add(d.clone().multiply(t));
            if (pt.distanceSquared(origin) < TRAIL_SKIP * TRAIL_SKIP) continue;
            w.spawnParticle(Particle.DUST, pt.toLocation(w), 1, 0.02, 0.02, 0.02, 0, opt, false);
        }
    }

    // ── 정리 ──────────────────────────────────────────────────────────────

    private void drop(UUID u) {
        flying.removeIf(b -> b.shooter.equals(u) && (b.removed = true));
        consumedTick.remove(u);
        firedTick.remove(u);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { drop(e.getPlayer().getUniqueId()); }

    @EventHandler
    public void onWorld(PlayerChangedWorldEvent e) { drop(e.getPlayer().getUniqueId()); }

    @EventHandler
    public void onDeath(PlayerDeathEvent e) { drop(e.getEntity().getUniqueId()); }

    @EventHandler
    public void onChunkUnload(ChunkUnloadEvent e) {
        if (flying.isEmpty()) return;
        World w = e.getWorld();
        int cx = e.getChunk().getX(), cz = e.getChunk().getZ();
        flying.removeIf(b -> b.world.equals(w) && ((int) Math.floor(b.path.position().getX()) >> 4) == cx
                && ((int) Math.floor(b.path.position().getZ()) >> 4) == cz && (b.removed = true));
    }

    /** 지금 날고 있는 마법탄 수 (진단용). */
    int flyingCount() { return flying.size(); }
}
