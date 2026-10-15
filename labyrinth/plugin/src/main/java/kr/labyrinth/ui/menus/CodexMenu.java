package kr.labyrinth.ui.menus;

import io.papermc.paper.datacomponent.DataComponentTypes;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.treasure.ChestSettings;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 도감 {@code /codex} (= {@code /도감}, {@code /미궁 도감}): 아이템을 종류·희귀도별로, 몬스터·보스를 층별로.
 * 아이템 툴팁 아래에 "획득처"(보스·정예·몬스터·상자·보물 상자·기믹 방·제작·상점·칭호 보상·시작 지급)를 콘텐츠에서 계산해 붙인다.
 */
public final class CodexMenu extends LabMenu {

    private enum Tab {
        WEAPON("무기", Material.IRON_SWORD), ARMOR("방어구", Material.IRON_CHESTPLATE), ACCESSORY("장신구", Material.AMETHYST_SHARD),
        MATERIAL("재료", Material.IRON_NUGGET), CONSUMABLE("소모품", Material.POTION), MOB("몬스터", Material.SPIDER_EYE),
        BOSS("보스", Material.WITHER_SKELETON_SKULL);

        final String label;
        final Material icon;

        Tab(String label, Material icon) { this.label = label; this.icon = icon; }
    }

    private static final int PER_PAGE = 36; // 9..44

    private Tab tab = Tab.WEAPON;
    private Rarity rarity; // null = 전체
    private int page;
    private Map<String, List<String>> sources;

    public CodexMenu(Services services) {
        super(services, "codex", 6, "<#ffd36b>미궁 도감");
    }

