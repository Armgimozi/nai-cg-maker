package kr.augsky.augment;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.Fx;
import kr.augsky.util.Items;
import kr.augsky.util.P;
import kr.augsky.util.Text;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Registry;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/** 증강 획득/제거, 수치 계산, 제단 비용과 선택지. */
public final class AugmentService {
    private static final String MOD_PREFIX = "aug_";

    private final AugSky plugin;
    private final AugmentRegistry registry;
    private final PlayerDataStore store;
    private final Map<UUID, Set<PotionEffectType>> appliedPotions = new HashMap<>();

    public AugmentService(AugSky plugin, AugmentRegistry registry, PlayerDataStore store) {
        this.plugin = plugin;
        this.registry = registry;
        this.store = store;
    }

    public AugmentRegistry registry() {
        return registry;
    }

    public PlayerDataStore store() {
        return store;
    }

    public PlayerData data(Player p) {
        PlayerData d = store.get(p.getUniqueId());
        d.lastName = p.getName();
        return d;
    }

    public Stats stats(Player p) {
        PlayerData d = data(p);
        if (d.stats == null) d.stats = Stats.compute(d.augments, registry);
        return d.stats;
    }

    // ------------------------------------------------------------------ 적용

    /** 증강이 바뀌었을 때: 수치 다시 계산, 속성/포션 다시 적용. */
    public void refresh(Player p) {
        PlayerData d = data(p);
        d.stats = Stats.compute(d.augments, registry);
        applyAttributes(p, d);
        applyPotions(p, d.stats, true);
    }

    public void applyAttributes(Player p, PlayerData d) {
        Stats st = d.stats == null ? stats(p) : d.stats;
        for (Attribute a : Registry.ATTRIBUTE) {
            AttributeInstance inst = p.getAttribute(a);
            if (inst == null) continue;
            for (AttributeModifier m : new ArrayList<>(inst.getModifiers())) {
                if (m.getKey().getNamespace().equals(Keys.NS) && m.getKey().getKey().startsWith(MOD_PREFIX)) {
                    inst.removeModifier(m);
                }
            }
        }
        Map<String, Double> sums = new LinkedHashMap<>();
        Map<String, Stats.AttrMod> sample = new HashMap<>();
        for (Stats.AttrMod m : st.attributes) {
            String k = m.attribute().getKey().getKey() + "|" + m.op().name();
            sums.merge(k, m.amount(), Double::sum);
            sample.putIfAbsent(k, m);
        }
        if (d.soul > 0) {
            String k = "max_health|" + AttributeModifier.Operation.ADD_NUMBER.name();
            sums.merge(k, d.soul, Double::sum);
            sample.putIfAbsent(k, new Stats.AttrMod(Attribute.MAX_HEALTH, AttributeModifier.Operation.ADD_NUMBER, 0));
        }
        for (Map.Entry<String, Double> en : sums.entrySet()) {
            Stats.AttrMod m = sample.get(en.getKey());
            AttributeInstance inst = p.getAttribute(m.attribute());
            if (inst == null) continue;
            String path = MOD_PREFIX + m.attribute().getKey().getKey() + "_" + m.op().name().toLowerCase();
            inst.addModifier(new AttributeModifier(Keys.of(path), en.getValue(), m.op()));
        }
        AttributeInstance mh = p.getAttribute(Attribute.MAX_HEALTH);
        if (mh != null && p.getHealth() > mh.getValue()) p.setHealth(mh.getValue());
    }

    /** 증강 포션 효과를 무한 지속으로 건다. force 면 사라진 효과를 정리한다. */
    public void applyPotions(Player p, Stats st, boolean force) {
        Set<PotionEffectType> applied = appliedPotions.computeIfAbsent(p.getUniqueId(), k -> new HashSet<>());
        Set<PotionEffectType> want = new HashSet<>();
        for (Stats.Potion pt : st.potions) {
            want.add(pt.type());
            PotionEffect cur = p.getPotionEffect(pt.type());
            if (cur == null || cur.getAmplifier() < pt.amplifier()
                    || (cur.getDuration() != PotionEffect.INFINITE_DURATION && cur.getAmplifier() == pt.amplifier())) {
                p.addPotionEffect(new PotionEffect(pt.type(), PotionEffect.INFINITE_DURATION, pt.amplifier(), true, false, true));
            }
        }
        if (force) {
            for (PotionEffectType t : applied) {
                if (want.contains(t)) continue;
                PotionEffect cur = p.getPotionEffect(t);
                if (cur != null && cur.getDuration() == PotionEffect.INFINITE_DURATION) p.removePotionEffect(t);
            }
        }
        applied.clear();
        applied.addAll(want);
    }

