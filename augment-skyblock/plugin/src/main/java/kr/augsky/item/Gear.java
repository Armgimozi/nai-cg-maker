package kr.augsky.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.Repairable;
import io.papermc.paper.registry.RegistryKey;
import io.papermc.paper.registry.set.RegistrySet;
import kr.augsky.Keys;
import kr.augsky.util.Items;
import org.bukkit.Material;
import org.bukkit.Tag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.ItemType;
import org.bukkit.inventory.meta.Damageable;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 장비(무기·활·곡괭이·커스텀 갑옷)의 내구도와 수리 재료.
 * 예전에는 모두 부서지지 않았는데, 내구도를 쓰게 되면서 무기와 갑옷이 같이 쓰는 규칙을 여기에 모았다.
 */
public final class Gear {
    /** 장비 아이템 형식의 판. 지문에 들어가므로 올리면 이미 있는 아이템을 refresh 가 한 번씩 다시 쓴다 (2: 내구도). */
    public static final int FORMAT = 2;

    private Gear() {}

    /**
     * 수리 재료. 바닐라 재료 목록이나 커스텀 재료 하나("item:id").
     * 모루의 수리 계산(한 개에 25%, 경험치)은 바닐라 repairable 컴포넌트에 맡기고,
     * 같은 껍데기의 다른 아이템(아무 메아리 조각, 증강 파편 등)이 끼지 않게 ItemGuard 가 matches 로 한 번 더 본다.
     */
    public record Repair(String spec, List<Material> mats, String item) {
        public static Repair parse(String spec) {
            if (spec == null || spec.isBlank()) return null;
            String s = spec.trim();
            if (s.startsWith("item:")) return new Repair(s, List.of(), s.substring(5));
            List<Material> mats = new ArrayList<>();
            for (String part : s.split(",")) {
                String p = part.trim();
                if (p.equalsIgnoreCase("PLANKS") || p.equalsIgnoreCase("#planks")) {
                    for (Material m : Tag.PLANKS.getValues()) if (m.isItem()) mats.add(m);
                    continue;
                }
                Material m = Material.matchMaterial(p);
                if (m != null && m.isItem()) mats.add(m);
            }
            return mats.isEmpty() ? null : new Repair(s, List.copyOf(mats), null);
        }

        public boolean matches(ItemStack it) {
            if (it == null || it.isEmpty()) return false;
            if (item != null) return item.equals(Items.tag(it, Keys.ITEM));
            return !Items.isCustom(it) && mats.contains(it.getType());
        }

        /** 바닐라 repairable 에 넣을 아이템 종류 (커스텀 재료는 그 껍데기). */
        public List<Material> types(CustomItems items) {
            if (item == null) return mats;
            CustomItems.Def d = items.def(item);
            return d == null ? List.of() : List.of(d.material());
        }

        /** 설명에 보일 재료 이름 (MiniMessage). 바닐라 재료는 클라이언트 언어로 보인다. */
        public String label(CustomItems items) {
            if (item != null) {
                CustomItems.Def d = items.def(item);
                return d == null ? item : d.name();
            }
            if (mats.size() > 1 && Tag.PLANKS.isTagged(mats.get(0))) return "<white>판자";
            List<String> names = new ArrayList<>();
            for (Material m : mats) names.add("<lang:" + m.translationKey() + ">");
            return "<white>" + String.join("<gray>/<white>", names);
        }
    }

    /** 장비 종류 id: 무기·곡괭이는 "w:<id>", 갑옷은 "a:<세트>:<부위>". 장비가 아니면 null. 모루·숫돌에서 '같은 아이템'인지 볼 때 쓴다. */
    public static String id(ItemStack it) {
        String w = Items.tag(it, Keys.WEAPON);
        if (w != null) return "w:" + w;
        String a = Items.tag(it, Keys.ARMOR);
        if (a != null) return "a:" + a + ":" + Items.tag(it, Keys.ARMOR_SLOT);
        return null;
    }

