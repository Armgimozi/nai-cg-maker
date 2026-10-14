package kr.labyrinth.items.enhance;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.items.ItemTooltip;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 강화 단계 PDC 코덱 + 현재 규칙 보관 (GDD §11.13). 아이템 코덱(GearItemService)·툴팁·장비 스탯이 여기서 단계를 읽는다.
 * <ul>
 *   <li>PDC {@code Keys.ITEM_ENHANCE} = Integer 0~max (없으면 0). 쓸 때 {@code ITEM_VERSION} 을 2 이상으로 올린다.</li>
 *   <li>규칙은 config.yml {@code enhance:} — ItemsModule enable/reload 때 {@link #configure} 로 교체.</li>
 * </ul>
 */
public final class Enhancement {

    /** 강화 단계 키가 생긴 아이템 데이터 버전. */
    public static final int ITEM_VERSION = 2;

    private static volatile EnhanceRules rules = new EnhanceRules(EnhanceRules.Config.DEFAULT);

    private Enhancement() {}

    public static EnhanceRules rules() { return rules; }

    /** config.yml {@code enhance:} 섹션을 다시 읽는다 (없으면 기본값). */
    public static void configure(ConfigurationSection section) {
        rules = new EnhanceRules(EnhanceRules.Config.from(section));
    }

    /** 아이템의 강화 단계 (미궁 장비가 아니거나 없으면 0). */
    public static int level(ItemStack stack) {
        if (stack == null || stack.isEmpty()) return 0;
        Integer v = stack.getPersistentDataContainer().get(Keys.ITEM_ENHANCE, PersistentDataType.INTEGER);
        return v == null ? 0 : Math.max(0, Math.min(rules.maxLevel(), v));
    }

    /** 강화 단계를 기록한다 (0 이면 키 제거). 이름·툴팁은 {@code GearItemService#render} 로 다시 그릴 것. */
    public static void setLevel(ItemStack stack, int level) {
        int lv = Math.max(0, Math.min(rules.maxLevel(), level));
        stack.editPersistentDataContainer(pdc -> {
            if (lv <= 0) pdc.remove(Keys.ITEM_ENHANCE);
            else pdc.set(Keys.ITEM_ENHANCE, PersistentDataType.INTEGER, lv);
            Integer ver = pdc.get(Keys.ITEM_VERSION, PersistentDataType.INTEGER);
            if (ver == null || ver < ITEM_VERSION) pdc.set(Keys.ITEM_VERSION, PersistentDataType.INTEGER, ITEM_VERSION);
        });
    }

    /**
     * 툴팁 강화 줄 (스탯 바로 아래): 현재 단계 / 다음 단계 확률·골드(할인 전)·강화석 / 하락 경고.
     * 강화할 수 없는 장비거나 강화가 꺼져 있으면 빈 목록.
     */
    public static List<String> tooltip(Content content, ItemDef def, int level) {
        EnhanceRules r = rules;
        List<String> out = new ArrayList<>();
        if (!r.config().enabled() || !EnhanceRules.enhanceable(def)) return out;
        int max = r.maxLevel();
        if (level >= max) {
            out.add("<gradient:#ff8a3d:#ffd36b:#fff4d6>⚒ 강화 +" + level + " (최대)</gradient> <dark_gray>· " + scaledText(def)
                    + " ×" + ItemTooltip.trim(r.multiplier(level)));
            return out;
        }
        String head = level > 0
                ? (r.shines(level) ? "<#ffd36b>⚒ 강화 +" + level + "</#ffd36b>" : "<#e8d9b0>⚒ 강화 +" + level + "</#e8d9b0>")
                        + " <dark_gray>/ +" + max + " · " + scaledText(def) + " ×" + ItemTooltip.trim(r.multiplier(level))
                : "<#c8b48a>⚒ 강화 +0</#c8b48a> <dark_gray>/ +" + max + " — 대장장이 두르간";
        out.add(head);
        int target = level + 1;
        String stone = r.stoneFor(def);
        ItemDef sd = stone == null ? null : content.item(stone);
        out.add("<dark_gray>다음 +" + target + ": <gray>" + EnhanceRules.pct(r.chance(target)) + "</gray> · 골드 <gray>"
                + kr.labyrinth.core.Text.num(r.baseGold(def, target)) + "</gray> · " + (sd == null ? stone : sd.name())
                + " <gray>×" + r.stoneCount(target));
        if (r.downgradesOnFail(level)) {
            out.add("<#ff8a8a>⚠ 실패하면 +" + (level - 1) + " 으로 내려감 <dark_gray>(보호 주문서로 막기)");
        }
        return out;
    }

    /** "피해" / "방어·HP" — 강화 배율이 곱해지는 스탯 이름. */
    static String scaledText(ItemDef def) {
        List<String> names = new ArrayList<>();
        for (String k : ItemTooltip.STAT_NAMES.keySet()) {
            if (rules.scaledKeys(def).contains(k) && def.stats().containsKey(k)) names.add(ItemTooltip.statName(k));
        }
        return names.isEmpty() ? "능력치" : String.join("·", names);
    }
}
