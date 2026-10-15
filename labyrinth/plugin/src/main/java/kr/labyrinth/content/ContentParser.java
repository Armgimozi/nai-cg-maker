package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.TreeMap;
import kr.labyrinth.stats.Stat;

/**
 * content/*.yml 의 원시 맵 → 타입 모델. 순수 로직(Bukkit 의존 없음)이라 단위 테스트에서도 그대로 쓴다.
 * 파싱 문제는 예외 대신 {@link #problems()} 에 모은다(한 파일이 틀려도 나머지는 로드).
 */
public final class ContentParser {

    /** 파일 이름 목록 (확장자 포함). glyphs.yml · enhance.yml 은 없어도 된다. */
    public static final List<String> FILES = List.of("classes.yml", "items.yml", "mobs.yml", "bosses.yml",
            "floors.yml", "loot.yml", "recipes.yml", "titles.yml", "npcs.yml", "fx.yml", "glyphs.yml", "enhance.yml");
    /** 없어도 되는 파일 — enhance.yml 이 없으면 모든 장비가 강화석·골드만 든다(예전 서버 그대로). */
    public static final List<String> OPTIONAL_FILES = List.of("glyphs.yml", "enhance.yml");
    /** 예전 버전이 복사해 두었지만 이제 쓰지 않는 파일 (손대지 않았으면 시작할 때 지운다). arenas.yml = 없앤 파티 대전 투기장. */
    public static final List<String> RETIRED_FILES = List.of("arenas.yml");

    private final List<String> problems = new ArrayList<>();

    public List<String> problems() { return Collections.unmodifiableList(problems); }

    private void problem(String file, String id, String msg) {
        problems.add(file + " [" + id + "] " + msg);
    }

    /** files: 파일 이름 → 원시 YAML 루트 맵 (없는 파일은 키 없음). */
    public Content parse(Map<String, Map<String, Object>> files) {
        Params classesRoot = root(files, "classes.yml");
        Params itemsRoot = root(files, "items.yml");
        Params mobsRoot = root(files, "mobs.yml");
        Params bossesRoot = root(files, "bosses.yml");
        Params floorsRoot = root(files, "floors.yml");
        Params lootRoot = root(files, "loot.yml");
        Params recipesRoot = root(files, "recipes.yml");
        Params titlesRoot = root(files, "titles.yml");
        Params npcsRoot = root(files, "npcs.yml");
        Params fxRoot = root(files, "fx.yml");
        Params glyphsRoot = root(files, "glyphs.yml");
        Params enhanceRoot = root(files, "enhance.yml");

        Map<String, ClassDef> classes = new LinkedHashMap<>();
        classesRoot.sub("classes").children().forEach((id, p) -> classes.put(id, parseClass(id, p)));

        Map<String, ItemDef> items = new LinkedHashMap<>();
        itemsRoot.sub("items").children().forEach((id, p) -> {
            ItemDef d = parseItem(id, p);
            if (d != null) items.put(id, d);
        });
        Map<String, ItemSetDef> sets = new LinkedHashMap<>();
        itemsRoot.sub("sets").children().forEach((id, p) -> sets.put(id, parseSet(id, p)));

        Map<String, MobDef> mobs = new LinkedHashMap<>();
        mobsRoot.sub("mobs").children().forEach((id, p) -> mobs.put(id, parseMob(id, p)));

        Map<String, BossDef> bosses = new LinkedHashMap<>();
        bossesRoot.sub("bosses").children().forEach((id, p) -> bosses.put(id, parseBoss(id, p)));

        NavigableMap<Integer, FloorDef> floors = new TreeMap<>();
        floorsRoot.sub("floors").children().forEach((key, p) -> {
            try {
                int n = Integer.parseInt(key.trim());
                floors.put(n, parseFloor(n, p));
            } catch (NumberFormatException e) {
                problem("floors.yml", key, "층 키는 숫자여야 함");
            }
        });

        Map<String, LootTable> loot = new LinkedHashMap<>();
        lootRoot.sub("tables").children().forEach((id, p) -> loot.put(id, parseLootTable(id, p)));
        LootTable.Settings lootSettings = parseLootSettings(lootRoot.sub("settings"));

        Map<String, RecipeDef> recipes = new LinkedHashMap<>();
        recipesRoot.sub("recipes").children().forEach((id, p) -> recipes.put(id, parseRecipe(id, p)));

        Map<String, AchievementDef> achievements = new LinkedHashMap<>();
        titlesRoot.sub("achievements").children().forEach((id, p) -> achievements.put(id, parseAchievement(id, p)));

        Map<String, NpcDef> npcs = new LinkedHashMap<>();
        npcsRoot.sub("npcs").children().forEach((id, p) -> npcs.put(id, parseNpc(id, p)));

        Map<String, AuraDef> auras = new LinkedHashMap<>();
        fxRoot.sub("auras").children().forEach((id, p) -> auras.put(id, parseAura(id, p)));
        Map<String, FxModelDef> fxModels = new LinkedHashMap<>();
        fxRoot.sub("models").children().forEach((id, p) -> fxModels.put(id, parseFxModel(id, p)));

        Map<String, GlyphDef> glyphs = new LinkedHashMap<>();
        glyphsRoot.sub("glyphs").children().forEach((id, p) -> glyphs.put(id,
                new GlyphDef(id, p.str("char", ""), p.str("file", ""), p.integer("ascent", 0), p.integer("height", 8),
                        p.integer("advance", -1))));
        Map<String, Integer> spaces = new LinkedHashMap<>();
        Params sp = glyphsRoot.sub("spaces");
        for (String k : sp.keys()) spaces.put(k, sp.integer(k, 0));

        EnhanceDef enhance = files.containsKey("enhance.yml") ? parseEnhance(enhanceRoot, items) : EnhanceDef.EMPTY;

        return new Content(
                Collections.unmodifiableMap(classes), Collections.unmodifiableMap(items),
                Collections.unmodifiableMap(sets), Collections.unmodifiableMap(mobs),
                Collections.unmodifiableMap(bosses), Collections.unmodifiableNavigableMap(floors),
                Collections.unmodifiableMap(loot), lootSettings, Collections.unmodifiableMap(recipes),
                Collections.unmodifiableMap(achievements), Collections.unmodifiableMap(npcs),
                Collections.unmodifiableMap(auras), Collections.unmodifiableMap(fxModels),
                Collections.unmodifiableMap(glyphs), Collections.unmodifiableMap(spaces), enhance);
    }