    @Override
    protected void draw(Player viewer) {
        if (sources == null) sources = buildSources(services.content());
        Tab[] tabs = Tab.values();
        for (int i = 0; i < tabs.length; i++) {
            Tab t = tabs[i];
            boolean sel = t == tab;
            set(i, UiTheme.glint(icon(t.icon, (sel ? "<#ffd36b><b>▶ " : "<gray>") + t.label, List.of("<dark_gray>클릭해서 보기")), sel), ctx -> {
                tab = t;
                page = 0;
                click(ctx.player());
                refresh();
            });
        }
        boolean itemTab = tab.ordinal() <= Tab.CONSUMABLE.ordinal();
        if (itemTab) {
            String rName = rarity == null ? "<white>전체" : "<" + rarity.color() + ">" + rarity.displayName();
            set(8, icon(Material.PRISMARINE_CRYSTALS, "<gray>희귀도: " + rName, List.of("<dark_gray>클릭: 다음 희귀도", "<dark_gray>우클릭: 전체")), ctx -> {
                if (ctx.isRight()) rarity = null;
                else rarity = rarity == null ? Rarity.values()[0]
                        : rarity.ordinal() + 1 < Rarity.values().length ? Rarity.values()[rarity.ordinal() + 1] : null;
                page = 0;
                click(ctx.player());
                refresh();
            });
        }

        List<ItemStack> entries = itemTab ? itemEntries(services.stats().requirementStats(viewer)) : tab == Tab.MOB ? mobEntries() : bossEntries();
        int pages = Math.max(1, (entries.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        for (int i = 0; i < PER_PAGE; i++) {
            int idx = page * PER_PAGE + i;
            if (idx >= entries.size()) break;
            deco(9 + i, entries.get(idx));
        }
        if (entries.isEmpty()) deco(22, icon(Material.BARRIER, "<gray>해당하는 항목이 없습니다", List.of()));
        if (page > 0) set(45, UiTheme.prev(page, pages), ctx -> { page--; click(ctx.player()); refresh(); });
        if (page < pages - 1) set(53, UiTheme.next(page, pages), ctx -> { page++; click(ctx.player()); refresh(); });
        deco(49, icon(Material.BOOK, "<#ffd36b>" + tab.label + " <gray>" + entries.size() + "종",
                List.of("<gray>" + (page + 1) + " / " + pages + " 쪽", "<dark_gray>장비 능력치는 얻을 때 범위 안에서 무작위")));
        backButton(47, null);
    }

    // ── 아이템 ────────────────────────────────────────────────────────────

    private boolean inTab(ItemDef d) {
        return switch (tab) {
            case WEAPON -> d.type() == ItemType.WEAPON;
            case ARMOR -> d.type() == ItemType.ARMOR;
            case ACCESSORY -> d.type() == ItemType.ACCESSORY;
            case MATERIAL -> d.type() == ItemType.MATERIAL;
            case CONSUMABLE -> d.type() == ItemType.CONSUMABLE || d.type() == ItemType.KEY;
            default -> false;
        };
    }

    /** @param viewer 보는 사람의 요구치 판정 능력치 — 장비 요구 능력치를 맞춤 초록 / 모자람 빨강 "(현재 22)" 로 보여 준다 */
    private List<ItemStack> itemEntries(Map<Stat, Integer> viewer) {
        List<ItemDef> list = new ArrayList<>();
        for (ItemDef d : services.content().items().values()) {
            if (inTab(d) && (rarity == null || d.rarity() == rarity)) list.add(d);
        }
        // 희귀도 → 층 → 숨은 내부 레벨(level_req, 표시 안 함) 순
        list.sort(Comparator.comparing((ItemDef d) -> d.rarity() == null ? 0 : d.rarity().ordinal())
                .thenComparingInt(ItemDef::floor).thenComparingInt(ItemDef::levelReq).thenComparing(ItemDef::id));
        List<ItemStack> out = new ArrayList<>();
        int from = page * PER_PAGE;
        for (int i = 0; i < list.size(); i++) {
            // 보이는 쪽만 실제 아이템(툴팁 계산)으로 만든다
            out.add(i >= from && i < from + PER_PAGE ? itemIcon(list.get(i), viewer) : null);
        }
        return out;
    }

    private ItemStack itemIcon(ItemDef d, Map<Stat, Integer> viewer) {
        ItemStack s;
        try {
            s = services.items().create(d.id());
        } catch (Throwable t) {
            s = null;
        }
        if (s == null || s.getType().isAir()) s = UiTheme.item(d.id(), Material.PAPER, d.name(), List.of());
        // 도감은 굴림값·강화 대신 범위로 보여 주고, 획득처 목록이 들어갈 자리를 비운다 (화면 안에 — ItemTooltip.MAX_LINES)
        List<String> src = sources.getOrDefault(d.id(), List.of());
        if (src.isEmpty()) src = List.of("<dark_gray>알려진 획득처 없음 (관리자 지급)");
        // 툴팁의 획득처 한 줄 요약은 아래 목록과 겹치므로 넣지 않는다
        List<String> lines = new ArrayList<>(ItemTooltip.lines(services.content(), d, null, Map.of(), List.of(),
                1 + Math.min(src.size(), SOURCE_LINES), false, viewer));
        lines.add("<#ffd36b>◆ 획득처");
        int room = Math.max(1, ItemTooltip.MAX_LINES - lines.size());
        if (src.size() <= room) {
            lines.addAll(src);
        } else {
            lines.addAll(src.subList(0, room - 1));
            lines.add("<dark_gray>  … 외 더 있음");
        }
        s.lore(Text.itemLines(lines));
        s.setAmount(1);
        return s;
    }

    // ── 몬스터·보스 ───────────────────────────────────────────────────────

    private ItemStack modelIcon(String mobId, ModelDef model, Material fallback, String name, List<String> lore) {
        ItemStack s = Button.icon(Material.PAPER, name, lore);
        String part = null;
        if (model != null && !model.parts().isEmpty()) {
            for (ModelDef.Part p : model.parts()) if ("head".equals(p.name())) part = p.name();
            if (part == null) part = model.parts().get(0).name();
        }
        if (part == null) return Button.icon(fallback, name, lore);
        s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, "mob/" + mobId + "/" + part));
        return s;
    }

    private List<String> dropLines(String table) {
        List<String> out = new ArrayList<>();
        LootTable t = services.content().lootTable(table);
        if (t == null) return out;
        Set<String> names = new LinkedHashSet<>();
        Set<String> commons = new LinkedHashSet<>();
        collectItems(services.content(), t, names, commons, new HashSet<>());
        int n = 0;
        for (String id : names) {
            ItemDef d = services.content().item(id);
            if (d == null) continue;
            if (n++ >= 6) {
                out.add("<dark_gray>  … 외 " + (names.size() - 6) + "종");
                break;
            }
            String c = d.rarity() == null ? "white" : d.rarity().color();
            out.add("<gray>  · <" + c + ">" + Text.escape(Text.strip(d.name())));
        }
        // 층 공용 무기 묶음은 무기를 하나하나 늘어놓지 않고 한 줄로
        for (String id : commons) out.add("<gray>  · 지하 " + commonFloor(id) + "층 무기 (몬스터·상자 공용)");
        return out;
    }

