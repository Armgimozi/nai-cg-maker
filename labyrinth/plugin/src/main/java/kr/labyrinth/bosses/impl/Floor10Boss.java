package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.bosses.Ticking;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 지하 10층 — 심연의 심장 넬카르 (GDD §7.10, core {@code collapse_and_chase}). 보스는 걷지 않는다(speed 0).
 * <p>
 * 투기장 ① 심장실(반경 18, 3×3 타일) ② 탈출 회랑(+z, 길이 80 폭 7, 틈 3곳) ③ 심연의 가장자리(반경 12 단 + 낭떠러지 고리).
 * ②③ 은 FloorGenerator 가 {@code arena.corridor_length}·{@code rim_radius} 로 깔고, 이 보스가 전투 중 블록을 바꾼다
 * (회랑 입구 막 → 2페이즈 개방, 틈·낭떠러지·다리 붕괴, 끝나면 기반이 전부 복원). 블록을 못 놓는 곳(관리자 소환)은 같은 자리를
 * "떨어지는 칸"으로 판정만 한다.
 * <ul>
 *   <li>1페이즈 심연 붕괴(9초마다, 배치 흩뿌리기·체스판·동심원·십자·나선): 보라 타일 경고 2.5초 → 실제로 무너짐 → 15초 뒤 복구.</li>
 *   <li>2페이즈 진입 = 심연의 추격: 심장이 가장자리로 가라앉고(무적), 회랑 입구가 열리고 3초 뒤 북쪽에서 해일 벽이 초속 4.6칸(+가속)으로
 *       심장실·회랑을 삼키며 쫓아온다(닿으면 초당 최대 HP 50% + 앞으로 밀침). 회랑엔 낙석 원과 점프할 틈. 전원 가장자리 도착 → 재개.</li>
 *   <li>2~3페이즈 가장자리: 회전 응시(광선 2·3개 초당 30°), 심연 균열(원 + 잔류), 촉수 채찍·공허 구체(1~2).</li>
 *   <li>3페이즈: 지난 층의 메아리(20초마다 1~9층 상징 패턴을 위력 70%·경고 ×1.2 로), 심장 박동(30초마다 전원, 매번 +15%).</li>
 *   <li>떨어짐(실제 낙하 또는 판정 칸) = 최대 HP 25% + 가장 가까운 안전한 칸으로 + 3초간 받는 피해 +20%.</li>
 *   <li>대응 (GDD §8.6): 걷지 않는 심장의 칼끝 거리(기본 공격 밖, 칼은 닿음)에서 때리면 맥동 고리 — 고리(자기 거리 −0.2 ~ 6칸) 안
 *       촉수 채찍 피해 + 심장 쪽 끌기 + 4초 잔류. 바짝 붙은 사람은 기본 공격, 멀리서는 그대로.</li>
 * </ul>
 * 문구는 분위기·단서만 (조작법은 bosses.yml {@code hints} 의 점진 힌트로).
 */
public final class Floor10Boss extends Boss {

    private static final Color ABYSS = Color.fromRGB(47, 224, 208);
    private static final Color VOID = Color.fromRGB(110, 40, 170);
    private static final Color HEART = Color.fromRGB(176, 26, 58);
    private static final Color ENRAGE = Color.fromRGB(255, 40, 40);
    private static final Color MOSS = Color.fromRGB(127, 191, 90);
    private static final Color SPORE = Color.fromRGB(90, 140, 255);
    private static final Color BLOOM = Color.fromRGB(255, 214, 74);
    private static final Color WATER = Color.fromRGB(90, 180, 255);
    private static final Color FORGE = Color.fromRGB(255, 138, 42);
    private static final Color ICE = Color.fromRGB(191, 230, 255);
    private static final Color CLOCK = Color.fromRGB(230, 194, 122);
    private static final Color INK = Color.fromRGB(40, 30, 60);
    private static final BlockData AIR = Material.AIR.createBlockData();
    private static final BlockData CRACK = Material.DEEPSLATE.createBlockData();

    private enum Stage { CHAMBER, PURSUIT, RIM }

    private Stage stage = Stage.CHAMBER;
    private World world;
    private int cx, cz, fy;
    private AbyssLogic.Geometry geo;
    private boolean realBlocks;

    // ── ① 심장실 붕괴 ──
    private AbyssLogic.Grid grid;
    private int tileSize;
    private List<AbyssLogic.Layout> layouts = List.of();
    private int wave;
    private final Map<Integer, List<Block>> fallenBlocks = new HashMap<>();
    private final Map<Integer, BlockDisplay> holeMarks = new HashMap<>();
    private final Map<Integer, Telegraph> warnings = new HashMap<>();

    // ── ②③ 회랑·가장자리 ──
    private final List<Block> membrane = new ArrayList<>();
    private final List<Block> bridge = new ArrayList<>();
    private boolean bridgeDown;
    private int[] gaps = new int[0];
    private int gapLen = 2;
    private final List<int[]> tickets = new ArrayList<>();

    // ── 추격 ──
    private long pursuitStart;
    private boolean wallRunning;
    private double wallStart, wallZ, wallSpeed, wallAccel;
    private final List<ItemDisplay> wallFx = new ArrayList<>();
    private int debrisLeft;
    private double debrisStep, nextDebris;
    private final Map<UUID, Long> wallHitAt = new HashMap<>();

    // ── 낙하·기타 ──
    private final Map<UUID, Long> fellAt = new HashMap<>();
    private final Set<UUID> anchored = new HashSet<>();
    private boolean gazeActive;
    private int pulses;
    private String lastEcho;

    public Floor10Boss(Init init) { super(init); }