    private Params root(Map<String, Map<String, Object>> files, String name) {
        Map<String, Object> raw = files.get(name);
        if (raw == null) {
            if (!OPTIONAL_FILES.contains(name)) problem(name, "-", "파일이 없음");
            return Params.EMPTY;
        }
        Params p = Params.of(raw);
        if (p.integer("version", 1) != 1) problem(name, "-", "알 수 없는 version: " + p.str("version"));
        return p;
    }

    // ── classes ───────────────────────────────────────────────────────────

    private ClassDef parseClass(String id, Params p) {
        Map<Stat, Integer> base = new EnumMap<>(Stat.class);
        Params bs = p.sub("base_stats");
        for (String k : bs.keys()) {
            Stat s = Stat.byKey(k);
            if (s == null) problem("classes.yml", id, "알 수 없는 스탯 " + k);
            else base.put(s, bs.integer(k, 0));
        }
        Stat primary = Stat.byKey(p.str("primary_stat", "STR"));
        if (primary == null) {
            problem("classes.yml", id, "primary_stat 이 스탯이 아님: " + p.str("primary_stat"));
            primary = Stat.STR;
        }
        Params passive = p.sub("passive");
        ClassDef.PassiveDef pd = passive.isEmpty() ? null : new ClassDef.PassiveDef(passive.str("id", ""),
                passive.str("name", ""), passive.str("description", ""), passive.sub("params"));
        List<ClassDef.SkillDef> skills = new ArrayList<>();
        for (Params s : p.maps("skills")) {
            skills.add(new ClassDef.SkillDef(s.str("id", ""), s.str("name", s.str("id", "")),
                    s.str("input", "SWAP").toUpperCase(), s.integer("unlock_level", 1), s.dbl("mana", 0),
                    s.dbl("cooldown", 0), s.sub("params"), s.str("description", "")));
        }
        Params pl = p.sub("per_level");
        return new ClassDef(id, p.str("name", id), p.str("role", "melee"), p.str("color", "#ffffff"),
                p.str("description", ""), p.str("icon_item"), p.strings("weapon_types"), primary,
                Collections.unmodifiableMap(base), p.dbl("base_hp", 100), p.dbl("base_mp", 50),
                pl.dbl("hp", 0), pl.dbl("mp", 0), p.dbl("mana_regen", 1.0), pd, List.copyOf(skills), p);
    }

