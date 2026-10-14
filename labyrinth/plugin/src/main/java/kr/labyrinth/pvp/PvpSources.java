package kr.labyrinth.pvp;

import java.util.UUID;
import org.bukkit.Bukkit;
import org.bukkit.damage.DamageSource;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LightningStrike;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.Tameable;
import org.bukkit.projectiles.ProjectileSource;

/**
 * 피해·효과의 "책임 플레이어" 찾기 — PvP 규칙을 근접뿐 아니라 쏜 것·붙인 것·길들인 동물에도 똑같이 적용하려고.
 * 근접 = 때린 사람, 화살·삼지창·눈덩이·물약 = 쏜/던진 사람, TNT·엔드 수정 폭발 = 불붙인/깨뜨린 사람(바닐라 피해 원인 추적),
 * 잔류 물약 구름 = 던진 사람, 집전 번개 = 삼지창 주인, 길들인 늑대 등 = 주인(접속 중일 때). 모르면 null (환경 피해).
 */
public final class PvpSources {

    private PvpSources() {}

    /** damager(직접 때린 엔티티)와 바닐라 피해 원인으로 책임 플레이어를 찾는다. */
    public static Player playerBehind(Entity damager, DamageSource source) {
        if (damager instanceof Player p) return p;
        Entity causing = null;
        try {
            causing = source == null ? null : source.getCausingEntity();
        } catch (Throwable ignored) {
            // 피해 원인 API 가 없는 피해 — 아래 엔티티별 규칙으로
        }
        if (causing instanceof Player p) return p;
        Player p = playerOf(damager);
        if (p != null) return p;
        return causing != null && causing != damager ? playerOf(causing) : null;
    }

    /** 엔티티 하나의 책임 플레이어 (플레이어 자신 · 투사체 주인 · TNT 점화자 · 구름 주인 · 번개 주인 · 동물 주인). */
    public static Player playerOf(Entity e) {
        if (e == null) return null;
        if (e instanceof Player p) return p;
        if (e instanceof Projectile proj) return shooter(proj.getShooter());
        if (e instanceof TNTPrimed t) return t.getSource() == null || t.getSource() == e ? null : playerOf(t.getSource());
        if (e instanceof AreaEffectCloud c) return shooter(c.getSource());
        if (e instanceof LightningStrike l) {
            Player cp = l.getCausingPlayer();
            return cp != null ? cp : l.getCausingEntity() instanceof Player p ? p : null;
        }
        return ownerOf(e);
    }

    /** 길들인 동물의 주인 (접속 중일 때만). */
    public static Player ownerOf(Entity e) {
        if (!(e instanceof Tameable t) || !t.isTamed()) return null;
        UUID u = t.getOwnerUniqueId();
        return u == null ? null : Bukkit.getPlayer(u);
    }

    private static Player shooter(ProjectileSource s) {
        if (s instanceof Player p) return p;
        return s instanceof Entity en ? ownerOf(en) : null;
    }
}
