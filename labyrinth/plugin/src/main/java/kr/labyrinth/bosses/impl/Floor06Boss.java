package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.BossReach;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.ObjectTarget;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Params;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 지하 6층 — 얼음관의 여제 시린 (GDD §7.6, core {@code shield_break_roles}).
 * 핵심: 빙결 껍질 — 2·3페이즈에 들어가는 순간 얼음 껍질(무적) + 12초(솔로 16초) 시전 "절대영도". 인장 링(반경 10)의 인장 3개를
 * 각자 맞는 피해 유형으로만 깰 수 있다(⚔ 붉은 = 근접, 🏹 초록 = 투사체, ✦ 보라 = 마법). 파티에 그 유형을 낼 직업이 없으면 그 인장은
 * 모든 피해를 받되 HP ×1.5, 솔로는 세 인장 모두 모든 피해 허용. 셋 다 깨면 껍질이 부서져 6초 기절 + 받는 피해 +30%,
 * 못 깨면 전원 9.0배. 껍질 중에는 2초마다 위협 1위에게 얼어붙은 응시(0.6배).
 * 패턴: scepter_sweep(부채꼴 80°) · glacial_spikes(선 폭 2 길이 16, 3페이즈 3갈래 35°) · frostbite(2초마다 1.5칸 미만 이동 = 서리 1중첩,
 * 5중첩 빙결 — 동료 4회 타격·사제 정화) · blizzard(10초 시야 입자 + 우박 원) · permafrost(3×3 타일 30% 얼음판 — 미끄러짐).
 * 대응 (GDD §8.6): 못 닿는 틈에서 맞으면 서리 걸음 — 대상 곁 설 자리에 서리 고리가 피고, 경고 뒤 그 자리로 순간이동하며
 * 서리 폭발(홀 휩쓸기 피해 + 동상 1중첩). 설 자리가 없으면 그 대상에게 빙창.
 * <p>
 * 영구 동토는 인스턴스 안에서는 실제 푸른 얼음 블록(바닐라 미끄러짐 그대로, 끝나면 복원)이고, 블록을 못 놓는 곳(관리자 소환)은
 * {@link FrostLogic#slide} 로 이동 관성을 흉내 낸다. 아레나 바닥의 원래 얼음은 전투 동안 눈·방해석으로 덮어 얼음판과 구별되게 한다.
 */
public final class Floor06Boss extends Boss {

    /** 하늘색 — 영구 동토 얼음판 (GDD §7.6). */
    private static final Color ICE = Color.fromRGB(120, 210, 255);
    private static final Color FROST = Color.fromRGB(191, 230, 255);
    private static final Set<Material> SLIPPERY = Set.of(Material.PACKED_ICE, Material.ICE, Material.BLUE_ICE, Material.FROSTED_ICE);

    // ── 동상 ──
    private final Map<UUID, Location> lastPos = new HashMap<>();
    private final Map<UUID, TextDisplay> frostLabels = new HashMap<>();
    private final Map<UUID, String> frostLabelText = new HashMap<>();
    private final Map<UUID, ItemDisplay> iceBlocks = new HashMap<>();

    // ── 빙결 껍질 ──
    private boolean shellActive;
    private ItemDisplay shellModel;
    private Location shellAnchor;
    private final List<ObjectTarget> sigils = new ArrayList<>();
    private int sigilsBroken;
    private int sigilTotal;
    private int shellTicks;

    // ── 눈보라 ──
    private boolean blizzardActive;

    // ── 영구 동토 (타일 격자) ──
    private static final class IceTile {
        final long key;
        final Location corner;
        ItemDisplay plate;
        final List<Block> blocks = new ArrayList<>();
        boolean simulated;
        boolean active;

        IceTile(long key, Location corner) {
            this.key = key;
            this.corner = corner;
        }
    }

    private double gridX, gridZ, tileSize;
    private int gridN;
    private final List<Long> validTiles = new ArrayList<>();
    private final Map<Long, IceTile> iceTiles = new LinkedHashMap<>();
    private final Map<UUID, double[]> slideVel = new HashMap<>();
    private final Map<UUID, Location> slidePos = new HashMap<>();
    /** 전투 시작 때 눈·방해석으로 덮은 바닥 → 덮은 블록 (얼음판이 녹으면 원래 얼음이 아니라 이걸로 되돌린다). */
    private final Map<Block, BlockData> thawed = new HashMap<>();

    public Floor06Boss(Init init) { super(init); }

    // ── 아레나 ───────────────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        Params pf = def.pattern("permafrost");
        tileSize = Math.max(2, Math.round(pf.dbl("tile_size", 3)));
        gridN = (int) Math.ceil(arenaRadius * 2 / tileSize);
        // 타일 모서리를 블록 경계에 맞춘다 (실제 얼음 블록과 판 표시가 겹치게)
        gridX = Math.floor(center.getX() - gridN * tileSize / 2.0);
        gridZ = Math.floor(center.getZ() - gridN * tileSize / 2.0);
        for (int i = 0; i < gridN; i++) {
            for (int j = 0; j < gridN; j++) {
                double cx = gridX + (i + 0.5) * tileSize, cz = gridZ + (j + 0.5) * tileSize;
                if (Math.hypot(cx - center.getX(), cz - center.getZ()) > arenaRadius - tileSize * 0.6) continue;
                if (tileTouchesStairs(i, j)) continue;
                validTiles.add(key(i, j));
            }
        }
        if (def.arena().bool("floor_thaw", true)) thawArenaFloor();
        nova(feet(), arenaRadius * 0.6, 14);
        BossFx.particle(Particle.SNOWFLAKE, center.clone().add(0, 2, 0), 120, arenaRadius * 0.5, 1.5, arenaRadius * 0.5, 0.02);
    }

    private static long key(int i, int j) { return ((long) i << 32) | (j & 0xffffffffL); }

    private boolean tileTouchesStairs(int i, int j) {
        for (double fx = 0.25; fx < 1; fx += 0.25) {
            for (double fz = 0.25; fz < 1; fz += 0.25) {
                double x = gridX + (i + fx) * tileSize - center.getX(), z = gridZ + (j + fz) * tileSize - center.getZ();
                if (BossMath.inStairZone(x, z, 2.5)) return true;
            }
        }
        return false;
    }

    /** 아레나 바닥의 원래 얼음(포장 얼음·푸른 얼음)을 눈·방해석으로 덮는다 → 영구 동토 얼음판만 미끄럽다. 끝나면 복원. */
    private void thawArenaFloor() {
        if (!canPlaceBlocks()) return;
        World w = center.getWorld();
        int y = center.getBlockY() - 1;
        int r = (int) Math.ceil(arenaRadius);
        List<BlockData> cover = List.of(Material.SNOW_BLOCK.createBlockData(), Material.CALCITE.createBlockData(),
                Material.POLISHED_DIORITE.createBlockData());
        BlockData accent = Material.CHISELED_QUARTZ_BLOCK.createBlockData();
        for (int dx = -r; dx <= r; dx++) {
            for (int dz = -r; dz <= r; dz++) {
                Block b = w.getBlockAt(center.getBlockX() + dx, y, center.getBlockZ() + dz);
                if (!SLIPPERY.contains(b.getType())) continue;
                if (horizontal(b.getLocation().add(0.5, 0, 0.5), center) > arenaRadius + 0.5) continue;
                if (BossMath.inStairZone(b.getX() + 0.5 - center.getX(), b.getZ() + 0.5 - center.getZ(), 2.5)) continue;
                BlockData d = b.getType() == Material.BLUE_ICE ? accent : cover.get(rng.nextInt(cover.size()));
                if (setBlock(b, d)) thawed.put(b, d);
            }
        }
    }

    // ── 매 틱 ────────────────────────────────────────────────────────────

    @Override
    protected void onTick() {
        if (now % 2 == 0) updateFrostDisplays();
        if (!iceTiles.isEmpty()) tickSlide();
        if (now % 10 == 0) {
            Location l = randomPoint(0, arenaRadius - 1).add(0, 2 + rng.nextDouble() * 4, 0);
            BossFx.particle(Particle.SNOWFLAKE, l, 3, 1.5, 1, 1.5, 0.01);
        }
        if (shellActive && now % 6 == 0 && shellAnchor != null) {
            BossFx.particle(Particle.END_ROD, shellAnchor, 2, 1.0, 1.4, 1.0, 0.01);
        }
    }

    @Override
    protected boolean canUse(String key) {
        if (shellActive) return false;
        return switch (key) {
            case "permafrost" -> iceTiles.isEmpty() && !validTiles.isEmpty();
            case "blizzard" -> !blizzardActive && !targets().isEmpty();
            default -> target() != null;
        };
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "scepter_sweep" -> scepterSweep();
            case "glacial_spikes" -> glacialSpikes();
            case "blizzard" -> blizzard();
            case "permafrost" -> permafrost();
            default -> 0;
        };
    }

    @Override
    protected void runInterval(String key) {
        if (key.equals("frostbite")) frostbite();
    }

    @Override
    protected void onPhase(int newPhase) {
        nova(feet(), arenaRadius, 16);
        BossFx.sound(center, Sound.BLOCK_POWDER_SNOW_BREAK, 2f, 0.5f);
        BossFx.particle(Particle.SNOWFLAKE, entity.getLocation().add(0, 2, 0), 160, 3, 2, 3, 0.15);
        Params p = def.pattern("glacier_shell");
        if (FrostLogic.triggersAt(p.list("trigger_phases"), newPhase)) startShell(p);
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    // ── 홀 휩쓸기 ────────────────────────────────────────────────────────

    private int scepterSweep() {
        Params p = def.pattern("scepter_sweep");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 0.8);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), p.dbl("angle", 80), p.dbl("length", 5));
        double dmg = dmg(p, "damage", 1.3);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "scepter_sweep", DamageType.MELEE, null);
            Location front = cone.origin().clone().add(cone.direction().multiply(2.5)).add(0, 1, 0);
            BossFx.sound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.4f, 0.6f);
            BossFx.sound(front, Sound.BLOCK_GLASS_BREAK, 0.8f, 1.5f);
            BossFx.particle(Particle.SWEEP_ATTACK, front, 3, 1.0, 0.2, 1.0, 0);
            BossFx.particle(Particle.SNOWFLAKE, front, 30, 1.6, 0.4, 1.6, 0.05);
        });
        return cast("scepter_sweep", "홀 휩쓸기", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 빙창 ─────────────────────────────────────────────────────────────

    private int glacialSpikes() {
        Params p = def.pattern("glacial_spikes");
        Player t = scaling().solo() || "threat".equals(p.str("target", "random")) ? target() : randomTarget();
        return t == null ? 0 : glacialSpikes(t);
    }

    private int glacialSpikes(Player t) {
        Params p = def.pattern("glacial_spikes");
        int w = windup(p, 1.2);
        int count = Math.max(1, (int) Math.round(p.phased("count", phase(), 1)));
        double spread = p.phased("spread", phase(), 35);
        double len = p.dbl("length", 16);
        double width = p.dbl("width", 2);
        double dmg = dmg(p, "damage", 1.4);
        Vector base = dirTo(t.getLocation());
        Location origin = feet();
        List<Telegraph.Shape> lines = new ArrayList<>();
        for (double off : FrostLogic.spreadOffsets(count, spread)) {
            double[] d = FrostLogic.rotate(base.getX(), base.getZ(), off);
            lines.add(Telegraph.Shape.line(origin, new Vector(d[0], 0, d[1]), len, width));
        }
        for (int i = 0; i < lines.size(); i++) {
            boolean last = i == lines.size() - 1;
            // 갈래가 보스 근처에서 겹쳐도 한 번만 맞는다 → 판정은 마지막 경고가 모든 갈래를 한꺼번에
            telegraph(lines.get(i), w, Telegraph.RED, null, last ? () -> fireSpikes(lines, dmg, p) : null);
        }
        if (count > 1) broadcastBar("<aqua>빙창 " + count + "갈래!</aqua> <gray>서릿발이 부챗살처럼 뻗는다…");
        return cast("glacial_spikes", "빙창", w, w + 8, BossAnim.THROW, t.getLocation(), false);
    }

    private void fireSpikes(List<Telegraph.Shape> lines, double dmg, Params p) {
        Set<UUID> struck = new HashSet<>();
        for (Player pl : players()) {
            for (Telegraph.Shape s : lines) {
                if (s.contains(pl.getLocation()) && struck.add(pl.getUniqueId())) {
                    hit(pl, dmg, "glacial_spikes", DamageType.MAGIC);
                    BossFx.particle(Particle.ITEM_SNOWBALL, pl.getLocation().add(0, 1, 0), 12, 0.3, 0.5, 0.3, 0.05);
                }
            }
        }
        String spike = p.str("fx_spike", "ice_spike");
        String shard = p.str("fx", "proj_frost_shard");
        float sc = 1.25f;
        double half = fx.size(spike, 1.5)[1] * sc / 2;
        for (Telegraph.Shape s : lines) {
            Vector d = s.direction();
            Location from = s.origin().clone().add(0, 1.0, 0);
            double speed = 1.6 * scaling().speedMult();
            int travel = Math.max(4, (int) Math.ceil(s.size() / speed));
            run(new Mechanics.Projectile(fx, shard, 2.2f, Mechanics.Projectile.straight(from, d, speed), travel, 0, false,
                    Particle.SNOWFLAKE, List::of, pl -> { }, null));
            int step = 0;
            for (double f = 1.5; f <= s.size(); f += 2.0, step++) {
                Location at = ground(s.origin().clone().add(d.clone().multiply(f)));
                at.setYaw(rng.nextFloat() * 360);
                int delay = step;
                after(delay, () -> {
                    ItemDisplay sp = fx.model(spike, at.clone().add(0, half - 0.15, 0), sc, Display.Billboard.FIXED);
                    BossFx.particle(Particle.SNOWFLAKE, at.clone().add(0, 0.4, 0), 6, 0.4, 0.3, 0.4, 0.04);
                    afterPersistent(16, () -> fx.discard(sp));
                });
            }
        }
        BossFx.sound(entity.getLocation(), Sound.ITEM_TRIDENT_THROW, 1.6f, 0.6f);
        BossFx.sound(entity.getLocation(), Sound.BLOCK_GLASS_BREAK, 1.4f, 0.7f);
    }

    // ── 대응: 서리 걸음 (GDD §8.6) ───────────────────────────────────────

    @Override
    protected boolean canAnswer(Player t) { return !shellActive; }

    @Override
    protected int answer(Answer a) {
        Player t = a.target();
        if (t == null || !t.isValid()) return 0;
        Location s = standSpot(t, ground(t.getLocation()), BossReach.Order.NEAR);
        if (s == null) {
            answerUses("glacial_spikes");
            return glacialSpikes(t);
        }
        return frostStep(t, s);
    }

    /**
     * 서리 걸음: 설 자리에 서리 고리(반경 = 자기 거리 + 0.4)가 빙창 경고 시간 동안 피고, 끝나면 여제가 그 자리로 순간이동(그새 막혔으면
     * 제자리) + 원 안 모두 홀 휩쓸기 피해(마법) + 동상 1중첩. 껍질 이동과 같은 결의 이동, 피해·경고 수치는 기존 패턴 그대로.
     */
    private int frostStep(Player t, Location spot) {
        Params sweep = def.pattern("scepter_sweep");
        Params spikes = def.pattern("glacial_spikes");
        Params bite = def.pattern("frostbite");
        int w = windup(spikes, 1.2);
        double r = reach() + 0.4;
        Location at = spot.clone();
        Telegraph.Shape c = Telegraph.Shape.circle(at, r);
        double dmg = dmg(sweep, "damage", 1.3);
        double decay = bite.dbl("stack_decay", 6.0);
        nova(at, r, w);
        notify(t, "<#bfe6ff>곁에서 서리가 피어난다…</#bfe6ff>");
        BossFx.sound(at, Sound.BLOCK_POWDER_SNOW_STEP, 1.6f, 0.5f);
        run(new Mechanics.Repeat(w, 4, tt -> {
            BossFx.particle(Particle.SNOWFLAKE, entity.getLocation().add(0, 1.4, 0), 6, 0.5, 0.9, 0.5, 0.02);
            return true;
        }, null, true));
        telegraph(c, w, Telegraph.RED, null, () -> {
            Location from = entity.getLocation();
            if (bodyFits(at)) {
                Location to = at.clone();
                Location tl = t.isValid() ? t.getLocation() : at;
                to.setYaw(BossMath.yawOf(tl.getX() - to.getX(), tl.getZ() - to.getZ()));
                to.setPitch(0);
                BossFx.particle(Particle.SNOWFLAKE, from.clone().add(0, 1.5, 0), 40, 0.6, 1.0, 0.6, 0.05);
                entity.teleport(to);
            }
            hitShape(c, dmg, "scepter_sweep", DamageType.MAGIC, pl -> effect(pl, "frost", decay, 1));
            BossFx.sound(at, Sound.BLOCK_GLASS_BREAK, 1.6f, 0.6f);
            BossFx.sound(at, Sound.ENTITY_PLAYER_HURT_FREEZE, 1.2f, 0.8f);
            BossFx.particle(Particle.SNOWFLAKE, at.clone().add(0, 1, 0), 80, r * 0.5, 0.6, r * 0.5, 0.08);
            BossFx.dustRing(at.clone().add(0, 0.3, 0), r, FROST, 1.6f, 36);
        });
        return cast("scepter_sweep", "서리 걸음", w, w + 10, BossAnim.CAST, t.getLocation(), false);
    }

    // ── 동상 (interval) ──────────────────────────────────────────────────

    private void frostbite() {
        Params p = def.pattern("frostbite");
        double threshold = p.dbl("move_threshold", 1.5);
        double decay = p.dbl("stack_decay", 6.0);
        int max = p.integer("max_stacks", 5);
        Set<UUID> seen = new HashSet<>();
        for (Player pl : players()) {
            UUID id = pl.getUniqueId();
            seen.add(id);
            Location here = pl.getLocation();
            if (services.effects().has(pl, "frozen")) {
                lastPos.remove(id); // 얼어 있는 동안은 쌓지 않고, 풀린 직후에도 바로 쌓이지 않게 기준점을 다시 잡는다
                continue;
            }
            Location prev = lastPos.put(id, here.clone());
            double moved = prev == null || prev.getWorld() != here.getWorld() ? Double.NaN : horizontal(prev, here);
            if (!FrostLogic.frostbiteStacks(moved, threshold)) continue;
            effect(pl, "frost", decay, 1);
            if (services.effects().has(pl, "frozen")) {
                lastPos.remove(id);
                broadcastBar("<#bfe6ff><b>❄ " + pl.getName() + " 빙결!</b></#bfe6ff> <gray>얼음 속에서 누군가의 두드림을 기다린다…");
                BossFx.sound(here, Sound.BLOCK_GLASS_PLACE, 1.4f, 0.6f);
            } else {
                int st = services.effects().stacks(pl, "frost");
                notify(pl, "<#bfe6ff>❄ 동상 " + st + "/" + max + "</#bfe6ff> <gray>— 발끝이 굳어 간다…");
                BossFx.sound(here, Sound.ENTITY_PLAYER_HURT_FREEZE, 0.7f, 1.2f);
            }
            BossFx.particle(Particle.SNOWFLAKE, here.clone().add(0, 1, 0), 10, 0.3, 0.6, 0.3, 0.02);
        }
        lastPos.keySet().retainAll(seen);
    }

    /** 머리 위 눈송이 중첩 수 + 빙결된 사람의 얼음 블록 (frostbite.fx = ice_block). */
    private void updateFrostDisplays() {
        int max = def.pattern("frostbite").integer("max_stacks", 5);
        String iceModel = def.pattern("frostbite").str("fx", "ice_block");
        Set<UUID> seen = new HashSet<>();
        for (Player pl : players()) {
            UUID id = pl.getUniqueId();
            seen.add(id);
            boolean frozen = services.effects().has(pl, "frozen");
            int st = services.effects().stacks(pl, "frost");
            String text = null;
            if (!services.effects().isStealthed(pl)) {
                if (frozen) text = "<#bfe6ff><b>❄ 빙결</b></#bfe6ff>\n<gray>쩡… 쩡…";
                else if (st > 0) text = "<#bfe6ff>" + "❄".repeat(Math.min(max, st)) + "</#bfe6ff><dark_gray>"
                        + "❄".repeat(Math.max(0, max - st)) + "</dark_gray>";
            }
            Location head = pl.getLocation().add(0, pl.getHeight() + 0.45, 0);
            TextDisplay label = frostLabels.get(id);
            if (text == null) {
                if (label != null) {
                    fx.discard(label);
                    frostLabels.remove(id);
                    frostLabelText.remove(id);
                }
            } else {
                if (label == null || !label.isValid()) {
                    label = fx.label(head, text, 0.8f);
                    frostLabels.put(id, label);
                    frostLabelText.put(id, text);
                } else {
                    head.setYaw(0);
                    head.setPitch(0);
                    label.teleport(head);
                    if (!text.equals(frostLabelText.get(id))) {
                        BossFx.text(label, text);
                        frostLabelText.put(id, text);
                    }
                }
            }
            ItemDisplay block = iceBlocks.get(id);
            if (frozen && (block == null || !block.isValid())) {
                double h = fx.size(iceModel, 2.0)[1] * 1.1;
                iceBlocks.put(id, fx.model(iceModel, pl.getLocation().add(0, h / 2 - 0.05, 0), 1.1f, Display.Billboard.FIXED));
            } else if (!frozen && block != null) {
                fx.discard(block);
                iceBlocks.remove(id);
                BossFx.particle(Particle.ITEM_SNOWBALL, pl.getLocation().add(0, 1, 0), 16, 0.4, 0.6, 0.4, 0.05);
            }
        }
        for (UUID id : new ArrayList<>(frostLabels.keySet())) {
            if (seen.contains(id)) continue;
            fx.discard(frostLabels.remove(id));
            frostLabelText.remove(id);
        }
        for (UUID id : new ArrayList<>(iceBlocks.keySet())) {
            if (!seen.contains(id)) fx.discard(iceBlocks.remove(id));
        }
    }

    // ── 빙결 껍질 (핵심, 페이즈 진입 트리거) ─────────────────────────────

    private void startShell(Params p) {
        if (shellActive) return;
        shellActive = true;
        sigilsBroken = 0;
        setPathing(false);
        setUntargetable(true);
        // 아레나 중앙으로 미끄러지듯 이동해 껍질에 싸인다
        Location old = entity.getLocation();
        Location to = center.clone();
        to.setYaw(old.getYaw());
        BossFx.particle(Particle.SNOWFLAKE, old.clone().add(0, 1.5, 0), 60, 0.8, 1.2, 0.8, 0.05);
        if (horizontal(old, to) > 0.5) entity.teleport(to);
        String shellFx = p.str("fx_shell", "ice_shell");
        float sc = (float) Math.max(1.0, def.scale() * 0.85);
        double h = fx.size(shellFx, 3.0)[1] * sc;
        shellModel = fx.model(shellFx, to.clone().add(0, h / 2 - 0.2, 0), sc, Display.Billboard.FIXED);
        if (shellModel != null) shellModel.setBrightness(new Display.Brightness(15, 15));
        shellAnchor = to.clone().add(0, h * 0.75, 0);

        // 인장 3개 (근접·원거리·마법) — 파티에 없는 역할의 인장은 모든 피해 허용 + HP ×1.5, 솔로는 전부 허용
        List<DamageType> types = FrostLogic.sigilTypes(p.strings("sigils"));
        Set<DamageType> present = partyTypes(p);
        boolean solo = scaling().solo();
        double ringR = Math.min(arenaRadius - 2, def.arena().dbl("sigil_ring_radius", 10));
        double[] angs = BossMath.ringAngles(types.size(), 90, 30);
        sigilTotal = types.size();
        for (int i = 0; i < types.size(); i++) {
            DamageType t = types.get(i);
            FrostLogic.SigilRule rule = FrostLogic.sigilRule(t, present, solo, p.dbl("missing_role_hp_mult", 1.5));
            spawnSigil(p, t, rule, ground(ringPoint(angs[i], ringR)));
        }

        shellTicks = FrostLogic.shellCastTicks(p.dbl("cast_time", 12), p.dbl("solo_cast_time", 16), solo, scaling().timerMult());
        int glareEvery = Math.max(10, ticks(p.dbl("glare_interval", 2.0)));
        cast("glacier_shell", "절대영도", shellTicks, shellTicks + 10, BossAnim.CAST, null, false);
        busyFor(shellTicks + 10);
        run(new Mechanics.Repeat(shellTicks, 1, tt -> {
            if (!shellActive) return false;
            if (tt % 4 == 0) {
                timerBar("<aqua><b>절대영도</b></aqua> " + Floor08Math.pips(sigilsBroken, sigilTotal, "<white>", "<dark_gray>"),
                        tt / (float) shellTicks, BossBar.Color.YELLOW);
            }
            if (tt > 0 && tt % glareEvery == 0) frozenGlare(p);
            if (tt % 2 == 0) spinSigils(tt);
            if (tt % 10 == 0) {
                BossFx.dustRing(center, ringR, FROST, 1.2f, 48);
                if (shellTicks - tt <= 60) BossFx.sound(center, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1.5f, 0.5f + (float) tt / shellTicks);
            }
            if (tt >= shellTicks) {
                absoluteZero(p);
                return false;
            }
            return true;
        }, null, false));

        BossFx.sound(center, Sound.ENTITY_ELDER_GUARDIAN_CURSE, 1.2f, 0.7f);
        BossFx.sound(center, Sound.BLOCK_GLASS_PLACE, 2f, 0.5f);
        BossFx.particle(Particle.SNOWFLAKE, to.clone().add(0, 2, 0), 120, 1.5, 2, 1.5, 0.05);
        broadcastBar("<aqua><b>빙결 껍질!</b></aqua> <gray>세 빛깔의 인장이 깨어난다 — <#ff6a5a>⚔</#ff6a5a> · "
                + "<#5ad08a>🏹</#5ad08a> · <#c87aff>✦</#c87aff>");
        say("<aqua>시린</aqua><gray>이(가) 얼음 껍질에 몸을 숨긴다. 차가운 주문이 낮게 울리기 시작한다…</gray>");
    }

    private void spawnSigil(Params p, DamageType t, FrostLogic.SigilRule rule, Location at) {
        double hp = FrostLogic.sigilHp(p.dbl("sigil_hp", 900), p.dbl("sigil_hp_per_member", 0.6), partySize(), scaling().objectHpMult(), rule);
        String id = t.name().toLowerCase(java.util.Locale.ROOT);
        String color = switch (t) {
            case MELEE -> "#ff6a5a";
            case RANGED -> "#5ad08a";
            default -> "#c87aff";
        };
        String model = p.str("fx_sigil_" + id, "frost_sigil_" + id);
        float msc = 1.4f;
        ObjectTarget o = spawnObject("sigil_" + id, "<" + color + ">" + FrostLogic.sigilName(t) + "</" + color + ">", at, hp, model, msc, 1.0, 2.6);
        if (rule.filtered()) {
            o.accept(t);
            o.extra("<gray>" + FrostLogic.sigilHint(t) + "</gray>");
        } else {
            o.extra("<gray>" + FrostLogic.sigilHint(null) + "</gray>");
        }
        ItemDisplay d = o.display();
        if (d != null && d.isValid()) {
            double h = fx.size(model, 2.0)[1] * msc;
            Location up = at.clone().add(0, h / 2, 0);
            up.setYaw(0);
            up.setPitch(0);
            d.teleport(up);
        }
        o.onDestroyed(hh -> sigilBroken(t, at));
        Location top = at.clone().add(0, 2.4, 0);
        run(new Mechanics.Tether(fx, p.str("fx_tether", "rime_beam"), () -> shellAnchor == null ? top : shellAnchor, () -> top,
                tt -> shellActive && o.isAlive()));
        sigils.add(o);
        BossFx.particle(Particle.END_ROD, at.clone().add(0, 1.5, 0), 20, 0.4, 0.8, 0.4, 0.05);
    }

    /** 아레나 안에서 싸울 수 있는 플레이어(쓰러짐·관전·아레나 밖 제외)의 직업 역할 → 낼 수 있는 피해 유형. */
    private Set<DamageType> partyTypes(Params p) {
        List<String> roles = new ArrayList<>();
        for (Player pl : players()) {
            ClassDef c = services.classes().classOf(pl);
            roles.add(c == null ? null : c.role());
        }
        Map<String, String> overrides = new HashMap<>();
        for (var e : p.sub("role_damage").asMap().entrySet()) if (e.getValue() != null) overrides.put(e.getKey(), e.getValue().toString());
        return FrostLogic.presentTypes(roles, overrides);
    }

    private void spinSigils(int tt) {
        for (ObjectTarget o : sigils) {
            ItemDisplay d = o.display();
            if (d == null || !d.isValid()) continue;
            Transformation tr = d.getTransformation();
            d.setInterpolationDelay(0);
            d.setInterpolationDuration(2);
            d.setTransformation(new Transformation(tr.getTranslation(), new Quaternionf().rotationY((float) Math.toRadians(tt * 3.0)),
                    tr.getScale(), tr.getRightRotation()));
        }
    }

    private void sigilBroken(DamageType t, Location at) {
        sigilsBroken++;
        BossFx.sound(at, Sound.BLOCK_GLASS_BREAK, 1.6f, 0.6f);
        BossFx.sound(at, Sound.BLOCK_AMETHYST_CLUSTER_BREAK, 1.4f, 0.8f);
        BossFx.particle(Particle.ITEM_SNOWBALL, at.clone().add(0, 1.4, 0), 40, 0.5, 0.8, 0.5, 0.1);
        BossFx.particle(Particle.END_ROD, at.clone().add(0, 1.4, 0), 20, 0.4, 0.8, 0.4, 0.08);
        if (!shellActive) return;
        broadcastBar("<white>" + FrostLogic.sigilName(t) + "이 깨졌다!</white> " + Floor08Math.pips(sigilsBroken, sigilTotal, "<aqua>", "<dark_gray>"));
        if (sigilsBroken >= sigilTotal) shatter();
    }

    /** 위협 1위에게 얼어붙은 응시 (껍질 하위 패턴). */
    private void frozenGlare(Params p) {
        Player t = target();
        if (t == null) return;
        Location eye = entity.getEyeLocation();
        run(new Mechanics.Tether(fx, p.str("fx_glare", "rime_beam"), () -> eye, () -> t.getLocation().add(0, 1.1, 0),
                tt -> tt < 8 && validPlayer(t)));
        hit(t, dmg(p, "glare_damage", 0.6), "frozen_glare", DamageType.MAGIC);
        BossFx.sound(t.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1.2f, 1.4f);
        BossFx.particle(Particle.SNOWFLAKE, t.getLocation().add(0, 1, 0), 14, 0.3, 0.6, 0.3, 0.03);
    }

    /** 인장 셋 다 파괴 → 껍질이 부서져 기절 + 받는 피해 증가. */
    private void shatter() {
        Params p = def.pattern("glacier_shell");
        Location at = entity.getLocation().add(0, 1.5, 0);
        endShell();
        double st = p.dbl("shatter_stun", 6.0);
        stun(st);
        makeVulnerable(p.dbl("shatter_vulnerable", 0.3), st);
        broadcastBar("<aqua><b>얼음 껍질이 부서졌다!</b></aqua> <yellow>시린이 비틀거린다…</yellow>");
        BossFx.sound(at, Sound.BLOCK_GLASS_BREAK, 2f, 0.5f);
        BossFx.sound(at, Sound.BLOCK_AMETHYST_CLUSTER_BREAK, 2f, 0.6f);
        BossFx.particle(Particle.ITEM_SNOWBALL, at, 100, 1.4, 1.6, 1.4, 0.2);
        BossFx.particle(Particle.END_ROD, at, 40, 1.2, 1.4, 1.2, 0.1);
        nova(feet(), 6, 10);
    }

    /** 시전 완료 — 전원 9.0배 (사실상 전멸). 살아남았다면 전투는 계속된다. */
    private void absoluteZero(Params p) {
        double dmg = dmg(p, "wipe_damage", 9.0);
        for (Player pl : players()) {
            hit(pl, dmg, "glacier_shell", DamageType.TRUE);
            BossFx.particle(Particle.SNOWFLAKE, pl.getLocation().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.05);
        }
        broadcastBar("<dark_aqua><b>절대영도!</b></dark_aqua> <gray>모든 것이 얼어붙는다…");
        BossFx.sound(center, Sound.ENTITY_PLAYER_HURT_FREEZE, 2f, 0.5f);
        BossFx.sound(center, Sound.BLOCK_POWDER_SNOW_BREAK, 2f, 0.4f);
        BossFx.sound(center, Sound.ENTITY_GENERIC_EXPLODE, 1.2f, 0.6f);
        BossFx.particle(Particle.SNOWFLAKE, center.clone().add(0, 1.5, 0), 400, arenaRadius * 0.5, 1.5, arenaRadius * 0.5, 0.2);
        nova(center, arenaRadius + 1, 12);
        endShell();
        releaseBusy();
    }

    private void endShell() {
        shellActive = false;
        setUntargetable(false);
        setPathing(true);
        fx.discard(shellModel);
        shellModel = null;
        shellAnchor = null;
        for (ObjectTarget o : new ArrayList<>(sigils)) if (o.isAlive()) o.remove();
        sigils.clear();
        hideTimerBar();
    }

    // ── 눈보라 ───────────────────────────────────────────────────────────

    private int blizzard() {
        Params p = def.pattern("blizzard");
        if (targets().isEmpty()) return 0;
        int dur = ticks(p.dbl("duration", 10));
        int waves = Math.max(1, p.integer("waves", 4));
        int gap = Math.max(20, dur / waves);
        int count = scaling().count(p, "hail", 6, p.integer("hail_max", 20));
        double r = p.dbl("hail_radius", 2);
        double dmg = dmg(p, "hail_damage", 1.0);
        int w = windup(p, 1.2);
        int vis = Math.max(0, p.integer("visibility_particles", 40));
        String shard = p.str("fx", "proj_frost_shard");
        blizzardActive = true;
        run(new Mechanics.Repeat(dur, 1, tt -> {
            if (tt >= dur) return false;
            if (tt % 5 == 0) whiteout(vis);
            if (tt % gap == 0) hailWave(count, r, dmg, w, shard);
            if (tt % 20 == 0) BossFx.sound(center, Sound.ITEM_ELYTRA_FLYING, 0.5f, 1.6f);
            return true;
        }, () -> blizzardActive = false, true));
        BossFx.sound(center, Sound.WEATHER_RAIN, 1.5f, 0.5f);
        broadcastBar("<white><b>눈보라!</b></white> <gray>하늘이 하얗게 무너져 내린다…");
        return cast("blizzard", "눈보라", 20, 24, BossAnim.CAST, null, false);
    }

    /** 시야 입자 (그 플레이어에게만 보이게 눈앞에 눈발). */
    private void whiteout(int vis) {
        for (Player pl : players()) {
            Location eye = pl.getEyeLocation().add(pl.getLocation().getDirection().multiply(1.5));
            pl.spawnParticle(Particle.WHITE_ASH, eye, vis, 2.2, 1.2, 2.2, 0.02);
            pl.spawnParticle(Particle.SNOWFLAKE, eye, Math.max(1, vis / 3), 2.5, 1.5, 2.5, 0.04);
            pl.spawnParticle(Particle.CLOUD, eye, Math.max(1, vis / 10), 1.6, 0.8, 1.6, 0.01);
        }
    }

    private void hailWave(int count, double r, double dmg, int w, String shard) {
        List<Location> spots = new ArrayList<>();
        // 절반은 사람 발밑(조금 비켜서), 나머지는 아레나 무작위
        for (Player t : pickTargets(Math.max(1, count / 2), null, false)) {
            Location l = ground(t.getLocation().add((rng.nextDouble() - 0.5) * 2, 0, (rng.nextDouble() - 0.5) * 2));
            spots.add(l);
        }
        while (spots.size() < count) spots.add(ground(randomPoint(1, arenaRadius - 1)));
        for (Location at : spots) {
            Telegraph.Shape c = Telegraph.Shape.circle(at, r);
            Location sky = at.clone().add(0, 9, 0);
            run(new Mechanics.Projectile(fx, shard, 2.4f, Mechanics.Projectile.straight(sky, new Vector(0, -1, 0), 9.0 / Math.max(1, w)), w, 0,
                    false, Particle.SNOWFLAKE, List::of, pl -> { }, null));
            telegraph(c, w, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "blizzard", DamageType.MAGIC, null);
                BossFx.particle(Particle.ITEM_SNOWBALL, at.clone().add(0, 0.4, 0), 20, r * 0.4, 0.2, r * 0.4, 0.1);
                BossFx.sound(at, Sound.BLOCK_GLASS_BREAK, 0.9f, 1.5f);
            });
        }
    }

    // ── 영구 동토 ────────────────────────────────────────────────────────

    private int permafrost() {
        Params p = def.pattern("permafrost");
        if (validTiles.isEmpty() || !iceTiles.isEmpty()) return 0;
        int n = FrostLogic.tilesToFreeze(validTiles.size(), p.dbl("coverage", 0.3));
        List<Long> pick = new ArrayList<>(validTiles);
        Collections.shuffle(pick, rng);
        int w = windup(p, 1.0);
        int dur = ticks(p.dbl("duration", 15));
        String model = p.str("fx", "telegraph_tile_ice");
        Material m = Material.matchMaterial(p.str("block", "BLUE_ICE"));
        BlockData ice = (m != null && m.isBlock() ? m : Material.BLUE_ICE).createBlockData();
        for (Long k : pick.subList(0, n)) {
            int i = (int) (k >> 32), j = (int) (long) k;
            Location corner = new Location(center.getWorld(), gridX + i * tileSize, center.getY(), gridZ + j * tileSize);
            corner.setY(ground(corner.clone().add(tileSize / 2, 0, tileSize / 2)).getY());
            IceTile tile = new IceTile(k, corner);
            tile.plate = fx.plate(Telegraph.Shape.tile(corner, tileSize), model);
            iceTiles.put(k, tile);
        }
        // 얼어붙는 동안: 하늘색 윤곽 + 눈송이 (피해 없음 — 미끄러짐만)
        run(new Mechanics.Repeat(w, 4, tt -> {
            for (IceTile tile : iceTiles.values()) {
                fx.outline(Telegraph.Shape.tile(tile.corner, tileSize), ICE, 1.0f);
                if (rng.nextDouble() < 0.5) {
                    BossFx.particle(Particle.SNOWFLAKE, tile.corner.clone().add(tileSize / 2, 0.3, tileSize / 2), 3, tileSize * 0.3, 0.1,
                            tileSize * 0.3, 0.01);
                }
            }
            return true;
        }, null, false));
        afterPersistent(w, () -> {
            for (IceTile tile : iceTiles.values()) freezeTile(tile, ice);
            BossFx.sound(center, Sound.BLOCK_GLASS_PLACE, 2f, 0.6f);
            BossFx.sound(center, Sound.BLOCK_POWDER_SNOW_BREAK, 1.6f, 0.5f);
        });
        afterPersistent(w + dur, this::thawAll);
        broadcastBar("<#78d2ff><b>영구 동토!</b></#78d2ff> <gray>발밑이 거울처럼 얼어붙는다…");
        return cast("permafrost", "영구 동토", w, w + 6, BossAnim.SLAM, null, false);
    }

    /** 얼음판 확정: 인스턴스 안이면 아레나 바닥을 실제 얼음 블록으로(바닐라 미끄러짐), 아니면 관성 흉내. */
    private void freezeTile(IceTile tile, BlockData ice) {
        tile.active = true;
        if (!canPlaceBlocks()) {
            tile.simulated = true;
            return;
        }
        World w = center.getWorld();
        int y = center.getBlockY() - 1;
        int x0 = (int) Math.floor(tile.corner.getX()), z0 = (int) Math.floor(tile.corner.getZ());
        int size = (int) Math.round(tileSize);
        int columns = 0, placed = 0;
        for (int dx = 0; dx < size; dx++) {
            for (int dz = 0; dz < size; dz++) {
                int bx = x0 + dx, bz = z0 + dz;
                if (Math.hypot(bx + 0.5 - center.getX(), bz + 0.5 - center.getZ()) > arenaRadius - 0.5) continue;
                if (BossMath.inStairZone(bx + 0.5 - center.getX(), bz + 0.5 - center.getZ(), 2.5)) continue;
                Block floor = w.getBlockAt(bx, y, bz);
                Block above = floor.getRelative(0, 1, 0);
                columns++;
                if (!floor.getType().isSolid()) continue;
                if (above.getType() == Material.SNOW) {
                    if (setBlock(above, Material.AIR.createBlockData())) tile.blocks.add(above);
                } else if (!above.getType().isAir()) {
                    continue;
                }
                if (setBlock(floor, ice)) {
                    tile.blocks.add(floor);
                    placed++;
                }
            }
        }
        tile.simulated = columns > 0 && placed < columns;
    }

    private void thawAll() {
        for (IceTile tile : iceTiles.values()) {
            for (Block b : tile.blocks) {
                BlockData cover = thawed.get(b);
                if (cover != null) setBlock(b, cover); // 원래 블록 기록은 그대로 → 전투가 끝나면 원래 바닥으로 복원
                else restoreBlock(b);
            }
            fx.discard(tile.plate);
        }
        iceTiles.clear();
        slideVel.clear();
        slidePos.clear();
        BossFx.sound(center, Sound.BLOCK_SNOW_BREAK, 1.4f, 0.8f);
    }

    /** 블록을 못 놓은 얼음판 위 플레이어의 이동 관성 (FrostLogic.slide). */
    private void tickSlide() {
        Params p = def.pattern("permafrost");
        double retention = p.dbl("slide_retention", 0.9);
        double input = p.dbl("slide_strength", 0.12);
        double maxSpeed = p.dbl("slide_max_speed", 0.5);
        Set<UUID> seen = new HashSet<>();
        for (Player pl : players()) {
            UUID id = pl.getUniqueId();
            seen.add(id);
            Location l = pl.getLocation();
            Location prev = slidePos.put(id, l.clone());
            IceTile tile = iceTiles.get(key(BossMath.tileOf(gridX, tileSize, l.getX()), BossMath.tileOf(gridZ, tileSize, l.getZ())));
            boolean onIce = tile != null && tile.active && tile.simulated && Math.abs(l.getY() - tile.corner.getY()) < 0.15;
            if (!onIce || prev == null || prev.getWorld() != l.getWorld() || services.effects().isRooted(pl)) {
                slideVel.remove(id);
                continue;
            }
            double[] v = slideVel.getOrDefault(id, new double[]{0, 0});
            double[] nv = FrostLogic.slide(v[0], v[1], l.getX() - prev.getX(), l.getZ() - prev.getZ(), retention, input, maxSpeed);
            slideVel.put(id, nv);
            if (nv[0] == 0 && nv[1] == 0) continue;
            pl.setVelocity(new Vector(nv[0], Math.min(0, pl.getVelocity().getY()), nv[1]));
            if (now % 4 == 0) BossFx.particle(Particle.SNOWFLAKE, l.clone().add(0, 0.1, 0), 1, 0.2, 0, 0.2, 0);
        }
        slideVel.keySet().retainAll(seen);
        slidePos.keySet().retainAll(seen);
    }

    // ── 연출 ─────────────────────────────────────────────────────────────

    /** 서리 고리가 퍼져 나간다 (frost_nova_ring 판을 키우며). */
    private void nova(Location c, double radius, int ticks) {
        double[] base = fx.size("frost_nova_ring", 2.0);
        ItemDisplay ring = fx.flat("frost_nova_ring", c.clone().add(0, 0.05, 0), (float) (1.0 / base[0]), (float) (1.0 / base[2]), 0);
        if (ring == null) return;
        afterPersistent(1, () -> {
            if (!ring.isValid()) return;
            Transformation tr = ring.getTransformation();
            ring.setInterpolationDelay(0);
            ring.setInterpolationDuration(ticks);
            ring.setTransformation(new Transformation(tr.getTranslation(), tr.getLeftRotation(),
                    new Vector3f((float) (radius * 2 / base[0]), 1f, (float) (radius * 2 / base[2])), tr.getRightRotation()));
        });
        afterPersistent(ticks + 4, () -> fx.discard(ring));
        BossFx.dustRing(c, Math.max(1, radius * 0.5), FROST, 1.4f, 32);
    }

    @Override
    protected void onEnd() {
        shellActive = false;
        blizzardActive = false;
        hideTimerBar();
        frostLabels.clear();
        frostLabelText.clear();
        iceBlocks.clear();
        iceTiles.clear();
        slideVel.clear();
        slidePos.clear();
        lastPos.clear();
        sigils.clear();
        thawed.clear();
    }
}
