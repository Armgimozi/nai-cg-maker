package kr.labyrinth.items.crafting;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.CraftingService;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.mine.MineNames;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Menu;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 제련소 창 (0.3.6 — recipes.yml {@code station: smelter}). 구역 제련공 이그나 · interact smelter · 광산 관리소가 연다. 레벨 조건 없음.
 * <ul>
 *   <li>제련: 광석 ×2 + 골드 → 주괴. 클릭 ×1 · 우클릭 ×8 · 쉬프트 클릭 = 가진 만큼 전부</li>
 *   <li>새기기: 보석 + 미궁 정수 + 골드 → 강화석 2개 (클릭 ×1 · 우클릭 ×8 · 쉬프트 전부)</li>
 *   <li>곡괭이: 앞 곡괭이 + 주괴 + 보석 + 정수 + 골드 → 다음 곡괭이 (앞 곡괭이는 재료로 사라진다)</li>
 * </ul>
 * 제련소 레시피는 제작 할인이 없다 (녹여 팔아 남는 일이 없게).
 */
public final class SmelterMenu extends Menu {

    enum Tab {
        SMELT("smelt", "제련", "<gray>광석 2개를 녹여 주괴 1개"),
        CARVE("carve", "새기기", "<gray>보석 + 미궁 정수 → 강화석 2개"),
        TOOL("pickaxe", "곡괭이", "<gray>쓰던 곡괭이를 더 좋은 금속으로");

        final String key;
        final String label;
        final String hint;

        Tab(String key, String label, String hint) {
            this.key = key;
            this.label = label;
            this.hint = hint;
        }

        /** glyphs.yml menus.smelter tab_order 이름 (smelt·carve·pickaxe, forge·tool 도 곡괭이) → 탭. 모르면 제련. */
        static Tab of(String key) {
            if (key == null) return SMELT;
            String k = key.trim().toLowerCase(java.util.Locale.ROOT);
            if (k.equals("forge") || k.equals("tool")) return TOOL;
            for (Tab t : values()) if (t.key.equals(k)) return t;
            return SMELT;
        }
    }

