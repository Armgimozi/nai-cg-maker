package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.TreeMap;

/**
 * 로드된 콘텐츠 전체 (불변 스냅샷). {@code /labadmin reload} 하면 새 인스턴스로 교체되므로
 * 오래 들고 있지 말고 매번 {@code services.content()} 로 얻는다.
 */
public record Content(
        Map<String, ClassDef> classes,
        Map<String, ItemDef> items,
        Map<String, ItemSetDef> sets,
        Map<String, MobDef> mobs,
        Map<String, BossDef> bosses,
        NavigableMap<Integer, FloorDef> floors,
        Map<String, LootTable> lootTables,
        LootTable.Settings lootSettings,
        Map<String, RecipeDef> recipes,
        Map<String, AchievementDef> achievements,
        Map<String, NpcDef> npcs,
        Map<String, AuraDef> auras,
        Map<String, FxModelDef> fxModels,
        Map<String, GlyphDef> glyphs,
        Map<String, Integer> spaces,
        EnhanceDef enhance,
        MineDef mine) {

    public Content {
        if (enhance == null) enhance = EnhanceDef.EMPTY;
        if (mine == null) mine = MineDef.EMPTY;
    }

    /** mine.yml(광산, 0.3.6)이 생기기 전 모양 — 광산 없음. */
    public Content(Map<String, ClassDef> classes, Map<String, ItemDef> items, Map<String, ItemSetDef> sets,
                   Map<String, MobDef> mobs, Map<String, BossDef> bosses, NavigableMap<Integer, FloorDef> floors,
                   Map<String, LootTable> lootTables, LootTable.Settings lootSettings, Map<String, RecipeDef> recipes,
                   Map<String, AchievementDef> achievements, Map<String, NpcDef> npcs, Map<String, AuraDef> auras,
                   Map<String, FxModelDef> fxModels, Map<String, GlyphDef> glyphs, Map<String, Integer> spaces, EnhanceDef enhance) {
        this(classes, items, sets, mobs, bosses, floors, lootTables, lootSettings, recipes, achievements, npcs, auras,
                fxModels, glyphs, spaces, enhance, MineDef.EMPTY);
    }

    /** enhance.yml(장비별 강화 재료)이 생기기 전 모양 — 재료 없음(강화석·골드만). */
    public Content(Map<String, ClassDef> classes, Map<String, ItemDef> items, Map<String, ItemSetDef> sets,
                   Map<String, MobDef> mobs, Map<String, BossDef> bosses, NavigableMap<Integer, FloorDef> floors,
                   Map<String, LootTable> lootTables, LootTable.Settings lootSettings, Map<String, RecipeDef> recipes,
                   Map<String, AchievementDef> achievements, Map<String, NpcDef> npcs, Map<String, AuraDef> auras,
                   Map<String, FxModelDef> fxModels, Map<String, GlyphDef> glyphs, Map<String, Integer> spaces) {
        this(classes, items, sets, mobs, bosses, floors, lootTables, lootSettings, recipes, achievements, npcs, auras,
                fxModels, glyphs, spaces, EnhanceDef.EMPTY);
    }

    public static Content empty() {
        return new Content(Map.of(), Map.of(), Map.of(), Map.of(), Map.of(), new TreeMap<>(), Map.of(),
                LootTable.Settings.DEFAULT, Map.of(), Map.of(), Map.of(), Map.of(), Map.of(), Map.of(), Map.of(), EnhanceDef.EMPTY,
                MineDef.EMPTY);
    }

    public ClassDef classDef(String id) { return id == null ? null : classes.get(id); }
    public ItemDef item(String id) { return id == null ? null : items.get(id); }
    public MobDef mob(String id) { return id == null ? null : mobs.get(id); }
    public BossDef boss(String id) { return id == null ? null : bosses.get(id); }
    public FloorDef floor(int n) { return floors.get(n); }
    public LootTable lootTable(String id) { return id == null ? null : lootTables.get(id); }
    public int maxFloor() { return floors.isEmpty() ? 0 : floors.lastKey(); }

    /** 층 보스 정의 (floors.yml 의 boss). */
    public BossDef bossOfFloor(int floor) {
        FloorDef f = floors.get(floor);
        return f == null ? null : bosses.get(f.boss());
    }

    /** rarity_pool 후보: 단계(tier) 일치·희귀도 일치·pool != false·장비 (loot.yml 의 rarity_pool 항목 floor 값 = 단계). */
    public List<ItemDef> poolCandidates(int tier, Rarity rarity) {
        List<ItemDef> out = new ArrayList<>();
        for (ItemDef d : items.values()) {
            if (d.isGear() && d.tier() == tier && d.rarity() == rarity && d.pool()) out.add(d);
        }
        return out;
    }

    /** 세트 피스가 속한 세트들. */
    public ItemSetDef setOf(ItemDef item) {
        if (item == null || item.setBonus() == null) return null;
        return sets.get(item.setBonus());
    }

    public String summary() {
        return "직업 " + classes.size() + ", 아이템 " + items.size() + ", 세트 " + sets.size() + ", 몹 " + mobs.size()
                + ", 보스 " + bosses.size() + ", 층 " + floors.size() + ", 루팅 " + lootTables.size()
                + ", 레시피 " + recipes.size() + ", 칭호 " + achievements.size() + ", NPC " + npcs.size()
                + ", 아우라 " + auras.size() + ", 이펙트 " + fxModels.size() + ", 글리프 " + glyphs.size()
                + ", 강화 재료 " + enhance.items().size() + ", 광산 층 " + mine.levels().size();
    }
}
