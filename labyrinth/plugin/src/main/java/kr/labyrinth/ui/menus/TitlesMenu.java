package kr.labyrinth.ui.menus;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.titles.AchievementRules;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * /칭호 — 업적·칭호 도감: 분류 탭 8개(전체 + 7분류), 달성 칭호 클릭 = 장착(채팅·탭·이름표), 미달성은 조건·진행도,
 * 숨김 업적은 ???. 아래 줄: 해제 · 서버 최초 기록.
 */
public final class TitlesMenu extends LabMenu {

    static final String[] CATS = {null, "pioneer", "clear", "challenge", "combat", "growth", "collection", "craft"};
    static final String[] CAT_NAMES = {"전체", "개척", "돌파", "도전", "전투", "성장", "수집", "제작"};
    static final Material[] CAT_ICONS = {Material.BOOKSHELF, Material.BEACON, Material.IRON_DOOR, Material.BLAZE_ROD,
            Material.IRON_SWORD, Material.EXPERIENCE_BOTTLE, Material.CHEST, Material.ANVIL};
    private static final int PER = 28;

    private int tab;
    private int page;

    public TitlesMenu(Services services) {
        super(services, "titles", 6, "<#ffd36b>칭호 · 업적");
    }

    @Override
    protected void draw(Player p) {
        PlayerData d = services.data().get(p);
        for (int i = 0; i < CATS.length; i++) {
            final int idx = i;
            boolean sel = i == tab;
            int total = 0;
            int done = 0;
            for (AchievementDef a : services.content().achievements().values()) {
                if (CATS[i] != null && !CATS[i].equals(a.category())) continue;
                total++;
                if (d.hasAchievement(a.id())) done++;
            }
            set(i, UiTheme.glint(Button.icon(CAT_ICONS[i], (sel ? "<#ffd36b><b>▶ " : "<gray>") + CAT_NAMES[i],
                    List.of("<gray>달성 <white>" + done + "</white> / " + total)), sel), ctx -> {
                tab = idx;
                page = 0;
                click(ctx.player());
                refresh();
            });
        }
        List<AchievementDef> list = new ArrayList<>();
        for (AchievementDef a : services.content().achievements().values()) {
            if (CATS[tab] != null && !CATS[tab].equals(a.category())) continue;
            list.add(a);
        }
        // 달성한 것 먼저, 그다음 원래 순서
        List<AchievementDef> sorted = new ArrayList<>();
        for (AchievementDef a : list) if (d.hasAchievement(a.id())) sorted.add(a);
        for (AchievementDef a : list) if (!d.hasAchievement(a.id())) sorted.add(a);
        int pages = Math.max(1, (sorted.size() + PER - 1) / PER);
        page = Math.min(page, pages - 1);
        int k = 0;
        int[] slots = new int[PER];
        for (int r = 1; r <= 4; r++) for (int c = 1; c <= 7; c++) slots[k++] = r * 9 + c;
        SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd");
        String equipped = d.equippedTitle();
        for (int i = 0; i < PER && page * PER + i < sorted.size(); i++) {
            AchievementDef a = sorted.get(page * PER + i);
            boolean has = d.hasAchievement(a.id());
            boolean eq = a.id().equals(equipped);
            List<String> lore = new ArrayList<>();
            ItemStack icon;
            if (has) {
                lore.add("<gray>" + Text.escape(a.description()));
                lore.add("<dark_gray>달성 " + fmt.format(new Date(d.achievements().get(a.id()))));
                if (!a.bonus().isEmpty()) lore.add("<#7fe07f>장착 효과: " + bonusText(a));
                lore.add("");
                lore.add(eq ? "<#ffd36b>▶ 장착 중 <gray>(클릭: 해제)" : "<#ffd36b>클릭: 장착");
                icon = UiTheme.glint(Button.icon(eq ? Material.NAME_TAG : Material.PAPER, a.title(), lore), eq);
            } else if (a.hidden()) {
                lore.add("<dark_gray>숨겨진 업적입니다.");
                lore.add("<dark_gray>조건을 만족하면 드러납니다.");
                icon = Button.icon(Material.GRAY_DYE, "<dark_gray><b>???</b>", lore);
            } else {
                lore.add("<gray>" + Text.escape(a.description()));
                String cond = AchievementRules.conditionText(a);
                if (!cond.isEmpty()) lore.add("<dark_gray>조건: " + Text.escape(cond));
                long[] pr = services.titles().progress(p, a.id());
                if (pr[1] > 1) lore.add("<gray>진행 <#7fd8ff>" + UiTheme.bar((double) pr[0] / pr[1], 10, "▮", "▯") + " <white>"
                        + Text.num(pr[0]) + "/" + Text.num(pr[1]));
                if (!a.bonus().isEmpty()) lore.add("<dark_gray>장착 효과: " + bonusText(a));
                if (a.rewardGold() > 0 || !a.rewardItems().isEmpty()) lore.add("<dark_gray>보상: " + rewardText(a));
                if (a.broadcast()) lore.add("<dark_gray>달성 시 서버 전체 방송");
                icon = Button.icon(Material.FIREWORK_STAR, "<gray>" + Text.escape(a.name()), lore);
            }
            final String id = a.id();
            set(slots[i], icon, ctx -> {
                if (!has) {
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
                cur == null ? List.of("<gray>달성한 칭호를 클릭해 장착하세요.") : List.of("<gray>현재 장착 중", "", "<#ff6b6b>클릭: 해제")),
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

    static String bonusText(AchievementDef a) {
        List<String> parts = new ArrayList<>();
        a.bonus().forEach((k, v) -> {
            kr.labyrinth.stats.Stat st = kr.labyrinth.stats.Stat.byKey(k);
            if (st != null) parts.add(st.displayName() + " +" + Math.round(v));
            else if ("xp_bonus".equals(k)) parts.add("경험치 +" + Text.pct(v));
            else if ("gold_bonus".equals(k)) parts.add("골드 +" + Text.pct(v));
            else parts.add(k + " +" + v);
        });
        return String.join(" · ", parts);
    }

    String rewardText(AchievementDef a) {
        List<String> parts = new ArrayList<>();
        if (a.rewardGold() > 0) parts.add(Text.num(a.rewardGold()) + " 골드");
        a.rewardItems().forEach((id, n) -> {
            var def = services.content().item(id);
            parts.add(Text.strip(def == null ? id : def.name()) + " ×" + n);
        });
        return String.join(", ", parts);
    }
}
