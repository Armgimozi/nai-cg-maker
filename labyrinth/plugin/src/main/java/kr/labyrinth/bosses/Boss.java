package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.UUID;
import java.util.function.Consumer;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import kr.labyrinth.event.MobKillEvent;
import kr.labyrinth.mobs.CustomMob;
import kr.labyrinth.mobs.RigMath;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.util.TriState;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Vector;

/**
 * 층 보스 공통 기반 (GDD §8): 자체 HP 풀(DamageService 경로), 페이즈(bosses.yml phases), 패턴 스케줄러(가중치·쿨다운·간격·상시),
 * 광폭화 타이머, 보스바(이름·칭호·페이즈) + 시전 바, 아레나 경계, 위협 표, 추격·기본 공격, {@link BossRig} 시전 애니메이션,
 * 기믹 부품(경고 장판·투사체·표식·테더·오브젝트·쫄 소환·넉백)과 정리(블록 복원 포함).
 * <p>
 * 하위 클래스(impl/FloorNNBoss)는 {@link #onSpawn()}(아레나 배치) · {@link #startPattern(String)}(쿨다운 패턴) ·
 * {@link #runInterval(String)}(interval 패턴) · {@link #tickSystem(String)}(상시 시스템) · {@link #onPhase(int)} 만 채우면 된다.
 * 수치는 전부 {@code def.pattern(key)} 의 YAML 값, 파티·난이도 배율은 {@link #scaling()} (GDD §8.4 + {@link MechanicScaling}).
 * <p>
 * 상태이상 규칙(ARCHITECTURE §4.1): 보스는 stun/root/빙결 면역(effects 가 거름) — 패턴 시작 전 {@code isStunned} 는 그래도 확인,
 * {@code interrupt} 신호는 {@code interruptible} 시전을 끊는다. 패턴 피해 대상은 {@link #players()}(TargetFilter·아레나 경계 통과).
 */
public abstract class Boss implements BossHandle {

    /** 보스 생성 인자 묶음 (BossFactory 로 넘어온다). */
    public record Init(Services services, LabBossService service, BossDef def, Location center, InstanceContext ctx, boolean adhoc) {}

    protected final Services services;
    protected final LabBossService service;
    protected final BossDef def;
    protected final InstanceContext ctx;
    protected final boolean adhoc;
    protected final Location center;
    protected final double arenaRadius;
    protected final double arenaHeight;
    protected final double floorY;
    protected final Random rng = new Random();
    protected final Mob entity;
    protected final BossRig rig;
    protected final BossFx fx;
    protected final PatternScheduler scheduler = new PatternScheduler(rng);

    private MechanicScaling scaling;
    private final double maxHp;
    private double hp;
    private final double baseDamage;
    private final double defenseValue;
    private int phase = 1;

    // 시간 (서비스 틱)
    protected long now;
    private final long spawnTick;
    private long busyUntil;
    private String casting;
    private String castName;
    private long castStart;
    private int castTicks;
    private boolean castInterruptible;
    private long stunUntil;
    private double vulnerable;
    private long vulnerableUntil;
    private long invulnUntil;
    private boolean untargetable;
    private boolean enraged;
    private final long enrageAt;
    private int enrageStacks;
    private boolean pathing = true;

    // 위협 (GDD §8.5)
    private final Map<UUID, Double> threat = new HashMap<>();
    private UUID tauntId;
    private long tauntUntil;
    private UUID targetId;
    private UUID lastDamager;

    // 애니메이션·이동
    protected float bodyYaw;
    private Float lockedYaw;
    private long nextAttack;
    private long attackTick = -100;
    private long hurtTick = -100;
    private double moveSpeed;
    private Location lastLoc;
    private long lastRepath;

    // 소유물
    private final List<Ticking> running = new ArrayList<>();
    private final List<Ticking> pending = new ArrayList<>();
    private final List<CustomMob> adds = new ArrayList<>();
    private final List<ObjectTarget> objects = new ArrayList<>();
    private final Map<Block, BlockData> placedBlocks = new java.util.LinkedHashMap<>();

    // 표시
    private final BossBar bar;
    private BossBar castBar;
    private final Set<UUID> viewers = new HashSet<>();
    private BossBar.Color barColor;
    private long barFlashUntil;

    private boolean dead;
    private boolean ended;
    private long deathTick = -1;
    private final List<Consumer<BossHandle>> deathCallbacks = new ArrayList<>();

    protected Boss(Init init) {
        this.services = init.services();
        this.service = init.service();
        this.def = init.def();
        this.ctx = init.ctx();
        this.adhoc = init.adhoc();
        this.center = init.center().clone();
        this.center.setYaw(0);
        this.center.setPitch(0);
        this.floorY = center.getY();
        this.arenaRadius = def.arena().dbl("radius", 14);
        this.arenaHeight = def.arena().dbl("height", 10);
        this.now = service.now();
        this.spawnTick = now;
        this.scaling = new MechanicScaling(ctx.partySize(), ctx.difficulty().id(), 1, false);
        this.maxHp = Math.max(1, def.hp() * ctx.hpMultiplier());
        this.hp = maxHp;
        this.baseDamage = def.damage() * ctx.damageMultiplier();
        this.defenseValue = def.defense();
        double enrageSec = enrageSeconds();
        this.enrageAt = enrageSec > 0 ? spawnTick + Math.round(enrageSec * 20) : Long.MAX_VALUE;

        // 히트박스 (투명·무음·목표 없음 — 이동은 Pathfinder 로 직접)
        Location spawnAt = center.clone();
        spawnAt.setYaw(180); // 입구(북쪽, −z)를 바라보며 등장
        this.bodyYaw = 180;
        this.entity = spawnHitbox(spawnAt);
        this.lastLoc = entity.getLocation();
        this.fx = new BossFx(services, def.id());
        this.rig = new BossRig(def.id(), def.model(), def.scale(), services.plugin().getConfig().getDouble("mobs.model_yaw_offset", 0.0));
        rig.spawn(spawnAt, def.id());

        String color = def.bossbar() == null ? "RED" : def.bossbar().toUpperCase(Locale.ROOT);
        BossBar.Color bc;
        try {
            bc = BossBar.Color.valueOf(color);
        } catch (IllegalArgumentException e) {
            bc = BossBar.Color.RED;
        }
        this.barColor = bc;
        this.bar = BossBar.bossBar(Text.mm(barTitle()), 1f, bc, BossBar.Overlay.NOTCHED_12);
    }

