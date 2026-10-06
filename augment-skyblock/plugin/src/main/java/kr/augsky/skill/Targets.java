package kr.augsky.skill;

import kr.augsky.Keys;
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

/** 누가 누구의 적인지 판단한다. 플레이어끼리는 PvP 가 켜진 월드(server.properties 의 pvp)에서만 서로 맞는다. */
public final class Targets {
    public static final String BOSS_TAG = "augsky_boss";

    private Targets() {}

    public static boolean isAlly(Entity e) {
        return e != null && e.getPersistentDataContainer().has(Keys.ALLY, PersistentDataType.STRING);
    }

    public static boolean isCustomMob(Entity e) {
        return e != null && e.getPersistentDataContainer().has(Keys.MOB, PersistentDataType.STRING);
    }

    public static boolean isBoss(Entity e) {
        return e != null && e.getScoreboardTags().contains(BOSS_TAG);
    }

    public static boolean playerSide(Entity e) {
        return e instanceof Player || isAlly(e);
    }

    public static boolean isEnemy(LivingEntity caster, Entity e) {
        if (!(e instanceof LivingEntity le) || e == caster) return false;
        if (le.isDead() || !le.isValid() || le.isInvulnerable()) return false;
        if (e instanceof ArmorStand) return false;
        if (e.getPersistentDataContainer().has(Keys.MAP_PART)) return false;
        if (playerSide(caster)) {
            // 소환수는 다른 플레이어를 노리지 않는다. 플레이어가 직접 쓴 스킬·무기·증강만 PvP 에 들어간다
            if (e instanceof Player p) return caster instanceof Player && p.getWorld().getPVP() && vulnerable(p);
            if (isAlly(e)) return false;
            if (e instanceof Tameable t && t.isTamed()) return false;
            if (e instanceof Enemy) return true;
            if (isCustomMob(e)) return true;
            // 화가 난 중립 몹(늑대, 좀비 피글린 등)
            return e instanceof Mob m && m.getTarget() instanceof Player;
        } else {
            if (e instanceof Player p) return vulnerable(p);
            return isAlly(e);
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
        if (playerSide(caster)) return e instanceof Player || isAlly(e);
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
