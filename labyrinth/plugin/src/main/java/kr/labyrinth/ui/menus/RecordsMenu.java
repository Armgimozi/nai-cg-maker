package kr.labyrinth.ui.menus;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.function.Consumer;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.ServerRecords;
import kr.labyrinth.titles.TitleView;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/** 서버의 역사: 층별 최초 돌파 파티(날짜·난이도·시간)와 최단 기록, 칭호의 주인. */
public final class RecordsMenu extends LabMenu {

    private static final int[] FLOOR_SLOTS = {11, 12, 13, 14, 15, 20, 21, 22, 23, 24};
    private final Consumer<Player> back;

    public RecordsMenu(Services services, Consumer<Player> back) {
        super(services, "records", 6, "<#ffd36b>서버 최초 기록");
        this.back = back;
    }

    @Override
    protected void draw(Player p) {
        SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd HH:mm");
        deco(4, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b><b>미궁의 역사</b>",
                List.of("<gray>각 층을 처음 돌파한 파티는 영원히 기록됩니다.", "<gray>칭호는 칭호마다 단 한 명만 가집니다.")));
        for (int i = 0; i < FLOOR_SLOTS.length; i++) {
            int n = i + 1;
            FloorDef f = services.content().floor(n);
            ServerRecords.Record first = services.records().get("first_clear.floor_" + n).orElse(null);
            ServerRecords.Record speed = services.records().get("speed.floor_" + n).orElse(null);
            List<String> lore = new ArrayList<>();
            if (first == null) {
                lore.add("<dark_gray>아직 아무도 돌파하지 못했습니다.");
            } else {
                lore.add("<gray>최초 돌파 <white>" + Text.escape(String.join(", ", first.names())));
                lore.add("<dark_gray>" + fmt.format(new Date(first.time())) + extra(first));
            }
            if (speed != null && speed.extra().get("seconds") instanceof Number sec) {
                lore.add("");
                lore.add("<#7fd8ff>최단 기록 <white>" + UiTheme.clock(Math.round(sec.doubleValue())));
                lore.add("<gray>" + Text.escape(String.join(", ", speed.names())));
            }
            String name = f == null ? "" : " <gray>" + Text.escape(Text.strip(f.name()));
            deco(FLOOR_SLOTS[i], UiTheme.glint(Button.icon(first == null ? Material.GRAY_DYE : Material.GOLD_BLOCK,
                    (first == null ? "<dark_gray>" : "<#ffd36b>") + "<b>지하 " + n + "층</b>" + name, lore), first != null));
        }
        // 칭호의 주인 (칭호마다 서버에서 단 한 명) — 조건은 주인이 생긴 칭호만 (TitleView)
        List<String> owners = new ArrayList<>();
        for (AchievementDef a : services.content().achievements().values()) {
            TitleView.Owner o = TitlesMenu.owner(services, a.id());
            owners.add(a.title() + " <dark_gray>— " + (o == null ? "주인 없음" : "<white>" + Text.escape(o.name())));
        }
        deco(40, Button.icon(Material.NETHER_STAR, "<#ffd36b><b>칭호의 주인</b>", owners));
        backButton(45, back);
    }

    private static String extra(ServerRecords.Record r) {
        StringBuilder sb = new StringBuilder();
        Object d = r.extra().get("difficulty");
        if (d != null) sb.append(" · ").append(diffName(String.valueOf(d)));
        if (r.extra().get("seconds") instanceof Number n) sb.append(" · ").append(UiTheme.clock(n.longValue()));
        if (r.extra().get("party_size") instanceof Number n) sb.append(" · ").append(n.intValue()).append("인");
        return sb.toString();
    }

    private static String diffName(String id) {
        return switch (id) {
            case "easy" -> "쉬움";
            case "hard" -> "어려움";
            case "nightmare" -> "악몽";
            default -> "보통";
        };
    }
}
