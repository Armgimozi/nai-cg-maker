package kr.labyrinth.pvp;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.core.Text;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.AreaEffectCloudApplyEvent;
import org.bukkit.event.entity.EntityCombustByEntityEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityTargetLivingEntityEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.entity.PotionSplashEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.WorldLoadEvent;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.potion.PotionType;

/**
 * 근접·화살 말고 바닐라가 처리하는 PvP 경로에도 같은 파티 규칙을 건다 (규칙 판정은 전부 {@code services.targets().isEnemy}).
 * <ul>
 *   <li>그 밖의 바닐라 PvP 피해(폭발·물약·눈덩이·늑대 등 — 같은 파티면 CombatListener 가 이미 취소): 'HP 20 기준' 환산 뒤
 *       × 완충(HP ÷ (HP + B)) × (1 − 강인함) — 미궁 공격력이 아니라 레벨 곡선·직업 보정은 안 곱함 · 한 방 상한(관리자가 켰을 때)</li>
 *   <li>투척 물약: 해로운 효과가 있으면 던진 사람의 파티원은 안 맞음 · 잔류 구름: 해로우면 파티원 제외</li>
 *   <li>발화(화염 · 불붙은 화살 · 번개): 파티원이면 취소 · 길들인 늑대 등: 주인의 파티원을 노리지 않음 · 낚싯대: 파티원은 못 끌어옴</li>
 *   <li>죽음 메시지: 미궁 피해로 쓰러졌으면 "누구의 무엇에 · 마지막 피해" (미궁 안은 당사자 둘에게만)</li>
 *   <li>새로 열린 월드도 PvP 게임 규칙을 config 대로</li>
 * </ul>
 */
final class PvpListener implements Listener {

    private final Services services;
    private final PvpModule module;

    PvpListener(Services services, PvpModule module) {
        this.services = services;
        this.module = module;
    }

    private boolean enemies(Player a, Player b) { return services.targets().isEnemy(a, b); }

    /** 바닐라 경로 PvP 피해 (CombatListener 의 비율 환산 다음). 근접·화살은 DamageService 로 가서 여기 오지 않는다. */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onVanillaPvp(EntityDamageByEntityEvent e) {
        if (services.damage().isApplyingVanilla() || !(e.getEntity() instanceof Player victim)) return;
        Player culprit = PvpSources.playerBehind(e.getDamager(), e.getDamageSource());
        if (culprit == null || culprit.equals(victim)) return;
        if (!enemies(culprit, victim)) { // 안전망 — 다른 리스너가 취소를 풀었을 때
            e.setCancelled(true);
            return;
        }
        var mh = victim.getAttribute(Attribute.MAX_HEALTH);
        double vanillaMax = mh == null ? 20.0 : mh.getValue();
        double d = Math.max(0, e.getDamage()) * module.vanillaFactor(culprit, victim);
        PvpConfig c = module.config();
        if (c.maxHitRatio() < 1.0 && vanillaMax > 0) d = Math.min(d, vanillaMax * c.maxHitRatio());
        e.setDamage(d);
        module.noticeHit(culprit, victim);
    }

    // ── 물약 ──────────────────────────────────────────────────────────────

    static boolean harmful(Collection<PotionEffect> effects) {
        for (PotionEffect pe : effects) {
            if (pe.getType().getEffectCategory() == PotionEffectType.Category.HARMFUL) return true;
        }
        return false;
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSplash(PotionSplashEvent e) {
        Player thrower = PvpSources.playerOf(e.getPotion());
        if (thrower == null || !harmful(e.getPotion().getEffects())) return;
        for (LivingEntity le : e.getAffectedEntities()) {
            if (le instanceof Player v && !v.equals(thrower) && !enemies(thrower, v)) e.setIntensity(v, 0);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onCloud(AreaEffectCloudApplyEvent e) {
        AreaEffectCloud cloud = e.getEntity();
        Player owner = PvpSources.playerOf(cloud);
        if (owner == null) return;
        List<PotionEffect> effects = new ArrayList<>(cloud.getCustomEffects());
        PotionType base = cloud.getBasePotionType();
        if (base != null) effects.addAll(base.getPotionEffects());
        if (!harmful(effects)) return;
        e.getAffectedEntities().removeIf(le -> le instanceof Player v && !v.equals(owner) && !enemies(owner, v));
    }

    // ── 불 · 동물 · 낚싯대 ────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onCombust(EntityCombustByEntityEvent e) {
        if (!(e.getEntity() instanceof Player v)) return;
        Player culprit = PvpSources.playerOf(e.getCombuster());
        if (culprit != null && !culprit.equals(v) && !enemies(culprit, v)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPetTarget(EntityTargetLivingEntityEvent e) {
        if (!(e.getTarget() instanceof Player v)) return;
        Player owner = PvpSources.ownerOf(e.getEntity());
        if (owner != null && !owner.equals(v) && !enemies(owner, v)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onFish(PlayerFishEvent e) {
        if (e.getState() != PlayerFishEvent.State.CAUGHT_ENTITY || !(e.getCaught() instanceof Player v)) return;
        if (v.equals(e.getPlayer()) || enemies(e.getPlayer(), v)) return;
        e.setCancelled(true);
        e.getHook().remove();
    }

    // ── 죽음 메시지 ───────────────────────────────────────────────────────

    /** 다른 플레이어의 미궁 피해(DamageService)가 막타였을 때 (폭발 등 바닐라 경로·낙사는 바닐라 메시지). 미궁 안은 DungeonManager 가 취소하므로 MONITOR. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) {
        Player victim = e.getPlayer();
        PvpModule.Hit hit = module.killingBlow(victim);
        if (hit == null) return;
        Player killer = victim.getKiller();
        if (killer != null && !killer.getUniqueId().equals(hit.attacker())) return;
        String amount = Text.num(Math.round(hit.amount()));
        String line = "<dark_red>☠</dark_red> <white>" + Text.escape(victim.getName()) + "</white><gray> 님이 </gray><white>"
                + Text.escape(hit.attackerName()) + "</white><gray> 님의 </gray><#ffd36b>" + Text.escape(hit.label())
                + "</#ffd36b><gray>에 쓰러졌습니다</gray> <dark_gray>(마지막 피해 <red>" + amount + "</red>)";
        module.forget(victim.getUniqueId());
        if (e.isCancelled() || services.dungeon().isLabyrinthWorld(victim.getWorld())) {
            // 미궁 안: 사망이 '쓰러짐(관전)'으로 바뀌고 방송도 없다 → 당사자 둘에게만
            victim.sendMessage(Text.mm(line));
            if (killer != null && killer.isOnline()) killer.sendMessage(Text.mm(line));
            return;
        }
        e.deathMessage(Text.mm(line));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) { module.forget(e.getPlayer().getUniqueId()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorldLoad(WorldLoadEvent e) { module.applyWorldRule(e.getWorld(), true); }
}
