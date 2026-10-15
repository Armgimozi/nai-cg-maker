package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.AuraDef;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.GlyphDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.WeaponTypes;

/**
 * 콘텐츠 교차참조 검사 (ARCHITECTURE §8). 시작·reload 때와 단위 테스트에서 실행.
 * errors = 게임이 깨지는 문제, warnings = 동작은 하지만 의심스러운 것.
 */
public final class ContentValidator {

    public record Report(List<String> errors, List<String> warnings) {
        public boolean ok() { return errors.isEmpty(); }
    }

    // ── 닫힌 목록 (GDD 가 원본) ───────────────────────────────────────────
    public static final Set<String> ROLES = Set.of("tank", "melee", "ranged", "magic", "healer", "assassin");
    public static final Set<String> CLASS_INPUTS = Set.of("SWAP", "SNEAK_SWAP", "DROP", "SNEAK_DROP");
    public static final Set<String> WEAPON_INPUTS = Set.of("LEFT", "RIGHT", "SNEAK_LEFT", "SNEAK_RIGHT");
    public static final Set<String> ARMOR_SLOTS = Set.of("head", "chest", "legs", "feet", "offhand");
    /** GDD §11.7 아이템 스탯 키 26개. */
    public static final Set<String> ITEM_STAT_KEYS = Set.of("damage", "STR", "DEX", "INT", "VIT", "WIS", "LUK", "hp", "mp",
            "defense", "crit_chance", "crit_damage", "attack_speed", "move_speed", "cooldown_reduction", "skill_damage",
            "mana_regen", "hp_regen", "heal_power", "lifesteal", "damage_reduction", "evasion", "block_chance",
            "gold_bonus", "xp_bonus", "craft_discount");
    /** GDD §17.2 무기 스킬 구현 17개. */
    public static final Set<String> WEAPON_SKILLS = Set.of("slash_wave", "dash_strike", "leap_slam", "nova", "fissure",
            "missile", "beam", "chain_bolt", "rain_zone", "whirlwind", "shadow_step", "empower", "sanctuary", "mend",
            "riposte", "vortex", "blade_orbit");
    /** GDD §11.9 소모품 action. */
    public static final Set<String> USE_ACTIONS = Set.of("heal", "mana", "restore", "cleanse", "buff", "return",
            "stat_reset", "revive");
    /** GDD §9.1 몹 스킬 26종. */
    public static final Set<String> MOB_SKILLS = Set.of("leap", "charge", "slam", "cleave", "projectile", "beam",
            "breath", "shield", "summon", "blink", "heal_allies", "buff_allies", "snare", "pull", "debuff", "stealth",
            "reflect", "life_drain", "trail", "aura", "explode_on_death", "split_on_death", "enrage", "ambush",
            "burrow", "dive");
    /** GDD §9.2 상태이상 14종. */
    public static final Set<String> EFFECTS = Set.of("poison", "bleed", "burn", "slow", "root", "stun", "weaken",
            "vulnerable", "blind", "silence", "frost", "infection", "knockback", "damage");
    public static final Set<String> AI_TYPES = Set.of("melee", "ranged", "caster", "charger", "swarm", "turret");
    /** 스폰 때 비행형이 되는 베이스 (mobs.MobServiceImpl: BAT·BLAZE·ALLAY + BAT 로 대체되는 VEX·PHANTOM). */
    public static final Set<String> FLYING_BASES = Set.of("BAT", "BLAZE", "ALLAY", "VEX", "PHANTOM");
    public static final Set<String> MOB_RANKS = Set.of("normal", "elite", "add");
    public static final Set<String> CONDITIONS = Set.of("FIRST_CLEAR", "CLEAR", "SOLO_CLEAR", "NO_DEATH_CLEAR",
            "DIFFICULTY_CLEAR", "SPEED_CLEAR", "KILL", "BOSS_KILL", "LEVEL", "OBTAIN_RARITY", "CRAFT", "ENHANCE", "TREASURE");
    public static final Set<String> TREASURE_KINDS = Set.of("chest", "gold_chest", "vault", "mimic");
    public static final Set<String> TITLE_BONUS_KEYS = Set.of("STR", "DEX", "INT", "VIT", "WIS", "LUK", "xp_bonus", "gold_bonus");
    public static final Set<String> NPC_ROLES = Set.of("entrance", "blacksmith", "class_master", "title_keeper", "merchant", "lore");
    public static final Set<String> DIFFICULTIES = Set.of("easy", "normal", "hard", "nightmare");
    public static final Set<String> RECIPE_CATEGORIES = Set.of("weapon", "armor", "accessory", "material");

