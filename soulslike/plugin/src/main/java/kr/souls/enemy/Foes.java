package kr.souls.enemy;

import com.destroystokyo.paper.event.entity.EntityRemoveFromWorldEvent;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.DamageCalc;
import kr.souls.combat.Hit;
import kr.souls.skill.Targets;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityRemoveEvent;
import org.bukkit.event.world.EntitiesUnloadEvent;
import org.bukkit.util.Vector;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.BiConsumer;
import java.util.function.Consumer;
import java.util.function.LongSupplier;
import java.util.function.Predicate;

/**
 * 우리 적의 등록부와 계약 (M1 P1-0 의 틀, P1b 가 채웠다. 부르는 쪽은 P1a·P3·P5·P7·P8).
 * <pre>
 *   Foe of(Entity e)                          우리 적이 아니면 null
 *   List&lt;Foe&gt; near(Location eye, double r)     눈에서 히트박스 가장자리까지 r 안 (가까운 차례)
 *   HitResult hit(Player by, Foe f, Hit h)    방어·가상 체력·맞는 손맛. lastCombatTick 을 찍는다 (R23)
 *   &lt;T extends Mob&gt; T spawn(String id, Location at)   enemies.yml 의 몸으로 (randomizeData=false, 어른, 떨굼 0, 조용히: R8)
 *   boolean teleport(Foe f, Location to)      탑승물 (P8 의 표식) 을 태운 채 옮긴다 (R6)
 * </pre>
 * 적의 몸은 늘 {@link #spawn} / {@link #body} 로 만들고 {@link #teleport} 로 옮긴다. world.spawn·entity.teleport 를 바로 부르지 않는다
 * (M1_PLAN 0.7). R6 은 1.21.11 에서 바뀌었다 (P1-0 의 contract 봇이 잰 것): 예전 Paper 는 탑승물이 있는 몸을 옮기지 않아
 * TeleportFlag.EntityState.RETAIN_PASSENGERS 가 있어야 했는데, 1.21.10 부터 이 깃발은 없앨 것으로 표시되었고 깃발 없는 teleport 도
 * 탑승물을 태운 채 옮긴다 (CONTRACT_TP plain=true plainkept=true). 그래서 {@link #teleport} 는 깃발 없이 옮기되, 옮기는 곳은 그대로
 * 여기 하나다 (판이 바뀌어 다시 깃발이 필요해지면 여기만 고친다. contract 봇이 표식이 남는지 본다).
 * <p>
 * 몸 (FoeBody) 에는 태그 souls_foe 와 souls_ent (켤 때 쓸기, Souls.SWEEP_TAGS) 가 붙고 저장되지 않는다: 청크가 내려가면 사라지므로
 * 등록부는 EntityRemoveFromWorldEvent 로 지우고 (R7), 세우는 쪽 (P1b 의 Dojo) 이 틱마다 다시 세운다. 등록부에서 빠질 때마다
 * {@link #onGone} 에 건 쪽에 왜 빠졌는지 (hit 맞아 쓰러짐, kill 바닐라 /kill, clear 지움, unload 청크가 내려감, 그 밖은 Paper 의
 * EntityRemoveEvent 원인 이름) 를 알린다.
 * <p>
 * 적은 enemies.yml 의 정의 (EnemyDefs) 와 가상 체력 (VirtualHealth: 최대치 = hp × 난이도 enemy-health, 생길 때 한 번) 을 가진
 * {@link Live}. 정의를 다시 읽어도 (/souls reload) 이미 선 적은 그대로이고 새로 서는 적부터 새 값이다. 맞으면 가상 체력이 깎이고
 * 손맛 (FoeBody.feel: 아파하는 몸짓·재질 소리·핏방울) 이 나며, 0 이 되면 setHealth(0) 으로 바닐라 쓰러짐 몸짓을 쓴다 (6.1. 떨굼·경험치 0).
 * <p>
 * 시험 줄 (서버 기록, 봇은 서버 기록에서 읽는다): FOE spawn|die|gone id= why= …
 */
public final class Foes implements Listener {
    /** 적의 몸 태그 */
    public static final String TAG = "souls_foe";
    /** 적의 표식 (P8 의 고정 표식, 탑승물) 태그 */
    public static final String MARK_TAG = "souls_mark";

    private final Souls plugin;
    private final Map<UUID, Foe> all = new LinkedHashMap<>();
    private final EnemyDefs defs = new EnemyDefs();
    /** 등록부에서 빠질 때 부르는 쪽 (Dojo …) */
    private final List<BiConsumer<Foe, String>> gone = new ArrayList<>();
    /** EntityRemoveEvent 가 알려 준 원인 (EntityRemoveFromWorldEvent 가 꺼낸다) */
    private final Map<UUID, String> causes = new HashMap<>();
    /** 몹이 아닌 몸 이름을 한 번만 알린다 */
    private final Set<String> warned = new HashSet<>();

