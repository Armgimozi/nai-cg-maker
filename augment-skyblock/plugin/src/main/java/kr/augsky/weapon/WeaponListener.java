package kr.augsky.weapon;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.Stats;
import kr.augsky.skill.Combat;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.SkillContext;
import kr.augsky.skill.SkillDef;
import kr.augsky.skill.Targets;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.NamespacedKey;
import org.bukkit.block.Block;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 무기 스킬 조작과 근접 공격 패시브.
 * 근접 무기: 우클릭(1번), 웅크리기+우클릭(2번, 없으면 1번), 웅크리기+좌클릭(3번).
 * 활: 우클릭은 그냥 당겨 쏘기, 웅크리기+당겨 쏘기(1번), 웅크리기+좌클릭(2번).
 */
public final class WeaponListener implements Listener {
    private final AugSky plugin;
    /** [0] = 아무 슬롯이나 마지막으로 시도한 틱, [1~3] = 슬롯별. */
    private final Map<UUID, int[]> lastCastTick = new HashMap<>();
    private final Map<UUID, Integer> suppressUntil = new HashMap<>();
    private final Map<UUID, Integer> fakeSwingTick = new HashMap<>();
    /** 안내서를 만들 때 쓴 guide-book 글의 지문. */
    private static final NamespacedKey BOOK_SIG = Keys.of("book_sig");

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
            // 들고 있는 사람에게는 보내지 않는다: 1인칭에서는 카메라 바로 앞이라 큰 덩어리로 보이고, 모델 아우라가 이미 있다
            if (spec.equals("PRISM")) {
                java.awt.Color c = java.awt.Color.getHSBColor((auraTick * 0.03f) % 1f, 0.55f, 1f);
                new kr.augsky.util.Fx.Spec(org.bukkit.Particle.DUST,
                        new org.bukkit.Particle.DustOptions(org.bukkit.Color.fromRGB(c.getRed(), c.getGreen(), c.getBlue()), 0.8f))
                        .spawnExcept(p, at, strong ? 2 : 1, 0.12, 0.3, 0.12, 0);
                continue;
            }
            kr.augsky.util.Fx.Spec sp = kr.augsky.util.Fx.parse(spec);
            if (sp != null) sp.spawnExcept(p, at, strong ? 2 : 1, 0.12, 0.3, 0.12, 0.005);
        }
    }

    /** 제단/소환대를 누를 때 같은 클릭으로 스킬이 나가지 않게 잠깐 막는다. */
    public void suppress(Player p, int ticks) {
        // 이미 더 길게 막혀 있으면 줄이지 않는다
        suppressUntil.merge(p.getUniqueId(), Bukkit.getCurrentTick() + ticks, Math::max);
    }

    /**
     * 클라이언트는 우클릭으로 물건을 쓸 때(특히 왼손 물건)나 Q 로 버릴 때도 팔을 휘두르고,
     * 서버는 그 휘두르기를 좌클릭으로 알린다. 그런 가짜 좌클릭이 웅크리기+좌클릭 스킬로 나가지 않게 표시해 둔다.
     */
    private void markFakeSwing(Player p) {
        fakeSwingTick.put(p.getUniqueId(), Bukkit.getCurrentTick());
    }

    private boolean isFakeSwing(Player p) {
        Integer t = fakeSwingTick.get(p.getUniqueId());
        return t != null && Bukkit.getCurrentTick() - t <= 1;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDrop(PlayerDropItemEvent e) {
        markFakeSwing(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        Action a = e.getAction();
        Player p = e.getPlayer();
        boolean right = a == Action.RIGHT_CLICK_AIR || a == Action.RIGHT_CLICK_BLOCK;
        if (right) markFakeSwing(p);
        if (e.getHand() != EquipmentSlot.HAND) return;
        // 허공 좌클릭은 늘 '취소된' 상태로 오므로 ignoreCancelled 를 쓰지 않는다
        if (a == Action.LEFT_CLICK_AIR || a == Action.LEFT_CLICK_BLOCK) {
            if (!isFakeSwing(p)) sneakLeftClick(p);
            return;
        }
        if (!right) return;
        if (p.getGameMode() == GameMode.SPECTATOR) return;
        WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        if (w == null || w.isBow()) return; // 활은 우클릭으로 당겨 쏜다 (스킬은 웅크리고 쏘기)
        // 웅크리기+우클릭은 2번 스킬. 2번이 없는 무기는 1번이 나간다
        int slot = p.isSneaking() && w.skill2() != null ? 2 : 1;
        if (w.skillOf(slot) == null) return; // 스킬 없는 무기는 바닐라 그대로
        if (a == Action.RIGHT_CLICK_BLOCK) {
            Block b = e.getClickedBlock();
            if (b != null && b.getType().isInteractable() && !p.isSneaking()) return;
        }
        e.setUseItemInHand(org.bukkit.event.Event.Result.DENY);
        cast(p, w, slot);
    }

    /** 웅크리고 엔티티를 때릴 때. 공격은 그대로 두고 스킬만 쓴다. */
    @EventHandler(priority = EventPriority.HIGH)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        // 제단은 좌클릭해도 아무 일 없어야 한다 (AltarService 가 안내만 띄운다)
        if (e.getAttacked() instanceof org.bukkit.entity.Interaction i && i.getPersistentDataContainer().has(kr.augsky.Keys.ALTAR)) {
            suppress(e.getPlayer(), 2);
            return;
        }
        // 같은 휘두르기로 허공 좌클릭이 함께 올 수 있지만 cast 의 같은 슬롯 3틱 막기가 하나로 친다
        sneakLeftClick(e.getPlayer());
    }

    /** 웅크리기+좌클릭: 근접 무기는 3번, 활은 2번 스킬. 공격·블록 부수기는 막지 않는다. */
    private void sneakLeftClick(Player p) {
        if (!p.isSneaking() || p.getGameMode() == GameMode.SPECTATOR) return;
        WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
        if (w == null) return;
        int slot = w.isBow() ? 2 : 3;
        if (w.skillOf(slot) == null) return;
        cast(p, w, slot);
    }

    /** 활: 웅크리고 당겨 쏘면 화살 대신 1번 스킬. 그냥 쏜 화살에는 무기 피해를 싣고, 맞으면 패시브가 터지게 표시한다. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onShoot(org.bukkit.event.entity.EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        WeaponDef w = plugin.weapons().of(e.getBow());
        if (w == null || !w.isBow()) return;
        // force 는 화살 속도(당긴 정도 × 3)다. 살짝 당겼다 놓은 건 스킬로 치지 않는다
        if (p.isSneaking() && e.getHand() == EquipmentSlot.HAND && w.skill() != null && e.getForce() / 3f >= 0.35f) {
            // 재사용 대기 중이면 cast 가 남은 시간만 띄우고, 화살은 그대로 나간다
            if (cast(p, w, 1)) {
                e.setCancelled(true);
                // 무한은 보통 화살만 아끼므로 분광·물약 화살은 이 이벤트 전에 이미 빠져 있다. 쏘지 않았으니 돌려준다
                ItemStack ammo = e.getConsumable();
                if (ammo != null && !ammo.isEmpty() && !ammo.hasData(io.papermc.paper.datacomponent.DataComponentTypes.INTANGIBLE_PROJECTILE))
                    kr.augsky.util.Items.give(p, ammo.clone());
                // 클라이언트가 화살을 쏜 줄 알고 인벤토리를 미리 바꿨을 수 있다
                Bukkit.getScheduler().runTask(plugin, () -> {
                    if (p.isOnline()) p.updateInventory();
                });
                return;
            }
        }
        if (!(e.getProjectile() instanceof org.bukkit.entity.AbstractArrow arrow)) return;
        // 바닐라 화살 피해 = 기본 피해 × 속도(끝까지 당기면 약 3) + 치명타 덤(평균 절반쯤)
        arrow.setDamage(w.damage() / 3.5);
        arrow.setPickupStatus(org.bukkit.entity.AbstractArrow.PickupStatus.CREATIVE_ONLY);
        arrow.getPersistentDataContainer().set(kr.augsky.Keys.WEAPON, org.bukkit.persistence.PersistentDataType.STRING, w.id());
        // 무한은 보통 화살만. 물약 화살·분광 화살은 그대로 쓰인다
        if (e.getConsumable() != null && e.getConsumable().getType() == org.bukkit.Material.ARROW) e.setConsumeItem(false);
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

    /** 슬롯 스킬을 쓴다. 실제로 나갔으면 true, 막혔거나 재사용 대기 중이면 false (대기 중이면 남은 시간을 띄운다). */
    public boolean cast(Player p, WeaponDef w, int slot) {
        int now = Bukkit.getCurrentTick();
        Integer sup = suppressUntil.get(p.getUniqueId());
        if (sup != null && now < sup) return false;
        SkillDef s = plugin.skills().get(w.skillOf(slot));
        if (s == null) return false;
        // 한 번 누른 것에 이벤트가 둘 올 수 있다 (엔티티 공격 + 허공 좌클릭, 블록 우클릭 + 허공 우클릭).
        // 같은 슬롯은 3틱, 다른 슬롯은 같은 틱만 하나로 쳐서 빠른 연계(우클릭 → 웅크리기+좌클릭)는 막지 않는다.
        // 스킬이 나갔거나 대기시간을 알렸을 때만 기록하므로, 아무 일 없던 클릭이 다음 입력을 삼키지 않는다
        int[] last = lastCastTick.computeIfAbsent(p.getUniqueId(), k -> new int[]{-100, -100, -100, -100});
        if (now - last[slot] < 3 || now == last[0]) return false;
        last[slot] = now;
        last[0] = now;

        String key = w.id() + "#" + slot;
        long rem = plugin.cooldowns().remainingMs(p.getUniqueId(), key);
        if (rem > 0) {
            p.sendActionBar(Text.mm("<#ff7070>⏳ " + s.name() + " <gray>" + String.format("%.1f", rem / 1000.0) + "초"));
            return false;
        }
        Stats st = plugin.augments().stats(p);
        double haste = Math.min(0.6, st.get("skill_haste.amount"));
        double cd = s.cooldown() * (1 - haste);
        plugin.cooldowns().set(p.getUniqueId(), key, cd);
        // 무기에 바닐라 아이템 쿨타임은 걸지 않는다. 걸면 다음 우클릭이 서버에 오지 않아
        // 1번이 도는 동안 웅크리기+우클릭(2번)까지 막힌다. 남은 시간은 액션바로 보여 준다
        double power = w.skillPower() * (1 + st.get("skill_power.amount"));
        SkillContext ctx = new SkillContext(plugin, p, null, power);
        s.cast(ctx);
        p.sendActionBar(Text.mm("<#ffcc55>✦ " + s.name()));
        return true;
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

    /**
     * 예전에 만든 무기와 안내서를 지금 내용으로 바꾼다.
     * 무기 설명·공격력과 안내서 글은 만들 때 아이템에 박히므로, 판이 바뀌거나 리로드하면 옛 조작법(F키 등)이 남는다.
     * 들어올 때 인벤토리·엔더 상자, 손에 들 때, 주울 때, 상자를 열 때 고친다. 지문이 같으면 건드리지 않는다.
     */
    public void refreshItems(Player p) {
        refreshItems(p.getInventory());
        refreshItems(p.getEnderChest());
    }

    private void refreshItems(Inventory inv) {
        ItemStack[] items = inv.getContents();
        for (int i = 0; i < items.length; i++) {
            ItemStack fresh = refreshed(items[i]);
            if (fresh != null) inv.setItem(i, fresh);
        }
    }

    /** 바꿔야 하면 새 아이템, 아니면 null. */
    private ItemStack refreshed(ItemStack it) {
        if (it == null || it.isEmpty()) return null;
        if (plugin.weapons().refresh(it)) return it;
        if (!"guide_book".equals(Items.tag(it, Keys.ITEM))) return null;
        // 안내서는 config.yml 의 guide-book 글이 바뀌었을 때만 새로 만든다
        int sig = plugin.getConfig().getStringList("guide-book").hashCode();
        Integer had = it.getItemMeta().getPersistentDataContainer().get(BOOK_SIG, PersistentDataType.INTEGER);
        if (had != null && had == sig) return null;
        ItemStack book = plugin.items().guideBook();
        book.setAmount(it.getAmount());
        book.editMeta(m -> m.getPersistentDataContainer().set(BOOK_SIG, PersistentDataType.INTEGER, sig));
        return book;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        refreshItems(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        PlayerInventory inv = e.getPlayer().getInventory();
        ItemStack fresh = refreshed(inv.getItem(e.getNewSlot()));
        if (fresh != null) inv.setItem(e.getNewSlot(), fresh);
    }

    /** 땅에 떨어져 있던 옛 무기. 줍는 중에는 아이템을 바꿀 수 없으니 다음 틱에 인벤토리를 훑는다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        ItemStack it = e.getItem().getItemStack();
        if (Items.tag(it, Keys.WEAPON) == null && !"guide_book".equals(Items.tag(it, Keys.ITEM))) return;
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) refreshItems(p.getInventory());
        });
    }

    /** 상자·통 등에 넣어 두었던 옛 무기. 플러그인 메뉴는 늘 새로 만들므로 건너뛴다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        if (e.getInventory().getHolder(false) instanceof kr.augsky.altar.Menus.Holder) return;
        refreshItems(e.getInventory());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        lastCastTick.remove(e.getPlayer().getUniqueId());
        suppressUntil.remove(e.getPlayer().getUniqueId());
        fakeSwingTick.remove(e.getPlayer().getUniqueId());
    }

    /** 스킬 있는 무기를 든 동안 액션바에 슬롯마다 조작과 상태를 띄운다. */
    private void hud() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.getGameMode() == GameMode.SPECTATOR) continue;
            WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
            if (w == null || !w.hasSkills()) continue;
            StringBuilder sb = new StringBuilder();
            for (int slot = 1; slot <= 3; slot++) {
                String part = part(p, w, slot);
                if (part == null) continue;
                if (sb.length() > 0) sb.append("  <dark_gray>|  ");
                sb.append(part);
            }
            if (sb.length() > 0) p.sendActionBar(Text.mm(sb.toString()));
        }
    }

    private String part(Player p, WeaponDef w, int slot) {
        String label = w.inputLabel(slot);
        SkillDef s = plugin.skills().get(w.skillOf(slot));
        if (label == null || s == null) return null;
        long rem = plugin.cooldowns().remainingMs(p.getUniqueId(), w.id() + "#" + slot);
        if (rem <= 0) return "<#ffcc55>[" + label + "] <white>" + s.name() + " <#7cff8c>✔";
        return "<gray>[" + label + "] " + s.name() + " <#ff7070>" + String.format("%.1f", rem / 1000.0) + "s";
    }
}
