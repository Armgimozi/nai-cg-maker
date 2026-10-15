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
import kr.labyrinth.bosses.impl.Floor07Logic.Polarity;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageInterceptor;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Text;
import net.kyori.adventure.bossbar.BossBar;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Display;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.util.Vector;

/**
 * 지하 7층 — 양극의 수정체 다이아드 (GDD §7.7, core {@code polarity}).
 * <p>
 * 핵심: 빛/어둠 <b>극성</b>. 전투 시작 때 플레이어를 번갈아 빛/어둠으로 배정(솔로 = 빛, 머리 위 수정 표식 + 개인 극성 막대),
 * 아레나 양쪽의 빛·어둠 기둥에 닿으면 그 색으로 바뀐다(개인 재사용 5초). 보스 <b>얼굴</b>은 20초(3페이즈 10초)마다
 * 바뀌며(모델 반쪽이 밝아짐 + 보스바 색), 얼굴과 반대 극성이면 주는 피해 +25%, 같으면 −50%.
 * <p>
 * 패턴: shard_orbit(보스 중심 원 r4, 3초 지속) · crystal_rain(무작위 원, 4 + (n−1)개) ·
 * polarity_wave(아레나 전체 색 경고 → 같은 극성 무사·다른 극성 3.0배, 3페이즈 2.5초 간격 반대 색 2연속) ·
 * split_beam(빛 광선 → 어둠 대상, 어둠 광선 → 빛 대상 — 같은 극성이 끼어들면 0.6배 흡수, 없으면 대상 3.0배) ·
 * prism_refraction(6초 수정 껍질 — 얼굴과 같은 극성 공격은 피해의 50% 반사).
 * 극성 피해 배율·반사는 {@link DamageInterceptor} 로 이 보스에게 들어오는 피해에만 건다(종료 때 해제).
 */
public final class Floor07Boss extends Boss {

    private static final Color LIGHT = Color.fromRGB(255, 214, 110);
    private static final Color DARK = Color.fromRGB(150, 80, 240);
    private static final Color ENRAGE = Color.fromRGB(255, 40, 40);
    private static final String BAR_KEY = "boss_polarity";

    private static Color color(Polarity p) { return p == Polarity.LIGHT ? LIGHT : DARK; }

    /** 기둥 하나: 위치(바닥) · 색 · 모델 · 이름표. */
    private record Pylon(Location at, Polarity polarity, ItemDisplay model, TextDisplay label, double height) {}

    private final List<Pylon> pylons = new ArrayList<>();
    private final Map<UUID, Polarity> polarity = new HashMap<>();
    private final Map<UUID, Long> swapReady = new HashMap<>();
    private final Map<UUID, ItemDisplay> marks = new HashMap<>();
    private final Map<UUID, BossBar> bars = new HashMap<>();
    private final Set<UUID> barShown = new HashSet<>();
    private final Map<UUID, Long> quietUntil = new HashMap<>();
    private final List<Runnable> nextTick = new ArrayList<>();

    private Polarity face = Polarity.DARK;
    private long nextFace;
    private boolean faceWarned;
    /** 극성 파동을 모으는 중인 색 (보스 전체가 그 색으로 빛남). */
    private Polarity charging;
    private boolean refracting;
    private ItemDisplay shell;
    private DamageInterceptor interceptor;

    public Floor07Boss(Init init) { super(init); }

    // ── 아레나: 빛·어둠 기둥 + 극성 배정 ─────────────────────────────────

    @Override
    protected void onSpawn() {
        Params pa = def.pattern("polarity_assign");
        int total = Math.max(2, pa.integer("pylons", def.arena().integer("pylons", 4)));
        double ring = Math.min(arenaRadius - 2, pa.dbl("pylon_ring_radius", 12));
        double spread = pa.dbl("pair_spread", 28);
        float scale = (float) pa.dbl("pylon_scale", 1.6);
        for (Floor07Logic.PylonSpot s : Floor07Logic.pylonLayout(total, spread)) {
            Location g = ground(ringPoint(s.angle(), ring));
            String model = pa.str(s.polarity() == Polarity.LIGHT ? "fx_light" : "fx_dark",
                    s.polarity() == Polarity.LIGHT ? "pylon_light" : "pylon_dark");
            double h = fx.size(model, 2.5)[1] * scale;
            ItemDisplay m = fx.model(model, g.clone().add(0, h / 2, 0), scale, Display.Billboard.FIXED);
            if (m != null) m.setBrightness(new Display.Brightness(15, 15));
            TextDisplay label = fx.label(g.clone().add(0, h + 0.5, 0), pylonLabel(s.polarity()), 0.85f);
            pylons.add(new Pylon(g, s.polarity(), m, label, h));
            BossFx.dust(g.clone().add(0, h / 2, 0), color(s.polarity()), 1.6f, 24, 0.6);
        }

        // 극성 배정: 번갈아 (솔로 = 빛)
        List<Player> ps = players();
        List<Polarity> as = Floor07Logic.assignAlternate(ps.size());
        for (int i = 0; i < ps.size(); i++) setPolarity(ps.get(i), as.get(i));

        Params fs = def.pattern("face_shift");
        face = Polarity.byName(fs.str("start", "dark"));
        nextFace = now + ticks(Floor07Logic.faceInterval(1, fs.dbl("interval", 20), fs.dbl("p3_interval", 10)));
        setBarColor(face == Polarity.LIGHT ? BossBar.Color.YELLOW : BossBar.Color.PURPLE);
        applyFaceLight();

        interceptor = this::intercept;
        services.damage().addInterceptor(interceptor);

        afterPersistent(30, this::awaken);
    }

