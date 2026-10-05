package kr.augsky.augment;

import kr.augsky.AugSky;
import kr.augsky.skill.Combat;
import kr.augsky.skill.Targets;
import kr.augsky.util.Fx;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import kr.augsky.weapon.WeaponDef;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Tag;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.Ageable;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockDropItemEvent;
import org.bukkit.event.block.BlockFormEvent;
import org.bukkit.event.block.LeavesDecayEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerExpChangeEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerGameModeChangeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerToggleFlightEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/** 증강 효과를 실제 게임 이벤트에 연결한다. */
public final class AugmentListener implements Listener {
    private final AugSky plugin;
    private final AugmentService aug;
    private final Set<UUID> jumpGranted = new HashSet<>();
    private int tick;

    public AugmentListener(AugSky plugin) {
        this.plugin = plugin;
        this.aug = plugin.augments();
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 20, 4);
    }

    private static ThreadLocalRandom rnd() {
        return ThreadLocalRandom.current();
    }

    private static boolean playing(Player p) {
        GameMode g = p.getGameMode();
        return g == GameMode.SURVIVAL || g == GameMode.ADVENTURE;
    }

    // ------------------------------------------------------------------ 접속/부활

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            aug.refresh(p);
            plugin.starterKit(p);
            PlayerData d = aug.data(p);
            if (d.hasOffer()) {
                p.sendMessage(Text.mm("<#ffcc55>✦ <gray>고르지 않은 " + d.offerTier.label() + " <gray>증강 선택지가 있습니다. <white>/증강 선택"));
            }
        }, 5);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        jumpGranted.remove(id);
        aug.forget(id);
        aug.store().unload(id);
        plugin.cooldowns().clear(id);
    }

    @EventHandler
    public void onRespawn(PlayerRespawnEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (p.isOnline()) aug.refresh(p);
        }, 2);
    }

    @EventHandler
    public void onGameMode(PlayerGameModeChangeEvent e) {
        if (jumpGranted.remove(e.getPlayer().getUniqueId())) {
            Bukkit.getScheduler().runTask(plugin, () -> {
                Player p = e.getPlayer();
                if (playing(p)) {
                    p.setAllowFlight(false);
                    p.setFlying(false);
                }
            });
        }
    }

    // ------------------------------------------------------------------ 공격/방어

    private static Player attackerOf(Entity damager) {
        if (damager instanceof Player p) return p;
        if (damager instanceof Projectile pr && pr.getShooter() instanceof Player p) return p;
        return null;
    }

    private static LivingEntity livingSource(Entity damager) {
        if (damager instanceof Projectile pr && pr.getShooter() instanceof LivingEntity le) return le;
        if (damager instanceof LivingEntity le) return le;
        return null;
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDamageModify(EntityDamageByEntityEvent e) {
        // 받는 쪽: 회피, 피해 감소
        if (e.getEntity() instanceof Player victim && playing(victim)) {
            Stats vs = aug.stats(victim);
            double dodge = Math.min(0.5, vs.get("dodge.chance"));
            if (dodge > 0 && rnd().nextDouble() < dodge) {
                e.setCancelled(true);
                victim.getWorld().spawnParticle(Particle.LARGE_SMOKE, victim.getLocation().add(0, 1, 0), 15, 0.3, 0.5, 0.3, 0.02);
                victim.sendActionBar(Text.mm("<#9ad8ff>✧ 회피!"));
                Fx.sound(victim.getLocation(), "entity.illusioner.mirror_move", 0.8f, 1.4f);
                return;
            }
            double dr = Math.min(0.6, vs.get("damage_reduction.amount"));
            if (dr > 0) e.setDamage(e.getDamage() * (1 - dr));
        }
        // 때리는 쪽: 배율
        Player attacker = attackerOf(e.getDamager());
        if (attacker == null || Combat.inSkill()) return;
        if (!(e.getEntity() instanceof LivingEntity target) || !Targets.isEnemy(attacker, target)) return;
        Stats st = aug.stats(attacker);
        double mult = 1 + st.get("damage_bonus.amount");
        double bt = st.get("berserk.threshold");
        if (bt > 0 && attacker.getHealth() / Combat.maxHealth(attacker) <= bt) mult += st.get("berserk.amount");
        if (st.get("first_strike.amount") > 0 && target.getHealth() >= Combat.maxHealth(target) - 0.01) {
            mult += st.get("first_strike.amount");
        }
        if (Targets.isBoss(target)) mult += st.get("boss_damage.amount");
        double cc = Math.min(0.75, st.get("crit.chance"));
        if (cc > 0 && rnd().nextDouble() < cc) {
            mult *= Math.max(1.3, st.get("crit.multiplier", 1.5));
            target.getWorld().spawnParticle(Particle.ENCHANTED_HIT, target.getLocation().add(0, target.getHeight() / 2, 0), 20, 0.3, 0.3, 0.3, 0.2);
            Fx.sound(target.getLocation(), "entity.player.attack.crit", 1f, 0.8f);
        }
        if (mult != 1) e.setDamage(e.getDamage() * mult);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamageAfter(EntityDamageByEntityEvent e) {
        double fin = e.getFinalDamage();
        // 가시: 받은 피해 일부를 되돌린다
        if (e.getEntity() instanceof Player victim && !Combat.inSkill()) {
            double th = aug.stats(victim).get("thorns.amount");
            LivingEntity src = livingSource(e.getDamager());
            if (th > 0 && src != null && !(src instanceof Player) && fin > 0) {
                double amt = fin * th;
                Bukkit.getScheduler().runTask(plugin, () -> Combat.damage(victim, src, amt, true, null));
            }
        }
        Player attacker = attackerOf(e.getDamager());
        if (attacker == null) return;
        if (!(e.getEntity() instanceof LivingEntity target) || !Targets.isEnemy(attacker, target)) return;
        Stats st = aug.stats(attacker);
        double ls = Math.min(0.5, st.get("lifesteal.amount"));
        if (ls > 0 && fin > 0) Combat.heal(attacker, fin * ls);
        if (Combat.inSkill()) return;
        boolean melee = e.getDamager() instanceof Player;
        double base = e.getDamage();

        double ig = st.get("ignite.chance");
        if (ig > 0 && rnd().nextDouble() < ig) {
            target.setFireTicks(Math.max(target.getFireTicks(), (int) (st.get("ignite.seconds", 3) * 20)));
        }
        for (Stats.HitPotion hp : st.hitPotions) {
            if (rnd().nextDouble() < hp.chance()) target.addPotionEffect(new PotionEffect(hp.type(), hp.ticks(), hp.amplifier()));
        }
        double lc = st.get("lightning.chance");
        if (lc > 0 && rnd().nextDouble() < lc) {
            double dmg = st.get("lightning.damage", 5);
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (!target.isValid()) return;
                target.getWorld().strikeLightningEffect(target.getLocation());
                Combat.damage(attacker, target, dmg, true, null);
            });
        }
        double cl = st.get("chain_lightning.chance");
        if (cl > 0 && rnd().nextDouble() < cl) {
            int n = (int) Math.max(2, st.get("chain_lightning.targets", 3));
            double dmg = st.get("chain_lightning.damage", 4);
            Bukkit.getScheduler().runTask(plugin, () -> chain(attacker, target, n, dmg));
        }
        double ds = st.get("double_strike.chance");
        if (melee && ds > 0 && rnd().nextDouble() < ds) {
            double amt = base * Math.max(0.3, st.get("double_strike.ratio", 0.6));
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (!target.isValid() || target.isDead()) return;
                target.getWorld().spawnParticle(Particle.SWEEP_ATTACK, target.getLocation().add(0, 1, 0), 2, 0.2, 0.2, 0.2, 0);
                Fx.sound(target.getLocation(), "entity.player.attack.sweep", 1f, 1.4f);
                Combat.damage(attacker, target, amt, false, null);
            }, 5);
        }
        double ex = st.get("execute.threshold");
        if (ex > 0 && !Targets.isBoss(target)) {
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (!target.isValid() || target.isDead()) return;
                if (target.getHealth() / Combat.maxHealth(target) <= ex) {
                    target.getWorld().spawnParticle(Particle.DAMAGE_INDICATOR, target.getLocation().add(0, 1, 0), 12, 0.3, 0.3, 0.3, 0.1);
                    Fx.sound(target.getLocation(), "entity.player.attack.knockback", 1f, 0.6f);
                    Combat.damage(attacker, target, target.getHealth() + target.getAbsorptionAmount() + 50, true, null);
                }
            });
        }
    }

    private void chain(Player attacker, LivingEntity first, int n, double dmg) {
        Set<UUID> hit = new HashSet<>();
        LivingEntity cur = first;
        Location from = attacker.getEyeLocation();
        Fx.Spec spark = new Fx.Spec(Particle.ELECTRIC_SPARK, null);
        for (int i = 0; i < n && cur != null; i++) {
            hit.add(cur.getUniqueId());
            Location to = cur.getLocation().add(0, cur.getHeight() / 2, 0);
            Fx.line(spark, from, to, 0.3);
            Combat.damage(attacker, cur, dmg, true, null);
            from = to;
            LivingEntity next = null;
            double best = 7;
            for (LivingEntity c : Targets.enemiesNear(attacker, to, 7)) {
                if (hit.contains(c.getUniqueId())) continue;
                double dd = c.getLocation().distance(to);
                if (dd < best) {
                    best = dd;
                    next = c;
                }
            }
            cur = next;
        }
        Fx.sound(first.getLocation(), "entity.lightning_bolt.impact", 0.6f, 1.6f);
    }

    /** 불사 / 공허 수호. */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onPlayerDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p) || !playing(p)) return;
        Stats st = aug.stats(p);
        PlayerData d = aug.data(p);
        long now = System.currentTimeMillis();
        if (e.getCause() == EntityDamageEvent.DamageCause.VOID) {
            if (st.has("void_rescue") && now >= d.voidReadyAt) {
                e.setCancelled(true);
                rescue(p, d, st);
            }
            return;
        }
        if (!st.has("undying") || now < d.undyingReadyAt) return;
        if (e.getFinalDamage() < p.getHealth() + p.getAbsorptionAmount()) return;
        e.setCancelled(true);
        d.undyingReadyAt = now + (long) (st.get("undying.cooldown", 180) * 1000);
        double max = Combat.maxHealth(p);
        p.setHealth(Math.max(1, Math.min(max, max * st.get("undying.heal", 0.5))));
        p.addPotionEffect(new PotionEffect(PotionEffectType.REGENERATION, 100, 1));
        p.addPotionEffect(new PotionEffect(PotionEffectType.ABSORPTION, 160, 1));
        p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 60, 2));
        p.addPotionEffect(new PotionEffect(PotionEffectType.FIRE_RESISTANCE, 200, 0));
        p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), 80, 0.5, 1, 0.5, 0.4);
        Fx.sound(p.getLocation(), "item.totem.use", 1f, 1f);
        p.showTitle(Title.title(Text.mm("<gradient:#ff6b9d:#ffd36b>불사</gradient>"), Text.mm("<gray>죽음을 한 번 버텼습니다"),
                Title.Times.times(Duration.ofMillis(100), Duration.ofMillis(1200), Duration.ofMillis(400))));
    }

    private void rescue(Player p, PlayerData d, Stats st) {
        d.voidReadyAt = System.currentTimeMillis() + (long) (st.get("void_rescue.cooldown", 300) * 1000);
        Location to = p.getRespawnLocation();
        if (to == null) to = plugin.spawnLocation();
        p.setFallDistance(0);
        p.setVelocity(new Vector());
        p.teleport(to);
        p.addPotionEffect(new PotionEffect(PotionEffectType.SLOW_FALLING, 100, 0));
        p.getWorld().spawnParticle(Particle.REVERSE_PORTAL, p.getLocation().add(0, 1, 0), 60, 0.4, 1, 0.4, 0.05);
        Fx.sound(p.getLocation(), "entity.enderman.teleport", 1f, 0.8f);
        p.sendMessage(Text.mm("<#c86bff>✦ 공허 수호<gray>가 당신을 끌어올렸습니다. <dark_gray>(재사용 "
                + Text.num(st.get("void_rescue.cooldown", 300)) + "초)"));
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onDeath(PlayerDeathEvent e) {
        Player p = e.getPlayer();
        EntityDamageEvent last = p.getLastDamageCause();
        if (last != null && last.getCause() == EntityDamageEvent.DamageCause.VOID
                && plugin.getConfig().getBoolean("void.keep-inventory", true)) {
            e.setKeepInventory(true);
            e.getDrops().clear();
            e.setKeepLevel(true);
            e.setDroppedExp(0);
            p.sendMessage(Text.mm("<gray>공허에 떨어져 죽었습니다. 아이템과 경험치는 지켜졌습니다."));
        }
    }

    // ------------------------------------------------------------------ 처치

    @EventHandler(priority = EventPriority.HIGH)
    public void onKill(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        Player killer = dead.getKiller();
        if (killer == null || dead instanceof Player || Targets.isAlly(dead)) return;
        Stats st = aug.stats(killer);
        PlayerData d = aug.data(killer);
        boolean hostile = dead instanceof Enemy || Targets.isCustomMob(dead);

        double kh = st.get("kill_heal.amount");
        if (kh > 0) Combat.heal(killer, kh);
        if (st.has("kill_speed")) {
            int secs = (int) st.get("kill_speed.seconds", 4);
            killer.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, secs * 20, (int) st.get("kill_speed.amplifier", 1)));
        }
        double per = st.get("soul_harvest.per_kill");
        if (per > 0 && hostile) {
            double max = st.get("soul_harvest.max", 10);
            if (d.soul < max) {
                double before = d.soul;
                d.soul = Math.min(max, d.soul + per);
                aug.applyAttributes(killer, d);
                if ((int) before != (int) d.soul) {
                    killer.sendActionBar(Text.mm("<#c86bff>☠ 영혼 수확 <white>최대 체력 +" + Text.num(d.soul)));
                }
                d.dirty = true;
            }
        }
        if (!hostile) return;
        List<ItemStack> extra = new ArrayList<>();
        if (!Targets.isCustomMob(dead)) {
            double sc = plugin.getConfig().getDouble("drops.shard-chance", 0.08) * (1 + st.get("shard_luck.amount"));
            if (rnd().nextDouble() < sc) extra.add(plugin.items().create("shard", 1));
        } else if (st.get("shard_luck.amount") > 0 && rnd().nextDouble() < st.get("shard_luck.amount") * 0.5) {
            extra.add(plugin.items().create("shard", 1));
        }
        double lb = st.get("loot_boost.chance");
        if (lb > 0 && !Targets.isBoss(dead)) {
            for (ItemStack it : new ArrayList<>(e.getDrops())) {
                if (rnd().nextDouble() < lb && !Items.isCustom(it)) extra.add(it.clone());
            }
        }
        double wl = st.get("weapon_luck.chance");
        if (wl > 0 && rnd().nextDouble() < wl) {
            WeaponDef w = plugin.weapons().randomCommon();
            if (w != null) {
                extra.add(plugin.weapons().create(w));
                killer.sendMessage(Text.mm("<#ffcc55>✦ 보물 발견! " + plugin.weapons().displayName(w)));
            }
        }
        e.getDrops().addAll(extra);
    }

    @EventHandler(ignoreCancelled = true)
    public void onExp(PlayerExpChangeEvent e) {
        double b = aug.stats(e.getPlayer()).get("xp_boost.amount");
        if (b > 0 && e.getAmount() > 0) {
            double v = e.getAmount() * (1 + b);
            int whole = (int) v;
            if (rnd().nextDouble() < v - whole) whole++;
            e.setAmount(whole);
        }
    }

    // ------------------------------------------------------------------ 채집/생성기

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBlockDrop(BlockDropItemEvent e) {
        Player p = e.getPlayer();
        if (!playing(p)) return;
        Stats st = aug.stats(p);
        BlockState state = e.getBlockState();
        Material type = state.getType();
        List<Item> items = e.getItems();
        Location at = e.getBlock().getLocation().add(0.5, 0.5, 0.5);

        if (st.has("auto_smelt")) {
            int xp = 0;
            for (Item it : items) {
                ItemStack s = it.getItemStack();
                Material to = smelt(s.getType());
                if (to != null) {
                    it.setItemStack(new ItemStack(to, s.getAmount()));
                    xp += s.getAmount();
                }
            }
            if (xp > 0) {
                at.getWorld().spawnParticle(Particle.FLAME, at, 8, 0.25, 0.25, 0.25, 0.01);
                p.giveExp(xp);
            }
        }
        if (state.getBlockData() instanceof Ageable ag && ag.getAge() >= ag.getMaximumAge() && isCrop(type)) {
            double hb = st.get("harvest_bonus.chance");
            if (hb > 0 && rnd().nextDouble() < hb) dupe(items, at, e.getBlock().getWorld());
        } else if (type == Material.MELON || type == Material.PUMPKIN || type == Material.SUGAR_CANE || type == Material.CACTUS) {
            double hb = st.get("harvest_bonus.chance");
            if (hb > 0 && rnd().nextDouble() < hb) dupe(items, at, e.getBlock().getWorld());
        }
        if (Tag.LEAVES.isTagged(type)) {
            double sl = st.get("sapling_luck.chance");
            if (sl > 0) leafBonus(type, at, sl);
        }
        if (type == Material.STONE || type == Material.COBBLESTONE || Tag.COAL_ORES.isTagged(type) || Tag.IRON_ORES.isTagged(type)
                || Tag.COPPER_ORES.isTagged(type) || Tag.GOLD_ORES.isTagged(type) || Tag.DIAMOND_ORES.isTagged(type)
                || Tag.REDSTONE_ORES.isTagged(type) || Tag.LAPIS_ORES.isTagged(type) || Tag.EMERALD_ORES.isTagged(type)
                || type == Material.NETHERRACK) {
            double sc = plugin.getConfig().getDouble("drops.shard-mining-chance", 0.004) * (1 + st.get("shard_luck.amount"));
            if (rnd().nextDouble() < sc) {
                at.getWorld().dropItemNaturally(at, plugin.items().create("shard", 1));
                p.sendActionBar(Text.mm("<#c86bff>✦ 증강 파편을 캐냈습니다!"));
            }
        }
    }

    private void dupe(List<Item> items, Location at, World w) {
        for (Item it : new ArrayList<>(items)) {
            Material m = it.getItemStack().getType();
            if (m == Material.WHEAT_SEEDS || m == Material.BEETROOT_SEEDS) continue;
            w.dropItemNaturally(at, it.getItemStack().clone());
        }
        w.spawnParticle(Particle.HAPPY_VILLAGER, at, 10, 0.3, 0.3, 0.3, 0);
    }

    private static boolean isCrop(Material m) {
        return m == Material.WHEAT || m == Material.CARROTS || m == Material.POTATOES || m == Material.BEETROOTS
                || m == Material.NETHER_WART || m == Material.COCOA || m == Material.SWEET_BERRY_BUSH;
    }

    private static Material smelt(Material m) {
        return switch (m) {
            case RAW_IRON -> Material.IRON_INGOT;
            case RAW_GOLD -> Material.GOLD_INGOT;
            case RAW_COPPER -> Material.COPPER_INGOT;
            case ANCIENT_DEBRIS -> Material.NETHERITE_SCRAP;
            case SAND -> Material.GLASS;
            case CACTUS -> Material.GREEN_DYE;
            default -> null;
        };
    }

    private void leafBonus(Material leaves, Location at, double chance) {
        if (rnd().nextDouble() >= chance) return;
        Material sap = sapling(leaves);
        World w = at.getWorld();
        if (sap != null) w.dropItemNaturally(at, new ItemStack(sap));
        if ((leaves == Material.OAK_LEAVES || leaves == Material.DARK_OAK_LEAVES) && rnd().nextDouble() < 0.5) {
            w.dropItemNaturally(at, new ItemStack(Material.APPLE));
        }
        w.spawnParticle(Particle.HAPPY_VILLAGER, at, 6, 0.3, 0.3, 0.3, 0);
    }

    private static Material sapling(Material leaves) {
        String n = leaves.name();
        if (!n.endsWith("_LEAVES")) return null;
        String base = n.substring(0, n.length() - "_LEAVES".length());
        if (base.equals("MANGROVE")) return Material.MANGROVE_PROPAGULE;
        if (base.equals("AZALEA") || base.equals("FLOWERING_AZALEA")) return Material.AZALEA;
        return Material.matchMaterial(base + "_SAPLING");
    }

    @EventHandler(ignoreCancelled = true)
    public void onDecay(LeavesDecayEvent e) {
        Location at = e.getBlock().getLocation().add(0.5, 0.5, 0.5);
        double best = 0;
        for (Player p : e.getBlock().getWorld().getPlayers()) {
            if (p.getLocation().distanceSquared(at) > 24 * 24) continue;
            best = Math.max(best, aug.stats(p).get("sapling_luck.chance"));
        }
        if (best > 0) leafBonus(e.getBlock().getType(), at, best * 0.6);
    }

    /** 조약돌 생성기: 근처에 '광맥' 증강을 가진 플레이어가 있으면 확률로 광석이 생긴다. */
    @EventHandler(ignoreCancelled = true)
    public void onForm(BlockFormEvent e) {
        Material t = e.getNewState().getType();
        if (t != Material.COBBLESTONE && t != Material.STONE) return;
        Location at = e.getBlock().getLocation();
        double chance = plugin.getConfig().getDouble("generator.base-ore-chance", 0);
        int tier = chance > 0 ? 1 : 0;
        for (Player p : at.getWorld().getPlayers()) {
            if (p.getLocation().distanceSquared(at) > 16 * 16) continue;
            Stats st = aug.stats(p);
            double c = st.get("ore_gen.chance");
            if (c > chance) chance = c;
            tier = Math.max(tier, (int) st.get("ore_gen.tier"));
        }
        if (chance <= 0 || rnd().nextDouble() >= Math.min(0.6, chance)) return;
        Material ore = pickOre(Math.max(1, tier));
        if (ore != null) {
            e.getNewState().setType(ore);
            at.getWorld().spawnParticle(Particle.WAX_ON, at.clone().add(0.5, 1, 0.5), 6, 0.3, 0.2, 0.3, 0);
        }
    }

    private Material pickOre(int tier) {
        ConfigurationSection tiers = plugin.getConfig().getConfigurationSection("generator.tiers");
        if (tiers == null) return Material.COAL_ORE;
        ConfigurationSection sec = null;
        for (int t = tier; t >= 1 && sec == null; t--) sec = tiers.getConfigurationSection(String.valueOf(t));
        if (sec == null) return Material.COAL_ORE;
        int total = 0;
        for (String k : sec.getKeys(false)) total += sec.getInt(k);
        int x = rnd().nextInt(Math.max(1, total));
        for (String k : sec.getKeys(false)) {
            x -= sec.getInt(k);
            if (x < 0) return Material.matchMaterial(k);
        }
        return Material.COAL_ORE;
    }

    @EventHandler(ignoreCancelled = true)
    public void onFish(PlayerFishEvent e) {
        if (e.getState() != PlayerFishEvent.State.CAUGHT_FISH || !(e.getCaught() instanceof Item caught)) return;
        Player p = e.getPlayer();
        double fl = aug.stats(p).get("fishing_luck.chance");
        if (fl <= 0) return;
        if (rnd().nextDouble() < fl) {
            Items.give(p, caught.getItemStack().clone());
            p.sendActionBar(Text.mm("<#6bc8ff>✦ 대어! 한 마리 더 낚았습니다"));
        }
        if (rnd().nextDouble() < fl * 0.2) Items.give(p, plugin.items().create("shard", 1));
    }

    // ------------------------------------------------------------------ 이동: 이단 점프, 공허 수호

    @EventHandler(ignoreCancelled = true)
    public void onMove(PlayerMoveEvent e) {
        Player p = e.getPlayer();
        if (!playing(p)) return;
        Stats st = aug.stats(p);
        if (st.has("double_jump")) {
            if (p.isOnGround() && !p.getAllowFlight() && System.currentTimeMillis() >= aug.data(p).jumpReadyAt) {
                p.setAllowFlight(true);
                jumpGranted.add(p.getUniqueId());
            }
        } else if (jumpGranted.remove(p.getUniqueId())) {
            p.setAllowFlight(false);
            p.setFlying(false);
        }
        if (e.getTo().getY() < p.getWorld().getMinHeight() - 4 && st.has("void_rescue")) {
            PlayerData d = aug.data(p);
            if (System.currentTimeMillis() >= d.voidReadyAt) rescue(p, d, st);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onToggleFlight(PlayerToggleFlightEvent e) {
        Player p = e.getPlayer();
        if (!playing(p) || !jumpGranted.contains(p.getUniqueId())) return;
        e.setCancelled(true);
        jumpGranted.remove(p.getUniqueId());
        p.setFlying(false);
        p.setAllowFlight(false);
        Stats st = aug.stats(p);
        double power = st.get("double_jump.power", 1.0);
        Vector dir = p.getLocation().getDirection().setY(0);
        if (dir.lengthSquared() > 1e-6) dir.normalize();
        Vector v = dir.multiply(0.55 * power);
        v.setY(0.75 * power);
        p.setVelocity(v);
        p.setFallDistance(0);
        aug.data(p).jumpReadyAt = System.currentTimeMillis() + (long) (st.get("double_jump.cooldown", 1.0) * 1000);
        p.getWorld().spawnParticle(Particle.CLOUD, p.getLocation(), 15, 0.3, 0.05, 0.3, 0.02);
        Fx.sound(p.getLocation(), "entity.breeze.jump", 0.8f, 1.2f);
    }

    // ------------------------------------------------------------------ 주기 효과

    private void tick() {
        tick++;
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.isDead()) continue;
            Stats st = aug.stats(p);
            PlayerData d = aug.data(p);
            if (tick % 15 == 0) aug.applyPotions(p, st, false);
            if (!playing(p)) continue;
            // 재생
            double ri = st.get("regen.interval");
            if (ri > 0 && now - d.regenLastAt >= ri * 1000) {
                d.regenLastAt = now;
                if (p.getHealth() < Combat.maxHealth(p)) Combat.heal(p, st.get("regen.amount", 1));
            }
            // 활공
            if (st.has("glide") && p.isSneaking() && !p.isOnGround() && p.getVelocity().getY() < -0.25) {
                p.addPotionEffect(new PotionEffect(PotionEffectType.SLOW_FALLING, 12, 0, true, false, false));
                if (tick % 2 == 0) p.getWorld().spawnParticle(Particle.CLOUD, p.getLocation(), 2, 0.2, 0, 0.2, 0);
            }
            // 자석
            double mr = st.get("magnet.radius");
            if (mr > 0) {
                for (Entity ent : p.getNearbyEntities(mr, mr, mr)) {
                    if (!(ent instanceof Item it) || it.getPickupDelay() > 10) continue;
                    Vector v = p.getLocation().add(0, 0.5, 0).toVector().subtract(it.getLocation().toVector());
                    if (v.lengthSquared() < 1) continue;
                    it.setVelocity(v.normalize().multiply(0.45));
                }
            }
            // 성장 오라
            double gr = st.get("growth_aura.radius");
            int gi = (int) Math.max(4, st.get("growth_aura.interval", 40) / 4);
            if (gr > 0 && tick % gi == 0) grow(p, (int) gr);
        }
        if (tick % 1500 == 0) {
            for (PlayerData d : aug.store().loaded()) if (d.dirty) aug.store().save(d);
        }
    }

    private void grow(Player p, int r) {
        Location c = p.getLocation();
        World w = p.getWorld();
        for (int i = 0; i < 14; i++) {
            int x = c.getBlockX() + rnd().nextInt(-r, r + 1);
            int z = c.getBlockZ() + rnd().nextInt(-r, r + 1);
            for (int y = c.getBlockY() - 2; y <= c.getBlockY() + 2; y++) {
                Block b = w.getBlockAt(x, y, z);
                if (b.getBlockData() instanceof Ageable ag && isCrop(b.getType()) && ag.getAge() < ag.getMaximumAge()) {
                    ag.setAge(ag.getAge() + 1);
                    b.setBlockData(ag);
                    w.spawnParticle(Particle.HAPPY_VILLAGER, b.getLocation().add(0.5, 0.5, 0.5), 3, 0.25, 0.25, 0.25, 0);
                    break;
                }
                if (Tag.SAPLINGS.isTagged(b.getType()) && rnd().nextDouble() < 0.15) {
                    b.applyBoneMeal(BlockFace.UP);
                    break;
                }
            }
        }
    }

}
