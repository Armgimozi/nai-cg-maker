package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
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
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Text;
import kr.labyrinth.mobs.ModelRig;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 지하 9층 — 시계탑의 간수 테오라 (GDD §7.9, core {@code timed_seals}).
 * 핵심: 시계판 아레나 중앙에서 바깥으로 뻗은 거대한 시곗바늘이 24초(2페이즈부터 16초)에 한 바퀴 돈다. 반경 12 링의 봉인석
 * 4개(12·3·6·9시, 6명 이상 6개)는 바늘이 지나는 ±1.5초 동안만 금색으로 열리고, 열린 봉인석에 1.5초 서 있으면
 * 종말 시계 +20초 · 보스 최대 HP 3% · 2초 기절. 닫힌 봉인석을 밟으면 "시간 역류" — 5초 전 자리로 되감기 + 1.0배 + 시계 −10초.
 * 3페이즈는 바늘이 반대로 돈다(소리 + 바늘 색으로 예고).
 * 보조: 종말 시계 {@code doom_clock} — 보스바 아래 4:00 카운트다운, 0 이면 "시간 종언"(전원 최대 HP 999%), 1분마다 보스 피해 +10%.
 * 패턴: hand_strike(부채꼴 90°) · pendulum_sweep(폭 3 차선 왕복 2회, 통과마다) · rewind_echo(각자 6초 전 자리 원 r2.5) ·
 * gear_storm(폭 2 선을 굴러가는 거대 톱니, 3 + ⌊(n−1)×0.34⌋줄).
 * <p>
 * 문구 규칙(GDD 보스 문구 규칙): 공지·이름표에는 분위기·단서만, 조작법은 bosses.yml {@code hints} 3단계로.
 */
public final class Floor09Boss extends Boss {

    private static final Color GOLD = Color.fromRGB(255, 205, 90);
    private static final Color BRASS = Color.fromRGB(232, 176, 96);
    private static final Color TEAL = Color.fromRGB(122, 224, 192);
    private static final Color RUST = Color.fromRGB(138, 90, 38);

    // ── 시곗바늘 ──
    private ItemDisplay hand;
    private String handModel;
    private double handDeg = ClockLogic.TWELVE;
    private int handDir = 1;
    private long handPauseUntil;
    private double handLen;
    private double handWidth;
    private Location hub;

    // ── 봉인석 ──
    private static final class Seal {
        final int index;
        final double deg;
        final Location at;
        ItemDisplay plate;
        TextDisplay label;
        String labelText;
        boolean open;
        boolean spent;

        Seal(int index, double deg, Location at) {
            this.index = index;
            this.deg = deg;
            this.at = at;
        }
    }

    private final List<Seal> seals = new ArrayList<>();
    private double sealRadius;
    /** 플레이어 → {봉인석 번호, 열린 봉인석 위에 선 틱}. */
    private final Map<UUID, int[]> standing = new HashMap<>();
    /** 플레이어 → 닫힌 봉인석 위에 있은 틱. */
    private final Map<UUID, Integer> closedTicks = new HashMap<>();
    private final Map<UUID, Long> reversalReady = new HashMap<>();

    // ── 종말 시계 ──
    private BossBar doomBar;
    private int doomStart;
    private int doomTicks;
    private long fightStart = -1;
    private long doomFlashUntil;
    private BossBar.Color doomFlash = BossBar.Color.WHITE;
    private final Set<UUID> doomViewers = new HashSet<>();

    // ── 위치 기록 (되감기 메아리·시간 역류) ──
    private final Map<UUID, PositionHistory> history = new HashMap<>();
    private int recordEvery = 10;
    private int historyCap = 20;

    public Floor09Boss(Init init) { super(init); }

    /** 종말 시계가 이 보스의 엔레이지 — 기본 광폭화 타이머는 bosses.yml {@code enrage} 를 따로 적었을 때만. */
    @Override
    protected double enrageSeconds() {
        return def.raw().has("enrage") ? super.enrageSeconds() : 0;
    }

    /** 1분마다 보스 피해 +damage_ramp_per_minute (종말 시계). */
    @Override
    protected double outgoingMult() {
        if (fightStart < 0) return 1.0;
        return ClockLogic.rampMult(now - fightStart, def.pattern("doom_clock").dbl("damage_ramp_per_minute", 0.10));
    }

    // ── 아레나 ───────────────────────────────────────────────────────────

