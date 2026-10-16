package kr.labyrinth.combat;

import io.papermc.paper.event.player.PlayerArmSwingEvent;
import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
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
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockDamageAbortEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.ChunkUnloadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.MainHand;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 시전 무기 마법탄 (0.3.6.1) — 지팡이·홀 같은 시전 무기({@link WeaponAttack.Style#CASTER})의 좌클릭 = 조준선으로 날아가는 마법탄.
 * <ul>
 *   <li>좌클릭 감지 = 주손 {@link PlayerArmSwingEvent} (Paper 26.3 의 좌클릭 패킷 하나에 한 번 — 버리기·우클릭·창 열기는 부르지 않는다).
 *       규칙은 {@link CasterBoltRules#punch}. 몹을 직접 클릭하면 {@link AttackClock} 이 그 공격을 막고 같은 시계로 그 몹에게 바로 넣는다
 *       ({@link #fire} 의 strike). 블록을 누르고 있는 동안 틱마다 오는 punch 는 새 클릭이 아니다 ({@link CasterBoltRules.Press}).
 *       캐기: 미궁 밖 서바이벌·크리에이티브에서 손 닿는 블록을 보고 눌렀고 조준선에 적이 없을 때만 ({@link CasterBoltRules#digs}).</li>
 *   <li>공격 시계: 근접·활과 같은 {@link AttackTiming} (무기 간격 ÷ 민첩 공속, 하한 0.25초). 너무 빨리 누르면 아무것도 안 나간다
 *       (간격 끝 0.35초 안이면 한 번 기억했다가 그때 바라보는 쪽으로). MP 는 들지 않는다.</li>
 *   <li>피해 = 예전 휘두르기와 같은 한 방 (무기 W × 지능 배율 × 마법 피해, 치명타 그대로) — {@code DamageContext.basic(…, MAGIC)}
 *       + 쏜 순간의 W·피해 종류. 플레이어에게는 × {@code pvp_damage}. 점프 치명(떨어지며 친 근접 ×1.2)은 없다 (화살처럼).
 *       날아가는 사이 손의 무기를 바꾸면(칸·무기가 달라지면) 그 마법탄은 사라진다 — 다른 무기의 고유 효과가 섞이지 않게.</li>
 *   <li>비행: 엔티티를 만들지 않는다. 틱마다 한 걸음(기본 2.5칸, 16칸까지) — 블록 광선({@code rayTraceBlocks}, 통과 가능한 풀·횃불은 지나감)
 *       + 그 걸음 상자 안 살아 있는 적의 히트박스({@link BoltPath#firstHit}). 처음 닿는 적 하나만, 벽 뒤는 못 맞힌다 — 굵기만큼 키운
 *       테두리에만 닿았으면 그 자리에서 몸까지 막는 블록이 없을 때만 (철창·유리판·닫힌 문 바로 뒤는 안 맞음). 블록은 바꾸지 않는다.</li>
 *   <li>보이는 것: 맞는 판정은 눈의 조준선이지만 꼬리는 지팡이 손에서 나와 6칸에 걸쳐 조준선으로 모인다 (조준선 위에만 그리면 쏜 사람 화면에서는
 *       조준점 한 곳에 겹쳐 안 보인다). 무기 색 DUST + 어두운 방에서도 밝은 TRAIL 알갱이, 끝에서 터짐. 멀리 맞히면 쏜 사람에게만 작은 '딩'.</li>
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
    /** 꼬리 입자 간격 (블록). */
    static final double TRAIL_STEP = 0.45;
    /** 꼬리가 시작하는 거리 (조준선 위, 블록) — 그 앞은 지팡이 끝 반짝임만 (쏜 사람 시야를 가리지 않게). */
    static final double TRAIL_START = 0.9;
    /** 지팡이 끝 반짝임 자리 (조준선 위, 블록). */
    static final double TIP = 0.6;
    /** 지팡이 손 (눈 기준 오른쪽·아래, 블록) — 꼬리는 여기서 나와 {@link #CONVERGE} 칸에 걸쳐 조준선으로 모인다. */
    static final double HAND_RIGHT = 0.35, HAND_DOWN = 0.3, CONVERGE = 6.0;
    /** 이보다 먼 적을 맞히면 쏜 사람에게만 작은 '딩' (맞는 자리 소리는 12~16칸이면 거의 안 들린다). */
    static final double HIT_TICK_MIN = 6.0;
    /** 시험·진단용 (서버를 -Dlabyrinth.debug.bolts=true 로 켜면 맞을 때마다 로그 한 줄). 설정 파일 키는 아님. */
    static final boolean DEBUG = Boolean.getBoolean("labyrinth.debug.bolts");

    private final Services services;
    private final DamageService damage;
    private AttackClock clock;
    private volatile CasterBoltConfig cfg = CasterBoltConfig.DEFAULT;
    private final List<Bolt> flying = new ArrayList<>();
    /** 이미 쓴 클릭의 틱 (몹 직접 클릭·다른 기능이 쓴 블록 좌클릭·실제로 깬 블록). */
    private final Map<UUID, Integer> consumedTick = new HashMap<>();
    /** 마지막으로 마법탄을 쏜 틱 — 같은 클릭의 다른 패킷(허공 휘두름이 먼저 오고 몹 클릭이 뒤따라도)이 두 번째 시도를 하지 않게. */
    private final Map<UUID, Integer> firedTick = new HashMap<>();
    /** 블록을 누르고 있는지 (punch 가 새 클릭인지). */
    private final Map<UUID, CasterBoltRules.Press> presses = new HashMap<>();
    private final Map<String, Color> colors = new ConcurrentHashMap<>();
    private BukkitTask task;

    /**
     * 쏜 순간의 무기. weaponKey = 손 칸 + 무기 id ({@code AttackClock#weaponKey} — 날던 중 무기를 바꿨는지),
     * weaponId = items.yml id (미궁 무기가 아니면 "" — {@link DamageContext#firedWith} 의 고유 효과·덧 피해), 한 방 W · 피해 종류 · 색.
     */
    record Shot(String weaponKey, String weaponId, double perHit, DamageKind kind, Color color) {}

    /** 날아가는 마법탄 하나. */
    static final class Bolt {
        final UUID shooter;
        final World world;
        final BoltPath path;
        final Shot shot;
        /** 쏜 자리 (눈) · 손 어긋남 — 꼬리 입자 자리 ({@link BoltPath#visualPoint}). */
        final Vector eye, hand;
        int ticks;
        /** 목록에서 빠짐 (tick 이 사본을 돌 때 건너뛰게). */
        boolean removed;

        Bolt(UUID shooter, World world, BoltPath path, Shot shot, Vector eye, Vector hand) {
            this.shooter = shooter;
            this.world = world;
            this.path = path;
            this.shot = shot;
            this.eye = eye;
            this.hand = hand;
        }

        Vector visual(double t) { return BoltPath.visualPoint(eye, path.direction(), hand, t, CONVERGE); }
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
        presses.clear();
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

    private CasterBoltRules.Press press(Player p) { return presses.computeIfAbsent(p.getUniqueId(), u -> new CasterBoltRules.Press()); }

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

    /**
     * 블록 좌클릭 (서바이벌 = 블록 캐기 시작, 어드벤처 = punch 바로 앞에 Paper 가 알림): 누름의 시작 ({@link CasterBoltRules.Press}).
     * 그 블록을 다른 기능이 썼으면(미궁 금 간 벽·포자 주머니·퍼즐 블록·상자 — 그 기능이 막아 둔 클릭) 같은 틱의 휘두름은 그 동작의 것.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getAction() != Action.LEFT_CLICK_BLOCK || e.getHand() == EquipmentSlot.OFF_HAND) return;
        Player p = e.getPlayer();
        GameMode gm = p.getGameMode();
        press(p).blockStart(tickNow(), gm == GameMode.SURVIVAL || gm == GameMode.CREATIVE);
        boolean deny = e.useInteractedBlock() == org.bukkit.event.Event.Result.DENY;
        if (deny) consume(p);
        if (DEBUG) Log.info("[마법탄] 블록 클릭 " + p.getName() + (deny ? " (다른 기능)" : ""));
    }

    /** 블록에서 손을 뗌 (클라이언트 ABORT — paper-26.3 은 ABORT 마다 부른다): 누름 끝. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onAbort(BlockDamageAbortEvent e) {
        CasterBoltRules.Press pr = presses.get(e.getPlayer().getUniqueId());
        if (pr != null) pr.release();
    }

    /**
     * 블록이 깨짐: 누름 끝 (클라이언트는 다음 블록을 새로 시작한다). 실제로 깨졌으면(야생의 풀·꽃처럼 바로 깨지는 블록, 크리에이티브) 같은 틱의
     * 휘두름은 캐기 — 깨진 뒤라 조준선에 블록이 없어 보여도 마법탄이 같이 나가지 않게. 미궁·광산처럼 막힌 부수기(취소됨)는 캐기로 세지 않는다.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onBreak(BlockBreakEvent e) {
        Player p = e.getPlayer();
        CasterBoltRules.Press pr = presses.get(p.getUniqueId());
        if (pr != null) pr.release();
        if (!e.isCancelled()) consume(p);
        if (DEBUG) Log.info("[마법탄] 블록 깸 " + p.getName() + (e.isCancelled() ? " (막힘)" : ""));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwing(PlayerArmSwingEvent e) {
        if (e.getHand() != EquipmentSlot.HAND || clock == null) return;
        Player p = e.getPlayer();
        boolean fresh = press(p).punch(tickNow());
        if (!ready(p)) return;
        CasterBoltRules.Punch k = CasterBoltRules.punch(true, consumed(p), busy(p), fresh, fresh && digs(p));
        if (k != CasterBoltRules.Punch.BOLT) {
            if (DEBUG && k != CasterBoltRules.Punch.HOLD) Log.info("[마법탄] 안 쏨 " + p.getName() + " " + k);
            return;
        }
        clock.casterClick(p, null);
    }

    /** 지금은 쏠 수 없음: 관전·죽음·기절·잠·창이 열려 있음. */
    boolean busy(Player p) {
        if (p.isDead() || p.getGameMode() == GameMode.SPECTATOR || p.isSleeping()) return true;
        if (services.effects().isStunned(p)) return true;
        InventoryType open = p.getOpenInventory().getType();
        return open != InventoryType.CRAFTING && open != InventoryType.CREATIVE;
    }

    /** 이 클릭은 블록 캐기인가 ({@link CasterBoltRules#digs}) — 캘 수 없는 곳·블록이 손 밖이면 적 찾기는 하지 않는다. */
    private boolean digs(Player p) {
        GameMode gm = p.getGameMode();
        boolean lab = services.dungeon() != null && services.dungeon().isLabyrinthWorld(p.getWorld());
        if (!CasterBoltRules.canDig(gm == GameMode.CREATIVE, gm == GameMode.SURVIVAL, lab)) return false;
        if (!blockInReach(p)) return false;
        return CasterBoltRules.digs(true, true, enemyOnLine(p));
    }

    /** 조준선이 손 닿는 블록에 닿는가 (통과 가능한 풀·거미줄도 — 클라이언트가 캐려고 고르는 블록). */
    private static boolean blockInReach(Player p) {
        AttributeInstance a = p.getAttribute(Attribute.BLOCK_INTERACTION_RANGE);
        double reach = a == null ? 4.5 : a.getValue();
        Location eye = p.getEyeLocation();
        return p.getWorld().rayTraceBlocks(eye, eye.getDirection(), reach, FluidCollisionMode.NEVER, false) != null;
    }

    /** 지금 쏘면 맞을 적이 조준선에 있는가 (막는 블록 앞, 사거리까지 — 마법탄과 같은 판정). */
    private boolean enemyOnLine(Player p) {
        Location eye = p.getEyeLocation();
        Vector from = eye.toVector(), dir = eye.getDirection().normalize();
        double range = cfg.range();
        RayTraceResult block = p.getWorld().rayTraceBlocks(eye, dir, range, FluidCollisionMode.NEVER, true);
        double blockDist = block == null ? Double.POSITIVE_INFINITY : block.getHitPosition().distance(from);
        return firstEnemy(p.getWorld(), p, from, dir, range, blockDist) != null;
    }

    // ── 쏘기 ──────────────────────────────────────────────────────────────

    /** 쏜 순간의 무기 (손 칸 + 무기 id · 한 방 W · 피해 종류 · 색). */
    private Shot shot(Player p) {
        DerivedStats s = services.stats().get(p);
        ItemDef def = services.items().heldWeapon(p);
        return new Shot(clock.weaponKey(p), def == null ? "" : def.id(), s.weaponDamage(), s.weaponKind(), color(def));
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
        Location eyeLoc = p.getEyeLocation();
        Vector eye = eyeLoc.toVector(), dir = eyeLoc.getDirection().normalize();
        Vector hand = BoltPath.handOffset(eyeLoc.getYaw(), dir, p.getMainHand() == MainHand.LEFT, HAND_RIGHT, HAND_DOWN);
        World w = p.getWorld();
        CasterBoltConfig c = cfg;
        if (DEBUG) Log.info("[마법탄] 쏨 " + p.getName() + (strike != null ? " (바로)" : ""));
        if (c.sound()) {
            float pitch = (float) (1.65 + Math.random() * 0.2);
            w.playSound(eyeLoc, Sound.BLOCK_AMETHYST_BLOCK_CHIME, SoundCategory.PLAYERS, 0.45f, pitch);
        }
        if (c.trail()) muzzle(w, BoltPath.visualPoint(eye, dir, hand, TIP, CONVERGE), shot.color());
        if (strike != null) {
            Vector to = strike.getBoundingBox().getCenter();
            Vector toDir = to.clone().subtract(eye);
            double dist = toDir.length();
            if (c.trail() && dist > TRAIL_START) {
                toDir.multiply(1 / dist);
                line(w, BoltPath.visualPoint(eye, toDir, hand, 0, CONVERGE), to, 0, dist, toDir, shot.color());
            }
            hit(p, strike, shot, to);
            return;
        }
        BoltPath path = new BoltPath(eye, dir, c.speed(), c.range());
        Bolt b = new Bolt(p.getUniqueId(), w, path, shot, eye, hand);
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
                gone = p == null || !p.isOnline() || p.isDead() || !p.getWorld().equals(b.world)
                        || !clock.weaponKey(p).equals(b.shot.weaponKey()) // 손의 무기를 바꿈 → 사라짐 (다른 무기의 고유 효과가 섞이지 않게)
                        || ++b.ticks > maxTicks || step(b, p);
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
        double t0 = path.travelled();
        RayTraceResult block = b.world.rayTraceBlocks(from.toLocation(b.world), dir, len, FluidCollisionMode.NEVER, true);
        double blockDist = block == null ? Double.POSITIVE_INFINITY : block.getHitPosition().distance(from);
        BoltPath.Hit<LivingEntity> hit = firstEnemy(b.world, p, from, dir, len, blockDist);
        CasterBoltConfig c = cfg;
        if (hit != null) {
            Vector at = from.clone().add(dir.clone().multiply(hit.distance()));
            if (c.trail()) trailStep(b, t0, t0 + hit.distance(), at);
            hit(p, hit.target(), b.shot, at);
            return true;
        }
        if (block != null) {
            Vector at = block.getHitPosition();
            if (c.trail()) {
                trailStep(b, t0, t0 + blockDist, at);
                burst(b.world, at, b.shot.color(), 4, 3, 0.3);
            }
            return true;
        }
        if (c.trail()) trailStep(b, t0, t0 + len, null);
        path.advance(len);
        if (path.done()) {
            if (c.trail()) burst(b.world, b.visual(path.travelled()), b.shot.color(), 2, 3, 0.35);
            return true;
        }
        return false;
    }

    /**
     * 이 선분에서 처음 맞는 적 (막는 블록 앞, 보이는 것만 — {@link BoltPath#firstHit} 의 시야 검사는 통과 가능한 블록을 지나가는 마법탄과
     * 같은 블록 광선).
     */
    private BoltPath.Hit<LivingEntity> firstEnemy(World w, Player p, Vector from, Vector dir, double len, double blockDist) {
        double radius = cfg.radius();
        BoundingBox area = BoltPath.segmentBox(from, dir, Math.min(len, blockDist), radius);
        List<BoltPath.Candidate<LivingEntity>> cands = new ArrayList<>(4);
        for (Entity e : w.getNearbyEntities(area, e -> e instanceof LivingEntity && !e.equals(p))) {
            LivingEntity le = (LivingEntity) e;
            if (le.isDead() || !le.isValid() || !services.targets().isEnemy(p, le)) continue;
            cands.add(new BoltPath.Candidate<>(le, le.getBoundingBox()));
        }
        if (cands.isEmpty()) return null;
        return BoltPath.firstHit(from, dir, len, radius, blockDist, cands, (cand, at, nearest) -> clear(w, at, nearest));
    }

    /** a → b 사이에 막는 블록이 없는가 (풀·거미줄처럼 통과 가능한 블록은 지나감). */
    private static boolean clear(World w, Vector a, Vector b) {
        Vector d = b.clone().subtract(a);
        double dist = d.length();
        if (dist < 1e-4) return true;
        RayTraceResult r = w.rayTraceBlocks(a.toLocation(w), d.multiply(1 / dist), dist, FluidCollisionMode.NEVER, true);
        return r == null || r.getHitPosition().distance(a) >= dist - 1e-3;
    }

    /** 선분이 지나는 청크가 모두 올라와 있는가 (마법탄이 청크를 불러오지 않게). */
    private static boolean loaded(World w, Vector a, Vector b) {
        int x0 = (int) Math.floor(Math.min(a.getX(), b.getX())) >> 4, x1 = (int) Math.floor(Math.max(a.getX(), b.getX())) >> 4;
        int z0 = (int) Math.floor(Math.min(a.getZ(), b.getZ())) >> 4, z1 = (int) Math.floor(Math.max(a.getZ(), b.getZ())) >> 4;
        for (int x = x0; x <= x1; x++) for (int z = z0; z <= z1; z++) if (!w.isChunkLoaded(x, z)) return false;
        return true;
    }

    // ── 맞음 ──────────────────────────────────────────────────────────────

    /** 맞은 적에게 기본 공격 한 방 (마법, 플레이어에게는 × pvp_damage). 맞는 순간 다시 적인지 본다. */
    private void hit(Player p, LivingEntity target, Shot shot, Vector at) {
        if (!target.isValid() || target.isDead() || !target.getWorld().equals(p.getWorld())) return;
        if (!services.targets().isEnemy(p, target)) return;
        CasterBoltConfig c = cfg;
        boolean pvp = target instanceof Player;
        DamageContext ctx = context(p, target, shot, pvp ? c.pvpDamage() : 1.0);
        if (pvp && c.pvpKnockback() > 0) ctx.knockback(c.pvpKnockback());
        damage.deal(ctx);
        World w = target.getWorld();
        if (c.trail()) burst(w, at, shot.color(), 6, 5, 0.5);
        if (c.sound()) {
            w.playSound(at.toLocation(w), Sound.BLOCK_AMETHYST_BLOCK_HIT, SoundCategory.PLAYERS, 0.6f, 1.4f);
            if (!ctx.cancelled() && !ctx.evaded() && p.getEyeLocation().toVector().distanceSquared(at) >= HIT_TICK_MIN * HIT_TICK_MIN) {
                p.playSound(p, Sound.ENTITY_ARROW_HIT_PLAYER, SoundCategory.PLAYERS, 0.3f, 1.6f); // 멀리 맞힘 — 쏜 사람만 듣는 '딩'
            }
        }
        if (DEBUG) {
            Log.info("[마법탄] " + p.getName() + " → " + target.getType() + " " + target.getUniqueId().toString().substring(0, 8)
                    + " 피해 " + String.format(java.util.Locale.ROOT, "%.1f", ctx.finalDamage())
                    + (ctx.cancelled() ? " (막힘)" : ctx.evaded() ? " (회피)" : ctx.crit() ? " (치명)" : ""));
        }
    }

    /**
     * 마법탄 한 발의 피해 (순수 — 시험 대상): 기본 공격 × mult (플레이어에게는 {@code pvp_damage}, 몹에게는 1) · 유형 마법 ·
     * 쏜 순간의 무기 W 와 피해 종류 · 쏜 무기 id ({@link DamageContext#firedWith}). 화살과 같은 길 — 고유 효과·덧 피해 W 는 쏜 시전 무기로
     * (0.3.6.1 통합. 무기를 바꾸면 날던 마법탄은 사라지므로 안전장치).
     */
    static DamageContext context(Player p, LivingEntity target, Shot shot, double mult) {
        return DamageContext.basic(p, target, mult, DamageType.MAGIC).kind(shot.kind()).weaponHit(shot.perHit())
                .firedWith(shot.weaponId()).casterBolt();
    }

    // ── 입자 ──────────────────────────────────────────────────────────────

    /**
     * 이번 걸음 [t0, t1] 의 꼬리. end == null 이면 손에서 조준선으로 모이는 길({@link Bolt#visual}), 아니면 이 걸음 시작 자리에서 끝(맞은 곳·벽)까지
     * 곧게 — 6칸 안에서 맞아도 꼬리가 맞은 자리에서 끝난다.
     */
    private void trailStep(Bolt b, double t0, double t1, Vector end) {
        Vector dir = b.path.direction();
        if (end == null) {
            for (double t = (Math.floor(t0 / TRAIL_STEP) + 1) * TRAIL_STEP; t <= t1 + 1e-9; t += TRAIL_STEP) {
                if (t >= TRAIL_START) dot(b.world, b.visual(t), dir, b.shot.color(), core(t));
            }
            if (t1 >= TRAIL_START) head(b.world, b.visual(t1), dir, b.shot.color());
            return;
        }
        line(b.world, b.visual(t0), end, t0, t1, dir, b.shot.color());
    }

    /** a(조준선 거리 t0) → b(거리 t1) 곧은 꼬리 (거리 {@link #TRAIL_START} 앞은 건너뜀). */
    private static void line(World w, Vector a, Vector b, double t0, double t1, Vector dir, Color color) {
        double span = t1 - t0;
        for (double t = (Math.floor(t0 / TRAIL_STEP) + 1) * TRAIL_STEP; t <= t1 + 1e-9; t += TRAIL_STEP) {
            if (t < TRAIL_START) continue;
            double k = span < 1e-6 ? 1 : (t - t0) / span;
            dot(w, a.clone().add(b.clone().subtract(a).multiply(k)), dir, color, core(t));
        }
    }

    private static boolean core(double t) { return Math.round(t / TRAIL_STEP) % 2 == 0; }

    /** 꼬리 한 점: 무기 색 DUST + (두 점에 하나) 밝은 TRAIL 알갱이가 조금 앞으로 미끄러진다 (TRAIL 은 빛이 없어도 밝게 그려진다). */
    private static void dot(World w, Vector pt, Vector dir, Color color, boolean core) {
        Location l = pt.toLocation(w);
        w.spawnParticle(Particle.DUST, l, 1, 0.02, 0.02, 0.02, 0, new Particle.DustOptions(color, 0.9f), false);
        if (core) {
            w.spawnParticle(Particle.TRAIL, l, 1, 0, 0, 0, 0,
                    new Particle.Trail(pt.clone().add(dir.clone().multiply(0.3)).toLocation(w), color, 4), false);
        }
    }

    /** 마법탄 머리: 밝은 알갱이 둘이 앞으로 1칸 미끄러짐 (2틱). */
    private static void head(World w, Vector pt, Vector dir, Color color) {
        Location target = pt.clone().add(dir.clone().multiply(1.0)).toLocation(w);
        w.spawnParticle(Particle.TRAIL, pt.toLocation(w), 2, 0.03, 0.03, 0.03, 0, new Particle.Trail(target, lighten(color, 0.45), 2), false);
    }

    /** 지팡이 끝 반짝임 (쏠 때). */
    private static void muzzle(World w, Vector tip, Color color) {
        w.spawnParticle(Particle.DUST, tip.toLocation(w), 2, 0.04, 0.04, 0.04, 0, new Particle.DustOptions(color, 0.7f), false);
        sparks(w, tip, lighten(color, 0.45), 3, 0.18, 4);
    }

    /** 터짐 (맞은 곳·벽·사거리 끝): 무기 색 DUST dust 개 + 밝은 알갱이 n 개가 radius 안으로 퍼짐. */
    private static void burst(World w, Vector at, Color color, int dust, int n, double radius) {
        w.spawnParticle(Particle.DUST, at.toLocation(w), dust, 0.15, 0.15, 0.15, 0, new Particle.DustOptions(color, 1.1f), false);
        sparks(w, at, lighten(color, 0.45), n, radius, 5);
    }

    /** 밝은 TRAIL 알갱이 n 개가 at 에서 radius 안의 아무 곳으로 ticks 동안 미끄러짐. */
    private static void sparks(World w, Vector at, Color color, int n, double radius, int ticks) {
        Location l = at.toLocation(w);
        ThreadLocalRandom r = ThreadLocalRandom.current();
        for (int i = 0; i < n; i++) {
            Vector to = at.clone().add(new Vector(r.nextDouble(-1, 1), r.nextDouble(-1, 1), r.nextDouble(-1, 1)).multiply(radius));
            w.spawnParticle(Particle.TRAIL, l, 1, 0, 0, 0, 0, new Particle.Trail(to.toLocation(w), color, ticks), false);
        }
    }

    /** 흰색 쪽으로 k 만큼. */
    static Color lighten(Color c, double k) {
        return Color.fromRGB((int) Math.round(c.getRed() + (255 - c.getRed()) * k), (int) Math.round(c.getGreen() + (255 - c.getGreen()) * k),
                (int) Math.round(c.getBlue() + (255 - c.getBlue()) * k));
    }

    // ── 정리 ──────────────────────────────────────────────────────────────

    private void drop(UUID u) {
        flying.removeIf(b -> b.shooter.equals(u) && (b.removed = true));
        consumedTick.remove(u);
        firedTick.remove(u);
        presses.remove(u);
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