    /** 광폭화 시간(초): bosses.yml {@code enrage}(숫자 또는 {time}) — 없으면 300 + 30 × 층. 0 = 없음. */
    protected double enrageSeconds() {
        Params raw = def.raw();
        if (raw.get("enrage") instanceof Number n) return n.doubleValue();
        Params e = raw.sub("enrage");
        if (e.has("time")) return e.dbl("time", 0);
        return 300 + 30.0 * def.floor();
    }

    private Mob spawnHitbox(Location at) {
        String base = def.base() == null ? "IRON_GOLEM" : def.base().toUpperCase(Locale.ROOT);
        EntityType type;
        double hitScale = 1.0;
        switch (base) {
            case "SPIDER", "CAVE_SPIDER" -> { type = EntityType.PANDA; hitScale = 1.0; } // 벽 타기 없는 히트박스
            case "ENDERMAN" -> { type = EntityType.HUSK; hitScale = 1.3; }
            default -> {
                try {
                    type = EntityType.valueOf(base);
                } catch (IllegalArgumentException e) {
                    type = EntityType.IRON_GOLEM;
                }
            }
        }
        Class<? extends Entity> cls = type.getEntityClass();
        if (cls == null || !Mob.class.isAssignableFrom(cls)) cls = org.bukkit.entity.IronGolem.class;
        @SuppressWarnings("unchecked")
        Class<? extends Mob> mobCls = (Class<? extends Mob>) cls;
        final double attrScale = Math.max(0.25, Math.min(8, def.scale() * hitScale));
        final String instanceId = adhoc ? null : ctx.id();
        Mob e = at.getWorld().spawn(at, mobCls, false, ent -> {
            ent.setPersistent(false);
            ent.setRemoveWhenFarAway(false);
            ent.setInvisible(true);
            ent.setSilent(true);
            ent.setCanPickupItems(false);
            ent.setCustomNameVisible(false);
            ent.setDespawnInPeacefulOverride(TriState.FALSE);
            if (ent.getEquipment() != null) ent.getEquipment().clear();
            if (ent instanceof org.bukkit.entity.Ageable a) a.setAdult();
            attr(ent, Attribute.MAX_HEALTH, 1000);
            ent.setHealth(1000);
            attr(ent, Attribute.MOVEMENT_SPEED, Math.max(0.05, def.speed() <= 0 ? 0.22 : def.speed()));
            attr(ent, Attribute.SCALE, attrScale);
            attr(ent, Attribute.FOLLOW_RANGE, 64);
            attr(ent, Attribute.KNOCKBACK_RESISTANCE, 1.0);
            attr(ent, Attribute.ATTACK_DAMAGE, 0);
            attr(ent, Attribute.STEP_HEIGHT, 1.1);
            if (def.flying()) ent.setGravity(false);
            Keys.tagTransient(ent, Keys.BOSS, def.id());
            if (instanceId != null) ent.getPersistentDataContainer().set(Keys.INSTANCE, PersistentDataType.STRING, instanceId);
        });
        Bukkit.getMobGoals().removeAllGoals(e);
        return e;
    }

    protected static void attr(LivingEntity e, Attribute a, double v) {
        AttributeInstance i = e.getAttribute(a);
        if (i != null) i.setBaseValue(v);
    }

    // ── 하위 클래스가 채우는 것 ──────────────────────────────────────────

    /** 아레나 배치 (기둥·단상·밸브·해자…) + 시작 상태. 생성 직후 한 번. */
    protected abstract void onSpawn();

    /**
     * 쿨다운 패턴 시작. 스케줄러가 고른 키로 불린다.
     * @return 보스가 묶이는 시간(틱) — 이 동안 이동·기본 공격·다음 패턴 없음. 0 = 시작 안 함.
     */
    protected abstract int startPattern(String key);

    /** 패턴을 지금 쓸 수 있는가 (대상·오브젝트 조건). */
    protected boolean canUse(String key) { return true; }

    /** interval 패턴 (자기 타이머). 기본: startPattern 을 부르되 보스를 묶지 않음. */
    protected void runInterval(String key) { startPattern(key); }

    /** 상시 시스템 패턴 — 그 페이즈 동안 매 틱. */
    protected void tickSystem(String key) { }

    /** 매 틱 (기절·시전 중에도). */
    protected void onTick() { }

    /** 페이즈 진입 (2, 3 …). 진행 중 경고는 이미 정리됨. */
    protected void onPhase(int newPhase) { }

    /** 종료·사망 정리 (블록 복원은 기반이 한다). */
    protected void onEnd() { }

    /** 웅크리기 시작 (고치 탈출·밸브 등). */
    protected void onSneak(Player p) { }

    /** 아레나 안 플레이어가 받는 바닐라 피해 (용암 등) — 취소하려면 e.setCancelled(true). */
    protected void onPlayerVanillaDamage(Player p, EntityDamageEvent e) { }

    /** 이 플레이어는 보스 밀쳐내기 면역인가 (기본: 넉백 면역 상태이상). */
    protected boolean knockbackImmune(Player p) { return services.effects().isKnockbackImmune(p); }

    /** 주는 피해 추가 배율 (물 속 강화 등). 기본 1. */
    protected double outgoingMult() { return 1.0; }

    /** 받는 피해 감소 0~0.9 (기믹). 기본 0. */
    protected double incomingReduction() { return 0; }

    // ── 수명 ─────────────────────────────────────────────────────────────

    final void start() {
        scheduler.setCooldownMult(scaling.cooldownMult());
        scheduler.setPhase(rotation(1), def.patterns(), now);
        try {
            onSpawn();
        } catch (Throwable t) {
            Log.error("보스 아레나 배치 오류 (" + def.id() + ")", t);
        }
        say(def.line("intro"));
        rig.play(BossAnim.ROAR, 40, now);
        BossFx.sound(center, def.sounds().str("ambient"), 2f, (float) def.sounds().dbl("pitch", 1.0));
        BossFx.sound(center, Sound.ENTITY_WARDEN_ROAR, 0.6f, 0.8f);
        busyUntil = now + 40;
        refreshViewers();
        refreshPlate();
    }

