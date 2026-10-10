package kr.souls.skill;

import kr.souls.Keys;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Tameable;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;

/**
 * 누가 누구의 적인지 판단한다. 플레이어끼리는 세계 설정의 PvP 가 켜졌고 맞는 사람이 보호받지 않을 때만 적이다 (5.7, combat/Pvp.allowed).
 * 플레이어 편에는 소환수가 없다 (skyblock 의 동료 분기는 뺐다).
 */
public final class Targets {
    public static final String BOSS_TAG = "souls_boss";

    /** 플레이어 → 플레이어를 해칠 수 있나 (Souls 가 combat/Pvp 를 끼운다. 끼우기 전에는 늘 거짓) */
    public static java.util.function.BiPredicate<Player, Player> pvp = (a, b) -> false;

    private Targets() {}

    public static boolean isCustomMob(Entity e) {
        return e != null && e.getPersistentDataContainer().has(Keys.MOB, PersistentDataType.STRING);
    }

    public static boolean isBoss(Entity e) {
        return e != null && e.getScoreboardTags().contains(BOSS_TAG);
    }

    public static boolean playerSide(Entity e) {
        return e instanceof Player;
    }

    public static boolean isEnemy(LivingEntity caster, Entity e) {
        if (!(e instanceof LivingEntity le) || e == caster) return false;
        if (le.isDead() || !le.isValid() || le.isInvulnerable()) return false;
        if (e instanceof ArmorStand) return false;
        if (e.getPersistentDataContainer().has(Keys.MAP_PART)) return false;
        if (playerSide(caster)) {
            // 플레이어끼리는 PvP 를 켰을 때만 (skyblock 의 getPVP 줄 대신)
            if (e instanceof Player other) return caster instanceof Player me && pvp.test(me, other);
            if (e instanceof Tameable t && t.isTamed()) return false;
            if (e instanceof Enemy) return true;
            if (isCustomMob(e)) return true;
            // 화가 난 중립 몹(늑대, 좀비 피글린 등)
            return e instanceof Mob m && m.getTarget() instanceof Player;
        } else {
            return e instanceof Player p && vulnerable(p);
        }
    }

    private static boolean vulnerable(Player p) {
        GameMode gm = p.getGameMode();
        return gm == GameMode.SURVIVAL || gm == GameMode.ADVENTURE;
    }

    /** 같은 편(치유/버프 대상). 시전자 자신 포함. */
    public static boolean isFriend(LivingEntity caster, Entity e) {
        if (!(e instanceof LivingEntity le) || le.isDead()) return false;
        if (e == caster) return true;
        if (playerSide(caster)) return e instanceof Player;
        return isCustomMob(e);
    }

    public static List<LivingEntity> enemiesNear(LivingEntity caster, Location c, double r) {
        List<LivingEntity> out = new ArrayList<>();
        if (c.getWorld() == null) return out;
        for (Entity e : c.getWorld().getNearbyEntities(c, r, r, r)) {
            if (!isEnemy(caster, e)) continue;
            LivingEntity le = (LivingEntity) e;
            if (distToBox(le, c) <= r) out.add(le);
        }
        return out;
    }

    public static List<LivingEntity> friendsNear(LivingEntity caster, Location c, double r) {
        List<LivingEntity> out = new ArrayList<>();
        if (c.getWorld() == null) return out;
        for (Entity e : c.getWorld().getNearbyEntities(c, r, r, r)) {
            if (isFriend(caster, e) && e.getLocation().distance(c) <= r + 0.5) out.add((LivingEntity) e);
        }
        return out;
    }

    /** 엔티티 히트박스까지의 거리. 큰 몬스터도 가장자리부터 맞게 한다. */
    public static double distToBox(LivingEntity e, Location p) {
        var box = e.getBoundingBox();
        double dx = Math.max(Math.max(box.getMinX() - p.getX(), 0), p.getX() - box.getMaxX());
        double dy = Math.max(Math.max(box.getMinY() - p.getY(), 0), p.getY() - box.getMaxY());
        double dz = Math.max(Math.max(box.getMinZ() - p.getZ(), 0), p.getZ() - box.getMaxZ());
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
}
