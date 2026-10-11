package kr.souls.enemy;

import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.combat.TestHits;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Raider;
import org.bukkit.entity.Zombie;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTransformEvent;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Vector;

import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Consumer;

/**
 * 적의 바닐라 몸 (DESIGN 6.1, M1 P1b). 몸을 세우는 법 (R8) 과 바닐라 몸이 저절로 하는 일 막기, 맞을 때의 손맛 (6.5, S12: 취소한 한 대에
 * 클라이언트는 아무것도 하지 않으니 모두 서버가 낸다).
 * <ul>
 *   <li>세우기 {@link #make}: spawn(at, cls, randomizeData=false, …) 라 아기·무작위 갑옷·닭 기수·변명자의 도끼가 없다. 어른, 모든 장비
 *       떨굼 0, 조용히 (바닐라 신음이 가짜 예고가 되지 않게), 바닐라 목표 모두 지우기 (removeAllGoals), 넉백 저항 1, 줍지 않기, 습격대·순찰대장
 *       아님, 태그 souls_foe + souls_ent, 저장하지 않기 (setPersistent false) 와 멀어도 사라지지 않기 (setRemoveWhenFarAway false: 앞의 것만
 *       걸면 바닐라가 32칸 밖에서 아무 때나 지운다), 좀비는 햇빛에 타지 않고 문을 부수지 않는다. 두뇌 없는 적 (ai: none, 허수아비) 은 AI 를
 *       끄고 (setAware false) 밀리지 않는다 (setCollidable false: 사람이 걸어 들어가도 제자리).</li>
 *   <li>막기 (리스너): 적에게 오는 바닐라 피해는 모두 취소한다 (가상 체력만 깎인다). 둘만 예외: 관리자의 /kill (KILL) 은 그대로 죽이고,
 *       공허 (VOID) 는 죽이지 않고 처음 선 자리로 돌려보낸다 (돌아갈 자리가 없는 몸은 그대로 떨어져 죽는다). 불붙기 (햇빛·불)·탈바꿈 (물속
 *       좀비 → 드라운드, 허스크 → 좀비) 을 막고, 쓰러지면 떨굼과 경험치를 0 으로.</li>
 *   <li>손맛 {@link #feel}: 맞는 쪽으로 아파하는 몸짓 (playHurtAnimation), 재질 소리 (enemies.yml material), 핏방울 (재질 색의 DUST, 깎인
 *       몫에 따라 많이), 쓰러지면 재질의 쓰러지는 소리.</li>
 * </ul>
 */
public final class FoeBody implements Listener {
    /** 재질마다 맞는 소리·쓰러지는 소리 (바닐라 소리 열쇠) 와 피 색 */
    record Feel(String hit, float pitch, String die, Color blood, float size) {}

    static final Map<EnemyDefs.Material, Feel> FEELS = Map.of(
            EnemyDefs.Material.FLESH, new Feel("minecraft:entity.zombie.hurt", 0.85f, "minecraft:entity.zombie.death", Color.fromRGB(0x5a, 0x0d, 0x0b), 1.1f),
            EnemyDefs.Material.BONE, new Feel("minecraft:entity.skeleton.hurt", 0.9f, "minecraft:entity.skeleton.death", Color.fromRGB(0xb9, 0xae, 0x92), 0.9f),
            EnemyDefs.Material.IRON, new Feel("minecraft:entity.iron_golem.hurt", 1.1f, "minecraft:entity.iron_golem.death", Color.fromRGB(0x6e, 0x64, 0x58), 0.8f),
            // 허수아비: 나무 거치대를 치는 둔한 소리와 짚 부스러기
            EnemyDefs.Material.STRAW, new Feel("minecraft:entity.armor_stand.hit", 0.8f, "minecraft:entity.armor_stand.break", Color.fromRGB(0x9c, 0x83, 0x4e), 1.0f));

    private final Souls plugin;

    public FoeBody(Souls plugin) {
        this.plugin = plugin;
    }

