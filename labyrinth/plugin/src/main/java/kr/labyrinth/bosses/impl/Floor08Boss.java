package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.BossRig;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.ObjectTarget;
import kr.labyrinth.bosses.Sequence;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Text;
import kr.labyrinth.mobs.RigMath;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Directional;
import org.bukkit.block.data.type.ChiseledBookshelf;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Vector3f;

/**
 * 지하 8층 — 잉크 사서 오르벨 (GDD §7.8, core {@code puzzle_phase}).
 * <p>
 * <b>핵심: 금서 색인 {@code forbidden_index}</b> — 2·3페이즈에 들어가는 순간 보스가 떠올라 무적이 되고, 반경 13 벽면의
 * 룬 책장 8개가 1초 간격으로 하나씩 빛나며 소리를 낸다(룬마다 다른 음). 빛난 순서대로 책장을 공격(누구든)해야 한다.
 * 성공 = 보스 추락 10초 기절 + 받는 피해 +50%. 틀리면 전원 1.5배 + 처음부터 + 제한 시간 −5초, 시간 초과면 전원 4.0배 + 보스 5% 회복.
 * 진행 중 2.5초마다 먹물 방울(원 r2, 0.8배)이 떨어진다. 서열 길이 4 + ⌊(n−1)/3⌋ (최대 7), 제한 시간 20초(솔로 25초).
 * <p>
 * <b>보조: 먹물 분신 {@code ink_doubles}</b> — 보스가 1 + 분신 여럿(같은 모델)으로 갈라지며 자리가 섞인다. 진짜는 발밑에 그림자,
 * 분신은 먹물 방울을 흘린다. 분신도 약한 패턴(0.5배)을 쓰고, 맞으면 터져 때린 사람에게 0.5배 + 2초 실명.
 * 사냥꾼 표식은 분신에 남지 않는다(번져 지워짐). 진짜가 최대 HP 5% 피해를 받으면 분신 소멸. 분신 2 + ⌊(n−1)×0.34⌋ (최대 5).
 * <p>
 * 패턴: ink_lash(부채꼴 90°·길이 6) · quill_barrage(대상마다 5갈래 깃펜) · ink_doubles · erasure(3페이즈, 앞 부채꼴 90°·반경 16).
 * 대응 (GDD §8.6): 못 닿는 자리에서 맞으면 그 대상 한 명에게 깃펜 난사 (깃펜은 블록에 막힌다). 색인·부양·분신 중에는 안 함.
 */
public final class Floor08Boss extends Boss {

    private static final float RUNE_SCALE = 1.8f;
    private static final float RUNE_LIT_SCALE = 2.4f;
    private static final int DIM = 5;
    private static final Color GOLD = Color.fromRGB(255, 214, 120);
    private static final Color INK = Color.fromRGB(20, 26, 48);

    /** 룬 책장 하나 (블록은 아레나에 상시, 히트박스는 색인 동안만). */
    private static final class Shelf {
        final int index;
        final Location base;
        final Location front;
        final Location runeAt;
        ItemDisplay rune;
        TextDisplay label;
        ObjectTarget hit;

        Shelf(int index, Location base, Location front, Location runeAt) {
            this.index = index;
            this.base = base;
            this.front = front;
            this.runeAt = runeAt;
        }
    }

    /** 먹물 분신 하나: 히트박스(ObjectTarget, HP 표시 없음) + 보스와 같은 모델 리그. */
    private static final class InkDouble {
        final ObjectTarget obj;
        final BossRig rig;
        final long seed;
        final List<Telegraph> pending = new ArrayList<>();
        float yaw;
        double moveSpeed;
        long nextAttack;
        long nextSwing;
        long busyUntil;
        long attackTick = -100;
        long retargetAt;
        UUID target;
        boolean lashNext = true;
        boolean dead;

        InkDouble(ObjectTarget obj, BossRig rig, float yaw, long seed) {
            this.obj = obj;
            this.rig = rig;
            this.yaw = yaw;
            this.seed = seed;
        }
    }

    private final List<Shelf> shelves = new ArrayList<>();
    private final List<ItemDisplay> glyphs = new ArrayList<>();

    // 금서 색인
    private Sequence index;
    private int litTicks = 15;
    private int revealInterval = 20;
    private long nextInkDrop;
    private boolean inputAnnounced;
    private boolean pendingWrong;
    private Location hoverTarget;
    private boolean landing;

    // 먹물 분신
    private final List<InkDouble> doubles = new ArrayList<>();
    private final List<UUID> pendingBursts = new ArrayList<>();
    private long doublesUntil = -1;
    private double damageSinceSplit;
    private boolean dispelPending;
    private ItemDisplay shadow;

    public Floor08Boss(Init init) { super(init); }

    private Params fi() { return def.pattern("forbidden_index"); }

