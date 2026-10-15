package kr.labyrinth.items.crafting;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.CraftingService;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Glyphs;
import kr.labyrinth.ui.Menu;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 대장장이 두르간 GUI (GDD §11.11). 탭 = recipes.yml category(무기 · 방어구·방패 · 장신구 · 정수 정제),
 * 레시피마다 재료 보유/필요 · 골드 · 레벨 표시(부족하면 빨강), 클릭 = 제작. 직업 필터는 없다(장비는 어느 직업이든 쓸 수 있다).
 * 배너 가운데(13) = [장비 강화] → 강화 창 (GDD §11.13).
 */
final class BlacksmithMenu extends Menu {

    private static final String[] TABS = {"weapon", "armor", "accessory", "material"};
    private static final String[] TAB_NAMES = {"무기", "방어구 · 방패", "장신구", "정수 정제"};
    private static final int[] TAB_SLOTS = {1, 3, 5, 7};
    private static final int PER_PAGE = 27;
    /** 배너 가운데(모루) — 강화 창 버튼. */
    private static final int ENHANCE_SLOT = 13;

    private final Services services;
    private final LabCraftingService crafting;
    private int tab;
    private int page;

    BlacksmithMenu(Services services, LabCraftingService crafting, Player viewer) {
        super(6, kr.labyrinth.ui.UiTheme.title("blacksmith", 6, "<#f3e3bd>대장장이 두르간의 대장간"));
        this.services = services;
        this.crafting = crafting;
    }

    private List<RecipeDef> recipes() {
        String cat = TABS[tab];
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : services.content().recipes().values()) {
            if (!cat.equals(r.category() == null ? "weapon" : r.category())) continue;
            ItemDef def = services.content().item(r.result());
            if (def == null) continue;
            out.add(r);
        }
        out.sort(Comparator.comparingInt(RecipeDef::levelReq)
                .thenComparing(r -> services.content().item(r.result()).rarity().ordinal())
                .thenComparing(RecipeDef::id));
        return out;
    }

    @Override
    protected void build(Player viewer) {
        PlayerData d = services.data().get(viewer);
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
                            "<gray>골드 + 강화석 · +" + enh.rules().config().downgradeFrom() + " 이상 실패하면 한 단계 하락",
                            "", "<#ffd27a>▶ 클릭하여 강화 창 열기"));
            kr.labyrinth.ui.UiTheme.glint(anvil, true);
            set(ENHANCE_SLOT, anvil, ctx -> {
                click(viewer);
                enh.open(viewer);
            });
        }

        List<RecipeDef> list = recipes();
        int pages = Math.max(1, (list.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        int start = page * PER_PAGE;
        int slot = 18; // 레시피 칸 = 18..44 (27칸)
        for (int i = start; i < list.size() && slot < 45; i++) {
            RecipeDef r = list.get(i);
            set(slot++, recipeIcon(viewer, d, r), ctx -> {
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
        double disc = services.stats().get(viewer).craftDiscount();
        deco(49, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(d.gold()),
                List.of("<gray>레벨 " + d.level() + (disc > 0 ? " · 제작 할인 " + Text.pct(Math.min(RecipeCheck.MAX_DISCOUNT, disc)) : ""),
                        "<dark_gray>재료는 미궁의 몬스터·정예·보스에게서 얻습니다.")));
        set(51, Button.icon(Material.OAK_DOOR, "<gray>닫기", List.of()), ctx -> viewer.closeInventory());
    }

    private void click(Player p) { p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.2f); }

    private String firstResult(String cat) {
        for (RecipeDef r : services.content().recipes().values()) {
            if (cat.equals(r.category())) return r.result();
        }
        return null;
    }

    private ItemStack recipeIcon(Player p, PlayerData d, RecipeDef r) {
        ItemDef def = services.content().item(r.result());
        List<String> tail = new ArrayList<>();
        tail.add("");
        tail.add("<#e0a050>━━ 제작 재료 ━━");
        boolean ok = true;
        for (Map.Entry<String, Integer> m : r.materials().entrySet()) {
            ItemDef md = services.content().item(m.getKey());
            int have = crafting.count(p, m.getKey());
            boolean enough = have >= m.getValue();
            ok &= enough;
            tail.add((enough ? "<#9be89b>✔ " : "<#ff6b6b>✘ ") + (md == null ? m.getKey() : md.name()) + " <gray>"
                    + have + "/" + m.getValue());
        }
        long gold = crafting.goldCost(p, r);
        boolean goldOk = d.gold() >= gold;
        boolean lvOk = d.level() >= r.levelReq();
        ok &= goldOk && lvOk;
        tail.add((goldOk ? "<#ffd27a>" : "<#ff6b6b>") + "골드 " + Text.num(gold) + (gold < r.gold() ? " <dark_gray>(원가 " + Text.num(r.gold()) + ")" : "")
                + " <dark_gray>·</dark_gray> " + (lvOk ? "<gray>" : "<#ff6b6b>") + "제작 레벨 " + r.levelReq());
        tail.add(ok ? "<#ffd27a>▶ 클릭하여 제작" + (r.amount() > 1 ? " (×" + r.amount() + ")" : "")
                : "<#ff6b6b>조건이 부족합니다");
        // 재료 줄만큼 자리를 비워 툴팁이 화면 안에 들어가게 (ItemTooltip.MAX_LINES)
        List<String> lore = new ArrayList<>(ItemTooltip.lines(services.content(), def, null, Map.of(), List.of(), tail.size()));
        lore.addAll(tail);
        String name = "<" + def.rarity().color() + ">" + def.name() + (r.amount() > 1 ? " <gray>×" + r.amount() : "");
        Material base = "bow".equals(def.weaponType()) ? Material.BOW : Material.PAPER;
        return Button.icon(base, def.id(), name, lore);
    }
}
