package kr.souls.enemy;

import com.destroystokyo.paper.event.entity.EntityRemoveFromWorldEvent;
import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.DamageCalc;
import kr.souls.combat.Hit;
import kr.souls.combat.TestHits;
import kr.souls.skill.Targets;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Raider;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;

/**
 * 우리 적의 등록부와 계약 (M1 P1-0 의 틀, P1b 가 채운다. 부르는 쪽은 P1a·P3·P5·P7·P8).
 * <pre>
 *   Foe of(Entity e)                          우리 적이 아니면 null
 *   List&lt;Foe&gt; near(Location eye, double r)     눈에서 히트박스 가장자리까지 r 안 (가까운 차례)
 *   HitResult hit(Player by, Foe f, Hit h)    방어·가상 체력·맞는 몸짓. lastCombatTick 을 찍는다 (R23)
 *   &lt;T extends Mob&gt; T spawn(String id, Location at)   enemies.yml 의 몸으로 (randomizeData=false, 어른, 떨굼 0, 조용히: R8)
 *   boolean teleport(Foe f, Location to)      탑승물 (P8 의 표식) 을 태운 채 옮긴다 (R6)
 * </pre>
 * 적의 몸은 늘 {@link #spawn} / {@link #body} 로 만들고 {@link #teleport} 로 옮긴다. world.spawn·entity.teleport 를 바로 부르지 않는다
 * (M1_PLAN 0.7). R6 은 1.21.11 에서 바뀌었다 (P1-0 의 contract 봇이 잰 것): 예전 Paper 는 탑승물이 있는 몸을 옮기지 않아
 * TeleportFlag.EntityState.RETAIN_PASSENGERS 가 있어야 했는데, 1.21.10 부터 이 깃발은 없앨 것으로 표시되었고 깃발 없는 teleport 도
 * 탑승물을 태운 채 옮긴다 (CONTRACT_TP plain=true plainkept=true). 그래서 {@link #teleport} 는 깃발 없이 옮기되, 옮기는 곳은 그대로
 * 여기 하나다 (판이 바뀌어 다시 깃발이 필요해지면 여기만 고친다. contract 봇이 표식이 남는지 본다). 몸에는 태그 souls_foe 와 souls_ent (켤 때 쓸기, Souls.SWEEP_TAGS) 가 붙고 저장되지 않는다: 청크가 내려가면 사라지므로
 * 등록부는 EntityRemoveFromWorldEvent 로 지우고, 세우는 쪽 (P1b 의 Dojo) 이 틱마다 다시 세운다 (R7).
 * S12 (PS): 취소한 한 대에 클라이언트는 아무것도 하지 않는다 (붉은 번쩍임·치명 입자·달리기 멈춤 없음). 맞는 느낌은 모두 서버가 낸다
 * (여기의 hurt 몸짓, P1b 의 소리·피 입자).
 * 이 판 (틀) 이 하는 것: 등록부, 몸 만들기·옮기기, 방어 공식과 가상 체력 (enemies.yml 의 body·hp·def 셋만), 아파하는 몸짓, 쓰러지면
 * 몸을 지운다. P1b 가 EnemyDefs·VirtualHealth·FoeBody (AI 끄기, 넉백 저항, 바닐라 피해 막기, 소리·입자, 쓰러짐) 로 바꾼다.
 */
public final class Foes implements Listener {
    /** 적의 몸 태그 */
    public static final String TAG = "souls_foe";
    /** 적의 표식 (P8 의 고정 표식, 탑승물) 태그 */
    public static final String MARK_TAG = "souls_mark";

    private final Souls plugin;
    private final Map<UUID, Foe> all = new LinkedHashMap<>();

    public Foes(Souls plugin) {
        this.plugin = plugin;
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
     * 맞는 쪽으로 아파하는 몸짓을 보인다. 0 이 되면 쓰러진다 (이 틀은 몸을 지운다).
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
        // 몸짓의 yaw 는 몸이 보는 쪽에 대한 상대 각 (0 = 앞에서 맞았다)
        float yaw = 0;
        if (d != null && d.lengthSquared() > 1e-9) {
            float from = (float) Math.toDegrees(Math.atan2(-d.getX(), d.getZ())) + 180f;
            yaw = from - m.getBodyYaw();
        }
        m.playHurtAnimation(yaw);
        boolean killed = hp <= 0;
        if (killed) {
            all.remove(m.getUniqueId());
            m.remove();
        }
        return new HitResult(true, h.raw(), def, dealt, hp, killed);
    }