    // ── 아레나: 룬 책장 ──────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        Params a = def.arena();
        Params fi = fi();
        int count = Math.max(2, a.integer("rune_shelves", fi.integer("runes", 8)));
        double ring = Math.min(arenaRadius - 1.5, a.dbl("rune_ring_radius", 13));
        BlockData low = mat(a.str("shelf_block", "BOOKSHELF"), Material.BOOKSHELF);
        String prefix = fi.str("fx_rune_prefix", "rune_");
        int y0 = center.getBlockY();
        double[] angs = Floor08Math.shelfAngles(count);
        for (int i = 0; i < angs.length; i++) {
            double ang = angs[i];
            Location c = ringPoint(ang, ring).getBlock().getLocation().add(0.5, 0, 0.5);
            c.setY(y0);
            int[] in = Floor08Math.inwardCardinal(ang);
            int tx = in[0] == 0 ? 1 : 0, tz = in[0] == 0 ? 0 : 1;
            BlockFace face = faceOf(in);
            for (int k = -1; k <= 1; k++) {
                int bx = c.getBlockX() + tx * k, bz = c.getBlockZ() + tz * k;
                if (BossMath.inStairZone(bx + 0.5 - center.getX(), bz + 0.5 - center.getZ(), 2.5)) continue;
                placeOrShow(bx, y0, bz, low);
                placeOrShow(bx, y0 + 1, bz, topShelf(a, face, i * 3 + k));
            }
            Location runeAt = c.clone().add(in[0] * 0.2, 2.9, in[1] * 0.2);
            runeAt.setYaw(BossMath.yawOf(in[0], in[1]));
            Location front = c.clone().add(in[0] * 1.5, 0, in[1] * 1.5);
            Shelf s = new Shelf(i, c, front, runeAt);
            s.rune = fx.model(prefix + (i % 8 + 1), runeAt, RUNE_SCALE, Display.Billboard.FIXED);
            runeState(s, null, RUNE_SCALE, DIM);
            shelves.add(s);
            BossFx.particle(Particle.ENCHANT, runeAt, 16, 0.5, 0.5, 0.5, 0.6);
        }
    }

    private void placeOrShow(int x, int y, int z, BlockData data) {
        World w = center.getWorld();
        Block b = w.getBlockAt(x, y, z);
        if (!setBlock(b, data)) fx.block(new Location(w, x, y, z), data, 1f, 1f, 1f);
    }

    private static BlockFace faceOf(int[] in) {
        if (in[0] > 0) return BlockFace.EAST;
        if (in[0] < 0) return BlockFace.WEST;
        return in[1] > 0 ? BlockFace.SOUTH : BlockFace.NORTH;
    }

    private static BlockData topShelf(Params a, BlockFace face, int seed) {
        BlockData d = mat(a.str("shelf_top_block", "CHISELED_BOOKSHELF"), Material.CHISELED_BOOKSHELF);
        if (d instanceof Directional dir && dir.getFaces().contains(face)) dir.setFacing(face);
        if (d instanceof ChiseledBookshelf cb) {
            for (int s = 0; s < cb.getMaximumOccupiedSlots(); s++) cb.setSlotOccupied(s, Math.floorMod(seed * 31 + s * 7, 4) != 0);
        }
        return d;
    }

    private static BlockData mat(String name, Material def) {
        Material m = Material.matchMaterial(name == null ? "" : name);
        return (m != null && m.isBlock() ? m : def).createBlockData();
    }

    /** 룬 표시 상태: glow = 발광 색(null = 끔), 크기, 밝기. */
    private void runeState(Shelf s, Color glow, float scale, int brightness) {
        ItemDisplay d = s.rune;
        if (d == null || !d.isValid()) return;
        d.setGlowing(glow != null);
        d.setGlowColorOverride(glow);
        d.setBrightness(new Display.Brightness(brightness, brightness));
        Transformation tr = d.getTransformation();
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(4);
        d.setTransformation(new Transformation(tr.getTranslation(), tr.getLeftRotation(), new Vector3f(scale, scale, scale),
                tr.getRightRotation()));
    }

    // ── 스케줄러 ─────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) {
        if (index != null || hoverTarget != null) return false;
        if (key.equals("ink_doubles")) return doubles.isEmpty() && !targets().isEmpty();
        return target() != null;
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "ink_lash" -> inkLash();
            case "quill_barrage" -> quillBarrage();
            case "ink_doubles" -> inkDoubles();
            case "erasure" -> erasure();
            default -> 0;
        };
    }

    @Override
    protected void onTick() {
        tickHover();
        if (index != null) tickIndex();
        tickDoubles();
        if (!pendingBursts.isEmpty()) {
            Params p = def.pattern("ink_doubles");
            for (UUID u : new ArrayList<>(pendingBursts)) {
                Player pl = Bukkit.getPlayer(u);
                if (pl == null || !validPlayer(pl)) continue;
                hit(pl, dmg(p, "burst_damage", 0.5), "ink_doubles", DamageType.MAGIC);
                effect(pl, "blind", p.dbl("burst_blind", 2.0), 1);
                notify(pl, "<dark_aqua>찢긴 것은 먹물뿐이었다…</dark_aqua> <gray>눈앞이 검게 번진다");
            }
            pendingBursts.clear();
        }
    }

    @Override
    protected void onPhase(int newPhase) {
        clearDoubles(0);
        if (index != null) endIndex();
        BossFx.sound(center, Sound.ITEM_BOOK_PAGE_TURN, 2f, 0.4f);
        BossFx.sound(center, Sound.BLOCK_ENCHANTMENT_TABLE_USE, 2f, 0.6f);
        BossFx.particle(Particle.SQUID_INK, entity.getLocation().add(0, 1.5, 0), 60, 1, 1, 1, 0.1);
        for (Shelf s : shelves) BossFx.particle(Particle.ENCHANT, s.runeAt, 30, 0.6, 0.6, 0.6, 1.2);
        if (triggers(newPhase)) startIndex();
    }

    private boolean triggers(int phase) {
        List<Object> list = fi().list("trigger_phases");
        if (list == null || list.isEmpty()) return phase == 2 || phase == 3;
        for (Object o : list) if (o instanceof Number n && n.intValue() == phase) return true;
        return false;
    }

    @Override
    public double applyDamage(double amount, DamageContext dctx) {
        double dealt = super.applyDamage(amount, dctx);
        if (dealt > 0 && !doubles.isEmpty()) {
            damageSinceSplit += dealt;
            double ratio = def.pattern("ink_doubles").dbl("reveal_damage_ratio", 0.05);
            if (Floor08Math.dispelled(damageSinceSplit, maxHealth(), ratio)) dispelPending = true;
        }
        return dealt;
    }

    private Vector dirTo(Location from, Location to) {
        Vector d = to.toVector().subtract(from.toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    private String plateText() {
        return def.name() + (enraged() ? " <dark_red>광폭</dark_red>" : "");
    }

    // ── 먹물 채찍 ────────────────────────────────────────────────────────

    private int inkLash() {
        Params p = def.pattern("ink_lash");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 1.0);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(entity.getLocation(), t.getLocation()), p.dbl("angle", 90), p.dbl("length", 6));
        double dmg = dmg(p, "damage", 1.4);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "ink_lash", DamageType.MELEE, null);
            lashFx(cone);
        });
        return cast("ink_lash", "먹물 채찍", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    private void lashFx(Telegraph.Shape cone) {
        Location o = cone.origin();
        BossFx.sound(o, Sound.ENTITY_SQUID_SQUIRT, 1.4f, 0.6f);
        BossFx.sound(o, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.2f, 0.5f);
        Vector d = cone.direction();
        double stepDeg = Math.max(5, cone.angle() / 8);
        for (double off = -cone.angle() / 2; off <= cone.angle() / 2 + 1e-6; off += stepDeg) {
            double[] r = Floor08Math.rotate(d.getX(), d.getZ(), off);
            for (double f = 1.5; f <= cone.size(); f += 1.5) {
                BossFx.particle(Particle.SQUID_INK, o.clone().add(r[0] * f, 1.0, r[1] * f), 1, 0.1, 0.1, 0.1, 0.01);
            }
        }
    }

    // ── 깃펜 난사 ────────────────────────────────────────────────────────

    private int quillBarrage() {
        Params p = def.pattern("quill_barrage");
        List<Player> all = targets();
        if (all.isEmpty()) return 0;
        int n = Math.min(all.size(), scaling().count(p, "targets", 1, all.size()));
        return quillBarrage(pickTargets(n, null, false));
    }

    // ── 대응 (GDD §8.6) ──────────────────────────────────────────────────

    @Override
    protected boolean canAnswer(Player t) { return index == null && hoverTarget == null && doubles.isEmpty(); }

    @Override
    protected int answer(Answer a) {
        Player t = a.target();
        return t == null || !t.isValid() ? 0 : quillBarrage(List.of(t));
    }

    /** 깃펜 난사: 대상마다 부채꼴 갈래 (원래 수치). */
    private int quillBarrage(List<Player> ts) {
        Params p = def.pattern("quill_barrage");
        if (ts.isEmpty()) return 0;
        int w = windup(p, 0.8);
        Location from = feet();
        double dmg = dmg(p, "damage", 0.7);
        for (Player t : ts) {
            fan(from, dirTo(from, t.getLocation()), p.integer("count", 5), p.dbl("spread", 40), p, dmg, "quill_barrage", w, null);
        }
        BossFx.sound(entity.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 1.6f, 1.4f);
        return cast("quill_barrage", "깃펜 난사", w, w + 6, BossAnim.THROW, ts.get(0).getLocation(), false);
    }

    /**
     * 부채꼴 깃펜: count 갈래 선 경고 → 발동 때 각 선을 따라 투사체(블록에 막힘). 투사체마다 따로 맞으므로 피해 = 배율 × 맞은 수.
     */
    private void fan(Location from, Vector dir, int count, double spread, Params p, double damage, String pattern, int w,
                     List<Telegraph> track) {
        double range = p.dbl("range", 18), width = p.dbl("width", 0.9);
        double speed = Math.max(0.3, p.dbl("speed", 1.3) * scaling().speedMult());
        int travel = Math.max(2, (int) Math.ceil(range / speed));
        String model = p.str("fx", "proj_quill");
        double[] offs = Floor08Math.fanOffsets(count, spread);
        for (int i = 0; i < offs.length; i++) {
            double[] r = Floor08Math.rotate(dir.getX(), dir.getZ(), offs[i]);
            Vector d = new Vector(r[0], 0, r[1]).normalize();
            Telegraph.Shape line = Telegraph.Shape.line(from, d, range, width);
            boolean first = i == 0;
            Telegraph tg = telegraph(line, w, Telegraph.RED, null, () -> {
                Location start = from.clone().add(d.clone().multiply(0.8)).add(0, 1.3, 0);
                run(new Mechanics.Projectile(fx, model, 1.4f, Mechanics.Projectile.straight(start, d, speed), travel, 0.45, true,
                        Particle.ENCHANT, this::players, pl -> hit(pl, damage, pattern, DamageType.RANGED), null));
                if (first) BossFx.sound(start, Sound.ENTITY_WITCH_THROW, 1.4f, 1.6f);
            });
            if (i != offs.length / 2) tg.noOutline();
            if (track != null) track.add(tg);
        }
    }

    // ── 지우기 (3페이즈) ─────────────────────────────────────────────────

    private int erasure() {
        Params p = def.pattern("erasure");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 2.0);
        Location o = feet();
        Telegraph.Shape cone = Telegraph.Shape.cone(o, dirTo(o, t.getLocation()), p.dbl("angle", 90), p.dbl("radius", 16));
        double dmg = dmg(p, "damage", 2.5);
        telegraph(cone, w, Telegraph.ORANGE, p.str("fx", "telegraph_cone"), () -> {
            hitShape(cone, dmg, "erasure", DamageType.MAGIC, pl -> notify(pl, "<dark_gray>당신의 한 줄이 하얗게 지워진다…</dark_gray>"));
            BossFx.sound(o, Sound.ENTITY_WARDEN_SONIC_BOOM, 1.0f, 0.6f);
            BossFx.sound(o, Sound.ITEM_BOOK_PAGE_TURN, 2f, 0.5f);
            Vector d = cone.direction();
            run(new Mechanics.Repeat(10, 1, tt -> {
                double f = cone.size() * (tt + 1) / 10.0;
                for (double off = -cone.angle() / 2; off <= cone.angle() / 2 + 1e-6; off += 7.5) {
                    double[] r = Floor08Math.rotate(d.getX(), d.getZ(), off);
                    Location at = o.clone().add(r[0] * f, 0.6, r[1] * f);
                    BossFx.particle(Particle.SQUID_INK, at, 1, 0.15, 0.3, 0.15, 0.02);
                    if (tt % 2 == 0) BossFx.dust(at.add(0, 0.5, 0), INK, 1.6f, 1, 0.1);
                }
                return true;
            }, null, false));
        });
        broadcastBar("<dark_gray>오르벨 앞의 글자들이 하얗게 바래 간다…</dark_gray>");
        return cast("erasure", "지우기", w, w + 10, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 금서 색인 (핵심 퍼즐) ────────────────────────────────────────────

    private void startIndex() {
        if (shelves.isEmpty()) return;
        Params p = fi();
        int symbols = shelves.size();
        int len = Math.min(symbols, Sequence.length(p.dbl("sequence_base", 4), p.dbl("sequence_per_members", 3),
                p.integer("sequence_max", 7), partySize()));
        int interval = Math.max(10, windupSec(p.dbl("show_interval", 1.0)));
        revealInterval = interval;
        litTicks = Math.max(6, (int) Math.round(interval * p.dbl("lit_ratio", 0.75)));
        int lead = ticks(p.dbl("reveal_lead", 2.5));
        int limit = ticks(p.scaled("time_limit", partySize(), 20) * scaling().timerMult());
        int penalty = ticks(p.dbl("wrong_time_penalty", 5));
        index = new Sequence(Sequence.generate(symbols, len, rng), now, lead, interval, litTicks, limit, penalty);
        inputAnnounced = false;
        pendingWrong = false;
        nextInkDrop = index.revealStart() + ticks(p.dbl("ink_drop_interval", 2.5)) / 2;

        // 보스가 떠올라 무적
        setUntargetable(true);
        setPathing(false);
        entity.setGravity(false);
        hoverTarget = center.clone().add(0, p.dbl("hover_height", 4), 0);
        landing = false;
        int castLen = (int) (index.inputStart() - now) + limit;
        afterPersistent(24, () -> {
            if (index != null) rig.play(BossAnim.CAST, castLen, 0.1, now);
        });

        for (Shelf s : shelves) {
            runeState(s, null, RUNE_SCALE, DIM);
            if (s.hit == null || !s.hit.isAlive()) {
                ObjectTarget o = spawnObject("rune_shelf", "<#c8a060>룬 책장</#c8a060>", s.front, 1, null, 1f, 2.0, 3.4);
                o.hideLabel();
                o.onHit((obj, dc) -> {
                    shelfHit(s, dc);
                    return false;
                });
                s.hit = o;
            }
            if (s.label == null || !s.label.isValid()) s.label = fx.label(s.runeAt.clone().add(0, 1.4, 0), "", 1.0f);
            BossFx.text(s.label, "");
        }
        BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 1.6f, 0.6f);
        BossFx.particle(Particle.ENCHANT, center.clone().add(0, 2, 0), 120, 3, 1.5, 3, 1.5);
        say("<gold><b>✦ 금서 색인</b></gold> <gray>— 서가가 깨어나 차례를 읊기 시작한다…</gray>");
        broadcastBar("<gold><b>금서 색인</b></gold> <gray>책장들이 숨을 죽인다…");
    }

    private void tickIndex() {
        Params p = fi();
        busyFor(3);
        Sequence.State st = index.update(now);
        int step = index.revealStep(now);
        if (step >= 0) lightRune(shelves.get(index.symbol(step)));
        if (st == Sequence.State.INPUT && !inputAnnounced) {
            inputAnnounced = true;
            lockYaw(null);
            broadcastBar("<gold>서가가 대답을 기다린다…</gold>");
            BossFx.sound(center, Sound.BLOCK_BELL_USE, 1.6f, 1.2f);
        }
        boolean live = st == Sequence.State.REVEAL || st == Sequence.State.INPUT;
        if (live && now >= nextInkDrop && now >= index.revealStart()) {
            inkDrops(p);
            nextInkDrop = now + Math.max(10, ticks(p.dbl("ink_drop_interval", 2.5)));
        }
        if (pendingWrong) {
            pendingWrong = false;
            applyWrong(p);
        }
        if (st == Sequence.State.SUCCESS) {
            indexSuccess(p);
            return;
        }
        if (st == Sequence.State.FAILED) {
            indexFail(p);
            return;
        }
        if (now % 4 == 0) indexBar();
    }

    private void indexBar() {
        if (index == null) return;
        if (index.state() == Sequence.State.REVEAL) {
            int shown = now < index.revealStart() ? 0
                    : (int) Math.min(index.length(), (now - index.revealStart()) / Math.max(1, revealInterval) + 1);
            timerBar("<gold>금서 색인</gold> " + Floor08Math.pips(shown, index.length(), "<gold>", "<dark_gray>"),
                    shown / (float) index.length(), BossBar.Color.YELLOW);
        } else {
            long left = index.remaining(now);
            timerBar("<gold>금서 색인</gold> " + Floor08Math.pips(index.progress(), index.length(), "<green>", "<dark_gray>"),
                    left / (float) index.timeLimit(),
                    left < 100 ? BossBar.Color.RED : BossBar.Color.YELLOW);
        }
    }

    private boolean accepted(int shelf) {
        if (index == null) return false;
        for (int k = 0; k < index.progress(); k++) if (index.symbol(k) == shelf) return true;
        return false;
    }

    /** 공개: 룬이 금빛으로 빛나며 그 룬만의 음. 보스가 그 책장을 바라본다. */
    private void lightRune(Shelf s) {
        Params p = fi();
        runeState(s, GOLD, RUNE_LIT_SCALE, 15);
        faceNow(s.base);
        BossFx.sound(s.base, Sound.BLOCK_NOTE_BLOCK_BELL, 2f, Floor08Math.runePitch(s.index));
        BossFx.sound(s.base, Sound.ITEM_BOOK_PAGE_TURN, 1.5f, 0.8f);
        BossFx.particle(Particle.ENCHANT, s.runeAt, 40, 0.6, 0.6, 0.6, 1.0);
        BossFx.particle(Particle.END_ROD, s.runeAt, 8, 0.3, 0.3, 0.3, 0.02);
        BossFx.dustLine(s.runeAt, entity.getLocation().add(0, 2.2, 0), GOLD, 0.9f, 0.9);
        ItemDisplay g = fx.flat(p.str("fx_glyph", "index_glyph"), s.front.clone().add(0, 0.04, 0), 2.6f, 2.6f, 0);
        if (g != null) glyphs.add(g);
        after(litTicks, () -> {
            fx.discard(g);
            glyphs.remove(g);
            if (index != null && !accepted(s.index)) runeState(s, null, RUNE_SCALE, DIM);
        });
    }

    /** 책장 피격 (ObjectTarget 가로채기 — HP 는 깎지 않는다). 해결(성공·실패·벌칙)은 다음 틱 {@link #tickIndex()} 에서. */
    private void shelfHit(Shelf s, DamageContext dc) {
        if (index == null) return;
        if (dc != null && dc.sourceId() != null && dc.sourceId().startsWith("effect:")) return; // 지속 피해는 입력이 아님
        Player by = dc == null ? null : dc.attackerPlayer();
        BossFx.sound(s.base, Sound.BLOCK_CHISELED_BOOKSHELF_PICKUP, 1f, 1f);
        switch (index.input(s.index, now)) {
            case ADVANCE, COMPLETE -> correct(s, index.progress());
            case WRONG -> pendingWrong = true;
            case IGNORED -> {
                if (by != null && index.state() == Sequence.State.REVEAL) {
                    notify(by, "<gray>서가는 아직 읊는 중이다…");
                }
            }
        }
    }

    private void correct(Shelf s, int k) {
        runeState(s, Telegraph.GREEN, 2.0f, 15);
        BossFx.text(s.label, "<green><b>✔ " + k + "</b></green>");
        BossFx.sound(s.base, Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 1.2f, (float) Math.min(2.0, 0.7 + 0.12 * k));
        BossFx.sound(s.base, Sound.BLOCK_NOTE_BLOCK_BELL, 1.4f, Floor08Math.runePitch(s.index));
        BossFx.particle(Particle.ENCHANT, s.runeAt, 30, 0.5, 0.5, 0.5, 0.8);
        BossFx.particle(Particle.HAPPY_VILLAGER, s.runeAt, 8, 0.4, 0.4, 0.4, 0);
    }

    private void applyWrong(Params p) {
        double d = dmg(p, "wrong_damage", 1.5);
        for (Player pl : players()) {
            hit(pl, d, "forbidden_index", DamageType.MAGIC);
            BossFx.particle(Particle.SQUID_INK, pl.getLocation().add(0, 1, 0), 16, 0.3, 0.5, 0.3, 0.05);
        }
        for (Shelf s : shelves) {
            runeState(s, Telegraph.RED, RUNE_SCALE, 15);
            BossFx.text(s.label, "");
        }
        after(12, () -> {
            if (index == null) return;
            for (Shelf s : shelves) if (!accepted(s.index)) runeState(s, null, RUNE_SCALE, DIM);
        });
        say(def.line("index_wrong"));
        broadcastBar("<red>책장들이 일제히 붉게 운다…</red>");
        BossFx.sound(center, Sound.BLOCK_NOTE_BLOCK_BASS, 2f, 0.5f);
        BossFx.sound(center, Sound.ENTITY_ELDER_GUARDIAN_CURSE, 0.6f, 1.3f);
    }

    private void indexSuccess(Params p) {
        for (Shelf s : shelves) BossFx.particle(Particle.END_ROD, s.runeAt, 20, 0.4, 0.4, 0.4, 0.08);
        endIndex();
        double sec = p.dbl("success_stun", 10);
        double vul = p.dbl("success_vulnerable", 0.5);
        stun(sec);
        makeVulnerable(vul, sec);
        say(def.line("index_success"));
        broadcastBar("<gold><b>색인이 맞물린다</b></gold> <yellow>— 오르벨이 허공에서 떨어진다!</yellow>");
        BossFx.sound(center, Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1.2f);
        BossFx.sound(center, Sound.BLOCK_ENCHANTMENT_TABLE_USE, 2f, 1.4f);
    }

    private void indexFail(Params p) {
        double d = dmg(p, "fail_damage", 4.0);
        for (Player pl : players()) {
            hit(pl, d, "forbidden_index", DamageType.MAGIC);
            BossFx.particle(Particle.SQUID_INK, pl.getLocation().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.1);
        }
        double ratio = p.dbl("fail_heal", 0.05);
        heal(maxHealth() * ratio);
        endIndex();
        say(def.line("index_fail"));
        broadcastBar("<dark_red>먹물이 서고를 덮친다…</dark_red> <gray>오르벨의 잉크가 다시 차오른다");
        BossFx.sound(center, Sound.ENTITY_WARDEN_SONIC_BOOM, 1f, 0.5f);
        BossFx.sound(center, Sound.ENTITY_SQUID_SQUIRT, 2f, 0.4f);
        run(new Mechanics.Repeat(14, 1, tt -> {
            double r = arenaRadius * (tt + 1) / 14.0;
            for (int i = 0; i < 24; i++) {
                double a = 2 * Math.PI * i / 24 + tt * 0.1;
                BossFx.particle(Particle.SQUID_INK, center.clone().add(Math.cos(a) * r, 0.4, Math.sin(a) * r), 1, 0.1, 0.1, 0.1, 0.01);
            }
            return true;
        }, null, false));
    }

    /** 색인 정리 (성공·실패·페이즈 전환): 히트박스·표시 제거, 보스 착지·무적 해제. */
    private void endIndex() {
        if (index != null) index.abort();
        index = null;
        pendingWrong = false;
        for (Shelf s : shelves) {
            if (s.hit != null) s.hit.remove();
            s.hit = null;
            fx.discard(s.label);
            s.label = null;
            runeState(s, null, RUNE_SCALE, DIM);
        }
        for (ItemDisplay g : glyphs) fx.discard(g);
        glyphs.clear();
        hideTimerBar();
        setUntargetable(false);
        lockYaw(null);
        rig.stop();
        if (entity.isValid()) {
            hoverTarget = ground(entity.getLocation());
            landing = true;
        }
    }

    /** 2.5초마다 먹물 방울: 플레이어마다 발밑 원 r2 (+ 난이도 추가분은 무작위 자리). */
    private void inkDrops(Params p) {
        List<Player> ps = players();
        int n = Floor08Math.inkDrops(ps.size(), scaling().extraCount(), 12);
        int w = windupSec(p.dbl("ink_drop_windup", 1.2));
        double r = p.dbl("ink_drop_radius", 2);
        double dmg = dmg(p, "ink_drop_damage", 0.8);
        String model = p.str("fx_drop", "proj_ink");
        for (int i = 0; i < n; i++) {
            Location at = i < ps.size() ? ground(ps.get(i).getLocation()) : ground(randomPoint(2, arenaRadius - 3));
            Telegraph.Shape c = Telegraph.Shape.circle(at, r);
            Location top = at.clone().add(0, 9, 0);
            run(new Mechanics.Projectile(fx, model, 2.2f, Mechanics.Projectile.lob(top, at.clone().add(0, 0.3, 0), w, 0), w, 0, false,
                    Particle.SQUID_INK, List::of, pl -> { }, null));
            telegraph(c, w, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "ink_drop", DamageType.MAGIC, null);
                BossFx.particle(Particle.SQUID_INK, at.clone().add(0, 0.3, 0), 30, r * 0.4, 0.1, r * 0.4, 0.05);
                BossFx.sound(at, Sound.BLOCK_SLIME_BLOCK_BREAK, 1.2f, 0.5f);
            });
        }
    }

    // ── 공중 부양·착지 ───────────────────────────────────────────────────

    private void tickHover() {
        if (hoverTarget == null || !entity.isValid()) return;
        Location l = entity.getLocation();
        Vector d = hoverTarget.toVector().subtract(l.toVector());
        double len = d.length();
        double step = landing ? 0.5 : 0.22;
        if (len > 0.05) {
            Location to = l.clone().add(d.multiply(Math.min(1.0, step / len)));
            to.setYaw(l.getYaw());
            to.setPitch(0);
            entity.teleport(to);
            entity.setVelocity(new Vector());
        } else if (landing) {
            finishLanding();
            return;
        }
        if (!landing && now % 3 == 0) {
            BossFx.particle(Particle.ENCHANT, l.clone().add(0, -0.2, 0), 6, 0.6, 0.2, 0.6, 0.4);
            BossFx.particle(Particle.SQUID_INK, l.clone().add(0, 0.6, 0), 1, 0.4, 0.4, 0.4, 0);
        }
    }

    private void finishLanding() {
        hoverTarget = null;
        landing = false;
        entity.setGravity(true);
        setPathing(true);
        Location at = entity.getLocation();
        BossFx.sound(at, Sound.BLOCK_ANVIL_LAND, 0.9f, 0.6f);
        BossFx.sound(at, Sound.ITEM_BOOK_PAGE_TURN, 2f, 0.6f);
        BossFx.particle(Particle.SQUID_INK, at.clone().add(0, 0.3, 0), 40, 1.2, 0.1, 1.2, 0.05);
        BossFx.particle(Particle.EXPLOSION, at.clone().add(0, 0.5, 0), 1, 0, 0, 0, 0);
    }

    // ── 먹물 분신 ────────────────────────────────────────────────────────

    private int inkDoubles() {
        Params p = def.pattern("ink_doubles");
        int count = scaling().count(p, "count", 2, p.integer("max", 5));
        int w = windup(p, 1.0);
        Telegraph.Shape swirl = Telegraph.Shape.circle(feet(), 2.2);
        telegraph(swirl, w, Telegraph.PURPLE, "telegraph_mechanic", () -> split(count, p));
        BossFx.sound(entity.getLocation(), Sound.ENTITY_ILLUSIONER_PREPARE_MIRROR, 2f, 0.7f);
        broadcastBar("<dark_aqua>오르벨이 먹물로 제 모습을 그려 낸다…</dark_aqua>");
        return cast("ink_doubles", "먹물 분신", w, w + 14, BossAnim.CAST, null, false);
    }

    private void split(int count, Params p) {
        clearDoubles(0);
        double[] angs = Floor08Math.splitAngles(count, rng.nextDouble() * 360);
        double r = Math.max(3, Math.min(arenaRadius - 4, p.dbl("split_radius", 7)));
        int real = Floor08Math.realSlot(angs.length, rng);
        BossFx.particle(Particle.SQUID_INK, entity.getLocation().add(0, 1.4, 0), 60, 0.6, 1.0, 0.6, 0.08);
        rig.setHidden(true);
        for (int i = 0; i < angs.length; i++) {
            Location slot = ground(ringPoint(angs[i], r));
            slot.setYaw(BossMath.yawOf(center.getX() - slot.getX(), center.getZ() - slot.getZ()));
            BossFx.particle(Particle.SQUID_INK, slot.clone().add(0, 1.2, 0), 50, 0.5, 0.9, 0.5, 0.05);
            BossFx.particle(Particle.LARGE_SMOKE, slot.clone().add(0, 1, 0), 14, 0.4, 0.8, 0.4, 0.02);
            if (i == real) {
                entity.teleport(slot);
                bodyYaw = slot.getYaw();
            } else {
                spawnDouble(slot, p);
            }
        }
        BossFx.sound(center, Sound.ENTITY_ILLUSIONER_MIRROR_MOVE, 2f, 0.7f);
        BossFx.sound(center, Sound.ENTITY_SQUID_SQUIRT, 2f, 0.5f);
        doublesUntil = now + ticks(p.dbl("duration", 20));
        damageSinceSplit = 0;
        dispelPending = false;
        shadow = fx.flat(p.str("fx_shadow", "ink_shadow"), feet().add(0, 0.02, 0), 1.5f, 1.5f, 0);
        afterPersistent(8, this::revealSplit);
        say(def.line("doubles"));
        broadcastBar("<dark_aqua>잉크가 똑, 똑 흘러내린다…</dark_aqua>");
    }

    private void revealSplit() {
        if (!isAlive()) return;
        rig.setHidden(false);
        rig.nameplate(Text.mm(plateText()));
        for (InkDouble d : doubles) {
            if (d.dead) continue;
            d.rig.setHidden(false);
            d.rig.nameplate(Text.mm(plateText()));
        }
    }

    private void spawnDouble(Location slot, Params p) {
        double sc = def.scale();
        ObjectTarget o = spawnObject("ink_double", def.name(), slot, 1, null, 1f, 0.6 * sc, 1.95 * sc);
        o.hideLabel();
        BossRig r = new BossRig(def.id(), def.model(), def.scale(), services.plugin().getConfig().getDouble("mobs.model_yaw_offset", 0.0));
        r.spawn(slot, def.id());
        r.setHidden(true);
        if (enraged()) r.setGlow(Color.fromRGB(255, 40, 40));
        InkDouble d = new InkDouble(o, r, slot.getYaw(), rng.nextLong());
        d.nextAttack = now + ticks(1.5 + rng.nextDouble() * 2.0);
        d.nextSwing = now + 20;
        o.onHit((obj, dc) -> {
            burst(d, dc == null ? null : dc.attackerPlayer(), true);
            return false;
        });
        doubles.add(d);
    }

    /** 분신이 터짐: 먹물 폭발 + (맞아서 터졌으면) 때린 사람 벌칙은 다음 틱에. */
    private void burst(InkDouble d, Player attacker, boolean punish) {
        if (d.dead) return;
        d.dead = true;
        for (Telegraph t : d.pending) t.cancel();
        d.pending.clear();
        Location at = d.obj.at();
        BossFx.particle(Particle.SQUID_INK, at.clone().add(0, 1.4, 0), 70, 0.5, 0.9, 0.5, 0.12);
        BossFx.sound(at, Sound.ENTITY_SQUID_SQUIRT, 1.6f, 0.7f);
        BossFx.sound(at, Sound.BLOCK_SLIME_BLOCK_BREAK, 1.2f, 0.6f);
        d.obj.remove();
        d.rig.remove();
        if (punish && attacker != null) pendingBursts.add(attacker.getUniqueId());
    }

    /** mode: 0 = 조용히(페이즈 전환·종료), 1 = 시간 만료, 2 = 진짜가 들켜 소멸. */
    private void clearDoubles(int mode) {
        boolean had = !doubles.isEmpty() || shadow != null;
        for (InkDouble d : new ArrayList<>(doubles)) burst(d, null, false);
        doubles.clear();
        fx.discard(shadow);
        shadow = null;
        doublesUntil = -1;
        dispelPending = false;
        damageSinceSplit = 0;
        if (!had) return;
        if (mode == 2) {
            say(def.line("doubles_gone"));
            broadcastBar("<gray>사본들이 녹아내린다…");
        } else if (mode == 1) {
            broadcastBar("<gray>사본들이 번져 사라진다…");
        }
    }

    private void tickDoubles() {
        if (doublesUntil < 0) return;
        for (InkDouble d : new ArrayList<>(doubles)) if (!d.dead && !d.obj.isAlive()) burst(d, null, false);
        doubles.removeIf(d -> d.dead);
        if (dispelPending) {
            clearDoubles(2);
            return;
        }
        if (now >= doublesUntil || doubles.isEmpty()) {
            clearDoubles(doubles.isEmpty() ? 0 : 1);
            return;
        }
        if (shadow != null && shadow.isValid()) {
            Location g = feet().add(0, 0.02, 0);
            g.setYaw(0);
            shadow.teleport(g);
        }
        Params p = def.pattern("ink_doubles");
        Particle tell = particleOf(p.str("tell_particle", "SQUID_INK"), Particle.SQUID_INK);
        for (InkDouble d : doubles) tickDouble(d, p, tell);
    }

    private void tickDouble(InkDouble d, Params p, Particle tell) {
        Location l = d.obj.at();
        if (now >= d.retargetAt) {
            Player t = nearest(l);
            d.target = t == null ? null : t.getUniqueId();
            d.retargetAt = now + 40 + rng.nextInt(20);
        }
        Player t = d.target == null ? null : Bukkit.getPlayer(d.target);
        if (t != null && !validPlayer(t)) {
            t = null;
            d.target = null;
        }
        double moved = 0;
        d.pending.removeIf(tg -> tg.elapsed() >= tg.total());
        if (t != null && now >= d.busyUntil) {
            double dist = horizontal(l, t.getLocation());
            if (now >= d.nextAttack) {
                doubleAttack(d, t, dist, p);
            } else if (dist <= reach() && now >= d.nextSwing && Math.abs(t.getLocation().getY() - l.getY()) < 3.5) {
                doubleSwing(d, t, p);
            } else if (dist > reach() * 0.85) {
                double step = p.dbl("double_speed", 0.11) * scaling().speedMult();
                Vector dir = t.getLocation().toVector().subtract(l.toVector()).setY(0);
                if (dir.lengthSquared() > 1e-4) {
                    dir.normalize().multiply(Math.min(step, Math.max(0, dist - reach() * 0.8)));
                    Location to = l.clone().add(dir);
                    to.setY(fx.groundY(to.clone().add(0, 0.5, 0)));
                    if (passable(to) && horizontal(to, center) <= arenaRadius - 1) {
                        to.setYaw(d.yaw);
                        to.setPitch(0);
                        d.obj.entity().teleport(to);
                        moved = horizontal(l, to);
                    }
                }
            }
            if (now >= d.busyUntil) {
                float want = BossMath.yawOf(t.getLocation().getX() - l.getX(), t.getLocation().getZ() - l.getZ());
                d.yaw = BossMath.turn(d.yaw, want, 12f);
            }
        }
        d.moveSpeed = d.moveSpeed * 0.6 + moved * 0.4;
        Location now0 = d.obj.at();
        d.rig.follow(now0);
        if (now % 2 == 0) d.rig.animate(d.yaw, animState(d, t, now0), 2);
        if (now % 3 == 0) {
            BossFx.particle(tell, now0.clone().add(rng.nextGaussian() * 0.25, 1.0 + rng.nextDouble() * 1.6, rng.nextGaussian() * 0.25), 1, 0.05, 0.05, 0.05, 0);
            if (now % 6 == 0) BossFx.dust(now0.clone().add(rng.nextGaussian() * 0.3, 0.4 + rng.nextDouble(), rng.nextGaussian() * 0.3), INK, 0.9f, 1, 0.05);
        }
        if (now % 5 == 0 && services.effects().has(d.obj.entity(), "mark")) {
            // 사냥꾼 표식은 진짜에만 남는다 — 분신에 걸면 먹물에 번져 지워진다
            services.effects().clear(d.obj.entity(), "mark");
            BossFx.particle(Particle.SQUID_INK, now0.clone().add(0, 3.2, 0), 20, 0.3, 0.3, 0.3, 0.05);
            broadcastBar("<gray>표식이 먹물에 번져 흐려진다…");
        }
        if (now % 20 == 0) d.rig.nameplate(Text.mm(plateText()));
    }

    private RigMath.AnimState animState(InkDouble d, Player t, Location at) {
        int atk = now - d.attackTick <= RigMath.ATTACK_TICKS + 2 ? (int) (now - d.attackTick) : -1;
        float headYaw = 0, headPitch = 0;
        if (t != null) {
            Vector v = t.getEyeLocation().toVector().subtract(at.clone().add(0, 1.62 * def.scale(), 0).toVector());
            headYaw = BossMath.yawDelta(d.yaw, BossMath.yawOf(v.getX(), v.getZ()));
            double h = Math.hypot(v.getX(), v.getZ());
            headPitch = (float) Math.toDegrees(Math.atan2(-v.getY(), Math.max(0.1, h)));
        }
        return new RigMath.AnimState(now, d.moveSpeed, atk, 2, -1, -1, headYaw, headPitch, -1, t != null, d.seed);
    }

    private Player nearest(Location l) {
        Player best = null;
        double bd = Double.MAX_VALUE;
        for (Player p : targets()) {
            double d2 = p.getLocation().distanceSquared(l);
            if (d2 < bd) {
                bd = d2;
                best = p;
            }
        }
        return best;
    }

    private static boolean passable(Location l) {
        return l.getBlock().isPassable() && l.clone().add(0, 1, 0).getBlock().isPassable();
    }

    /** 분신의 기본 휘두르기 (진짜처럼 보이도록 — 보스 기본 공격 × double_damage_mult). */
    private void doubleSwing(InkDouble d, Player t, Params p) {
        d.nextSwing = now + 40;
        d.attackTick = now;
        double dm = damage() * p.dbl("double_damage_mult", 0.5);
        UUID id = t.getUniqueId();
        after(3, () -> {
            Player pl = Bukkit.getPlayer(id);
            if (d.dead || pl == null || !validPlayer(pl) || horizontal(d.obj.at(), pl.getLocation()) > reach() + 0.8) return;
            hit(pl, dm, "ink_double", DamageType.MELEE);
            BossFx.sound(pl.getLocation(), Sound.ENTITY_PLAYER_ATTACK_STRONG, 0.8f, 0.6f);
        });
    }

    /** 분신의 약한 패턴: 가까우면 먹물 채찍, 멀면 3갈래 깃펜 (피해 × double_damage_mult). */
    private void doubleAttack(InkDouble d, Player t, double dist, Params p) {
        Params lash = def.pattern("ink_lash");
        Params quill = def.pattern("quill_barrage");
        double mult = p.dbl("double_damage_mult", 0.5);
        Location from = ground(d.obj.at());
        Vector dir = dirTo(from, t.getLocation());
        d.yaw = BossMath.yawOf(dir.getX(), dir.getZ());
        double len = Math.max(3, lash.dbl("length", 6) - 1);
        if (dist <= len + 1 && (d.lashNext || dist < 4)) {
            int w = windup(lash, 1.0);
            Telegraph.Shape cone = Telegraph.Shape.cone(from, dir, lash.dbl("angle", 90), len);
            double dm = dmg(lash, "damage", 1.4) * mult;
            d.pending.add(telegraph(cone, w, Telegraph.RED, null, () -> {
                if (d.dead) return;
                hitShape(cone, dm, "ink_doubles", DamageType.MELEE, null);
                lashFx(cone);
            }));
            d.rig.play(BossAnim.SWEEP, w + 6, w / (double) (w + 6), now);
            d.busyUntil = now + w + 6;
        } else {
            int w = windup(quill, 0.8);
            fan(from, dir, p.integer("double_quills", 3), p.dbl("double_spread", 30), quill, dmg(quill, "damage", 0.7) * mult,
                    "ink_doubles", w, d.pending);
            d.rig.play(BossAnim.THROW, w + 6, w / (double) (w + 6), now);
            d.busyUntil = now + w + 4;
        }
        d.lashNext = !d.lashNext;
        double min = p.dbl("double_attack_min", 3.5), max = Math.max(min, p.dbl("double_attack_max", 6.0));
        d.nextAttack = now + Math.round((min + rng.nextDouble() * (max - min)) * 20 * scaling().cooldownMult());
    }

    private static Particle particleOf(String name, Particle def) {
        if (name == null) return def;
        try {
            return Particle.valueOf(name.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return def;
        }
    }

    // ── 정리 ─────────────────────────────────────────────────────────────

    @Override
    protected void onEnd() {
        clearDoubles(0);
        if (index != null) index.abort();
        index = null;
        for (Shelf s : shelves) {
            if (s.hit != null) s.hit.remove();
            s.hit = null;
        }
        hoverTarget = null;
        hideTimerBar();
        if (entity.isValid()) entity.setGravity(true);
    }
}