    // ── items ─────────────────────────────────────────────────────────────

    private ItemDef parseItem(String id, Params p) {
        ItemType type = ItemType.byId(p.str("type"));
        if (type == null) {
            problem("items.yml", id, "type 이 올바르지 않음: " + p.str("type"));
            return null;
        }
        Rarity rarity = Rarity.byId(p.str("rarity", "common"));
        if (rarity == null) {
            problem("items.yml", id, "rarity 가 올바르지 않음: " + p.str("rarity"));
            rarity = Rarity.COMMON;
        }
        Map<String, Range> stats = new LinkedHashMap<>();
        Params st = p.sub("stats");
        for (String k : st.keys()) {
            Range r = st.range(k, null);
            if (r == null) problem("items.yml", id, "stats." + k + " 는 [최소, 최대] 이어야 함");
            else stats.put(k, r);
        }
        List<ItemDef.WeaponSkillDef> ws = new ArrayList<>();
        for (Params s : p.maps("weapon_skills")) {
            Params sp = s.sub("params");
            if (s.has("mechanics")) {
                // 조합형 무기 스킬(id: mechanics, GDD §17.5): 항목의 mechanics 목록을 params.mechanics 로 옮겨 둔다
                Map<String, Object> merged = new LinkedHashMap<>(sp.asMap());
                merged.put("mechanics", s.get("mechanics"));
                sp = Params.of(merged);
            }
            ws.add(new ItemDef.WeaponSkillDef(s.str("id", ""), s.str("name", s.str("id", "")),
                    s.str("input", "RIGHT").toUpperCase(), s.dbl("cooldown", 0), s.dbl("mana", 0), sp,
                    s.str("description", "")));
        }
        StatRequirement req = StatRequirement.of(requirementStats(id, p, "requires"), requirementStats(id, p, "requires_any"));
        return new ItemDef(id, p.str("name", id), type, p.str("weapon_type"), p.str("armor_slot"),
                p.str("armor_set"), rarity, p.integer("level_req", 1), req, p.strings("classes"),
                Collections.unmodifiableMap(stats), p.str("set_bonus"), p.str("aura"), List.copyOf(ws),
                p.integer("floor", 0), p.bool("pool", true), p.strings("sources"), p.sub("use"), p.sub("model"),
                p.sub("texture"), p.str("lore", ""), p);
    }

    /** requires / requires_any: {STR: 30, ...} — 키는 STR DEX INT VIT WIS LUK, 값은 0 이상 정수 (0 = 요구 없음). */
    private Map<Stat, Integer> requirementStats(String id, Params p, String key) {
        if (!p.has(key)) return Map.of();
        if (!(p.get(key) instanceof Map<?, ?>)) {
            problem("items.yml", id, key + " 는 {STR: 30, ...} 꼴이어야 함");
            return Map.of();
        }
        Params r = p.sub(key);
        Map<Stat, Integer> out = new EnumMap<>(Stat.class);
        for (String k : r.keys()) {
            Stat s = Stat.byKey(k);
            Object raw = r.get(k);
            if (s == null) {
                problem("items.yml", id, key + "." + k + " — 능력치는 STR DEX INT VIT WIS LUK 중 하나");
            } else if (!(raw instanceof Number n) || n.doubleValue() < 0 || n.doubleValue() != Math.rint(n.doubleValue())) {
                problem("items.yml", id, key + "." + k + " 는 0 이상 정수여야 함: " + raw);
            } else if (n.intValue() > 0) {
                out.put(s, n.intValue());
            }
        }
        return out;
    }