    /** 무기 기본 내구도: 얻는 곳(pool)으로 바닐라 도구에 맞춘다 (초반 ≈ 철, 균열 = 다이아몬드, 보스 = 네더라이트). */
    public static int weaponDurability(String pool, String type, double speed, int fromYml) {
        if (fromYml > 0) return fromYml;
        int base = switch (pool) {
            case "basic" -> 250;
            case "island" -> 750;
            case "frost", "flame", "void" -> 1561;
            case "boss" -> 2031;
            case "prism" -> 3000;
            default -> 750;
        };
        if (type.equals("bow")) return Math.max(base, 384); // 바닐라 활
        if (type.equals("pickaxe")) return base;
        // 빠른 무기(단검·카타나)는 같은 적을 잡는 데 더 많이 휘두르므로 그만큼 늘린다
        double k = Math.max(1.0, Math.min(1.4, speed / 1.6));
        return (int) Math.round(base * k);
    }

    /** 무기 기본 수리 재료: 섬 무기는 속성(재질)의 재료, 균열은 그 정수, 보스는 다이아몬드, 프리즘은 결정. */
    public static String weaponRepair(String pool, String element, String fromYml) {
        if (fromYml != null && !fromYml.isBlank()) return fromYml;
        return switch (pool) {
            case "frost", "flame", "void" -> "item:essence_" + pool;
            case "boss" -> "DIAMOND";
            case "prism" -> "item:prism_crystal";
            default -> switch (element.toLowerCase(Locale.ROOT)) {
                case "stone" -> "COBBLESTONE";
                case "wood" -> "PLANKS";
                case "bone" -> "BONE";
                case "copper" -> "COPPER_INGOT";
                case "gold", "holy" -> "GOLD_INGOT";
                case "crystal" -> "AMETHYST_SHARD";
                case "nature" -> "VINE";
                case "storm" -> "LIGHTNING_ROD";
                case "venom" -> "SPIDER_EYE";
                // 프리즈머린 수정은 다시 얻을 수 없는 재료라 산호초에서 기르는 다시마로
                case "ocean" -> "DRIED_KELP_BLOCK";
                case "earth" -> "MOSSY_COBBLESTONE";
                case "wind" -> "PHANTOM_MEMBRANE";
                case "blood" -> "REDSTONE";
                case "star" -> "END_ROD";
                default -> "IRON_INGOT";
            };
        };
    }

    /**
     * 스킬 한 번에 깎이는 내구도: 실제 재사용 대기(스킬 가속 반영) 2초에 1, 최소 1.
     * 한 번에 최대 내구도의 1% (최대 30) 를 넘지 않게 해서 초반 지팡이가 회복 몇 번에 닳지 않게 한다.
     */
    public static int skillCost(double cooldownSec, int maxDurability) {
        int cap = Math.max(1, Math.min(30, maxDurability / 100));
        return Math.max(1, Math.min(cap, (int) Math.round(cooldownSec / 2)));
    }

    public static String loreLine(int max, Repair r, CustomItems items) {
        return "<white>🔧 내구도 <#9ad8ff>" + max + (r == null ? "" : " <dark_gray>· <gray>수리 재료 " + r.label(items));
    }

    /**
     * 내구도를 쓴다. 예전 형식(부서지지 않음)이었으면 꽉 찬 상태로 바꾼다.
     * 최대치가 줄어도 아이템이 사라지지 않게 남은 내구도를 1 이상으로 둔다. 예전 형식이었으면 true.
     */
    public static boolean applyDurability(ItemMeta meta, int max) {
        boolean old = meta.isUnbreakable();
        if (old) meta.setUnbreakable(false);
        if (meta instanceof Damageable dm) {
            dm.setMaxDamage(max);
            if (old) dm.setDamage(0);
            else if (dm.getDamage() >= max) dm.setDamage(max - 1);
        }
        meta.removeItemFlags(org.bukkit.inventory.ItemFlag.HIDE_UNBREAKABLE);
        return old;
    }

    /** 바닐라 repairable 을 이 재료로 바꾼다 (껍데기 기본값인 네더라이트 주괴 등을 없앤다). setItemMeta 다음에 불러야 한다. */
    public static void applyRepairable(ItemStack it, Repair r, CustomItems items) {
        List<ItemType> types = new ArrayList<>();
        if (r != null) for (Material m : r.types(items)) {
            ItemType t = m.asItemType();
            if (t != null) types.add(t);
        }
        it.setData(DataComponentTypes.REPAIRABLE, Repairable.repairable(RegistrySet.keySetFromValues(RegistryKey.ITEM, types)));
    }
}
