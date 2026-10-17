package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.bosses.Boss;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.bosses.BossFx;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.Mechanics;
import kr.labyrinth.bosses.Telegraph;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;

/**
 * 지하 3층 — 균사의 왕 무르노크 (GDD §7.3, core {@code stack_spread}).
 * 핵심: 포자 낙인(흩어지기 — 낙인마다 r5 폭발, 겹친 사람도 맞음, 자리에 독 웅덩이) / 공생의 꽃(모이기 — 총 피해를 원 안 인원수로 나눔).
 * 2페이즈부터 둘을 동시에(꽃은 3초 늦게), 3페이즈엔 균사망이 타일을 감염시키며 번진다.
 * 대응 (GDD §8.6): 못 닿는 구석에서 맞으면 구석 낙인 — 그 자리에 독 포자 웅덩이(낙인 웅덩이 수치 그대로) + 그 대상에게 포자 낙인.
 */
public final class Floor03Boss extends Boss {

    // 균사망 타일 격자
    private double gridX, gridZ, tileSize;
    private int gridN;
    private final Set<Long> validTiles = new HashSet<>();
    private final Map<Long, ItemDisplay> infected = new HashMap<>();
    private long nextSpread;
    /** 포자 낙인이 터지는 틱 (대상별) — 이미 낙인이 있는 사람에게는 구석 낙인을 다시 걸지 않는다. */
    private final Map<java.util.UUID, Long> brandedUntil = new HashMap<>();

    public Floor03Boss(Init init) { super(init); }

    @Override
    protected void onSpawn() {
        Params p = def.pattern("mycelium_network");
        tileSize = Math.max(2, p.dbl("tile_size", 3));
        gridN = (int) Math.ceil(arenaRadius * 2 / tileSize);
        gridX = center.getX() - gridN * tileSize / 2.0;
        gridZ = center.getZ() - gridN * tileSize / 2.0;
        for (int i = 0; i < gridN; i++) {
            for (int j = 0; j < gridN; j++) {
                double cx = gridX + (i + 0.5) * tileSize, cz = gridZ + (j + 0.5) * tileSize;
                if (Math.hypot(cx - center.getX(), cz - center.getZ()) <= arenaRadius - tileSize * 0.4) validTiles.add(key(i, j));
            }
        }
    }

    private static long key(int i, int j) { return ((long) i << 32) | (j & 0xffffffffL); }