    private ItemSetDef parseSet(String id, Params p) {
        NavigableMap<Integer, Map<String, Double>> bonuses = new TreeMap<>();
        p.sub("bonuses").children().forEach((count, b) -> {
            try {
                Map<String, Double> m = new LinkedHashMap<>();
                for (String k : b.keys()) m.put(k, b.dbl(k, 0));
                bonuses.put(Integer.parseInt(count.trim()), Collections.unmodifiableMap(m));
            } catch (NumberFormatException e) {
                problem("items.yml", "sets." + id, "bonuses 키는 착용 개수(숫자)여야 함: " + count);
            }
        });
        return new ItemSetDef(id, p.str("name", id), p.str("look", "light"), p.strings("pieces"),
                Collections.unmodifiableNavigableMap(bonuses));
    }

    // ── mobs / bosses ─────────────────────────────────────────────────────

    private ModelDef parseModel(Params m) {
        if (m.isEmpty()) return ModelDef.EMPTY;
        IntRange ts = m.intRange("texture_size", new IntRange(64, 64));
        List<ModelDef.Part> parts = new ArrayList<>();
        for (Params part : m.maps("parts")) {
            List<Double> size = part.doubles("size");
            List<Double> pivot = part.doubles("pivot");
            double px = at(pivot, 0, 0), py = at(pivot, 1, 0), pz = at(pivot, 2, 0);
            List<Double> joint = part.doubles("joint");
            List<Double> foot = part.doubles("foot");
            parts.add(new ModelDef.Part(part.str("name", "part"), part.str("form", "box"),
                    at(size, 0, 8), at(size, 1, 8), at(size, 2, 8), px, py, pz, part.str("anim", "none"),
                    part.str("set"), at(joint, 0, px), at(joint, 1, py), at(joint, 2, pz),
                    foot.size() >= 3 ? new ModelDef.Foot(foot.get(0), foot.get(1), foot.get(2), at(foot, 3, 0)) : null));
        }
        // texture_size 는 [w, h] → IntRange(min,max) 로 읽으면 정렬되므로 직접 읽는다
        List<Double> tsz = m.doubles("texture_size");
        int w = tsz.isEmpty() ? ts.min() : tsz.get(0).intValue();
        int h = tsz.size() > 1 ? tsz.get(1).intValue() : w;
        return new ModelDef(w, h, List.copyOf(parts), m.sub("style"));
    }

    private static double at(List<Double> l, int i, double def) {
        return l.size() > i ? l.get(i) : def;
    }

    private List<MobDef.MobSkillDef> parseMobSkills(Params p) {
        List<MobDef.MobSkillDef> out = new ArrayList<>();
        for (Params s : p.maps("skills")) out.add(new MobDef.MobSkillDef(s.str("type", ""), s.dbl("cooldown", 0), s.sub("params")));
        return List.copyOf(out);
    }

    private MobDef parseMob(String id, Params p) {
        return new MobDef(id, p.str("name", id), p.str("description", ""), p.integer("floor", 1),
                p.str("rank", "normal"), p.str("base", "HUSK"), p.dbl("scale", 1.0), p.dbl("hp", 20),
                p.dbl("damage", 1), p.dbl("defense", 0), p.dbl("speed", 0.25), p.dbl("xp", 0),
                p.intRange("gold", IntRange.ZERO), p.str("ai", "melee"), parseMobSkills(p), p.str("drops"),
                p.bool("flying", false), p.sub("sounds"), parseModel(p.sub("model")), p);
    }

    private BossDef parseBoss(String id, Params p) {
        Map<String, String> lines = new LinkedHashMap<>();
        Params l = p.sub("lines");
        for (String k : l.keys()) lines.put(k, l.str(k, ""));
        Map<Integer, List<String>> rotation = new TreeMap<>();
        Params rot = p.sub("rotation");
        for (String k : rot.keys()) {
            try {
                rotation.put(Integer.parseInt(k.trim()), rot.strings(k));
            } catch (NumberFormatException e) {
                problem("bosses.yml", id, "rotation 키는 페이즈 번호여야 함: " + k);
            }
        }
        Map<String, Params> patterns = new LinkedHashMap<>(p.sub("patterns").children());
        List<Double> phases = p.doubles("phases");
        if (phases.isEmpty()) phases = List.of(1.0);
        return new BossDef(id, p.str("name", id), p.integer("floor", 1), p.str("title", ""), p.str("core", ""),
                p.str("description", ""), p.str("base", "IRON_GOLEM"), p.dbl("scale", 1.0), p.dbl("hp", 1000),
                p.dbl("damage", 10), p.dbl("defense", 0), p.dbl("speed", 0.25), phases, p.dbl("xp", 0),
                p.intRange("gold", IntRange.ZERO), p.str("drops"), p.str("bossbar", "RED"), p.sub("arena"),
                Collections.unmodifiableMap(lines), Collections.unmodifiableMap(rotation),
                Collections.unmodifiableMap(patterns), p.sub("sounds"), parseModel(p.sub("model")),
                p.bool("flying", false), p);
    }

