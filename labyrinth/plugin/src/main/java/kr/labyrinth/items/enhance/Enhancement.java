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
 * 장비별 재료(content/enhance.yml)는 규칙이 아니라 콘텐츠({@link Content#enhance()})에 있다 — 툴팁은 넘겨받은 콘텐츠로 그린다.
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

    /** 툴팁 한 줄 최대 폭(px, TooltipFitTest 기준 330 보다 조금 좁게). */
    static final int LINE_PX = 322;

    /**
     * 툴팁 강화 줄 (스탯 바로 아래, 최대 2줄):
     * <ol>
     *   <li>현재 단계 · 배율 → 다음 단계 배율 (상승폭이 보이게) · 하락 경고</li>
     *   <li>다음 단계 확률 · 골드(할인 전) · 강화석 · 그 장비의 첫 재료 (나머지는 "…" — 전체는 강화 창에서)</li>
     * </ol>
     * 줄이 넓으면 덜 중요한 말부터 줄인다. 강화할 수 없는 장비거나 강화가 꺼져 있으면 빈 목록.
     */
    public static List<String> tooltip(Content content, ItemDef def, int level) {
        EnhanceRules r = rules;
        List<String> out = new ArrayList<>();
        if (!r.config().enabled() || !EnhanceRules.enhanceable(def)) return out;
        int max = r.maxLevel();
        String stat = scaledText(def);
        if (level >= max) {
            out.add("<gradient:#ff8a3d:#ffd36b:#fff4d6>⚒ 강화 +" + level + " (최대)</gradient> <dark_gray>· " + stat
                    + " ×" + ItemTooltip.trim(r.multiplier(level)));
            return out;
        }
        int target = level + 1;
        String now = ItemTooltip.trim(r.multiplier(level));
        String next = ItemTooltip.trim(r.multiplier(target));
        String head = level > 0
                ? (r.shines(level) ? "<#ffd36b>⚒ 강화 +" + level + "</#ffd36b>" : "<#e8d9b0>⚒ 강화 +" + level + "</#e8d9b0>")
                : "<#c8b48a>⚒ 강화 +0</#c8b48a>";
        String gain = level > 0 ? " · " + stat + " ×" + now + " → <gray>×" + next + "</gray>" : " · " + stat + " → <gray>×" + next + "</gray>";
        // 하락 경고는 첫 줄 끝에, 보호 주문서 안내는 강화 창에 (툴팁 줄 수 — ItemTooltip.MAX_LINES)
        String warn = r.downgradesOnFail(level) ? " <#ff8a8a>⚠ 실패 시 +" + (level - 1) + ro(level - 1) + " 하락" : "";
        String warnShort = r.downgradesOnFail(level) ? " <#ff8a8a>⚠ 실패 시 +" + (level - 1) : "";
        String tail = level == 0 ? " — 대장장이 두르간" : "";
        out.add(fit(head + " <dark_gray>/ +" + max + gain + warn + tail,
                head + " <dark_gray>/ +" + max + gain + warn,
                head + " <dark_gray>" + gain.substring(1) + warn,
                head + " <dark_gray>" + gain.substring(1) + warnShort));

        EnhanceCost cost = r.cost(def, target, 0, content == null ? null : content.enhance());
        String chance = "<gray>" + EnhanceRules.pct(r.chance(target)) + "</gray>";
        String gold = "<gray>" + kr.labyrinth.core.Text.num(cost.gold()) + "G</gray>";
        EnhanceCost.Line st = cost.stone();
        String stone = st == null ? "" : " · " + itemName(content, st.item()) + " <gray>×" + st.amount() + "</gray>";
        String stoneShort = st == null ? "" : " · 강화석 <gray>×" + st.amount() + "</gray>";
        List<EnhanceCost.Line> mats = cost.materials();
        String mat = mats.isEmpty() ? "" : " · " + itemName(content, mats.get(0).item()) + " <gray>×" + mats.get(0).amount() + "</gray>";
        String more = mats.size() > 1 ? " …" : "";
        String moreAll = mats.isEmpty() ? "" : " …";
        String pre = "<dark_gray>다음 +" + target + ": ";
        String preShort = "<dark_gray>+" + target + ": ";
        out.add(fit(pre + chance + " · " + gold + stone + mat + more,
                pre + chance + " · " + gold + stoneShort + mat + more,
                preShort + chance + " · " + gold + stoneShort + mat + more,
                preShort + chance + " · " + gold + stoneShort + moreAll));
        return out;
    }

    /** 숫자 뒤 '(으)로' — 숫자를 읽은 마지막 글자 받침 기준 (+6으로 · +7로 · +10으로). */
    static String ro(int n) {
        int d = Math.abs(n) % 10;
        // 영·십·삼·육 = ㄹ 아닌 받침 → 으로, 일·칠·팔 = ㄹ 받침 · 이·사·오·구 = 받침 없음 → 로
        return d == 0 || d == 3 || d == 6 ? "으로" : "로";
    }

    private static String itemName(Content content, String id) {
        ItemDef d = content == null ? null : content.item(id);
        return d == null ? id : d.name();
    }

    /** 폭 안에 드는 첫 후보 (모두 넓으면 마지막). */
    static String fit(String... candidates) {
        for (String c : candidates) if (px(c) <= LINE_PX) return c;
        return candidates[candidates.length - 1];
    }

    /** 대략적인 픽셀 폭 (MiniMessage 태그 제외): 한글 9 · 영문·숫자 6 · 공백 4 · 기호 8. */
    static int px(String mm) {
        String t = mm.replaceAll("<key:[^>]+>", "\u0001").replaceAll("<[^>]+>", "");
        int w = 0;
        for (char ch : t.toCharArray()) {
            if (ch == '\u0001') w += 60;
            else if (ch == ' ') w += 4;
            else if (ch >= 0xAC00 && ch <= 0xD7A3) w += 9;
            else if (ch < 128) w += 6;
            else w += 8;
        }
        return w;
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