    protected List<String> rotation(int ph) {
        List<String> r = def.rotation().get(ph);
        if (r == null) {
            for (int p = ph; p >= 1 && r == null; p--) r = def.rotation().get(p);
        }
        return r == null ? List.of() : r;
    }

    /** 서비스가 매 틱 호출. */
    final void tick(long tick) {
        this.now = tick;
        if (ended) return;
        if (dead) {
            tickDeath();
            return;
        }
        if (!entity.isValid() || rig.broken()) {
            Log.warn("보스 엔티티가 사라져 전투를 종료합니다 (" + def.id() + ")");
            end();
            return;
        }
        Location loc = entity.getLocation();
        double moved = Math.hypot(loc.getX() - lastLoc.getX(), loc.getZ() - lastLoc.getZ());
        moveSpeed = moveSpeed * 0.6 + moved * 0.4;
        lastLoc = loc.clone();
        leash(loc);
        rig.follow(entity.getLocation());

        // 진행형 효과
        if (!pending.isEmpty()) {
            running.addAll(pending);
            pending.clear();
        }
        for (Ticking t : new ArrayList<>(running)) {
            if (!running.contains(t)) continue; // 이번 틱에 다른 효과가 취소함
            boolean done;
            try {
                done = t.tick(now);
            } catch (Throwable ex) {
                Log.error("보스 효과 오류 (" + def.id() + ")", ex);
                done = true;
            }
            if (done) running.remove(t);
        }
        if (dead || ended) return;

        try {
            onTick();
            for (String sys : scheduler.systems()) tickSystem(sys);
            for (String key : scheduler.dueIntervals(now)) {
                if (!stunned()) runInterval(key);
            }
        } catch (Throwable ex) {
            Log.error("보스 기믹 오류 (" + def.id() + ")", ex);
        }

        if (!enraged && now >= enrageAt) enrage();
        if (enraged && (now - enrageAt) % 300 == 0 && now > enrageAt) {
            enrageStacks++;
            say("<dark_red>" + Text.strip(def.name()) + "의 분노가 더욱 커집니다! <gray>(피해 +" + (10 * enrageStacks) + "%)");
        }

        // 시전 끊기 신호
        if (casting != null && castInterruptible && services.effects().has(entity, "interrupt")) interruptCast();

        boolean stunned = stunned();
        if (stunned) {
            stopPath();
            if (rig.current(now) != BossAnim.STUN) rig.play(BossAnim.STUN, 20, now);
        } else {
            if (rig.current(now) == BossAnim.STUN) rig.stop();
            if (now >= busyUntil) {
                if (casting != null) endCast();
                lockedYaw = null;
                chase();
                if (now >= busyUntil) {
                    String key = scheduler.next(now, k -> !stunned() && canUse(k));
                    if (key != null) {
                        int busy = 0;
                        try {
                            busy = startPattern(key);
                        } catch (Throwable ex) {
                            Log.error("보스 패턴 시작 오류 (" + def.id() + "/" + key + ")", ex);
                        }
                        if (busy > 0) {
                            busyUntil = now + busy;
                            scheduler.busyUntil(busyUntil);
                        }
                    }
                }
            } else {
                stopPath();
            }
        }
        face();
        if (now % 2 == 0) rig.animate(bodyYaw, animState(), 2);
        if (now % 5 == 0) updateBars();
        if (now % 20 == 0) {
            refreshViewers();
            refreshPlate();
            fx.sweep();
            adds.removeIf(m -> !m.isAlive());
            pruneThreat();
        }
    }

    private RigMath.AnimState animState() {
        int atk = now - attackTick <= RigMath.ATTACK_TICKS + 2 ? (int) (now - attackTick) : -1;
        int hurt = now - hurtTick < RigMath.HURT_TICKS ? (int) (now - hurtTick) : -1;
        Player t = target();
        float headYaw = 0, headPitch = 0;
        if (t != null) {
            Vector d = t.getEyeLocation().toVector().subtract(entity.getEyeLocation().toVector());
            headYaw = BossMath.yawDelta(bodyYaw, BossMath.yawOf(d.getX(), d.getZ()));
            double h = Math.hypot(d.getX(), d.getZ());
            headPitch = (float) Math.toDegrees(Math.atan2(-d.getY(), Math.max(0.1, h)));
        }
        return new RigMath.AnimState(now, moveSpeed, atk, 2, -1, hurt, headYaw, headPitch, -1, t != null,
                entity.getUniqueId().getLeastSignificantBits());
    }

    private void face() {
        float want;
        if (lockedYaw != null) want = lockedYaw;
        else {
            Player t = target();
            if (t != null && now >= busyUntil) {
                Vector d = t.getLocation().toVector().subtract(entity.getLocation().toVector());
                want = d.lengthSquared() < 0.01 ? bodyYaw : BossMath.yawOf(d.getX(), d.getZ());
            } else want = bodyYaw;
        }
        bodyYaw = BossMath.turn(bodyYaw, want, stunned() ? 0 : 12f);
    }

    /** 아레나 밖으로 밀려나면 되돌린다 (돌진·넉백). */
    private void leash(Location loc) {
        if (loc.getWorld() != center.getWorld()) return;
        double d = Math.hypot(loc.getX() - center.getX(), loc.getZ() - center.getZ());
        boolean below = loc.getY() < floorY - 4;
        if (d > arenaRadius + 2 || below) {
            Vector back = center.toVector().subtract(loc.toVector()).setY(0);
            if (back.lengthSquared() > 1e-6) back.normalize();
            Location to = below ? center.clone() : center.clone().add(back.multiply(-(arenaRadius - 2)));
            to.setY(below ? floorY : Math.max(floorY, loc.getY()));
            entity.teleport(to);
        }
    }

    // ── 추격·기본 공격 ───────────────────────────────────────────────────

    protected double reach() { return 2.0 + def.scale() * 0.7; }

