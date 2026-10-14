package kr.labyrinth.pvp;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import kr.labyrinth.Services;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Monster;
import org.bukkit.entity.Player;

/**
 * 기본 규칙 (PvP 매치 없음): 플레이어에게 적 = 커스텀 몹·보스 (미궁 밖에선 바닐라 적대 몹도), 플레이어는 절대 적 아님.
 * 몹에게 적 = 플레이어. 아군 = 같은 파티(솔로면 자기 자신). pvp 담당이 매치 규칙을 얹어 대체한다.
 */
public class DefaultTargetFilter implements TargetFilter {

    protected final Services services;

    public DefaultTargetFilter(Services services) { this.services = services; }

    protected boolean isCustom(Entity e) {
        return services.mobs().byEntity(e).isPresent() || services.bosses().byEntity(e).isPresent();
    }

    @Override
    public boolean isEnemy(LivingEntity source, Entity target) {
        if (source == null || target == null || source.equals(target) || target.isDead()) return false;
        if (!(target instanceof LivingEntity)) return false;
        boolean sourceIsMob = isCustom(source);
        if (source instanceof Player) {
            if (target instanceof Player) return false;
            if (isCustom(target)) return true;
            return target instanceof Monster && !services.dungeon().isLabyrinthWorld(target.getWorld());
        }
        if (sourceIsMob) return target instanceof Player p && p.getGameMode().isInvulnerable() == false;
        return false;
    }

    @Override
    public boolean isAlly(LivingEntity source, Entity target) {
        if (source == null || target == null) return false;
        if (source.equals(target)) return true;
        if (source instanceof Player a && target instanceof Player b) return services.party().sameParty(a, b);
        return isCustom(source) && isCustom(target);
    }

    @Override
    public List<LivingEntity> enemiesIn(LivingEntity source, Location center, double radius) {
        List<LivingEntity> out = new ArrayList<>();
        for (Entity e : center.getWorld().getNearbyEntities(center, radius, radius, radius)) {
            if (e instanceof LivingEntity le && e.getLocation().distanceSquared(center) <= radius * radius
                    && isEnemy(source, le)) {
                out.add(le);
            }
        }
        out.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(center)));
        return out;
    }

    @Override
    public List<Player> alliesIn(Player source, Location center, double radius) {
        List<Player> out = new ArrayList<>();
        for (Player p : center.getWorld().getPlayers()) {
            if (p.getLocation().distanceSquared(center) <= radius * radius && isAlly(source, p) && !p.isDead()) out.add(p);
        }
        return out;
    }
}