    public void forget(UUID id) {
        appliedPotions.remove(id);
    }

    // ------------------------------------------------------------------ 획득/제거

    public boolean grant(Player p, String id, boolean announce) {
        AugmentDef def = registry.get(id);
        if (def == null) return false;
        PlayerData d = data(p);
        if (d.stacks(id) >= def.maxStacks()) return false;
        d.augments.merge(id, 1, Integer::sum);
        d.picks++;
        d.dirty = true;
        refresh(p);
        for (AugmentDef.Effect ef : def.effects()) instant(p, ef);
        store.save(d);
        if (announce) celebrate(p, def);
        return true;
    }

    private void instant(Player p, AugmentDef.Effect ef) {
        P e = ef.p();
        switch (ef.type()) {
            case "grant_random" -> {
                Tier t = Tier.parse(e.s("tier", "GOLD"));
                int n = e.i("count", 1);
                Bukkit.getScheduler().runTaskLater(plugin, () -> {
                    for (int i = 0; i < n; i++) {
                        List<String> pick = roll(p, t, 1, List.of());
                        if (pick.isEmpty()) break;
                        grant(p, pick.get(0), true);
                    }
                }, 30);
            }
            case "grant_item" -> {
                int amt = e.i("amount", 1);
                ItemStack it = plugin.items().spec(e.s("item", "shard"), amt);
                if (it != null) Items.give(p, it);
            }
            default -> {
            }
        }
    }

    public boolean remove(Player p, String id) {
        PlayerData d = data(p);
        Integer cur = d.augments.get(id);
        if (cur == null) return false;
        if (cur <= 1) d.augments.remove(id);
        else d.augments.put(id, cur - 1);
        refresh(p);
        store.save(d);
        return true;
    }

    public void reset(Player p) {
        PlayerData d = data(p);
        d.augments.clear();
        d.soul = 0;
        d.clearOffer();
        refresh(p);
        store.save(d);
    }

    private void celebrate(Player p, AugmentDef def) {
        Tier t = def.tier();
        p.showTitle(Title.title(Text.mm(t.wrap("✦ " + t.korean + " 증강 ✦")), Text.mm("<white>" + def.name()),
                Title.Times.times(Duration.ofMillis(200), Duration.ofMillis(2200), Duration.ofMillis(600))));
        Fx.sound(p.getLocation(), t.sound, 1f, 1f);
        Particle part = switch (t) {
            case SILVER -> Particle.END_ROD;
            case GOLD -> Particle.WAX_ON;
            case PRISM -> Particle.TOTEM_OF_UNDYING;
        };
        p.getWorld().spawnParticle(part, p.getLocation().add(0, 1, 0), 60, 0.6, 1, 0.6, 0.15);
        Component hover = Text.mm(t.wrap(def.name()) + "\n<gray>" + String.join("\n<gray>", def.description()));
        Component msg = Text.mm("<#ffcc55>✦ <white>" + p.getName() + "<gray>님이 " + t.label() + " <white>")
                .append(Text.mm("<u>" + def.name() + "</u>").hoverEvent(HoverEvent.showText(hover)))
                .append(Text.mm(" <gray>증강을 얻었습니다!"));
        Bukkit.broadcast(msg);
    }

    // ------------------------------------------------------------------ 선택지

    /** 아직 최대 중첩에 닿지 않은 증강 중에서 겹치지 않게 count 개를 뽑는다. */
    public List<String> roll(Player p, Tier tier, int count, Collection<String> exclude) {
        PlayerData d = data(p);
        List<AugmentDef> pool = new ArrayList<>();
        for (AugmentDef def : registry.ofTier(tier)) {
            if (d.stacks(def.id()) >= def.maxStacks()) continue;
            if (exclude.contains(def.id())) continue;
            pool.add(def);
        }
        List<String> out = new ArrayList<>();
        ThreadLocalRandom r = ThreadLocalRandom.current();
        while (out.size() < count && !pool.isEmpty()) {
            int total = 0;
            for (AugmentDef def : pool) total += def.weight();
            int x = r.nextInt(total);
            for (int i = 0; i < pool.size(); i++) {
                x -= pool.get(i).weight();
                if (x < 0) {
                    out.add(pool.remove(i).id());
                    break;
                }
            }
        }
        return out;
    }

    public int choiceCount(Player p) {
        int base = plugin.getConfig().getInt("altar.choices", 3);
        return Math.min(5, base + (int) stats(p).get("extra_choice.amount"));
    }