    @Override
    protected boolean canUse(String key) { return target() != null; }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "cap_slam" -> capSlam();
            case "puffball_toss" -> puffballToss();
            case "spore_brand" -> {
                List<Player> branded = sporeBrand(0, null, null);
                yield branded.isEmpty() ? 0 : cast("spore_brand", "포자 낙인", 20, 24, BossAnim.CAST, null, false);
            }
            case "symbiosis_bloom" -> {
                boolean ok = symbiosisBloom(0, List.of());
                yield ok ? cast("symbiosis_bloom", "공생의 꽃", 20, 24, BossAnim.CAST, null, false) : 0;
            }
            case "brand_and_bloom" -> brandAndBloom();
            default -> 0;
        };
    }

    // ── 갓 내려찍기 / 독 포자 투척 ───────────────────────────────────────

    private int capSlam() {
        Params p = def.pattern("cap_slam");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 1.2);
        double r = p.dbl("radius", 5);
        Telegraph.Shape c = Telegraph.Shape.circle(ground(t.getLocation()), r);
        double dmg = dmg(p, "damage", 1.5);
        telegraph(c, w, Telegraph.RED, null, () -> {
            hitShape(c, dmg, "cap_slam", DamageType.MELEE, pl -> push(pl, pl.getLocation().toVector().subtract(c.origin().toVector()), 0.5, 0.35));
            BossFx.sound(c.origin(), Sound.BLOCK_MUD_BREAK, 2f, 0.4f);
            BossFx.sound(c.origin(), Sound.ENTITY_GENERIC_EXPLODE, 0.8f, 0.8f);
            BossFx.particle(Particle.CRIMSON_SPORE, c.origin().clone().add(0, 0.6, 0), 80, r * 0.5, 0.4, r * 0.5, 0.02);
            BossFx.ring(c.origin(), r, Particle.CLOUD, 28);
        });
        return cast("cap_slam", "갓 내려찍기", w, w + 10, BossAnim.SLAM, t.getLocation(), false);
    }

    private int puffballToss() {
        Params p = def.pattern("puffball_toss");
        Player t = "farthest".equals(p.str("target", "farthest")) ? farthest() : randomTarget();
        if (t == null) return 0;
        int w = windup(p, 0.9);
        double r = p.dbl("radius", 3);
        Location at = ground(t.getLocation());
        Telegraph.Shape c = Telegraph.Shape.circle(at, r);
        double dmg = dmg(p, "damage", 1.2);
        Location hand = entity.getLocation().add(0, 2.6, 0);
        run(new Mechanics.Projectile(fx, "proj_spore", 1.4f, Mechanics.Projectile.lob(hand, at.clone().add(0, 0.4, 0), w, 4.5), w, 0, false,
                Particle.SPORE_BLOSSOM_AIR, List::of, pl -> { }, null));
        telegraph(c, w, Telegraph.RED, null, () -> {
            hitShape(c, dmg, "puffball_toss", DamageType.MAGIC, pl -> effect(pl, p.str("effect", "poison"), p.dbl("effect_duration", 3), 0));
            BossFx.particle(Particle.SPORE_BLOSSOM_AIR, at.clone().add(0, 0.8, 0), 60, r * 0.5, 0.6, r * 0.5, 0);
            BossFx.particle(Particle.SNEEZE, at.clone().add(0, 0.5, 0), 30, r * 0.4, 0.3, r * 0.4, 0.05);
            BossFx.sound(at, Sound.ENTITY_PUFFER_FISH_BLOW_UP, 1.5f, 0.5f);
        });
        return cast("puffball_toss", "독 포자 투척", Math.min(w, 16), 18, BossAnim.THROW, t.getLocation(), false);
    }

    // ── 포자 낙인 (흩어지기) ─────────────────────────────────────────────

    /**
     * @param extraDelay 추가 지연 틱 (조합 패턴용)
     * @param forced     낙인 대상을 정해 줌 (대응), null = 무작위 count 명
     * @param notice     대상에게 보일 공지 (null = 원래 문구)
     * @return 낙인 대상
     */
    private List<Player> sporeBrand(int extraDelay, List<Player> forced, String notice) {
        Params p = def.pattern("spore_brand");
        int count = scaling().count(p, "count", 1, p.integer("max", 5));
        List<Player> ts = forced != null ? new ArrayList<>(forced) : pickTargets(count, null, false);
        if (ts.isEmpty()) return ts;
        int dur = windupSec(p.dbl("duration", 5.0)) + extraDelay;
        double r = p.dbl("radius", 5);
        double dmg = dmg(p, "damage", 1.6);
        String marker = p.str("fx", "marker_spread");
        for (Player t : ts) {
            brandedUntil.put(t.getUniqueId(), now + dur);
            notify(t, notice != null ? notice : "<blue><b>포자 낙인!</b></blue> <gray>몸 안에서 무언가 부풀어 오른다…");
            run(new Mechanics.Marker(fx, marker, t, dur, null));
            Telegraph tg = new Telegraph(fx, Telegraph.Shape.circle(ground(t.getLocation()), r), dur, Telegraph.BLUE, "", null);
            tg.follow(t);
            run(tg);
            after(dur, () -> {
                if (!validPlayer(t)) return;
                Location at = ground(t.getLocation());
                Telegraph.Shape boom = Telegraph.Shape.circle(at, r);
                hitShape(boom, dmg, "spore_brand", DamageType.MAGIC, null);
                BossFx.particle(Particle.SPORE_BLOSSOM_AIR, at.clone().add(0, 1, 0), 80, r * 0.5, 0.8, r * 0.5, 0);
                BossFx.dust(at.clone().add(0, 1, 0), Telegraph.BLUE, 2f, 40, r * 0.4);
                BossFx.sound(at, Sound.ENTITY_GENERIC_EXPLODE, 1f, 1.3f);
                sporePatch(at, p);
            });
        }
        BossFx.sound(entity.getLocation(), Sound.BLOCK_SCULK_SENSOR_CLICKING, 1.6f, 0.5f);
        return ts;
    }

    /** 독 포자 웅덩이 (낙인 웅덩이 수치: patch_radius · patch_duration · 20틱마다 patch_damage TRUE + 독 2초). */
    private void sporePatch(Location at, Params p) {
        double patchR = p.dbl("patch_radius", 3);
        double patchDmg = dmg(p, "patch_damage", 0.2);
        run(new Mechanics.Zone(fx, Telegraph.Shape.circle(at, patchR), ticks(p.dbl("patch_duration", 10)), 20, "telegraph_circle",
                Telegraph.GREEN, Particle.SPORE_BLOSSOM_AIR, this::players, pl -> {
            hit(pl, patchDmg, "spore_patch", DamageType.TRUE);
            effect(pl, "poison", 2, 0);
        }));
    }

    // ── 대응: 구석 낙인 (GDD §8.6) ───────────────────────────────────────

    /**
     * 못 닿는 구석에서 맞으면: 대상 발 자리에 초록 원이 1초 자라난 뒤 독 포자 웅덩이(10초)가 남고, 같은 순간 그 대상 한 명에게
     * 포자 낙인(5초 뒤 r5 폭발 + 그 자리 웅덩이). 그 구석은 10초 동안 막힌다. 이미 낙인이 있으면 지금은 못 함(0).
     */
    @Override
    protected int answer(Answer a) {
        Player t = a.target();
        if (t == null || !t.isValid()) return 0;
        if (brandedUntil.getOrDefault(t.getUniqueId(), Long.MIN_VALUE) > now) return 0;
        Params p = def.pattern("spore_brand");
        Location pocket = ground(t.getLocation());
        int pw = windupSec(answerDef().dbl("patch_windup", 1.0));
        double r = p.dbl("patch_radius", 3);
        Telegraph grow = new Telegraph(fx, Telegraph.Shape.circle(pocket, r), pw, Telegraph.GREEN, null, () -> {
            sporePatch(pocket, p);
            BossFx.particle(Particle.SPORE_BLOSSOM_AIR, pocket.clone().add(0, 0.8, 0), 40, r * 0.5, 0.5, r * 0.5, 0);
            BossFx.sound(pocket, Sound.BLOCK_SCULK_SPREAD, 1.4f, 0.6f);
        });
        grow.onTick(g -> {
            if (g.elapsed() % 3 == 0) {
                double f = Math.min(1.0, (g.elapsed() + 1) / (double) Math.max(1, g.total()));
                BossFx.dustRing(pocket.clone().add(0, 0.15, 0), Math.max(0.4, r * f), Telegraph.GREEN, 1.3f, 18);
            }
        });
        run(grow);
        sporeBrand(0, List.of(t), "<blue><b>포자 낙인!</b></blue> <gray>발밑에서 균사가 피어오른다…");
        return cast("spore_brand", "구석 낙인", 20, 24, BossAnim.CAST, t.getLocation(), false);
    }

    // ── 공생의 꽃 (모이기) ───────────────────────────────────────────────

    private boolean symbiosisBloom(int extraDelay, List<Player> avoid) {
        Params p = def.pattern("symbiosis_bloom");
        List<Player> pick = pickTargets(1, avoid, false);
        if (pick.isEmpty()) pick = pickTargets(1, null, false);
        if (pick.isEmpty()) return false;
        Player t = pick.get(0);
        int dur = windupSec(p.dbl("duration", 5.0)) + extraDelay;
        double r = p.dbl("radius", 3);
        String marker = p.str("fx", "marker_stack");
        run(new Mechanics.Marker(fx, marker, t, dur, null));
        Telegraph tg = new Telegraph(fx, Telegraph.Shape.circle(ground(t.getLocation()), r), dur, Telegraph.YELLOW, "", null);
        tg.follow(t);
        run(tg);
        broadcastBar("<yellow><b>공생의 꽃 — " + t.getName() + "</b></yellow> <gray>홀로 피기엔 너무 무거운 꽃이다…");
        after(dur, () -> {
            if (!validPlayer(t)) return;
            Location at = ground(t.getLocation());
            Telegraph.Shape bloom = Telegraph.Shape.circle(at, r);
            List<Player> inside = new ArrayList<>();
            for (Player pl : players()) if (bloom.contains(pl.getLocation())) inside.add(pl);
            double each;
            if (scaling().solo()) each = dmg(p, "solo_damage", 1.4);
            else {
                double total = damage() * (p.dbl("total_damage", 6.0) + p.dbl("total_per_member", 1.0) * (partySize() - 1));
                each = BossMath.shareDamage(total, inside.size(), p.integer("min_share", 1));
            }
            for (Player pl : inside) hit(pl, each, "symbiosis_bloom", DamageType.MAGIC);
            BossFx.particle(Particle.FIREWORK, at.clone().add(0, 1, 0), 40, r * 0.5, 0.6, r * 0.5, 0.05);
            BossFx.dust(at.clone().add(0, 1, 0), Telegraph.YELLOW, 2f, 40, r * 0.4);
            BossFx.sound(at, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 2f, 0.6f);
            if (!scaling().solo()) broadcastBar("<yellow>공생의 꽃</yellow> <gray>꽃잎이 " + inside.size() + "갈래로 흩어졌다");
        });
        return true;
    }

    private int brandAndBloom() {
        Params p = def.pattern("brand_and_bloom");
        List<Player> branded = sporeBrand(0, null, null);
        int delay = ticks(p.dbl("bloom_delay", 3.0));
        boolean bloom = symbiosisBloom(delay, branded);
        if (branded.isEmpty() && !bloom) return 0;
        broadcastBar("<blue>낙인</blue><gray>과</gray> <yellow>꽃</yellow><gray>이 함께 깨어난다…</gray>");
        return cast("brand_and_bloom", "낙인과 꽃", 24, 28, BossAnim.ROAR, null, false);
    }

    // ── 균사망 (3페이즈 상시) ────────────────────────────────────────────

    @Override
    protected void tickSystem(String key) {
        if (!key.equals("mycelium_network")) return;
        Params p = def.pattern(key);
        if (now >= nextSpread) {
            nextSpread = now + ticks(p.dbl("spread_interval", 4));
            spread(p);
        }
        if (now % 20 == 0) infectPlayers(p);
        if (now % 10 == 0) {
            for (Long k : infected.keySet()) {
                if (rng.nextDouble() < 0.12) {
                    int i = (int) (k >> 32), j = (int) (long) k;
                    BossFx.particle(Particle.CRIMSON_SPORE, new Location(center.getWorld(), gridX + (i + 0.5) * tileSize, center.getY() + 0.3,
                            gridZ + (j + 0.5) * tileSize), 2, tileSize * 0.3, 0.1, tileSize * 0.3, 0);
                }
            }
        }
    }

    private void spread(Params p) {
        double max = p.dbl("max_coverage", 0.45);
        int cap = (int) Math.floor(validTiles.size() * max);
        if (infected.size() >= cap) return;
        List<Long> add = new ArrayList<>();
        if (infected.isEmpty()) {
            List<Long> all = new ArrayList<>(validTiles);
            java.util.Collections.shuffle(all, rng);
            int seeds = Math.min(all.size(), 2 + scaling().extraCount());
            add.addAll(all.subList(0, seeds));
            broadcastBar("<dark_purple><b>균사망이 바닥을 타고 번진다…</b></dark_purple>");
        } else {
            int step = Math.max(1, (int) Math.ceil(validTiles.size() * 0.06));
            List<Long> frontier = new ArrayList<>();
            for (Long k : infected.keySet()) {
                int i = (int) (k >> 32), j = (int) (long) k;
                int[][] nb = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                for (int[] d : nb) {
                    long n = key(i + d[0], j + d[1]);
                    if (validTiles.contains(n) && !infected.containsKey(n) && !frontier.contains(n)) frontier.add(n);
                }
            }
            java.util.Collections.shuffle(frontier, rng);
            add.addAll(frontier.subList(0, Math.min(step, frontier.size())));
        }
        for (Long k : add) {
            if (infected.size() >= cap) break;
            int i = (int) (k >> 32), j = (int) (long) k;
            Location corner = new Location(center.getWorld(), gridX + i * tileSize, center.getY(), gridZ + j * tileSize);
            Location g = ground(corner.clone().add(tileSize / 2, 0, tileSize / 2));
            corner.setY(g.getY());
            ItemDisplay d = fx.plate(Telegraph.Shape.tile(corner, tileSize), def.pattern("mycelium_network").str("fx", "telegraph_tile"));
            infected.put(k, d);
        }
        if (!add.isEmpty()) BossFx.sound(center, Sound.BLOCK_SCULK_SPREAD, 1.5f, 0.6f);
    }

    private void infectPlayers(Params p) {
        int perSec = Math.max(1, p.integer("infection_per_second", 1));
        int max = p.integer("infection_max", 5);
        for (Player pl : players()) {
            Location l = pl.getLocation();
            int i = BossMath.tileOf(gridX, tileSize, l.getX()), j = BossMath.tileOf(gridZ, tileSize, l.getZ());
            if (!infected.containsKey(key(i, j)) || Math.abs(l.getY() - center.getY()) > 1.5) continue;
            int before = services.effects().stacks(pl, "infection");
            effect(pl, "infection", 8, perSec);
            int after = services.effects().stacks(pl, "infection");
            if (before >= max - perSec && after < before) {
                // 5중첩 폭발: 상태이상 서비스가 2초 속박 + 기본 피해를 주고, 보스 패턴 배율(1.2)까지 나머지를 더한다
                hit(pl, dmg(p, "burst_damage", 1.2) * (1.0 / 3.0), "mycelium_burst", DamageType.TRUE);
                effect(pl, "root", p.dbl("root", 2.0), 1);
            } else if (after > 0) {
                notify(pl, "<dark_purple>감염</dark_purple> <dark_purple>" + "●".repeat(Math.min(after, max)) + "<dark_gray>" + "○".repeat(Math.max(0, max - after)));
            }
        }
    }

    @Override
    protected void onEnd() {
        for (Entity e : infected.values()) fx.discard(e);
        infected.clear();
    }
}