    /** 기둥 이름표 = 이름만 (조작법은 글로 알려 주지 않는다 — 단서는 bosses.yml hints). */
    private String pylonLabel(Polarity p) {
        return "<" + p.hex() + "><b>" + p.icon() + " " + p.label() + "의 기둥</b></" + p.hex() + ">";
    }

    /** 배정 직후 분위기 한 줄 + 각자 받은 색 (무슨 일이 일어났는지만). */
    private void awaken() {
        say("<gray>두 빛깔의 수정이 서로를 부르며 운다…</gray>");
        for (Player p : players()) {
            Polarity pol = polarity.get(p.getUniqueId());
            if (pol != null) notify(p, pol.tag() + " <gray>이 당신의 가슴에 깃든다…</gray>");
        }
    }

    private Polarity polarityOf(Player p) { return p == null ? null : polarity.get(p.getUniqueId()); }

    private long ready(Player p) { return swapReady.getOrDefault(p.getUniqueId(), 0L); }

    /** 극성 설정 (+ 머리 위 표식 교체, 개인 막대 갱신). */
    private void setPolarity(Player p, Polarity pol) {
        UUID id = p.getUniqueId();
        polarity.put(id, pol);
        ItemDisplay old = marks.remove(id);
        fx.discard(old);
        ItemDisplay m = spawnMark(p, pol);
        if (m != null) marks.put(id, m);
        refreshBar(p);
    }

    private ItemDisplay spawnMark(Player p, Polarity pol) {
        Params pa = def.pattern("polarity_assign");
        String model = pa.str(pol == Polarity.LIGHT ? "fx_mark_light" : "fx_mark_dark", pol == Polarity.LIGHT ? "marker_light" : "marker_dark");
        ItemDisplay m = fx.model(model, markAt(p), 1.3f, Display.Billboard.VERTICAL);
        if (m != null) m.setBrightness(new Display.Brightness(15, 15));
        return m;
    }

    private Location markAt(Player p) {
        Location at = p.getLocation().add(0, p.getHeight() + 0.75 + 0.06 * Math.sin(now * 0.25), 0);
        at.setYaw(0);
        at.setPitch(0);
        return at;
    }

