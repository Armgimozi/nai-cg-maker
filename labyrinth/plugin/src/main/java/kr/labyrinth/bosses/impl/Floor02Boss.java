package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
import kr.labyrinth.content.Params;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 지하 2층 — 실잣는 여왕 베셀라 (GDD §7.2, core {@code tether}).
 * 핵심: 은실 테더 — 묶인 두 사람이 6초 안에 12칸 이상 떨어져 1.5초 유지하면 끊김, 실패하면 서로 끌려가 충돌(1.5배 + 속박).
 * 홀수·솔로의 남는 사람은 아레나 가장자리 은실 말뚝에 묶인다.
 * 패턴: venom_spit(선 → 착탄 원 + 독 웅덩이) · foreleg_sweep(부채꼴 120°) · silk_tether(20초 간격) ·
 * egg_sacs(벽 둥지 알주머니, 15초 안에 못 깨면 부화) · ceiling_ambush(천장 매복 → 낙하) · cocoon(고치 — 동료가 깨기, 솔로는 웅크리기 연타).
 * 대응 (GDD §8.6): 못 닿는 틈에서 맞으면 짧은 천장 낙하 — 원은 그 순간 대상 발 자리에 고정, 몸은 대상 옆 설 자리에 내려앉는다
 * (설 자리가 없으면 독침).
 */
public final class Floor02Boss extends Boss {

    private final List<Location> nests = new ArrayList<>();
    /** 고치에 갇힌 플레이어 → 고치. */
    private final Map<UUID, ObjectTarget> cocoons = new HashMap<>();
    private final Map<UUID, Location> cocoonAt = new HashMap<>();
    private boolean airborne;
    /** 공중에 있을 때 내려앉을 자리 (대응 = 대상 옆 설 자리, 로테이션 = 원 가운데). 페이즈 전환·안전 착지가 쓴다. */
    private Location landAt;

    public Floor02Boss(Init init) { super(init); }

    @Override
    protected void onSpawn() {
        int n = Math.max(2, def.arena().integer("nests", 4));
        double r = arenaRadius - 1.6;
        for (double a : BossMath.ringAngles(n, 90, 26)) {
            if (BossMath.angleGap(a, 270) < 14) a += 18;
            Location l = ringPoint(a, r);
            l.setY(center.getY());
            nests.add(l);
            BossFx.particle(Particle.WHITE_ASH, l.clone().add(0, 1.5, 0), 20, 0.6, 1, 0.6, 0);
        }
    }