    public Foes(Souls plugin) {
        this.plugin = plugin;
        reload();
    }

    /** enemies.yml 을 다시 읽는다 (켤 때, /souls reload. Content.reload 다음). */
    public void reload() {
        YamlConfiguration jar = null;
        try (InputStream in = plugin.getResource("content/enemies.yml")) {
            if (in != null) jar = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
        } catch (IOException ignored) {
            // jar 사본을 못 읽으면 겹쳐 읽은 값과 기본값만
        }
        defs.load(plugin.content().merged("enemies.yml"), jar, msg -> plugin.getLogger().warning(msg));
        warned.clear();
    }

    /** 적 정의 (enemies.yml). */
    public EnemyDefs defs() {
        return defs;
    }

    // ── 계약 ──

    /** 우리 적이면 그 Foe (쓰러졌거나 사라진 몸은 null). */
    public Foe of(Entity e) {
        if (e == null) return null;
        Foe f = all.get(e.getUniqueId());
        return f != null && f.entity().isValid() ? f : null;
    }

    /** 눈 (eye) 에서 히트박스 가장자리까지 r 안에 있는 살아 있는 적 (가까운 차례). */
    public List<Foe> near(Location eye, double r) {
        List<Foe> out = new ArrayList<>();
        if (eye == null || eye.getWorld() == null) return out;
        for (Foe f : all.values()) {
            Mob m = f.entity();
            if (!f.alive() || m.getWorld() != eye.getWorld()) continue;
            if (Targets.distToBox(m, eye) <= r) out.add(f);
        }
        out.sort(Comparator.comparingDouble(f -> Targets.distToBox(f.entity(), eye)));
        return out;
    }

    /**
     * 한 대를 넣는다: 피해 = DamageCalc.toFoe(raw, 방어력, 흡수, 약점), 가상 체력을 깎고, 때린 사람의 lastCombatTick 을 찍고 (R23),
     * 손맛 (맞는 쪽으로 아파하는 몸짓, 재질 소리, 핏방울) 을 낸다. 0 이 되면 등록부에서 빼고 (FOE die why=hit) 바닐라 쓰러짐 몸짓.
     */
    public HitResult hit(Player by, Foe f, Hit h) {
        if (f == null || h == null || !f.alive()) return HitResult.NONE;
        long now = plugin.ticker().now();
        if (by != null) CombatState.of(by).lastCombatTick = now;
        double def = f.def();
        double dealt = DamageCalc.toFoe(h.raw(), def, f.absorb(h.type()), f.weak(h.type()));
        double before = f.hp();
        double hp = f.hurt(dealt);
        dealt = Math.max(0, before - hp);
        Mob m = f.entity();
        Vector d = h.dir();
        if (d == null && by != null) d = m.getLocation().toVector().subtract(by.getLocation().toVector()).setY(0);
        boolean killed = hp <= 0;
        FoeBody.feel(m, f instanceof Live l ? l.def.material() : EnemyDefs.MATERIAL, d, dealt, f.max(), killed);
        if (killed) {
            drop(f, "hit", by == null ? "-" : by.getName());
            // 바닐라 쓰러짐 몸짓 (20틱 뒤 몸이 사라진다. 떨굼·경험치는 FoeBody 가 0 으로)
            m.setHealth(0);
        }
        return new HitResult(true, h.raw(), def, dealt, hp, killed);
    }

    /**
     * enemies.yml 의 id 로 몸을 세우고 등록한다. 그 id 가 없거나 몸이 몹이 아니면 null (서버 기록에 알린다). 가상 체력 = hp × 난이도
     * enemy-health (생길 때 한 번).
     */
    @SuppressWarnings("unchecked")
    public <T extends Mob> T spawn(String id, Location at) {
        Live f = spawn(id, at, "api");
        return f == null ? null : (T) f.entity();
    }

    /** {@link #spawn(String, Location)} 에 왜 세우는지 (시험 줄 FOE spawn why=, dojo·cmd·api) 를 붙인 것. 세운 적 (없으면 null). */
    public Live spawn(String id, Location at, String why) {
        EnemyDefs.Def d = defs.get(id);
        if (d == null) {
            plugin.getLogger().warning("enemies.yml 에 적 " + id + " 이 없어 세우지 않았습니다.");
            return null;
        }
        return spawn(d, at, d.hp(), why, null);
    }

