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
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.treasure.ChestSettings;
import kr.labyrinth.dungeon.treasure.ChestTier;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.items.LookText;
import kr.labyrinth.items.WeaponFilter;
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
 * 아이템 툴팁 아래에 "획득처"(보스·정예·몬스터·상자·보물 상자·시련방·특별 시련·금고·미믹·대장간·상인·칭호 보상·시작 지급)를
 * 콘텐츠에서 계산해 붙인다. 장비 획득처에는 층 숫자를 적지 않는다 (0.3.5 — 이웃 층 셋이 나눠 준다). 재료·소모품은 층을 적는다.
 * <p>
 * 거르개: 희귀도 · 무기 방식(근접·원거리·시전·물리·마법) / 방어구 겉모습(판금·가죽·천·평상복)·부위 · "지금 낄 수 있는 것만".
 * 장비를 클릭하면 자세히 보기 (무기 = 공격 방식·간격·스킬 위력, 방어구 = 4부위 효과 전문·요구 짝).
 */
public final class CodexMenu extends LabMenu {

    private enum Tab {
        WEAPON("무기", Material.IRON_SWORD), ARMOR("방어구", Material.IRON_CHESTPLATE), ACCESSORY("장신구", Material.AMETHYST_SHARD),
        MATERIAL("재료", Material.IRON_NUGGET), MINE("광산", Material.IRON_PICKAXE), CONSUMABLE("소모품", Material.POTION),
        MOB("몬스터", Material.SPIDER_EYE),
        BOSS("보스", Material.WITHER_SKELETON_SKULL);

        final String label;
        final Material icon;

        Tab(String label, Material icon) { this.label = label; this.icon = icon; }
    }

    /** 방어구 부위 거르개 (null = 전체). */
    private static final String[] SLOTS = {null, "head", "chest", "legs", "feet", "offhand"};
    private static final String[] SLOT_NAMES = {"전체", "투구", "흉갑", "각반", "장화", "방패"};
    /** 방어구 겉모습 거르개 (null = 전체). */
    private static final ArmorLook[] LOOKS = {null, ArmorLook.HEAVY, ArmorLook.LIGHT, ArmorLook.CLOTH, ArmorLook.PLAIN};

    private static final int PER_PAGE = 36; // 9..44
    private static final int FILTER_SLOT = 48, PART_SLOT = 50, WEARABLE_SLOT = 51;   // 0.3.6: 탭이 8개 (0~7)

    private Tab tab = Tab.WEAPON;
    private Rarity rarity; // null = 전체
    private WeaponFilter weaponFilter = WeaponFilter.ALL;
    private int look;      // LOOKS 위치
    private int part;      // SLOTS 위치
    private boolean wearableOnly;
    /** 자세히 보는 장비 id (null = 없음). */
    private String detail;
    private int page;
    private Map<String, List<String>> sources;

    public CodexMenu(Services services) {
        super(services, "codex", 6, "<#ffd36b>미궁 도감");
    }

    /** 지금 보는 사람 (도안 배움 줄, 0.3.6 Q6). */
    private Player who;