    private final Content c;
    private final List<String> errors = new ArrayList<>();
    private final List<String> warnings = new ArrayList<>();

    private ContentValidator(Content c) {
        this.c = c;
    }

    public static Report validate(Content content) {
        ContentValidator v = new ContentValidator(content);
        v.run();
        return new Report(List.copyOf(v.errors), List.copyOf(v.warnings));
    }

    private void err(String where, String msg) { errors.add(where + ": " + msg); }
    private void warn(String where, String msg) { warnings.add(where + ": " + msg); }

    private void run() {
        classes();
        items();
        sets();
        mobs();
        bosses();
        floors();
        loot();
        recipes();
        gearHomes();
        titles();
        npcs();
        fx();
        glyphs();
    }

    private void requireItem(String where, String id) {
        if (id == null || id.isBlank()) err(where, "아이템 id 비어 있음");
        else if (!c.items().containsKey(id)) err(where, "없는 아이템 '" + id + "'");
    }

    private void requireMob(String where, String id) {
        if (id == null || !c.mobs().containsKey(id)) err(where, "없는 몹 '" + id + "'");
    }

    private void requireTable(String where, String id) {
        if (id == null || !c.lootTables().containsKey(id)) err(where, "없는 루팅 테이블 '" + id + "'");
    }

    private void requireFx(String where, String id) {
        if (id != null && !c.fxModels().containsKey(id)) err(where, "없는 fx 모델 '" + id + "'");
    }

    private void classes() {
        if (c.classes().isEmpty()) err("classes.yml", "직업이 하나도 없음");
        Set<String> weaponTypes = new HashSet<>();
        for (ItemDef d : c.items().values()) if (d.weaponType() != null) weaponTypes.add(d.weaponType());
        for (ClassDef d : c.classes().values()) {
            String w = "classes." + d.id();
            if (!ROLES.contains(d.role())) err(w, "role 이 올바르지 않음: " + d.role());
            if (d.iconItem() != null) requireItem(w + ".icon_item", d.iconItem());
            for (String wt : d.weaponTypes()) {
                if (!weaponTypes.contains(wt)) warn(w, "weapon_type '" + wt + "' 을 쓰는 무기가 없음");
            }
            Set<String> inputs = new HashSet<>();
            for (ClassDef.SkillDef s : d.skills()) {
                if (!CLASS_INPUTS.contains(s.input())) err(w + ".skills." + s.id(), "input 이 올바르지 않음: " + s.input());
                if (!inputs.add(s.input())) err(w + ".skills." + s.id(), "같은 input 을 쓰는 스킬이 둘: " + s.input());
                if (s.id().isBlank()) err(w, "스킬 id 비어 있음");
                checkFxParams(w + ".skills." + s.id(), s.params());
            }
            if (d.baseHp() <= 0) err(w, "base_hp 는 양수");
        }
    }

    private void checkFxParams(String where, Params p) {
        for (String k : p.keys()) {
            if (isFxKey(k) && p.get(k) instanceof String s) requireFx(where + ".params." + k, s);
        }
    }

