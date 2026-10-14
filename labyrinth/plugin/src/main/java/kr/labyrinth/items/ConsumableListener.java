package kr.labyrinth.items;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageInterceptor;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.weaponskills.LabWeaponSkillService;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Menu;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityResurrectEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemConsumeEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;

/**
 * 소모품 (GDD §11.9): heal · mana · restore · cleanse · buff = 바닐라 '마시기'(CONSUMABLE) 완료 시 효과,
 * return = 시전(전투 중 cast_time, 평소 cast_time_safe, 피해 시 끊김) 후 입구 귀환, stat_reset = 확인 창 후 스탯 초기화,
 * revive = 인벤토리에 있으면 치명상 순간 자동 소모 → HP × amount 로 일어나 invulnerable 초 무적.
 * cooldown_group 끼리 재사용 대기 공유(서버 기록 + 클라이언트 USE_COOLDOWN 표시).
 */
final class ConsumableListener implements Listener, DamageInterceptor {

    private final Services services;
    private final LabWeaponSkillService skills;
    /** uuid → (그룹 → 끝 ms). */
    private final Map<UUID, Map<String, Long>> cooldowns = new ConcurrentHashMap<>();
    private final Map<UUID, Long> lastHurt = new ConcurrentHashMap<>();
    private final Map<UUID, BukkitTask> casting = new ConcurrentHashMap<>();

    ConsumableListener(Services services, LabWeaponSkillService skills) {
        this.services = services;
        this.skills = skills;
    }

