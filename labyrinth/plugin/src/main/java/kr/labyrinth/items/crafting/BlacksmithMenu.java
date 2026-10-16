package kr.labyrinth.items.crafting;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.CraftingService;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.items.WeaponFilter;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Glyphs;
import kr.labyrinth.ui.Menu;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 대장장이 두르간 GUI (GDD §11.11). 탭 = recipes.yml category(무기 · 방어구·방패 · 장신구 · 정수 정제),
 * 레시피마다 재료 보유/필요 · 골드 표시(부족하면 빨강), 클릭 = 제작. 제작 레벨 제한·직업 필터는 없다 — 장비의 요구 능력치는
 * 툴팁에 보는 사람 기준(맞춤 초록 / 모자람 빨강 "(현재 22)")으로 보여 주기만 하고 제작은 막지 않는다(입을 때 가린다).
 * 거르개 (0.3.5, 분류 이름 없음): 무기 = 방식·피해 종류, 방어구 = 겉모습, 둘 다 "지금 낄 수 있는 것만".
 * 목록 순서 = 숨은 내부 레벨 → 희귀도. 배너 가운데(13) = [장비 강화] → 강화 창 (GDD §11.13).
 * 0.3.6: {@code station: blacksmith} 레시피만 (제련·새기기·곡괭이 벼리기는 제련소 {@link SmelterMenu}).
 */
public final class BlacksmithMenu extends Menu {

    private static final String[] TABS = {"weapon", "armor", "accessory", "material"};
    private static final String[] TAB_NAMES = {"무기", "방어구 · 방패", "장신구", "정수 정제"};
    private static final int[] TAB_SLOTS = {1, 3, 5, 7};
    private static final int PER_PAGE = 27;
    /** 배너 가운데(모루) — 강화 창 버튼. */
    private static final int ENHANCE_SLOT = 13;

    /** 거르개 칸: 47 = 방식(무기) · 겉모습(방어구), 50 = 지금 낄 수 있는 것만. */
    private static final int FILTER_SLOT = 47, WEARABLE_SLOT = 50;
    private static final ArmorLook[] LOOKS = {null, ArmorLook.HEAVY, ArmorLook.LIGHT, ArmorLook.CLOTH, ArmorLook.PLAIN};

    private final Services services;
    private final LabCraftingService crafting;
    private int tab;
    private int page;
    private WeaponFilter weaponFilter = WeaponFilter.ALL;
    private int look;
    private boolean wearableOnly;

    BlacksmithMenu(Services services, LabCraftingService crafting, Player viewer) {
        super(6, kr.labyrinth.ui.UiTheme.title("blacksmith", 6, "<#f3e3bd>대장장이 두르간의 대장간"));
        this.services = services;
        this.crafting = crafting;
    }