    /** glyphs.yml menus.smelter 칸: 돌아가기 0 · 탭 2·4·6 · 지갑 8 · 레시피 행 1~4 × 열 1~7 · 이전 45 · ×1·×8·전부 48·49·50 · 다음 53. */
    private static final int[] TAB_SLOTS = {2, 4, 6};
    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};
    private static final int PER_PAGE = GRID.length;

    private final Services services;
    private final LabCraftingService crafting;
    private Tab tab = Tab.SMELT;
    private int page;

    SmelterMenu(Services services, LabCraftingService crafting) { this(services, crafting, Tab.SMELT); }

    SmelterMenu(Services services, LabCraftingService crafting, Tab tab) {
        super(6, kr.labyrinth.ui.UiTheme.title("smelter", 6, "<#ff9a5a>제련소"));
        this.services = services;
        this.crafting = crafting;
        this.tab = tab == null ? Tab.SMELT : tab;
    }

    /** 레시피가 어느 탭인가 (제련소 레시피가 아니면 null). */
    static Tab tabOf(RecipeDef r, ItemDef result) {
        if (!MineNames.STATION_SMELTER.equals(LabCraftingService.station(r))) return null;
        if (MineNames.CATEGORY_TOOL.equals(r.category()) || (result != null && result.isTool())) return Tab.TOOL;
        if (result != null && result.mineKind() == MineKind.INGOT) return Tab.SMELT;
        return Tab.CARVE;
    }

    private List<RecipeDef> recipes(Tab t) {
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : services.content().recipes().values()) {
            ItemDef def = services.content().item(r.result());
            if (def != null && tabOf(r, def) == t) out.add(r);
        }
        out.sort(Comparator.comparingInt((RecipeDef r) -> rank(services.content().item(r.result()))).thenComparing(RecipeDef::id));
        return out;
    }

    /** 순서 = 광물 등급 · 곡괭이 tier · 희귀도 (화면에 숫자로 쓰지 않음). */
    private static int rank(ItemDef d) {
        if (d.isTool()) return d.tool().tier() * 10;
        if (d.mineLevel() > 0) return d.mineLevel() * 10;
        return d.rarity().ordinal() * 10;
    }

    @Override
    protected void build(Player viewer) {
        PlayerData d = services.data().get(viewer);
        Tab[] tabs = Tab.values();
        for (int i = 0; i < tabs.length; i++) {
            Tab t = tabs[i];
            boolean sel = t == tab;
            List<RecipeDef> list = recipes(t);
            String model = list.isEmpty() ? null : list.get(0).result();
            set(TAB_SLOTS[i], Button.icon(Material.PAPER, model, (sel ? "<#ffd27a><b>▶ " : "<gray>") + t.label,
                    List.of(t.hint, sel ? "<#ffd27a>선택됨" : "<dark_gray>클릭하여 보기")), ctx -> {
                tab = t;
                page = 0;
                click(viewer);
                refresh();
            });
        }

        List<RecipeDef> list = recipes(tab);
        int pages = Math.max(1, (list.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        int g = 0;
        for (int i = page * PER_PAGE; i < list.size() && g < GRID.length; i++) {
            RecipeDef r = list.get(i);
            set(GRID[g++], recipeIcon(viewer, d, r), ctx -> {
                int times = tab == Tab.TOOL ? 1 : ctx.isShift() ? Integer.MAX_VALUE : ctx.isRight() ? 8 : 1;
                int[] res = crafting.craftMany(viewer, r.id(), times);
                if (res[0] == 0) {
                    Text.error(viewer, LabCraftingService.message(CraftingService.Result.values()[Math.max(0, res[1])]));
                    viewer.playSound(viewer.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
                }
                refresh();
            });
        }
        if (list.isEmpty()) deco(22, Button.icon(Material.BARRIER, "<gray>만들 수 있는 것이 없습니다", List.of()));

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
        deco(8, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(d.gold()),
                List.of("<gray>광석은 광산에서 캡니다.", "<gray>던전 몬스터·상자에서도 조금 나옵니다.")));
        if (tab == Tab.TOOL) {
            deco(49, Button.icon(Material.ANVIL, "<#ffd27a>클릭: 벼리기", List.of("<gray>쓰던 곡괭이는 재료로 사라집니다.")));
        } else {
            deco(48, Button.icon(Material.PAPER, "<#ffd27a>클릭 ×1", List.of("<gray>한 번 만듭니다.")));
            deco(49, Button.icon(Material.PAPER, "<#ffd27a>우클릭 ×8", List.of("<gray>여덟 번 만듭니다.")));
            deco(50, Button.icon(Material.PAPER, "<#ffd27a>쉬프트 클릭 전부", List.of("<gray>재료·골드가 있는 만큼 만듭니다.")));
        }
        set(0, Button.icon(Material.OAK_DOOR, "<gray>닫기", List.of()), ctx -> viewer.closeInventory());
    }

    private void click(Player p) { p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.2f); }

    private ItemStack recipeIcon(Player p, PlayerData d, RecipeDef r) {
        ItemDef def = services.content().item(r.result());
        List<String> tail = new ArrayList<>();
        tail.add("");
        tail.add("<#ff9a5a>━━ 재료 ━━");
        boolean ok = true;
        int most = Integer.MAX_VALUE;
        for (Map.Entry<String, Integer> m : r.materials().entrySet()) {
            ItemDef md = services.content().item(m.getKey());
            int have = crafting.count(p, m.getKey());
            boolean enough = have >= m.getValue();
            ok &= enough;
            most = Math.min(most, have / Math.max(1, m.getValue()));
            tail.add((enough ? "<#9be89b>✔ " : "<#ff6b6b>✘ ") + (md == null ? m.getKey() : md.name()) + " <gray>" + have + "/" + m.getValue());
        }
        long gold = crafting.goldCost(p, r);
        boolean goldOk = d.gold() >= gold;
        ok &= goldOk;
        if (gold > 0) most = (int) Math.min(most, d.gold() / gold);
        tail.add((goldOk ? "<#ffd27a>" : "<#ff6b6b>") + "골드 " + Text.num(gold));
        if (!ok) tail.add("<#ff6b6b>재료나 골드가 모자랍니다");
        else if (tab == Tab.TOOL) tail.add("<#ffd27a>▶ 클릭하여 벼리기");
        else tail.add("<#ffd27a>▶ 클릭 ×1 · 우클릭 ×8 · 쉬프트 전부 <dark_gray>(" + most + "번 가능)");
        List<String> lore = new ArrayList<>(ItemTooltip.lines(services.content(), def, null, Map.of(), List.of(), tail.size(), true,
                services.stats().requirementStats(p)));
        lore.addAll(tail);
        String name = "<" + def.rarity().color() + ">" + def.name() + (r.amount() > 1 ? " <gray>×" + r.amount() : "");
        return Button.icon(Material.PAPER, def.id(), name, lore);
    }
}