    private void items() {
        if (c.items().isEmpty()) err("items.yml", "아이템이 하나도 없음");
        for (ItemDef d : c.items().values()) {
            String w = "items." + d.id();
            if (d.type() == ItemType.WEAPON && (d.weaponType() == null || d.weaponType().isBlank())) {
                err(w, "무기인데 weapon_type 이 없음");
            } else if (d.type() == ItemType.WEAPON) {
                if (!WeaponTypes.known(d.weaponType())) warn(w, "weapon_type '" + d.weaponType() + "' 의 피해 배율(WeaponTypes)이 없음 — 직업 스킬 환산 1.0");
                // classes = 추천 직업(드롭 편향) — classes.yml weapon_types(재사용 대기 보너스)와 어긋나면 표시가 헷갈린다
                for (String cls : d.classes()) {
                    ClassDef cd = c.classes().get(cls);
                    if (cd != null && !cd.recommendsWeapon(d.weaponType())) warn(w, "추천 직업 '" + cls + "' 의 weapon_types 에 '" + d.weaponType() + "' 이 없음");
                }
            }
            if (d.type() == ItemType.ARMOR && (d.armorSlot() == null || !ARMOR_SLOTS.contains(d.armorSlot()))) {
                err(w, "방어구 armor_slot 이 올바르지 않음: " + d.armorSlot());
            }
            if (d.armorSlot() != null && !ARMOR_SLOTS.contains(d.armorSlot())) err(w, "armor_slot 이 올바르지 않음: " + d.armorSlot());
            if (d.setBonus() != null && !c.sets().containsKey(d.setBonus())) err(w, "없는 세트 '" + d.setBonus() + "'");
            if (d.aura() != null && !c.auras().containsKey(d.aura())) err(w, "없는 아우라 '" + d.aura() + "'");
            for (String cls : d.classes()) if (!c.classes().containsKey(cls)) err(w, "없는 직업 '" + cls + "'");
            for (String k : d.stats().keySet()) if (!ITEM_STAT_KEYS.contains(k)) err(w, "알 수 없는 스탯 키 '" + k + "'");
            if (d.isGear() && (d.floor() < 0 || d.floor() > 10)) err(w, "floor 는 1~10");
            Set<String> inputs = new HashSet<>();
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                String sw = w + ".weapon_skills." + s.id();
                if ("mechanics".equals(s.id())) {
                    mechanics(sw, d, s);
                } else if (!WEAPON_SKILLS.contains(s.id())) err(sw, "알 수 없는 무기 스킬 구현 id");
                if (!WEAPON_INPUTS.contains(s.input())) err(sw, "input 이 올바르지 않음: " + s.input());
                if (!inputs.add(s.input())) err(sw, "같은 input 을 쓰는 무기 스킬이 둘: " + s.input());
                checkFxParams(sw, s.params());
            }
            if (d.type() == ItemType.CONSUMABLE) {
                String action = d.use().str("action");
                if (action == null || !USE_ACTIONS.contains(action)) err(w, "소모품 use.action 이 올바르지 않음: " + action);
            }
            if (d.rarity().atLeast(Rarity.LEGENDARY) && d.isWeapon() && d.aura() == null) {
                warn(w, "전설/신화 무기인데 aura 가 없음");
            }
        }
    }

    /** 조합형 무기 스킬(id: mechanics, GDD §17.5) — 부품·효과 문법, fx 모델 참조, 활 입력 규칙. */
    private void mechanics(String sw, ItemDef d, ItemDef.WeaponSkillDef s) {
        Object raw = s.params().get("mechanics");
        if (raw == null) {
            err(sw, "id: mechanics 인데 mechanics 목록이 없음");
            return;
        }
        kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.Result r =
                kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.parse(raw);
        for (String p : r.problems()) err(sw, p);
        for (String fx : r.displays()) requireFx(sw + ".mechanics.display", fx);
        if (s.name() == null || s.name().isBlank() || s.name().equals("mechanics")) warn(sw, "조합형 스킬에 name 이 없음");
        if (s.cooldown() <= 0) warn(sw, "조합형 스킬의 cooldown 이 0");
    }

    private void sets() {
        for (ItemSetDef s : c.sets().values()) {
            String w = "sets." + s.id();
            if (s.pieces().isEmpty()) err(w, "pieces 비어 있음");
            for (String p : s.pieces()) {
                requireItem(w + ".pieces", p);
                ItemDef d = c.item(p);
                if (d != null && !s.id().equals(d.setBonus())) warn(w, "피스 '" + p + "' 의 set_bonus 가 이 세트가 아님");
            }
            s.bonuses().forEach((n, m) -> {
                for (String k : m.keySet()) if (!ITEM_STAT_KEYS.contains(k)) err(w + ".bonuses." + n, "알 수 없는 스탯 키 '" + k + "'");
            });
        }
    }

    private void mobSkills(String w, List<MobDef.MobSkillDef> skills) {
        for (MobDef.MobSkillDef s : skills) {
            String sw = w + ".skills." + s.type();
            if (!MOB_SKILLS.contains(s.type())) err(sw, "알 수 없는 몹 스킬 타입");
            String mob = s.params().str("mob");
            if (mob != null) requireMob(sw + ".params.mob", mob);
            String effect = s.params().str("effect");
            if (effect != null && !EFFECTS.contains(effect)) err(sw, "알 수 없는 상태이상 '" + effect + "'");
            String fx = s.params().str("fx");
            requireFx(sw + ".params.fx", fx);
        }
    }

    private void mobs() {
        if (c.mobs().isEmpty()) err("mobs.yml", "몹이 하나도 없음");
        for (MobDef m : c.mobs().values()) {
            String w = "mobs." + m.id();
            if (!AI_TYPES.contains(m.ai())) err(w, "ai 가 올바르지 않음: " + m.ai());
            if (!MOB_RANKS.contains(m.rank())) err(w, "rank 가 올바르지 않음: " + m.rank());
            if (m.hp() <= 0) err(w, "hp 는 양수");
            if (m.drops() != null) requireTable(w + ".drops", m.drops());
            else if (!m.isAdd()) warn(w, "drops 가 없음(소환물이 아닌데)");
            if (!isEntityType(m.base())) err(w, "base 엔티티 타입이 올바르지 않음: " + m.base());
            mobSkills(w, m.skills());
            boolean flies = m.flying() || (m.base() != null && FLYING_BASES.contains(m.base().toUpperCase(java.util.Locale.ROOT)));
            for (MobDef.MobSkillDef s : m.skills()) {
                if ("dive".equals(s.type()) && !flies) err(w + ".skills.dive", "dive 는 비행 몹(flying: true 또는 비행 베이스)만 쓸 수 있음");
                if ("burrow".equals(s.type()) && flies) err(w + ".skills.burrow", "burrow 는 땅 위 몹만 쓸 수 있음");
            }
            if (m.model().parts().isEmpty()) err(w, "model.parts 가 비어 있음");
        }
    }

    private static boolean isEntityType(String name) {
        if (name == null) return false;
        try {
            org.bukkit.entity.EntityType.valueOf(name.toUpperCase(java.util.Locale.ROOT));
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        } catch (Throwable t) {
            return true; // 테스트 환경에서 레지스트리 초기화 실패 시 검사 생략
        }
    }

    private void bosses() {
        Map<Integer, String> byFloor = new HashMap<>();
        for (BossDef b : c.bosses().values()) {
            String w = "bosses." + b.id();
            if (b.drops() != null) requireTable(w + ".drops", b.drops());
            else err(w, "보스 drops 가 없음");
            String prev = byFloor.put(b.floor(), b.id());
            if (prev != null) err(w, "floor " + b.floor() + " 보스가 둘: " + prev);
            if (!isEntityType(b.base())) err(w, "base 엔티티 타입이 올바르지 않음: " + b.base());
            if (b.phases().isEmpty() || Math.abs(b.phases().get(0) - 1.0) > 1e-6) warn(w, "phases 첫 값은 1.0 이어야 함");
            b.rotation().forEach((phase, keys) -> {
                for (String k : keys) {
                    if (!b.patterns().containsKey(k)) err(w + ".rotation." + phase, "patterns 에 없는 패턴 '" + k + "'");
                }
            });
            b.patterns().forEach((k, p) -> {
                String add = p.str("add");
                if (add != null) requireMob(w + ".patterns." + k + ".add", add);
                String mob = p.str("mob");
                if (mob != null && c.mobs().containsKey(mob) == false && mob.matches("[a-z0-9_]+")) {
                    requireMob(w + ".patterns." + k + ".mob", mob);
                }
                for (String pk : p.keys()) {
                    if (isFxKey(pk) && p.get(pk) instanceof String s) requireFx(w + ".patterns." + k, s);
                }
            });
            if (b.model().parts().isEmpty()) err(w, "model.parts 가 비어 있음");
            // 점진 힌트 단서 (GDD "보스 문구 규칙"): 없으면 단서 없음, 있으면 3단계 권장
            Object hints = b.raw().get("hints");
            if (hints != null && !(hints instanceof List<?>)) err(w + ".hints", "단서 목록(리스트)이어야 함");
            else if (hints instanceof List<?> l && l.size() != 3) {
                warn(w + ".hints", "단서는 3단계(흐릿 → 조금 분명 → 거의 정답)로 쓰는 것을 권장 (지금 " + l.size() + "줄)");
            }
        }
    }

    private void floors() {
        if (c.floors().isEmpty()) err("floors.yml", "층이 하나도 없음");
        for (int n = 1; n <= c.maxFloor(); n++) {
            if (!c.floors().containsKey(n)) err("floors.yml", "지하 " + n + "층이 빠져 있음");
        }
        for (FloorDef f : c.floors().values()) {
            String w = "floors." + f.number();
            for (String m : f.mobs()) requireMob(w + ".mobs", m);
            if (f.elite() != null) requireMob(w + ".elite", f.elite());
            BossDef b = c.boss(f.boss());
            if (b == null) err(w, "없는 보스 '" + f.boss() + "'");
            else if (b.floor() != f.number()) err(w, "보스 '" + b.id() + "' 의 floor 가 " + b.floor());
            if (f.mobs().isEmpty()) err(w, "mobs 비어 있음");
            for (String key : List.of("floor", "wall")) {
                if (f.palette(key).isEmpty()) err(w, "palette." + key + " 비어 있음");
            }
            requireTable(w + " 보물방", "treasure_floor_" + f.number());
            // 미로 함정·상자 (GDD §5.5·§5.6)
            for (String t : f.raw().sub("traps").strings("types")) {
                if (kr.labyrinth.dungeon.traps.TrapType.byId(t) == null) err(w + ".traps.types", "알 수 없는 함정 '" + t + "'");
            }
            int bracket = kr.labyrinth.dungeon.treasure.ChestSettings.of(f.raw().sub("chests")).bracket();
            for (kr.labyrinth.dungeon.treasure.ChestTier tier : kr.labyrinth.dungeon.treasure.ChestTier.values()) {
                // Treasures 와 같은 규칙: 구간 강제가 없으면 층별 표, 없으면 구간 표
                requireTable(w + " 미로 상자", tier.table(f.number(), bracket, c.lootTables()::containsKey));
                String et = tier.enhanceTable(f.number());
                if (et != null) requireTable(w + " 미로 상자 강화석", et);
            }
            requireTable(w + " 기믹방", "gimmick_floor_" + f.number());
            String failSpawn = f.gimmickParams().str("fail_spawn");
            if (failSpawn != null) requireMob(w + ".gimmick_params.fail_spawn", failSpawn);
        }
    }

    private void lootEntry(String w, LootTable.Entry e) {
        switch (e.kind()) {
            case ITEM -> requireItem(w, e.item());
            case ONE_OF -> {
                if (e.oneOf().isEmpty()) err(w, "one_of 비어 있음");
                for (String id : e.oneOf()) requireItem(w + ".one_of", id);
            }
            case TABLE -> requireTable(w + ".table", e.table());
            case RARITY_POOL -> {
                if (c.poolCandidates(e.floor(), e.rarityPool()).isEmpty()) {
                    warn(w, "rarity_pool " + e.rarityPool().id() + " floor " + e.floor() + " 후보 장비가 없음");
                }
            }
        }
        if (e.chance() < 0 || e.chance() > 1.0 + 1e-9) err(w, "chance 는 0~1: " + e.chance());
        if (e.minDifficulty() != null && !DIFFICULTIES.contains(e.minDifficulty())) err(w, "min_difficulty 가 올바르지 않음: " + e.minDifficulty());
    }

    private void loot() {
        for (LootTable t : c.lootTables().values()) {
            String w = "loot." + t.id();
            if (t.entries().isEmpty() && t.guaranteed().isEmpty() && t.gold().max() == 0) warn(w, "빈 테이블");
            for (LootTable.Entry e : t.entries()) lootEntry(w, e);
            for (LootTable.Entry e : t.guaranteed()) lootEntry(w + ".guaranteed", e);
            // rarity_pool 은 층 번호만으로 후보를 모아 같은 장비가 여러 층·여러 경로에서 나온다 → 명시 목록(one_of)으로
            long pools = t.entries().stream().filter(e -> e.kind() == LootTable.Kind.RARITY_POOL).count()
                    + t.guaranteed().stream().filter(e -> e.kind() == LootTable.Kind.RARITY_POOL).count();
            if (pools > 0) warn(w, "rarity_pool 항목 " + pools + "개 — 장비 획득처가 섞인다. one_of 명시 목록을 권장");
        }
        // 순환 참조 검사
        for (String id : c.lootTables().keySet()) {
            if (hasCycle(id, new HashSet<>())) err("loot." + id, "table 참조가 순환함");
        }
        for (String d : c.lootSettings().rarityWeight().keySet()) {
            if (!DIFFICULTIES.contains(d)) warn("loot.settings.rarity_weight", "알 수 없는 난이도 '" + d + "'");
        }
    }

    private boolean hasCycle(String id, Set<String> stack) {
        if (!stack.add(id)) return true;
        LootTable t = c.lootTable(id);
        if (t != null) {
            for (LootTable.Entry e : t.entries()) {
                if (e.kind() == LootTable.Kind.TABLE && hasCycle(e.table(), stack)) return true;
            }
        }
        stack.remove(id);
        return false;
    }

    // ── 장비 획득처 구조 (GDD §11 — 장비 하나는 자기 층에만, 집은 최대 2곳) ──────────────

    /** 집 이름 (경고 문구용). */
    private static final Map<String, String> HOME_NAMES = Map.of("common", "몬스터·상자", "elite", "정예", "boss", "보스",
            "craft", "제작", "reward", "칭호 보상", "shop", "상점", "starter", "시작 지급");

    /**
     * 층에 묶인 테이블(몹·정예·보스·보물방·기믹방·미로 상자)을 펼쳐 (a) 다른 층 장비, (b) 집이 3곳 이상인 장비,
     * (c) items.yml sources(툴팁·도감 표시)가 실제와 다른 장비, (d) 루팅·제작에도 나오는 시작 지급 장비를 경고한다.
     */
    /** 층에 묶인 테이블 하나 — 집(common·elite·boss), items.yml sources 꼬리표(drop·chest·elite·boss), 층(-1 = 여러 층이 같이 씀). */
    private record FloorTable(String home, String tag, int floor) {}

    private static void bind(Map<String, FloorTable> out, String table, String home, String tag, int floor) {
        FloorTable prev = out.get(table);
        out.put(table, new FloorTable(home, tag, prev != null && prev.floor() != floor ? -1 : floor));
    }

    private void gearHomes() {
        Map<String, FloorTable> bound = new LinkedHashMap<>();
        for (MobDef m : c.mobs().values()) {
            if (m.drops() != null) bind(bound, m.drops(), m.isElite() ? "elite" : "common", m.isElite() ? "elite" : "drop", m.floor());
        }
        for (BossDef b : c.bosses().values()) {
            if (b.drops() != null) bind(bound, b.drops(), "boss", "boss", b.floor());
        }
        for (FloorDef f : c.floors().values()) {
            List<String> chests = new ArrayList<>(List.of("treasure_floor_" + f.number(), "gimmick_floor_" + f.number()));
            int bracket = kr.labyrinth.dungeon.treasure.ChestSettings.of(f.raw().sub("chests")).bracket();
            for (kr.labyrinth.dungeon.treasure.ChestTier tier : kr.labyrinth.dungeon.treasure.ChestTier.values()) {
                chests.add(tier.table(f.number(), bracket, c.lootTables()::containsKey)); // Treasures 가 실제로 굴리는 표
            }
            for (String t : chests) if (c.lootTables().containsKey(t)) bind(bound, t, "common", "chest", f.number());
        }
        Map<String, Set<String>> homes = new HashMap<>();
        Map<String, Set<String>> tags = new HashMap<>();
        bound.forEach((t, ft) -> {
            List<String> leaks = new ArrayList<>();
            for (String id : expand(t)) {
                ItemDef d = c.item(id);
                if (d == null || !d.isGear()) continue;
                homes.computeIfAbsent(id, k -> new HashSet<>()).add(ft.home());
                tags.computeIfAbsent(id, k -> new HashSet<>()).add(ft.tag());
                if (ft.floor() == -1 || (ft.floor() > 0 && d.floor() != ft.floor())) leaks.add(id + "(" + d.floor() + "층)");
            }
            if (!leaks.isEmpty()) {
                warn("loot." + t, (ft.floor() == -1 ? "여러 층이 같이 쓰는 표인데 장비 " : "지하 " + ft.floor() + "층 표인데 다른 층 장비 ")
                        + leaks.size() + "종 (예: " + String.join(", ", leaks.subList(0, Math.min(3, leaks.size()))) + ")");
            }
        });
        for (RecipeDef r : c.recipes().values()) {
            homes.computeIfAbsent(r.result(), k -> new HashSet<>()).add("craft");
            tags.computeIfAbsent(r.result(), k -> new HashSet<>()).add("craft");
        }
        for (AchievementDef a : c.achievements().values()) {
            for (String id : a.rewardItems().keySet()) {
                homes.computeIfAbsent(id, k -> new HashSet<>()).add("reward");
                tags.computeIfAbsent(id, k -> new HashSet<>()).add("reward");
            }
        }
        for (NpcDef n : c.npcs().values()) {
            for (NpcDef.ShopEntry s : n.shop()) {
                homes.computeIfAbsent(s.item(), k -> new HashSet<>()).add("shop");
                tags.computeIfAbsent(s.item(), k -> new HashSet<>()).add("shop");
            }
        }
        for (ItemDef d : c.items().values()) {
            if (!d.isGear()) continue;
            String w = "items." + d.id();
            Set<String> h = new HashSet<>(homes.getOrDefault(d.id(), Set.of()));
            Set<String> tg = new HashSet<>(tags.getOrDefault(d.id(), Set.of()));
            if (d.sources().contains("starter")) {
                if (!h.isEmpty()) warn(w, "시작 지급 장비인데 " + homeNames(h) + "에서도 나옴");
                h.add("starter");
                tg.add("starter");
            }
            if (h.size() > 2) warn(w, "획득처가 " + h.size() + "곳 (" + homeNames(h) + ") — 장비는 최대 2곳 권장");
            if (!tg.isEmpty() && !tg.equals(new HashSet<>(d.sources()))) {
                warn(w, "sources " + d.sources() + " 가 실제 획득처 " + new TreeSet<>(tg) + " 와 다름 (툴팁·도감 표시가 틀림)");
            }
        }
    }

    private static String homeNames(Set<String> homes) {
        List<String> out = new ArrayList<>();
        for (String k : List.of("common", "elite", "boss", "craft", "reward", "shop", "starter")) {
            if (homes.contains(k)) out.add(HOME_NAMES.get(k));
        }
        return String.join("·", out);
    }

    /** 테이블이 줄 수 있는 아이템 id (하위 테이블·one_of·guaranteed·rarity_pool 후보 포함, 순환은 끊는다). */
    private Set<String> expand(String tableId) {
        Set<String> out = new HashSet<>();
        expand(c.lootTable(tableId), out, new HashSet<>());
        return out;
    }

    private void expand(LootTable t, Set<String> out, Set<String> visiting) {
        if (t == null || !visiting.add(t.id())) return;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> { if (e.item() != null) out.add(e.item()); }
                case ONE_OF -> out.addAll(e.oneOf());
                case TABLE -> expand(c.lootTable(e.table()), out, visiting);
                case RARITY_POOL -> {
                    if (e.rarityPool() != null) for (ItemDef d : c.poolCandidates(e.floor(), e.rarityPool())) out.add(d.id());
                }
            }
        }
        visiting.remove(t.id());
    }

    private void recipes() {
        for (RecipeDef r : c.recipes().values()) {
            String w = "recipes." + r.id();
            requireItem(w + ".result", r.result());
            if (r.materials().isEmpty()) err(w, "materials 비어 있음");
            r.materials().forEach((id, n) -> {
                requireItem(w + ".materials", id);
                if (n <= 0) err(w, "재료 개수는 양수: " + id);
            });
            if (!RECIPE_CATEGORIES.contains(r.category())) err(w, "category 가 올바르지 않음: " + r.category());
        }
    }

    private void titles() {
        for (AchievementDef a : c.achievements().values()) {
            String w = "achievements." + a.id();
            if (!CONDITIONS.contains(a.conditionType())) err(w, "condition.type 이 올바르지 않음: " + a.conditionType());
            Params cond = a.condition();
            if (cond.has("floor") && !c.floors().containsKey(cond.integer("floor", 0))) err(w, "없는 층 " + cond.str("floor"));
            if (cond.has("mob")) requireMob(w + ".condition.mob", cond.str("mob"));
            for (String mob : cond.strings("mobs")) requireMob(w + ".condition.mobs", mob);
            if (cond.has("boss") && !c.bosses().containsKey(cond.str("boss"))) err(w, "없는 보스 '" + cond.str("boss") + "'");
            if (cond.has("rarity") && Rarity.byId(cond.str("rarity")) == null) err(w, "rarity 가 올바르지 않음: " + cond.str("rarity"));
            if (cond.has("difficulty") && !DIFFICULTIES.contains(cond.str("difficulty"))) err(w, "difficulty 가 올바르지 않음");
            if ("TREASURE".equals(a.conditionType()) && !TREASURE_KINDS.contains(cond.str("kind", "chest"))) {
                err(w, "TREASURE kind 가 올바르지 않음: " + cond.str("kind"));
            }
            for (String k : a.bonus().keySet()) if (!TITLE_BONUS_KEYS.contains(k)) err(w, "bonus 키가 올바르지 않음: " + k);
            for (String id : a.rewardItems().keySet()) requireItem(w + ".reward.items", id);
        }
    }

    private void npcs() {
        for (NpcDef n : c.npcs().values()) {
            String w = "npcs." + n.id();
            if (!NPC_ROLES.contains(n.role())) err(w, "role 이 올바르지 않음: " + n.role());
            for (NpcDef.ShopEntry s : n.shop()) {
                requireItem(w + ".shop", s.item());
                if (s.price() <= 0) err(w, "상점 가격은 양수: " + s.item());
            }
            if ("floor".equals(n.placement()) && !c.floors().containsKey(n.floor())) err(w, "없는 층 " + n.floor());
        }
    }

    private void fx() {
        for (AuraDef a : c.auras().values()) {
            String w = "auras." + a.id();
            requireFx(w + ".ring_model", a.ringModel());
            requireFx(w + ".secondary_model", a.secondaryModel());
            for (Params p : a.particles()) {
                if (p.str("type") == null) err(w, "particles[].type 없음");
            }
        }
    }

    private void glyphs() {
        Set<String> chars = new HashSet<>();
        for (GlyphDef g : c.glyphs().values()) {
            String w = "glyphs." + g.id();
            if (g.ch().codePointCount(0, g.ch().length()) != 1) err(w, "char 는 정확히 한 글자여야 함");
            else if (!chars.add(g.ch())) err(w, "char 가 다른 글리프와 겹침");
            if (g.file().isBlank()) err(w, "file 없음");
        }
    }

    /** 사용자에게 보여 줄 요약 (최대 n줄). */
    public static List<String> summarize(Report r, int max) {
        List<String> out = new ArrayList<>();
        for (String e : r.errors()) {
            if (out.size() >= max) break;
            out.add("[오류] " + e);
        }
        for (String w : r.warnings()) {
            if (out.size() >= max) break;
            out.add("[경고] " + w);
        }
        return out;
    }

    /** fx 모델 이름을 담는 파라미터 키: fx, fx_* (단 *_prefix 는 접두어라 제외). */
    private static boolean isFxKey(String k) {
        return (k.equals("fx") || k.startsWith("fx_")) && !k.endsWith("_prefix");
    }
}
