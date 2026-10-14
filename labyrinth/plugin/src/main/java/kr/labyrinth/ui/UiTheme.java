package kr.labyrinth.ui;

import io.papermc.paper.datacomponent.DataComponentTypes;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.GlyphDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.ItemStack;

/**
 * 미궁 UI 공통 테마: 글리프 배경 메뉴 제목, 아이콘·버튼 규칙, 텍스트/글리프 막대.
 * <p>
 * <b>글리프 이름 계약</b> (glyphs.yml 이 주면 자동 적용, 없으면 평범한 제목 — 절대 실패하지 않음):
 * 메뉴 배경 {@code gui_<메뉴>} (main, stats, class, class_detail, party, players, titles, entrance, setup, accessories,
 * pvp, pvp_ranking, records, blacksmith, merchant, confirm), 없으면 {@code gui_rows_<줄 수>}. 배경 폭은 glyphs.yml 의 선택 필드
 * {@code width}(px, 기본 176), 제목 글자 시작 x 는 선택 필드 {@code title_x}(px, 기본 8 = 바닐라 제목 위치), 제목 색은 선택 필드
 * {@code title_color}(#RRGGBB, 기본 #3b2a4d → 글리프 있을 때만).
 * HUD 는 {@link HudBars} 참고.
 */
public final class UiTheme {

    /** 글리프 메타(선택 필드: width, title_x, title_color). glyphs.yml 원문에서 읽는다 (GlyphDef 는 core 소유라 필드가 없음). */
    public record Meta(int width, int titleX, String titleColor) {}

    private static final Map<String, Meta> META = new ConcurrentHashMap<>();

    // 색 (MiniMessage)
    public static final String GOLD = "#ffd36b";
    public static final String MUTED = "#9a93a8";
    public static final String OK = "#7fe07f";
    public static final String BAD = "#ff6b6b";
    public static final String ACCENT = "#c9a2ff";
    public static final String SKY = "#7fd8ff";

    private UiTheme() {}

    /** glyphs.yml 원문을 다시 읽어 선택 필드를 갱신 (UiModule enable/reload). */
    public static void loadMeta(Services services) {
        META.clear();
        Path file = services.plugin().getDataFolder().toPath().resolve("content").resolve("glyphs.yml");
        if (!Files.exists(file)) return;
        try {
            YamlConfiguration y = new YamlConfiguration();
            y.loadFromString(Files.readString(file));
            ConfigurationSection gs = y.getConfigurationSection("glyphs");
            if (gs == null) return;
            for (String id : gs.getKeys(false)) {
                ConfigurationSection g = gs.getConfigurationSection(id);
                if (g == null) continue;
                META.put(id, new Meta(g.getInt("width", g.getInt("advance", 176)), g.getInt("title_x", 8),
                        g.getString("title_color", "#3b2a4d")));
            }
        } catch (Exception e) {
            Log.warn("[UI] glyphs.yml 선택 필드 읽기 실패 (글리프 없이 계속): " + e.getMessage());
        }
    }

    static Meta meta(String id) { return META.getOrDefault(id, new Meta(176, 8, "#3b2a4d")); }

    private static boolean has(String id) {
        try {
            return id != null && Services.get().content().glyphs().containsKey(id);
        } catch (Throwable t) {
            return false;
        }
    }

    /** 여러 후보 중 처음 존재하는 글리프 id (없으면 null). */
    public static String firstGlyph(String... candidates) {
        for (String c : candidates) if (has(c)) return c;
        return null;
    }

    /**
     * 메뉴 제목. 글리프 {@code gui_<menu>}(없으면 {@code gui_rows_<rows>})가 있으면 배경을 깔고 그 위에 제목,
     * 없으면 MiniMessage 제목 그대로.
     */
    public static Component title(String menu, int rows, String miniTitle) {
        String g = firstGlyph("gui_" + menu, "gui_rows_" + rows);
        if (g == null) return Text.mm(miniTitle);
        Meta m = meta(g);
        GlyphDef def = Services.get().content().glyphs().get(g);
        if (def == null) return Text.mm(miniTitle);
        // 펜 x=0 은 바닐라 제목 위치(컨테이너 왼쪽 + 8px). 배경을 왼쪽 끝(-8)부터 그리고, 제목은 title_x 로 되돌아와 쓴다.
        Component bg = Component.text(def.ch()).font(Glyphs.FONT).color(NamedTextColor.WHITE);
        int back = -(m.width() + 1) + 8 + (m.titleX() - 8);
        return Component.empty()
                .append(Glyphs.space(-8))
                .append(bg)
                .append(Glyphs.space(back))
                .append(Text.mm("<" + m.titleColor() + ">" + Text.strip(miniTitle)));
    }

    /** 리소스팩 아이템 모델(labyrinth:&lt;id&gt;)을 쓰는 아이콘 — items.yml 에 있는 id 일 때만 모델 지정. */
    public static ItemStack item(String itemId, Material fallback, String name, List<String> lore) {
        boolean known;
        try {
            known = itemId != null && Services.get().content().item(itemId) != null;
        } catch (Throwable t) {
            known = false;
        }
        ItemStack s = Button.icon(known ? Material.PAPER : fallback, name, lore);
        if (known) s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, itemId));
        return s;
    }

    /** 반짝이는(선택됨) 아이콘. */
    public static ItemStack glint(ItemStack s, boolean on) {
        if (on) s.setData(DataComponentTypes.ENCHANTMENT_GLINT_OVERRIDE, true);
        return s;
    }

    public static ItemStack filler() { return Button.filler(Material.GRAY_STAINED_GLASS_PANE); }

    public static ItemStack darkFiller() { return Button.filler(Material.BLACK_STAINED_GLASS_PANE); }

    /** 글리프 배경이 있으면 투명(빈 칸)으로 두고, 없으면 유리판으로 채운다. */
    public static void frame(Menu menu, String menuId, int rows) {
        if (firstGlyph("gui_" + menuId, "gui_rows_" + rows) != null) return;
        int size = menu.size();
        for (int i = 0; i < size; i++) {
            int r = i / 9;
            int c = i % 9;
            if (r == 0 || r == rows - 1 || c == 0 || c == 8) menu.deco(i, darkFiller());
        }
    }

    public static ItemStack back() {
        return Button.icon(Material.ARROW, "<" + MUTED + ">◀ 돌아가기", List.of("<dark_gray>이전 메뉴로"));
    }

    public static ItemStack close() {
        return Button.icon(Material.BARRIER, "<" + BAD + ">닫기", List.of());
    }

    public static ItemStack prev(int page, int pages) {
        return Button.icon(Material.SPECTRAL_ARROW, "<" + SKY + ">◀ 이전 쪽", List.of("<gray>" + (page + 1) + " / " + pages + " 쪽"));
    }

    public static ItemStack next(int page, int pages) {
        return Button.icon(Material.SPECTRAL_ARROW, "<" + SKY + ">다음 쪽 ▶", List.of("<gray>" + (page + 1) + " / " + pages + " 쪽"));
    }

    /** 텍스트 막대: ▮ 채움 / ▯ 빈칸. */
    public static String bar(double ratio, int cells, String fill, String empty) {
        return HudBars.textBar(ratio, cells, fill, empty);
    }

    /** 1:23:45 / 05:12 형식. */
    public static String clock(long seconds) {
        seconds = Math.max(0, seconds);
        long h = seconds / 3600;
        long m = (seconds % 3600) / 60;
        long s = seconds % 60;
        return h > 0 ? String.format("%d:%02d:%02d", h, m, s) : String.format("%02d:%02d", m, s);
    }
}