    /** 기둥에 닿아 색 바꾸기. */
    private void swap(Player p, Pylon py) {
        Params pa = def.pattern("polarity_assign");
        int cd = ticks(pa.dbl("swap_cooldown", 5));
        swapReady.put(p.getUniqueId(), now + cd);
        setPolarity(p, py.polarity());
        notify(p, py.polarity().tag() + " <gray>이 몸에 스며든다…</gray>");
        Location top = py.at().clone().add(0, py.height() * 0.8, 0);
        BossFx.dustLine(top, p.getLocation().add(0, 1.0, 0), color(py.polarity()), 1.0f, 0.5);
        BossFx.dust(p.getLocation().add(0, 1.0, 0), color(py.polarity()), 1.4f, 18, 0.4);
        BossFx.particle(Particle.END_ROD, p.getLocation().add(0, 1.0, 0), 6, 0.3, 0.5, 0.3, 0.02);
        BossFx.sound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1.2f, py.polarity() == Polarity.LIGHT ? 1.6f : 0.7f);
        BossFx.sound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 0.6f, py.polarity() == Polarity.LIGHT ? 1.8f : 1.1f);
    }

    /** 같은 플레이어에게 너무 자주 액션바를 띄우지 않기. */
    private boolean quiet(Player p, int ticks) {
        long until = quietUntil.getOrDefault(p.getUniqueId(), -1L);
        if (now < until) return true;
        quietUntil.put(p.getUniqueId(), now + ticks);
        return false;
    }

    // ── 매 틱: 얼굴 전환 · 기둥 접촉 · 표식 · 개인 막대 · 반사 ────────────

    @Override
    protected void onTick() {
        if (!nextTick.isEmpty()) {
            List<Runnable> q = new ArrayList<>(nextTick);
            nextTick.clear();
            for (Runnable r : q) r.run();
        }
        tickFace();
        if (now % 2 == 0) tickPlayers();
        if (now % 5 == 0) refreshBars();
        if (now % 10 == 0) pylonFx();
        if (now % 20 == 0) {
            assignLate();
            applyFaceLight();
        }
    }

    private void tickFace() {
        Params fs = def.pattern("face_shift");
        long left = nextFace - now;
        if (!faceWarned && left <= ticks(fs.dbl("warn", 2.0))) {
            faceWarned = true;
            // 전환 예고: 반대쪽 반쪽이 깜빡이며 차임
            Polarity next = face.opposite();
            BossFx.sound(entity.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 2f, next == Polarity.LIGHT ? 1.5f : 0.6f);
            BossFx.dust(entity.getLocation().add(0, 1.65 * def.scale(), 0), color(next), 1.8f, 30, 1.0);
        }
        if (left <= 0) shiftFace(fs);
    }

    private void shiftFace(Params fs) {
        face = face.opposite();
        faceWarned = false;
        nextFace = now + ticks(Floor07Logic.faceInterval(phase(), fs.dbl("interval", 20), fs.dbl("p3_interval", 10)));
        setBarColor(face == Polarity.LIGHT ? BossBar.Color.YELLOW : BossBar.Color.PURPLE);
        applyFaceLight();
        Location eye = entity.getLocation().add(0, 1.65 * def.scale(), 0);
        BossFx.dust(eye, color(face), 2.0f, 50, 1.2);
        BossFx.particle(face == Polarity.LIGHT ? Particle.END_ROD : Particle.REVERSE_PORTAL, eye, 30, 0.8, 1.0, 0.8, 0.05);
        BossFx.sound(eye, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 2f, face == Polarity.LIGHT ? 1.4f : 0.5f);
        BossFx.sound(eye, face == Polarity.LIGHT ? Sound.BLOCK_BEACON_ACTIVATE : Sound.BLOCK_BEACON_DEACTIVATE, 1.2f, 1.2f);
        if (!casting()) broadcastBar("<gray>다이아드가 얼굴을 돌린다 —</gray> " + face.tag() + " <gray>이 깨어난다…</gray>");
        refreshBars();
    }

    /** 모델 반쪽 밝기 + 발광 (얼굴 표시). 파동을 모으는 중이거나 기절 중이면 건드리지 않는다. */
    private void applyFaceLight() {
        if (charging != null || stunned()) return;
        rig.partLight("light_half", face == Polarity.LIGHT ? 15 : 3, face == Polarity.LIGHT ? LIGHT : null);
        rig.partLight("dark_half", face == Polarity.DARK ? 15 : 3, face == Polarity.DARK ? DARK : null);
    }

    private void tickPlayers() {
        Params pa = def.pattern("polarity_assign");
        double touch = pa.dbl("pylon_radius", 1.5);
        List<Player> ps = players();
        Set<UUID> valid = new HashSet<>();
        for (Player p : ps) {
            UUID id = p.getUniqueId();
            valid.add(id);
            Polarity cur = polarity.get(id);
            if (cur == null) continue;
            for (Pylon py : pylons) {
                if (py.polarity() == cur) continue;
                Location l = p.getLocation();
                if (horizontal(l, py.at()) > touch || Math.abs(l.getY() - py.at().getY()) > 3) continue;
                long rem = Floor07Logic.swapRemaining(now, ready(p));
                if (rem <= 0) swap(p, py);
                else if (!quiet(p, 20)) notify(p, "<gray>기둥이 아직 잠잠하다… <dark_gray>⌛ " + Text.num(rem / 20.0) + "</dark_gray></gray>");
                break;
            }
            ItemDisplay m = marks.get(id);
            if (m == null || !m.isValid()) {
                m = spawnMark(p, cur);
                if (m != null) marks.put(id, m);
            } else {
                m.teleport(markAt(p));
            }
        }
        // 쓰러지거나 떠난 사람의 표식은 치운다 (극성은 기억)
        for (UUID id : new ArrayList<>(marks.keySet())) {
            if (!valid.contains(id)) fx.discard(marks.remove(id));
        }
    }

    private void assignLate() {
        int light = 0, dark = 0;
        for (Polarity p : polarity.values()) {
            if (p == Polarity.LIGHT) light++;
            else dark++;
        }
        for (Player p : players()) {
            if (polarity.containsKey(p.getUniqueId())) continue;
            Polarity pol = Floor07Logic.forLateJoiner(light, dark);
            if (pol == Polarity.LIGHT) light++;
            else dark++;
            setPolarity(p, pol);
            notify(p, pol.tag() + " <gray>이 당신의 가슴에 깃든다…</gray>");
        }
    }

    private void pylonFx() {
        for (Pylon py : pylons) {
            Location mid = py.at().clone().add(0, py.height() * (0.3 + 0.6 * rng.nextDouble()), 0);
            BossFx.dust(mid, color(py.polarity()), 1.1f, 3, 0.35);
            if (now % 40 == 0) BossFx.dustRing(py.at(), def.pattern("polarity_assign").dbl("pylon_radius", 1.5), color(py.polarity()), 0.9f, 14);
        }
    }

    // ── 개인 극성 막대 (보스바 아래) ─────────────────────────────────────

    private void refreshBars() {
        Set<UUID> want = new HashSet<>();
        for (Player p : players()) {
            if (!polarity.containsKey(p.getUniqueId())) continue;
            want.add(p.getUniqueId());
            refreshBar(p);
        }
        for (UUID id : new ArrayList<>(barShown)) {
            if (want.contains(id)) continue;
            Player p = Bukkit.getPlayer(id);
            if (p != null) services.hud().hideBossBar(p, BAR_KEY);
            barShown.remove(id);
        }
    }

    private void refreshBar(Player p) {
        Polarity pol = polarity.get(p.getUniqueId());
        if (pol == null) return;
        // 문구 규칙: 색·아이콘·남은 시간만 (피해 배율 같은 정답 수치는 쓰지 않는다)
        int cdTicks = Math.max(1, ticks(def.pattern("polarity_assign").dbl("swap_cooldown", 5)));
        long rem = Floor07Logic.swapRemaining(now, ready(p));
        boolean same = pol == face;
        String pylon = rem > 0 ? "<dark_gray>◇ ⌛ " + Text.num(rem / 20.0) + "</dark_gray>" : "<aqua>◆</aqua>";
        long faceLeft = Math.max(0, nextFace - now);
        String name = pol.tag() + " <dark_gray>·</dark_gray> <gray>다이아드</gray> " + face.tag()
                + " <dark_gray>⌛ " + (int) Math.ceil(faceLeft / 20.0) + "</dark_gray> <dark_gray>·</dark_gray> " + pylon
                + (refracting && same ? " <light_purple>✦</light_purple>" : "");
        BossBar b = bars.computeIfAbsent(p.getUniqueId(), u -> BossBar.bossBar(Text.mm(""), 1f, BossBar.Color.WHITE, BossBar.Overlay.PROGRESS));
        b.name(Text.mm(name));
        b.color(pol == Polarity.LIGHT ? BossBar.Color.YELLOW : BossBar.Color.PURPLE);
        b.progress((float) Math.max(0, Math.min(1, 1.0 - rem / (double) cdTicks)));
        if (barShown.add(p.getUniqueId())) services.hud().showBossBar(p, BAR_KEY, b);
    }

    // ── 피해 가로채기: 극성 배율 + 굴절 반사 ─────────────────────────────

    private double intercept(DamageContext c, double dmg) {
        if (c.target() == null || !c.target().getUniqueId().equals(entity.getUniqueId()) || !isAlive()) return dmg;
        Player a = c.attackerPlayer();
        if (a == null) return dmg;
        Polarity pol = polarity.get(a.getUniqueId());
        if (pol == null) return dmg;
        Params fs = def.pattern("face_shift");
        double out = dmg * Floor07Logic.damageMult(pol, face, fs.dbl("opposite_bonus", 0.25), fs.dbl("same_penalty", 0.5));
        boolean dot = c.sourceId() != null && c.sourceId().startsWith("effect:");
        if (refracting && !dot) {
            Params pr = def.pattern("prism_refraction");
            double cap = services.stats().maxHp(a) * pr.dbl("reflect_cap_pct", 0.4);
            double r = Floor07Logic.reflected(pol, face, true, dmg, pr.dbl("reflect_ratio", 0.5), cap);
            if (r > 0) nextTick.add(() -> reflect(a, r));
        }
        return out;
    }

    private void reflect(Player a, double amount) {
        if (!validPlayer(a)) return;
        hit(a, amount, "prism_refraction", DamageType.TRUE);
        BossFx.dustLine(entity.getLocation().add(0, 1.65 * def.scale(), 0), a.getLocation().add(0, 1.0, 0), color(face), 1.0f, 0.6);
        BossFx.sound(a.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_HIT, 1.2f, 1.7f);
        if (!quiet(a, 30)) {
            notify(a, "<light_purple><b>굴절 반사!</b></light_purple> <gray>수정이 당신의</gray> " + polarityOf(a).tag() + "<gray>을 되돌려 보낸다…</gray>");
        }
    }

    // ── 패턴 ─────────────────────────────────────────────────────────────

    @Override
    protected boolean canUse(String key) {
        if (key.equals("prism_refraction")) return !refracting && target() != null;
        return target() != null;
    }

    @Override
    protected int startPattern(String key) {
        return switch (key) {
            case "shard_orbit" -> shardOrbit();
            case "crystal_rain" -> crystalRain();
            case "polarity_wave" -> polarityWave();
            case "split_beam" -> splitBeam();
            case "prism_refraction" -> prismRefraction();
            default -> 0;
        };
    }

    @Override
    protected void onPhase(int newPhase) {
        // 진행 중이던 파동 충전은 취소됨 → 발광 원래대로
        charging = null;
        rig.setGlow(enraged() ? ENRAGE : null);
        applyFaceLight();
        Location eye = entity.getLocation().add(0, 1.65 * def.scale(), 0);
        BossFx.dust(eye, LIGHT, 2.2f, 40, 1.6);
        BossFx.dust(eye, DARK, 2.2f, 40, 1.6);
        BossFx.particle(Particle.END_ROD, eye, 40, 1.2, 1.2, 1.2, 0.1);
        BossFx.sound(eye, Sound.BLOCK_AMETHYST_BLOCK_BREAK, 2f, 0.5f);
        BossFx.sound(eye, Sound.BLOCK_AMETHYST_CLUSTER_BREAK, 2f, 0.7f);
        if (newPhase == 2) {
            broadcastBar("<light_purple><b>빛이 갈라진다</b></light_purple> <gray>— 수정의 두 눈이 서로 다른 곳을 겨눈다…</gray>");
        } else if (newPhase >= 3) {
            Params fs = def.pattern("face_shift");
            nextFace = Math.min(nextFace, now + ticks(Floor07Logic.faceInterval(3, fs.dbl("interval", 20), fs.dbl("p3_interval", 10))));
            broadcastBar("<light_purple><b>공명 붕괴</b></light_purple> <gray>— 두 얼굴이 숨 가쁘게 뒤바뀌고, 수정이 겹겹이 울린다…</gray>");
        }
    }

    private Vector dirTo(Location to) {
        Vector d = to.toVector().subtract(entity.getLocation().toVector()).setY(0);
        return d.lengthSquared() < 1e-4 ? facing() : d.normalize();
    }

    private Location eye() { return entity.getLocation().add(0, 1.65 * def.scale(), 0); }

    // 수정 궤도 ──────────────────────────────────────────────────────────

    /** 보스 중심 원 r4 경고 → 3초 동안 수정 파편이 돌며 0.5초마다 0.8배. 보스는 그 자리에서 궤도를 유지한다. */
    private int shardOrbit() {
        Params p = def.pattern("shard_orbit");
        int w = windup(p, 1.0);
        double r = p.dbl("radius", 4);
        int dur = Math.max(1, ticks(p.dbl("duration", 3)));
        int period = Math.max(1, ticks(p.dbl("tick", 0.5)));
        int hits = Math.max(1, dur / period);
        double dmg = dmg(p, "damage", 0.8);
        int n = Math.max(3, p.integer("shards", 6));
        String model = p.str("fx", "proj_crystal");
        Location c = feet();
        Telegraph.Shape circle = Telegraph.Shape.circle(c, r);
        telegraph(circle, w, Telegraph.RED, null, () -> {
            List<ItemDisplay> shards = new ArrayList<>();
            for (int i = 0; i < n; i++) shards.add(fx.model(model, c.clone().add(0, 1.2, 0), 1.6f, Display.Billboard.FIXED));
            ItemDisplay plate = fx.plate(circle, "telegraph_circle");
            BossFx.sound(c, Sound.BLOCK_AMETHYST_CLUSTER_PLACE, 2f, 0.6f);
            final int[] done = {0};
            run(new Mechanics.Repeat(dur, 1, tt -> {
                double spin = Math.toRadians(tt * 14.0);
                for (int i = 0; i < shards.size(); i++) {
                    ItemDisplay d = shards.get(i);
                    if (d == null || !d.isValid()) continue;
                    double a = spin + 2 * Math.PI * i / shards.size();
                    double rr = r * (0.55 + 0.25 * Math.sin(tt * 0.3 + i));
                    Location at = c.clone().add(Math.cos(a) * rr, 1.0 + 0.4 * Math.sin(tt * 0.2 + i * 1.3), Math.sin(a) * rr);
                    at.setYaw(0);
                    at.setPitch(0);
                    d.teleport(at);
                    fx.orient(d, new Vector(-Math.sin(a), 0, Math.cos(a)), 1.6f, 1.6f, 1);
                }
                if (tt % period == 0 && done[0] < hits) {
                    done[0]++;
                    hitShape(circle, dmg, "shard_orbit", DamageType.MAGIC, null);
                    BossFx.sound(c, Sound.BLOCK_AMETHYST_BLOCK_HIT, 1.4f, 0.8f + 0.1f * done[0]);
                }
                if (tt % 3 == 0) BossFx.dustRing(c, r * (0.4 + 0.6 * rng.nextDouble()), rng.nextBoolean() ? LIGHT : DARK, 1.0f, 10);
                return true;
            }, () -> {
                for (ItemDisplay d : shards) fx.discard(d);
                fx.discard(plate);
            }, true));
        });
        return cast("shard_orbit", "수정 궤도", w, w + dur + 6, BossAnim.SPIN, null, false);
    }

    // 수정비 ──────────────────────────────────────────────────────────────

    /** 무작위 원 r2.5 여러 개 (4 + (n−1)개): 한 명당 하나는 발밑, 나머지는 아레나 무작위. 위에서 수정이 떨어진다. */
    private int crystalRain() {
        Params p = def.pattern("crystal_rain");
        int count = scaling().count(p, "count", 4, 24);
        int w = windup(p, 1.3);
        double r = p.dbl("radius", 2.5);
        double dmg = dmg(p, "damage", 1.2);
        String model = p.str("fx", "proj_crystal");
        List<Location> spots = new ArrayList<>();
        List<Player> ts = targets();
        java.util.Collections.shuffle(ts, rng);
        for (Player t : ts) {
            if (spots.size() >= count) break;
            spots.add(ground(t.getLocation()));
        }
        for (int tries = 0; spots.size() < count && tries < count * 8; tries++) {
            Location l = randomPoint(0, arenaRadius - 1.5);
            boolean clash = false;
            for (Location s : spots) if (horizontal(s, l) < r * 1.2) clash = true;
            if (!clash || tries > count * 6) spots.add(ground(l));
        }
        if (spots.isEmpty()) return 0;
        for (Location s : spots) {
            Telegraph.Shape c = Telegraph.Shape.circle(s, r);
            Location top = s.clone().add(0, 10, 0);
            run(new Mechanics.Projectile(fx, model, 2.2f, Mechanics.Projectile.straight(top, new Vector(0, -1, 0), 9.6 / Math.max(1, w)), w, 0,
                    false, Particle.END_ROD, List::of, pl -> { }, null));
            telegraph(c, w, Telegraph.RED, null, () -> {
                hitShape(c, dmg, "crystal_rain", DamageType.MAGIC, null);
                BossFx.sound(s, Sound.BLOCK_AMETHYST_CLUSTER_BREAK, 1.6f, 0.7f + rng.nextFloat() * 0.4f);
                BossFx.dust(s.clone().add(0, 0.4, 0), rng.nextBoolean() ? LIGHT : DARK, 1.4f, 16, r * 0.4);
                BossFx.particle(Particle.END_ROD, s.clone().add(0, 0.3, 0), 6, r * 0.3, 0.2, r * 0.3, 0.04);
            });
        }
        BossFx.sound(entity.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 2f, 0.5f);
        return cast("crystal_rain", "수정비", Math.min(w, 20), 20, BossAnim.CAST, null, false);
    }

    // 극성 파동 (핵심) ────────────────────────────────────────────────────

    private int polarityWave() {
        Params p = def.pattern("polarity_wave");
        int w = windup(p, 3.0);
        boolean dbl = phase() >= 3 && p.bool("p3_double", true);
        int gap = dbl ? windupSec(p.dbl("p3_gap", 2.5)) : 0;
        List<Polarity> seq = Floor07Logic.waveSequence(chooseWaveColor(w), dbl);
        wave(seq, 0, w, p);
        String name = "극성 파동 — " + seq.get(0).label() + (dbl ? " → " + seq.get(1).label() : "");
        return cast("polarity_wave", name, w, w + gap + 12, BossAnim.CAST, null, false);
    }

    /**
     * 파동 색: 무작위. 솔로 대체 — 혼자인데 기둥 재사용 대기 때문에 경고 안에 색을 못 바꾸면 지금 색으로 (못 피하는 파동 금지).
     */
    private Polarity chooseWaveColor(int windupTicks) {
        Polarity pick = rng.nextBoolean() ? Polarity.LIGHT : Polarity.DARK;
        if (scaling().solo()) {
            List<Player> ts = targets();
            if (!ts.isEmpty()) {
                Player s = ts.get(0);
                Polarity cur = polarityOf(s);
                if (cur != null && Floor07Logic.swapRemaining(now, ready(s)) > windupTicks - 20) pick = cur;
            }
        }
        return pick;
    }

    /** seq[i] 색 파동 경고 (windup w) → 발동 → 다음 색이 있으면 기둥 재사용 초기화 + 반대 색 파동. */
    private void wave(List<Polarity> seq, int i, int w, Params p) {
        Polarity col = seq.get(i);
        boolean more = i + 1 < seq.size();
        charging = col;
        rig.setGlow(color(col));
        Location c = ground(center);
        Telegraph.Shape all = Telegraph.Shape.circle(c, arenaRadius + 1);
        String model = p.str(col == Polarity.LIGHT ? "fx_light" : "fx_dark", col == Polarity.LIGHT ? "telegraph_light" : "telegraph_dark");
        if (i == 0) {
            broadcastBar(col.phrase("의 파동!") + " <gray>수정이 " + col.label() + "으로 차오른다…"
                    + (more ? " 그 뒤에서 다른 빛깔이 웅크린다." : "") + "</gray>");
        } else {
            broadcastBar(col.phrase("의 파동이 이어진다!") + " <gray>기둥들이 다시 울린다…</gray>");
        }
        // 차오름: 보스 둘레로 그 색 입자가 나선으로 올라간다
        run(new Mechanics.Repeat(w, 2, tt -> {
            Location base = entity.getLocation();
            double k = tt / (double) Math.max(1, w);
            for (int j = 0; j < 3; j++) {
                double a = tt * 0.35 + j * 2.094;
                double rr = 1.4 + 0.6 * (1 - k);
                BossFx.dust(base.clone().add(Math.cos(a) * rr, 0.3 + 3.4 * k * def.scale() / 2, Math.sin(a) * rr), color(col), 1.4f, 1, 0);
            }
            if (tt % 10 == 0) BossFx.sound(base, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1.4f, (float) (0.5 + k * (col == Polarity.LIGHT ? 1.3 : 0.7)));
            return true;
        }, null, true));
        telegraph(all, w, color(col), model, () -> {
            fireWave(col, p);
            if (more) {
                if (p.bool("p3_reset_swap", true)) swapReady.clear();
                int gap = windupSec(p.dbl("p3_gap", 2.5));
                cast("polarity_wave", "극성 파동 — " + seq.get(i + 1).label() + " (2연속)", gap, gap + 12, BossAnim.CAST, null, false);
                wave(seq, i + 1, gap, p);
            } else {
                charging = null;
                rig.setGlow(enraged() ? ENRAGE : null);
                applyFaceLight();
            }
        });
    }

    private void fireWave(Polarity col, Params p) {
        double dmg = dmg(p, "damage", 3.0);
        Location c = feet();
        for (Player pl : players()) {
            double m = Floor07Logic.waveMult(polarityOf(pl), col, 1.0);
            if (m <= 0) {
                BossFx.dust(pl.getLocation().add(0, 1.0, 0), color(col), 1.2f, 10, 0.4);
                if (!quiet(pl, 10)) notify(pl, col.tag() + " <gray>파동이 당신을 스치고 지나간다…</gray>");
                continue;
            }
            hit(pl, dmg * m, "polarity_wave", DamageType.MAGIC);
            BossFx.particle(Particle.CRIT, pl.getLocation().add(0, 1.0, 0), 10, 0.3, 0.5, 0.3, 0.2);
            if (!quiet(pl, 10)) notify(pl, "<red><b>파동이 꿰뚫는다!</b></red> " + col.tag() + " <gray>이 당신을 밀어낸다…</gray>");
        }
        BossFx.sound(c, Sound.BLOCK_AMETHYST_BLOCK_BREAK, 2f, col == Polarity.LIGHT ? 1.2f : 0.5f);
        BossFx.sound(c, col == Polarity.LIGHT ? Sound.BLOCK_BEACON_ACTIVATE : Sound.BLOCK_BEACON_DEACTIVATE, 2f, 0.6f);
        BossFx.sound(c, Sound.ENTITY_GENERIC_EXPLODE, 0.7f, 1.4f);
        for (int i = 1; i <= 8; i++) {
            double rr = (arenaRadius + 1) * i / 8.0;
            afterPersistent(i, () -> BossFx.dustRing(c, rr, color(col), 1.6f, (int) Math.max(12, rr * 5)));
        }
    }

    // 분광 광선 ───────────────────────────────────────────────────────────

    private int splitBeam() {
        Params p = def.pattern("split_beam");
        List<Player> ts = targets();
        if (ts.isEmpty()) return 0;
        int w = windup(p, 2.5);
        if (scaling().solo() || ts.size() == 1) {
            // 솔로 대체: 광선 하나 — 기둥을 쓸 수 있으면 반대 색(바꿔서 0.6배), 대기 중이면 지금 색(그대로 흡수)
            Player t = ts.get(0);
            Polarity cur = polarityOf(t);
            boolean canSwap = Floor07Logic.swapRemaining(now, ready(t)) <= Math.max(0, w - 20);
            beam(Floor07Logic.soloBeamColor(cur, canSwap), t, w, p);
        } else {
            Player a = pickBeamTarget(ts, Polarity.DARK, null);   // 빛 광선 → 어둠 극성 대상
            Player b = pickBeamTarget(ts, Polarity.LIGHT, a);     // 어둠 광선 → 빛 극성 대상
            if (a != null) beam(Polarity.LIGHT, a, w, p);
            if (b != null) beam(Polarity.DARK, b, w, p);
        }
        BossFx.sound(entity.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 2f, 0.6f);
        return cast("split_beam", "분광 광선", w, w + 10, BossAnim.CAST, null, false);
    }

    private Player pickBeamTarget(List<Player> ts, Polarity want, Player exclude) {
        List<Player> c = new ArrayList<>();
        for (Player p : ts) if (p != exclude && polarityOf(p) == want) c.add(p);
        if (c.isEmpty()) for (Player p : ts) if (p != exclude) c.add(p);
        return c.isEmpty() ? null : c.get(rng.nextInt(c.size()));
    }

    private double beamLength(Player t, double len) {
        return Math.max(len, horizontal(entity.getLocation(), t.getLocation()) + 1.5);
    }

    /** 보스 → 대상 광선 경고 (대상을 따라 돈다) → 발동 순간 대상 쪽으로 쏴서 흡수 판정. */
    private void beam(Polarity col, Player t, int w, Params p) {
        double width = p.dbl("width", 1.5);
        double len = p.dbl("length", 22);
        String model = p.str(col == Polarity.LIGHT ? "fx_light" : "fx_dark", col == Polarity.LIGHT ? "telegraph_beam_light" : "telegraph_beam_dark");
        Telegraph tg = new Telegraph(fx, Telegraph.Shape.line(feet(), dirTo(t.getLocation()), beamLength(t, len), width), w, color(col), model,
                () -> fireBeam(col, t, p));
        tg.onTick(g -> {
            if (t.isValid() && g.elapsed() % 2 == 0) g.reshape(Telegraph.Shape.line(feet(), dirTo(t.getLocation()), beamLength(t, len), width));
        });
        run(tg);
        notify(t, col.phrase("의 광선이 당신을 겨눈다!"));
        BossFx.sound(t.getLocation(), Sound.BLOCK_NOTE_BLOCK_BELL, 1f, col == Polarity.LIGHT ? 1.6f : 0.7f);
    }

    private void fireBeam(Polarity col, Player t, Params p) {
        if (!isAlive()) return;
        double width = p.dbl("width", 1.5);
        boolean targetOk = validPlayer(t);
        Vector dir = targetOk ? dirTo(t.getLocation()) : facing();
        double len = targetOk ? beamLength(t, p.dbl("length", 22)) : p.dbl("length", 22);
        Location from = feet();
        List<Player> inLine = new ArrayList<>();
        List<Double> along = new ArrayList<>();
        for (Player pl : players()) {
            Location l = pl.getLocation();
            if (!BossMath.heightOk(from.getY(), l.getY())) continue;
            boolean in = BossMath.inLine(from.getX(), from.getZ(), dir.getX(), dir.getZ(), len, width, l.getX(), l.getZ());
            if (!in && !(pl == t && targetOk)) continue;
            inLine.add(pl);
            along.add((l.getX() - from.getX()) * dir.getX() + (l.getZ() - from.getZ()) * dir.getZ());
        }
        double[] al = new double[inLine.size()];
        Polarity[] pols = new Polarity[inLine.size()];
        for (int i = 0; i < al.length; i++) {
            al[i] = along.get(i);
            pols[i] = polarityOf(inLine.get(i));
        }
        double soakMult = p.dbl("soak_damage", 0.6);
        double[] mult = Floor07Logic.resolveBeam(al, pols, col, soakMult, p.dbl("damage", 3.0));
        int absorber = Floor07Logic.absorberIndex(al, pols, col);
        double endAlong = len;
        for (int i = 0; i < mult.length; i++) {
            if (mult[i] <= 0) continue;
            Player pl = inLine.get(i);
            hit(pl, damage() * mult[i], "split_beam", DamageType.MAGIC);
            if (i == absorber) {
                endAlong = Math.max(1, al[i]);
                BossFx.dust(pl.getLocation().add(0, 1.0, 0), color(col), 1.6f, 20, 0.4);
                notify(pl, "<green><b>광선 흡수!</b></green> " + col.tag() + " <gray>이 당신 안에서 잦아든다…</gray>");
            } else {
                BossFx.particle(Particle.CRIT, pl.getLocation().add(0, 1.0, 0), 12, 0.3, 0.5, 0.3, 0.2);
                if (!quiet(pl, 10)) notify(pl, "<red><b>광선 직격!</b></red> " + col.tag() + " <gray>이 살을 태운다…</gray>");
            }
        }
        // 광선 연출: 보스 가슴 → 흡수 지점(또는 끝)
        Location a = eye().subtract(0, 0.4 * def.scale(), 0);
        Location b = from.clone().add(dir.clone().multiply(endAlong)).add(0, 1.1, 0);
        String model = p.str(col == Polarity.LIGHT ? "fx_beam_light" : "fx_beam_dark", col == Polarity.LIGHT ? "beam_light" : "beam_dark");
        ItemDisplay ray = fx.tether(model, a, b);
        if (ray != null) ray.setBrightness(new Display.Brightness(15, 15));
        afterPersistent(10, () -> fx.discard(ray));
        BossFx.dustLine(a, b, color(col), 1.3f, 0.5);
        BossFx.sound(a, Sound.ENTITY_GUARDIAN_ATTACK, 1.6f, col == Polarity.LIGHT ? 1.7f : 0.8f);
        BossFx.sound(b, Sound.BLOCK_AMETHYST_BLOCK_BREAK, 1.2f, 1.2f);
    }

    // 굴절 ────────────────────────────────────────────────────────────────

    private int prismRefraction() {
        Params p = def.pattern("prism_refraction");
        if (refracting) return 0;
        int w = windup(p, 1.0);
        int dur = ticks(p.dbl("duration", 6));
        run(new Mechanics.Repeat(w, 2, tt -> {
            Location e = eye();
            for (int j = 0; j < 4; j++) {
                double a = rng.nextDouble() * Math.PI * 2;
                double rr = 3.5 - 2.5 * tt / (double) Math.max(1, w);
                BossFx.dust(e.clone().add(Math.cos(a) * rr, (rng.nextDouble() - 0.5) * 2, Math.sin(a) * rr), rng.nextBoolean() ? LIGHT : DARK, 1.2f, 1, 0);
            }
            return true;
        }, null, true));
        after(w, () -> startRefraction(dur, p));
        return cast("prism_refraction", "굴절", w, w + 6, BossAnim.CAST, null, false);
    }

    private Location shellAt() {
        Location at = entity.getLocation().add(0, 1.6 * def.scale(), 0);
        at.setYaw(0);
        at.setPitch(0);
        return at;
    }

    private void startRefraction(int dur, Params p) {
        refracting = true;
        float scale = (float) Math.max(1.0, def.scale() * 0.8);
        shell = fx.model(p.str("fx", "refraction_shell"), shellAt(), scale, Display.Billboard.FIXED);
        if (shell != null) shell.setBrightness(new Display.Brightness(15, 15));
        BossFx.sound(entity.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 2f, 1.0f);
        BossFx.sound(entity.getLocation(), Sound.BLOCK_GLASS_PLACE, 1.6f, 0.6f);
        broadcastBar("<light_purple><b>굴절!</b></light_purple> <gray>수정 껍질이</gray> " + face.tag() + "<gray>을 머금고 번뜩인다…</gray>");
        refreshBars();
        run(new Mechanics.Repeat(dur, 1, tt -> {
            if (shell != null && shell.isValid()) shell.teleport(shellAt());
            if (tt % 4 == 0 && !casting()) {
                timerBar("<light_purple>굴절</light_purple> " + face.tag() + " <dark_gray>⌛ " + Text.num(Math.max(0, dur - tt) / 20.0) + "</dark_gray>",
                        1f - tt / (float) dur, BossBar.Color.PINK);
            }
            if (tt % 5 == 0) {
                Location e = eye();
                double a = rng.nextDouble() * Math.PI * 2;
                BossFx.dust(e.clone().add(Math.cos(a) * 2.2, (rng.nextDouble() - 0.5) * 3, Math.sin(a) * 2.2), color(face), 1.3f, 2, 0.1);
                BossFx.particle(Particle.END_ROD, e, 1, 1.4, 1.4, 1.4, 0.01);
            }
            return true;
        }, () -> {
            refracting = false;
            fx.discard(shell);
            shell = null;
            hideTimerBar();
            if (isAlive()) {
                BossFx.sound(entity.getLocation(), Sound.BLOCK_GLASS_BREAK, 1.6f, 1.2f);
                broadcastBar("<gray>굴절 껍질이 부서졌다</gray>");
            }
        }, true));
    }

    @Override
    protected void onEnd() {
        if (interceptor != null) services.damage().removeInterceptor(interceptor);
        interceptor = null;
        for (UUID id : barShown) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) services.hud().hideBossBar(p, BAR_KEY);
        }
        barShown.clear();
        bars.clear();
        for (ItemDisplay m : marks.values()) fx.discard(m);
        marks.clear();
        fx.discard(shell);
        shell = null;
        refracting = false;
        nextTick.clear();
    }
}