    @Override
    protected boolean canUse(String key) {
        if (airborne) return false;
        if (key.equals("egg_sacs")) {
            Params p = def.pattern(key);
            return aliveAdds(p.str("add", "silk_hatchling")) < p.integer("max_alive", 14);
        }
        if (key.equals("cocoon")) return !targets().isEmpty() && cocoons.isEmpty();
        return target() != null;
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "venom_spit" -> venomSpit();
            case "foreleg_sweep" -> forelegSweep();
            case "egg_sacs" -> eggSacs();
            case "ceiling_ambush" -> ceilingAmbush();
            case "cocoon" -> cocoon();
            default -> 0;
        };
    }

    @Override
    protected void runInterval(String key) {
        if (key.equals("silk_tether")) silkTether();
    }

    // ── 독침 ─────────────────────────────────────────────────────────────

    private int venomSpit() {
        Player t = scaling().solo() ? target() : randomTarget();
        return t == null ? 0 : venomSpit(t);
    }

    private int venomSpit(Player t) {
        Params p = def.pattern("venom_spit");
        int w = windup(p, 0.8);
        Location impact = ground(t.getLocation());
        Location mouth = entity.getLocation().add(facingTo(impact).multiply(1.2)).add(0, 1.1, 0);
        double dist = Math.max(1, Math.hypot(impact.getX() - mouth.getX(), impact.getZ() - mouth.getZ()));
        Telegraph.Shape line = Telegraph.Shape.line(feet(), facingTo(impact), dist, 1.2);
        double r = p.dbl("pool_radius", 2.0);
        Telegraph.Shape circle = Telegraph.Shape.circle(impact, r);
        double dmg = dmg(p, "damage", 1.0);
        telegraph(line, w, Telegraph.RED, null, null);
        telegraph(circle, w, Telegraph.RED, null, () -> {
            double speed = p.dbl("speed", 0.9) * scaling().speedMult();
            int travel = Math.max(2, (int) Math.ceil(dist / speed));
            run(new Mechanics.Projectile(fx, "proj_web", 1.2f, Mechanics.Projectile.lob(mouth, impact.clone().add(0, 0.3, 0), travel, 1.2),
                    travel, 0.4, false, Particle.ITEM_SLIME, this::players, pl -> { }, at -> {
                hitShape(circle, dmg, "venom_spit", DamageType.MAGIC,
                        pl -> effect(pl, p.str("effect", "poison"), p.dbl("effect_duration", 3), 0));
                BossFx.sound(impact, Sound.ENTITY_SLIME_SQUISH, 1.4f, 0.6f);
                BossFx.particle(Particle.ITEM_SLIME, impact.clone().add(0, 0.3, 0), 20, r * 0.5, 0.2, r * 0.5, 0.05);
                double poolDmg = dmg(p, "pool_damage", 0.3);
                run(new Mechanics.Zone(fx, circle, ticks(p.dbl("pool_duration", 6)), 20, "telegraph_circle", Telegraph.GREEN,
                        Particle.ITEM_SLIME, this::players, pl -> hit(pl, poolDmg, "venom_pool", DamageType.TRUE)));
            }));
            BossFx.sound(mouth, Sound.ENTITY_LLAMA_SPIT, 1.4f, 0.5f);
        });
        return cast("venom_spit", "독침", w, w + 6, BossAnim.THROW, impact, false);
    }

    private Vector facingTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    // ── 앞다리 휩쓸기 ────────────────────────────────────────────────────

    private int forelegSweep() {
        Params p = def.pattern("foreleg_sweep");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 0.9);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), facingTo(t.getLocation()), p.dbl("angle", 120), p.dbl("length", 5));
        double dmg = dmg(p, "damage", 1.4);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "foreleg_sweep", DamageType.MELEE, pl -> push(pl, pl.getLocation().toVector().subtract(cone.origin().toVector()), 0.6, 0.3));
            BossFx.sound(entity.getLocation(), Sound.ENTITY_SPIDER_HURT, 1.4f, 0.4f);
            BossFx.particle(Particle.SWEEP_ATTACK, cone.origin().clone().add(cone.direction().multiply(2)).add(0, 1, 0), 3, 1, 0.2, 1, 0);
        });
        return cast("foreleg_sweep", "앞다리 휩쓸기", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 은실 테더 (핵심) ─────────────────────────────────────────────────

    private void silkTether() {
        Params p = def.pattern("silk_tether");
        List<Player> list = targets();
        if (list.isEmpty() || airborne) return;
        java.util.Collections.shuffle(list, rng);
        int contract = ticks(p.dbl("contract_time", 6.0) * scaling().timerMult());
        double snap = p.dbl("snap_distance", 12);
        int hold = ticks(p.dbl("snap_hold", 1.5));
        String model = p.str("fx", "tether_silk");
        int i = 0;
        for (; i + 1 < list.size(); i += 2) tetherPair(list.get(i), list.get(i + 1), p, contract, snap, hold, model);
        if (i < list.size() && p.bool("solo_anchor", true)) {
            Player lone = list.get(i);
            double a = rng.nextDouble() * 360;
            Location post = ringPoint(a, Math.min(arenaRadius - 1.5, p.dbl("anchor_ring_radius", 12)));
            post.setY(center.getY());
            tetherPost(lone, post, p, contract, snap, hold, model);
        }
        BossFx.sound(entity.getLocation(), Sound.ENTITY_SPIDER_AMBIENT, 1.6f, 0.5f);
        rig.play(BossAnim.CAST, 24, now);
    }

    private void tetherPair(Player a, Player b, Params p, int contract, double snap, int hold, String model) {
        notify(a, "<white><b>은실이 감겼다!</b></white> <gray>" + b.getName() + " 쪽으로 실이 서서히 조여 온다…");
        notify(b, "<white><b>은실이 감겼다!</b></white> <gray>" + a.getName() + " 쪽으로 실이 서서히 조여 온다…");
        final int[] held = {0};
        final int[] pulling = {-1};
        run(new Mechanics.Tether(fx, model, () -> a.getLocation().add(0, 1.1, 0), () -> b.getLocation().add(0, 1.1, 0), t -> {
            if (!validPlayer(a) || !validPlayer(b)) return false;
            double d = a.getLocation().distance(b.getLocation());
            if (pulling[0] >= 0) {
                pulling[0]++;
                Location mid = a.getLocation().add(b.getLocation()).multiply(0.5);
                pullHard(a, mid);
                pullHard(b, mid);
                if (d < 2.2 || pulling[0] > 16) {
                    collide(p, a);
                    collide(p, b);
                    BossFx.sound(mid, Sound.BLOCK_WOOL_BREAK, 1.5f, 0.5f);
                    return false;
                }
                return true;
            }
            held[0] = d >= snap ? held[0] + 1 : Math.max(0, held[0] - 2);
            if (held[0] >= hold) {
                snapFx(a.getLocation().add(b.getLocation()).multiply(0.5));
                notify(a, "<green>은실이 끊어졌습니다!</green>");
                notify(b, "<green>은실이 끊어졌습니다!</green>");
                return false;
            }
            if (t % 5 == 0) {
                String bar = progress(d, snap, held[0], hold, contract - t);
                notify(a, bar);
                notify(b, bar);
                BossFx.dustLine(a.getLocation().add(0, 1.1, 0), b.getLocation().add(0, 1.1, 0), lerpColor(t / (double) contract), 0.8f, 1.5);
            }
            if (t >= contract) {
                pulling[0] = 0;
                BossFx.sound(a.getLocation(), Sound.ENTITY_SPIDER_STEP, 1.5f, 0.4f);
            }
            return true;
        }));
    }

    private void tetherPost(Player a, Location post, Params p, int contract, double snap, int hold, String model) {
        ItemDisplay pole = fx.model("chain_anchor", post, 1.6f, Display.Billboard.FIXED);
        notify(a, "<white><b>은실이 말뚝에 감겼다!</b></white> <gray>실이 서서히 조여 온다…");
        final int[] held = {0};
        final int[] pulling = {-1};
        Location top = post.clone().add(0, 1.4, 0);
        run(new Mechanics.Tether(fx, model, () -> top, () -> a.getLocation().add(0, 1.1, 0), t -> {
            if (!validPlayer(a)) {
                fx.discard(pole);
                return false;
            }
            double d = horizontal(a.getLocation(), post);
            if (pulling[0] >= 0) {
                pulling[0]++;
                pullHard(a, post);
                if (d < 2.0 || pulling[0] > 16) {
                    collide(p, a);
                    fx.discard(pole);
                    return false;
                }
                return true;
            }
            held[0] = d >= snap ? held[0] + 1 : Math.max(0, held[0] - 2);
            if (held[0] >= hold) {
                snapFx(top);
                notify(a, "<green>은실이 끊어졌습니다!</green>");
                fx.discard(pole);
                return false;
            }
            if (t % 5 == 0) notify(a, progress(d, snap, held[0], hold, contract - t));
            if (t >= contract) pulling[0] = 0;
            return true;
        }));
    }

    /** 은실 긴장 막대 (숫자·정답 없이 팽팽함만): 멀어질수록 차오르고, 끊어질 듯하면 초록, 버틴 만큼 흰 칸. */
    private static String progress(double d, double snap, int held, int hold, int leftTicks) {
        int cells = 8;
        int fill = (int) Math.round(Math.max(0, Math.min(1, d / Math.max(1, snap))) * cells);
        String col = d >= snap ? "<green>" : "<yellow>";
        String tension = col + "▰".repeat(fill) + "<dark_gray>" + "▱".repeat(cells - fill);
        int keep = hold <= 0 ? 0 : (int) Math.round(Math.min(1.0, held / (double) hold) * 3);
        return "<white>은실</white> " + tension + (keep > 0 ? " <white>" + "✦".repeat(keep) + "</white>" : "")
                + " <gray>⌛ " + String.format("%.1f", Math.max(0, leftTicks) / 20.0);
    }

    private static Color lerpColor(double f) {
        f = Math.max(0, Math.min(1, f));
        return Color.fromRGB(230, (int) (230 - 170 * f), (int) (240 - 200 * f));
    }

    private void pullHard(Player p, Location to) {
        Vector d = to.toVector().subtract(p.getLocation().toVector()).setY(0);
        double len = d.length();
        if (len < 0.4) return;
        p.setVelocity(d.multiply(Math.min(1.1, len * 0.4) / len).setY(0.1));
    }

    private void collide(Params p, Player pl) {
        hit(pl, dmg(p, "contract_damage", 1.5), "silk_tether", DamageType.MELEE);
        effect(pl, "root", p.dbl("root", 1.5), 1);
        BossFx.particle(Particle.WHITE_ASH, pl.getLocation().add(0, 1, 0), 30, 0.4, 0.6, 0.4, 0.02);
    }

    private void snapFx(Location at) {
        BossFx.sound(at, Sound.ITEM_LEAD_BREAK, 1.6f, 0.8f);
        BossFx.particle(Particle.END_ROD, at, 20, 0.4, 0.4, 0.4, 0.08);
    }

    // ── 알주머니 ─────────────────────────────────────────────────────────

    private int eggSacs() {
        Params p = def.pattern("egg_sacs");
        int count = Math.min(nests.size(), scaling().count(p, "count", 2, nests.size()));
        List<Location> free = new ArrayList<>(nests);
        java.util.Collections.shuffle(free, rng);
        int hatch = ticks(p.dbl("hatch_time", 15) * scaling().timerMult());
        String add = p.str("add", "silk_hatchling");
        int hatchlings = Math.max(1, (int) Math.round(p.scaled("hatchlings", partySize(), 3)) + scaling().extraCount());
        for (int i = 0; i < count; i++) {
            Location at = free.get(i).clone();
            ObjectTarget sac = spawnObject("egg_sac", "<#dfe6f2>알주머니</#dfe6f2>", at, scaling().objectHp(p, 220), p.str("fx", "egg_sac"),
                    1.5f, 1.3, 1.8);
            final boolean[] done = {false};
            sac.onDestroyed(h -> {
                done[0] = true;
                broadcastBar("<green>알주머니를 터뜨렸습니다!</green>");
            });
            run(new Mechanics.Repeat(hatch, 10, tt -> {
                if (done[0] || !sac.isAlive()) return false;
                int left = hatch - tt;
                sac.extra("<red>부화까지 " + String.format("%.0f", Math.ceil(left / 20.0)) + "초</red>");
                if (tt % 40 == 0) BossFx.sound(at, Sound.BLOCK_SNIFFER_EGG_CRACK, 0.9f, 0.6f + 0.6f * tt / (float) hatch);
                return true;
            }, () -> {
                if (done[0] || !sac.isAlive()) return;
                done[0] = true;
                Location l = sac.at();
                sac.remove();
                int room = Math.max(0, p.integer("max_alive", 14) - aliveAdds(add));
                int n = Math.min(room, hatchlings);
                for (int k = 0; k < n; k++) spawnAdd(add, l.clone().add(rng.nextGaussian() * 0.8, 0.1, rng.nextGaussian() * 0.8));
                BossFx.sound(l, Sound.ENTITY_TURTLE_EGG_HATCH, 1.6f, 0.6f);
                BossFx.particle(Particle.WHITE_ASH, l.clone().add(0, 1, 0), 40, 0.6, 0.6, 0.6, 0.05);
                broadcastBar("<red>알주머니가 터지며 새끼들이 쏟아진다!</red>");
            }, false));
        }
        broadcastBar("<white>벽 둥지에서 무언가 꿈틀거린다…</white>");
        return cast("egg_sacs", "알주머니", 20, 24, BossAnim.ROAR, null, false);
    }

    // ── 천장 매복 ────────────────────────────────────────────────────────

    private int ceilingAmbush() {
        Params p = def.pattern("ceiling_ambush");
        int w = windup(p, 2.0);
        int air = Math.max(ticks(p.dbl("airborne_time", 6)), w + 20);
        double r = p.dbl("radius", 4);
        double dmg = dmg(p, "damage", 2.0);
        rise(null, center.clone());
        after(air - w, () -> {
            Player t = scaling().solo() ? target() : randomTarget();
            Location at = t == null ? randomPoint(0, arenaRadius * 0.6) : ground(t.getLocation());
            Telegraph.Shape c = Telegraph.Shape.circle(at, r);
            telegraph(c, w, Telegraph.RED, null, () -> {
                Location land = c.origin().clone();
                land.setYaw(entity.getLocation().getYaw());
                land(land);
                slam(c, dmg, land, r);
            });
            if (t != null) notify(t, "<red><b>⚠ 머리 위!</b></red>");
        });
        safetyLanding(air + 10);
        return cast("ceiling_ambush", "천장 매복", air, air + 16, BossAnim.NONE, null, false);
    }

    /**
     * 대응 — 짧은 천장 낙하: 1초 동안 천장으로 → 그 순간 대상 발 자리에 원 r4 고정(경고 2초, 천장에서 은실이 늘어짐) →
     * 몸은 대상 옆 설 자리에 내려앉고 원 안 피해·밀침 (ceiling_ambush 수치 그대로).
     */
    private int ceilingDrop(Player t, Location spot) {
        Params p = def.pattern("ceiling_ambush");
        Params ad = answerDef();
        int w = windup(p, 2.0);
        int rise = Math.max(20, ticks(ad.dbl("rise", 1.0)));
        int air = rise + w;
        double r = p.dbl("radius", 4);
        double dmg = dmg(p, "damage", 2.0);
        Location from = entity.getLocation().clone();
        rise(t, spot);
        after(rise, () -> {
            if (!validPlayer(t)) return;
            Location at = ground(t.getLocation());
            Telegraph.Shape c = Telegraph.Shape.circle(at, r);
            Location ceiling = at.clone();
            ceiling.setY(Math.min(floorY + arenaHeight - 1, at.getY() + 9));
            Telegraph tg = new Telegraph(fx, c, w, Telegraph.RED, null, () -> {
                // 내려앉을 자리: 고른 설 자리 (그새 막혔으면 그 둘레, 그것도 없으면 뛰기 전 자리)
                Location land = bodyFits(spot) ? spot.clone() : nearestFit(spot, 2.0);
                if (land == null) land = from.clone();
                land.setYaw(BossMath.yawOf(at.getX() - land.getX(), at.getZ() - land.getZ()));
                land(land);
                slam(c, dmg, land, r);
            });
            tg.onTick(g -> {
                if (g.elapsed() % 3 == 0 && t.isValid()) {
                    Location head = t.getLocation().add(0, 2.0, 0);
                    BossFx.dustLine(ceiling, head, Color.fromRGB(235, 240, 255), 0.7f, 0.9);
                    if (g.elapsed() % 9 == 0) BossFx.particle(Particle.END_ROD, head.clone().add(0, 1.2, 0), 1, 0.05, 0.4, 0.05, 0);
                }
            });
            run(tg);
            notify(t, "<red><b>⚠ 머리 위!</b></red>");
        });
        safetyLanding(air + 10);
        return cast("ceiling_ambush", "천장 낙하", air, air + 16, BossAnim.NONE, null, false);
    }

    /** 천장으로: 도약 애니 → 1초 뒤 숨음·무적·중력 끔·위로. land = 안전 착지 자리. */
    private void rise(Player t, Location land) {
        airborne = true;
        landAt = land == null ? center.clone() : land.clone();
        setPathing(false);
        rig.play(BossAnim.LEAP, 24, now);
        BossFx.sound(entity.getLocation(), Sound.ENTITY_SPIDER_AMBIENT, 1.8f, 0.3f);
        after(20, () -> {
            setUntargetable(true);
            rig.setHidden(true);
            entity.setGravity(false);
            Location up = entity.getLocation().clone();
            up.setY(Math.min(floorY + arenaHeight - 3, floorY + 8));
            entity.teleport(up);
            broadcastBar("<gray>베셀라가 천장 어둠 속으로 사라졌다… 머리 위에서 실이 흔들린다</gray>");
            if (t != null) notify(t, "<gray>천장에서 실 한 가닥이 늘어진다…</gray>");
        });
    }

    /** 내려앉기: 몸 보임·중력·무적 풂·길찾기 켬, 블록에 끼었으면 빼냄. */
    private void land(Location at) {
        entity.teleport(at);
        entity.setGravity(true);
        rig.setHidden(false);
        rig.play(BossAnim.DROP, 24, now);
        setUntargetable(false);
        airborne = false;
        setPathing(true);
        unstick();
    }

    private void slam(Telegraph.Shape c, double dmg, Location land, double r) {
        Location o = c.origin();
        hitShape(c, dmg, "ceiling_ambush", DamageType.MELEE, pl -> push(pl, pl.getLocation().toVector().subtract(o.toVector()), 0.8, 0.4));
        BossFx.sound(land, Sound.ENTITY_GENERIC_EXPLODE, 1.2f, 0.6f);
        BossFx.particle(Particle.EXPLOSION, land.clone().add(0, 0.5, 0), 3, r * 0.4, 0.2, r * 0.4, 0);
    }

    /** 페이즈 전환 등으로 취소돼도 반드시 착지시키는 안전장치 (내려앉을 자리 = 설 자리 또는 원 가운데). */
    private void safetyLanding(int ticks) {
        afterPersistent(ticks, () -> {
            if (airborne) landNow();
        });
    }

    private void landNow() {
        Location at = landAt != null && landAt.getWorld() == entity.getWorld() ? landAt.clone() : center.clone();
        if (!bodyFits(at)) {
            Location near = nearestFit(at, 2.0);
            at = near != null ? near : center.clone();
        }
        at.setYaw(entity.getLocation().getYaw());
        land(at);
    }

    @Override
    protected void onPhase(int newPhase) {
        // 공중에서 페이즈가 바뀌면 (경고는 이미 정리됨) 곧바로 내려앉는다 — 숨은 채·무적인 채 남지 않게
        if (airborne) landNow();
    }

    // ── 대응 (GDD §8.6) ──────────────────────────────────────────────────

    @Override
    protected boolean canAnswer(Player t) {
        return !airborne && !cocoons.containsKey(t.getUniqueId());
    }

    @Override
    protected int answer(Answer a) {
        Player t = a.target();
        if (t == null || !t.isValid()) return 0;
        Location s = standSpot(t, ground(t.getLocation()), BossReach.Order.NEAR);
        if (s == null) {
            answerUses("venom_spit");
            return venomSpit(t);
        }
        return ceilingDrop(t, s);
    }

    // ── 고치 ─────────────────────────────────────────────────────────────

    private int cocoon() {
        Params p = def.pattern("cocoon");
        List<Player> all = targets();
        if (all.isEmpty()) return 0;
        int cap = scaling().solo() ? 1 : Math.max(1, all.size() - 1);
        int count = Math.min(cap, scaling().count(p, "count", 1, cap));
        List<Player> ts = pickTargets(count, null, true);
        int dur = ticks(p.dbl("duration", 8) * scaling().timerMult());
        double dot = dmg(p, "dot", 0.15);
        double fail = dmg(p, "fail_damage", 3.0);
        for (Player t : ts) encase(t, p, dur, dot, fail);
        return cast("cocoon", "고치", 16, 20, BossAnim.CAST, null, false);
    }

    private void encase(Player t, Params p, int dur, double dot, double fail) {
        Location at = t.getLocation().clone();
        ObjectTarget c = spawnObject("cocoon", "<#dfe6f2>" + t.getName() + "의 고치</#dfe6f2>", at, scaling().objectHp(p, 300),
                p.str("fx", "cocoon"), 1.15f, 1.0, 2.1);
        UUID id = t.getUniqueId();
        cocoons.put(id, c);
        cocoonAt.put(id, at);
        effect(t, "stun", dur / 20.0 + 0.5, 1);
        effect(t, "root", dur / 20.0 + 0.5, 1);
        notify(t, scaling().solo() ? "<white><b>고치에 갇혔다!</b></white> <gray>실이 온몸을 옥죈다… 몸부림쳐라"
                : "<white><b>고치에 갇혔다!</b></white> <gray>실 너머로 동료들의 그림자가 보인다…");
        broadcastBar("<white>" + t.getName() + " 이(가) 은실 고치에 감싸였다!</white>");
        BossFx.sound(at, Sound.BLOCK_WOOL_PLACE, 1.6f, 0.5f);
        final boolean[] freed = {false};
        c.onDestroyed(h -> {
            freed[0] = true;
            release(t, true);
        });
        run(new Mechanics.Repeat(dur, 1, tt -> {
            if (freed[0] || !c.isAlive()) return false;
            if (!validPlayer(t)) {
                c.remove();
                return false;
            }
            if (t.getLocation().distanceSquared(at) > 0.25) {
                Location back = at.clone();
                back.setYaw(t.getLocation().getYaw());
                back.setPitch(t.getLocation().getPitch());
                t.teleport(back);
            }
            if (tt % 20 == 0 && tt > 0) hit(t, dot, "cocoon", DamageType.TRUE);
            if (tt % 10 == 0) c.extra("<red>" + String.format("%.0f", Math.ceil((dur - tt) / 20.0)) + "초</red>");
            return true;
        }, () -> {
            if (freed[0]) return;
            freed[0] = true;
            if (c.isAlive()) {
                c.remove();
                if (validPlayer(t)) {
                    hit(t, fail, "cocoon_crush", DamageType.TRUE);
                    BossFx.sound(t.getLocation(), Sound.ENTITY_PLAYER_HURT_SWEET_BERRY_BUSH, 1.4f, 0.5f);
                }
            }
            release(t, false);
        }, false));
    }

    private void release(Player t, boolean rescued) {
        UUID id = t.getUniqueId();
        cocoons.remove(id);
        cocoonAt.remove(id);
        services.effects().clear(t, "stun");
        services.effects().clear(t, "root");
        if (rescued && t.isOnline()) {
            notify(t, "<green>고치에서 풀려났습니다!</green>");
            BossFx.particle(Particle.WHITE_ASH, t.getLocation().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.05);
        }
    }

    @Override
    protected void onSneak(Player p) {
        ObjectTarget c = cocoons.get(p.getUniqueId());
        if (c == null || !c.isAlive()) return;
        double per = def.pattern("cocoon").dbl("struggle_per_sneak", 0.1);
        // GDD: 솔로는 웅크리기 연타(1회당 10%). 파티에서도 1/4 효율로 몸부림 허용 (동료 구출이 주 해법)
        double ratio = scaling().solo() ? per : per * 0.25;
        c.chip(c.maxHealth() * ratio);
        BossFx.particle(Particle.WHITE_ASH, p.getLocation().add(0, 1, 0), 6, 0.3, 0.5, 0.3, 0.02);
        BossFx.sound(p.getLocation(), Sound.BLOCK_WOOL_HIT, 0.8f, 1.2f);
    }

    @Override
    protected void onEnd() {
        for (UUID id : new ArrayList<>(cocoons.keySet())) {
            Player p = org.bukkit.Bukkit.getPlayer(id);
            if (p != null) release(p, false);
        }
        if (airborne) entity.setGravity(true);
    }
}