    private void chase() {
        Player t = target();
        if (t == null) {
            stopPath();
            return;
        }
        double dist = horizontal(entity.getLocation(), t.getLocation());
        if (pathing && dist > reach() * 0.85) {
            if (now - lastRepath >= 10 || !entity.getPathfinder().hasPath()) {
                entity.getPathfinder().moveTo(t.getLocation(), 1.0);
                lastRepath = now;
            }
        } else {
            stopPath();
        }
        if (dist <= reach() && now >= nextAttack && Math.abs(t.getLocation().getY() - entity.getLocation().getY()) < 3.5) {
            nextAttack = now + 40;
            attackTick = now;
            final UUID id = t.getUniqueId();
            pending.add(new Mechanics.Delay(now, 3, () -> {
                Player p = Bukkit.getPlayer(id);
                if (p != null && validPlayer(p) && horizontal(entity.getLocation(), p.getLocation()) <= reach() + 0.8) {
                    services.damage().deal(DamageContext.raw(entity, p, damage(), DamageType.MELEE).source("basic_attack"));
                    BossFx.sound(p.getLocation(), Sound.ENTITY_PLAYER_ATTACK_STRONG, 0.8f, 0.6f);
                }
            }, true));
        }
    }

    protected void stopPath() {
        if (entity.getPathfinder().hasPath()) entity.getPathfinder().stopPathfinding();
    }

    /** false = 패턴이 직접 움직이는 동안 길찾기 끔. */
    protected void setPathing(boolean on) {
        pathing = on;
        if (!on) stopPath();
    }

    protected static double horizontal(Location a, Location b) {
        return Math.hypot(a.getX() - b.getX(), a.getZ() - b.getZ());
    }

    // ── 시전 ─────────────────────────────────────────────────────────────

    /**
     * 시전 시작: 시전 바(보스바 아래 2번째), 애니메이션, 방향 고정. 반환값을 startPattern 에서 그대로 돌려주면 된다.
     * @param name   시전 바에 보일 한국어 패턴 이름
     * @param ticks  시전(경고) 시간
     * @param busy   보스가 묶이는 총 시간 (≥ ticks)
     */
    protected int cast(String key, String name, int ticks, int busy, BossAnim anim, Location faceTo, boolean interruptible) {
        casting = key;
        castName = name;
        castStart = now;
        castTicks = Math.max(1, ticks);
        castInterruptible = interruptible || def.pattern(key).bool("interruptible", false);
        if (anim != null && anim != BossAnim.NONE) rig.play(anim, Math.max(ticks + 6, 10), ticks / (double) Math.max(ticks + 6, 10), now);
        if (faceTo != null) faceNow(faceTo);
        stopPath();
        showCastBar();
        return Math.max(ticks, busy);
    }

