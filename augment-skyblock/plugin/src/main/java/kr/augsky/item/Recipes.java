package kr.augsky.item;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.armor.ArmorService;
import kr.augsky.util.P;
import kr.augsky.weapon.WeaponDef;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.RecipeChoice;
import org.bukkit.inventory.ShapedRecipe;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** weapons.yml / items.yml 의 recipe 항목을 작업대 조합법으로 등록한다. */
public final class Recipes {
    private final AugSky plugin;
    private final List<NamespacedKey> keys = new ArrayList<>();
    /** 무기·갑옷을 껍데기 재료로만 받는 숨은 판. 레시피 책에는 넣지 않는다. */
    private final Set<NamespacedKey> hidden = new HashSet<>();
    /** 조합법 키 → 재료로 들어가야 하는 무기 id 목록 (무기 업그레이드용) */
    private final Map<NamespacedKey, List<String>> weaponInputs = new HashMap<>();
    /** 조합법 키 → 재료로 들어갈 수 있는 갑옷 세트들 (프리즘 갑옷처럼 다른 갑옷을 강화할 때) */
    private final Map<NamespacedKey, List<String>> armorInputs = new HashMap<>();

    /** 기본 갑옷 모양: M 주재료, S 특수 재료. */
    private static final Map<ArmorService.Slot, List<String>> ARMOR_SHAPES = Map.of(
            ArmorService.Slot.HELMET, List.of("MSM", "M M"),
            ArmorService.Slot.CHESTPLATE, List.of("M M", "MSM", "MMM"),
            ArmorService.Slot.LEGGINGS, List.of("MSM", "M M", "M M"),
            ArmorService.Slot.BOOTS, List.of("M M", "MSM"));

    public Recipes(AugSky plugin) {
        this.plugin = plugin;
    }

    public List<NamespacedKey> keys() {
        return keys;
    }

    public boolean isHidden(NamespacedKey k) {
        return hidden.contains(k);
    }

    public List<String> weaponInputs(NamespacedKey key) {
        return weaponInputs.get(key);
    }

    public List<String> armorInputs(NamespacedKey key) {
        return armorInputs.get(key);
    }

    public void registerAll() {
        for (NamespacedKey k : keys) Bukkit.removeRecipe(k);
        for (NamespacedKey k : hidden) Bukkit.removeRecipe(k);
        keys.clear();
        hidden.clear();
        weaponInputs.clear();
        armorInputs.clear();
        for (WeaponDef w : plugin.weapons().all().values()) {
            if (w.recipe() == null) continue;
            register("w_" + w.id(), plugin.weapons().create(w), w.recipe());
        }
        for (CustomItems.Def d : plugin.items().all().values()) {
            P r = d.raw().sub("recipe");
            if (r == null) continue;
            register("i_" + d.id(), plugin.items().create(d.id(), Math.max(1, r.i("amount", 1))), r);
        }
        for (ArmorService.SetDef a : plugin.armor().all().values()) {
            P r = a.recipe();
            if (r == null) continue;
            for (ArmorService.Slot sl : ArmorService.Slot.values()) {
                Map<String, Object> m = new java.util.LinkedHashMap<>();
                List<String> shape = r.has("shape") ? r.strings("shape") : ARMOR_SHAPES.get(sl);
                m.put("shape", shape);
                Map<String, Object> ing = new java.util.LinkedHashMap<>();
                for (Map.Entry<String, Object> en : r.m.entrySet()) {
                    if (en.getKey().equals("shape")) continue;
                    String v = String.valueOf(en.getValue());
                    // "armor:세트들" 은 같은 부위의 갑옷
                    ing.put(en.getKey(), v.startsWith("armor:") ? v + ":" + sl.id : v);
                }
                m.put("ingredients", ing);
                register("a_" + a.id() + "_" + sl.id, plugin.armor().create(a.id(), sl), new P(m));
            }
        }
        plugin.getLogger().info("조합법 " + keys.size() + "개 등록 (숨은 판 " + hidden.size() + "개)");
    }

