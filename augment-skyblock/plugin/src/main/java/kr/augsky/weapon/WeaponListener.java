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
        Bukkit.getScheduler().runTaskTimer(plugin, this::heldAura, 25, 3);
    }

    // 손에 든 무기 주변에 도는 속성 입자 (아우라가 있는 보스/프리즘 무기만)
    private static final Map<String, String[]> HELD = Map.ofEntries(
            Map.entry("flame", new String[]{"SMALL_FLAME", "FLAME"}), Map.entry("sun", new String[]{"WAX_ON", "SMALL_FLAME"}),
            Map.entry("frost", new String[]{"SNOWFLAKE", "END_ROD"}), Map.entry("crystal", new String[]{"DUST:#d0a0ff:0.7", "END_ROD"}),
            Map.entry("star", new String[]{"END_ROD", "DUST:#a8b8ff:0.7"}), Map.entry("storm", new String[]{"ELECTRIC_SPARK", "DUST:#c8b8ff:0.7"}),
            Map.entry("venom", new String[]{"DUST:#9ad850:0.8", "DUST:#5aa02a:0.6"}), Map.entry("ocean", new String[]{"BUBBLE_POP", "DUST:#6ad8e8:0.7"}),
            Map.entry("earth", new String[]{"DUST:#c8a060:0.8", "FALLING_DUST:sand"}), Map.entry("wind", new String[]{"DUST:#d8fff0:0.6", "CLOUD"}),
            Map.entry("holy", new String[]{"WAX_ON", "END_ROD"}), Map.entry("nature", new String[]{"HAPPY_VILLAGER", "DUST:#8ad870:0.7"}),
            Map.entry("blood", new String[]{"DUST:#d8304a:0.8", "DAMAGE_INDICATOR"}), Map.entry("abyss", new String[]{"REVERSE_PORTAL", "DUST:#8a3ad8:0.8"}),
            Map.entry("ender", new String[]{"PORTAL", "DUST:#3ac8a8:0.7"}), Map.entry("shadow", new String[]{"SMOKE", "DUST:#5a5a78:0.8"}),
            Map.entry("doom", new String[]{"SOUL", "DUST:#ff3a6a:0.8"}), Map.entry("prism", new String[]{"PRISM", "END_ROD"}));
    private int auraTick;

    private void heldAura() {
        auraTick++;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.getGameMode() == org.bukkit.GameMode.SPECTATOR || p.isInvisible()) continue;
            WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
            if (w == null) continue;
            String pool = w.pool();
            if (!pool.equals("boss") && !pool.equals("prism")) continue;
            String[] fx = HELD.get(w.element());
            if (fx == null) continue;
            // 오른손 앞쪽, 무기 날 부근
            org.bukkit.Location eye = p.getEyeLocation();
            org.bukkit.util.Vector dir = eye.getDirection().setY(0);
            if (dir.lengthSquared() < 1e-4) dir = new org.bukkit.util.Vector(0, 0, 1);
            dir.normalize();
            org.bukkit.util.Vector right = new org.bukkit.util.Vector(-dir.getZ(), 0, dir.getX());
            double up = p.isSneaking() ? 0.75 : 0.95;
            org.bukkit.Location at = p.getLocation().add(right.multiply(0.42)).add(dir.multiply(0.35)).add(0, up, 0);
            boolean strong = pool.equals("boss") || pool.equals("prism");
            String spec = fx[auraTick % 3 == 0 ? 1 : 0];
            if (spec.equals("PRISM")) {
                java.awt.Color c = java.awt.Color.getHSBColor((auraTick * 0.03f) % 1f, 0.55f, 1f);
                p.getWorld().spawnParticle(org.bukkit.Particle.DUST, at, strong ? 2 : 1, 0.12, 0.3, 0.12, 0,
                        new org.bukkit.Particle.DustOptions(org.bukkit.Color.fromRGB(c.getRed(), c.getGreen(), c.getBlue()), 0.8f));
                continue;
            }
            kr.augsky.util.Fx.Spec sp = kr.augsky.util.Fx.parse(spec);
            if (sp != null) sp.spawn(at, strong ? 2 : 1, 0.12, 0.3, 0.12, 0.005);
        }
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
        if (w.isBow()) return; // 활은 우클릭으로 당겨 쏜다 (스킬은 F키)
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
        if (w == null) return;
        if (w.isBow()) {
            // 활: F키 = 첫 스킬, 웅크리고 F키 = 두 번째 스킬
            int slot = p.isSneaking() && w.skill2() != null ? 2 : 1;
            if ((slot == 1 ? w.skill() : w.skill2()) == null) return;
            e.setCancelled(true);
            cast(p, main, w, slot);
            return;
        }
        if (w.skill2() == null) return;
        e.setCancelled(true);
        cast(p, main, w, 2);
    }

    /** 활: 쏜 화살에 무기 피해를 싣고, 맞으면 패시브가 터지게 표시한다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onShoot(org.bukkit.event.entity.EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        WeaponDef w = plugin.weapons().of(e.getBow());
        if (w == null || !w.isBow()) return;
        if (!(e.getProjectile() instanceof org.bukkit.entity.AbstractArrow arrow)) return;
        // 바닐라 화살 피해 = 기본 피해 × 속도(끝까지 당기면 약 3)
        arrow.setDamage(w.damage() / 3.0);
        arrow.setPickupStatus(org.bukkit.entity.AbstractArrow.PickupStatus.CREATIVE_ONLY);
        arrow.getPersistentDataContainer().set(kr.augsky.Keys.WEAPON, org.bukkit.persistence.PersistentDataType.STRING, w.id());
        e.setConsumeItem(false);
        String[] fx = HELD.get(w.element());
        if (fx != null && (w.pool().equals("boss") || w.pool().equals("prism"))) {
            kr.augsky.util.Fx.Spec sp = kr.augsky.util.Fx.parse(fx[0].equals("PRISM") ? "END_ROD" : fx[0]);
            org.bukkit.entity.AbstractArrow a = arrow;
            new org.bukkit.scheduler.BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    if (++t > 60 || !a.isValid() || a.isInBlock() || a.isOnGround()) {
                        cancel();
                        return;
                    }
                    if (sp != null) sp.spawn(a.getLocation(), 1, 0.05, 0.0);
                }
            }.runTaskTimer(plugin, 1, 1);
        }
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
        // 활은 아이템 쿨타임을 걸면 당길 수 없게 되므로 걸지 않는다
        if (slot == 1 && !w.isBow()) p.setCooldown(item, Math.max(1, (int) Math.round(cd * 20)));
        double power = w.skillPower() * (1 + st.get("skill_power.amount"));
        SkillContext ctx = new SkillContext(plugin, p, null, power);
        s.cast(ctx);
        p.sendActionBar(Text.mm("<#ffcc55>✦ " + s.name()));
    }

    /** 근접 공격 패시브 (활은 화살이 맞았을 때). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHit(EntityDamageByEntityEvent e) {
        if (Combat.inSkill()) return;
        if (!(e.getEntity() instanceof LivingEntity victim)) return;
        Player p;
        WeaponDef w;
        if (e.getDamager() instanceof org.bukkit.entity.AbstractArrow arrow && arrow.getShooter() instanceof Player shooter) {
            p = shooter;
            w = plugin.weapons().get(arrow.getPersistentDataContainer().get(kr.augsky.Keys.WEAPON, org.bukkit.persistence.PersistentDataType.STRING));
        } else if (e.getDamager() instanceof Player pl && e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK) {
            p = pl;
            w = plugin.weapons().of(p.getInventory().getItemInMainHand());
            if (w != null && w.isBow()) return; // 활로 때리는 건 패시브 없음
        } else {
            return;
        }
        if (!Targets.isEnemy(p, victim)) return;
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
            sb.append(part(p, w, 1, w.isBow() ? "F" : "우클릭"));
            if (w.skill2() != null) sb.append("  <dark_gray>|  ").append(part(p, w, 2, w.isBow() ? "웅크리고 F" : "F"));
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