    /**
     * 적의 몸을 세운다 (위의 목록). def 가 있으면 두뇌 없는 적의 AI 를 끈다. at 의 yaw 로 몸과 머리를 돌린다. init 은 세계에 놓이기 전에 더 할 일
     * (없으면 null). 등록은 하지 않는다 (Foes.register).
     */
    public static <T extends Mob> T make(Class<T> cls, Location at, String id, EnemyDefs.Def def, Consumer<? super T> init) {
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
            if (m instanceof Zombie z) {
                z.setShouldBurnInDay(false);
                z.setCanBreakDoors(false);
            }
            AttributeInstance kb = m.getAttribute(Attribute.KNOCKBACK_RESISTANCE);
            if (kb != null) kb.setBaseValue(1.0);
            Bukkit.getMobGoals().removeAllGoals(m);
            if (def != null && def.brainless()) {
                m.setAware(false);
                m.setCollidable(false);
            }
            m.setRotation(at.getYaw(), 0f);
            m.setBodyYaw(at.getYaw());
            m.addScoreboardTag(Foes.TAG);
            m.addScoreboardTag(TestHits.ENT_TAG);
            if (id != null) m.getPersistentDataContainer().set(Keys.MOB, PersistentDataType.STRING, id);
            if (init != null) init.accept(m);
        });
    }

    /** 우리 적의 몸인가 (태그. 등록부에서 빠진 쓰러지는 몸도 포함). */
    public static boolean tagged(Entity e) {
        return e != null && e.getScoreboardTags().contains(Foes.TAG);
    }

    /**
     * 맞을 때의 손맛 (6.5). from: 맞는 쪽으로 미는 수평 방향 (때린 쪽에서 몸 쪽, null 이면 앞에서), dealt/max: 깎인 몫, killed: 이 한 대로
     * 쓰러졌다.
     */
    public static void feel(Mob m, EnemyDefs.Material mat, Vector from, double dealt, double max, boolean killed) {
        // 몸짓의 yaw 는 몸이 보는 쪽에 대한 상대 각 (0 = 앞에서 맞았다)
        float yaw = 0;
        if (from != null && from.lengthSquared() > 1e-9) {
            float dir = (float) Math.toDegrees(Math.atan2(-from.getX(), from.getZ())) + 180f;
            yaw = dir - m.getBodyYaw();
        }
        m.playHurtAnimation(yaw);
        Feel f = FEELS.getOrDefault(mat == null ? EnemyDefs.MATERIAL : mat, FEELS.get(EnemyDefs.MATERIAL));
        World w = m.getWorld();
        Location at = m.getLocation();
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        w.playSound(at, f.hit(), SoundCategory.HOSTILE, 1.0f, f.pitch() * (0.92f + 0.16f * rnd.nextFloat()));
        if (killed) w.playSound(at, f.die(), SoundCategory.HOSTILE, 1.0f, f.pitch());
        // 핏방울: 몸 가슴 높이, 때린 쪽 겉면. 깎인 몫 (최대치의 25% 면 가득) 에 따라 4..18 알
        double share = max > 0 ? Math.min(1, dealt / (max * 0.25)) : 1;
        int n = (int) Math.round(4 + 14 * share);
        Location c = at.clone().add(0, m.getHeight() * 0.62, 0);
        if (from != null && from.lengthSquared() > 1e-9) c.subtract(from.clone().setY(0).normalize().multiply(m.getWidth() * 0.5));
        w.spawnParticle(Particle.DUST, c, n, 0.18, 0.22, 0.18, 0, new Particle.DustOptions(f.blood(), f.size()));
    }

    // ── 바닐라 몸이 저절로 하는 일 막기 ──

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDamage(EntityDamageEvent e) {
        if (!tagged(e.getEntity())) return;
        switch (e.getCause()) {
            case KILL -> {
                // 관리자의 /kill: 그대로 죽는다 (쓰러지면 등록부에서 빠진다)
            }
            case VOID -> {
                if (plugin.foes() != null && plugin.foes().sendHome(e.getEntity())) e.setCancelled(true);
            }
            default -> e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onCombust(EntityCombustEvent e) {
        if (tagged(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onTransform(EntityTransformEvent e) {
        if (tagged(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDeath(EntityDeathEvent e) {
        if (!tagged(e.getEntity())) return;
        e.getDrops().clear();
        e.setDroppedExp(0);
        if (plugin.foes() != null) plugin.foes().died(e.getEntity(), "kill");
    }
}