    private void register(String keyName, ItemStack result, P r) {
        if (result == null) return;
        List<String> shape = r.strings("shape");
        P ing = r.sub("ingredients");
        if (shape.isEmpty() || ing == null) return;
        // 글자마다 레시피 책에 보일 재료(shown)와 숨은 판의 재료(loose). 무기·갑옷만 둘이 다르다
        Map<Character, RecipeChoice> shown = new LinkedHashMap<>();
        Map<Character, RecipeChoice> loose = new LinkedHashMap<>();
        List<String> wIn = new ArrayList<>();
        List<String> aIn = new ArrayList<>();
        for (Map.Entry<String, Object> en : ing.m.entrySet()) {
            char c = en.getKey().charAt(0);
            String spec = String.valueOf(en.getValue());
            if (spec.startsWith("armor:")) {
                // armor:세트1,세트2:부위
                String[] parts = spec.substring(6).split(":");
                ArmorService.Slot sl = parts.length > 1 ? ArmorService.Slot.parse(parts[1]) : null;
                if (sl == null) {
                    plugin.getLogger().warning("조합법 " + keyName + " 갑옷 재료의 부위를 알 수 없음: " + spec);
                    return;
                }
                List<ItemStack> real = new ArrayList<>();
                for (String set : parts[0].split(",")) {
                    aIn.add(set.trim() + ":" + sl.id);
                    ItemStack it = plugin.armor().create(set.trim(), sl);
                    if (it != null) real.add(it);
                }
                if (real.isEmpty()) {
                    plugin.getLogger().warning("조합법 " + keyName + " 재료 갑옷 세트가 없음: " + spec);
                    return;
                }
                shown.put(c, new RecipeChoice.ExactChoice(real));
                loose.put(c, new RecipeChoice.MaterialChoice(sl.shell));
            } else if (spec.startsWith("weapon:")) {
                WeaponDef w = plugin.weapons().get(spec.substring(7));
                if (w == null) {
                    plugin.getLogger().warning("조합법 " + keyName + " 재료 무기가 없음: " + spec);
                    return;
                }
                shown.put(c, new RecipeChoice.ExactChoice(plugin.weapons().create(w)));
                loose.put(c, new RecipeChoice.MaterialChoice(w.material()));
                long cnt = String.join("", shape).chars().filter(ch -> ch == c).count();
                for (int i = 0; i < cnt; i++) wIn.add(w.id());
            } else {
                RecipeChoice choice;
                if (spec.startsWith("item:") || plugin.items().def(spec) != null) {
                    String id = spec.startsWith("item:") ? spec.substring(5) : spec;
                    ItemStack it = plugin.items().create(id, 1);
                    if (it == null) {
                        plugin.getLogger().warning("조합법 " + keyName + " 재료 아이템이 없음: " + spec);
                        return;
                    }
                    choice = new RecipeChoice.ExactChoice(it);
                } else {
                    Material m = Material.matchMaterial(spec);
                    if (m == null) {
                        plugin.getLogger().warning("조합법 " + keyName + " 재료를 알 수 없음: " + spec);
                        return;
                    }
                    choice = new RecipeChoice.MaterialChoice(m);
                }
                shown.put(c, choice);
                loose.put(c, choice);
            }
        }
        NamespacedKey key = new NamespacedKey(Keys.NS, keyName);
        // 보이는 판을 먼저 넣어서, 둘 다 맞으면 보이는 판이 쓰이게 한다
        if (!Bukkit.addRecipe(shaped(key, result, shape, shown))) return;
        keys.add(key);
        if (!wIn.isEmpty()) weaponInputs.put(key, wIn);
        if (!aIn.isEmpty()) armorInputs.put(key, aIn);
        if (wIn.isEmpty() && aIn.isEmpty()) return;
        // 레시피 책엔 진짜 무기 모양으로 보이게 하고, 이름 바꾼 무기는 숨은 판으로 받는다
        // (정확한 아이템 재료는 이름·마법 부여가 하나라도 다르면 맞지 않는다. 어떤 무기인지는 ItemGuard 가 태그로 본다)
        NamespacedKey any = new NamespacedKey(Keys.NS, keyName + "_any");
        if (Bukkit.addRecipe(shaped(any, result, shape, loose))) {
            hidden.add(any);
            if (!wIn.isEmpty()) weaponInputs.put(any, wIn);
            if (!aIn.isEmpty()) armorInputs.put(any, aIn);
        } else {
            plugin.getLogger().warning("조합법 " + keyName + " 의 숨은 판을 등록하지 못함 (이름 바꾼 무기·갑옷으로는 만들 수 없다)");
        }
    }

    private static ShapedRecipe shaped(NamespacedKey key, ItemStack result, List<String> shape, Map<Character, RecipeChoice> choices) {
        ShapedRecipe recipe = new ShapedRecipe(key, result);
        recipe.shape(shape.toArray(new String[0]));
        for (Map.Entry<Character, RecipeChoice> en : choices.entrySet()) recipe.setIngredient(en.getKey(), en.getValue());
        return recipe;
    }
}