    /**
     * 정의 d 로 세운다. baseHp: 난이도 배율 전의 가상 체력 (보통 d.hp(), 시험 명령이 바꿀 수 있다). init: 세계에 놓이기 전에 더 할 일.
     */
    public Live spawn(EnemyDefs.Def d, Location at, double baseHp, String why, Consumer<? super Mob> init) {
        if (d == null || at == null || at.getWorld() == null) return null;
        Class<? extends Mob> cls = mobClass(d.body());
        if (cls == null) {
            if (warned.add(d.id())) plugin.getLogger().warning("enemies.yml 의 " + d.id() + ".body " + d.body() + " 는 몹이 아니라 세우지 않았습니다.");
            return null;
        }
        double max = VirtualHealth.maxFor(baseHp, plugin.difficulty().enemyHealth());
        Mob m = FoeBody.make(cls, at, d.id(), d, init);
        if (m == null) return null;
        Live f = new Live(d, m, new VirtualHealth(max, d.regenAfter()), at.clone(), plugin.ticker()::now);
        register(f);
        Location l = m.getLocation();
        plugin.test(null, String.format(Locale.ROOT, "FOE spawn id=%s why=%s hp=%.1f def=%.1f type=%s x=%.2f y=%.2f z=%.2f yaw=%.0f eid=%d", d.id(), why,
                max, d.def(), m.getType().getKey().getKey(), l.getX(), l.getY(), l.getZ(), l.getYaw(), m.getEntityId()));
        return f;
    }

    /** 옮긴다. 탑승물 (표식) 을 태운 채 (R6). */
    public boolean teleport(Foe f, Location to) {
        return f != null && teleport(f.entity(), to);
    }

    // ── 몸 도우미 (계약 시험과 나중 묶음이 쓴다) ──

    /**
     * 적의 몸을 세운다 (R8, FoeBody.make: 무작위 없이, 어른, 떨굼 0, 조용히, 바닐라 목표 지우기, 넉백 저항 1, 줍지 않기, 습격대 아님,
     * 저장하지 않기와 멀어도 사라지지 않기, 태그 souls_foe + souls_ent, PDC souls:mob = id). init 은 세계에 놓이기 전에 더 할 일 (없으면
     * null). 등록은 하지 않는다 ({@link #register}).
     */
    public static <T extends Mob> T body(Class<T> cls, Location at, String id, Consumer<? super T> init) {
        return FoeBody.make(cls, at, id, null, init);
    }

    /** 몸을 옮긴다. 탑승물을 태운 채 (1.21.11 의 teleport 는 깃발 없이도 탑승물을 남긴다, 위의 R6). */
    public static boolean teleport(Entity e, Location to) {
        return e != null && to != null && e.teleport(to);
    }

    /** "zombie" 같은 이름 → 몹 클래스 (몹이 아니면 null). */
    @SuppressWarnings("unchecked")
    public static Class<? extends Mob> mobClass(String name) {
        if (name == null) return null;
        NamespacedKey k = NamespacedKey.fromString(name.trim().toLowerCase(Locale.ROOT));
        EntityType t = k == null ? null : Registry.ENTITY_TYPE.get(k);
        Class<? extends Entity> c = t == null ? null : t.getEntityClass();
        return c != null && Mob.class.isAssignableFrom(c) ? (Class<? extends Mob>) c : null;
    }

    /** 등록한다 (같은 몸이면 바꾼다). */
    public void register(Foe f) {
        if (f != null && f.entity() != null) all.put(f.entity().getUniqueId(), f);
    }

    /** 등록에서 뺀다 (몸은 그대로, 알리지 않는다). */
    public void unregister(Entity e) {
        if (e != null) all.remove(e.getUniqueId());
    }

    /** 등록된 적 모두 (사본). */
    public Collection<Foe> all() {
        return List.copyOf(all.values());
    }

    /** 등록부에서 빠질 때 불린다 (적, 왜: hit·kill·clear·unload …). 세우는 쪽이 다시 세울 때를 정한다. */
    public void onGone(BiConsumer<Foe, String> fn) {
        if (fn != null) gone.add(fn);
    }

    /** 등록된 적의 몸을 모두 지운다 (FOE gone why=clear). 지운 수 (세계에 있던 몸). */
    public int clear() {
        return clear(f -> true);
    }

    /** which 에 맞는 적의 몸을 지운다. 지운 수 (세계에 있던 몸). */
    public int clear(Predicate<Foe> which) {
        int n = 0;
        for (Foe f : List.copyOf(all.values())) {
            if (!which.test(f)) continue;
            Mob m = f.entity();
            if (m.isValid()) n++;
            drop(f, "clear", null);
            m.remove();
        }
        return n;
    }

    /** 공허로 떨어진 몸을 처음 선 자리로 돌려보낸다 (FoeBody, 6.1). 돌아갈 자리가 있어 옮겼으면 true. */
    public boolean sendHome(Entity e) {
        Foe f = e == null ? null : all.get(e.getUniqueId());
        if (!(f instanceof Live l) || l.home == null || l.home.getWorld() != e.getWorld()) return false;
        e.setFallDistance(0);
        e.setVelocity(new Vector());
        return teleport(e, l.home);
    }

