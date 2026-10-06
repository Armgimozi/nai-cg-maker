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
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
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
    /** 플레이어마다 마지막으로 휘두른 근접 공격 (휩쓸기 대상에게 같은 효과를 주려고 기억한다) */
    private final Map<UUID, Swing> swings = new HashMap<>();
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
        swings.remove(id);
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

    /**
     * 한 번 휘두른 근접 공격에서 주 대상에게 터진 전투 효과.
     * 바닐라는 주 대상의 피해 이벤트를 먼저 부르고, 같은 틱 안에서 휩쓸기에 함께 맞은 몹들을 부른다.
     */
    private record Swing(int tick, Set<String> fired) {}

    /**
     * 이번 피해에서 전투 효과 key 가 터지는지 정한다.
     *  - 직접 휘두른 근접 공격, 화살 같은 투사체: 효과마다 하나 세어 every 번째에 터진다.
     *  - 휩쓸기에 함께 맞은 몹: 세지 않고, 같은 휘두름에서 주 대상에게 터진 효과면 똑같이 받는다.
     *    예전에 휩쓸린 몹도 저마다 확률을 굴렸으니, 여러 마리를 칠 때의 평균을 지키려는 것이다.
     *    세지는 않으므로 '몇 번 남았는지'는 주 대상 기준 그대로다.
     *  - 그 밖의 피해(가시, 폭발, 스킬 등): 세지도 터지지도 않는다.
     */
    private boolean proc(Player p, EntityDamageEvent e, String key, int every) {
        if (every <= 0) return false;
        UUID id = p.getUniqueId();
        switch (e.getCause()) {
            case ENTITY_ATTACK, PROJECTILE -> {
                boolean fire = aug.procs().hit(id, key, every);
                if (fire && e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK) {
                    Swing s = swings.get(id);
                    if (s != null && s.tick() == Bukkit.getCurrentTick()) s.fired().add(key);
                }
                return fire;
            }
            case ENTITY_SWEEP_ATTACK -> {
                Swing s = swings.get(id);
                return s != null && s.tick() == Bukkit.getCurrentTick() && s.fired().contains(key);
            }
            default -> {
                return false;
            }
        }
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
            // 회피는 확률이 아니라 받는 공격 N번째마다 (비율 상한 0.5 → 적어도 2번에 한 번은 맞는다)
            if (aug.procs().hit(victim.getUniqueId(), "dodge", vs.every("dodge", 0.5))) {
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
        // 직접 휘두른 근접 공격은 새 휘두름이다. 이 기록을 이어지는 휩쓸기 대상들이 본다 (proc)
        if (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK && e.getDamager() == attacker) {
            swings.put(attacker.getUniqueId(), new Swing(Bukkit.getCurrentTick(), new HashSet<>()));
        }
        if (!(e.getEntity() instanceof LivingEntity target) || !Targets.isEnemy(attacker, target)) return;
        Stats st = aug.stats(attacker);
        double mult = 1 + st.get("damage_bonus.amount");
        double bt = st.get("berserk.threshold");
        if (bt > 0 && attacker.getHealth() / Combat.maxHealth(attacker) <= bt) mult += st.get("berserk.amount");
        if (st.get("first_strike.amount") > 0 && target.getHealth() >= Combat.maxHealth(target) - 0.01) {
            mult += st.get("first_strike.amount");
        }
        if (Targets.isBoss(target)) mult += st.get("boss_damage.amount");
        // 치명타: 맞힌 공격 N번째마다 (휩쓸린 몹은 주 대상이 치명타일 때 함께)
        if (proc(attacker, e, "crit", st.every("crit", 0.75))) {
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

        // 공격 시 효과는 확률 대신 효과마다 따로 세어 N번째 공격마다 터진다 (ProcCounter, proc)
        onHitProcs(e, attacker, target, st, melee, base);

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

    /** 맞힌 공격 하나를 세고, 차례가 된 '공격 시' 효과를 터뜨린다. */
    private void onHitProcs(EntityDamageEvent e, Player attacker, LivingEntity target, Stats st, boolean melee, double base) {
        if (proc(attacker, e, "ignite", st.every("ignite", 1))) {
            target.setFireTicks(Math.max(target.getFireTicks(), (int) (st.get("ignite.seconds", 3) * 20)));
        }
        // 갑옷 세트와 증강이 같은 둔화를 따로 줄 수 있으니 항목마다 따로 센다
        for (int i = 0; i < st.hitPotions.size(); i++) {
            Stats.HitPotion hp = st.hitPotions.get(i);
            if (proc(attacker, e, "hit_potion#" + i + ":" + hp.type().getKey().getKey(), hp.every())) {
                target.addPotionEffect(new PotionEffect(hp.type(), hp.ticks(), hp.amplifier()));
            }
        }
        if (proc(attacker, e, "lightning", st.every("lightning", 1))) {
            double dmg = st.get("lightning.damage", 5);
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (!target.isValid()) return;
                target.getWorld().strikeLightningEffect(target.getLocation());
                Combat.damage(attacker, target, dmg, true, null);
            });
        }
        if (proc(attacker, e, "chain_lightning", st.every("chain_lightning", 1))) {
            int n = (int) Math.max(2, st.get("chain_lightning.targets", 3));
            double dmg = st.get("chain_lightning.damage", 4);
            Bukkit.getScheduler().runTask(plugin, () -> chain(attacker, target, n, dmg));
        }
        // 쌍검술은 근접 공격만 센다
        if (melee && proc(attacker, e, "double_strike", st.every("double_strike", 1))) {
            double amt = base * Math.max(0.3, st.get("double_strike.ratio", 0.6));
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (!target.isValid() || target.isDead()) return;
                target.getWorld().spawnParticle(Particle.SWEEP_ATTACK, target.getLocation().add(0, 1, 0), 2, 0.2, 0.2, 0.2, 0);
                Fx.sound(target.getLocation(), "entity.player.attack.sweep", 1f, 1.4f);
                Combat.damage(attacker, target, amt, false, null);
            }, 5);
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
        World here = p.getWorld();
        var nether = plugin.nether();
        boolean sky = nether != null && nether.isSky(here);
        // 떨어진 쪽(하늘 / 하늘 네더) 안에서 끌어올린다. 침대·정박기가 건너편에 있어도 그리로 보내지 않는다 (돌아오려면 문을 다시 찾아야 한다)
        if (to != null && !to.getWorld().equals(here) && (sky || here.equals(Bukkit.getWorlds().get(0)))) to = null;
        if (to == null && sky) to = nether.hubSpawn();
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

    /**
     * 죽으면 기본적으로 아이템을 떨어뜨린다. 증강이 있으면 일부를 지킨다.
     * 지킨 아이템은 Paper 의 getItemsToKeep 으로 원래 칸에 그대로 남는다.
     */
    @EventHandler(priority = EventPriority.HIGH)
    public void onDeath(PlayerDeathEvent e) {
        if (e.getKeepInventory()) return;
        Player p = e.getPlayer();
        Stats st = aug.stats(p);
        if (st.has("keep_all")) {
            e.setKeepInventory(true);
            e.getDrops().clear();
            e.setKeepLevel(true);
            e.setDroppedExp(0);
            p.sendMessage(Text.mm("<gradient:#ff6b9d:#c86bff>영혼 결속</gradient><gray>: 아무것도 잃지 않았습니다."));
            return;
        }
        boolean levels = st.has("keep_levels");
        if (levels) {
            e.setKeepLevel(true);
            e.setDroppedExp(0);
        }
        PlayerInventory inv = p.getInventory();
        Set<Integer> slots = new java.util.TreeSet<>();
        int hotbar = (int) Math.min(9, st.get("keep_hotbar.slots"));
        for (int i = 0; i < hotbar; i++) slots.add(i);
        if (st.has("keep_armor")) {
            for (int i = 36; i <= 40; i++) slots.add(i); // 갑옷 4칸 + 왼손
        }
        boolean weapons = st.has("keep_weapons"), materials = st.has("keep_materials");
        if (weapons || materials) {
            for (int i = 0; i < inv.getSize(); i++) {
                ItemStack it = inv.getItem(i);
                if (weapons && Items.tag(it, kr.augsky.Keys.WEAPON) != null) slots.add(i);
                if (materials && Items.tag(it, kr.augsky.Keys.ITEM) != null) slots.add(i);
            }
        }
        int kept = 0;
        for (int slot : slots) {
            if (slot >= inv.getSize()) continue;
            ItemStack it = inv.getItem(slot);
            if (it == null || it.getType().isAir()) continue;
            // 저주받은 '소실' 마법은 존중한다 (원래 사라질 아이템)
            if (it.containsEnchantment(org.bukkit.enchantments.Enchantment.VANISHING_CURSE)) continue;
            e.getItemsToKeep().add(it);
            removeOne(e.getDrops(), it);
            kept += it.getAmount();
        }
        if (kept > 0 || levels) {
            p.sendMessage(Text.mm("<#9ad8ff>✦ 증강 덕분에 " + (kept > 0 ? "아이템 " + kept + "개" : "") + (kept > 0 && levels ? "와 " : "")
                    + (levels ? "경험치" : "") + "<#9ad8ff>를 지켰습니다."));
        }
    }

    /**
     * 탱크엔진: 다른 플레이어를 처치할 때마다 최대 체력이 영구히 오른다. 상한 없이 계속 쌓인다 (그래서 프리즘).
     * 쌓인 값은 PlayerData.tank 에 저장되어 죽음·재접속·재시작 뒤에도 applyAttributes 가 다시 붙인다.
     * (기본 server.properties 는 pvp=true. pvp=false 로 바꾼 서버에서는 쌓이지 않는다.)
     */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlayerKill(PlayerDeathEvent e) {
        Player victim = e.getPlayer();
        Player killer = victim.getKiller();
        // 스스로 죽은 것(자기 화살, 자기에게 쓴 피해)은 치지 않는다
        if (killer == null || killer.getUniqueId().equals(victim.getUniqueId()) || !killer.isOnline()) return;
        Stats st = aug.stats(killer);
        if (!st.has("tank_engine")) return;
        double per = st.get("tank_engine.amount", 1);
        if (per <= 0) return;
        PlayerData d = aug.data(killer);
        d.tank += per;
        aug.applyAttributes(killer, d);
        // 바로 저장해 서버가 갑자기 꺼져도 잃지 않게 한다
        aug.store().save(d);
        killer.sendMessage(Text.mm("<#ffb347>⚙ 탱크엔진<gray>: 최대 체력 <white>+" + Text.num(per) + " <gray>(총 +" + Text.num(d.tank) + ")"));
        Fx.sound(killer.getLocation(), "block.anvil.use", 0.7f, 1.4f);
    }

    private static void removeOne(List<ItemStack> drops, ItemStack it) {
        for (int i = 0; i < drops.size(); i++) {
            if (it.equals(drops.get(i))) {
                drops.remove(i);
                return;
            }
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
            double sc = plugin.getConfig().getDouble("drops.shard-chance", 0.06) * (1 + st.get("shard_luck.amount"));
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
                // 화로 경험치 구슬처럼 수선 장비를 먼저 고친다
                p.giveExp(xp, true);
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
            double sc = plugin.getConfig().getDouble("drops.shard-mining-chance", 0.01) * (1 + st.get("shard_luck.amount"));
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