    private List<ItemStack> mobEntries() {
        List<MobDef> list = new ArrayList<>(services.content().mobs().values());
        list.sort(Comparator.comparingInt(MobDef::floor).thenComparing(m -> m.isElite() ? 1 : 0).thenComparing(MobDef::id));
        List<ItemStack> out = new ArrayList<>();
        for (MobDef m : list) {
            List<String> lore = new ArrayList<>();
            String rank = m.isElite() ? "<#ffb52e>정예" : m.isAdd() ? "<gray>소환물" : "<white>일반";
            lore.add("<gray>지하 <white>" + m.floor() + "</white>층 · " + rank);
            lore.add("<gray>HP <white>" + Text.num(m.hp()) + "</white> · 공격 <white>" + Text.num(m.damage()) + "</white> · 방어 <white>"
                    + Text.num(m.defense()) + "</white> <dark_gray>(보통·보정 전)");
            lore.add("<gray>경험치 <white>" + Text.num(m.xp()));
            lore.addAll(wrap(m.description(), 26, "<dark_gray>"));
            List<String> drops = dropLines(m.drops());
            if (!drops.isEmpty()) {
                lore.add("<#ffd36b>◆ 드롭");
                lore.addAll(drops);
            }
            out.add(modelIcon(m.id(), m.model(), Material.SPIDER_EYE, (m.isElite() ? "<#ffb52e>" : "<white>") + m.name(), lore));
        }
        return out;
    }

    private List<ItemStack> bossEntries() {
        List<BossDef> list = new ArrayList<>(services.content().bosses().values());
        list.sort(Comparator.comparingInt(BossDef::floor));
        List<ItemStack> out = new ArrayList<>();
        for (BossDef b : list) {
            List<String> lore = new ArrayList<>();
            if (b.title() != null && !b.title().isBlank()) lore.add("<gray>" + b.title());
            FloorDef f = services.content().floor(b.floor());
            lore.add("<gray>지하 <white>" + b.floor() + "</white>층" + (f == null ? "" : " · " + Text.escape(Text.strip(f.name()))));
            lore.add("<gray>HP <white>" + Text.num(b.hp()) + "</white> · 공격 <white>" + Text.num(b.damage()) + "</white> · 페이즈 <white>"
                    + Math.max(1, b.phases().size()) + "</white> <dark_gray>(보통·보정 전)");
            lore.addAll(wrap(b.description(), 26, "<dark_gray>"));
            List<String> drops = dropLines(b.drops());
            if (!drops.isEmpty()) {
                lore.add("<#ffd36b>◆ 드롭");
                lore.addAll(drops);
            }
            out.add(modelIcon(b.id(), b.model(), Material.WITHER_SKELETON_SKULL, "<#ff6b6b><b>" + b.name() + "</b>", lore));
        }
        return out;
    }

    // ── 획득처 계산 ───────────────────────────────────────────────────────

    /** 층 공용 무기 묶음 {@code gear_fNN_common} 의 층 (아니면 -1). 몬스터·보물방·기믹방·미로 상자가 함께 굴리는 한 집이다. */
    static int commonFloor(String tableId) {
        if (tableId == null || !tableId.startsWith("gear_f") || !tableId.endsWith("_common")) return -1;
        try {
            return Integer.parseInt(tableId.substring(6, tableId.length() - 7));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    /**
     * 테이블이 줄 수 있는 아이템 id (중첩 테이블·one_of 포함, rarity_pool 은 그 층·희귀도 풀).
     * 층 공용 무기 묶음(gear_fNN_common)은 따라 들어가지 않고 {@code commons} 에 테이블 id 만 모은다 —
     * 그 무기들의 획득처는 몹 6종·보물방·기믹방 이름을 줄줄이 붙이지 않고 "몬스터·상자 지하 N층" 한 줄이다.
     */
    private static void collectItems(Content c, LootTable t, Set<String> out, Set<String> commons, Set<String> visiting) {
        if (t == null || !visiting.add(t.id())) return;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> { if (e.item() != null) out.add(e.item()); }
                case ONE_OF -> { if (e.oneOf() != null) out.addAll(e.oneOf()); }
                case TABLE -> {
                    if (commonFloor(e.table()) > 0) commons.add(e.table());
                    else collectItems(c, c.lootTable(e.table()), out, commons, visiting);
                }
                case RARITY_POOL -> {
                    if (e.rarityPool() != null) for (ItemDef d : c.poolCandidates(e.floor(), e.rarityPool())) out.add(d.id());
                }
            }
        }
        visiting.remove(t.id());
    }

