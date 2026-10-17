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
import org.bukkit.FluidCollisionMode;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
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
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 층 보스 공통 기반 (GDD §8): 자체 HP 풀(DamageService 경로), 페이즈(bosses.yml phases), 패턴 스케줄러(가중치·쿨다운·간격·상시),
 * 광폭화 타이머, 보스바(이름·칭호·페이즈) + 시전 바, 아레나 경계, 위협 표, 추격·기본 공격(보스별 거리 + 시야, 막힘 → 설 자리로 걷기),
 * 보스별 대응({@link #answer} — 못 닿는 자리에서 맞고 있으면 그 보스 자기 패턴으로 답함, {@link AnswerWatch}), {@link BossRig} 시전 애니메이션,
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
    /** 전투 중심 (아레나 경계·무작위 지점·관전자 판정 기준). 아레나가 옮겨 가는 보스만 {@link #relocate} 로 바꾼다. */
    protected Location center;
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
    /** 이번 전투에서 플레이어별로 준 피해 합 (칭호: 파티 공동 위업은 가장 많이 때린 한 명이 받는다). */
    private final Map<UUID, Double> damageBy = new HashMap<>();

    // 애니메이션·이동
    protected float bodyYaw;
    private Float lockedYaw;
    private long nextAttack;
    private long attackTick = -100;
    private long hurtTick = -100;
    private double moveSpeed;
    private Location lastLoc;
    private long lastRepath;

    // 막힘 감시 (bs362 → bs363): 설 자리로 곧장 걷기 → 돌아가기 → 자리 지키기
    private final ChaseGuard guard = new ChaseGuard();
    /** 이번 틱 추격에서 보스가 걸어 막힘 창이 다시 잡혔다 (대응 감시의 −10). */
    private boolean guardMoved;
    /** 플레이어별 마지막으로 보스를 때린 틱 (교전 판정). */
    private final Map<UUID, Long> lastHitAt = new HashMap<>();
    /**
     * 마지막 moveTo 가 false (길이 없거나, 이미 끝난 길과 같은 길 — Paper 는 그때도 false). 그동안은 10틱마다만 다시 찾는다
     * (길 끝에 선 채 매 틱 큰 몸 A* 를 돌리지 않게). 막힘 판정에는 안 쓴다 — 땅 보스의 막힘은 {@link ChaseGuard} 의 멈춤 감시가 본다.
     */
    private boolean moveFailed;
    private UUID sightFor;
    private long sightTick = -100;
    private boolean sightOk;
    /** 칼끝 띠 기억 — 같은 대상·같은 거리 5틱. */
    private UUID bandFor;
    private long bandTick = -100;
    private double bandMax;
    private boolean bandOk;
    /** 돌아가기: 곧장 걸어서 못 가는 설 자리까지 길찾기로 걸어간다 (그 대상에게만, 최대 5초). */
    private Location detourTo;
    private UUID detourFor;
    private long detourUntil;
    /** 걷기용 설 자리 (대상 둘레, 보스 자기 거리 안). 대상이 1칸 넘게 움직이면 다시 찾는다. */
    private Location spot;
    private long spotChecked;
    private int spotStall;
    private long nextSearch;
    private int spotFails;
    /** 걸어서 갈 설 자리가 없다 (PERCH 대응 조건). */
    private boolean noSpot;
    private UUID pocketFor;
    private double pocketX, pocketZ;
    /** 못 가는 설 자리 (좌표 키 → 풀리는 틱). */
    private final Map<Long, Long> badSpots = new HashMap<>();

    // 대응 (bs363, GDD §8.6): 못 닿는 자리에서 맞고 있으면 보스 자기 패턴으로 답한다
    private final AnswerWatch watch = new AnswerWatch();
    /** 지금 시전을 멈춘 채 시작했는가 (바쁜 틱의 대응 셈). */
    private boolean castStalled;
    /** 지금 시전을 시작한 자리 (끝날 때 1칸 넘게 옮겨졌으면 대응 셈 0). */
    private Location castFrom;
    /** 대응이 대체 패턴을 썼으면 그 키 ({@link #answerUses}). */
    private String answerUsed;
    // 기록 칸 (실서버 확인 도구가 반사로 읽는다)
    private int answersFired;
    private String lastAnswerKey;
    private String lastAnswerKind;
    private long lastAnswerAt = -1;
    private int answerArm;
    private long answerNanos;
    private long answerTicks;

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
        this.scaling = new MechanicScaling(ctx.partySize(), ctx.difficulty().id(), 1, false, ctx.rampProgress()); // 층 램프까지
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
        refreshViewers(); // 등장 대사가 참가자에게 가도록 보스바 시청자를 먼저 채운다
        say(def.line("intro"));
        rig.play(BossAnim.ROAR, 40, now);
        BossFx.sound(center, def.sounds().str("ambient"), 2f, (float) def.sounds().dbl("pitch", 1.0));
        BossFx.sound(center, Sound.ENTITY_WARDEN_ROAR, 0.6f, 0.8f);
        busyUntil = now + 40;
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
            answerStep(false);
        } else {
            if (rig.current(now) == BossAnim.STUN) rig.stop();
            if (now >= busyUntil) {
                if (casting != null) endCast();
                castEnded();
                lockedYaw = null;
                chase();
                boolean answered = answerStep(true); // 쏘면 이번 틱은 로테이션을 건너뛴다
                if (!answered && now >= busyUntil) {
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
                            castStalled = guard.stalled() || stationary();
                            castFrom = entity.getLocation();
                        }
                    }
                }
            } else {
                stopPath();
                answerStep(false);
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

    /**
     * 기본 공격 거리 (GDD §8.6): 보스 중심 ↔ 플레이어 발 수평 — 보스마다 다르다 (0.3.6.1 그대로). 트인 곳의 거리 재기·피하기가
     * 보스마다 달라지는 까닭이다. 칼끝 띠({@link #band})는 판단에만 쓰고 이 거리를 늘리지 않는다.
     */
    protected final double reach() { return BossReach.reach(def.scale()); }

    private void chase() {
        Player t = target();
        if (t == null) {
            stopPath();
            guard.update(new ChaseGuard.Input(null, false, false, 0, false, false, 0, 0, 0, 0, false));
            guardMoved = false;
            return;
        }
        Location bl = entity.getLocation(), tl = t.getLocation();
        double dist = horizontal(bl, tl);
        boolean sees = sight(t, false);
        boolean inReach = canHit(t, 0, false);
        if (detourTo != null && (!pathing || inReach || now >= detourUntil || detourTo.getWorld() != bl.getWorld()
                || !t.getUniqueId().equals(detourFor) || horizontal(bl, detourTo) < 0.8)) {
            // 돌아가기가 끝났는데 닿지도 않고 설 자리에서 1.5칸 넘게 남았다 → 못 가는 자리
            if (!inReach && pathing && t.getUniqueId().equals(detourFor) && detourTo.getWorld() == bl.getWorld()
                    && horizontal(bl, detourTo) > 1.5) {
                badSpot(detourTo);
            }
            detourTo = null;
        }
        // 길 없음(거리 무관 곧장 다가가기)은 떠다니는 보스만 — 땅 보스는 길 끝에 서면 멈춤 감시가 잡는다.
        // (moveTo 의 false 는 "이미 끝난 길과 같음" 도 뜻해서, 그걸로 켜면 카이팅 중에도 길찾기 없이 곧장 걸어 장애물에 걸렸다)
        ChaseGuard.Output o = guard.update(new ChaseGuard.Input(t.getUniqueId(), pathing, inReach, dist, def.flying(), sees,
                bl.getX(), bl.getZ(), tl.getX(), tl.getZ(), detourTo != null));
        guardMoved = o.moved();
        long t0 = System.nanoTime();
        walkSpot(t, inReach, o);
        answerNanos += System.nanoTime() - t0; // 틱 비용 (감시 + 띠 + 설 자리 합)
        ChaseGuard.Move move = detourTo != null ? ChaseGuard.Move.PATH : o.move();
        // 설 자리로 곧장 걷는데 다시 0.5초 멈춤 → 길찾기로 돌아가기 (길이 없거나 어긋나면 그 자리는 못 가는 자리)
        if (move == ChaseGuard.Move.STEER && spot != null && o.stalled()) {
            if (++spotStall >= ChaseGuard.WINDOW) {
                spotStall = 0;
                Location s = spot;
                if (detour(t, s)) move = ChaseGuard.Move.PATH;
                else badSpot(s);
            }
        } else {
            spotStall = 0;
        }
        switch (move) {
            case HOLD -> {
                stopPath();
                if (guard.latched()) {
                    // 자리 지키기: 곧장 걷던 관성으로 미끄러져 나가지 않게
                    Vector v = entity.getVelocity();
                    if (v.getX() * v.getX() + v.getZ() * v.getZ() > 1e-6) entity.setVelocity(new Vector(0, def.flying() ? 0 : v.getY(), 0));
                }
            }
            case STEER -> {
                stopPath();
                steer(t, spot);
            }
            case PATH -> {
                if (def.flying()) {
                    // 떠다니는 보스는 땅 길찾기가 길을 못 만든다 (중력 없음) — 보일 때만 STEER 로 다가간다
                    stopPath();
                    if (entity.getVelocity().lengthSquared() > 1e-4) entity.setVelocity(new Vector()); // 다가가던 관성 멈춤
                } else if (detourTo != null) {
                    if (now - lastRepath >= 10 || (!moveFailed && !entity.getPathfinder().hasPath())) {
                        moveFailed = !entity.getPathfinder().moveTo(detourTo, 1.0);
                        if (moveFailed) {
                            badSpot(detourTo);
                            detourTo = null;
                        }
                        lastRepath = now;
                    }
                } else if (dist > reach() * 0.85 || !inReach) {
                    if (now - lastRepath >= 10 || (!moveFailed && !entity.getPathfinder().hasPath())) {
                        moveFailed = !entity.getPathfinder().moveTo(tl, 1.0);
                        lastRepath = now;
                    }
                } else {
                    stopPath();
                }
            }
        }
        if (now >= nextAttack && canHit(t, 0, true)) {
            nextAttack = now + 40;
            attackTick = now;
            final UUID id = t.getUniqueId();
            pending.add(new Mechanics.Delay(now, 3, () -> {
                Player p = Bukkit.getPlayer(id);
                if (p != null && validPlayer(p) && canHit(p, BossReach.CONFIRM_SLACK, true)) {
                    services.damage().deal(DamageContext.raw(entity, p, damage(), DamageType.MELEE).source("basic_attack"));
                    BossFx.sound(p.getLocation(), Sound.ENTITY_PLAYER_ATTACK_STRONG, 0.8f, 0.6f);
                    watch.landed(id);
                }
            }, true));
        }
    }

    /** 이 플레이어의 손 닿음 (칼끝 띠 판단용). */
    protected static double playerReach(Player p) {
        AttributeInstance a = p.getAttribute(Attribute.ENTITY_INTERACTION_RANGE);
        return BossReach.playerReach(a == null ? Double.NaN : a.getValue());
    }

    private static BossReach.Box box(BoundingBox bb) {
        return new BossReach.Box(bb.getMinX(), bb.getMinY(), bb.getMinZ(), bb.getMaxX(), bb.getMaxY(), bb.getMaxZ());
    }

    private static double halfWidth(BoundingBox bb) { return Math.max(bb.getWidthX(), bb.getWidthZ()) / 2; }

    /**
     * 기본 공격이 닿는가 (GDD §8.6): 보스 자기 거리({@link #reach()} + slack, 발 높이 차 3.5 미만) + 시야(플레이어 눈과 히트박스
     * 사이에 막는 블록 없음 — 벽 너머 공격 없음). fresh = false 면 시야를 같은 대상 5틱 기억.
     */
    protected boolean canHit(Player p, double slack, boolean fresh) {
        Location bl = entity.getLocation(), pl = p.getLocation();
        return BossReach.legacy(horizontal(bl, pl), pl.getY() - bl.getY(), reach() + slack) && sight(p, fresh);
    }

    /**
     * 칼끝 띠 (판단 전용 — 피해에는 안 씀): 플레이어 눈 → 보스 히트박스 ≤ 플레이어 손 닿음 + 0.5, 그 거리 안에 보이는 점이 있음.
     * "플레이어 칼은 닿는데 보스 기본 공격은 안 닿는 자리" 를 알아보는 잣대. 같은 대상 5틱 기억.
     */
    protected boolean band(Player t) {
        Location bl = entity.getLocation(), tl = t.getLocation();
        if (tl.getWorld() != bl.getWorld()) return false;
        BoundingBox bb = entity.getBoundingBox();
        double pr = playerReach(t), max = pr + AnswerWatch.BAND_SLACK;
        if (horizontal(bl, tl) - halfWidth(bb) * 1.42 > max) return false; // 광선 없이 빠른 거절
        Location eye = t.getEyeLocation();
        BossReach.Box b = box(bb);
        if (!BossReach.inBand(BossReach.pointToBox(eye.getX(), eye.getY(), eye.getZ(), b), pr, AnswerWatch.BAND_SLACK)) return false;
        if (t.getUniqueId().equals(bandFor) && now - bandTick < 5 && bandMax == max) return bandOk;
        World w = entity.getWorld();
        boolean ok = BossReach.sees(eye.getX(), eye.getY(), eye.getZ(), b, (ax, ay, az, bx, by, bz) -> rayClear(w, ax, ay, az, bx, by, bz), max);
        bandFor = t.getUniqueId();
        bandTick = now;
        bandMax = max;
        bandOk = ok;
        return ok;
    }

    /** 플레이어 눈 ↔ 보스 히트박스 사이에 막는 블록이 없는가 (fresh = false 면 같은 대상 5틱 기억). */
    protected boolean sight(Player p, boolean fresh) {
        if (!fresh && p.getUniqueId().equals(sightFor) && now - sightTick < 5) return sightOk;
        World w = entity.getWorld();
        Location eye = p.getEyeLocation();
        boolean ok = p.getWorld() == w && BossReach.sees(eye.getX(), eye.getY(), eye.getZ(), box(entity.getBoundingBox()),
                (ax, ay, az, bx, by, bz) -> rayClear(w, ax, ay, az, bx, by, bz));
        sightFor = p.getUniqueId();
        sightTick = now;
        sightOk = ok;
        return ok;
    }

    private static boolean rayClear(World w, double ax, double ay, double az, double bx, double by, double bz) {
        Vector d = new Vector(bx - ax, by - ay, bz - az);
        double len = d.length();
        if (len < BossReach.RAY_END_SLACK * 2) return true;
        RayTraceResult r = w.rayTraceBlocks(new Location(w, ax, ay, az), d.multiply(1 / len), len - BossReach.RAY_END_SLACK,
                FluidCollisionMode.NEVER, true);
        return r == null;
    }

    /**
     * 곧장 걷기 (길찾기가 길을 못 내는 1칸 틈·벽 앞 · 떠다니는 보스). aim = 설 자리(있으면, 0.15칸까지) 아니면 대상(몸 반폭 + 0.35칸 앞까지).
     * 벽은 바닐라 충돌이 막는다.
     */
    private void steer(Player t, Location aim) {
        Location bl = entity.getLocation();
        boolean toSpot = aim != null && aim.getWorld() == bl.getWorld();
        Location to = toSpot ? aim : t.getLocation();
        double dx = to.getX() - bl.getX(), dz = to.getZ() - bl.getZ();
        double len = Math.hypot(dx, dz);
        double hw = halfWidth(entity.getBoundingBox());
        double keep = toSpot ? 0.15 : hw + 0.35; // 플레이어를 밀고 들어가지 않는다
        double vy = def.flying() ? 0 : entity.getVelocity().getY();
        AttributeInstance ms = entity.getAttribute(Attribute.MOVEMENT_SPEED);
        double v = Math.min(BossReach.walkSpeed(ms == null ? 0.22 : ms.getValue()), len - keep);
        if (len <= keep || v <= 0.005) {
            entity.setVelocity(new Vector(0, vy, 0));
            return;
        }
        double vx = dx / len * v, vz = dz / len * v;
        if (!safeAhead(bl, bl.getX() + dx / len * 0.6, bl.getZ() + dz / len * 0.6, hw)) {
            entity.setVelocity(new Vector(0, vy, 0));
            return;
        }
        entity.setVelocity(new Vector(vx, vy, vz));
    }

    /** 걸어 들어가도 되는 곳인가 (용암·불·가루눈 없음, 땅 몹은 발밑 가운데가 1칸 안에서 받쳐짐, 아레나 안). */
    private boolean safeAhead(Location from, double x, double z, double hw) {
        if (Math.hypot(x - center.getX(), z - center.getZ()) > arenaRadius + 1) return false;
        World w = from.getWorld();
        double y = from.getY();
        double in = Math.max(0, hw - 0.15);
        double[][] pts = {{0, 0}, {in, in}, {-in, in}, {in, -in}, {-in, -in}};
        for (double[] q : pts) {
            int bx = (int) Math.floor(x + q[0]), bz = (int) Math.floor(z + q[1]);
            int fy = (int) Math.floor(y - 0.01);
            if (hazard(w.getBlockAt(bx, fy, bz).getType()) || hazard(w.getBlockAt(bx, fy + 1, bz).getType())) return false;
        }
        if (def.flying()) return true;
        int bx = (int) Math.floor(x), bz = (int) Math.floor(z), fy = (int) Math.floor(y - 0.01);
        return hasCollision(w.getBlockAt(bx, fy, bz)) || hasCollision(w.getBlockAt(bx, fy - 1, bz));
    }

    private static boolean hazard(Material m) {
        return m == Material.LAVA || m == Material.FIRE || m == Material.SOUL_FIRE || m == Material.POWDER_SNOW;
    }

    private static boolean hasCollision(Block b) {
        return !b.getCollisionShape().getBoundingBoxes().isEmpty();
    }

    /** 블록 충돌 상자의 윗면 (블록 안 0~1.5, 없으면 NaN). */
    private static double collisionTop(Block b) {
        double top = Double.NaN;
        for (BoundingBox s : b.getCollisionShape().getBoundingBoxes()) top = Double.isNaN(top) ? s.getMaxY() : Math.max(top, s.getMaxY());
        return top;
    }

    // ── 설 자리 (bs363) ──────────────────────────────────────────────────

    /**
     * 걷기용 설 자리 관리: 대상이 1칸 넘게 움직이면(또는 대상이 바뀌면) 처음부터. 멈췄을 때만, 10틱에 한 번까지 찾는다.
     * 고른 자리는 20틱마다 다시 확인한다 (블록이 바뀌었거나 대상 눈에서 안 보이게 됐으면 버림).
     */
    private void walkSpot(Player t, boolean inReach, ChaseGuard.Output o) {
        Location tl = t.getLocation();
        UUID id = t.getUniqueId();
        if (!id.equals(pocketFor) || Math.hypot(tl.getX() - pocketX, tl.getZ() - pocketZ) > 1.0) {
            pocketFor = id;
            pocketX = tl.getX();
            pocketZ = tl.getZ();
            spot = null;
            noSpot = false;
            spotFails = 0;
            nextSearch = now;
        }
        if (inReach || !pathing) return;
        if (spot != null && now - spotChecked >= 20) {
            spotChecked = now;
            if (!spotStillGood(t, spot)) spot = null;
        }
        if (spot == null && o.stalled() && now >= nextSearch) {
            nextSearch = now + 10;
            spot = standSpot(t, null, BossReach.Order.BOSS);
            if (spot != null) {
                spotChecked = now;
                noSpot = false;
            } else {
                noSpot = true;
                nextSearch = now + 20;
            }
        }
    }

    /** 못 가는 설 자리로 60틱 적어 두고 다음 후보로. 이 대상 자리에서 두 번 실패하면 "갈 곳 없음" (200틱 동안 더 안 찾음). */
    private void badSpot(Location s) {
        if (s != null) badSpots.put(spotKey(s.getX(), s.getZ()), now + 60);
        badSpots.values().removeIf(until -> until <= now);
        spot = null;
        if (++spotFails >= 2) {
            spotFails = 0;
            noSpot = true;
            nextSearch = now + 200;
        }
    }

    private static long spotKey(double x, double z) {
        return ((long) Math.round(x * 4) << 32) ^ (Math.round(z * 4) & 0xffffffffL);
    }

    /**
     * 대상 옆 설 자리 (GDD §8.6): 대상 둘레 고리에서 대상 발까지 수평 ≤ 보스 자기 거리 − 0.3, 대상 몸 위 아님, 발 높이 차 3.2 미만,
     * 아레나 안, 용암·불 아님, 몸이 들어가고(블록과 안 겹침) 땅 보스는 발판이 받쳐짐, 대상 눈에서 그 자리의 몸이 보임 — 서면 기본 공격이 닿는다.
     * 순서: BOSS = 지금 보스 자리에서 가까운 순 (걷기, 못 가는 자리 건너뜀), NEAR = near 에서 가까운 순 (착지·순간이동).
     * 시야 광선은 통과 후보 앞 4곳까지만. 떠다니는 보스는 높이 = 지금 보스 높이.
     * @return 설 자리 (없으면 null)
     */
    protected Location standSpot(Player t, Location near, BossReach.Order order) {
        World w = entity.getWorld();
        Location tl = t.getLocation(), bl = entity.getLocation();
        if (tl.getWorld() != w) return null;
        BoundingBox bb = entity.getBoundingBox();
        double hw = halfWidth(bb), h = bb.getHeight();
        boolean walk = order == BossReach.Order.BOSS;
        Location ref = !walk && near != null && near.getWorld() == w ? near : bl;
        int rays = 0;
        for (double[] c : BossReach.standOrder(tl.getX(), tl.getZ(), hw, reach(), center.getX(), center.getZ(), arenaRadius,
                ref.getX(), ref.getZ())) {
            if (walk) {
                Long until = badSpots.get(spotKey(c[0], c[1]));
                if (until != null && now < until) continue;
            }
            double y = def.flying() ? bl.getY() : landY(w, c[0], tl.getY(), c[1]);
            if (!placeOk(w, tl, c[0], y, c[1], hw, h)) continue;
            if (rays >= 4) return null;
            rays++;
            if (seenFrom(t, c[0], y, c[1], hw, h)) return new Location(w, c[0], y, c[1], bl.getYaw(), 0);
        }
        return null;
    }

    private boolean placeOk(World w, Location tl, double x, double y, double z, double hw, double h) {
        if (Double.isNaN(y) || Math.abs(y - tl.getY()) >= 3.2) return false;
        if (y < floorY - 1.5 || y + h > floorY + arenaHeight - 0.5) return false;
        if (!fits(w, BossReach.Box.of(x, y, z, hw, h))) return false;
        return def.flying() || standable(w, x, y, z, hw);
    }

    private boolean seenFrom(Player t, double x, double y, double z, double hw, double h) {
        World w = entity.getWorld();
        Location eye = t.getEyeLocation();
        return BossReach.sees(eye.getX(), eye.getY(), eye.getZ(), BossReach.Box.of(x, y, z, hw, h),
                (ax, ay, az, bx, by, bz) -> rayClear(w, ax, ay, az, bx, by, bz));
    }

    private boolean spotStillGood(Player t, Location s) {
        World w = entity.getWorld();
        if (s.getWorld() != w || t.getWorld() != w) return false;
        BoundingBox bb = entity.getBoundingBox();
        double hw = halfWidth(bb), h = bb.getHeight();
        if (horizontal(s, t.getLocation()) > reach() - BossReach.STAND_MARGIN + 1e-6) return false;
        return placeOk(w, t.getLocation(), s.getX(), s.getY(), s.getZ(), hw, h) && seenFrom(t, s.getX(), s.getY(), s.getZ(), hw, h);
    }

    /**
     * 돌아가기: 설 자리까지 길찾기 길의 끝이 그 자리 2.5칸 안에 닿으면 걸어간다 (최대 5초, 대상이 바뀌면 그만).
     * 큰 몸 길찾기는 발판 모서리 기준이라 끝이 1~2칸 어긋날 수 있어 2.5칸까지 받는다. 지금 자리보다 가까워지지 않으면 안 간다.
     * @return 걷기 시작했는가 (false = 못 가는 자리)
     */
    private boolean detour(Player t, Location to) {
        if (to == null || !pathing || def.flying() || to.getWorld() != entity.getWorld()) return false;
        Location here = entity.getLocation();
        var path = entity.getPathfinder().findPath(to);
        if (path == null || path.getFinalPoint() == null) return false;
        Location fin = path.getFinalPoint();
        double miss = Math.hypot(fin.getX() - to.getX(), fin.getZ() - to.getZ());
        if (miss > 2.5 || miss + 0.5 >= horizontal(here, to)) return false;
        detourTo = to;
        detourFor = t.getUniqueId(); // 대상이 바뀌면 그만 (새 대상을 두고 옛 대상 쪽으로 걷지 않게)
        detourUntil = now + 100;
        moveFailed = !entity.getPathfinder().moveTo(path, 1.0);
        lastRepath = now;
        return true;
    }

    /** 발 높이: refY 1칸 위에서 아래로 10칸 안 첫 충돌 윗면. 용암·불을 먼저 만나면 NaN. */
    protected static double landY(World w, double x, double refY, double z) {
        int bx = (int) Math.floor(x), bz = (int) Math.floor(z);
        int top = (int) Math.floor(refY + 1.01);
        for (int yy = top; yy >= top - 10; yy--) {
            Block b = w.getBlockAt(bx, yy, bz);
            if (hazard(b.getType())) return Double.NaN;
            double hi = collisionTop(b);
            if (!Double.isNaN(hi)) return yy + hi;
        }
        return Double.NaN;
    }

    /** 몸 상자가 블록과 겹치지 않는가 (겉면 0.03 안쪽). */
    protected static boolean fits(World w, BossReach.Box b) {
        return !w.hasCollisionsIn(new BoundingBox(b.minX() + 0.03, b.minY() + 0.03, b.minZ() + 0.03, b.maxX() - 0.03, b.maxY() - 0.03,
                b.maxZ() - 0.03));
    }

    /** 몸 발판 가운데·네 모서리가 모두 받쳐지고(1칸 아래까지) 용암·불이 없다. */
    protected static boolean standable(World w, double x, double y, double z, double hw) {
        double in = Math.max(0, hw - 0.15);
        double[][] pts = {{0, 0}, {in, in}, {-in, in}, {in, -in}, {-in, -in}};
        int fy = (int) Math.floor(y - 0.01);
        for (double[] q : pts) {
            int bx = (int) Math.floor(x + q[0]), bz = (int) Math.floor(z + q[1]);
            Block under = w.getBlockAt(bx, fy, bz);
            if (hazard(under.getType()) || hazard(w.getBlockAt(bx, fy + 1, bz).getType())) return false;
            if (!hasCollision(under) && !hasCollision(w.getBlockAt(bx, fy - 1, bz))) return false;
        }
        return true;
    }

    /** 이 자리에 보스 몸이 설 수 있는가 (블록과 안 겹침 + 땅 보스는 받쳐짐). */
    protected boolean bodyFits(Location at) {
        if (at == null || at.getWorld() != entity.getWorld()) return false;
        BoundingBox bb = entity.getBoundingBox();
        double hw = halfWidth(bb), h = bb.getHeight();
        World w = at.getWorld();
        if (!fits(w, BossReach.Box.of(at.getX(), at.getY(), at.getZ(), hw, h))) return false;
        return def.flying() || standable(w, at.getX(), at.getY(), at.getZ(), hw);
    }

    /** around 둘레 maxR 칸 안에서 몸이 설 수 있는 가장 가까운 자리 (없으면 null). */
    protected Location nearestFit(Location around, double maxR) {
        if (around == null || around.getWorld() != entity.getWorld()) return null;
        World w = around.getWorld();
        BoundingBox bb = entity.getBoundingBox();
        double hw = halfWidth(bb), h = bb.getHeight();
        for (double[] c : BossReach.landingRing(around.getX(), around.getZ())) {
            if (Math.hypot(c[0] - around.getX(), c[1] - around.getZ()) > maxR + 1e-9) break;
            double y = def.flying() ? around.getY() : landY(w, c[0], around.getY(), c[1]);
            if (Double.isNaN(y) || !fits(w, BossReach.Box.of(c[0], y, c[1], hw, h))) continue;
            if (!def.flying() && !standable(w, c[0], y, c[1], hw)) continue;
            return new Location(w, c[0], y, c[1], around.getYaw(), around.getPitch());
        }
        return null;
    }

    /**
     * 끼임 빼기: 몸 상자가 블록과 겹쳐 있으면 2칸 안에서 몸이 들어가고 받쳐지는 가장 가까운 곳으로 옮긴다 (돌진 끝·착지 뒤).
     * @return 옮겼는가
     */
    protected boolean unstick() {
        if (!entity.isValid()) return false;
        World w = entity.getWorld();
        if (fits(w, box(entity.getBoundingBox()))) return false;
        Location l = entity.getLocation();
        Location to = nearestFit(l, 2.0);
        if (to == null) return false;
        to.setYaw(l.getYaw());
        to.setPitch(l.getPitch());
        entity.teleport(to);
        return true;
    }

    // ── 대응 (bs363, GDD §8.6) ───────────────────────────────────────────

    /**
     * 대응 한 번의 정보.
     * @param target 대상 (위협 1위·도발)
     * @param kind   종류 (칼끝 띠 · 높은 곳 · 걷지 않는 보스)
     * @param pocket 무장했을 때 대상 발 자리
     * @param spot   걷기용 설 자리 (없으면 null)
     * @param gap    보스 중심 ↔ 대상 수평 거리
     * @param dy     대상 발 − 보스 발 높이
     */
    public record Answer(Player target, AnswerWatch.Kind kind, Location pocket, Location spot, double gap, double dy) {}

    /** 대응 정의 = bosses.yml {@code patterns.answer} {use, cooldown, min_gap, shares, name, …}. 없으면 대응 없음(움직임만). */
    protected final Params answerDef() { return def.pattern("answer"); }

    /** 걷지 않는 보스 (기본: bosses.yml speed ≤ 0 → 10층). */
    protected boolean stationary() { return def.speed() <= 0; }

    /** 지금 이 대상에게 대응할 수 있는가 (공중·껍질·색인·분신·추격 단계·밸브 등). 기본 true. */
    protected boolean canAnswer(Player t) { return true; }

    /**
     * 대응 시작 — 그 보스 자기 패턴(경고·피해 그대로)으로 "못 닿는 자리" 에 답한다.
     * @return &gt;0 묶이는 틱(보통 cast 반환값) · 0 = 지금 못 함(10틱 뒤 다시) · −1 = 이 보스는 대응 없음
     */
    protected int answer(Answer a) { return -1; }

    /** 대응이 대체 패턴을 썼으면 그 키를 알린다 (그 패턴의 쿨이 다시 돈다, 기본 = answer.use). */
    protected final void answerUses(String key) { answerUsed = key; }

    /** 시전이 끝났다: 패턴이 몸을 1칸 넘게 옮겼으면 대응 셈 0 (돌진·낙하·순간이동 뒤 새 자리에서 다시 잰다). */
    private void castEnded() {
        if (castFrom == null) return;
        if (castFrom.getWorld() == entity.getWorld() && horizontal(castFrom, entity.getLocation()) > 1.0) watch.bodyMoved();
        castFrom = null;
    }

    /** 대응 감시 한 틱 (바쁠 때·기절 중에도 셈만). @return 이번 틱에 대응을 시작했는가 */
    private boolean answerStep(boolean free) {
        if (watch.disabled()) return false;
        Params ad = answerDef();
        if (ad.isEmpty()) {
            watch.none();
            return false;
        }
        long t0 = System.nanoTime();
        try {
            return answerTick(free, ad);
        } catch (Throwable ex) {
            Log.error("보스 대응 감시 오류 (" + def.id() + ")", ex);
            watch.none();
            return false;
        } finally {
            answerNanos += System.nanoTime() - t0;
            answerTicks++;
        }
    }

    private boolean answerTick(boolean free, Params ad) {
        Player t = target();
        if (t == null) {
            watch.update(new AnswerWatch.Input(null, 0, 0, 0, free, stationary(), false, false, false, Long.MAX_VALUE / 4,
                    Long.MAX_VALUE / 4, false, false, false, false, false, false, now));
            answerArm = 0;
            return false;
        }
        Location tl = t.getLocation();
        long never = Long.MIN_VALUE / 4;
        long tHit = now - lastHitAt.getOrDefault(t.getUniqueId(), never);
        long last = never;
        for (long v : lastHitAt.values()) last = Math.max(last, v);
        long anyHit = now - last;
        boolean reached = canHit(t, 0, false);
        boolean engagedish = !reached && (tHit <= AnswerWatch.ENGAGE_TICKS || anyHit <= AnswerWatch.ENGAGE_TICKS);
        boolean b = engagedish && band(t);
        boolean sees = sight(t, false);
        boolean allowed = engagedish && !stunned() && !invulnerable() && canAnswerSafe(t);
        String use = ad.str("use");
        double mult = scheduler.cooldownMult();
        long lastUse = scheduler.lastUse(use);
        for (String k : ad.strings("shares")) lastUse = Math.max(lastUse, scheduler.lastUse(k));
        boolean gapOk = now - lastUse >= Math.round(ad.dbl("min_gap", 0) * 20 * mult);
        AnswerWatch.Kind k = watch.update(new AnswerWatch.Input(t.getUniqueId(), tl.getX(), tl.getY(), tl.getZ(), free, stationary(),
                reached, b, sees, tHit, anyHit, guard.stalled(), castStalled, free && guardMoved, noSpot, allowed, gapOk, now));
        answerArm = Math.max(watch.arm(), Math.max(watch.still(), watch.perch()));
        if (k == null || !free) return false;
        return fireAnswer(t, k, ad, use, mult);
    }

    private boolean canAnswerSafe(Player t) {
        try {
            return canAnswer(t);
        } catch (Throwable ex) {
            Log.error("보스 대응 조건 오류 (" + def.id() + ")", ex);
            return false;
        }
    }

    private boolean fireAnswer(Player t, AnswerWatch.Kind k, Params ad, String use, double mult) {
        Location bl = entity.getLocation(), tl = t.getLocation();
        Answer a = new Answer(t, k, tl.clone(), spot == null ? null : spot.clone(), horizontal(bl, tl), tl.getY() - bl.getY());
        double cd = ad.dbl("cooldown", 10) * 20 * mult;
        int arm = answerArm;
        answerUsed = null;
        int busy;
        try {
            busy = answer(a);
        } catch (Throwable ex) {
            Log.error("보스 대응 시작 오류 (" + def.id() + ")", ex);
            busy = -1;
        }
        if (busy < 0) {
            watch.none();
            return false;
        }
        if (busy == 0) {
            watch.zero(now, cd);
            return false;
        }
        // 로테이션과 같은 길: 묶임 → 그 패턴 쿨 다시 돎 → 대응 쿨 → 기본 공격 1초 쉼
        busyUntil = now + busy;
        scheduler.busyUntil(busyUntil);
        String used = answerUsed != null ? answerUsed : use;
        scheduler.markUsed(used, now);
        long gap = Math.round(ad.dbl("min_gap", 0) * 20 * mult);
        for (String s : ad.strings("shares")) scheduler.delay(s, now + gap);
        watch.fired(now, cd);
        guard.reset();
        nextAttack = Math.max(nextAttack, now + busy + 20);
        castFrom = entity.getLocation();
        castStalled = stationary();
        detourTo = null;
        spot = null;
        spotStall = 0;
        answersFired++;
        lastAnswerKey = used;
        lastAnswerKind = k.name();
        lastAnswerAt = now;
        Log.debug("answer " + def.id() + " → " + t.getName() + " " + k + " arm=" + arm + " key=" + used);
        return true;
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
        lastHitAt.values().removeIf(t -> now - t > AnswerWatch.ENGAGE_TICKS * 4L);
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
        if (!blockAllowed(b)) return false;
        placedBlocks.putIfAbsent(b, b.getBlockData().clone());
        b.setBlockData(data, false);
        return true;
    }

    /** 이 블록을 보스가 바꿔도 되는가 (기본: 아레나 원 + 3칸). 추격 복도처럼 원 밖까지 쓰는 보스가 넓힌다. */
    protected boolean blockAllowed(Block b) {
        return horizontal(b.getLocation().add(0.5, 0, 0.5), center) <= arenaRadius + 3;
    }

    /**
     * 전투 중심을 옮기고 보스를 그 자리로 순간이동 (10층 심장실 → 심연의 가장자리처럼 아레나가 바뀌는 보스).
     * 바닥 높이({@link #floorY})는 그대로다 — 같은 층 같은 높이의 다른 단으로만 옮긴다.
     */
    protected void relocate(Location to) {
        if (to == null || to.getWorld() != center.getWorld()) return;
        center = to.clone();
        center.setY(floorY);
        center.setYaw(0);
        center.setPitch(0);
        stopPath();
        Location at = center.clone();
        at.setYaw(bodyYaw);
        entity.teleport(at);
        lastLoc = at.clone();
        rig.follow(at);
        refreshViewers();
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

    /** 보스바 기본 색 바꾸기 (7층 극성 얼굴처럼 전투 중 색이 바뀌는 기믹). 광폭화·깜빡임은 그대로 위에 덮인다. */
    protected void setBarColor(BossBar.Color color) {
        if (color == null || color == barColor) return;
        barColor = color;
        updateBars();
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
    public Map<UUID, Double> damageByPlayer() { return Map.copyOf(damageBy); }

    @Override
    public UUID lastHitPlayer() { return lastDamager; }

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
        if (attacker != null) {
            lastDamager = attacker.getUniqueId();
            damageBy.merge(lastDamager, dealt, Double::sum);
            lastHitAt.put(lastDamager, now);
        }
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