    void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.damage().addInterceptor(this);
    }

    void stop() {
        HandlerList.unregisterAll(this);
        services.damage().removeInterceptor(this);
        casting.values().forEach(BukkitTask::cancel);
        casting.clear();
    }

    private static String group(ItemDef def) { return def.use().str("cooldown_group", def.id()); }

    private double remaining(Player p, String group) {
        Map<String, Long> m = cooldowns.get(p.getUniqueId());
        if (m == null) return 0;
        Long end = m.get(group);
        return end == null ? 0 : Math.max(0, (end - System.currentTimeMillis()) / 1000.0);
    }

    private void startCooldown(Player p, ItemDef def) {
        double cd = def.use().dbl("cooldown", 0);
        if (cd <= 0) return;
        String g = group(def);
        cooldowns.computeIfAbsent(p.getUniqueId(), u -> new ConcurrentHashMap<>()).put(g, System.currentTimeMillis() + Math.round(cd * 1000));
        p.setCooldown(GearItemService.cooldownGroupKey(g), (int) Math.round(cd * 20));
    }

    private ItemDef consumable(ItemStack s) {
        return services.items().defOf(s).filter(d -> d.type() == ItemType.CONSUMABLE && d.use() != null && !d.use().isEmpty())
                .orElse(null);
    }

    private boolean levelOk(Player p, ItemDef def) {
        if (services.data().get(p).level() >= def.levelReq()) return true;
        Text.error(p, def.name() + " <gray>— 레벨 " + def.levelReq() + " 이상 사용할 수 있습니다.");
        return false;
    }

    // ── 마시기 (heal/mana/restore/cleanse/buff) ───────────────────────────

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onConsume(PlayerItemConsumeEvent e) {
        ItemDef def = consumable(e.getItem());
        if (def == null) return;
        Player p = e.getPlayer();
        String action = def.use().str("action", "");
        if (!GearItemService.DRINK_ACTIONS.contains(action)) {
            e.setCancelled(true);
            return;
        }
        if (!levelOk(p, def)) {
            e.setCancelled(true);
            return;
        }
        double rem = remaining(p, group(def));
        if (rem > 0) {
            e.setCancelled(true);
            services.hud().actionBar(p, Text.mm("<gray>" + def.name() + " <dark_gray>— <#ff9a6b>" + String.format("%.1f", rem) + "초</#ff9a6b> 후 사용 가능"), 30);
            return;
        }
        apply(p, def);
        startCooldown(p, def);
    }

    private void apply(Player p, ItemDef def) {
        Params u = def.use();
        double amount = u.dbl("amount", 0);
        switch (u.str("action", "")) {
            case "heal" -> services.damage().heal(p, services.stats().maxHp(p) * amount, true);
            case "mana" -> services.classes().restoreMana(p, services.classes().maxMana(p) * amount);
            case "restore" -> {
                services.damage().heal(p, services.stats().maxHp(p) * amount, true);
                services.classes().restoreMana(p, services.classes().maxMana(p) * amount);
            }
            case "cleanse" -> {
                services.effects().cleanse(p);
                p.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, p.getLocation().add(0, 1, 0), 12, 0.4, 0.6, 0.4);
            }
            case "buff" -> {
                Map<String, Double> buff = new LinkedHashMap<>();
                Params b = u.sub("buff");
                for (String k : b.keys()) buff.put(k, b.dbl(k, 0));
                services.effects().applyBuff(p, buff, u.dbl("duration", 60), "consumable:" + group(def));
            }
            default -> { }
        }
        services.hud().refresh(p);
        services.hud().actionBar(p, Text.mm("<#9be89b>" + def.name() + " <gray>— " + ItemTooltip.useText(u)), 40);
    }

    // ── 우클릭 (return / stat_reset / revive) ─────────────────────────────

    @EventHandler(priority = EventPriority.HIGH)
    public void onUse(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        ItemDef def = consumable(e.getItem());
        if (def == null) return;
        String action = def.use().str("action", "");
        if (GearItemService.DRINK_ACTIONS.contains(action)) return; // 바닐라 마시기
        e.setUseItemInHand(org.bukkit.event.Event.Result.DENY);
        e.setUseInteractedBlock(org.bukkit.event.Event.Result.DENY);
        Player p = e.getPlayer();
        if (!levelOk(p, def)) return;
        double rem = remaining(p, group(def));
        if (rem > 0) {
            Text.error(p, def.name() + " <gray>— " + String.format("%.1f", rem) + "초 후 사용할 수 있습니다.");
            return;
        }
        switch (action) {
            case "return" -> startReturn(p, def);
            case "stat_reset" -> {
                if (def.use().bool("confirm", true)) new ConfirmMenu(def).open(p);
                else statReset(p, def);
            }
            case "revive" -> Text.send(p, "<gray>" + def.name() + " 은(는) 쓰러지는 순간 <white>자동으로</white> 사용됩니다.");
            default -> { }
        }
    }

    private void startReturn(Player p, ItemDef def) {
        if (casting.containsKey(p.getUniqueId())) return;
        if (!services.dungeon().isInLabyrinth(p)) {
            Text.error(p, "귀환 주문서는 미궁 안에서만 쓸 수 있습니다.");
            return;
        }
        Params u = def.use();
        boolean combat = System.currentTimeMillis() - lastHurt.getOrDefault(p.getUniqueId(), 0L) < 10_000;
        double cast = combat ? u.dbl("cast_time", 5) : u.dbl("cast_time_safe", 1);
        int total = Math.max(1, (int) Math.round(cast * 20));
        boolean cancelOnDamage = u.bool("cancel_on_damage", true);
        long startHurt = lastHurt.getOrDefault(p.getUniqueId(), 0L);
        int[] t = {0};
        p.playSound(p.getLocation(), Sound.BLOCK_PORTAL_TRIGGER, 0.3f, 1.8f);
        BukkitTask task = Bukkit.getScheduler().runTaskTimer(services.plugin(), () -> {
            t[0] += 2;
            if (!p.isOnline() || p.isDead()) {
                cancelCast(p, null);
                return;
            }
            if (cancelOnDamage && lastHurt.getOrDefault(p.getUniqueId(), 0L) > startHurt) {
                cancelCast(p, "피해를 받아 귀환이 끊겼습니다.");
                return;
            }
            double prog = Math.min(1.0, (double) t[0] / total);
            int bars = (int) Math.round(prog * 20);
            services.hud().actionBar(p, Text.mm("<#c9a2ff>귀환 중 <white>" + "▮".repeat(bars) + "<dark_gray>" + "▯".repeat(20 - bars)
                    + " <gray>" + String.format("%.1f", Math.max(0, (total - t[0]) / 20.0)) + "초"), 6);
            p.getWorld().spawnParticle(Particle.PORTAL, p.getLocation().add(0, 1, 0), 10, 0.4, 0.8, 0.4, 0.3);
            if (t[0] >= total) {
                cancelCast(p, null);
                if (!consumeOne(p, def.id())) return;
                startCooldown(p, def);
                services.dungeon().leave(p);
                p.playSound(p.getLocation(), Sound.ENTITY_ENDERMAN_TELEPORT, 0.8f, 1.2f);
            }
        }, 2L, 2L);
        casting.put(p.getUniqueId(), task);
    }

    private void cancelCast(Player p, String msg) {
        BukkitTask task = casting.remove(p.getUniqueId());
        if (task != null) task.cancel();
        if (msg != null) {
            services.hud().actionBar(p, Text.mm("<#ff6b6b>" + msg), 30);
            p.playSound(p.getLocation(), Sound.BLOCK_FIRE_EXTINGUISH, 0.4f, 1.6f);
        }
    }

    private void statReset(Player p, ItemDef def) {
        PlayerData d = services.data().get(p);
        int total = 0;
        for (int v : d.allocated().values()) total += v;
        if (total <= 0) {
            Text.error(p, "되돌릴 스탯 포인트가 없습니다.");
            return;
        }
        if (!consumeOne(p, def.id())) return;
        int back = d.resetAllocation();
        startCooldown(p, def);
        services.stats().recalc(p);
        services.hud().refresh(p);
        p.playSound(p.getLocation(), Sound.BLOCK_ENCHANTMENT_TABLE_USE, 0.8f, 0.8f);
        p.getWorld().spawnParticle(Particle.ENCHANT, p.getLocation().add(0, 1.2, 0), 60, 0.5, 0.8, 0.5, 0.5);
        Text.send(p, "<#c9a2ff>망각의 주문서</#c9a2ff><gray>가 타올랐습니다. 스탯 포인트 <white>" + back + "</white>점을 돌려받았습니다. <dark_gray>(/스탯)");
    }

    /** 확인 창 (망각의 주문서). */
    private final class ConfirmMenu extends Menu {
        private final ItemDef def;

        ConfirmMenu(ItemDef def) {
            super(3, Text.mm("<#3a2a5a>정말 스탯을 초기화할까요?"));
            this.def = def;
        }

        @Override
        protected void build(Player viewer) {
            PlayerData d = services.data().get(viewer);
            int total = 0;
            for (int v : d.allocated().values()) total += v;
            set(11, Button.icon(Material.LIME_CONCRETE, "<#9be89b><b>초기화</b>", List.of("<gray>투자한 포인트 <white>" + total
                    + "</white>점을 돌려받습니다.", "<gray>" + def.name() + " 1개가 소모됩니다.")), ctx -> {
                viewer.closeInventory();
                statReset(viewer, def);
            });
            deco(13, Button.icon(Material.PAPER, def.id(), "<" + def.rarity().color() + ">" + def.name(),
                    List.of("<gray>" + ItemTooltip.useText(def.use()))));
            set(15, Button.icon(Material.RED_CONCRETE, "<#ff6b6b><b>취소</b>", List.of()), ctx -> viewer.closeInventory());
        }
    }

    /** 인벤토리에서 id 1개 소모. */
    private boolean consumeOne(Player p, String itemId) {
        ItemStack[] contents = p.getInventory().getContents();
        for (int i = 0; i < contents.length; i++) {
            ItemStack s = contents[i];
            if (s == null || s.isEmpty()) continue;
            if (!services.items().defOf(s).map(d -> d.id().equals(itemId)).orElse(false)) continue;
            s.setAmount(s.getAmount() - 1);
            p.getInventory().setItem(i, s.getAmount() <= 0 ? null : s);
            return true;
        }
        return false;
    }

    // ── 자동 부활 ─────────────────────────────────────────────────────────

    /** 인벤토리의 자동 부활 소모품 (쿨다운 끝난 것). */
    private ItemDef reviveItem(Player p) {
        for (ItemStack s : p.getInventory().getContents()) {
            ItemDef def = consumable(s);
            if (def == null || !"revive".equals(def.use().str("action", "")) || !def.use().bool("auto", true)) continue;
            if (services.data().get(p).level() < def.levelReq()) continue;
            if (remaining(p, group(def)) > 0) continue;
            return def;
        }
        return null;
    }

    private void revive(Player p, ItemDef def) {
        Params u = def.use();
        consumeOne(p, def.id());
        startCooldown(p, def);
        double hp = services.stats().maxHp(p) * u.dbl("amount", 0.3);
        int inv = (int) Math.round(u.dbl("invulnerable", 2.0) * 20);
        skills.invulnerable(p, inv);
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (!p.isOnline() || p.isDead()) return;
            services.stats().setHp(p, hp);
            for (PotionEffectType t : new PotionEffectType[] {PotionEffectType.REGENERATION, PotionEffectType.ABSORPTION,
                    PotionEffectType.FIRE_RESISTANCE}) p.removePotionEffect(t);
            services.hud().refresh(p);
        });
        Location at = p.getLocation().add(0, 1, 0);
        p.getWorld().spawnParticle(Particle.FLAME, at, 60, 0.4, 0.8, 0.4, 0.08);
        p.getWorld().spawnParticle(Particle.END_ROD, at, 30, 0.3, 0.8, 0.3, 0.1);
        p.getWorld().playSound(at, Sound.ENTITY_BLAZE_SHOOT, 1f, 0.6f);
        p.getWorld().playSound(at, Sound.BLOCK_BEACON_ACTIVATE, 1f, 1.5f);
        p.getServer().sendMessage(Text.mm(Text.PREFIX + "<#ffb627>" + Text.escape(p.getName()) + "</#ffb627><gray> 님이 "
                + def.name() + "<gray>의 불꽃으로 되살아났습니다!"));
    }

    /** DamageService 경로의 치명상: 부활 소모품이 있으면 피해를 0 으로 바꾸고 부활. */
    @Override
    public double intercept(DamageContext ctx, double damage) {
        if (!(ctx.target() instanceof Player p) || damage <= 0) return damage;
        lastHurt.put(p.getUniqueId(), System.currentTimeMillis()); // 전투 판정·귀환 끊기 (커스텀 피해는 바닐라 이벤트가 없음)
        if (damage + 1e-6 < services.stats().currentHp(p)) return damage;
        ItemDef def = reviveItem(p);
        if (def == null) return damage;
        revive(p, def);
        return 0;
    }

    /** 바닐라 경로의 치명상(낙하·용암 등): 토템 판정 이벤트를 살려 부활. */
    @EventHandler(priority = EventPriority.HIGH)
    public void onResurrect(EntityResurrectEvent e) {
        if (!(e.getEntity() instanceof Player p) || !e.isCancelled()) return;
        ItemDef def = reviveItem(p);
        if (def == null) return;
        e.setCancelled(false);
        revive(p, def);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHurt(EntityDamageEvent e) {
        if (e.getEntity() instanceof Player p) lastHurt.put(p.getUniqueId(), System.currentTimeMillis());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        cancelCast(e.getPlayer(), null);
        lastHurt.remove(e.getPlayer().getUniqueId());
    }
}