    protected void faceNow(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector());
        if (d.lengthSquared() < 1e-4) return;
        float y = BossMath.yawOf(d.getX(), d.getZ());
        lockedYaw = y;
        bodyYaw = y;
    }

    protected void lockYaw(Float yaw) { lockedYaw = yaw; }

    /** 패턴이 진행 중 보스를 더 묶어 둔다 (지금부터 ticks). */
    protected void busyFor(int ticks) {
        busyUntil = Math.max(busyUntil, now + ticks);
        scheduler.busyUntil(busyUntil);
    }

    /** 패턴이 일찍 끝났다 — 곧바로 행동 재개 (최소 간격은 유지). */
    protected void releaseBusy() {
        busyUntil = now;
        scheduler.busyUntil(now);
    }

    protected Vector facing() { return new Vector(BossMath.yawX(bodyYaw), 0, BossMath.yawZ(bodyYaw)); }

    private void showCastBar() {
        if (castBar == null) {
            castBar = BossBar.bossBar(Text.mm(""), 0f, BossBar.Color.YELLOW, BossBar.Overlay.PROGRESS);
        }
        castBar.name(Text.mm("<yellow>⚠ " + castName + "</yellow>"));
        castBar.progress(0f);
        castBar.color(castInterruptible ? BossBar.Color.BLUE : BossBar.Color.YELLOW);
        for (Player p : viewerPlayers()) services.hud().showBossBar(p, "boss_cast", castBar);
    }

    private void endCast() {
        casting = null;
        for (Player p : viewerPlayers()) services.hud().hideBossBar(p, "boss_cast");
    }

    /** 시전 바만 따로 (긴 기믹 타이머 — 밸브 창 등). progress 0~1. */
    protected void timerBar(String name, float progress, BossBar.Color color) {
        if (castBar == null) castBar = BossBar.bossBar(Text.mm(""), 0f, color, BossBar.Overlay.PROGRESS);
        castBar.name(Text.mm(name));
        castBar.progress(Math.max(0f, Math.min(1f, progress)));
        castBar.color(color);
        for (Player p : viewerPlayers()) services.hud().showBossBar(p, "boss_cast", castBar);
    }

    protected void hideTimerBar() {
        if (casting == null) for (Player p : viewerPlayers()) services.hud().hideBossBar(p, "boss_cast");
    }

    private void interruptCast() {
        String k = casting;
        cancelPhaseBound();
        endCast();
        busyUntil = now + 20;
        rig.play(BossAnim.STUN, 20, now);
        BossFx.sound(entity.getLocation(), Sound.BLOCK_ANVIL_LAND, 0.8f, 1.6f);
        services.effects().clear(entity, "interrupt");
        broadcastBar("<aqua>시전 차단!</aqua> <gray>" + (castName == null ? k : castName));
    }

    public boolean casting() { return casting != null; }

    // ── 페이즈·광폭화 ────────────────────────────────────────────────────

    private void checkPhase() {
        int want = def.phaseAt(hp / maxHp);
        if (want > phase) enterPhase(want);
    }

    private void enterPhase(int newPhase) {
        phase = newPhase;
        scaling = scaling.withPhase(newPhase);
        scheduler.setCooldownMult(scaling.cooldownMult());
        cancelPhaseBound();
        endCast();
        invulnUntil = now + 30;
        busyUntil = Math.max(busyUntil, now + 30);
        lockedYaw = null;
        stunUntil = 0;
        pathing = true;
        untargetable = false;
        scheduler.setPhase(rotation(newPhase), def.patterns(), now + 30);
        say(def.line("phase" + newPhase));
        rig.play(BossAnim.ROAR, 30, now);
        barFlashUntil = now + 30;
        BossFx.sound(center, Sound.ENTITY_RAVAGER_ROAR, 1.6f, 0.6f);
        BossFx.particle(Particle.EXPLOSION, entity.getLocation().add(0, 1.5, 0), 3, 0.8, 0.8, 0.8, 0);
        try {
            onPhase(newPhase);
        } catch (Throwable t) {
            Log.error("보스 페이즈 전환 오류 (" + def.id() + ")", t);
        }
        updateBars();
    }

    private void enrage() {
        enraged = true;
        scaling = scaling.withEnraged(true);
        scheduler.setCooldownMult(scaling.cooldownMult());
        say("<dark_red><b>" + Text.strip(def.name()) + "이(가) 광폭화합니다!</b></dark_red> <gray>— 주는 피해 +50%, 패턴이 빨라집니다");
        rig.setGlow(Color.fromRGB(255, 40, 40));
        BossFx.sound(center, Sound.ENTITY_WITHER_SPAWN, 0.8f, 0.7f);
        updateBars();
    }

    public boolean enraged() { return enraged; }

    // ── 대상 ─────────────────────────────────────────────────────────────

    /** 패턴이 맞힐 수 있는 플레이어 (TargetFilter 적 + 아레나 안 + 살아 있음). 은신 포함(장판은 은신도 맞는다). */
    public List<Player> players() {
        List<Player> out = new ArrayList<>();
        World w = center.getWorld();
        if (w == null) return out;
        for (Player p : w.getPlayers()) if (validPlayer(p)) out.add(p);
        return out;
    }

    protected boolean validPlayer(Player p) {
        if (p == null || !p.isOnline() || p.isDead() || p.getWorld() != center.getWorld()) return false;
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return false;
        Location l = p.getLocation();
        if (horizontal(l, center) > arenaRadius + 6) return false;
        if (l.getY() < floorY - 6 || l.getY() > floorY + arenaHeight + 6) return false;
        try {
            if (services.dungeon().isDowned(p)) return false;
        } catch (Throwable ignored) {
            // dungeon 미구현
        }
        return services.targets().isEnemy(entity, p);
    }

    /** 대상으로 고를 수 있는 플레이어 (은신 제외). */
    public List<Player> targets() {
        List<Player> out = players();
        out.removeIf(p -> services.effects().isStealthed(p));
        return out;
    }

    /** 위협 1위 (도발 우선). */
    @Override
    public Player target() {
        List<Player> list = targets();
        if (list.isEmpty()) return null;
        if (tauntId != null && now < tauntUntil) {
            for (Player p : list) if (p.getUniqueId().equals(tauntId)) return p;
        }
        Player best = null;
        double bestT = -1;
        for (Player p : list) {
            double t = threat.getOrDefault(p.getUniqueId(), 0.0);
            if (t > bestT) {
                bestT = t;
                best = p;
            }
        }
        if (bestT <= 0) {
            // 아무도 때리지 않았으면 가장 가까운 사람
            best = list.stream().min(Comparator.comparingDouble(p -> p.getLocation().distanceSquared(entity.getLocation()))).orElse(best);
        }
        if (best != null) targetId = best.getUniqueId();
        return best;
    }

    protected Player randomTarget() {
        List<Player> list = targets();
        return list.isEmpty() ? null : list.get(rng.nextInt(list.size()));
    }

    protected Player farthest() {
        return targets().stream().max(Comparator.comparingDouble(p -> p.getLocation().distanceSquared(entity.getLocation()))).orElse(null);
    }

    /** 서로 다른 무작위 대상 n 명 (exclude 제외, 모자라면 있는 만큼). preferNotTop = 위협 1위는 마지막에. */
    protected List<Player> pickTargets(int n, Collection<Player> exclude, boolean preferNotTop) {
        List<Player> list = targets();
        if (exclude != null) list.removeAll(exclude);
        Collections.shuffle(list, rng);
        if (preferNotTop && list.size() > n) {
            Player top = target();
            if (top != null && list.remove(top)) list.add(top);
        }
        return new ArrayList<>(list.subList(0, Math.min(n, list.size())));
    }

    private void pruneThreat() {
        threat.keySet().removeIf(u -> {
            Player p = Bukkit.getPlayer(u);
            return p == null || !p.isOnline() || p.getWorld() != center.getWorld();
        });
    }

    // ── 피해·효과 헬퍼 ───────────────────────────────────────────────────

    /** 패턴 피해 원값 = 보스 damage × 배율 (GDD §8.4). */
    protected double dmg(Params p, String key, double def) { return damage() * p.dbl(key, def); }

    /** 패턴 피해 (회피 불가). @return 실제 피해 컨텍스트 */
    protected DamageContext hit(Player p, double amount, String patternId, DamageType type) {
        return services.damage().deal(DamageContext.raw(entity, p, amount, type).pattern(patternId));
    }

    /** 도형 안의 모든 플레이어에게 피해 + 추가 효과. @return 맞은 사람 */
    protected List<Player> hitShape(Telegraph.Shape s, double amount, String patternId, DamageType type, Consumer<Player> extra) {
        List<Player> out = new ArrayList<>();
        for (Player p : players()) {
            if (!s.contains(p.getLocation())) continue;
            hit(p, amount, patternId, type);
            if (extra != null) extra.accept(p);
            out.add(p);
        }
        return out;
    }

    /** 대상 최대 HP 비율 피해 (방어 무시). */
    protected void hitPct(Player p, double pct, String patternId) {
        services.damage().deal(DamageContext.percent(entity, p, pct).pattern(patternId).hideNumber());
    }

    /** 상태이상 (GDD §9.2 효과 id). */
    protected void effect(Player p, String id, double seconds, double potency) {
        if (id == null || id.isBlank()) return;
        services.effects().apply(p, id, seconds, potency, entity);
    }

    /**
     * 밀쳐내기 (GDD §8.2 Knockback): dir 방향(수평)으로 strength, 위로 vertical. 면역(넉백 면역 상태이상, 보스별 조건)이면 무시.
     * @return 실제로 밀었는가
     */
    protected boolean push(Player p, Vector dir, double strength, double vertical) {
        if (knockbackImmune(p)) {
            BossFx.dust(p.getLocation().add(0, 0.3, 0), Color.fromRGB(200, 200, 255), 1.2f, 6, 0.3);
            return false;
        }
        Vector d = dir.clone().setY(0);
        if (d.lengthSquared() < 1e-6) d = new Vector(rng.nextDouble() - 0.5, 0, rng.nextDouble() - 0.5);
        d.normalize().multiply(strength * scaling.speedMult());
        d.setY(vertical);
        p.setVelocity(p.getVelocity().multiply(0.2).add(d));
        return true;
    }

    /** 위치로 끌어당기기 (속도). */
    protected void pull(Player p, Location to, double strength) {
        if (knockbackImmune(p)) return;
        Vector d = to.toVector().subtract(p.getLocation().toVector()).setY(0);
        double len = d.length();
        if (len < 0.3) return;
        d.multiply(Math.min(strength, len * 0.35) / len);
        d.setY(Math.max(p.getVelocity().getY(), 0.12));
        p.setVelocity(d);
    }

    /** 경고 시간(틱) — 난이도 telegraph 배율 + 최소 0.5초 (GDD §8.1). */
    protected int windup(Params p, double defSeconds) {
        return (int) Math.round(ctx.windup(p.dbl("windup", defSeconds)) * 20);
    }

    protected int windupSec(double seconds) {
        return (int) Math.round(ctx.windup(seconds) * 20);
    }

    protected int ticks(double seconds) { return (int) Math.round(seconds * 20); }

    /** 지면 높이의 위치 (판 위치용). */
    protected Location ground(Location l) {
        Location g = l.clone();
        g.setY(fx.groundY(l));
        g.setPitch(0);
        return g;
    }

    /** 보스 발밑 지면. */
    protected Location feet() { return ground(entity.getLocation()); }

    /** 아레나 안 무작위 지점 (반경 비율 minR~maxR). */
    protected Location randomPoint(double minR, double maxR) {
        double a = rng.nextDouble() * Math.PI * 2;
        double r = minR + rng.nextDouble() * (maxR - minR);
        return center.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r);
    }

    /** 각도(도, 0 = +X, 90 = +Z 남쪽) · 반경의 아레나 지점. */
    protected Location ringPoint(double deg, double r) {
        return center.clone().add(BossMath.ax(deg) * r, 0, BossMath.az(deg) * r);
    }

    // ── 진행형 효과 등록 ─────────────────────────────────────────────────

    protected <T extends Ticking> T run(T t) {
        pending.add(t);
        return t;
    }

    protected void after(int ticks, Runnable r) { run(new Mechanics.Delay(now, ticks, r, true)); }

    /** 페이즈가 바뀌어도 취소되지 않는 지연 실행 (기믹 복구 등). */
    protected void afterPersistent(int ticks, Runnable r) { run(new Mechanics.Delay(now, ticks, r, false)); }

    protected Telegraph telegraph(Telegraph.Shape s, int ticks, Color color, String model, Runnable onFire) {
        return run(new Telegraph(fx, s, ticks, color, model, onFire));
    }

    private void cancelPhaseBound() {
        running.addAll(pending);
        pending.clear();
        for (Ticking t : new ArrayList<>(running)) {
            if (t.phaseBound()) {
                t.cancel();
                running.remove(t);
            }
        }
    }

    private void cancelAll() {
        running.addAll(pending);
        pending.clear();
        for (Ticking t : running) {
            try {
                t.cancel();
            } catch (Throwable ignored) {
                // 정리 중 오류 무시
            }
        }
        running.clear();
    }

    // ── 쫄·오브젝트·블록 ─────────────────────────────────────────────────

    /** 쫄 소환 (mobs.yml id). 인스턴스 정리 때 MobService 가 함께 지우고, 보스가 끝나도 지운다. */
    protected CustomMob spawnAdd(String mobId, Location at) {
        CustomMob m = services.mobs().spawn(mobId, at, adhoc ? null : ctx, false);
        if (m != null) {
            adds.add(m);
            BossFx.particle(Particle.HAPPY_VILLAGER, at.clone().add(0, 0.5, 0), 6, 0.3, 0.3, 0.3, 0);
        }
        return m;
    }

    protected int aliveAdds(String mobId) {
        adds.removeIf(m -> !m.isAlive());
        int n = 0;
        for (CustomMob m : adds) if (mobId == null || mobId.equals(m.id())) n++;
        return n;
    }

    protected ObjectTarget spawnObject(String kind, String name, Location at, double hp, String fxModel, float modelScale,
                                       double hitWidth, double hitHeight) {
        ObjectTarget o = new ObjectTarget(this, kind, name, at, hp, fxModel, modelScale, hitWidth, hitHeight);
        objects.add(o);
        service.registerObject(o);
        return o;
    }

    protected List<ObjectTarget> objects() {
        objects.removeIf(o -> !o.isAlive());
        return objects;
    }

    /** 블록을 놓을 수 있는가 — 미궁 월드의 실제 인스턴스 아레나에서만 (기존 지형 보호). */
    protected boolean canPlaceBlocks() {
        return !adhoc && center.getWorld() != null && services.dungeon().isLabyrinthWorld(center.getWorld());
    }

    /** 아레나 블록 설치 (원래 블록을 기억했다가 사망·종료 때 복원). canPlaceBlocks 가 false 면 무시하고 false. */
    protected boolean setBlock(Block b, BlockData data) {
        if (!canPlaceBlocks() || b.getWorld() != center.getWorld()) return false;
        if (horizontal(b.getLocation().add(0.5, 0, 0.5), center) > arenaRadius + 3) return false;
        placedBlocks.putIfAbsent(b, b.getBlockData().clone());
        b.setBlockData(data, false);
        return true;
    }

    /** 설치한 블록 하나를 원래대로 (또는 data 로) 되돌린다. */
    protected void restoreBlock(Block b) {
        BlockData orig = placedBlocks.remove(b);
        if (orig != null) b.setBlockData(orig, false);
    }

    private void restoreBlocks() {
        for (Map.Entry<Block, BlockData> e : placedBlocks.entrySet()) {
            try {
                e.getKey().setBlockData(e.getValue(), false);
            } catch (Throwable ignored) {
                // 청크 언로드 등
            }
        }
        placedBlocks.clear();
    }

    // ── 상태 ─────────────────────────────────────────────────────────────

    /** 기절 (보스 기믹 보상 — 상태이상 면역과 별개). */
    protected void stun(double seconds) {
        stunUntil = Math.max(stunUntil, now + Math.round(seconds * 20));
        cancelPhaseBound();
        endCast();
        busyUntil = 0;
        lockedYaw = null;
        stopPath();
        rig.play(BossAnim.STUN, ticks(seconds), now);
        rig.setGlow(Color.fromRGB(255, 230, 90));
        afterPersistent(ticks(seconds), () -> rig.setGlow(enraged ? Color.fromRGB(255, 40, 40) : null));
        broadcastBar("<yellow><b>" + Text.strip(def.name()) + " 기절!</b></yellow> <gray>" + Text.num(seconds) + "초");
    }

    protected void makeVulnerable(double extra, double seconds) {
        vulnerable = Math.max(vulnerable, extra);
        vulnerableUntil = Math.max(vulnerableUntil, now + Math.round(seconds * 20));
    }

    public boolean stunned() { return now < stunUntil || services.effects().isStunned(entity); }

    protected void setUntargetable(boolean on) { this.untargetable = on; }

    protected void invulnerableFor(int ticks) { invulnUntil = Math.max(invulnUntil, now + ticks); }

    protected MechanicScaling scaling() { return scaling; }

    protected int partySize() { return ctx.partySize(); }

    BossFx fx() { return fx; }

    LabBossService service() { return service; }

    Services services() { return services; }

    public Location center() { return center.clone(); }

    public double arenaRadius() { return arenaRadius; }

    // ── 메시지·표시 ──────────────────────────────────────────────────────

    protected void say(String mm) {
        if (mm == null || mm.isBlank()) return;
        for (Player p : viewerPlayers()) Text.send(p, mm);
    }

    /** 액션바 공지 (모든 참가자). */
    protected void broadcastBar(String mm) {
        for (Player p : viewerPlayers()) services.hud().actionBar(p, Text.mm(mm), 50);
    }

    protected void notify(Player p, String mm) { services.hud().actionBar(p, Text.mm(mm), 50); }

    private String barTitle() {
        String t = def.title() == null || def.title().isBlank() ? "" : " <gray>— " + def.title() + "</gray>";
        String ph = def.phases().size() > 1 ? " <dark_gray>[" + phase + "/" + def.phases().size() + "]</dark_gray>" : "";
        String state = enraged ? " <dark_red><b>광폭</b></dark_red>" : "";
        if (now < stunUntil) state += " <yellow>기절</yellow>";
        return ornament("boss_ornament_left", true) + "<b>" + def.name() + "</b>" + t + ph + state
                + ornament("boss_ornament_right", false);
    }

    /** 보스바 이름 양옆 금장식 글리프 (glyphs.yml; 없으면 빈 문자열). 좌우 대칭이라 이름이 자동 가운데. */
    private String ornament(String id, boolean left) {
        var g = services.content().glyphs().get(id);
        if (g == null) return "";
        String ch = "<!shadow><white><font:labyrinth:ui>" + g.ch() + "</font></white></!shadow>";
        String gap = "<font:labyrinth:ui>" + new String(Character.toChars(0xF800 + 2)) + "</font>";
        return left ? ch + gap : gap + ch;
    }

    private void updateBars() {
        bar.progress((float) Math.max(0, Math.min(1, hp / maxHp)));
        bar.name(Text.mm(barTitle()));
        BossBar.Color c = enraged ? BossBar.Color.RED : barColor;
        if (now < barFlashUntil) c = (now / 5) % 2 == 0 ? BossBar.Color.WHITE : c;
        bar.color(c);
        if (casting != null && castBar != null) castBar.progress((float) Math.max(0, Math.min(1, (now - castStart) / (double) castTicks)));
    }

    private void refreshPlate() {
        String s = def.name();
        if (enraged) s += " <dark_red>광폭</dark_red>";
        rig.nameplate(Text.mm(s));
    }

    private List<Player> viewerPlayers() {
        List<Player> out = new ArrayList<>();
        for (UUID u : viewers) {
            Player p = Bukkit.getPlayer(u);
            if (p != null && p.isOnline()) out.add(p);
        }
        return out;
    }

    private void refreshViewers() {
        Set<UUID> want = new LinkedHashSet<>();
        if (!adhoc) for (Player p : ctx.onlineMembers()) want.add(p.getUniqueId());
        World w = center.getWorld();
        if (w != null) {
            for (Player p : w.getPlayers()) {
                if (horizontal(p.getLocation(), center) <= arenaRadius + 16 && Math.abs(p.getLocation().getY() - floorY) < 24) want.add(p.getUniqueId());
            }
        }
        for (UUID u : new ArrayList<>(viewers)) {
            if (!want.contains(u)) {
                Player p = Bukkit.getPlayer(u);
                if (p != null) {
                    services.hud().hideBossBar(p, "boss");
                    services.hud().hideBossBar(p, "boss_cast");
                }
                viewers.remove(u);
            }
        }
        for (UUID u : want) {
            if (viewers.add(u)) {
                Player p = Bukkit.getPlayer(u);
                if (p != null) services.hud().showBossBar(p, "boss", bar);
            }
        }
    }

    private void hideBars() {
        for (Player p : viewerPlayers()) {
            services.hud().hideBossBar(p, "boss");
            services.hud().hideBossBar(p, "boss_cast");
        }
        viewers.clear();
    }

    // ── BossHandle / CustomMob / HealthPool ──────────────────────────────

    @Override public BossDef def() { return def; }
    @Override public int phase() { return phase; }
    @Override public void onDeath(Consumer<BossHandle> callback) { if (callback != null) deathCallbacks.add(callback); }
    @Override public String id() { return def.id(); }
    @Override public String displayName() { return def.name(); }
    @Override public LivingEntity entity() { return entity; }
    @Override public InstanceContext instance() { return adhoc ? null : ctx; }
    @Override public Location location() { return dead || !entity.isValid() ? lastLoc.clone() : entity.getLocation(); }

    @Override
    public double damage() {
        double m = outgoingMult();
        if (enraged) m *= 1.5 + 0.1 * enrageStacks;
        if (services.effects().has(entity, "weaken")) m *= 0.8;
        return baseDamage * m;
    }

    @Override
    public void addThreat(Player player, double amount) {
        if (player == null || dead) return;
        threat.merge(player.getUniqueId(), amount, Double::sum);
    }

    @Override
    public void taunt(Player player, double seconds) {
        if (player == null || dead) return;
        tauntId = player.getUniqueId();
        tauntUntil = now + Math.round(seconds * 20);
    }

    @Override public double health() { return hp; }
    @Override public double maxHealth() { return maxHp; }
    @Override public double defense() { return defenseValue; }

    @Override
    public double damageReduction() { return Math.max(0, Math.min(0.9, incomingReduction())); }

    @Override
    public double damageTaken() { return now < vulnerableUntil ? vulnerable : 0; }

    @Override
    public boolean invulnerable() { return dead || ended || untargetable || now < invulnUntil; }

    @Override
    public boolean isAlive() { return !dead && !ended && hp > 0; }

    @Override
    public double applyDamage(double amount, DamageContext dctx) {
        if (!isAlive() || amount <= 0) return 0;
        double dealt = Math.min(hp, amount);
        hp -= dealt;
        hurtTick = now;
        Player attacker = dctx == null ? null : dctx.attackerPlayer();
        if (attacker != null) lastDamager = attacker.getUniqueId();
        if (now % 6 == 0) BossFx.sound(entity.getLocation(), def.sounds().str("hurt"), 0.9f, (float) def.sounds().dbl("pitch", 1.0));
        if (hp <= 0.0001) {
            hp = 0;
            die(attacker);
        } else {
            checkPhase();
            if (now % 3 == 0) updateBars();
        }
        return dealt;
    }

    @Override
    public double heal(double amount) {
        if (!isAlive() || amount <= 0) return 0;
        double h = Math.min(maxHp - hp, amount);
        hp += h;
        return h;
    }

    // ── 사망·종료 ────────────────────────────────────────────────────────

    private void die(Player killer) {
        if (dead) return;
        dead = true;
        deathTick = now;
        Location at = entity.getLocation();
        lastLoc = at.clone();
        cancelAll();
        endCast();
        rig.setGlow(null);
        rig.play(BossAnim.DEATH, 40, now);
        say(def.line("death"));
        BossFx.sound(at, def.sounds().str("death"), 2f, (float) def.sounds().dbl("pitch", 1.0));
        BossFx.sound(at, Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.8f, 1.0f);
        BossFx.particle(Particle.TOTEM_OF_UNDYING, at.clone().add(0, 1.5, 0), 60, 1.2, 1.2, 1.2, 0.3);
        if (killer == null && lastDamager != null) killer = Bukkit.getPlayer(lastDamager);
        stopPath();
        entity.remove();
        cleanupWorld();
        try {
            reward(killer, at);
        } catch (Throwable t) {
            Log.error("보스 보상 오류 (" + def.id() + ")", t);
        }
        hideBars();
        for (Consumer<BossHandle> cb : deathCallbacks) {
            try {
                cb.accept(this);
            } catch (Throwable t) {
                Log.error("보스 사망 콜백 오류 (" + def.id() + ")", t);
            }
        }
    }

    private void tickDeath() {
        int dt = (int) (now - deathTick);
        if (dt % 2 == 0) rig.animate(bodyYaw, new RigMath.AnimState(now, 0, -1, 0, -1, -1, 0, 0, -1, false, 0), 2);
        if (dt % 4 == 0) BossFx.particle(Particle.LARGE_SMOKE, lastLoc.clone().add(0, 1, 0), 4, 0.6, 0.6, 0.6, 0.02);
        if (dt > 44) {
            ended = true;
            rig.remove();
            service.unregister(this);
        }
    }

    private void reward(Player killer, Location at) {
        List<Player> participants = new ArrayList<>();
        if (!adhoc) participants.addAll(ctx.onlineMembers());
        else {
            for (UUID u : threat.keySet()) {
                Player p = Bukkit.getPlayer(u);
                if (p != null && p.getWorld() == at.getWorld() && p.getLocation().distanceSquared(at) <= 64 * 64) participants.add(p);
            }
        }
        if (killer != null && !participants.contains(killer) && killer.getWorld() == at.getWorld()) participants.add(killer);
        participants.removeIf(p -> !p.isOnline());
        double xpMult = ctx.xpMultiplier();
        double goldMult = ctx.goldMultiplier();
        for (Player p : participants) {
            try {
                long xp = services.levels().reward(p, def.xp() * xpMult);
                long gold = 0;
                if (def.gold() != null && def.gold().max() > 0) {
                    gold = Math.max(0, Math.round(def.gold().roll(rng) * goldMult * (1.0 + services.stats().get(p).goldBonus())));
                    if (gold > 0) services.data().get(p).addGold(gold);
                }
                Text.send(p, "<gold><b>" + Text.strip(def.name()) + " 처치!</b></gold> <green>+" + Text.num(xp) + " XP</green>"
                        + (gold > 0 ? " <gold>+" + Text.num(gold) + " G</gold>" : ""));
                services.hud().refresh(p);
            } catch (Throwable t) {
                Log.error("보스 보상 지급 오류", t);
            }
        }
        if (def.drops() != null && !def.drops().isBlank() && !participants.isEmpty()) {
            services.loot().drop(def.drops(), participants, at.clone().add(0, 0.5, 0), adhoc ? null : ctx, "boss");
        }
        Bukkit.getPluginManager().callEvent(new MobKillEvent(this, killer, participants, true));
    }

    /** 쫄·오브젝트·효과·설치 블록 정리. */
    private void cleanupWorld() {
        try {
            onEnd();
        } catch (Throwable t) {
            Log.error("보스 종료 정리 오류 (" + def.id() + ")", t);
        }
        for (CustomMob m : adds) {
            try {
                if (m.isAlive()) m.remove();
            } catch (Throwable ignored) {
                // 이미 제거
            }
        }
        adds.clear();
        for (ObjectTarget o : new ArrayList<>(objects)) o.remove();
        objects.clear();
        restoreBlocks();
        fx.clear();
    }

    @Override
    public void end() {
        if (ended) return;
        boolean wasDead = dead;
        dead = true;
        ended = true;
        cancelAll();
        endCast();
        if (!wasDead) cleanupWorld();
        hideBars();
        if (entity.isValid()) entity.remove();
        rig.remove();
        fx.clear();
        service.unregister(this);
    }

    @Override
    public void remove() { end(); }

    /** byEntity 조회용: 히트박스 + 리그 파트. */
    List<UUID> entityIds() {
        List<UUID> out = new ArrayList<>(rig.entityIds());
        out.add(entity.getUniqueId());
        return out;
    }
}
