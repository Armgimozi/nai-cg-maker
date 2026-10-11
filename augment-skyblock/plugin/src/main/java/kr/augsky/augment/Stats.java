package kr.augsky.augment;

import kr.augsky.skill.HitEffects;
import kr.augsky.util.P;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.potion.PotionEffectType;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 플레이어가 가진 증강을 모두 합친 수치.
 * 효과 {type: lifesteal, amount: 0.05} 는 "lifesteal.amount" 에 (수치 × 중첩 수) 로 더해진다.
 * 이름이 cooldown/interval 인 값은 가장 작은 값을, threshold/radius/tier/multiplier/power/max 는 가장 큰 값을 쓴다.
 *
 * 전투 효과(공격 시 효과, 회피, 치명타)는 확률이 아니라 'N번째 공격마다' 터진다.
 * {every: 5} 는 비율 1/5 로 바꿔 "종류.chance" 에 더하고(예전 chance 표기도 그대로 비율로 읽는다),
 * 쓸 때 {@link #every(double)} 로 다시 N 으로 바꾼다. 비율로 더해 두어야 증강과 갑옷 세트처럼
 * 여러 곳에서 같은 효과를 얻을 때 자연스럽게 합쳐진다. 예) 5번마다 + 4번마다 → 비율 0.45 → 2번마다.
 */
public final class Stats {
    public record AttrMod(Attribute attribute, AttributeModifier.Operation op, double amount) {}
    public record Potion(PotionEffectType type, int amplifier) {}
    /** chance 는 확률이 아니라 비율(1/N). 실제로는 {@link #every()} 번째 공격마다 건다. */
    public record HitPotion(PotionEffectType type, double chance, int ticks, int amplifier) {
        public int every() {
            return Stats.every(chance);
        }
    }

    private final Map<String, Double> values = new HashMap<>();
    private final Set<String> types = new HashSet<>();
    public final List<AttrMod> attributes = new ArrayList<>();
    public final List<Potion> potions = new ArrayList<>();
    public final List<HitPotion> hitPotions = new ArrayList<>();

    public static final Stats EMPTY = new Stats();

    public double get(String key) {
        return values.getOrDefault(key, 0.0);
    }

    public double get(String key, double def) {
        return values.getOrDefault(key, def);
    }

    public boolean has(String type) {
        return types.contains(type);
    }

    /**
     * 비율을 'N번째마다' 의 N 으로 바꾼다. 0.2 → 5, 0.15 → 7, 1 이상 → 1(매번), 0 이하 → 0(없음).
     * 무기 패시브(weapons.yml 의 chance)도 같은 규칙을 쓴다.
     */
    public static int every(double rate) {
        if (!(rate > 0)) return 0;
        return (int) Math.max(1, Math.round(1 / rate));
    }

    /** 전투 효과 type 이 몇 번째 공격마다 터지는지. cap 은 비율 상한 (회피 0.5 → 적어도 2번에 한 번). */
    public int every(String type, double cap) {
        return every(Math.min(cap, get(type + ".chance")));
    }

    public static Stats compute(Map<String, Integer> owned, AugmentRegistry reg) {
        return compute(owned, reg, List.of());
    }

    /** extra: 갑옷 세트 효과처럼 증강이 아닌 곳에서 오는 효과 (한 번씩 더한다). */
    public static Stats compute(Map<String, Integer> owned, AugmentRegistry reg, List<AugmentDef.Effect> extra) {
        Stats st = new Stats();
        for (AugmentDef.Effect ef : extra) st.add(ef, 1);
        for (Map.Entry<String, Integer> en : owned.entrySet()) {
            AugmentDef def = reg.get(en.getKey());
            if (def == null) continue;
            int stacks = Math.max(1, en.getValue());
            for (AugmentDef.Effect ef : def.effects()) st.add(ef, stacks);
        }
        return st;
    }

    private void add(AugmentDef.Effect ef, int stacks) {
        String type = ef.type();
        P p = ef.p();
        switch (type) {
            case "attribute" -> {
                Attribute a = attribute(p.s("attribute", "max_health"));
                if (a == null) return;
                AttributeModifier.Operation op = operation(p.s("operation", "add"));
                attributes.add(new AttrMod(a, op, p.d("amount", 0) * stacks));
                types.add(type);
            }
            case "potion" -> {
                PotionEffectType t = HitEffects.potion(p.s("effect", "night_vision"));
                if (t != null) potions.add(new Potion(t, p.i("amplifier", 0)));
                types.add(type);
            }
            case "hit_potion" -> {
                PotionEffectType t = HitEffects.potion(p.s("effect", "slowness"));
                if (t != null) hitPotions.add(new HitPotion(t, rate(p, 0.2) * stacks,
                        (int) (p.d("seconds", 3) * 20), p.i("amplifier", 0)));
                types.add(type);
            }
            case "grant_random", "grant_item" -> {
                // 획득 순간에만 적용되는 효과
            }
            default -> {
                types.add(type);
                for (Map.Entry<String, Object> e : p.m.entrySet()) {
                    if (e.getKey().equals("type")) continue;
                    if (!(e.getValue() instanceof Number n)) continue;
                    // every: N 은 비율 1/N 으로 chance 에 더한다 (위 설명). 둘 다 적혀 있으면 every 를 따른다
                    if (e.getKey().equals("every")) {
                        merge(type + ".chance", rate(p, 0), stacks);
                        continue;
                    }
                    if (e.getKey().equals("chance") && p.has("every")) continue;
                    merge(type + "." + e.getKey(), n.doubleValue(), stacks);
                }
            }
        }
    }

    /** {every: N} 이면 1/N, 아니면 chance 그대로. */
    private static double rate(P p, double def) {
        if (p.has("every")) return 1.0 / Math.max(1, p.d("every", 1));
        return p.d("chance", def);
    }

    private void merge(String key, double val, int stacks) {
        String leaf = key.substring(key.lastIndexOf('.') + 1);
        switch (leaf) {
            case "cooldown", "interval" -> values.merge(key, val, Math::min);
            case "threshold", "multiplier", "radius", "tier", "power", "max", "seconds", "amplifier", "heal" ->
                    values.merge(key, val, Math::max);
            default -> values.merge(key, val * stacks, Double::sum);
        }
    }

    public static Attribute attribute(String name) {
        String k = name.toLowerCase(Locale.ROOT).replace("minecraft:", "").replace("generic.", "").replace("player.", "");
        return Registry.ATTRIBUTE.get(NamespacedKey.minecraft(k));
    }

    public static AttributeModifier.Operation operation(String s) {
        return switch (s.toLowerCase(Locale.ROOT)) {
            case "multiply_base", "add_multiplied_base", "percent", "base" -> AttributeModifier.Operation.ADD_SCALAR;
            case "multiply", "multiply_total", "add_multiplied_total", "total" -> AttributeModifier.Operation.MULTIPLY_SCALAR_1;
            default -> AttributeModifier.Operation.ADD_NUMBER;
        };
    }
}
