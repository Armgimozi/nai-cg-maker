package kr.augsky.weapon;

import kr.augsky.AugSky;
import kr.augsky.augment.Stats;
import kr.augsky.skill.Combat;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.SkillContext;
import kr.augsky.skill.SkillDef;
import kr.augsky.skill.Targets;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.block.Block;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/** 무기 우클릭(스킬1), F키(스킬2), 근접 공격 패시브. */
public final class WeaponListener implements Listener {
    private final AugSky plugin;
    private final Map<UUID, Integer> lastCastTick = new HashMap<>();
    private final Map<UUID, Integer> suppressUntil = new HashMap<>();

    public WeaponListener(AugSky plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::hud, 20, 10);
    }

    /** 제단/소환대를 누를 때 같은 클릭으로 스킬이 나가지 않게 잠깐 막는다. */
    public void suppress(Player p, int ticks) {
        suppressUntil.put(p.getUniqueId(), Bukkit.getCurrentTick() + ticks);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Action a = e.getAction();
        if (a != Action.RIGHT_CLICK_AIR && a != Action.RIGHT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        ItemStack item = p.getInventory().getItemInMainHand();
        WeaponDef w = plugin.weapons().of(item);
        if (w == null || w.skill() == null) return;
        if (a == Action.RIGHT_CLICK_BLOCK) {
            Block b = e.getClickedBlock();
            if (b != null && b.getType().isInteractable() && !p.isSneaking()) return;
        }
        e.setUseItemInHand(org.bukkit.event.Event.Result.DENY);
        cast(p, item, w, 1);
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        ItemStack main = p.getInventory().getItemInMainHand();
        WeaponDef w = plugin.weapons().of(main);
        if (w == null || w.skill2() == null) return;
        e.setCancelled(true);
        cast(p, main, w, 2);
    }

    public void cast(Player p, ItemStack item, WeaponDef w, int slot) {
        int now = Bukkit.getCurrentTick();
        Integer sup = suppressUntil.get(p.getUniqueId());
        if (sup != null && now < sup) return;
        String skillId = slot == 1 ? w.skill() : w.skill2();
        SkillDef s = plugin.skills().get(skillId);
        if (s == null) return;
        Integer last = lastCastTick.get(p.getUniqueId());
        if (last != null && now - last < 3) return;
        lastCastTick.put(p.getUniqueId(), now);

        String key = w.id() + "#" + slot;
        long rem = plugin.cooldowns().remainingMs(p.getUniqueId(), key);
        if (rem > 0) {
            p.sendActionBar(Text.mm("<#ff7070>⏳ " + s.name() + " <gray>" + String.format("%.1f", rem / 1000.0) + "초"));
            return;
        }
        Stats st = plugin.augments().stats(p);
        double haste = Math.min(0.6, st.get("skill_haste.amount"));
        double cd = s.cooldown() * (1 - haste);
        plugin.cooldowns().set(p.getUniqueId(), key, cd);
        if (slot == 1) p.setCooldown(item, Math.max(1, (int) Math.round(cd * 20)));
        double power = w.skillPower() * (1 + st.get("skill_power.amount"));
        SkillContext ctx = new SkillContext(plugin, p, null, power);
        s.cast(ctx);
        p.sendActionBar(Text.mm("<#ffcc55>✦ " + s.name()));
    }

    /** 근접 공격 패시브. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHit(EntityDamageByEntityEvent e) {
        if (Combat.inSkill()) return;
        if (!(e.getDamager() instanceof Player p)) return;
        if (e.getCause() != EntityDamageEvent.DamageCause.ENTITY_ATTACK) return;
        if (!(e.getEntity() instanceof LivingEntity victim)) return;
        if (!Targets.isEnemy(p, victim)) return;
        WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        if (w == null || w.passive().isEmpty()) return;
        if (ThreadLocalRandom.current().nextDouble() >= w.passiveChance()) return;
        SkillContext ctx = new SkillContext(plugin, p, victim, w.skillPower());
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (victim.isValid() && !victim.isDead()) HitEffects.apply(w.passive(), ctx, victim, p.getLocation());
        });
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        lastCastTick.remove(e.getPlayer().getUniqueId());
        suppressUntil.remove(e.getPlayer().getUniqueId());
    }

    /** 무기를 든 동안 액션바에 스킬 상태를 띄운다. */
    private void hud() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
            if (w == null || w.skill() == null) continue;
            StringBuilder sb = new StringBuilder();
            sb.append(part(p, w, 1, "우클릭"));
            if (w.skill2() != null) sb.append("  <dark_gray>|  ").append(part(p, w, 2, "F"));
            p.sendActionBar(Text.mm(sb.toString()));
        }
    }

    private String part(Player p, WeaponDef w, int slot, String label) {
        SkillDef s = plugin.skills().get(slot == 1 ? w.skill() : w.skill2());
        if (s == null) return "";
        long rem = plugin.cooldowns().remainingMs(p.getUniqueId(), w.id() + "#" + slot);
        if (rem <= 0) return "<#ffcc55>[" + label + "] <white>" + s.name() + " <#7cff8c>✔";
        return "<gray>[" + label + "] " + s.name() + " <#ff7070>" + String.format("%.1f", rem / 1000.0) + "s";
    }
}