    /**
     * 획득처 종류 (표시 순서). 장비는 보스 · 정예 · 몬스터·상자 · 제작 · 칭호 보상 · 시작 지급 중 1~2곳이고,
     * 보물 상자 · 기믹 방 · 몬스터 는 재료·소모품용으로 남긴다.
     */
    private static final List<String> SOURCE_GROUPS = List.of("보스", "정예", "몬스터·상자", "보물 상자", "기믹 방", "제작", "상점",
            "칭호 보상", "시작 지급", "몬스터");
    /** 층만 모아 "지하 9·10층" 으로 적는 묶음. */
    private static final Set<String> FLOOR_GROUPS = Set.of("몬스터·상자", "보물 상자", "기믹 방");
    // 제작 = 대장장이 (재료 ×개수 · … · 골드)
    private static final Map<String, String> SOURCE_COLORS = Map.of("보스", "#ff6b6b", "정예", "#ffb52e", "제작", "#7fd8ff",
            "상점", "#7fe07f", "칭호 보상", "#c9a2ff", "시작 지급", "#9be89b");
    /** 도감 툴팁에서 획득처에 비워 두는 최대 줄 수 (넘치면 장비 설명 쪽이 빈 줄·스킬 설명을 줄인다). */
    public static final int SOURCE_LINES = 6;
    /** 획득처 줄바꿈 글자 수 (툴팁 폭). */
    private static final int SOURCE_WRAP = 34;

    private record Src(String group, String label) {}

