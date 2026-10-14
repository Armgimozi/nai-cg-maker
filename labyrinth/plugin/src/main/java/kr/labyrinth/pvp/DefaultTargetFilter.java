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
 * {@link PvpRules} 를 엔티티에 적용하는 구현. 기본(이 클래스 그대로) = PvP 꺼짐: 플레이어끼리는 절대 적이 아니다.
 * pvp 모듈이 {@link #pvpConfig()}·{@link #inSafeZone} 을 config 대로 바꾼 하위 클래스를 등록한다.
 */
public class DefaultTargetFilter implements TargetFilter {

    protected final Services services;

    public DefaultTargetFilter(Services services) { this.services = services; }

    protected boolean isCustom(Entity e) {
        return services.mobs().byEntity(e).isPresent() || services.bosses().byEntity(e).isPresent();
    }

    /** 엔티티 → 판정 재료. */
    protected PvpRules.Side side(Entity e) {
        if (e instanceof Player p) {
            String party = services.party().partyOf(p).map(kr.labyrinth.party.Party::id).orElse(null);
            boolean invulnerable = p.isDead() || p.getGameMode().isInvulnerable();
            return new PvpRules.Side(PvpRules.Kind.PLAYER, p.getUniqueId(), party, invulnerable, inSafeZone(p.getLocation()));
        }
        PvpRules.Kind kind;
        if (isCustom(e)) kind = PvpRules.Kind.MOB;
        else if (services.npcs().npcIdOf(e).isPresent()) kind = PvpRules.Kind.NPC;
        else if (e instanceof Monster && !services.dungeon().isLabyrinthWorld(e.getWorld())) kind = PvpRules.Kind.HOSTILE;
        else kind = PvpRules.Kind.OTHER;
        return new PvpRules.Side(kind, e.getUniqueId(), null, e.isDead(), false);
    }

    @Override
    public boolean isEnemy(LivingEntity source, Entity target) {
        if (source == null || target == null || source.equals(target) || target.isDead()) return false;
        if (!(target instanceof LivingEntity)) return false;
        return PvpRules.isEnemy(pvpConfig(), side(source), side(target));
    }

    @Override
    public boolean isAlly(LivingEntity source, Entity target) {
        if (source == null || target == null) return false;
        if (source.equals(target)) return true;
        return PvpRules.isAlly(side(source), side(target));
    }

    @Override
    public List<LivingEntity> enemiesIn(LivingEntity source, Location center, double radius) {
        List<LivingEntity> out = new ArrayList<>();
        if (source == null) return out;
        PvpConfig cfg = pvpConfig();
        PvpRules.Side src = side(source);
        for (Entity e : center.getWorld().getNearbyEntities(center, radius, radius, radius)) {
            if (e instanceof LivingEntity le && !le.equals(source) && !le.isDead()
                    && e.getLocation().distanceSquared(center) <= radius * radius
                    && PvpRules.isEnemy(cfg, src, side(le))) {
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