    @Override
    protected void onSpawn() {
        fightStart = now;
        Params ts = def.pattern("timed_seals");
        hub = ground(center).add(0, 0.05, 0);

        // 봉인석 — 12시부터 시계 방향
        int count = ClockLogic.sealCount(partySize(), ts.integer("seals_base", 4), ts.integer("seals_at_six_or_more", 6));
        double ringR = Math.min(arenaRadius - 1.5, def.arena().dbl("seal_ring_radius", 12));
        sealRadius = ts.dbl("seal_radius", 1.6);
        double[] angs = ClockLogic.sealAngles(count);
        String closed = ts.str("fx_seal", "seal_glyph");
        for (int i = 0; i < angs.length; i++) {
            Seal s = new Seal(i, angs[i], ground(ringPoint(angs[i], ringR)));
            s.plate = fx.plate(Telegraph.Shape.circle(s.at, sealRadius), closed);
            seals.add(s);
            BossFx.particle(Particle.WAX_OFF, s.at.clone().add(0, 0.4, 0), 8, 0.6, 0.2, 0.6, 0.02);
        }

        // 시곗바늘 — 중앙에서 아레나 가장자리까지
        handModel = ts.str("fx_hand", "clock_hand");
        handLen = Math.max(4, arenaRadius - 0.5);
        handWidth = ts.dbl("hand_width", 1.2);
        hand = fx.plate(handShape(), handModel);

        // 종말 시계
        Params dc = def.pattern("doom_clock");
        doomStart = ClockLogic.doomStartTicks(dc.scaled("start_seconds", partySize(), 240), scaling().timerMult());
        doomTicks = doomStart;
        doomBar = BossBar.bossBar(Text.mm(doomTitle()), 1f, BossBar.Color.YELLOW, BossBar.Overlay.NOTCHED_10);
        refreshDoomViewers();

        // 위치 기록 간격 = rewind_echo.record_interval (0.5초)
        Params re = def.pattern("rewind_echo");
        double interval = Math.max(0.1, re.dbl("record_interval", 0.5));
        recordEvery = Math.max(2, ticks(interval));
        historyCap = PositionHistory.capacityFor(Math.max(re.dbl("delay", 6), ts.dbl("rewind_seconds", 5)) + 2, interval);

        BossFx.sound(center, Sound.BLOCK_BELL_USE, 2f, 0.5f);
        BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 1.4f, 0.6f);
        BossFx.dustRing(hub, ringR, BRASS, 1.4f, 64);
    }

    private Telegraph.Shape handShape() {
        Vector d = new Vector(BossMath.ax(handDeg), 0, BossMath.az(handDeg));
        return Telegraph.Shape.line(hub, d, handLen, handWidth);
    }

    // ── 매 틱 ────────────────────────────────────────────────────────────

    @Override
    protected void onTick() {
        if (now % recordEvery == 0) recordPositions();
        tickHand();
        tickSeals();
        tickDoom();
        if (now % 20 == 0) refreshDoomViewers();
        if (now % 12 == 0) {
            Location l = randomPoint(0, arenaRadius - 1).add(0, 1 + rng.nextDouble() * 5, 0);
            BossFx.dust(l, BRASS, 0.9f, 2, 0.6);
        }
    }

    private double handPeriod() {
        return def.pattern("timed_seals").phased("hand_period", phase(), 24);
    }

    private void tickHand() {
        if (now >= handPauseUntil) handDeg = BossMath.norm(handDeg + ClockLogic.degPerTick(handPeriod(), handDir));
        if (now % 2 == 0) fx.movePlate(hand, handShape());
        if (now % 4 == 0) {
            Location tip = hub.clone().add(BossMath.ax(handDeg) * handLen, 0.25, BossMath.az(handDeg) * handLen);
            BossFx.dust(tip, handDir > 0 ? GOLD : TEAL, 1.2f, 2, 0.15);
        }
        // 한 바퀴의 12시 — 낮은 종소리 (박자)
        double step = Math.abs(ClockLogic.degPerTick(handPeriod(), 1));
        if (step > 0 && now >= handPauseUntil && BossMath.angleGap(handDeg, ClockLogic.TWELVE) < step / 2 + 1e-6) {
            BossFx.sound(center, Sound.BLOCK_BELL_USE, 1.4f, 0.5f);
        }
    }

    // ── 시간 봉인 (핵심) ─────────────────────────────────────────────────

    private void tickSeals() {
        Params ts = def.pattern("timed_seals");
        int n = partySize();
        double window = ClockLogic.windowDeg(ts.scaled("window", n, 1.5), handPeriod());
        int standTicks = Math.max(4, ticks(ts.scaled("stand_time", n, 1.5)));
        int grace = Math.max(0, ticks(ts.dbl("closed_grace", 0.5)));
        for (Seal s : seals) {
            boolean open = now >= handPauseUntil && ClockLogic.isOpen(handDeg, s.deg, window);
            if (open != s.open) {
                s.open = open;
                if (open) {
                    s.spent = false;
                    BossFx.sound(s.at, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1.4f, 1.4f);
                    BossFx.sound(s.at, Sound.BLOCK_COPPER_BULB_TURN_ON, 1.0f, 1.2f);
                    BossFx.particle(Particle.WAX_ON, s.at.clone().add(0, 0.3, 0), 14, sealRadius * 0.5, 0.1, sealRadius * 0.5, 0.05);
                } else {
                    s.spent = false;
                    BossFx.sound(s.at, Sound.BLOCK_COPPER_BULB_TURN_OFF, 1.0f, 0.7f);
                }
                setModel(s.plate, sealModel(s));
            }
            if (s.open && !s.spent && now % 4 == 0) BossFx.dustRing(s.at.clone().add(0, 0.15, 0), sealRadius, GOLD, 1.1f, 18);
            if (!s.open && now % 20 == s.index % 20) BossFx.dustRing(s.at.clone().add(0, 0.1, 0), sealRadius * 0.8, RUST, 0.8f, 10);
        }

        Set<UUID> seen = new HashSet<>();
        Map<Integer, Integer> best = new HashMap<>();
        for (Player pl : players()) {
            UUID id = pl.getUniqueId();
            seen.add(id);
            Seal on = sealUnder(pl.getLocation());
            int[] st = standing.get(id);
            if (on == null) {
                standing.remove(id);
                closedTicks.remove(id);
                continue;
            }
            if (on.open && !on.spent) {
                closedTicks.remove(id);
                int prev = st != null && st[0] == on.index ? st[1] : 0;
                int prog = ClockLogic.standProgress(prev, true, true);
                standing.put(id, new int[]{on.index, prog});
                best.merge(on.index, prog, Math::max);
                if (prog % 5 == 1) BossFx.sound(pl.getLocation(), Sound.BLOCK_NOTE_BLOCK_HAT, 0.8f, 1.2f + 0.6f * prog / standTicks);
                if (prog >= standTicks) sealLocked(on, pl);
            } else if (on.open) {
                // 이번 바퀴에 이미 맞물린 봉인석 — 아무 일도 없다
                standing.remove(id);
                closedTicks.remove(id);
            } else {
                standing.remove(id);
                int c = closedTicks.merge(id, 1, Integer::sum);
                if (c > grace && now >= reversalReady.getOrDefault(id, 0L)) {
                    closedTicks.remove(id);
                    timeReversal(pl, ts);
                }
            }
        }
        standing.keySet().retainAll(seen);
        closedTicks.keySet().retainAll(seen);
        if (now % 2 == 0) updateSealLabels(best, standTicks);
    }

    private Seal sealUnder(Location l) {
        for (Seal s : seals) {
            if (Math.abs(l.getY() - s.at.getY()) > 1.5) continue;
            if (horizontal(l, s.at) <= sealRadius) return s;
        }
        return null;
    }

    private String sealModel(Seal s) {
        Params ts = def.pattern("timed_seals");
        return s.open && !s.spent ? ts.str("fx_seal_open", "seal_glyph_open") : ts.str("fx_seal", "seal_glyph");
    }

    private static void setModel(ItemDisplay d, String model) {
        if (d == null || !d.isValid()) return;
        d.setItemStack(ModelRig.modelItem(BossFx.fxKey(model)));
    }

    /** 봉인석 위 진행 표시 (⌛ ▰▰▱▱) — 누군가 열린 봉인석 위에 서 있는 동안만. */
    private void updateSealLabels(Map<Integer, Integer> best, int standTicks) {
        for (Seal s : seals) {
            Integer prog = best.get(s.index);
            String text = null;
            if (prog != null && s.open && !s.spent) {
                int filled = Math.min(6, (int) Math.floor(6.0 * prog / Math.max(1, standTicks)));
                text = "<gold>⌛ " + "▰".repeat(filled) + "</gold><dark_gray>" + "▱".repeat(6 - filled) + "</dark_gray>";
            }
            if (text == null) {
                if (s.label != null) {
                    fx.discard(s.label);
                    s.label = null;
                    s.labelText = null;
                }
                continue;
            }
            if (s.label == null || !s.label.isValid()) {
                s.label = fx.label(s.at.clone().add(0, 1.6, 0), text, 1.0f);
                s.labelText = text;
            } else if (!text.equals(s.labelText)) {
                BossFx.text(s.label, text);
                s.labelText = text;
            }
        }
    }

    /** 열린 봉인석에 stand_time 동안 서 있었다 → 시계 +seal_bonus, 보스 최대 HP 비율 피해, 기절. */
    private void sealLocked(Seal s, Player by) {
        Params ts = def.pattern("timed_seals");
        Params dc = def.pattern("doom_clock");
        s.spent = true;
        setModel(s.plate, sealModel(s));
        for (Map.Entry<UUID, int[]> e : new ArrayList<>(standing.entrySet())) if (e.getValue()[0] == s.index) standing.remove(e.getKey());

        doomTicks = ClockLogic.adjust(doomTicks, dc.dbl("seal_bonus", 20));
        flashDoom(BossBar.Color.WHITE);
        double amount = maxHealth() * ts.dbl("seal_damage_pct", 0.03);
        services.damage().deal(DamageContext.raw(by, entity, amount, DamageType.TRUE).source("timed_seals"));
        if (isAlive()) stun(ts.dbl("seal_stun", 2.0));

        Location top = entity.getLocation().add(0, def.scale() * 1.2, 0);
        BossFx.dustLine(s.at.clone().add(0, 0.6, 0), top, GOLD, 1.4f, 0.4);
        BossFx.particle(Particle.WAX_ON, s.at.clone().add(0, 0.5, 0), 30, sealRadius * 0.5, 0.4, sealRadius * 0.5, 0.1);
        BossFx.particle(Particle.END_ROD, top, 24, 0.6, 0.8, 0.6, 0.05);
        BossFx.sound(s.at, Sound.BLOCK_BELL_RESONATE, 1.6f, 1.2f);
        BossFx.sound(s.at, Sound.BLOCK_VAULT_OPEN_SHUTTER, 1.4f, 0.8f);
        BossFx.sound(top, Sound.BLOCK_ANVIL_LAND, 0.8f, 1.6f);
        broadcastBar("<gold><b>봉인이 맞물렸다!</b></gold> <gray>톱니가 삐걱이며 한 칸 물러선다…</gray>");
    }

    /** 닫힌 봉인석을 밟았다 → 시간 역류: rewind_seconds 전 자리로 + rewind_damage + 시계 −wrong_penalty. */
    private void timeReversal(Player pl, Params ts) {
        UUID id = pl.getUniqueId();
        reversalReady.put(id, now + Math.max(20, ticks(ts.dbl("reversal_cooldown", 3.0))));
        Location from = pl.getLocation();
        PositionHistory h = history.get(id);
        double[] back = h == null ? null : h.ago(now, ticks(ts.dbl("rewind_seconds", 5)));
        BossFx.particle(Particle.REVERSE_PORTAL, from.clone().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.05);
        if (back != null) {
            Location to = new Location(from.getWorld(), back[0], back[1], back[2], (float) back[3], (float) back[4]);
            if (horizontal(to, center) <= arenaRadius && sealUnder(to) == null && horizontal(to, from) > 0.5) {
                pl.teleport(to);
                pl.setFallDistance(0);
                BossFx.particle(Particle.REVERSE_PORTAL, to.clone().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.05);
                BossFx.dustLine(from.clone().add(0, 1, 0), to.clone().add(0, 1, 0), TEAL, 1.0f, 0.5);
            }
        }
        hit(pl, dmg(ts, "rewind_damage", 1.0), "time_reversal", DamageType.MAGIC);
        Params dc = def.pattern("doom_clock");
        doomTicks = ClockLogic.adjust(doomTicks, -dc.dbl("wrong_penalty", 10));
        flashDoom(BossBar.Color.PURPLE);
        BossFx.sound(from, Sound.ENTITY_ENDERMAN_TELEPORT, 1.0f, 0.5f);
        BossFx.sound(from, Sound.BLOCK_BELL_RESONATE, 1.0f, 0.4f);
        notify(pl, "<#7ae0c0><b>시간 역류</b></#7ae0c0> <gray>— 잠든 봉인이 너를 밀어낸다…</gray>");
    }

    // ── 종말 시계 (보조 기믹 = 엔레이지 타이머) ─────────────────────────

    private String doomTitle() {
        String t = ClockLogic.clock(doomTicks);
        String col = doomTicks <= 600 ? "red" : doomTicks <= 1200 ? "gold" : "yellow";
        return "<" + col + ">⌛ 종말 시계</" + col + "> <white><b>" + t + "</b></white>";
    }

    private void flashDoom(BossBar.Color c) {
        doomFlashUntil = now + 30;
        doomFlash = c;
        updateDoomBar();
    }

    private void tickDoom() {
        if (doomBar == null) return;
        if (doomTicks > 0) doomTicks--;
        int s = doomTicks / 20;
        if (doomTicks % 20 == 0) {
            if (s == 60 || s == 30) {
                BossFx.sound(center, Sound.BLOCK_BELL_USE, 2f, 0.6f);
                BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 1.5f, 0.5f);
            } else if (s > 0 && s <= 10) {
                BossFx.sound(center, Sound.BLOCK_NOTE_BLOCK_HAT, 1.5f, 0.6f + 0.05f * (10 - s));
            }
        }
        if (now % 5 == 0) updateDoomBar();
        if (doomTicks <= 0) timeEnd();
    }

    private void updateDoomBar() {
        if (doomBar == null) return;
        doomBar.name(Text.mm(doomTitle()));
        doomBar.progress((float) Math.max(0, Math.min(1, doomTicks / (double) Math.max(1, doomStart))));
        BossBar.Color c = doomTicks <= 600 ? BossBar.Color.RED : BossBar.Color.YELLOW;
        if (now < doomFlashUntil && (now / 4) % 2 == 0) c = doomFlash;
        doomBar.color(c);
    }

    private void refreshDoomViewers() {
        if (doomBar == null) return;
        Set<UUID> want = new HashSet<>();
        List<Player> show = new ArrayList<>();
        if (!adhoc) for (Player p : ctx.onlineMembers()) if (want.add(p.getUniqueId())) show.add(p);
        World w = center.getWorld();
        if (w != null) {
            for (Player p : w.getPlayers()) {
                if (horizontal(p.getLocation(), center) <= arenaRadius + 16 && Math.abs(p.getLocation().getY() - floorY) < 24
                        && want.add(p.getUniqueId())) show.add(p);
            }
        }
        for (UUID u : new ArrayList<>(doomViewers)) {
            if (want.contains(u)) continue;
            Player p = org.bukkit.Bukkit.getPlayer(u);
            if (p != null) services.hud().hideBossBar(p, "boss_doom");
            doomViewers.remove(u);
        }
        for (Player p : show) if (doomViewers.add(p.getUniqueId())) services.hud().showBossBar(p, "boss_doom", doomBar);
    }

    private void hideDoom() {
        for (UUID u : doomViewers) {
            Player p = org.bukkit.Bukkit.getPlayer(u);
            if (p != null) services.hud().hideBossBar(p, "boss_doom");
        }
        doomViewers.clear();
    }

    /** 시계가 0 — "시간 종언": 전원 최대 HP × zero_damage_pct. 살아남은 사람이 있으면 시계는 reset_seconds 로 다시. */
    private void timeEnd() {
        Params dc = def.pattern("doom_clock");
        say(def.line("doom"));
        for (Player pl : players()) {
            hitPct(pl, dc.dbl("zero_damage_pct", 9.99), "doom_clock");
            BossFx.particle(Particle.REVERSE_PORTAL, pl.getLocation().add(0, 1, 0), 60, 0.5, 1.0, 0.5, 0.1);
        }
        BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 2f, 0.3f);
        BossFx.sound(center, Sound.ENTITY_WARDEN_SONIC_BOOM, 1.6f, 0.5f);
        BossFx.sound(center, Sound.BLOCK_END_PORTAL_SPAWN, 1.0f, 0.6f);
        BossFx.particle(Particle.REVERSE_PORTAL, center.clone().add(0, 2, 0), 400, arenaRadius * 0.5, 2, arenaRadius * 0.5, 0.2);
        broadcastBar("<dark_red><b>시간 종언.</b></dark_red>");
        doomTicks = ClockLogic.adjust(0, dc.dbl("reset_seconds", 60));
        flashDoom(BossBar.Color.RED);
    }

    // ── 위치 기록 ────────────────────────────────────────────────────────

    private void recordPositions() {
        Set<UUID> seen = new HashSet<>();
        for (Player pl : players()) {
            UUID id = pl.getUniqueId();
            seen.add(id);
            Location l = pl.getLocation();
            // 봉인석 위 자리는 되감기 목적지로 쓰지 않도록 기록하지 않는다
            if (sealUnder(l) != null) continue;
            history.computeIfAbsent(id, k -> new PositionHistory(historyCap)).record(now, l.getX(), l.getY(), l.getZ(), l.getYaw(), l.getPitch());
        }
        history.keySet().retainAll(seen);
    }

    // ── 패턴 선택 ────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) {
        return switch (key) {
            case "hand_strike" -> target() != null;
            case "rewind_echo" -> !players().isEmpty();
            default -> !targets().isEmpty();
        };
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "hand_strike" -> handStrike();
            case "pendulum_sweep" -> pendulumSweep();
            case "rewind_echo" -> rewindEcho();
            case "gear_storm" -> gearStorm();
            default -> 0;
        };
    }

    @Override
    protected void onPhase(int newPhase) {
        BossFx.sound(center, Sound.BLOCK_BELL_USE, 2f, 0.5f + 0.15f * newPhase);
        BossFx.dustRing(hub, arenaRadius - 2, BRASS, 1.4f, 72);
        Params ts = def.pattern("timed_seals");
        if (newPhase >= 3 && ts.bool("p3_reverse", true) && handDir > 0) {
            // 예고: 바늘이 멈칫하고 색이 바뀐 뒤 거꾸로 돈다
            handDir = -1;
            handPauseUntil = now + Math.max(20, ticks(ts.dbl("reverse_pause", 1.5)));
            handModel = ts.str("fx_hand_reverse", "clock_hand_reverse");
            setModel(hand, handModel);
            for (Seal s : seals) s.spent = false;
            BossFx.sound(center, Sound.BLOCK_BEACON_DEACTIVATE, 2f, 0.5f);
            BossFx.sound(center, Sound.BLOCK_RESPAWN_ANCHOR_DEPLETE, 1.6f, 0.6f);
            BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 1.6f, 0.35f);
            BossFx.particle(Particle.REVERSE_PORTAL, hub.clone().add(0, 1, 0), 200, arenaRadius * 0.4, 1.0, arenaRadius * 0.4, 0.15);
            BossFx.dustRing(hub, arenaRadius - 2, TEAL, 1.6f, 72);
            broadcastBar("<#7ae0c0><b>톱니가 거꾸로 맞물린다…</b></#7ae0c0>");
        } else if (newPhase == 2) {
            BossFx.sound(center, Sound.BLOCK_NOTE_BLOCK_HAT, 2f, 1.6f);
            broadcastBar("<gold>초침이 숨을 몰아쉰다…</gold>");
        }
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    // ── 시침 베기 ────────────────────────────────────────────────────────

    private int handStrike() {
        Params p = def.pattern("hand_strike");
        Player t = target();
        if (t == null) return 0;
        int w = windup(p, 0.9);
        Telegraph.Shape cone = Telegraph.Shape.cone(feet(), dirTo(t.getLocation()), p.dbl("angle", 90), p.dbl("length", 5));
        double dmg = dmg(p, "damage", 1.4);
        telegraph(cone, w, Telegraph.RED, null, () -> {
            hitShape(cone, dmg, "hand_strike", DamageType.MELEE, null);
            Location front = cone.origin().clone().add(cone.direction().multiply(2.5)).add(0, 1, 0);
            BossFx.sound(entity.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.4f, 0.6f);
            BossFx.sound(front, Sound.BLOCK_CHAIN_BREAK, 1.0f, 0.8f);
            BossFx.particle(Particle.SWEEP_ATTACK, front, 3, 1.0, 0.2, 1.0, 0);
            BossFx.dust(front, BRASS, 1.3f, 16, 1.2);
        });
        return cast("hand_strike", "시침 베기", w, w + 8, BossAnim.SWEEP, t.getLocation(), false);
    }

    // ── 진자 베기 ────────────────────────────────────────────────────────

    private int pendulumSweep() {
        Params p = def.pattern("pendulum_sweep");
        Player t = randomTarget();
        if (t == null) return 0;
        double width = p.dbl("width", 3);
        double ang = rng.nextDouble() * 360;
        Vector dir = new Vector(BossMath.ax(ang), 0, BossMath.az(ang));
        Location tl = t.getLocation();
        double[] ch = ClockLogic.chord(tl.getX(), tl.getZ(), dir.getX(), dir.getZ(), center.getX(), center.getZ(), arenaRadius - 1);
        if (ch == null || ch[2] < 4) {
            ch = ClockLogic.chord(center.getX(), center.getZ(), dir.getX(), dir.getZ(), center.getX(), center.getZ(), arenaRadius - 1);
            if (ch == null) return 0;
        }
        double half = Math.min(ch[2] / 2, p.dbl("length", 18) / 2);
        double st = (tl.getX() - ch[0]) * dir.getX() + (tl.getZ() - ch[1]) * dir.getZ();
        double midS = ClockLogic.laneCenter(st, ch[2], half);
        Location mid = ground(new Location(center.getWorld(), ch[0] + dir.getX() * midS, center.getY(), ch[1] + dir.getZ() * midS));
        Location start = mid.clone().subtract(dir.clone().multiply(half));
        Telegraph.Shape lane = Telegraph.Shape.line(start, dir, half * 2, width);

        int w = windup(p, 1.5);
        int passTicks = Math.max(8, (int) Math.round(ticks(p.dbl("swing_time", 1.2)) / scaling().speedMult()));
        int passes = Math.max(1, p.integer("swings", 2)) * 2;
        double dmg = dmg(p, "damage", 1.8);
        double arm = Math.max(4, Math.min(arenaHeight - 1.5, p.dbl("arm", 12)));
        String model = p.str("fx", "pendulum");
        double[] base = fx.size(model, 2.0);
        Vector3f scale = new Vector3f((float) p.dbl("blade_scale", 1.6), (float) (arm / Math.max(0.5, base[1])), (float) p.dbl("depth_scale", 2.5));
        float yawRad = (float) Math.atan2(-dir.getZ(), dir.getX()); // 모델 +X(흔들림 방향) → 차선 방향
        Location pivot = mid.clone().add(0, arm + 0.2, 0);
        pivot.setYaw(0);
        pivot.setPitch(0);
        ItemDisplay pend = fx.model(model, pivot, 1f, Display.Billboard.FIXED);
        double maxAng = ClockLogic.pendulumAngle(-half, arm);
        orientPendulum(pend, yawRad, 0, scale, 0);

        telegraph(lane, w, Telegraph.RED, null, null);
        int total = w + passTicks * passes;
        Set<UUID> struck = new HashSet<>();
        double[] prev = {-half};
        int[] lastPass = {0};
        ItemDisplay[] lanePlate = {null};
        run(new Mechanics.Repeat(total, 1, tt -> {
            if (tt < w) {
                // 끌어올리기: 차선 한쪽 끝으로 천천히 당겨진다
                if (tt % 2 == 0) orientPendulum(pend, yawRad, maxAng * Math.min(1, tt / (double) Math.max(1, w - 4)), scale, 2);
                if (tt % 10 == 0) BossFx.sound(pivot, Sound.BLOCK_CHAIN_STEP, 1.2f, 0.5f);
                return true;
            }
            int sw = tt - w;
            if (sw == 0) {
                lanePlate[0] = fx.plate(lane, "telegraph_line");
                BossFx.sound(pivot, Sound.BLOCK_CHAIN_BREAK, 1.6f, 0.5f);
            }
            double along = ClockLogic.pendulumAlong(sw, passTicks, passes, half);
            int pass = ClockLogic.pendulumPass(sw, passTicks, passes);
            if (pass != lastPass[0]) {
                lastPass[0] = pass;
                struck.clear();
            }
            if (sw % passTicks == passTicks / 2) BossFx.sound(mid, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1.8f, 0.5f);
            for (Player pl : players()) {
                Location l = pl.getLocation();
                double rx = l.getX() - mid.getX(), rz = l.getZ() - mid.getZ();
                double s = rx * dir.getX() + rz * dir.getZ();
                double lat = Math.abs(rx * dir.getZ() - rz * dir.getX());
                if (lat > width / 2 + 0.3 || Math.abs(s) > half + 0.6 || !BossMath.heightOk(mid.getY(), l.getY())) continue;
                if (!ClockLogic.swept(prev[0], along, s, 0.9) || !struck.add(pl.getUniqueId())) continue;
                hit(pl, dmg, "pendulum_sweep", DamageType.MELEE);
                push(pl, dir.clone().multiply(Math.signum(along - prev[0]) == 0 ? 1 : Math.signum(along - prev[0])), 0.7, 0.3);
                BossFx.particle(Particle.CRIT, l.clone().add(0, 1, 0), 12, 0.3, 0.5, 0.3, 0.2);
            }
            prev[0] = along;
            orientPendulum(pend, yawRad, ClockLogic.pendulumAngle(along, arm), scale, 1);
            if (sw % 2 == 0) {
                Location bob = mid.clone().add(dir.clone().multiply(along)).add(0, 0.4, 0);
                BossFx.dust(bob, BRASS, 1.2f, 3, 0.4);
            }
            return true;
        }, () -> {
            fx.discard(pend);
            fx.discard(lanePlate[0]);
        }, true));
        return cast("pendulum_sweep", "진자 베기", w, w + 10, BossAnim.CAST, mid, false);
    }

    /** 진자: 매단 점(디스플레이 위치)을 축으로 차선 방향으로 angleDeg 만큼 흔든다 (모델 Z축 회전). */
    private static void orientPendulum(ItemDisplay d, float yawRad, double angleDeg, Vector3f scale, int interp) {
        if (d == null || !d.isValid()) return;
        Quaternionf q = new Quaternionf().rotationY(yawRad).rotateZ((float) Math.toRadians(angleDeg));
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(Math.max(0, interp));
        d.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(scale), new Quaternionf()));
    }

    // ── 되감기 메아리 ────────────────────────────────────────────────────

    private int rewindEcho() {
        Params p = def.pattern("rewind_echo");
        List<Player> all = players();
        if (all.isEmpty()) return 0;
        int delay = windupSec(p.dbl("delay", 6));
        double r = p.dbl("radius", 2.5);
        double dmg = dmg(p, "damage", 1.2);
        for (Player pl : all) {
            PositionHistory h = history.get(pl.getUniqueId());
            double[] s = h == null ? null : h.latest();
            Location at = s == null ? pl.getLocation() : new Location(pl.getWorld(), s[0], s[1], s[2]);
            at = ground(at);
            Telegraph.Shape c = Telegraph.Shape.circle(at, r);
            final Location spot = at;
            TextDisplay echo = fx.label(spot.clone().add(0, 1.4, 0), "<#7ae0c0>⌛</#7ae0c0>", 1.4f);
            telegraph(c, delay, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "rewind_echo", DamageType.MAGIC, null);
                BossFx.particle(Particle.REVERSE_PORTAL, spot.clone().add(0, 0.6, 0), 50, r * 0.4, 0.4, r * 0.4, 0.15);
                BossFx.sound(spot, Sound.BLOCK_BELL_RESONATE, 1.0f, 1.6f);
                BossFx.sound(spot, Sound.ENTITY_ILLUSIONER_MIRROR_MOVE, 1.0f, 0.6f);
            });
            run(new Mechanics.Repeat(delay, 5, tt -> {
                BossFx.dust(spot.clone().add(0, 0.9, 0), TEAL, 1.2f, 3, 0.25);
                BossFx.particle(Particle.REVERSE_PORTAL, spot.clone().add(0, 0.4, 0), 2, 0.3, 0.3, 0.3, 0.01);
                return true;
            }, null, true));
            afterPersistent(delay + 2, () -> fx.discard(echo));
        }
        BossFx.sound(center, Sound.ENTITY_ILLUSIONER_PREPARE_MIRROR, 1.6f, 0.6f);
        BossFx.sound(center, Sound.BLOCK_BELL_RESONATE, 1.2f, 0.7f);
        return cast("rewind_echo", "되감기 메아리", 20, 24, BossAnim.CAST, null, false);
    }

    // ── 톱니 폭풍 ────────────────────────────────────────────────────────

    private int gearStorm() {
        Params p = def.pattern("gear_storm");
        if (targets().isEmpty()) return 0;
        int n = scaling().count(p, "lines", 3, p.integer("lines_max", 8));
        double width = p.dbl("width", 2);
        int w = windup(p, 1.4);
        double speed = Math.max(0.1, p.dbl("speed", 0.6) * scaling().speedMult());
        double dmg = dmg(p, "damage", 1.3);
        String model = p.str("fx", "proj_gear_large");
        List<Player> aimed = pickTargets(n, null, false);
        double y = ground(center).getY();
        int made = 0;
        for (int i = 0; i < n * 3 && made < n; i++) {
            Location through = made < aimed.size() ? aimed.get(made).getLocation() : randomPoint(0, arenaRadius * 0.75);
            double ang = rng.nextDouble() * 360;
            double dx = BossMath.ax(ang), dz = BossMath.az(ang);
            double[] c = ClockLogic.chord(through.getX(), through.getZ(), dx, dz, center.getX(), center.getZ(), arenaRadius - 0.5);
            if (c == null || c[2] < 6) continue;
            Location start = new Location(center.getWorld(), c[0], y, c[1]);
            Telegraph.Shape line = Telegraph.Shape.line(start, new Vector(dx, 0, dz), c[2], width);
            int stagger = made * 4;
            telegraph(line, w + stagger, Telegraph.RED, null, () -> rollGear(line, speed, dmg, model, width));
            made++;
        }
        if (made == 0) return 0;
        BossFx.sound(center, Sound.BLOCK_GRINDSTONE_USE, 1.6f, 0.5f);
        return cast("gear_storm", "톱니 폭풍", w, w + 6, BossAnim.SLAM, null, false);
    }

    private void rollGear(Telegraph.Shape line, double speed, double dmg, String model, double width) {
        double[] base = fx.size(model, 2.0);
        float sc = (float) Math.max(0.5, width / Math.max(0.25, base[0]));
        double radius = base[1] * sc / 2;
        Vector d = line.direction();
        float yawRad = (float) Math.atan2(-d.getZ(), d.getX()); // 모델 +X → 진행 방향, 축(Z) = 옆
        int travel = Math.max(4, (int) Math.ceil(line.size() / speed));
        Location start = line.origin().clone().add(0, radius, 0);
        ItemDisplay g = fx.model(model, start, sc, Display.Billboard.FIXED);
        Set<UUID> struck = new HashSet<>();
        double[] prev = {0};
        BossFx.sound(start, Sound.BLOCK_GRINDSTONE_USE, 1.4f, 0.6f);
        run(new Mechanics.Repeat(travel, 1, tt -> {
            double dist = Math.min(line.size(), tt * speed);
            Location at = line.origin().clone().add(d.clone().multiply(dist)).add(0, radius, 0);
            if (g != null && g.isValid()) {
                Location tp = at.clone();
                tp.setYaw(0);
                tp.setPitch(0);
                g.teleport(tp);
                Quaternionf q = new Quaternionf().rotationY(yawRad).rotateZ((float) ClockLogic.rollAngle(dist, radius));
                g.setInterpolationDelay(0);
                g.setInterpolationDuration(1);
                g.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(sc, sc, sc), new Quaternionf()));
            }
            for (Player pl : players()) {
                if (struck.contains(pl.getUniqueId())) continue;
                Location l = pl.getLocation();
                if (!BossMath.heightOk(line.origin().getY(), l.getY())) continue;
                double ax = line.origin().getX() + d.getX() * prev[0], az = line.origin().getZ() + d.getZ() * prev[0];
                double bx = line.origin().getX() + d.getX() * dist, bz = line.origin().getZ() + d.getZ() * dist;
                double r = width / 2 + 0.3;
                if (BossMath.segmentDist2(ax, az, bx, bz, l.getX(), l.getZ()) > r * r) continue;
                struck.add(pl.getUniqueId());
                hit(pl, dmg, "gear_storm", DamageType.MELEE);
                BossFx.particle(Particle.CRIT, l.clone().add(0, 1, 0), 10, 0.3, 0.5, 0.3, 0.2);
            }
            prev[0] = dist;
            if (tt % 2 == 0) BossFx.particle(Particle.WAX_OFF, at.clone().add(0, -radius + 0.1, 0), 2, 0.3, 0.05, 0.3, 0.05);
            if (tt % 6 == 0) BossFx.sound(at, Sound.BLOCK_CHAIN_STEP, 0.9f, 0.6f);
            return true;
        }, () -> fx.discard(g), true));
    }

    // ── 정리 ─────────────────────────────────────────────────────────────

    @Override
    protected void onEnd() {
        hideDoom();
        doomBar = null;
        seals.clear();
        standing.clear();
        closedTicks.clear();
        reversalReady.clear();
        history.clear();
        hand = null;
    }
}