    private List<RecipeDef> recipes(Map<Stat, Integer> reqStats) {
        String cat = TABS[tab];
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : services.content().recipes().values()) {
            if (!kr.labyrinth.mine.MineNames.STATION_BLACKSMITH.equals(LabCraftingService.station(r))) continue;
            if (!cat.equals(r.category() == null ? "weapon" : r.category())) continue;
            ItemDef def = services.content().item(r.result());
            if (def == null || !passes(def, reqStats)) continue;
            out.add(r);
        }
        // 결과 장비의 숨은 내부 레벨(items.yml level_req) → 희귀도 순 — 제작 레벨 제한은 없다
        out.sort(Comparator.comparingInt((RecipeDef r) -> services.content().item(r.result()).levelReq())
                .thenComparing(r -> services.content().item(r.result()).rarity().ordinal())
                .thenComparing(RecipeDef::id));
        return out;
    }

    private boolean passes(ItemDef def, Map<Stat, Integer> reqStats) {
        if (def.isWeapon() && !weaponFilter.test(def)) return false;
        if (def.type() == ItemType.ARMOR && LOOKS[look] != null && def.armorLook() != LOOKS[look]) return false;
        return !wearableOnly || !def.isGear() || def.requirement().met(reqStats);
    }

    @Override
    protected void build(Player viewer) {
        PlayerData d = services.data().get(viewer);
        Map<Stat, Integer> reqStats = services.stats().requirementStats(viewer);
        for (int i = 0; i < TABS.length; i++) {
            final int idx = i;
            boolean sel = i == tab;
            String model = firstResult(TABS[i]);
            ItemStack icon = Button.icon(Material.PAPER, model, (sel ? "<#ffd27a><b>▶ " : "<gray>") + TAB_NAMES[i],
                    List.of(sel ? "<#ffd27a>선택됨" : "<dark_gray>클릭하여 보기"));
            set(TAB_SLOTS[i], icon, ctx -> {
                tab = idx;
                page = 0;
                click(viewer);
                refresh();
            });
        }

        // [강화] — 배너의 모루 자리(glyphs.yml menus.blacksmith.slots.enhance)
        var enh = crafting.enhance();
        if (enh != null && enh.rules().config().enabled()) {
            ItemStack anvil = kr.labyrinth.ui.UiTheme.item(enh.rules().config().stones().isEmpty() ? null
                    : enh.rules().config().stones().get(0).item(), Material.ANVIL,
                    "<gradient:#ffd36b:#ff8a3d><b>⚒ 장비 강화</b></gradient>",
                    List.of("<gray>무기·방어구·방패를 +1 ~ +" + enh.rules().maxLevel() + " 까지 강화합니다.",
                            "<gray>골드 + 강화석 + 장비마다 다른 재료",
                            "<gray>+" + enh.rules().config().downgradeFrom() + " 이상에서 실패하면 한 단계 하락",
                            "", "<#ffd27a>▶ 클릭하여 강화 창 열기"));
            kr.labyrinth.ui.UiTheme.glint(anvil, true);
            set(ENHANCE_SLOT, anvil, ctx -> {
                click(viewer);
                enh.open(viewer);
            });
        }

        drawFilters(viewer);
        List<RecipeDef> list = recipes(reqStats);
        int pages = Math.max(1, (list.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        int start = page * PER_PAGE;
        int slot = 18; // 레시피 칸 = 18..44 (27칸)
        for (int i = start; i < list.size() && slot < 45; i++) {
            RecipeDef r = list.get(i);
            set(slot++, recipeIcon(viewer, d, reqStats, r), ctx -> {
                CraftingService.Result res = crafting.craft(viewer, r.id());
                if (res != CraftingService.Result.OK) {
                    Text.error(viewer, LabCraftingService.message(res));
                    viewer.playSound(viewer.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
                }
                refresh();
            });
        }
        if (list.isEmpty()) deco(31, Button.icon(Material.BARRIER, "<gray>제작할 수 있는 물건이 없습니다", List.of()));

        if (page > 0) set(45, Button.icon(Material.ARROW, "<white>이전 쪽", List.of("<gray>" + page + " / " + pages)), ctx -> {
            page--;
            click(viewer);
            refresh();
        });
        if (page < pages - 1) set(53, Button.icon(Material.ARROW, "<white>다음 쪽", List.of("<gray>" + (page + 2) + " / " + pages)), ctx -> {
            page++;
            click(viewer);
            refresh();
        });
        // 아래 줄 = 45 이전 · 47 거르개 · 49 골드·제작 안내 · 50 낄 수 있는 것만 · 51 닫기 · 53 다음
        double disc = services.stats().get(viewer).craftDiscount();
        deco(49, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(d.gold()),
                List.of(disc > 0 ? "<gray>제작 할인 " + Text.pct(Math.min(RecipeCheck.MAX_DISCOUNT, disc)) : "<gray>제작 레벨 제한 없음",
                        "<dark_gray>재료는 미궁의 몬스터·정예·보스에게서 얻습니다.",
                        "",
                        "<gray>레시피를 클릭하면 바로 제작합니다.",
                        "<gray>모자란 재료·골드는 <#ff6b6b>빨강</#ff6b6b>으로 표시됩니다.",
                        "<gray>요구 능력치는 입을 때 필요합니다 (제작은 언제나 가능).")));
        set(51, Button.icon(Material.OAK_DOOR, "<gray>닫기", List.of()), ctx -> viewer.closeInventory());
    }

    /** 무기 탭 = 방식 거르개, 방어구 탭 = 겉모습 거르개, 두 탭 모두 "지금 낄 수 있는 것만". */
    private void drawFilters(Player viewer) {
        String cat = TABS[tab];
        if (cat.equals("weapon")) {
            set(FILTER_SLOT, Button.icon(Material.HOPPER, "<gray>방식: <white>" + weaponFilter.label(),
                    List.of("<dark_gray>근접 · 원거리 · 시전 · 물리 피해 · 마법 피해", "<dark_gray>클릭: 다음 · 우클릭: 전체")), ctx -> {
                weaponFilter = ctx.isRight() ? WeaponFilter.ALL : weaponFilter.next();
                page = 0;
                click(viewer);
                refresh();
            });
        } else if (cat.equals("armor")) {
            ArmorLooks cfg = services.settings().armorLooks();
            ArmorLook l = LOOKS[look];
            set(FILTER_SLOT, Button.icon(Material.LEATHER_CHESTPLATE, "<gray>겉모습: " + (l == null ? "<white>전체" : "<" + cfg.color(l) + ">" + cfg.name(l)),
                    List.of("<dark_gray>판금 · 가죽 · 천 · 평상복", "<dark_gray>클릭: 다음 · 우클릭: 전체")), ctx -> {
                look = ctx.isRight() ? 0 : (look + 1) % LOOKS.length;
                page = 0;
                click(viewer);
                refresh();
            });
        }
        if (cat.equals("weapon") || cat.equals("armor")) {
            set(WEARABLE_SLOT, Button.icon(wearableOnly ? Material.LIME_DYE : Material.GRAY_DYE,
                    (wearableOnly ? "<#7fe07f>" : "<gray>") + "지금 낄 수 있는 것만: " + (wearableOnly ? "켜짐" : "꺼짐"),
                    List.of("<dark_gray>요구 능력치를 모두 채운 장비만", "<dark_gray>클릭: 켜기/끄기")), ctx -> {
                wearableOnly = !wearableOnly;
                page = 0;
                click(viewer);
                refresh();
            });
        }
    }

    private void click(Player p) { p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.2f); }

    /** 재료 줄 수 (주괴는 몇 개든 한 줄). */
    static int materialLines(int plain, int ingots) { return plain + (ingots > 0 ? 1 : 0); }

    /** 대장간 목록 툴팁 꼬리 줄 수 (빈 줄 · 제목(재료 줄 6 미만일 때) · 재료 줄 · 골드 · 제작 안내) — TooltipFitTest 가 쓴다. */
    public static int tailSize(kr.labyrinth.content.Content content, RecipeDef r) {
        int plain = 0, ingots = 0;
        for (String id : r.materials().keySet()) {
            ItemDef md = content.item(id);
            if (md != null && md.isMineMaterial()) ingots++;
            else plain++;
        }
        int lines = materialLines(plain, ingots);
        return 3 + lines + (lines < 6 ? 1 : 0);
    }

    private String firstResult(String cat) {
        for (RecipeDef r : services.content().recipes().values()) {
            if (cat.equals(r.category()) && kr.labyrinth.mine.MineNames.STATION_BLACKSMITH.equals(LabCraftingService.station(r))) return r.result();
        }
        return null;
    }

    private ItemStack recipeIcon(Player p, PlayerData d, Map<Stat, Integer> reqStats, RecipeDef r) {
        ItemDef def = services.content().item(r.result());
        List<String> tail = new ArrayList<>();
        tail.add("");
        List<Map.Entry<String, Integer>> plain = new ArrayList<>(), ingots = new ArrayList<>();
        for (Map.Entry<String, Integer> m : r.materials().entrySet()) {
            ItemDef md = services.content().item(m.getKey());
            (md != null && md.isMineMaterial() ? ingots : plain).add(m);
        }
        // 0.3.6: 주괴는 한 줄로 묶는다 · 재료 줄이 많으면 제목 줄을 뺀다 (툴팁이 화면 안에 들어가게 — tailSize)
        if (materialLines(plain.size(), ingots.size()) < 6) tail.add("<#e0a050>━━ 제작 재료 ━━");
        boolean ok = true;
        for (Map.Entry<String, Integer> m : plain) {
            ItemDef md = services.content().item(m.getKey());
            int have = crafting.count(p, m.getKey());
            boolean enough = have >= m.getValue();
            ok &= enough;
            tail.add((enough ? "<#9be89b>✔ " : "<#ff6b6b>✘ ") + (md == null ? m.getKey() : md.name()) + " <gray>"
                    + have + "/" + m.getValue());
        }
        if (!ingots.isEmpty()) {
            StringBuilder line = new StringBuilder();
            boolean all = true;
            for (Map.Entry<String, Integer> m : ingots) {
                ItemDef md = services.content().item(m.getKey());
                int have = crafting.count(p, m.getKey());
                boolean enough = have >= m.getValue();
                all &= enough;
                if (line.length() > 0) line.append(" <dark_gray>·</dark_gray> ");
                line.append(enough ? "<#9be89b>" : "<#ff6b6b>").append(md.name()).append(" <gray>").append(have).append("/").append(m.getValue());
            }
            ok &= all;
            tail.add((all ? "<#9be89b>✔ " : "<#ff6b6b>✘ ") + line);
        }
        long gold = crafting.goldCost(p, r);
        boolean goldOk = d.gold() >= gold;
        ok &= goldOk;
        tail.add((goldOk ? "<#ffd27a>" : "<#ff6b6b>") + "골드 " + Text.num(gold) + (gold < r.gold() ? " <dark_gray>(원가 " + Text.num(r.gold()) + ")" : ""));
        tail.add(ok ? "<#ffd27a>▶ 클릭하여 제작" + (r.amount() > 1 ? " (×" + r.amount() + ")" : "")
                : "<#ff6b6b>조건이 부족합니다");
        // 재료 줄만큼 자리를 비워 툴팁이 화면 안에 들어가게 (ItemTooltip.MAX_LINES)
        // 요구 능력치는 보는 사람 기준으로 (맞춤 초록 / 모자람 빨강) — 제작은 막지 않는다
        List<String> lore = new ArrayList<>(ItemTooltip.lines(services.content(), def, null, Map.of(), List.of(), tail.size(), true, reqStats));
        lore.addAll(tail);
        String name = "<" + def.rarity().color() + ">" + def.name() + (r.amount() > 1 ? " <gray>×" + r.amount() : "");
        Material base = def.isRanged() ? Material.BOW : Material.PAPER;
        return Button.icon(base, def.id(), name, lore);
    }
}