    @Override
    protected void draw(Player viewer) {
        who = viewer;
        if (sources == null) sources = buildSources(services.content());
        Tab[] tabs = Tab.values();
        for (int i = 0; i < tabs.length; i++) {
            Tab t = tabs[i];
            boolean sel = t == tab;
            set(i, UiTheme.glint(icon(t.icon, (sel ? "<#ffd36b><b>▶ " : "<gray>") + t.label, List.of("<dark_gray>클릭해서 보기")), sel), ctx -> {
                tab = t;
                page = 0;
                detail = null;
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
        drawFilters();

        Map<Stat, Integer> req = services.stats().requirementStats(viewer);
        List<ItemDef> defs = itemTab ? itemDefs(req) : List.of();
        List<ItemStack> entries = itemTab ? itemEntries(defs, req) : tab == Tab.MOB ? mobEntries() : bossEntries();
        int pages = Math.max(1, (entries.size() + PER_PAGE - 1) / PER_PAGE);
        page = Math.max(0, Math.min(page, pages - 1));
        for (int i = 0; i < PER_PAGE; i++) {
            int idx = page * PER_PAGE + i;
            if (idx >= entries.size()) break;
            if (itemTab && defs.get(idx).isGear()) {
                String id = defs.get(idx).id();
                set(9 + i, entries.get(idx), ctx -> {
                    detail = id.equals(detail) ? null : id;
                    click(ctx.player());
                    refresh();
                });
            } else {
                deco(9 + i, entries.get(idx));
            }
        }
        if (entries.isEmpty()) deco(22, icon(Material.BARRIER, "<gray>해당하는 항목이 없습니다", List.of()));
        if (page > 0) set(45, UiTheme.prev(page, pages), ctx -> { page--; click(ctx.player()); refresh(); });
        if (page < pages - 1) set(53, UiTheme.next(page, pages), ctx -> { page++; click(ctx.player()); refresh(); });
        List<String> info = new ArrayList<>();
        info.add("<gray>" + (page + 1) + " / " + pages + " 쪽");
        info.add("<dark_gray>장비 능력치는 얻을 때 범위 안에서 무작위");
        if (tab == Tab.WEAPON || tab == Tab.ARMOR) info.add("<dark_gray>장비를 클릭: 자세히 보기");
        deco(49, icon(Material.BOOK, "<#ffd36b>" + tab.label + " <gray>" + entries.size() + "종", info));
        backButton(47, null);
    }

    /** 무기 = 방식 거르개, 방어구 = 겉모습·부위 거르개, 두 탭 모두 "지금 낄 수 있는 것만". */
    private void drawFilters() {
        if (tab == Tab.WEAPON) {
            set(FILTER_SLOT, icon(Material.HOPPER, "<gray>방식: <white>" + weaponFilter.label(),
                    List.of("<dark_gray>근접 · 원거리 · 시전 · 물리 피해 · 마법 피해", "<dark_gray>클릭: 다음 · 우클릭: 전체")), ctx -> {
                weaponFilter = ctx.isRight() ? WeaponFilter.ALL : weaponFilter.next();
                page = 0;
                click(ctx.player());
                refresh();
            });
        }
        if (tab == Tab.ARMOR) {
            ArmorLooks cfg = services.settings().armorLooks();
            ArmorLook l = LOOKS[look];
            String name = l == null ? "<white>전체" : "<" + cfg.color(l) + ">" + cfg.name(l);
            set(FILTER_SLOT, icon(Material.LEATHER_CHESTPLATE, "<gray>겉모습: " + name,
                    List.of("<dark_gray>판금 · 가죽 · 천 · 평상복", "<dark_gray>클릭: 다음 · 우클릭: 전체")), ctx -> {
                look = ctx.isRight() ? 0 : (look + 1) % LOOKS.length;
                page = 0;
                click(ctx.player());
                refresh();
            });
            set(PART_SLOT, icon(Material.ARMOR_STAND, "<gray>부위: <white>" + SLOT_NAMES[part],
                    List.of("<dark_gray>클릭: 다음 · 우클릭: 전체")), ctx -> {
                part = ctx.isRight() ? 0 : (part + 1) % SLOTS.length;
                page = 0;
                click(ctx.player());
                refresh();
            });
        }
        if (tab == Tab.WEAPON || tab == Tab.ARMOR) {
            set(WEARABLE_SLOT, UiTheme.glint(icon(wearableOnly ? Material.LIME_DYE : Material.GRAY_DYE,
                    (wearableOnly ? "<#7fe07f>" : "<gray>") + "지금 낄 수 있는 것만: " + (wearableOnly ? "켜짐" : "꺼짐"),
                    List.of("<dark_gray>요구 능력치를 모두 채운 장비만", "<dark_gray>클릭: 켜기/끄기")), wearableOnly), ctx -> {
                wearableOnly = !wearableOnly;
                page = 0;
                click(ctx.player());
                refresh();
            });
        }
    }

    // ── 아이템 ────────────────────────────────────────────────────────────

    private boolean inTab(ItemDef d) {
        return switch (tab) {
            case WEAPON -> d.type() == ItemType.WEAPON;
            case ARMOR -> d.type() == ItemType.ARMOR;
            case ACCESSORY -> d.type() == ItemType.ACCESSORY;
            case MATERIAL -> d.type() == ItemType.MATERIAL && !d.isMineMaterial();
            case MINE -> d.isMineMaterial() || d.type() == ItemType.TOOL;   // 0.3.6: 광석·주괴·보석·곡괭이
            case CONSUMABLE -> d.type() == ItemType.CONSUMABLE || d.type() == ItemType.KEY || d.type() == ItemType.BLUEPRINT;
            default -> false;
        };
    }

    private boolean passes(ItemDef d, Map<Stat, Integer> req) {
        if (rarity != null && d.rarity() != rarity) return false;
        if (tab == Tab.WEAPON && !weaponFilter.test(d)) return false;
        if (tab == Tab.ARMOR) {
            if (LOOKS[look] != null && d.armorLook() != LOOKS[look]) return false;
            if (SLOTS[part] != null && !SLOTS[part].equals(d.armorSlot())) return false;
        }
        return !wearableOnly || !d.isGear() || d.requirement().met(req);
    }

    /** 탭·거르개를 통과한 아이템, 정렬: 희귀도 → 단계(장비, 숨김)·층(재료) → 숨은 내부 레벨 → id. */
    private List<ItemDef> itemDefs(Map<Stat, Integer> req) {
        List<ItemDef> list = new ArrayList<>();
        for (ItemDef d : services.content().items().values()) {
            if (inTab(d) && passes(d, req)) list.add(d);
        }
        list.sort(ORDER);
        return list;
    }

    /** 도감 정렬 (희귀도 → 장비 단계 / 재료 층 → level_req → id). */
    static final Comparator<ItemDef> ORDER = Comparator.comparing((ItemDef d) -> d.rarity() == null ? 0 : d.rarity().ordinal())
            .thenComparingInt((ItemDef d) -> d.isGear() ? d.tier() : d.floor()).thenComparingInt(ItemDef::levelReq).thenComparing(ItemDef::id);

    /** @param viewer 보는 사람의 요구치 판정 능력치 — 장비 요구 능력치를 맞춤 초록 / 모자람 빨강 "(현재 22)" 로 보여 준다 */
    private List<ItemStack> itemEntries(List<ItemDef> list, Map<Stat, Integer> viewer) {
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
        List<String> src = sources.getOrDefault(d.id(), List.of());
        if (src.isEmpty()) src = List.of("<dark_gray>알려진 획득처 없음 (관리자 지급)");
        // 0.3.6 Q6: 희귀 이상 장비의 도안을 배웠는가
        var bp = kr.labyrinth.items.blueprint.BlueprintService.get();
        var gated = bp != null && bp.enabled() && who != null
                ? kr.labyrinth.items.blueprint.BlueprintRules.recipeFor(services.content(), d.id()) : null;
        if (gated != null) {
            List<String> withBp = new ArrayList<>();
            withBp.add(bp.knows(who, gated.id()) ? "<#9be89b>✔ 도안을 배웠다" : "<#ff8a8a>✘ 도안을 아직 못 배웠다");
            withBp.addAll(src);
            src = withBp;
        }
        List<String> lines = d.id().equals(detail)
                ? detailLore(services.content(), d, services.settings().armorLooks(), viewer, src)
                : lore(services.content(), d, viewer, src);
        s.lore(Text.itemLines(lines));
        s.setAmount(1);
        return s;
    }

    /**
     * 도감 툴팁: 굴림값·강화 대신 범위, 아래에 "◆ 획득처" 목록 (툴팁의 획득처 한 줄 요약은 목록과 겹치므로 넣지 않는다).
     * 화면 안에 들도록 ({@link ItemTooltip#MAX_LINES}) 목록 자리를 먼저 비운다.
     */
    public static List<String> lore(Content c, ItemDef d, Map<Stat, Integer> viewer, List<String> src) {
        List<String> lines = new ArrayList<>(ItemTooltip.lines(c, d, null, Map.of(), List.of(),
                1 + Math.min(src.size(), SOURCE_LINES), false, viewer));
        lines.add("<#ffd36b>◆ 획득처");
        int room = Math.max(1, ItemTooltip.MAX_LINES - lines.size());
        if (src.size() <= room) {
            lines.addAll(src);
        } else {
            lines.addAll(src.subList(0, room - 1));
            lines.add("<dark_gray>  … 외 더 있음");
        }
        return lines;
    }

    /** 자세히 보기: 첫 줄·요구 줄 + {@link #detailLines} + 획득처 전부 (줄이 넘치면 획득처를 줄인다). */
    public static List<String> detailLore(Content c, ItemDef d, ArmorLooks cfg, Map<Stat, Integer> viewer, List<String> src) {
        List<String> all = ItemTooltip.lines(c, d, null, Map.of(), List.of(), 0, false, viewer);
        List<String> lines = new ArrayList<>(all.subList(0, d.requirement().isEmpty() ? 1 : Math.min(2, all.size())));
        lines.add("");
        lines.addAll(detailLines(c, d, cfg));
        lines.add("");
        lines.add("<#ffd36b>◆ 획득처");
        int room = Math.max(1, ItemTooltip.MAX_LINES - lines.size() - 1); // 끝의 '다시 클릭' 한 줄
        if (src.size() <= room) lines.addAll(src);
        else {
            lines.addAll(src.subList(0, Math.max(0, room - 1)));
            lines.add("<dark_gray>  … 외 더 있음");
        }
        lines.add("<dark_gray>다시 클릭: 돌아가기");
        return lines;
    }

    /**
     * 자세히 보기 본문 (순수). 무기: 공격 방식·피해 종류 · 공격 간격 · 스킬 위력 (combat_spec §3.3, 힘·지능·공격 속도 넣기 전).
     * 방어구: 겉모습 · 요구 짝 ("판금 · 체력과 힘") · 4부위 효과 전문 (look_spec §1.3). 그 밖은 빈 목록.
     */
    public static List<String> detailLines(Content c, ItemDef d, ArmorLooks cfg) {
        List<String> out = new ArrayList<>();
        out.add("<#ffd36b>◆ 자세히");
        if (d.isWeapon()) {
            WeaponAttack a = WeaponAttack.of(d);
            String style = switch (a.style()) {
                case MELEE -> "근접";
                case RANGED -> "원거리 (당겨 쏘기)";
                case CASTER -> a.firesBolt() ? "시전 (" + ItemTooltip.CASTER_BOLT + ")" : "시전";
            };
            out.add("<gray>공격 방식 <white>" + style + "</white> · 피해 <white>" + a.kind().displayName());
            out.add("<gray>공격 간격 <white>" + ItemTooltip.trim(Math.round(a.interval() * 100) / 100.0) + "초</white> <dark_gray>(초당 "
                    + ItemTooltip.perSecond(a.attacksPerSecond()) + "회, 민첩 넣기 전)");
            Range dmg = d.stats().get("damage");
            double mid = dmg == null ? 0 : (dmg.min() + dmg.max()) / 2.0;
            out.add("<gray>스킬 위력 <white>" + Math.round(CombatMath.skillPower(mid, a, 0)) + "</white> <dark_gray>(힘·지능·공격 속도 넣기 전)");
            out.add("<dark_gray>스킬 위력 = 직업 스킬·무기 스킬 피해의 기준.");
            out.add("<dark_gray>무거운 무기도 가벼운 무기도 같은 단계면 비슷하다.");
            if (d.unique() != null) {
                out.add(kr.labyrinth.items.unique.UniqueText.head(d.unique()));
                out.add(kr.labyrinth.items.unique.UniqueText.descLine(d.unique()));
            }
        } else if (d.type() == ItemType.ARMOR) {
            ArmorLook l = d.armorLook();
            String pair = pairText(d);
            if (l == null || !l.real() || cfg == null || !cfg.enabled()) {
                out.add("<gray>겉모습 <white>" + (l == ArmorLook.ANY ? "어느 겉모습과도 4부위를 이룸" : "평상복 (겉모습 효과 없음)"));
                if (!pair.isEmpty()) out.add("<gray>요구 짝 <white>" + pair);
            } else {
                String col = cfg.color(l);
                out.add("<gray>겉모습 <" + col + ">" + Text.escape(cfg.name(l)) + "</" + col + ">" + (pair.isEmpty() ? "" : " <gray>· 요구 " + pair));
                // 부위 하나 몫 ▲/▼ + 4부위 줄 (방패는 4부위 대신 안내 한 줄) — 툴팁과 같은 줄
                out.addAll(LookText.tooltip(cfg, l, d.isShield()));
                out.add("<" + col + ">" + cfg.fullPieces() + "부위 · " + Text.escape(cfg.fullName(l)) + "</" + col + "> <gray>자세히");
                for (String t : fullDescription(cfg, l)) out.addAll(LabMenu.wrap(t, 32, "<gray>  "));
            }
        }
        return out;
    }

    /** 요구 짝 이름 ("체력과 힘", 셋이면 "민첩·힘·행운"). 요구 없음 = 빈 문자열. */
    static String pairText(ItemDef d) {
        List<String> names = new ArrayList<>();
        for (Map.Entry<Stat, Integer> e : d.requirement().ordered()) names.add(e.getKey().displayName());
        if (names.size() == 2) return names.get(0) + "과 " + names.get(1); // 능력치 이름은 모두 받침으로 끝난다 (힘·민첩·지능·체력·정신·행운)
        return String.join("·", names);
    }

    /** 4부위 효과 전문 (look_spec §1.3 첫 두 줄, 설정 숫자 그대로). */
    static List<String> fullDescription(ArmorLooks cfg, ArmorLook l) {
        return switch (l) {
            case HEAVY -> List.of(
                    "몬스터·함정·다른 플레이어가 미는 힘 −" + Text.pct(cfg.steadfast().knockbackResist()) + " (힘의 밀려남 저항과 더함, 최대 85%).",
                    "기절·속박·빙결 시간 −" + Text.pct(cfg.steadfast().ccResist()) + ". 보스가 미는 것·거는 것은 그대로.");
            case LIGHT -> List.of(
                    "땅 위에서 웅크리기를 " + ItemTooltip.trim(cfg.tumble().doubleTap()) + "초 안에 두 번 → 움직이던 방향으로 "
                            + ItemTooltip.trim(cfg.tumble().distance()) + "칸 구름 (방향 없으면 뒤로 " + ItemTooltip.trim(cfg.tumble().backDistance()) + "칸).",
                    "구르는 " + ItemTooltip.trim(cfg.tumble().iframe()) + "초 동안 피할 수 있는 공격을 모두 피함. "
                            + ItemTooltip.trim(cfg.tumble().cooldown()) + "초에 한 번. /스탯 에서 끌 수 있다.");
            case CLOTH -> List.of(
                    "받는 최종 피해의 " + Text.pct(cfg.manaShield().absorb()) + "를 MP가 대신 받음 (MP 1 = 피해 "
                            + ItemTooltip.trim(cfg.manaShield().damagePerMp()) + ").",
                    "MP가 최대의 " + Text.pct(cfg.manaShield().offBelow()) + " 아래면 쉼. 지속 피해에도 든다.");
            default -> List.of();
        };
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
        Set<String> pools = new LinkedHashSet<>();
        collectItems(services.content(), t, names, pools, new HashSet<>());
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
        // 몬스터·상자 공용 장비 묶음은 장비를 하나하나 늘어놓지 않고 한 줄로 (층 숫자 없음)
        if (!pools.isEmpty()) {
            Set<String> gear = new LinkedHashSet<>();
            for (String id : pools) collectItems(services.content(), services.content().lootTable(id), gear, new HashSet<>(), new HashSet<>());
            out.add("<gray>  · 장비 " + gear.size() + "종 <dark_gray>(몬스터·상자 공용)");
        }
        return out;
    }

    /** 배율 글자: 1.35 → "1.35", 4.0 → "4". */
    static String times(double v) {
        String t = String.format(java.util.Locale.ROOT, "%.2f", v);
        while (t.contains(".") && (t.endsWith("0") || t.endsWith("."))) t = t.substring(0, t.length() - 1);
        return t;
    }

    private List<ItemStack> mobEntries() {
        List<MobDef> list = new ArrayList<>(services.content().mobs().values());
        // floor 0 (미믹 — 모든 층의 보물 상자)은 맨 뒤
        list.sort(Comparator.comparingInt((MobDef m) -> m.floor() <= 0 ? Integer.MAX_VALUE : m.floor())
                .thenComparing(m -> m.isElite() ? 1 : 0).thenComparing(MobDef::id));
        List<ItemStack> out = new ArrayList<>();
        for (MobDef m : list) {
            List<String> lore = new ArrayList<>();
            String rank = m.isElite() ? "<#ffb52e>정예" : m.isAdd() ? "<gray>소환물" : "<white>일반";
            if (kr.labyrinth.dungeon.treasure.MimicSpec.isMimic(m)) {
                // 미믹: 수치는 나오는 층 일반 몹 평균 × 배율 (MimicSpec)
                var k = m.raw().sub("mimic");
                int[] fl = kr.labyrinth.dungeon.treasure.MimicSpec.floors(m);
                String where = fl == null ? "큰 미믹과 함께" : fl[0] == fl[1] ? "지하 " + fl[0] + "층" : "지하 " + fl[0] + "~" + fl[1] + "층";
                lore.add("<gray>" + where + " 보물 상자 속 · " + rank);
                lore.add("<gray>HP <white>그 층 몬스터 ×" + times(k.dbl("hp", 4)) + "</white> · 공격 <white>×"
                        + times(k.dbl("damage", 1.3)) + "</white> · 방어 <white>×" + times(k.dbl("defense", 1)) + "</white>");
                lore.add("<gray>경험치 <white>그 층 몬스터 ×" + times(k.dbl("xp", 3)));
            } else {
                lore.add("<gray>지하 <white>" + m.floor() + "</white>층 · " + rank);
                lore.add("<gray>HP <white>" + Text.num(m.hp()) + "</white> · 공격 <white>" + Text.num(m.damage()) + "</white> · 방어 <white>"
                        + Text.num(m.defense()) + "</white> <dark_gray>(보통·보정 전)");
                lore.add("<gray>경험치 <white>" + Text.num(m.xp()));
            }
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

    /**
     * 몬스터·상자 공용 장비 묶음인가 — 층 몬스터·보물방·미로 상자가 함께 굴리는 {@code mix_fNN_drop}
     * (0.3.5, 이웃 단계 풀 PICK) 또는 옛 {@code gear_fNN_common}. 몬스터 도감은 그 장비를 하나하나 늘어놓지 않는다.
     */
    static boolean sharedPool(String tableId) {
        return tableId != null && (tableId.matches("mix_f\\d+_drop") || tableId.matches("gear_f\\d+_common"));
    }

    /** 표 이름 끝의 층 번호 ({@code mix_f03_drop} → 3, {@code gimmick_floor_4} → 4, 없으면 0). 재료·소모품 획득처에만 적는다. */
    static int floorOf(String tableId) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("(?:_f|_floor_)0*(\\d+)").matcher(tableId == null ? "" : tableId);
        return m.find() ? Integer.parseInt(m.group(1)) : 0;
    }

    /**
     * 테이블이 줄 수 있는 아이템 id (중첩 테이블·PICK·one_of 포함, rarity_pool 은 그 단계·희귀도 풀).
     * 공용 장비 묶음({@link #sharedPool})은 따라 들어가지 않고 {@code pools} 에 테이블 id 만 모은다 (pools 가 null 이면 따라 들어간다).
     * 루트 표 자신은 언제나 펼친다.
     */
    private static void collectItems(Content c, LootTable t, Set<String> out, Set<String> pools, Set<String> visiting) {
        if (t == null || !visiting.add(t.id())) return;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> { if (e.item() != null) out.add(e.item()); }
                case ONE_OF -> { if (e.oneOf() != null) out.addAll(e.oneOf()); }
                case TABLE -> {
                    if (pools != null && sharedPool(e.table())) pools.add(e.table());
                    else collectItems(c, c.lootTable(e.table()), out, pools, visiting);
                }
                case PICK -> { for (LootTable.Pick p : e.pick()) collectItems(c, c.lootTable(p.table()), out, pools, visiting); }
                case RARITY_POOL -> {
                    if (e.rarityPool() != null) for (ItemDef d : c.poolCandidates(e.floor(), e.rarityPool())) out.add(d.id());
                }
            }
        }
        visiting.remove(t.id());
    }

    /**
     * 획득처 종류 (표시 순서). 장비는 보스 · 정예 · 몬스터·상자 · 시련방 · 특별 시련 · 금고·미믹 · 대장간 · 상인 · 칭호 보상 · 시작 지급
     * 중 1~2곳이고, 보물 상자 · 몬스터 는 재료·소모품용으로 남긴다.
     */
    public static final List<String> SOURCE_GROUPS = List.of("보스", "정예", "몬스터·상자", "보물 상자", "시련방", "특별 시련",
            "금고·미믹", "광산", "제련소", "대장간", "상인", "칭호 보상", "시작 지급", "몬스터");
    /** 층을 모아 "지하 9·10층" 으로 적는 묶음 (장비는 층 없이 종류 이름만). */
    private static final Set<String> FLOOR_GROUPS = Set.of("몬스터·상자", "보물 상자", "시련방", "특별 시련", "금고·미믹");
    // 대장간 = 대장장이 (재료 ×개수 · … · 골드)
    private static final Map<String, String> SOURCE_COLORS = Map.ofEntries(Map.entry("보스", "#ff6b6b"), Map.entry("정예", "#ffb52e"),
            Map.entry("대장간", "#7fd8ff"), Map.entry("상인", "#7fe07f"), Map.entry("칭호 보상", "#c9a2ff"), Map.entry("시작 지급", "#9be89b"),
            Map.entry("특별 시련", "#9fe3ff"), Map.entry("금고·미믹", "#ffd36b"), Map.entry("광산", "#e8c58a"), Map.entry("제련소", "#ff9a5a"));
    /** 도감 툴팁에서 획득처에 비워 두는 최대 줄 수 (넘치면 장비 설명 쪽이 빈 줄·스킬 설명을 줄인다). */
    public static final int SOURCE_LINES = 6;
    /** 획득처 줄바꿈 글자 수 (툴팁 폭). */
    private static final int SOURCE_WRAP = 34;

    /** 획득처 하나: 종류 · 재료·소모품에 쓰는 글 ("테오라(9층)", 층 묶음은 층 번호) · 장비에 쓰는 글 (층 없음, 층 묶음은 null). */
    private record Src(String group, String label, String gearLabel) {
        Src(String group, String label) { this(group, label, label); }
    }

    /**
     * 아이템 id → 획득처 표시 줄. 종류별로 한 줄에 묶는다. 장비: "보스 테오라 · 대장간 …", "몬스터·상자", "시련방" (층 숫자 없음).
     * 재료·소모품: "정예 대시계 집행관(9층) · 심연의 문지기(10층)", "보물 상자 지하 9·10층". 길면 다음 줄로 이어 쓴다.
     */
    public static Map<String, List<String>> buildSources(Content c) {
        Map<String, Map<String, Set<String>>> src = new LinkedHashMap<>();
        Map<String, List<Src>> tableLabels = new LinkedHashMap<>();
        for (MobDef m : c.mobs().values()) {
            if (m.drops() == null) continue;
            String name = Text.strip(m.name()).trim();
            tableLabels.computeIfAbsent(m.drops(), k -> new ArrayList<>())
                    .add(new Src(m.isElite() ? "정예" : "몬스터", name + "(" + m.floor() + "층)", name));
        }
        for (BossDef b : c.bosses().values()) {
            if (b.drops() == null) continue;
            // 보스는 짧은 이름 ("시계탑의 간수 테오라" → "테오라") — 한 줄에 여럿 들어간다
            String name = ItemTooltip.bossShortName(b);
            tableLabels.computeIfAbsent(b.drops(), k -> new ArrayList<>()).add(new Src("보스", name + "(" + b.floor() + "층)", name));
        }
        for (String tid : c.lootTables().keySet()) {
            String group = sharedPool(tid) ? "몬스터·상자"
                    : tid.startsWith("treasure_floor_") ? "보물 상자"
                    : tid.startsWith("gimmick_floor_") ? "시련방"
                    : tid.matches("special_trial_f\\d+") ? "특별 시련"
                    : tid.matches("hoard_f\\d+") ? "금고·미믹" : null;
            if (group != null) tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src(group, String.valueOf(floorOf(tid)), null));
        }
        // 미로 상자 — Treasures·검사기와 같은 규칙으로 실제로 굴리는 표 (층별 maze_chest_<tier>_f<층>, floors.yml
        // chests.bracket 강제거나 층별 표가 없으면 구간 표) 를 보물 상자 묶음에 층으로
        for (FloorDef f : c.floors().values()) {
            int bracket = ChestSettings.of(f.raw().sub("chests")).bracket();
            for (ChestTier tier : ChestTier.values()) {
                String tid = tier.table(f.number(), bracket, c.lootTables()::containsKey);
                if (c.lootTables().containsKey(tid)) {
                    tableLabels.computeIfAbsent(tid, k -> new ArrayList<>()).add(new Src("보물 상자", String.valueOf(f.number()), null));
                }
            }
        }
        for (var e : tableLabels.entrySet()) {
            Set<String> items = new LinkedHashSet<>();
            // 공용 장비 묶음(mix_fNN_drop)은 그 표 자신만 "몬스터·상자" 로 센다 — 몹·상자 표에서 따라 들어가지 않는다
            collectItems(c, c.lootTable(e.getKey()), items, new HashSet<>(), new HashSet<>());
            for (String id : items) {
                ItemDef d = c.item(id);
                // 장비와 광산 재료는 층 숫자 없이 (0.3.6 — 광석·주괴·보석·곡괭이 글에 층 표지 없음)
                boolean gear = d != null && (d.isGear() || d.isMineMaterial() || d.isTool());
                for (Src s : e.getValue()) add(src, id, s.group(), gear ? s.gearLabel() : s.label());
            }
        }
        for (RecipeDef r : c.recipes().values()) {
            StringBuilder sb = new StringBuilder();
            int n = 0;
            for (var m : r.materials().entrySet()) {
                ItemDef md = c.item(m.getKey());
                if (n++ > 0) sb.append(", ");
                sb.append(md == null ? m.getKey() : Text.strip(md.name())).append(" ×").append(m.getValue());
            }
            if (r.gold() > 0) sb.append(n > 0 ? ", " : "").append(Text.num(r.gold())).append("G");
            boolean smelter = kr.labyrinth.mine.MineNames.STATION_SMELTER.equals(r.station());
            add(src, r.result(), smelter ? "제련소" : "대장간", sb.toString());
        }
        // 0.3.6 광산: 광석·보석이 많이 나는 층 이름 (층 번호 없이, 몫이 큰 순 2곳)
        for (String id : c.mine().ores().keySet()) for (String name : mineHomes(c, id, true)) add(src, id, "광산", name);
        for (String id : c.mine().gems().keySet()) for (String name : mineHomes(c, id, false)) add(src, id, "광산", name);
        for (NpcDef npc : c.npcs().values()) {
            if (npc.shop() == null) continue;
            for (NpcDef.ShopEntry s : npc.shop()) add(src, s.item(), "상인", ItemTooltip.shortName(npc.name()) + " " + Text.num(s.price()) + "G");
        }
        for (AchievementDef a : c.achievements().values()) {
            if (a.rewardItems() == null) continue;
            for (String id : a.rewardItems().keySet()) add(src, id, "칭호 보상", "칭호의 주인에게 한 번");
        }
        // 시작 꾸러미 (items.yml sources: [starter]) — 루팅·제작에는 없다
        for (ItemDef d : c.items().values()) {
            if (d.sources().contains("starter")) add(src, d.id(), "시작 지급", "처음 직업을 고를 때");
        }
        Map<String, List<String>> out = new LinkedHashMap<>();
        // 원문 이름에 든 MiniMessage 기호는 strip 으로 걷었으므로 그대로 써도 안전
        src.forEach((id, groups) -> out.put(id, List.copyOf(formatSources(groups))));
        return out;
    }

    /** 광석(ore=true)·보석이 많이 나는 광산 층 이름, 몫이 큰 순 최대 2곳 (층 번호 없이 이름만). */
    static List<String> mineHomes(Content c, String id, boolean ore) {
        List<MineHome> homes = new ArrayList<>();
        for (var l : c.mine().levels()) {
            Map<String, Integer> w = ore ? l.oreWeights() : l.gemWeights();
            if (w == null) continue;
            int total = 0;
            for (int v : w.values()) total += v;
            Integer mine = w.get(id);
            if (mine != null && mine > 0 && total > 0) homes.add(new MineHome(Text.strip(l.name()).trim(), mine / (double) total));
        }
        homes.sort(Comparator.comparingDouble(MineHome::share).reversed());
        List<String> out = new ArrayList<>();
        for (int i = 0; i < homes.size() && i < 2; i++) out.add(homes.get(i).name());
        return out;
    }

    private record MineHome(String name, double share) {}

    /** label == null = 층 없이 종류만 (장비의 층 묶음). */
    private static void add(Map<String, Map<String, Set<String>>> src, String id, String group, String label) {
        Set<String> labels = src.computeIfAbsent(id, k -> new LinkedHashMap<>()).computeIfAbsent(group, k -> new LinkedHashSet<>());
        if (label != null) labels.add(label);
    }

    /**
     * 종류별 한 줄 (넘치면 들여 써서 이어 감). 층 묶음(몬스터·상자·보물 상자·시련방·특별 시련·금고·미믹)은 층만 모아 "지하 9·10층",
     * 층이 없으면(장비) 종류 이름만.
     */
    static List<String> formatSources(Map<String, Set<String>> groups) {
        List<String> lines = new ArrayList<>();
        for (String g : SOURCE_GROUPS) {
            Set<String> labels = groups.get(g);
            if (labels == null) continue;
            String color = SOURCE_COLORS.getOrDefault(g, "#d0d0d0");
            List<String> parts = new ArrayList<>();
            if (FLOOR_GROUPS.contains(g)) {
                List<Integer> floors = new ArrayList<>();
                for (String l : labels) {
                    try { floors.add(Integer.parseInt(l)); } catch (NumberFormatException ignored) { }
                }
                floors.removeIf(f -> f <= 0);
                floors.sort(Integer::compare);
                List<String> fs = new ArrayList<>();
                for (int f : floors) fs.add(String.valueOf(f));
                if (!fs.isEmpty()) parts.add("지하 " + String.join("·", fs) + "층");
            } else if (g.equals("광산")) {
                parts.add("많이 나는 곳: " + String.join(" · ", labels));
            } else if (g.equals("대장간") || g.equals("제련소")) {
                for (String l : labels) parts.addAll(List.of(l.split(", "))); // 재료마다 끊어 줄바꿈
            } else {
                parts.addAll(labels);
            }
            if (parts.isEmpty()) {
                lines.add("<" + color + ">" + g);
                continue;
            }
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