    // ── 아레나 ───────────────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        world = center.getWorld();
        cx = center.getBlockX();
        cz = center.getBlockZ();
        fy = (int) Math.floor(floorY + 0.01) - 1;
        Params a = def.arena();
        int r = (int) Math.round(arenaRadius);
        geo = AbyssLogic.Geometry.of(r, a.integer("corridor_length", 80), a.integer("corridor_width", 7), a.integer("rim_radius", 12),
                FloorGenerator.RIM_MOAT);
        Params pc = def.pattern("abyssal_collapse");
        tileSize = AbyssLogic.oddSize(pc.dbl("tile_size", a.dbl("tile_size", 3)));
        grid = new AbyssLogic.Grid(AbyssLogic.chamberTiles(r, tileSize), tileSize);
        layouts = AbyssLogic.Layout.parseAll(pc.strings("layouts"));
        wave = rng.nextInt(Math.max(1, layouts.size()));
        Params pp = def.pattern("devouring_pursuit");
        gapLen = Math.max(1, pp.integer("gap_length", 2));
        gaps = geo.gapStarts(pp.integer("gaps", 3), gapLen);
        // 인스턴스 투기장이 실제로 회랑·가장자리까지 깔려 있을 때만 블록을 바꾼다
        realBlocks = canPlaceBlocks() && solidAt(0, geo.uStart() + 6) && solidAt(0, geo.rimU());
        setPathing(false);
        if (realBlocks) {
            holdChunks();
            sealCorridor();
            carveMoat();
        }
        BossFx.sound(center, Sound.ENTITY_WARDEN_HEARTBEAT, 2f, 0.5f);
        BossFx.particle(Particle.SCULK_SOUL, center.clone().add(0, 1.5, 0), 60, arenaRadius * 0.4, 1.0, arenaRadius * 0.4, 0.02);
    }

    private boolean solidAt(int dx, int dz) { return world.getBlockAt(cx + dx, fy, cz + dz).getType().isSolid(); }

    /** 심장실 중심 블록 기준 오프셋 → 바닥 위 위치 (블록 중심). */
    private Location at(double dx, double dz) { return new Location(world, cx + 0.5 + dx, floorY, cz + 0.5 + dz); }

    private int ox(Location l) { return l.getBlockX() - cx; }

    private int oz(Location l) { return l.getBlockZ() - cz; }

    /** 회랑·가장자리 청크를 전투 동안 붙잡아 둔다 (보스가 가장자리로 옮겨 가도 사라지지 않게). */
    private void holdChunks() {
        int minX = Math.floorDiv(cx - geo.rimOuter() - 1, 16), maxX = Math.floorDiv(cx + geo.rimOuter() + 1, 16);
        int minZ = Math.floorDiv(cz + geo.uStart(), 16), maxZ = Math.floorDiv(cz + geo.rimU() + geo.rimOuter() + 1, 16);
        for (int x = minX; x <= maxX; x++) {
            for (int z = minZ; z <= maxZ; z++) {
                if (world.addPluginChunkTicket(x, z, services.plugin())) tickets.add(new int[]{x, z});
            }
        }
    }

    /** 1페이즈 동안 회랑 입구를 심장의 막(스컬크·우는 흑요석)으로 막는다. */
    private void sealCorridor() {
        int z = cz + geo.r() + 1;
        for (int dx = -geo.half(); dx <= geo.half(); dx++) {
            for (int dy = 1; dy <= 10; dy++) {
                Block b = world.getBlockAt(cx + dx, fy + dy, z);
                if (!b.getType().isAir()) continue;
                BlockData d = (Math.floorMod(dx * 7 + dy * 3, 5) == 0 ? Material.CRYING_OBSIDIAN : Material.SCULK).createBlockData();
                if (setBlock(b, d)) membrane.add(b);
            }
        }
    }

    /** 가장자리 단 바깥 고리를 비워 낭떠러지로 (다리 = 회랑 폭 북쪽은 추격이 끝날 때까지 남긴다). */
    private void carveMoat() {
        int ro = geo.rimOuter();
        for (int dx = -ro; dx <= ro; dx++) {
            for (int dz = geo.rimU() - ro; dz <= geo.rimU() + ro; dz++) {
                if (!geo.inMoat(dx, dz)) continue;
                Block f = world.getBlockAt(cx + dx, fy, cz + dz);
                if (geo.inBridge(dx, dz)) {
                    if (f.getType().isSolid()) bridge.add(f);
                    continue;
                }
                clearColumn(f, null);
            }
        }
    }

    /** 바닥 블록 + 그 위 장식 2칸을 비운다. @return 실제로 바꾼 블록 */
    private List<Block> clearColumn(Block floor, List<Block> into) {
        List<Block> out = into == null ? new ArrayList<>() : into;
        if (!floor.getType().isAir() && setBlock(floor, AIR)) out.add(floor);
        for (int dy = 1; dy <= 2; dy++) {
            Block up = floor.getRelative(0, dy, 0);
            if (!up.getType().isAir() && !up.getType().isOccluding() && setBlock(up, AIR)) out.add(up);
        }
        return out;
    }

    @Override
    protected boolean blockAllowed(Block b) {
        if (geo == null) return super.blockAllowed(b);
        return geo.inBattle(b.getX() - cx, b.getZ() - cz, 2);
    }

    /** 심장실·회랑·가장자리 어디든 (기반은 전투 중심 원만 본다). */
    @Override
    protected boolean validPlayer(Player p) {
        if (geo == null) return super.validPlayer(p);
        if (p == null || !p.isOnline() || p.isDead() || p.getWorld() != world) return false;
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return false;
        Location l = p.getLocation();
        if (!geo.inBattle(ox(l), oz(l), 4)) return false;
        if (l.getY() < floorY - 6 || l.getY() > floorY + arenaHeight + 6) return false;
        if (downed(p)) return false;
        return services.targets().isEnemy(entity, p);
    }

    private boolean downed(Player p) {
        try {
            return services.dungeon().isDowned(p);
        } catch (Throwable ignored) {
            return false;
        }
    }

    @Override
    protected boolean knockbackImmune(Player p) {
        return anchored.contains(p.getUniqueId()) || super.knockbackImmune(p);
    }

    // ── 매 틱 ────────────────────────────────────────────────────────────

    @Override
    protected void onTick() {
        if (geo == null) return;
        tickTiles();
        tickFalls();
        if (stage == Stage.PURSUIT) tickPursuit();
        if (now % 30 == 0) {
            Location l = entity.getLocation();
            BossFx.sound(l, Sound.ENTITY_WARDEN_HEARTBEAT, 1.6f, 0.55f);
            BossFx.particle(Particle.SCULK_SOUL, l.clone().add(0, def.scale() * 0.9, 0), 6, 1.2, 1.0, 1.2, 0.02);
        }
        if (stage == Stage.RIM && now % 6 == 0) {
            // 낭떠러지 고리에서 올라오는 어둠
            double ang = rng.nextDouble() * Math.PI * 2, rr = geo.rimR() + 1 + rng.nextDouble() * (geo.rimOuter() - geo.rimR());
            Location m = at(Math.cos(ang) * rr, geo.rimU() + Math.sin(ang) * rr).add(0, -1.5, 0);
            BossFx.particle(Particle.SQUID_INK, m, 3, 0.4, 0.6, 0.4, 0.02);
            BossFx.particle(Particle.REVERSE_PORTAL, m, 4, 0.5, 0.5, 0.5, 0.02);
        }
    }

    @Override
    protected boolean canUse(String key) {
        if (stage == Stage.PURSUIT) return false;
        return switch (key) {
            case "rotating_gaze" -> !gazeActive && target() != null;
            case "abyssal_collapse", "heartbeat_pulse", "devouring_pursuit" -> false;
            default -> target() != null;
        };
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "tendril_lash" -> tendrilLash();
            case "void_orbs" -> voidOrbs();
            case "rotating_gaze" -> rotatingGaze();
            case "abyss_rift" -> abyssRift();
            case "floor_echoes" -> floorEcho();
            default -> 0;
        };
    }

    @Override
    protected void runInterval(String key) {
        switch (key) {
            case "abyssal_collapse" -> {
                if (stage == Stage.CHAMBER) collapseWave();
            }
            case "heartbeat_pulse" -> {
                if (stage == Stage.RIM) heartbeat();
            }
            default -> { }
        }
    }

    @Override
    protected void onPhase(int newPhase) {
        setPathing(false);
        if (stage == Stage.CHAMBER) startPursuit();
        if (newPhase >= 3) {
            pulses = 0;
            rig.setGlow(HEART);
            afterPersistent(30, () -> rig.setGlow(enraged() ? ENRAGE : null));
            BossFx.sound(center, Sound.ENTITY_WARDEN_HEARTBEAT, 3f, 0.4f);
            BossFx.dustRing(feet(), geo.rimR() * 0.7, HEART, 2f, 64);
        }
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    // ── 촉수 채찍 ────────────────────────────────────────────────────────

    private int tendrilLash() {
        Params p = def.pattern("tendril_lash");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 1.0);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), p.dbl("angle", 100), p.dbl("length", 7));
        double dmg = dmg(p, "damage", 1.4);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "tendril_lash", DamageType.MELEE, null);
            Vector d = cone.direction();
            for (double f = 1.5; f <= cone.size(); f += 1.5) {
                Location l = cone.origin().clone().add(d.clone().multiply(f)).add(0, 0.8, 0);
                BossFx.particle(Particle.SQUID_INK, l, 4, 0.6, 0.3, 0.6, 0.04);
                BossFx.particle(Particle.SCULK_SOUL, l, 2, 0.6, 0.3, 0.6, 0.02);
            }
            BossFx.sound(entity.getLocation(), Sound.ENTITY_WARDEN_ATTACK_IMPACT, 1.6f, 0.6f);
            BossFx.sound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.2f, 0.5f);
        });
        return cast("tendril_lash", "촉수 채찍", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 대응: 맥동 고리 (GDD §8.6) ───────────────────────────────────────

    @Override
    protected boolean canAnswer(Player t) { return stage != Stage.PURSUIT && !gazeActive; }

    /**
     * 심장 발밑 고리(안 = 자기 거리 − inner_pad, 밖 = outer) 경고 → 고리 안 모두 촉수 채찍 피해 + 심장 쪽으로 끌기(구멍 너머면 끌기 없음)
     * + 심연 균열 잔류(linger 초, linger_dps). 칼끝 거리에 머물지 말고 붙거나 물러나야 한다.
     */
    @Override
    protected int answer(Answer a) {
        Player t = a.target();
        if (t == null || !t.isValid() || geo == null) return 0;
        Params ad = answerDef();
        Params tp = def.pattern("tendril_lash");
        Params rp = def.pattern("abyss_rift");
        int w = windup(tp, 1.0);
        double inner = Math.max(0.5, reach() - ad.dbl("inner_pad", 0.2));
        double outer = Math.max(inner + 0.5, ad.dbl("outer", 6.0));
        double pull = ad.dbl("pull", 0.9);
        Location c = feet();
        Telegraph.Shape ring = Telegraph.Shape.ring(c, inner, outer);
        double dmg = dmg(tp, "damage", 1.4);
        int linger = ticks(rp.dbl("linger", 4));
        double ld = dmg(rp, "linger_dps", 0.3);
        broadcastBar("<dark_aqua>심장 둘레가 크게 고동친다…</dark_aqua>");
        run(new Mechanics.Repeat(w, 10, tt -> {
            BossFx.sound(c, Sound.ENTITY_WARDEN_HEARTBEAT, 1.8f, 0.6f);
            BossFx.dustRing(c.clone().add(0, 0.3, 0), inner + (outer - inner) * Math.min(1, tt / (double) Math.max(1, w)), HEART, 1.6f, 32);
            return true;
        }, null, true));
        telegraph(ring, w, Telegraph.RED, "telegraph_ring", () -> {
            Location hc = entity.getLocation();
            boolean chamber = stage == Stage.CHAMBER;
            hitShape(ring, dmg, "tendril_lash", DamageType.MELEE, pl -> {
                Location l = pl.getLocation();
                if (AbyssLogic.pullClear(grid, l.getX() - cx, l.getZ() - cz, hc.getX() - cx, hc.getZ() - cz, inner, chamber)) pull(pl, c, pull);
            });
            BossFx.sound(c, Sound.ENTITY_WARDEN_ATTACK_IMPACT, 1.8f, 0.5f);
            BossFx.particle(Particle.SQUID_INK, c.clone().add(0, 0.6, 0), 40, outer * 0.5, 0.3, outer * 0.5, 0.05);
            BossFx.particle(Particle.SCULK_SOUL, c.clone().add(0, 0.6, 0), 20, outer * 0.5, 0.3, outer * 0.5, 0.02);
            run(new Mechanics.Zone(fx, ring, linger, 20, "telegraph_ring", VOID, Particle.REVERSE_PORTAL, this::players,
                    pl -> hit(pl, ld, "tendril_lash", DamageType.MAGIC)));
        });
        return cast("tendril_lash", "맥동 고리", w, w + 8, BossAnim.SLAM, null, false);
    }

    // ── 공허 구체 ────────────────────────────────────────────────────────

    private int voidOrbs() {
        Params p = def.pattern("void_orbs");
        List<Player> ts = targets();
        if (ts.isEmpty()) return 0;
        Collections.shuffle(ts, rng);
        int count = scaling().count(p, "count", 2, 0);
        int w = windup(p, 0.8);
        double speed = p.dbl("speed", 0.2) * scaling().speedMult();
        double homing = p.dbl("homing", 0.06);
        double radius = p.dbl("radius", 2);
        double dmg = dmg(p, "damage", 1.2);
        int life = ticks(p.dbl("lifetime", 8));
        String model = p.str("fx", "proj_void_orb");
        Location base = entity.getLocation().add(0, Math.max(1.5, def.scale() * 1.1), 0);
        for (int i = 0; i < count; i++) {
            UUID tgt = ts.get(i % ts.size()).getUniqueId();
            double ang = 360.0 * i / count + rng.nextDouble() * 20;
            Location start = base.clone().add(BossMath.ax(ang) * 2.4, 0, BossMath.az(ang) * 2.4);
            BossFx.particle(Particle.REVERSE_PORTAL, start, 16, 0.3, 0.3, 0.3, 0.05);
            after(w + i * 4, () -> run(new VoidOrb(start, tgt, speed, homing, radius, dmg, life, model)));
        }
        BossFx.sound(entity.getLocation(), Sound.BLOCK_SCULK_SHRIEKER_SHRIEK, 1.2f, 0.5f);
        return cast("void_orbs", "공허 구체", w, w + 6, BossAnim.CAST, null, false);
    }

    /** 느리게 유도되는 공허 구체 — 닿으면 r2 폭발, 수명이 다하면 흩어진다. */
    private final class VoidOrb implements Ticking {
        private final ItemDisplay display;
        private final Location pos;
        private final double speed, homing, radius, dmg;
        private final int life;
        private UUID target;
        private double vx, vz;
        private int t;
        private boolean done;

        VoidOrb(Location start, UUID target, double speed, double homing, double radius, double dmg, int life, String model) {
            this.pos = start.clone();
            this.pos.setYaw(0);
            this.pos.setPitch(0);
            this.target = target;
            this.speed = speed;
            this.homing = homing;
            this.radius = radius;
            this.dmg = dmg;
            this.life = life;
            Player tp = Bukkit.getPlayer(target);
            Vector d = tp == null ? facing() : tp.getLocation().toVector().subtract(pos.toVector()).setY(0);
            if (d.lengthSquared() < 1e-6) d = facing();
            d.normalize().multiply(speed);
            vx = d.getX();
            vz = d.getZ();
            this.display = fx.model(model, pos, 1.6f, Display.Billboard.CENTER);
            if (display != null) display.setBrightness(new Display.Brightness(15, 15));
        }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            if (++t > life) {
                fizzle();
                return true;
            }
            Player tp = Bukkit.getPlayer(target);
            if (tp == null || !validPlayer(tp)) {
                tp = nearest(pos);
                if (tp != null) target = tp.getUniqueId();
            }
            double vy = 0;
            if (tp != null) {
                Location aim = tp.getLocation().add(0, 1.0, 0);
                double[] v = AbyssLogic.steer(vx, vz, aim.getX() - pos.getX(), aim.getZ() - pos.getZ(), homing, speed);
                vx = v[0];
                vz = v[1];
                vy = Math.max(-0.08, Math.min(0.08, (aim.getY() - pos.getY()) * 0.1));
            }
            pos.add(vx, vy, vz);
            if (display != null && display.isValid()) display.teleport(pos.clone());
            if (t % 2 == 0) {
                BossFx.particle(Particle.REVERSE_PORTAL, pos, 2, 0.15, 0.15, 0.15, 0.01);
                BossFx.dust(pos, ABYSS, 1.2f, 1, 0.1);
            }
            for (Player pl : players()) {
                if (pl.getLocation().add(0, 1.0, 0).distanceSquared(pos) <= 1.4 * 1.4) {
                    explode();
                    return true;
                }
            }
            return false;
        }

        private void explode() {
            done = true;
            fx.discard(display);
            Location g = pos.clone();
            g.setY(Math.max(floorY, pos.getY() - 1.0));
            hitShape(Telegraph.Shape.circle(g, radius), dmg, "void_orbs", DamageType.MAGIC, null);
            BossFx.particle(Particle.SONIC_BOOM, pos, 1, 0, 0, 0, 0);
            BossFx.particle(Particle.REVERSE_PORTAL, pos, 40, radius * 0.4, 0.5, radius * 0.4, 0.1);
            BossFx.dustRing(g.clone().add(0, 0.2, 0), radius, VOID, 1.6f, 24);
            BossFx.sound(pos, Sound.ENTITY_WARDEN_SONIC_BOOM, 0.8f, 1.4f);
        }

        private void fizzle() {
            done = true;
            fx.discard(display);
            BossFx.particle(Particle.SMOKE, pos, 12, 0.2, 0.2, 0.2, 0.02);
            BossFx.sound(pos, Sound.BLOCK_SCULK_SENSOR_CLICKING_STOP, 0.8f, 0.6f);
        }

        @Override
        public void cancel() {
            done = true;
            fx.discard(display);
        }
    }

    private Player nearest(Location l) {
        Player best = null;
        double bd = Double.MAX_VALUE;
        for (Player p : targets()) {
            double d = p.getLocation().distanceSquared(l);
            if (d < bd) {
                bd = d;
                best = p;
            }
        }
        return best;
    }

    // ── ① 심연 붕괴 (interval, 1페이즈) ──────────────────────────────────

    private void collapseWave() {
        Params p = def.pattern("abyssal_collapse");
        List<int[]> avail = grid.solidTiles();
        if (avail.isEmpty()) return;
        int count = AbyssLogic.collapseCount(grid.count(), avail.size(), p.dbl("tiles_per_wave", 0.3),
                p.dbl("tiles_per_wave_per_member", 0.02), partySize());
        AbyssLogic.Layout layout = AbyssLogic.nextLayout(layouts, wave++);
        List<int[]> pick = AbyssLogic.pick(layout, avail, count, rng);
        int w = windup(p, p.dbl("warn_time", 2.5));
        String model = p.str("fx", "telegraph_tile");
        for (int[] t : pick) {
            int k = grid.indexOf(t[0], t[1]);
            if (k < 0) continue;
            grid.warn(k, now + w);
            Location corner = tileCorner(k);
            Location mid = at(grid.centerX(k), grid.centerZ(k)).add(0, 0.1, 0);
            Telegraph tg = telegraph(Telegraph.Shape.tile(corner, tileSize), w, Telegraph.PURPLE, model, null);
            tg.onTick(x -> {
                if (x.elapsed() % 5 == 0) world.spawnParticle(Particle.BLOCK, mid, 4, tileSize * 0.3, 0.05, tileSize * 0.3, 0, CRACK);
            });
            warnings.put(k, tg);
        }
        BossFx.sound(center, Sound.BLOCK_SCULK_CATALYST_BLOOM, 2f, 0.5f);
        BossFx.sound(center, Sound.BLOCK_DEEPSLATE_BREAK, 1.6f, 0.5f);
        rig.play(BossAnim.CAST, 24, now);
        if (wave <= 1 || rng.nextInt(4) == 0) broadcastBar("<dark_purple>…바닥이 숨을 들이쉰다.</dark_purple>");
    }

    private Location tileCorner(int k) {
        int h = tileSize / 2;
        return new Location(world, cx + grid.centerX(k) - h, floorY, cz + grid.centerZ(k) - h);
    }

    private void tickTiles() {
        List<List<Integer>> due = grid.due(now);
        long regen = ticks(def.pattern("abyssal_collapse").dbl("regen_time", 15));
        for (int k : due.get(0)) collapseTile(k, stage == Stage.CHAMBER ? now + regen : Long.MAX_VALUE, true);
        if (stage == Stage.CHAMBER) for (int k : due.get(1)) restoreTile(k);
    }

    /** 타일이 무너진다: 블록 → 공기 (+ 떨어지는 블록 연출), 블록을 못 놓으면 검은 구멍 표시만. */
    private void collapseTile(int k, long restoreAt, boolean fancy) {
        grid.collapse(k, restoreAt);
        Telegraph tg = warnings.remove(k);
        if (tg != null) tg.cancel();
        int h = tileSize / 2;
        int bx0 = cx + grid.centerX(k), bz0 = cz + grid.centerZ(k);
        Location corner = tileCorner(k);
        Location mid = at(grid.centerX(k), grid.centerZ(k));
        if (realBlocks) {
            BlockData look = world.getBlockAt(bx0, fy, bz0).getBlockData();
            List<Block> removed = fallenBlocks.computeIfAbsent(k, x -> new ArrayList<>());
            int before = removed.size();
            for (int a = -h; a <= h; a++) {
                for (int b = -h; b <= h; b++) clearColumn(world.getBlockAt(bx0 + a, fy, bz0 + b), removed);
            }
            if (fancy && removed.size() > before && look.getMaterial().isSolid()) dropDisplay(look, corner.clone().add(0, -1, 0));
        } else if (!holeMarks.containsKey(k)) {
            BlockDisplay d = fx.block(corner.clone().add(0, 0.01, 0), Material.BLACK_CONCRETE.createBlockData(), tileSize, 0.03f, tileSize);
            if (d != null) holeMarks.put(k, d);
        }
        if (fancy) {
            world.spawnParticle(Particle.BLOCK, mid.clone().add(0, 0.3, 0), 12, tileSize * 0.3, 0.2, tileSize * 0.3, 0, CRACK);
            BossFx.particle(Particle.SQUID_INK, mid.clone().add(0, 0.2, 0), 4, tileSize * 0.3, 0.1, tileSize * 0.3, 0.02);
            if (k % 3 == 0) BossFx.sound(mid, Sound.BLOCK_DEEPSLATE_BREAK, 1.0f, 0.5f + rng.nextFloat() * 0.3f);
        }
    }

    /** 무너진 바닥 블록이 아래로 떨어지는 연출 (블록 디스플레이 하나, 1초 뒤 사라짐). */
    private void dropDisplay(BlockData look, Location corner) {
        BlockDisplay d = fx.block(corner, look, tileSize, 1f, tileSize);
        if (d == null) return;
        afterPersistent(1, () -> {
            if (!d.isValid()) return;
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(18);
            d.setTransformation(new Transformation(new Vector3f(0, -9f, 0), new Quaternionf().rotateY((float) (rng.nextDouble() - 0.5)),
                    new Vector3f(tileSize * 0.9f, 0.9f, tileSize * 0.9f), new Quaternionf()));
        });
        afterPersistent(20, () -> fx.discard(d));
    }

    private void restoreTile(int k) {
        grid.restore(k);
        List<Block> bs = fallenBlocks.remove(k);
        if (bs != null) for (Block b : bs) restoreBlock(b);
        BlockDisplay d = holeMarks.remove(k);
        if (d != null) fx.discard(d);
        Location mid = at(grid.centerX(k), grid.centerZ(k)).add(0, 0.2, 0);
        BossFx.particle(Particle.REVERSE_PORTAL, mid, 10, tileSize * 0.3, 0.2, tileSize * 0.3, 0.05);
        if (k % 4 == 0) BossFx.sound(mid, Sound.BLOCK_SCULK_SPREAD, 0.8f, 0.6f);
    }

    // ── 떨어짐 ───────────────────────────────────────────────────────────

    /** 떨어질 수 있는 사람: 인스턴스면 파티원 전원(쓰러진 사람도 끌어올린다), 관리자 소환이면 판정 대상. */
    private List<Player> fallCandidates() {
        if (adhoc) return players();
        List<Player> out = new ArrayList<>();
        for (Player p : ctx.onlineMembers()) {
            if (p.getWorld() != world || p.isDead()) continue;
            if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) continue;
            out.add(p);
        }
        return out;
    }

    private void tickFalls() {
        for (Player p : fallCandidates()) {
            Long last = fellAt.get(p.getUniqueId());
            if (last != null && now - last < 15) continue;
            Location l = p.getLocation();
            int dx = ox(l), dz = oz(l);
            if (!geo.inBattle(dx, dz, 3)) continue;
            boolean fell = l.getY() < floorY - 1.5 && l.getY() > floorY - 48;
            // 블록을 못 바꾼 곳: 바닥 높이에 서 있는데(점프 중 아님) 그 칸이 구멍이면 떨어진 것으로
            if (!fell && !realBlocks && Math.abs(l.getY() - floorY) < 0.2) fell = simulatedHole(dx, dz);
            if (fell) fall(p);
        }
    }

    /** 블록을 못 바꾼 곳의 "떨어지는 칸". */
    private boolean simulatedHole(int dx, int dz) {
        if (geo.inCorridor(dx, dz)) return stage != Stage.CHAMBER && AbyssLogic.Geometry.inGap(dz, gaps, gapLen);
        if (geo.inChamber(dx, dz)) return grid.hole(grid.tileAtBlock(dx, dz));
        if (geo.inMoat(dx, dz)) return !geo.inBridge(dx, dz) || bridgeDown;
        return false;
    }

    private void fall(Player p) {
        fellAt.put(p.getUniqueId(), now);
        Params pc = def.pattern("abyssal_collapse");
        Location from = p.getLocation();
        Location to = safeSpot(from);
        p.setFallDistance(0);
        p.setVelocity(new Vector(0, 0, 0));
        p.teleport(to);
        if (!downed(p)) {
            hitPct(p, pc.dbl("fall_damage_pct", 0.25), "abyss_fall");
            effect(p, "vulnerable", pc.dbl("fall_mark_duration", 3), pc.dbl("fall_mark_vulnerable", 0.2));
        }
        BossFx.particle(Particle.REVERSE_PORTAL, to.clone().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.1);
        BossFx.particle(Particle.SQUID_INK, to.clone().add(0, 0.5, 0), 8, 0.3, 0.3, 0.3, 0.02);
        BossFx.sound(to, Sound.ENTITY_ENDERMAN_TELEPORT, 1f, 0.5f);
        BossFx.sound(to, Sound.ENTITY_WARDEN_HEARTBEAT, 1.2f, 0.8f);
        notify(p, "<dark_purple>…심연이 너를 뱉어 낸다.</dark_purple>");
    }

    /** 가장 가까운 안전한 칸: 심장실 = 멀쩡한 타일, 추격 = 해일 앞 회랑, 가장자리 = 단 안쪽. */
    private Location safeSpot(Location l) {
        double dx = l.getX() - (cx + 0.5), dz = l.getZ() - (cz + 0.5);
        Location out;
        switch (stage) {
            case CHAMBER -> {
                int k = grid.nearestSolid(dx, dz);
                out = k >= 0 ? at(grid.centerX(k), grid.centerZ(k)) : at(0, -tileSize * 2);
            }
            case PURSUIT -> {
                int z = AbyssLogic.pursuitSafeZ((int) Math.floor(dz + 0.5), wallZ, geo, gaps, gapLen);
                double x = Math.max(-geo.half() + 0.5, Math.min(geo.half() - 0.5, dx));
                out = z >= geo.uEnd() ? at(0, geo.rimU() - geo.rimR() + 2) : at(x, z);
            }
            default -> out = rimInside(dx, dz - geo.rimU(), geo.rimR() - 1.5);
        }
        out.setYaw(l.getYaw());
        out.setPitch(l.getPitch());
        return out;
    }

    /** 가장자리 단 중심 기준 (rx, rz) 방향으로 maxR 안쪽 지점. */
    private Location rimInside(double rx, double rz, double maxR) {
        double d = Math.hypot(rx, rz);
        if (d < 1e-3) {
            rx = 0;
            rz = -1;
            d = 1;
        }
        double k = Math.min(d, maxR) / d;
        return at(rx * k, geo.rimU() + rz * k);
    }

    /** 가장자리 단 위 무작위 지점 (반경 maxR 안, 면적 균등). */
    private Location rimPoint(double maxR) {
        double a = rng.nextDouble() * Math.PI * 2, r = Math.sqrt(rng.nextDouble()) * maxR;
        return at(Math.cos(a) * r, geo.rimU() + Math.sin(a) * r);
    }

    // ── ② 심연의 추격 (2페이즈 진입) ─────────────────────────────────────

    private void startPursuit() {
        if (stage != Stage.CHAMBER) return;
        stage = Stage.PURSUIT;
        Params p = def.pattern("devouring_pursuit");
        setUntargetable(true);
        // 진행 중이던 붕괴 정리: 금 간 칸은 되살리고 이미 무너진 칸은 그대로(해일이 마저 삼킨다)
        for (Telegraph tg : warnings.values()) tg.cancel();
        warnings.clear();
        for (int k = 0; k < grid.count(); k++) {
            if (grid.state(k) == AbyssLogic.State.WARN) grid.restore(k);
            else if (grid.state(k) == AbyssLogic.State.FALLEN) grid.collapse(k, Long.MAX_VALUE);
        }
        // 회랑 입구의 막이 찢어진다
        for (Block b : membrane) {
            Location l = b.getLocation().add(0.5, 0.5, 0.5);
            restoreBlock(b);
            if (rng.nextInt(3) == 0) BossFx.particle(Particle.SCULK_SOUL, l, 2, 0.3, 0.3, 0.3, 0.02);
        }
        membrane.clear();
        // 회랑 틈
        if (realBlocks) {
            for (int s : gaps) {
                for (int dz = s; dz < s + gapLen; dz++) {
                    for (int dx = -geo.half(); dx <= geo.half(); dx++) clearColumn(world.getBlockAt(cx + dx, fy, cz + dz), null);
                }
            }
        }
        // 심장이 가라앉아 회랑 끝 가장자리에서 다시 떠오른다
        Location old = entity.getLocation();
        BossFx.particle(Particle.SQUID_INK, old.clone().add(0, 1.5, 0), 80, 1.2, 1.5, 1.2, 0.1);
        BossFx.particle(Particle.SCULK_SOUL, old.clone().add(0, 1.5, 0), 40, 1.2, 1.5, 1.2, 0.05);
        BossFx.sound(old, Sound.ENTITY_WARDEN_DIG, 2f, 0.6f);
        relocate(at(0, geo.rimU()));
        if (!realBlocks && !entity.getLocation().clone().add(0, -0.5, 0).getBlock().getType().isSolid()) entity.setGravity(false);
        BossFx.particle(Particle.SCULK_SOUL, entity.getLocation().add(0, 1.5, 0), 40, 1.2, 1.5, 1.2, 0.05);

        pursuitStart = now;
        wallRunning = false;
        wallStart = -geo.r() - 2;
        wallZ = wallStart;
        wallSpeed = p.dbl("wall_speed", 4.6) * scaling().speedMult();
        wallAccel = p.dbl("wall_accel", 0.05);
        int total = Math.max(0, (int) Math.round(p.scaled("debris", partySize(), 6)));
        debrisLeft = total;
        debrisStep = (geo.uEnd() - wallStart) / (total + 1.0);
        nextDebris = wallStart + debrisStep;
        wallHitAt.clear();
        busyFor(ticks(p.dbl("start_delay", 3)) + ticks(60));
        BossFx.sound(center, Sound.ENTITY_WARDEN_ROAR, 3f, 0.5f);
        for (Player pl : players()) {
            pl.playSound(pl.getLocation(), Sound.ENTITY_WARDEN_ROAR, 1.4f, 0.5f);
            pl.playSound(pl.getLocation(), Sound.BLOCK_SCULK_SHRIEKER_SHRIEK, 1.2f, 0.6f);
        }
        broadcastBar("<dark_aqua><b>…쿵.</b></dark_aqua> <gray>심장이 가라앉는다. 등 뒤가 차오른다.</gray>");
    }

    private void tickPursuit() {
        Params p = def.pattern("devouring_pursuit");
        long t = now - pursuitStart;
        int delay = ticks(p.dbl("start_delay", 3));
        List<Player> ps = players();
        if (t >= 10 && allOnRim(ps)) {
            endPursuit();
            return;
        }
        if (t > delay + ticks(70)) {
            endPursuit();
            return;
        }
        if (t < delay) {
            if (t % 4 == 0) timerBar("<dark_aqua>…</dark_aqua>", 1f - t / (float) delay, BossBar.Color.BLUE);
            if (t % 20 == 0) {
                for (Player pl : ps) pl.playSound(pl.getLocation(), Sound.ENTITY_WARDEN_HEARTBEAT, 2f, 0.6f + t / (float) delay * 0.4f);
            }
            if (t % 3 == 0) {
                Location l = at(rng.nextDouble() * geo.r() * 1.6 - geo.r() * 0.8, -geo.r() + 1).add(0, 1 + rng.nextDouble() * 5, 0);
                BossFx.particle(Particle.SQUID_INK, l, 6, 1.5, 1.0, 0.3, 0.03);
            }
            return;
        }
        if (!wallRunning) startWall(p);
        wallZ = AbyssLogic.wallPos(wallStart, wallSpeed, wallAccel, (t - delay) / 20.0);
        moveWall();
        // 심장실이 해일에 삼켜진다 (앞 6칸은 금이 간다)
        for (int k = 0; k < grid.count(); k++) {
            AbyssLogic.State s = grid.state(k);
            if (s == AbyssLogic.State.GONE) continue;
            if (grid.centerZ(k) <= wallZ + 1) collapseTile(k, Long.MAX_VALUE, k % 2 == 0);
            else if (s == AbyssLogic.State.SOLID && grid.centerZ(k) <= wallZ + 6 && now % 4 == 0) {
                world.spawnParticle(Particle.BLOCK, at(grid.centerX(k), grid.centerZ(k)).add(0, 0.2, 0), 3, 1, 0.05, 1, 0, CRACK);
            }
        }
        // 해일에 닿은 사람: 초당 최대 HP 50% + 앞으로 밀침 (0.5초마다 절반씩)
        double pct = p.dbl("wall_damage_pct", 0.5) / 2;
        double pushS = p.dbl("wall_push", 1.2);
        for (Player pl : ps) {
            double dz = pl.getLocation().getZ() - (cz + 0.5);
            if (!AbyssLogic.wallTouches(dz, wallZ)) continue;
            Long h = wallHitAt.get(pl.getUniqueId());
            if (h != null && now - h < 10) continue;
            wallHitAt.put(pl.getUniqueId(), now);
            hitPct(pl, pct, "devouring_pursuit");
            push(pl, new Vector(0, 0, 1), pushS, 0.35);
            BossFx.particle(Particle.SQUID_INK, pl.getLocation().add(0, 1, 0), 12, 0.4, 0.6, 0.4, 0.05);
            pl.playSound(pl.getLocation(), Sound.ENTITY_WARDEN_ATTACK_IMPACT, 1f, 0.5f);
        }
        // 낙석
        while (debrisLeft > 0 && wallZ >= nextDebris) {
            debrisLeft--;
            nextDebris += debrisStep;
            debris(p, ps);
        }
        // 틈 가장자리 (보라 = 기믹)
        if (now % 10 == 0) {
            for (int s : gaps) {
                if (s < wallZ) continue;
                BossFx.dustLine(at(-geo.half(), s - 0.5).add(0, 0.15, 0), at(geo.half(), s - 0.5).add(0, 0.15, 0), Telegraph.PURPLE, 1.2f, 0.5);
                BossFx.dustLine(at(-geo.half(), s + gapLen - 0.5).add(0, 0.15, 0), at(geo.half(), s + gapLen - 0.5).add(0, 0.15, 0),
                        Telegraph.PURPLE, 1.2f, 0.5);
            }
        }
        if (now % 4 == 0) {
            float prog = (float) ((wallZ - wallStart) / Math.max(1, geo.uEnd() - wallStart));
            timerBar("<dark_aqua>심연의 해일</dark_aqua>", prog, BossBar.Color.BLUE);
        }
        if (wallZ >= geo.uEnd() + 1) endPursuit();
    }

    private boolean allOnRim(List<Player> ps) {
        for (Player pl : ps) {
            Location l = pl.getLocation();
            if (!geo.onRim(ox(l), oz(l))) return false;
        }
        return true;
    }

    private void startWall(Params p) {
        wallRunning = true;
        String model = p.str("fx_wall", "abyss_wall");
        float sc = 3.4f;
        double h = fx.size(model, 3.0)[1] * sc;
        for (int xo = -16; xo <= 16; xo += 8) {
            Location l = at(xo, wallZ).add(0, h / 2 - 0.3, 0);
            ItemDisplay d = fx.model(model, l, sc, Display.Billboard.FIXED);
            if (d == null) continue;
            d.setBrightness(new Display.Brightness(15, 15));
            fx.orient(d, new Vector(0, 0, 1), sc, 1.2f, 0);
            wallFx.add(d);
        }
        BossFx.sound(at(0, wallZ), Sound.ENTITY_WARDEN_SONIC_BOOM, 3f, 0.4f);
        for (Player pl : players()) pl.playSound(pl.getLocation(), Sound.AMBIENT_UNDERWATER_ENTER, 1.6f, 0.5f);
    }

    private void moveWall() {
        double h = 3.4 * 1.5 - 0.3;
        int i = 0;
        for (int xo = -16; xo <= 16 && i < wallFx.size(); xo += 8, i++) {
            ItemDisplay d = wallFx.get(i);
            if (d.isValid()) d.teleport(at(xo, wallZ).add(0, h, 0));
        }
        if (now % 2 == 0) {
            boolean inChamber = wallZ < geo.uStart();
            double half = inChamber ? Math.sqrt(Math.max(0, geo.r() * geo.r() - wallZ * wallZ)) : geo.half() + 0.5;
            for (int k = 0; k < 6; k++) {
                Location l = at((rng.nextDouble() * 2 - 1) * half, wallZ + 0.4).add(0, rng.nextDouble() * 6, 0);
                BossFx.particle(Particle.SQUID_INK, l, 2, 0.3, 0.3, 0.1, 0.02);
                BossFx.dust(l, ABYSS, 1.6f, 1, 0.2);
            }
        }
        if (now % 20 == 0) BossFx.sound(at(0, wallZ), Sound.ENTITY_RAVAGER_ROAR, 2.4f, 0.4f);
    }

    /** 회랑 낙석: 앞서 달리는 누군가의 앞길에 원 r2 (천장에서 바위가 떨어진다). */
    private void debris(Params p, List<Player> ps) {
        List<Player> ahead = new ArrayList<>();
        for (Player pl : ps) if (pl.getLocation().getZ() - (cz + 0.5) > wallZ + 3) ahead.add(pl);
        double z;
        if (!ahead.isEmpty()) z = ahead.get(rng.nextInt(ahead.size())).getLocation().getZ() - (cz + 0.5) + 3 + rng.nextDouble() * 5;
        else z = wallZ + 8 + rng.nextDouble() * 12;
        z = Math.max(geo.uStart() + 1, Math.min(geo.uEnd() - 1, z));
        double x = (rng.nextDouble() * 2 - 1) * (geo.half() - 0.5);
        Location spot = at(x, z);
        double r = p.dbl("debris_radius", 2);
        int w = windupSec(1.0);
        double dmg = dmg(p, "debris_damage", 1.0);
        Telegraph.Shape c = Telegraph.Shape.circle(spot, r);
        BlockDisplay rock = fx.block(spot.clone().add(-0.6, 8, -0.6), Material.COBBLED_DEEPSLATE.createBlockData(), 1.2f, 1.2f, 1.2f);
        if (rock != null) {
            afterPersistent(1, () -> {
                if (!rock.isValid()) return;
                rock.setInterpolationDelay(0);
                rock.setInterpolationDuration(Math.max(1, w - 1));
                rock.setTransformation(new Transformation(new Vector3f(0, -8f, 0), new Quaternionf().rotateXYZ(0.6f, 0.4f, 0.3f),
                        new Vector3f(1.2f, 1.2f, 1.2f), new Quaternionf()));
            });
        }
        telegraph(c, w, Telegraph.RED, null, () -> {
            if (rock != null) fx.discard(rock);
            hitShape(c, dmg, "devouring_pursuit_debris", DamageType.MELEE, null);
            world.spawnParticle(Particle.BLOCK, spot.clone().add(0, 0.5, 0), 30, r * 0.4, 0.3, r * 0.4, 0, CRACK);
            BossFx.particle(Particle.EXPLOSION, spot.clone().add(0, 0.5, 0), 1, 0, 0, 0, 0);
            BossFx.sound(spot, Sound.BLOCK_DEEPSLATE_BREAK, 1.6f, 0.5f);
            BossFx.sound(spot, Sound.ENTITY_GENERIC_EXPLODE, 0.6f, 0.8f);
        });
        afterPersistent(w + 4, () -> {
            if (rock != null) fx.discard(rock);
        });
    }

    private void endPursuit() {
        if (stage != Stage.PURSUIT) return;
        stage = Stage.RIM;
        wallRunning = false;
        for (ItemDisplay d : wallFx) fx.discard(d);
        wallFx.clear();
        wallHitAt.clear();
        hideTimerBar();
        // 심장실은 남김없이 심연으로
        int bulk = 0;
        for (int k = 0; k < grid.count(); k++) {
            if (grid.state(k) == AbyssLogic.State.GONE) continue;
            collapseTile(k, Long.MAX_VALUE, bulk++ % 4 == 0);
        }
        // 회랑·심장실에 남은 사람(쓰러졌거나 뒤처진)은 가장자리로 끌어올린다
        for (Player m : fallCandidates()) {
            Location l = m.getLocation();
            int dx = ox(l), dz = oz(l);
            if (!geo.inBattle(dx, dz, 3) || dz >= geo.uEnd() - 2) continue;
            Location to = at(0, geo.rimU() - geo.rimR() + 2);
            to.setYaw(l.getYaw());
            m.setFallDistance(0);
            m.teleport(to);
            BossFx.particle(Particle.REVERSE_PORTAL, to.clone().add(0, 1, 0), 20, 0.4, 0.8, 0.4, 0.1);
        }
        // 다리는 2초 뒤 무너진다
        for (Block b : bridge) {
            world.spawnParticle(Particle.BLOCK, b.getLocation().add(0.5, 1.1, 0.5), 2, 0.3, 0.05, 0.3, 0, CRACK);
        }
        afterPersistent(40, this::dropBridge);
        setUntargetable(false);
        invulnerableFor(20);
        releaseBusy();
        rig.play(BossAnim.ROAR, 30, now);
        BossFx.sound(center, Sound.ENTITY_WARDEN_ROAR, 2.4f, 0.6f);
        BossFx.sound(center, Sound.ENTITY_WARDEN_HEARTBEAT, 3f, 0.5f);
        BossFx.dustRing(feet(), geo.rimR() - 0.5, VOID, 1.8f, 72);
        broadcastBar("<dark_aqua><b>…쿵.</b></dark_aqua> <gray>더는 물러설 곳이 없다.</gray>");
    }

    private void dropBridge() {
        if (bridgeDown) return;
        bridgeDown = true;
        for (Block b : bridge) {
            Location l = b.getLocation().add(0.5, 1, 0.5);
            clearColumn(b, null);
            if (rng.nextInt(3) == 0) world.spawnParticle(Particle.BLOCK, l, 6, 0.3, 0.2, 0.3, 0, CRACK);
        }
        if (!bridge.isEmpty()) BossFx.sound(bridge.get(0).getLocation(), Sound.BLOCK_DEEPSLATE_BREAK, 2f, 0.4f);
    }

    // ── 회전 응시 ────────────────────────────────────────────────────────

    private int rotatingGaze() {
        Params p = def.pattern("rotating_gaze");
        if (target() == null) return 0;
        int beams = Math.max(1, (int) Math.round(p.phased("beams", phase(), 2)));
        double len = p.dbl("length", 16), width = p.dbl("width", 1.5);
        double speed = p.dbl("rotation_speed", 30) * scaling().speedMult();
        int dur = ticks(p.dbl("duration", 8));
        int period = Math.max(1, ticks(p.dbl("tick", 0.25)));
        double dmg = dmg(p, "damage_per_tick", 0.5);
        int w = windup(p, 2.0);
        int dir = rng.nextBoolean() ? 1 : -1;
        double start = rng.nextDouble() * 360;
        String model = p.str("fx", "telegraph_line");
        Location origin = feet();
        List<ItemDisplay> plates = new ArrayList<>();
        for (int k = 0; k < beams; k++) {
            double ang = AbyssLogic.beamAngle(start, k, beams, speed, 0, dir);
            plates.add(fx.plate(beamShape(origin, ang, len, width), model));
        }
        gazeActive = true;
        run(new Mechanics.Repeat(w + dur, 1, tt -> {
            // 경고 중에도 같은 방향으로 아주 천천히 돈다 (방향 단서)
            double secs = Math.min(tt, w) / 20.0 * 0.15 + Math.max(0, tt - w) / 20.0;
            boolean live = tt >= w;
            for (int k = 0; k < beams; k++) {
                double ang = AbyssLogic.beamAngle(start, k, beams, speed, secs, dir);
                Telegraph.Shape s = beamShape(origin, ang, len, width);
                if (k < plates.size()) fx.movePlate(plates.get(k), s);
                if (tt % 2 == 0) {
                    Location a = origin.clone().add(0, live ? 1.1 : 0.2, 0);
                    Location b = a.clone().add(BossMath.ax(ang) * len, 0, BossMath.az(ang) * len);
                    BossFx.dustLine(a, b, live ? VOID : Telegraph.RED, live ? 1.6f : 1.0f, live ? 0.6 : 1.2);
                }
            }
            if (tt == w) {
                BossFx.sound(origin, Sound.BLOCK_BEACON_ACTIVATE, 2f, 0.5f);
                BossFx.sound(origin, Sound.ENTITY_WARDEN_SONIC_CHARGE, 2f, 0.6f);
            }
            if (live && (tt - w) % period == 0) {
                for (Player pl : players()) {
                    Location l = pl.getLocation();
                    for (int k = 0; k < beams; k++) {
                        double ang = AbyssLogic.beamAngle(start, k, beams, speed, secs, dir);
                        if (Math.abs(l.getY() - origin.getY()) <= 3 && AbyssLogic.inBeam(l.getX() - origin.getX(), l.getZ() - origin.getZ(), ang, len,
                                width)) {
                            hit(pl, dmg, "rotating_gaze", DamageType.MAGIC);
                            BossFx.particle(Particle.REVERSE_PORTAL, l.clone().add(0, 1, 0), 4, 0.2, 0.4, 0.2, 0.02);
                            break;
                        }
                    }
                }
            }
            return true;
        }, () -> {
            for (ItemDisplay d : plates) fx.discard(d);
            gazeActive = false;
        }, true));
        return cast("rotating_gaze", "회전 응시", w, w + 10, BossAnim.CAST, null, false);
    }

    private static Telegraph.Shape beamShape(Location origin, double angDeg, double len, double width) {
        return Telegraph.Shape.line(origin, new Vector(BossMath.ax(angDeg), 0, BossMath.az(angDeg)), len, width);
    }

    // ── 심연 균열 ────────────────────────────────────────────────────────

    private int abyssRift() {
        Params p = def.pattern("abyss_rift");
        int count = scaling().count(p, "count", 3, 0);
        double r = p.dbl("radius", 3);
        int w = windup(p, 1.6);
        double dmg = dmg(p, "damage", 1.6);
        int linger = ticks(p.dbl("linger", 4));
        double ld = dmg(p, "linger_dps", 0.3);
        List<Location> spots = new ArrayList<>();
        for (Player pl : pickTargets(count, null, false)) spots.add(ground(pl.getLocation()));
        while (spots.size() < count) spots.add(rimPoint(geo.rimR() - 2));
        if (spots.isEmpty()) return 0;
        for (Location s : spots) {
            Telegraph.Shape c = Telegraph.Shape.circle(s, r);
            telegraph(c, w, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "abyss_rift", DamageType.MAGIC, null);
                BossFx.particle(Particle.SQUID_INK, s.clone().add(0, 0.5, 0), 30, r * 0.4, 0.4, r * 0.4, 0.05);
                BossFx.particle(Particle.REVERSE_PORTAL, s.clone().add(0, 0.5, 0), 30, r * 0.4, 0.6, r * 0.4, 0.1);
                BossFx.sound(s, Sound.BLOCK_SCULK_SHRIEKER_BREAK, 1.4f, 0.5f);
                BossFx.sound(s, Sound.ENTITY_WARDEN_SONIC_BOOM, 0.5f, 1.2f);
                run(new Mechanics.Zone(fx, c, linger, 20, "telegraph_circle", VOID, Particle.REVERSE_PORTAL, this::players,
                        pl -> hit(pl, ld, "abyss_rift", DamageType.MAGIC)));
            });
        }
        return cast("abyss_rift", "심연 균열", w, w + 6, BossAnim.SLAM, null, false);
    }

    // ── 심장 박동 (3페이즈 소프트 엔레이지) ──────────────────────────────

    private void heartbeat() {
        Params p = def.pattern("heartbeat_pulse");
        int k = pulses++;
        double dmg = damage() * AbyssLogic.heartbeatMult(p.dbl("damage", 0.8), p.dbl("ramp", 0.15), k);
        rig.setGlow(HEART);
        for (int i = 0; i < 3; i++) {
            float vol = 1.2f + i * 0.6f;
            after(i * 10, () -> {
                for (Player pl : players()) pl.playSound(pl.getLocation(), Sound.ENTITY_WARDEN_HEARTBEAT, vol, 0.5f);
                BossFx.dustRing(feet().add(0, 0.3, 0), 2.5, HEART, 2f, 24);
            });
        }
        after(30, () -> {
            for (Player pl : players()) {
                hit(pl, dmg, "heartbeat_pulse", DamageType.MAGIC);
                pl.sendHurtAnimation(rng.nextFloat() * 360);
                pl.playSound(pl.getLocation(), Sound.ENTITY_WARDEN_SONIC_BOOM, 0.6f, 0.4f);
            }
            BossFx.sound(center, Sound.ENTITY_WARDEN_HEARTBEAT, 3f, 0.4f);
            BossFx.dustRing(feet().add(0, 0.3, 0), geo.rimR() * 0.8, HEART, 2f, 72);
            BossFx.particle(Particle.SCULK_SOUL, entity.getLocation().add(0, 1.5, 0), 30, 1.5, 1.2, 1.5, 0.08);
            rig.setGlow(enraged() ? ENRAGE : null);
            broadcastBar("<dark_red><b>" + "쿵. ".repeat(Math.min(5, k + 1)).trim() + "</b></dark_red>");
        });
    }

    // ── 지난 층의 메아리 (3페이즈) ───────────────────────────────────────

    private int floorEcho() {
        Params p = def.pattern("floor_echoes");
        String key = AbyssLogic.pickEcho(p.strings("pool"), lastEcho, rng);
        if (key == null) return 0;
        double power = p.dbl("power", 0.7), wm = p.dbl("windup_mult", 1.2);
        Params src = echoSource(key);
        int busy = switch (key) {
            case "rampage_charge" -> echoCharge(src, power, wm);
            case "spore_brand" -> echoSpores(src, power, wm);
            case "symbiosis_bloom" -> echoBloom(src, power, wm);
            case "tidal_sweep" -> echoTide(src, power, wm);
            case "forge_quake" -> echoQuake(src, power, wm);
            case "glacial_spikes" -> echoSpikes(src, power, wm);
            case "rewind_echo" -> echoRewind(src, power, wm);
            case "erasure" -> echoErasure(src, power, wm);
            default -> 0;
        };
        if (busy > 0) lastEcho = key;
        return busy;
    }

    /** 그 패턴을 가진 이전 층 보스의 수치 (없으면 빈 값 → 기본값). */
    private Params echoSource(String key) {
        for (BossDef d : services.content().bosses().values()) {
            if (d == def || d.floor() >= def.floor()) continue;
            Params p = d.patterns().get(key);
            if (p != null) return p;
        }
        return Params.EMPTY;
    }

    private void echoTint(Color c, int ticks) {
        rig.setGlow(c);
        afterPersistent(ticks, () -> rig.setGlow(enraged() ? ENRAGE : null));
    }

    private int echoWindup(Params src, double defSec, double wm) { return AbyssLogic.echoWindup(windup(src, defSec), wm); }

    /** 1층 돌진: 표식 대상에게 보스에서 뻗는 보라 화살표(대상을 따라 돈다) → 유령 돌진 + 밀침. 막아 줄 기둥은 없다. */
    private int echoCharge(Params src, double power, double wm) {
        Player t = randomTarget();
        if (t == null) return 0;
        int mark = AbyssLogic.echoWindup(windupSec(src.dbl("mark_time", 2.0)), wm);
        double width = src.dbl("width", 3), len = geo.rimR() + 3;
        double dmg = damage() * src.dbl("damage", 2.0) * power;
        double kb = src.dbl("knockback", 1.2) * power;
        run(new Mechanics.Marker(fx, "marker_target", t, mark, null));
        Telegraph[] ref = new Telegraph[1];
        ref[0] = telegraph(Telegraph.Shape.arrow(feet(), dirTo(t.getLocation()), len, width), mark, Telegraph.PURPLE, null, () -> {
            Telegraph.Shape s = ref[0].shape();
            Vector d = s.direction();
            hitShape(s, dmg, "floor_echoes", DamageType.MELEE, pl -> push(pl, d, kb, 0.35));
            for (double f = 0; f <= len; f += 1.0) {
                Location l = s.origin().clone().add(d.clone().multiply(f)).add(0, 1, 0);
                BossFx.dust(l, MOSS, 1.8f, 3, 0.5);
                BossFx.particle(Particle.CLOUD, l, 1, 0.3, 0.3, 0.3, 0.02);
            }
            BossFx.sound(entity.getLocation(), Sound.ENTITY_RAVAGER_ROAR, 1.6f, 0.8f);
            BossFx.sound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_KNOCKBACK, 1.4f, 0.6f);
        });
        ref[0].onTick(tg -> {
            if (validPlayer(t) && tg.elapsed() < tg.total() - 6) tg.reshape(Telegraph.Shape.arrow(feet(), dirTo(t.getLocation()), len, width));
        });
        echoTint(MOSS, mark + 10);
        broadcastBar("<#7fbf5a>…이끼 낀 발굽 소리가 땅을 울린다.</#7fbf5a>");
        return cast("floor_echoes", "메아리 — 돌진", mark, mark + 10, BossAnim.CHARGE, t.getLocation(), false);
    }

    /** 3층 포자 낙인(흩어지기): 낙인자 발밑 파란 원이 따라다니다 터진다. 겹친 사람도 맞고, 자리에 독 웅덩이. */
    private int echoSpores(Params src, double power, double wm) {
        int count = scaling().count(src, "count", 1, src.integer("max", 5));
        List<Player> ts = pickTargets(count, null, false);
        if (ts.isEmpty()) return 0;
        int dur = AbyssLogic.echoWindup(windupSec(src.dbl("duration", 5.0)), wm);
        double r = src.dbl("radius", 5);
        double dmg = damage() * src.dbl("damage", 1.6) * power;
        double patchR = src.dbl("patch_radius", 3), patchDmg = damage() * src.dbl("patch_damage", 0.2) * power;
        int patchDur = ticks(src.dbl("patch_duration", 10));
        for (Player t : ts) {
            run(new Mechanics.Marker(fx, src.str("fx", "marker_spread"), t, dur, null));
            Telegraph tg = new Telegraph(fx, Telegraph.Shape.circle(ground(t.getLocation()), r), dur, Telegraph.BLUE, "", null);
            tg.follow(t);
            run(tg);
            after(dur, () -> {
                if (!validPlayer(t)) return;
                Location at = ground(t.getLocation());
                hitShape(Telegraph.Shape.circle(at, r), dmg, "floor_echoes", DamageType.MAGIC, null);
                BossFx.particle(Particle.SPORE_BLOSSOM_AIR, at.clone().add(0, 1, 0), 60, r * 0.5, 0.8, r * 0.5, 0);
                BossFx.dust(at.clone().add(0, 1, 0), SPORE, 2f, 30, r * 0.4);
                BossFx.sound(at, Sound.ENTITY_GENERIC_EXPLODE, 1f, 1.3f);
                run(new Mechanics.Zone(fx, Telegraph.Shape.circle(at, patchR), patchDur, 20, "telegraph_circle", Telegraph.GREEN,
                        Particle.SPORE_BLOSSOM_AIR, this::players, pl -> {
                    hit(pl, patchDmg, "floor_echoes", DamageType.TRUE);
                    effect(pl, "poison", 2, 0);
                }));
            });
        }
        echoTint(SPORE, dur);
        broadcastBar("<#5a8cff>…포자가 누군가의 어깨에 내려앉는다.</#5a8cff>");
        return cast("floor_echoes", "메아리 — 포자 낙인", 20, 24, BossAnim.CAST, null, false);
    }

    /** 3층 공생의 꽃(모이기): 노란 원 안 인원수로 총 피해를 나눈다. */
    private int echoBloom(Params src, double power, double wm) {
        List<Player> pick = pickTargets(1, null, false);
        if (pick.isEmpty()) return 0;
        Player t = pick.get(0);
        int dur = AbyssLogic.echoWindup(windupSec(src.dbl("duration", 5.0)), wm);
        double r = src.dbl("radius", 3);
        run(new Mechanics.Marker(fx, src.str("fx", "marker_stack"), t, dur, null));
        Telegraph tg = new Telegraph(fx, Telegraph.Shape.circle(ground(t.getLocation()), r), dur, Telegraph.YELLOW, "", null);
        tg.follow(t);
        run(tg);
        after(dur, () -> {
            if (!validPlayer(t)) return;
            Location at = ground(t.getLocation());
            Telegraph.Shape bloom = Telegraph.Shape.circle(at, r);
            List<Player> inside = new ArrayList<>();
            for (Player pl : players()) if (bloom.contains(pl.getLocation())) inside.add(pl);
            double each;
            if (scaling().solo()) each = damage() * src.dbl("solo_damage", 1.4) * power;
            else {
                double total = damage() * (src.dbl("total_damage", 6.0) + src.dbl("total_per_member", 1.0) * (partySize() - 1)) * power;
                each = BossMath.shareDamage(total, inside.size(), src.integer("min_share", 1));
            }
            for (Player pl : inside) hit(pl, each, "floor_echoes", DamageType.MAGIC);
            BossFx.particle(Particle.FIREWORK, at.clone().add(0, 1, 0), 40, r * 0.5, 0.6, r * 0.5, 0.05);
            BossFx.dust(at.clone().add(0, 1, 0), BLOOM, 2f, 40, r * 0.4);
            BossFx.sound(at, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 2f, 0.6f);
        });
        echoTint(BLOOM, dur);
        broadcastBar("<yellow>…한 송이 꽃이 피어난다. 혼자 받기엔 무겁다.</yellow>");
        return cast("floor_echoes", "메아리 — 공생의 꽃", 20, 24, BossAnim.CAST, null, false);
    }

    /** 4층 해일 쓸기: 단 한쪽 끝에서 반대편까지 폭 4 직사각형 (대상을 지나는 무작위 방향) + 밀침. */
    private int echoTide(Params src, double power, double wm) {
        Player t = randomTarget();
        if (t == null) return 0;
        int w = echoWindup(src, 1.6, wm);
        double width = src.dbl("width", 4), len = geo.rimR() * 2 + 4;
        double dmg = damage() * src.dbl("damage", 1.6) * power;
        double kb = src.dbl("knockback", 1.0) * power;
        double ang = rng.nextDouble() * 360;
        Vector dir = new Vector(BossMath.ax(ang), 0, BossMath.az(ang));
        Location tl = ground(t.getLocation());
        double along = tl.toVector().subtract(center.toVector()).setY(0).dot(dir);
        Location origin = tl.clone().subtract(dir.clone().multiply(along + geo.rimR() + 2));
        origin.setY(tl.getY());
        Telegraph.Shape line = Telegraph.Shape.line(origin, dir, len, width);
        telegraph(line, w, Telegraph.RED, null, () -> {
            hitShape(line, dmg, "floor_echoes", DamageType.MAGIC, pl -> push(pl, dir, kb, 0.3));
            for (int i = 0; i < 10; i++) {
                double f = len * i / 10.0;
                Location l = origin.clone().add(dir.clone().multiply(f)).add(0, 0.6, 0);
                after(i, () -> {
                    BossFx.particle(Particle.SPLASH, l, 30, width * 0.4, 0.4, width * 0.4, 0.1);
                    BossFx.particle(Particle.BUBBLE_POP, l, 10, width * 0.4, 0.4, width * 0.4, 0.05);
                    BossFx.dust(l, WATER, 1.8f, 6, width * 0.3);
                });
            }
            BossFx.sound(origin, Sound.ENTITY_GENERIC_SPLASH, 2f, 0.5f);
            BossFx.sound(center, Sound.AMBIENT_UNDERWATER_EXIT, 1.6f, 0.6f);
        });
        echoTint(WATER, w + 10);
        broadcastBar("<#5ab4ff>…어디선가 물이 차오르는 소리.</#5ab4ff>");
        return cast("floor_echoes", "메아리 — 해일 쓸기", w, w + 8, BossAnim.SWEEP, null, false);
    }

    /**
     * 5층 단조 진동: 주황 링 → 단 전체 피해 + 보스 반대 방향 강한 넉백(가장자리 = 낭떠러지). 5층처럼 쇠사슬 말뚝이 잠깐 솟는다 —
     * 말뚝 2칸 안에서 웅크린 사람(말뚝당 2명)과 넉백 면역은 버틴다.
     */
    private int echoQuake(Params src, double power, double wm) {
        if (players().isEmpty()) return 0;
        int w = echoWindup(src, 2.0, wm);
        Location c = feet();
        Telegraph.Shape all = Telegraph.Shape.ring(c, 1.5, geo.rimR() + 1);
        double dmg = damage() * src.dbl("damage", 1.0) * power;
        double kb = src.dbl("knockback", 2.4) * power, up = src.dbl("vertical", 0.4);
        Params grip = echoSource("chain_grip");
        double gr = grip.dbl("grip_radius", 2.0);
        int perStake = grip.integer("max_grips_per_anchor", 2);
        String stakeFx = grip.str("fx", "chain_anchor");
        int n = AbyssLogic.echoStakes(partySize());
        double a0 = rng.nextDouble() * 360;
        List<Location> stakes = new ArrayList<>();
        List<ItemDisplay> stakeModels = new ArrayList<>();
        double sh = fx.size(stakeFx, 1.5)[1];
        for (int i = 0; i < n; i++) {
            double ang = a0 + 360.0 * i / n;
            Location s = at(BossMath.ax(ang) * geo.rimR() * 0.55, geo.rimU() + BossMath.az(ang) * geo.rimR() * 0.55);
            stakes.add(s);
            ItemDisplay d = fx.model(stakeFx, s.clone().add(0, sh / 2, 0), 1f, Display.Billboard.FIXED);
            if (d != null) stakeModels.add(d);
            BossFx.particle(Particle.SMOKE, s.clone().add(0, 0.5, 0), 10, 0.3, 0.4, 0.3, 0.02);
        }
        BossFx.sound(c, Sound.BLOCK_CHAIN_PLACE, 2f, 0.6f);
        run(new Mechanics.Repeat(w, 10, tt -> {
            for (Location s : stakes) BossFx.dustRing(s.clone().add(0, 0.15, 0), gr, FORGE, 1.0f, 16);
            return true;
        }, null, true));
        telegraph(all, w, Telegraph.ORANGE, null, () -> {
            anchored.clear();
            for (Location s : stakes) {
                int held = 0;
                for (Player pl : players()) {
                    if (held >= perStake || anchored.contains(pl.getUniqueId())) continue;
                    if (pl.isSneaking() && horizontal(pl.getLocation(), s) <= gr) {
                        anchored.add(pl.getUniqueId());
                        held++;
                        BossFx.dustLine(s.clone().add(0, 0.6, 0), pl.getLocation().add(0, 0.8, 0), Color.fromRGB(150, 150, 160), 1.0f, 0.3);
                    }
                }
            }
            for (Player pl : players()) {
                if (!all.contains(pl.getLocation())) continue;
                hit(pl, dmg, "floor_echoes", DamageType.MAGIC);
                push(pl, pl.getLocation().toVector().subtract(c.toVector()), kb, up);
            }
            anchored.clear();
            for (ItemDisplay d : stakeModels) afterPersistent(10, () -> fx.discard(d));
            BossFx.sound(c, Sound.BLOCK_ANVIL_LAND, 2f, 0.5f);
            BossFx.sound(c, Sound.ENTITY_GENERIC_EXPLODE, 1.4f, 0.6f);
            BossFx.ring(c.clone().add(0, 0.3, 0), geo.rimR() * 0.6, Particle.EXPLOSION, 12);
            BossFx.dustRing(c.clone().add(0, 0.3, 0), geo.rimR(), FORGE, 2f, 64);
        });
        afterPersistent(w + 40, () -> {
            for (ItemDisplay d : stakeModels) fx.discard(d);
        });
        echoTint(FORGE, w + 12);
        broadcastBar("<gold>…모루를 내려치는 소리가 가장자리를 흔든다. 어디선가 사슬이 운다.</gold>");
        return cast("floor_echoes", "메아리 — 단조 진동", w, w + 12, BossAnim.SLAM, null, false);
    }

    /** 6층 빙창: 보스→대상 선 폭 2 길이 16, 3갈래 35° (겹쳐도 한 번만 맞는다). */
    private int echoSpikes(Params src, double power, double wm) {
        Player t = randomTarget();
        if (t == null) return 0;
        int w = echoWindup(src, 1.2, wm);
        int count = Math.max(1, (int) Math.round(src.phased("count", 3, 1)));
        double spread = src.phased("spread", 3, 35);
        double len = src.dbl("length", 16), width = src.dbl("width", 2);
        double dmg = damage() * src.dbl("damage", 1.4) * power;
        Vector base = dirTo(t.getLocation());
        double baseAng = Math.toDegrees(Math.atan2(base.getZ(), base.getX()));
        Location origin = feet();
        List<Telegraph.Shape> lines = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            double off = (i - (count - 1) / 2.0) * spread;
            lines.add(beamShape(origin, baseAng + off, len, width));
        }
        for (int i = 0; i < lines.size(); i++) {
            boolean last = i == lines.size() - 1;
            telegraph(lines.get(i), w, Telegraph.RED, null, last ? () -> {
                Set<UUID> struck = new HashSet<>();
                for (Player pl : players()) {
                    for (Telegraph.Shape s : lines) {
                        if (s.contains(pl.getLocation()) && struck.add(pl.getUniqueId())) hit(pl, dmg, "floor_echoes", DamageType.MAGIC);
                    }
                }
                for (Telegraph.Shape s : lines) {
                    Vector d = s.direction();
                    for (double f = 1.5; f <= s.size(); f += 1.5) {
                        Location l = s.origin().clone().add(d.clone().multiply(f)).add(0, 0.5, 0);
                        BossFx.particle(Particle.SNOWFLAKE, l, 4, 0.3, 0.4, 0.3, 0.02);
                        BossFx.dust(l, ICE, 1.6f, 2, 0.3);
                    }
                }
                BossFx.sound(origin, Sound.BLOCK_GLASS_BREAK, 1.6f, 0.7f);
                BossFx.sound(origin, Sound.ITEM_TRIDENT_THROW, 1.6f, 0.6f);
            } : null);
        }
        echoTint(ICE, w + 8);
        broadcastBar("<#bfe6ff>…서늘한 숨결이 갈래를 친다.</#bfe6ff>");
        return cast("floor_echoes", "메아리 — 빙창", w, w + 8, BossAnim.THROW, t.getLocation(), false);
    }

    /** 9층 되감기 메아리: 지금 선 자리마다 원 r2.5 — 6초(×1.2) 뒤 그 자리가 터진다. */
    private int echoRewind(Params src, double power, double wm) {
        List<Player> ps = players();
        if (ps.isEmpty()) return 0;
        int delay = AbyssLogic.echoWindup(windupSec(src.dbl("delay", 6)), wm);
        double r = src.dbl("radius", 2.5);
        double dmg = damage() * src.dbl("damage", 1.2) * power;
        for (Player pl : ps) {
            Location spot = ground(pl.getLocation());
            Telegraph.Shape c = Telegraph.Shape.circle(spot, r);
            telegraph(c, delay, Telegraph.RED, src.str("fx", "telegraph_circle"), () -> {
                hitShape(c, dmg, "floor_echoes", DamageType.MAGIC, null);
                BossFx.particle(Particle.END_ROD, spot.clone().add(0, 0.6, 0), 20, r * 0.4, 0.4, r * 0.4, 0.05);
                BossFx.dust(spot.clone().add(0, 0.8, 0), CLOCK, 1.8f, 20, r * 0.4);
                BossFx.sound(spot, Sound.BLOCK_BELL_USE, 1.2f, 1.6f);
            });
        }
        run(new Mechanics.Repeat(delay, 10, tt -> {
            BossFx.sound(center, Sound.BLOCK_NOTE_BLOCK_HAT, 1.4f, tt % 20 == 0 ? 1.8f : 1.5f);
            return true;
        }, null, true));
        echoTint(CLOCK, delay);
        broadcastBar("<#e6c27a>…초침이 거꾸로 돈다. 방금 선 자리가 낯설다.</#e6c27a>");
        return cast("floor_echoes", "메아리 — 되감기", 20, 24, BossAnim.CAST, null, false);
    }

    /** 8층 지우기: 보스 앞 부채꼴 90°, 반경 16. */
    private int echoErasure(Params src, double power, double wm) {
        Player t = target();
        if (t == null) return 0;
        int w = echoWindup(src, 2.0, wm);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), src.dbl("angle", 90), src.dbl("radius", 16));
        double dmg = damage() * src.dbl("damage", 2.5) * power;
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "floor_echoes", DamageType.MAGIC, null);
            Vector d = cone.direction();
            for (double f = 2; f <= cone.size(); f += 2) {
                Location l = cone.origin().clone().add(d.clone().multiply(f)).add(0, 0.8, 0);
                BossFx.particle(Particle.SQUID_INK, l, (int) (f * 1.5), f * 0.35, 0.3, f * 0.35, 0.03);
            }
            BossFx.sound(entity.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 2f, 0.5f);
            BossFx.sound(entity.getLocation(), Sound.ENTITY_WARDEN_SONIC_BOOM, 0.8f, 0.7f);
        });
        echoTint(INK, w + 8);
        broadcastBar("<dark_gray>…누군가 이 페이지를 지우려 한다.</dark_gray>");
        return cast("floor_echoes", "메아리 — 지우기", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 정리 ─────────────────────────────────────────────────────────────

    @Override
    protected void onEnd() {
        for (Telegraph tg : warnings.values()) tg.cancel();
        warnings.clear();
        for (ItemDisplay d : wallFx) fx.discard(d);
        wallFx.clear();
        for (BlockDisplay d : holeMarks.values()) fx.discard(d);
        holeMarks.clear();
        fallenBlocks.clear();
        membrane.clear();
        bridge.clear();
        wallHitAt.clear();
        fellAt.clear();
        anchored.clear();
        hideTimerBar();
        if (world != null) {
            for (int[] t : tickets) {
                try {
                    world.removePluginChunkTicket(t[0], t[1], services.plugin());
                } catch (Throwable ignored) {
                    // 월드 언로드 중
                }
            }
        }
        tickets.clear();
    }
}