    // ── floors ────────────────────────────────────────────────────────────

    private static Map<String, List<String>> palette(Params pal) {
        Map<String, List<String>> out = new LinkedHashMap<>();
        for (String k : pal.keys()) out.put(k, pal.strings(k));
        return Collections.unmodifiableMap(out);
    }

    private FloorDef parseFloor(int n, Params p) {
        Map<String, Integer> rooms = new LinkedHashMap<>();
        Params r = p.sub("rooms");
        for (String k : r.keys()) rooms.put(k, r.integer(k, 0));
        return new FloorDef(n, p.str("name", "지하 " + n + "층"), p.str("subtitle", "지하 " + n + "층"),
                p.str("theme", "default"), p.intRange("level_range", new IntRange(1, 50)), p.str("description", ""),
                palette(p.sub("palette")), p.maps("decor"), p.str("liquid"), p.integer("room_height", 5),
                p.sub("size").integer("cells", 6), Collections.unmodifiableMap(rooms),
                p.intRange("mob_density", new IntRange(3, 5)), p.strings("mobs"), p.str("elite"), p.str("boss"),
                p.str("gimmick"), p.sub("gimmick_params"), p.sub("ambient"), p);
    }

    // ── loot ──────────────────────────────────────────────────────────────

    private LootTable.Entry parseLootEntry(String table, Params e) {
        double chance = e.dbl("chance", 1.0);
        IntRange amount = e.intRange("amount", IntRange.ONE);
        String minDiff = e.str("min_difficulty");
        if (e.has("item")) {
            return new LootTable.Entry(LootTable.Kind.ITEM, e.str("item"), null, 0, List.of(), null, chance, amount, minDiff);
        }
        if (e.has("rarity_pool")) {
            Rarity r = Rarity.byId(e.str("rarity_pool"));
            if (r == null) {
                problem("loot.yml", table, "rarity_pool 희귀도가 올바르지 않음: " + e.str("rarity_pool"));
                return null;
            }
            return new LootTable.Entry(LootTable.Kind.RARITY_POOL, null, r, e.integer("floor", 1), List.of(), null,
                    chance, amount, minDiff);
        }
        if (e.has("one_of")) {
            return new LootTable.Entry(LootTable.Kind.ONE_OF, null, null, 0, e.strings("one_of"), null, chance, amount, minDiff);
        }
        if (e.has("table")) {
            return new LootTable.Entry(LootTable.Kind.TABLE, null, null, 0, List.of(), e.str("table"), chance, amount, minDiff);
        }
        problem("loot.yml", table, "항목 종류를 알 수 없음(item/rarity_pool/one_of/table): " + e);
        return null;
    }

    private LootTable parseLootTable(String id, Params p) {
        List<LootTable.Entry> entries = new ArrayList<>();
        for (Params e : p.maps("entries")) {
            LootTable.Entry le = parseLootEntry(id, e);
            if (le != null) entries.add(le);
        }
        List<LootTable.Entry> guaranteed = new ArrayList<>();
        for (Params e : p.maps("guaranteed")) {
            LootTable.Entry le = parseLootEntry(id, e);
            if (le != null) guaranteed.add(le);
        }
        return new LootTable(id, Math.max(1, p.integer("rolls", 1)), List.copyOf(entries), List.copyOf(guaranteed),
                p.intRange("gold", IntRange.ZERO));
    }