    public boolean startOffer(Player p, Tier tier) {
        PlayerData d = data(p);
        List<String> options = roll(p, tier, choiceCount(p), List.of());
        if (options.isEmpty()) return false;
        d.offerTier = tier;
        d.offer.clear();
        d.offer.addAll(options);
        d.rerolls = plugin.getConfig().getInt("altar.rerolls", 1) + (int) stats(p).get("reroll_bonus.amount");
        store.save(d);
        return true;
    }

    public boolean reroll(Player p) {
        PlayerData d = data(p);
        if (!d.hasOffer() || d.rerolls <= 0) return false;
        // 지금 보이는 것들은 빼고 다시 뽑되, 남은 게 모자라면 다시 섞어서라도 채운다
        List<String> fresh = roll(p, d.offerTier, d.offer.size(), d.offer);
        if (fresh.size() < d.offer.size()) {
            List<String> more = roll(p, d.offerTier, d.offer.size() - fresh.size(), fresh);
            fresh.addAll(more);
        }
        if (fresh.isEmpty()) return false;
        d.offer.clear();
        d.offer.addAll(fresh);
        d.rerolls--;
        store.save(d);
        Fx.sound(p.getLocation(), "block.enchantment_table.use", 1f, 1.3f);
        return true;
    }

    public boolean pick(Player p, int index) {
        PlayerData d = data(p);
        if (!d.hasOffer() || index < 0 || index >= d.offer.size()) return false;
        String id = d.offer.get(index);
        d.clearOffer();
        store.save(d);
        return grant(p, id, true);
    }

    // ------------------------------------------------------------------ 비용

    public record Cost(int shards, int crystals, Map<Material, Integer> items) {
        public boolean free() {
            return shards <= 0 && crystals <= 0 && items.isEmpty();
        }
    }

    public Cost cost(Player p, Tier tier) {
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("altar.cost." + tier.name());
        if (c == null) return new Cost(0, 0, Map.of());
        int owned = data(p).owned(tier, registry);
        double discount = Math.min(0.6, stats(p).get("altar_discount.amount"));
        int shards = (int) Math.ceil((c.getInt("shards", 0) + c.getInt("shards-per-owned", 0) * owned) * (1 - discount));
        int crystals = c.getInt("crystals", 0) + c.getInt("crystals-per-owned", 0) * owned;
        if (discount >= 0.3 && crystals > 1) crystals -= 1;
        Map<Material, Integer> items = new LinkedHashMap<>();
        ConfigurationSection it = c.getConfigurationSection("items");
        if (it != null) {
            for (String k : it.getKeys(false)) {
                Material m = Material.matchMaterial(k);
                if (m == null) continue;
                int n = (int) Math.ceil(it.getInt(k) * (1 - discount));
                if (n > 0) items.put(m, n);
            }
        }
        return new Cost(shards, crystals, items);
    }

    public boolean canPay(Player p, Cost cost) {
        if (Items.count(p, it -> "shard".equals(Items.tag(it, Keys.ITEM))) < cost.shards()) return false;
        if (Items.count(p, it -> "prism_crystal".equals(Items.tag(it, Keys.ITEM))) < cost.crystals()) return false;
        for (Map.Entry<Material, Integer> en : cost.items().entrySet()) {
            Material m = en.getKey();
            if (Items.count(p, it -> it.getType() == m && !Items.isCustom(it)) < en.getValue()) return false;
        }
        return true;
    }

    public boolean pay(Player p, Cost cost) {
        if (!canPay(p, cost)) return false;
        Items.take(p, it -> "shard".equals(Items.tag(it, Keys.ITEM)), cost.shards());
        Items.take(p, it -> "prism_crystal".equals(Items.tag(it, Keys.ITEM)), cost.crystals());
        for (Map.Entry<Material, Integer> en : cost.items().entrySet()) {
            Material m = en.getKey();
            Items.take(p, it -> it.getType() == m && !Items.isCustom(it), en.getValue());
        }
        return true;
    }

    public static String ticketId(Tier t) {
        return "ticket_" + t.name().toLowerCase();
    }

    public boolean hasTicket(Player p, Tier t) {
        String id = ticketId(t);
        return Items.count(p, it -> id.equals(Items.tag(it, Keys.ITEM))) > 0;
    }

    public boolean useTicket(Player p, Tier t) {
        String id = ticketId(t);
        return Items.take(p, it -> id.equals(Items.tag(it, Keys.ITEM)), 1);
    }
}