    /** 바닐라로 쓰러진 몸 (FoeBody 의 EntityDeathEvent): 아직 등록되어 있으면 뺀다. */
    void died(Entity e, String why) {
        Foe f = e == null ? null : all.get(e.getUniqueId());
        if (f != null) drop(f, why, null);
    }

    /** 등록부에서 빼고 알린다 (by: 때린 사람, 쓰러졌을 때만). */
    private void drop(Foe f, String why, String by) {
        Mob m = f.entity();
        if (all.remove(m.getUniqueId()) == null) return;
        causes.remove(m.getUniqueId());
        boolean died = "hit".equals(why) || "kill".equals(why);
        plugin.test(null, String.format(Locale.ROOT, "FOE %s id=%s why=%s%s eid=%d", died ? "die" : "gone", f.id(), why,
                by == null ? "" : " by=" + by, m.getEntityId()));
        for (BiConsumer<Foe, String> fn : List.copyOf(gone)) {
            try {
                fn.accept(f, why);
            } catch (RuntimeException ex) {
                plugin.getLogger().warning("적이 빠질 때의 처리 오류: " + ex);
            }
        }
    }

    /**
     * 몸이 지워질 원인을 적어 둔다. 등록부에서 빼는 것은 아래 EntityRemoveFromWorldEvent. 청크가 내려갈 때는 EntityRemoveEvent 가 오지 않아
     * (1.21.11 Paper 에서 잰 것: 원인 없이 EntityRemoveFromWorldEvent 만 왔다) 그 앞에 오는 EntitiesUnloadEvent 로 unload 를 적는다.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onRemoveCause(EntityRemoveEvent e) {
        UUID id = e.getEntity().getUniqueId();
        if (all.containsKey(id)) causes.putIfAbsent(id, e.getCause().name().toLowerCase(Locale.ROOT));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onUnload(EntitiesUnloadEvent e) {
        for (Entity en : e.getEntities()) if (all.containsKey(en.getUniqueId())) causes.put(en.getUniqueId(), "unload");
    }

    /** 청크가 내려가거나 지워지면 등록부에서 뺀다 (R7, FOE gone why=unload …). 다시 세우는 것은 세운 쪽의 틱이다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onRemove(EntityRemoveFromWorldEvent e) {
        UUID id = e.getEntity().getUniqueId();
        Foe f = all.get(id);
        String why = causes.remove(id);
        if (f != null) drop(f, why == null ? "removed" : why, null);
    }

    /** enemies.yml 의 정의와 가상 체력을 가진 적 (spawn 이 만든다). */
    public static final class Live implements Foe {
        private final EnemyDefs.Def def;
        private final Mob body;
        private final VirtualHealth health;
        private final Location home;
        private final LongSupplier clock;

        Live(EnemyDefs.Def def, Mob body, VirtualHealth health, Location home, LongSupplier clock) {
            this.def = def;
            this.body = body;
            this.health = health;
            this.home = home;
            this.clock = clock;
        }

        @Override public Mob entity() { return body; }
        @Override public String id() { return def.id(); }
        @Override public double hp() { return health.hp(clock.getAsLong()); }
        @Override public double max() { return health.max(); }
        @Override public double def() { return def.def(); }
        @Override public double absorb(Hit.Type type) { return def.absorbOf(type); }
        @Override public double weak(Hit.Type type) { return def.weakOf(type); }
        @Override public double hurt(double amount) { return health.hurt(amount, clock.getAsLong()); }

        /** 세울 때의 정의 (enemies.yml) */
        public EnemyDefs.Def definition() { return def; }

        /** 처음 선 자리 (공허에서 돌아오는 곳) */
        public Location home() { return home.clone(); }

        /** 가상 체력 */
        public VirtualHealth health() { return health; }
    }

    /** 이 틀의 적 (계약 시험이 쓴다: 정의 없이 가상 체력·방어력만). */
    public static final class Basic implements Foe {
        private final String id;
        private final Mob body;
        private final double max;
        private final double def;
        private double hp;

        public Basic(String id, Mob body, double max, double def) {
            this.id = id;
            this.body = body;
            this.max = Math.max(1, max);
            this.def = Math.max(0, def);
            this.hp = this.max;
        }

        @Override public Mob entity() { return body; }
        @Override public String id() { return id; }
        @Override public double hp() { return hp; }
        @Override public double max() { return max; }
        @Override public double def() { return def; }

        @Override
        public double hurt(double amount) {
            if (amount > 0) hp = Math.max(0, hp - amount);
            return hp;
        }
    }
}