    /**
     * enemies.yml 의 id 로 몸을 세우고 등록한다. 그 id 가 없거나 몸이 몹이 아니면 null (서버 기록에 한 번). 가상 체력 = hp × 난이도
     * enemy-health (생길 때 한 번).
     */
    @SuppressWarnings("unchecked")
    public <T extends Mob> T spawn(String id, Location at) {
        ConfigurationSection d = plugin.content().merged("enemies.yml").getConfigurationSection(id == null ? "" : id);
        if (d == null) {
            plugin.getLogger().warning("enemies.yml 에 적 " + id + " 이 없어 세우지 않았습니다.");
            return null;
        }
        Class<? extends Mob> cls = mobClass(d.getString("body", "zombie"));
        if (cls == null) {
            plugin.getLogger().warning("enemies.yml 의 " + id + ".body " + d.getString("body") + " 는 몹이 아니라 세우지 않았습니다.");
            return null;
        }
        double max = Math.max(1, d.getDouble("hp", 100)) * plugin.difficulty().enemyHealth();
        double def = Math.max(0, d.getDouble("def", 20));
        T m = (T) body(cls, at, id, null);
        if (m != null) register(new Basic(id, m, max, def));
        return m;
    }

    /** 옮긴다. 탑승물 (표식) 을 태운 채 (R6). */
    public boolean teleport(Foe f, Location to) {
        return f != null && teleport(f.entity(), to);
    }

    // ── 틀이 주는 도우미 (P1b 의 FoeBody 도 이것을 쓴다) ──

    /**
     * 적의 몸을 세운다 (R8): randomizeData=false (아기·무작위 갑옷·닭 기수·변명자의 도끼가 없다), 어른, 모든 장비 떨굼 0, 조용히,
     * 아이템 줍지 않기, 습격대에 끼지 않기, 저장하지 않기 (setPersistent false) 와 멀어도 사라지지 않기, 태그 souls_foe + souls_ent,
     * PDC souls:mob = id. init 은 세계에 놓이기 전에 더 할 일 (없으면 null). 등록은 하지 않는다 ({@link #register}).
     */
    public static <T extends Mob> T body(Class<T> cls, Location at, String id, Consumer<? super T> init) {
        if (at == null || at.getWorld() == null || cls == null) return null;
        return at.getWorld().spawn(at, cls, false, m -> {
            if (m instanceof Ageable a) a.setAdult();
            EntityEquipment eq = m.getEquipment();
            for (EquipmentSlot s : EquipmentSlot.values()) {
                try {
                    eq.setDropChance(s, 0f);
                } catch (IllegalArgumentException ignored) {
                    // 이 몹에 없는 칸 (몸통·안장)
                }
            }
            m.setSilent(true);
            m.setCanPickupItems(false);
            m.setPersistent(false);
            m.setRemoveWhenFarAway(false);
            if (m instanceof Raider r) {
                r.setCanJoinRaid(false);
                r.setPatrolLeader(false);
            }
            m.addScoreboardTag(TAG);
            m.addScoreboardTag(TestHits.ENT_TAG);
            if (id != null) m.getPersistentDataContainer().set(Keys.MOB, PersistentDataType.STRING, id);
            if (init != null) init.accept(m);
        });
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

    /** 등록에서 뺀다 (몸은 그대로). */
    public void unregister(Entity e) {
        if (e != null) all.remove(e.getUniqueId());
    }

    /** 등록된 적 모두 (사본). */
    public Collection<Foe> all() {
        return List.copyOf(all.values());
    }

    /** 등록된 적의 몸을 모두 지운다. 지운 수. */
    public int clear() {
        int n = 0;
        for (Foe f : List.copyOf(all.values())) {
            if (f.entity().isValid()) n++;
            f.entity().remove();
        }
        all.clear();
        return n;
    }

    /** 청크가 내려가거나 지워지면 등록부에서 뺀다 (R7). 다시 세우는 것은 세운 쪽의 틱이다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onRemove(EntityRemoveFromWorldEvent e) {
        all.remove(e.getEntity().getUniqueId());
    }

    /** 이 틀의 적 (P1b 가 VirtualHealth·EnemyDefs 로 바꾼다). */
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
