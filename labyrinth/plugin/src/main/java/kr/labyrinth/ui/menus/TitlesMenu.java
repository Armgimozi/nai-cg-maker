package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.data.ServerRecords;
import kr.labyrinth.titles.TitleView;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * /칭호 — 칭호 12개를 한 화면에 (칭호마다 서버에서 단 한 명). 아이콘마다 칭호·설명·장착 효과·"조건: ???"(주인이 생기면 실제 조건)·주인.
 * 내 칭호 클릭 = 장착/해제. 맨 위 = 안내, 아래 줄 = 뒤로 · 장착 중(해제) · 서버 최초 기록. 문구는 {@link TitleView}.
 */
public final class TitlesMenu extends LabMenu {

    /** 12개까지: 4줄 × 3칸 (gui_titles 배경의 받침 자리와 같다). */
    static final int[] SLOTS_12 = {11, 13, 15, 20, 22, 24, 29, 31, 33, 38, 40, 42};
    private static final int PER = 28;

    private int page;

    public TitlesMenu(Services services) {
        super(services, "titles", 6, "<#ffd36b>칭호");
    }

    static TitleView.Owner owner(Services services, String id) {
        ServerRecords.Record r = services.records().get(TitleView.recordKey(id)).orElse(null);
        return r == null ? null : new TitleView.Owner(r.names().isEmpty() ? "?" : r.names().get(0), r.time());
    }

    @Override
    protected void draw(Player p) {
        PlayerData d = services.data().get(p);
        List<AchievementDef> list = new ArrayList<>(services.content().achievements().values());
        int owned = 0;
        int mineCount = 0;
        for (AchievementDef a : list) {
            if (owner(services, a.id()) != null) owned++;
            if (d.hasAchievement(a.id())) mineCount++;
        }
        deco(4, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b><b>칭호</b>", TitleView.summary(list.size(), owned, mineCount)));

        int[] slots;
        int pages = 1;
        if (list.size() <= SLOTS_12.length) {
            slots = SLOTS_12;
            page = 0;
        } else {
            slots = new int[PER];
            int k = 0;
            for (int r = 1; r <= 4; r++) for (int c = 1; c <= 7; c++) slots[k++] = r * 9 + c;
            pages = (list.size() + PER - 1) / PER;
            page = Math.min(page, pages - 1);
        }
        String equipped = d.equippedTitle();
        int start = page * slots.length;
        for (int i = 0; i < slots.length && start + i < list.size(); i++) {
            AchievementDef a = list.get(start + i);
            TitleView.Owner o = owner(services, a.id());
            boolean mine = d.hasAchievement(a.id());
            boolean eq = mine && a.id().equals(equipped);
            List<String> lore = TitleView.lore(a, o, mine, eq, services.content());
            Material m = mine ? (eq ? Material.NAME_TAG : Material.PAPER) : o != null ? Material.NETHER_STAR : Material.FIREWORK_STAR;
            final String id = a.id();
            set(slots[i], UiTheme.glint(Button.icon(m, a.title(), lore), eq), ctx -> {
                if (!services.data().get(ctx.player()).hasAchievement(id)) {
                    deny(ctx.player());
                    return;
                }
                boolean wasEq = id.equals(services.data().get(ctx.player()).equippedTitle());
                services.titles().equip(ctx.player(), wasEq ? null : id);
                ok(ctx.player());
                refresh();
            });
        }
        if (page > 0) set(47, UiTheme.prev(page, pages), ctx -> { page--; click(ctx.player()); refresh(); });
        if (page < pages - 1) set(51, UiTheme.next(page, pages), ctx -> { page++; click(ctx.player()); refresh(); });
        AchievementDef cur = services.titles().equipped(p);
        set(49, Button.icon(cur == null ? Material.STRUCTURE_VOID : Material.NAME_TAG,
                cur == null ? "<gray>장착한 칭호 없음" : cur.title(),
                cur == null ? List.of("<gray>내 칭호를 클릭해 장착하세요.") : List.of("<gray>현재 장착 중", "", "<#ff6b6b>클릭: 해제")),
                ctx -> {
                    if (services.titles().equipped(ctx.player()) == null) return;
                    services.titles().equip(ctx.player(), null);
                    click(ctx.player());
                    refresh();
                });
        set(53, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b><b>서버 최초 기록</b>", List.of("<gray>각 층 최초 돌파 파티 · 최단 기록")),
                ctx -> { click(ctx.player()); new RecordsMenu(services, pl -> new TitlesMenu(services).open(pl)).open(ctx.player()); });
        backButton(45, MainMenu::reopen);
    }
}