    /**
     * 아이템 id → 획득처 표시 줄. 종류별로 한 줄에 묶는다 ("정예 대시계 집행관(9층) · 심연의 문지기(10층)",
     * "보물 상자 지하 9·10층") — 길면 다음 줄로 이어 쓴다.
     */
    public static Map<String, List<String>> buildSources(Content c) {
        Map<String, Map<String, Set<String>>> src = new LinkedHashMap<>();
        Map<String, List<Src>> tableLabels = new LinkedHashMap<>();
        for (MobDef m : c.mobs().values()) {
            if (m.drops() == null) continue;
            tableLabels.computeIfAbsent(m.drops(), k -> new ArrayList<>())
                    .add(new Src(m.isElite() ? "정예" : "몬스터", Text.strip(m.name()) + "(" + m.floor() + "층)"));
        }
        for (BossDef b : c.bosses().values()) {
            if (b.drops() == null) continue;
            // 보스는 짧은 이름 ("시계탑의 간수 테오라" → "테오라") — 몇 층인지와 함께면 충분하고 한 줄에 여럿 들어간다
            tableLabels.computeIfAbsent(b.drops(), k -> new ArrayList<>())
                    .add(new Src("보스", ItemTooltip.bossShortName(b) + "(" + b.floor() + "층)"));
        }
        for (String tid : c.lootTables().keySet()) {
            int common = commonFloor(tid);
            if (common > 0) {
                tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src("몬스터·상자", String.valueOf(common)));
            } else if (tid.startsWith("treasure_floor_")) {
                tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src("보물 상자", tid.substring(15)));
            } else if (tid.startsWith("gimmick_floor_")) {
                tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src("기믹 방", tid.substring(14)));
            }
        }
        // 미로 상자 — Treasures·검사기와 같은 규칙으로 실제로 굴리는 표 (층별 maze_chest_<tier>_f<층>, floors.yml
        // chests.bracket 강제거나 층별 표가 없으면 구간 표) 를 보물 상자 묶음에 층으로
        for (FloorDef f : c.floors().values()) {
            int bracket = ChestSettings.of(f.raw().sub("chests")).bracket();
            for (ChestTier tier : ChestTier.values()) {
                String tid = tier.table(f.number(), bracket, c.lootTables()::containsKey);
                if (c.lootTables().containsKey(tid)) {
                    tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src("보물 상자", String.valueOf(f.number())));
                }
            }
        }
        for (var e : tableLabels.entrySet()) {
            Set<String> items = new LinkedHashSet<>();
            collectItems(c, c.lootTable(e.getKey()), items, new HashSet<>(), new HashSet<>());
            for (String id : items) for (Src s : e.getValue()) add(src, id, s);
        }
        for (RecipeDef r : c.recipes().values()) {
            StringBuilder sb = new StringBuilder();
            int n = 0;
            for (var m : r.materials().entrySet()) {
                ItemDef md = c.item(m.getKey());
                if (n++ > 0) sb.append(", ");
                sb.append(md == null ? m.getKey() : Text.strip(md.name())).append(" ×").append(m.getValue());
            }
            if (r.gold() > 0) sb.append(n > 0 ? ", " : "").append(r.gold()).append("G");
            add(src, r.result(), new Src("제작", sb.toString()));
        }
        for (NpcDef npc : c.npcs().values()) {
            if (npc.shop() == null) continue;
            for (NpcDef.ShopEntry s : npc.shop()) add(src, s.item(), new Src("상점", Text.strip(npc.name()) + " " + s.price() + "G"));
        }
        for (AchievementDef a : c.achievements().values()) {
            if (a.rewardItems() == null) continue;
            for (String id : a.rewardItems().keySet()) add(src, id, new Src("칭호 보상", "칭호의 주인에게 한 번"));
        }
        // 시작 꾸러미 (items.yml sources: [starter]) — 루팅·제작에는 없다
        for (ItemDef d : c.items().values()) {
            if (d.sources().contains("starter")) add(src, d.id(), new Src("시작 지급", "처음 직업을 고를 때"));
        }
        Map<String, List<String>> out = new LinkedHashMap<>();
        // 원문 이름에 든 MiniMessage 기호는 strip 으로 걷었으므로 그대로 써도 안전
        src.forEach((id, groups) -> out.put(id, List.copyOf(formatSources(groups))));
        return out;
    }

    private static void add(Map<String, Map<String, Set<String>>> src, String id, Src s) {
        src.computeIfAbsent(id, k -> new LinkedHashMap<>()).computeIfAbsent(s.group(), k -> new LinkedHashSet<>()).add(s.label());
    }

    /** 종류별 한 줄 (넘치면 들여 써서 이어 감). 몬스터·상자·보물 상자·기믹 방은 층만 모아 "지하 9·10층". */
    static List<String> formatSources(Map<String, Set<String>> groups) {
        List<String> lines = new ArrayList<>();
        for (String g : SOURCE_GROUPS) {
            Set<String> labels = groups.get(g);
            if (labels == null || labels.isEmpty()) continue;
            List<String> parts = new ArrayList<>();
            if (FLOOR_GROUPS.contains(g)) {
                List<Integer> floors = new ArrayList<>();
                for (String l : labels) {
                    try { floors.add(Integer.parseInt(l)); } catch (NumberFormatException ignored) { }
                }
                floors.sort(Integer::compare);
                List<String> fs = new ArrayList<>();
                for (int f : floors) fs.add(String.valueOf(f));
                parts.add("지하 " + String.join("·", fs) + "층");
            } else if (g.equals("제작")) {
                for (String l : labels) parts.addAll(List.of(l.split(", "))); // 재료마다 끊어 줄바꿈
            } else {
                parts.addAll(labels);
            }
            String color = SOURCE_COLORS.getOrDefault(g, "#d0d0d0");
            StringBuilder cur = new StringBuilder();
            int curLen = g.length() + 1;
            boolean firstLine = true;
            for (String p : parts) {
                int add = (cur.length() == 0 ? 0 : 3) + p.length();
                if (cur.length() > 0 && curLen + add > SOURCE_WRAP) {
                    lines.add((firstLine ? "<" + color + ">" + g + "</" + color + "> " : "   ") + "<gray>" + cur);
                    firstLine = false;
                    cur.setLength(0);
                    curLen = 3;
                    add = p.length();
                }
                if (cur.length() > 0) cur.append(" <dark_gray>·</dark_gray> <gray>");
                cur.append(p);
                curLen += add;
            }
            if (cur.length() > 0) lines.add((firstLine ? "<" + color + ">" + g + "</" + color + "> " : "   ") + "<gray>" + cur);
        }
        return lines;
    }
}