    private LootTable.Settings parseLootSettings(Params s) {
        if (s.isEmpty()) return LootTable.Settings.DEFAULT;
        Map<String, Map<String, Double>> rw = new LinkedHashMap<>();
        s.sub("rarity_weight").children().forEach((diff, m) -> {
            Map<String, Double> w = new LinkedHashMap<>();
            for (String k : m.keys()) w.put(k, m.dbl(k, 1.0));
            rw.put(diff, Collections.unmodifiableMap(w));
        });
        Params rwp = s.sub("rarity_weight");
        for (String k : rwp.keys()) rw.putIfAbsent(k, Map.of()); // normal: {} 처럼 빈 맵
        Rarity ann = Rarity.byId(s.str("announce_rarity", "legendary"));
        return new LootTable.Settings(s.dbl("own_class_bias", 0.65), s.dbl("luck_per_point", 0.005),
                s.dbl("party_bonus_per_member", 0.05), s.dbl("max_chance", 1.0), Collections.unmodifiableMap(rw),
                ann == null ? Rarity.LEGENDARY : ann);
    }

    // ── recipes / titles / npcs / fx ─────────────────────────────

    // ── enhance ───────────────────────────────────────────────────────────

    /**
     * enhance.yml → 장비별 강화 재료. 틀린 줄은 문제(problems) 대신 {@link EnhanceDef#warnings()} 에 모은다 —
     * 강화 재료가 틀려도 콘텐츠 전체는 정상이고, 그 줄만 빠진다(강화 서비스가 시작할 때 경고).
     * items.yml 에 아직 없는 장비 항목(다른 작업으로 들어올 새 장비)은 조용히 건너뛰고 개수만 한 줄로 알린다.
     */
    private EnhanceDef parseEnhance(Params root, Map<String, ItemDef> items) {
        List<String> warn = new ArrayList<>();
        List<EnhanceDef.Band> bands = new ArrayList<>();
        Params bs = root.sub("bands");
        for (String id : bs.keys()) {
            List<Double> r = bs.doubles(id);
            if (r.size() != 2 || r.get(0) < 1 || r.get(1) < r.get(0)) {
                warn.add("bands." + id + " 는 [시작, 끝] (목표 단계, 1 이상) 이어야 함: " + bs.get(id));
                continue;
            }
            bands.add(new EnhanceDef.Band(id, r.get(0).intValue(), r.get(1).intValue()));
        }
        if (bands.isEmpty()) bands.addAll(EnhanceDef.DEFAULT_BANDS);
        bands.sort((a, b) -> Integer.compare(a.from(), b.from()));
        java.util.Set<String> bandIds = new java.util.HashSet<>();
        for (EnhanceDef.Band b : bands) bandIds.add(b.id());

        Map<String, Map<String, List<EnhanceDef.Material>>> out = new LinkedHashMap<>();
        List<String> unknownItems = new ArrayList<>();
        root.sub("items").children().forEach((id, p) -> {
            ItemDef def = items.get(id);
            if (def == null) {
                unknownItems.add(id);
                return;
            }
            if (def.type() != ItemType.WEAPON && def.type() != ItemType.ARMOR) {
                warn.add(id + ": 무기·방어구·방패만 강화할 수 있어 무시");
                return;
            }
            Map<String, List<EnhanceDef.Material>> entry = new LinkedHashMap<>();
            for (String band : p.keys()) {
                if (!bandIds.contains(band)) {
                    warn.add(id + "." + band + ": bands 에 없는 구간이라 무시");
                    continue;
                }
                Params mats = p.sub(band);
                List<EnhanceDef.Material> list = new ArrayList<>();
                for (String mat : mats.keys()) {
                    ItemDef md = items.get(mat);
                    if (md == null) {
                        warn.add(id + "." + band + ": 없는 재료 " + mat + " — 이 줄 무시");
                        continue;
                    }
                    if (md.type() != ItemType.MATERIAL) {
                        warn.add(id + "." + band + ": " + mat + " 은 재료(material)가 아니라 무시");
                        continue;
                    }
                    List<Integer> amounts = enhanceAmounts(mats.get(mat));
                    if (amounts.isEmpty()) {
                        warn.add(id + "." + band + "." + mat + ": 개수는 숫자나 숫자 목록이어야 함 — 이 줄 무시");
                        continue;
                    }
                    list.add(new EnhanceDef.Material(mat, amounts));
                }
                entry.put(band, List.copyOf(list));
            }
            out.put(id, Collections.unmodifiableMap(entry));
        });
        if (!unknownItems.isEmpty()) {
            warn.add("items.yml 에 없는 장비 " + unknownItems.size() + "개 건너뜀 (예: "
                    + String.join(", ", unknownItems.subList(0, Math.min(5, unknownItems.size()))) + ")");
        }
        return new EnhanceDef(true, List.copyOf(bands), Collections.unmodifiableMap(out), List.copyOf(warn));
    }

    /** 개수: 숫자 하나 또는 숫자 목록 (음수는 0). 아니면 빈 목록. */
    private static List<Integer> enhanceAmounts(Object v) {
        if (v instanceof Number n) return List.of(Math.max(0, n.intValue()));
        List<Integer> out = new ArrayList<>();
        if (v instanceof List<?> l) {
            for (Object o : l) {
                if (!(o instanceof Number n)) return List.of();
                out.add(Math.max(0, n.intValue()));
            }
        }
        return List.copyOf(out);
    }

    private RecipeDef parseRecipe(String id, Params p) {
        Map<String, Integer> mats = new LinkedHashMap<>();
        Params m = p.sub("materials");
        for (String k : m.keys()) mats.put(k, m.integer(k, 1));
        return new RecipeDef(id, p.str("result", id), p.str("category", "material"), p.str("station", "blacksmith"),
                Collections.unmodifiableMap(mats), p.integer("gold", 0), p.integer("level_req", 1),
                Math.max(1, p.integer("amount", 1)));
    }

    private AchievementDef parseAchievement(String id, Params p) {
        Params cond = p.sub("condition");
        Map<String, Double> bonus = new LinkedHashMap<>();
        Params b = p.sub("bonus");
        for (String k : b.keys()) bonus.put(k, b.dbl(k, 0));
        Params reward = p.sub("reward");
        Map<String, Integer> rewardItems = new LinkedHashMap<>();
        Params ri = reward.sub("items");
        for (String k : ri.keys()) rewardItems.put(k, ri.integer(k, 1));
        return new AchievementDef(id, p.str("name", id), p.str("description", ""), p.str("category", "growth"),
                cond.str("type", "").toUpperCase(), cond, p.str("title", p.str("name", id)),
                Collections.unmodifiableMap(bonus), p.bool("broadcast", false), p.bool("hidden", false),
                reward.integer("gold", 0), Collections.unmodifiableMap(rewardItems));
    }

    private NpcDef parseNpc(String id, Params p) {
        List<NpcDef.ShopEntry> shop = new ArrayList<>();
        for (Params s : p.maps("shop")) {
            shop.add(new NpcDef.ShopEntry(s.str("item", ""), s.integer("price", 0), s.integer("level_req", 1)));
        }
        return new NpcDef(id, p.str("name", id), p.str("nameplate", ""), p.str("skin", id), p.str("role", "lore"),
                p.str("placement", "overworld"), p.integer("floor", 0), p.strings("dialogue"), List.copyOf(shop),
                p.sub("skin_style"), p);
    }

    private AuraDef parseAura(String id, Params p) {
        return new AuraDef(id, p.str("tier", "legendary"), p.maps("particles"), p.str("ring_model"),
                p.dbl("ring_spin", 0), p.dbl("ring_scale", 1.0), p.dbl("ring_height", 0.05), p.bool("ring_step", false),
                p.str("secondary_model"), p.dbl("secondary_spin", 0), p.str("secondary_mode", "ring"),
                Math.max(1, p.integer("interval", 3)), p.sub("swing"), p);
    }

    private FxModelDef parseFxModel(String id, Params p) {
        List<Integer> size = new ArrayList<>();
        for (Double d : p.doubles("size")) size.add(d.intValue());
        return new FxModelDef(id, p.str("style", ""), p.str("motif"), p.str("shape"), p.strings("palette"),
                p.bool("animated", false), p.integer("frames", 1), p.integer("frametime", 2), List.copyOf(size),
                p.bool("flat", false), p.bool("glow", false), p.str("billboard", "FIXED"));
    }
}
