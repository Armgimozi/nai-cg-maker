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
import kr.labyrinth.content.ArmorLook;
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
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.StatRequirement;
import kr.labyrinth.stats.Stat;

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
    /** 직업 스킬 피해 종류 꼬리표 (classes.yml skills[].kind). */
    public static final Set<String> SKILL_KINDS = Set.of("physical", "magic", "hybrid", "none");
    /** 무기 attack 블록 (0.3.5). */
    public static final Set<String> ATTACK_STYLES = Set.of("melee", "ranged", "caster");
    public static final Set<String> ATTACK_KINDS = Set.of("physical", "magic", "hybrid");
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
    /** 0.3.6: miner (광부 → 광산 관리소 메뉴) · smelter (제련공 → 제련소 메뉴) — 이름은 kr.labyrinth.mine.MineNames. */
    public static final Set<String> NPC_ROLES = Set.of("entrance", "blacksmith", "class_master", "title_keeper", "merchant", "lore",
            kr.labyrinth.mine.MineNames.ROLE_MINER, kr.labyrinth.mine.MineNames.ROLE_SMELTER);
    public static final Set<String> DIFFICULTIES = Set.of("easy", "normal", "hard", "nightmare");
    /** recipes.yml station (0.3.6): 대장간 · 제련소. */
    public static final Set<String> RECIPE_STATIONS = Set.of(kr.labyrinth.mine.MineNames.STATION_BLACKSMITH,
            kr.labyrinth.mine.MineNames.STATION_SMELTER);
    public static final Set<String> RECIPE_CATEGORIES = Set.of("weapon", "armor", "accessory", "material",
            kr.labyrinth.mine.MineNames.CATEGORY_TOOL);

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
        mine();
        requirements();
        armorLooks();
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
        for (ClassDef d : c.classes().values()) {
            String w = "classes." + d.id();
            if (!ROLES.contains(d.role())) err(w, "role 이 올바르지 않음: " + d.role());
            if (d.iconItem() != null) requireItem(w + ".icon_item", d.iconItem());
            // 0.3.5: 무기 종류 없음 — 추천 무기 대신 처음 줄 무기 하나 (starter_weapon)
            if (d.raw().has("weapon_types")) {
                warn(w, "weapon_types 는 0.3.5 부터 쓰지 않음 (무기 종류 없음) — 지울 것 (예전 파일로 보고 스킬 재사용 대기를 ×0.9 로 읽음)");
            }
            String starter = d.starterWeapon();
            if (starter != null) {
                requireItem(w + ".starter_weapon", starter);
                ItemDef sw = c.item(starter);
                if (sw != null && !sw.isWeapon()) err(w + ".starter_weapon", "무기가 아님: " + starter);
            }
            for (String k : d.raw().strings("main_stats")) {
                if (Stat.byKey(k) == null) err(w + ".main_stats", "능력치가 아님: " + k);
            }
            Set<String> inputs = new HashSet<>();
            for (ClassDef.SkillDef s : d.skills()) {
                if (!CLASS_INPUTS.contains(s.input())) err(w + ".skills." + s.id(), "input 이 올바르지 않음: " + s.input());
                if (!inputs.add(s.input())) err(w + ".skills." + s.id(), "같은 input 을 쓰는 스킬이 둘: " + s.input());
                if (s.id().isBlank()) err(w, "스킬 id 비어 있음");
                if (!s.kind().isEmpty() && !SKILL_KINDS.contains(s.kind())) {
                    err(w + ".skills." + s.id(), "kind 는 physical | magic | hybrid | none: " + s.kind());
                }
                pvpMult(w + ".skills." + s.id(), s.pvpMult());
                checkFxParams(w + ".skills." + s.id(), s.params());
            }
            if (d.baseHp() <= 0) err(w, "base_hp 는 양수");
        }
    }

    /** 스킬 pvp_mult (플레이어에게 주는 피해 배율, pvp_spec §6): 0.1 ~ 1.0. */
    private void pvpMult(String where, double v) {
        if (Double.isNaN(v) || v < 0.1 - 1e-9 || v > 1.0 + 1e-9) err(where, "pvp_mult 는 0.1 ~ 1.0: " + v);
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
            if (d.type() == ItemType.WEAPON) attack(w, d);
            unique(w, d);
            if (d.type() == ItemType.ARMOR && (d.armorSlot() == null || !ARMOR_SLOTS.contains(d.armorSlot()))) {
                err(w, "방어구 armor_slot 이 올바르지 않음: " + d.armorSlot());
            }
            if (d.armorSlot() != null && !ARMOR_SLOTS.contains(d.armorSlot())) err(w, "armor_slot 이 올바르지 않음: " + d.armorSlot());
            if (d.setBonus() != null && !c.sets().containsKey(d.setBonus())) err(w, "없는 세트 '" + d.setBonus() + "'");
            if (d.aura() != null && !c.auras().containsKey(d.aura())) err(w, "없는 아우라 '" + d.aura() + "'");
            for (String cls : d.classes()) if (!c.classes().containsKey(cls)) err(w, "없는 직업 '" + cls + "'");
            for (String k : d.stats().keySet()) if (!ITEM_STAT_KEYS.contains(k)) err(w, "알 수 없는 스탯 키 '" + k + "'");
            if (d.isGear() && (d.tier() < 0 || d.tier() > 10)) err(w, "tier 는 1~10");
            if (d.isGear() && d.raw() != null && d.raw().has("floor") && !d.raw().has("tier")) {
                warn(w, "장비의 floor 는 0.3.5 부터 tier (숨은 단계) — 같은 값으로 읽음");
            }
            Set<String> inputs = new HashSet<>();
            for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
                String sw = w + ".weapon_skills." + s.id();
                if ("mechanics".equals(s.id())) {
                    mechanics(sw, d, s);
                } else if (!WEAPON_SKILLS.contains(s.id())) err(sw, "알 수 없는 무기 스킬 구현 id");
                if (!WEAPON_INPUTS.contains(s.input())) err(sw, "input 이 올바르지 않음: " + s.input());
                if (!inputs.add(s.input())) err(sw, "같은 input 을 쓰는 무기 스킬이 둘: " + s.input());
                pvpMult(sw, s.pvpMult());
                checkFxParams(sw, s.params());
            }
            if (d.type() == ItemType.CONSUMABLE) {
                String action = d.use().str("action");
                if (action == null || !USE_ACTIONS.contains(action)) err(w, "소모품 use.action 이 올바르지 않음: " + action);
            }
            if (d.rarity().atLeast(Rarity.LEGENDARY) && d.isWeapon() && d.aura() == null) {
                warn(w, "전설/신화 무기인데 aura 가 없음");
            }
            if (d.requires() != null && !d.requires().isEmpty() && d.requirement().isEmpty()) {
                warn(w, "requires 는 무기·방어구·방패만 — " + d.type().id() + " 에는 무시됨");
            }
        }
    }

    /** 무기 공격 간격 검사 범위 (초, 민첩 전). combat_spec §11: 0.35 ~ 1.30. */
    public static final double MIN_WEAPON_INTERVAL = 0.35;
    public static final double MAX_WEAPON_INTERVAL = 1.30;

    /**
     * 무기 attack 블록 (0.3.5 — 무기 종류 없음): style melee | ranged | caster · interval 0.35~1.30초 · kind physical | magic | hybrid.
     * 활 모양(model.shape 가 …bow)이면 ranged, 아니면 ranged 가 아님 (당기는 모델·바닐라 활 재료가 모양을 따른다).
     * 예전 weapon_type 만 있는 무기는 그때 주기로 대신하고 경고.
     */
    private void attack(String w, ItemDef d) {
        Params a = d.raw() == null ? Params.EMPTY : d.raw().sub("attack");
        boolean legacy = d.raw() != null && d.raw().has("weapon_type");
        if (legacy) warn(w, "weapon_type 은 0.3.5 부터 쓰지 않음 — attack: {style, interval, kind} 로 바꿀 것 (지금은 예전 주기로 대신)");
        if (a.isEmpty()) {
            if (!legacy) err(w, "무기인데 attack: {style, interval, kind} 가 없음");
            return;
        }
        String style = a.str("style");
        if (style == null || !ATTACK_STYLES.contains(style)) err(w + ".attack", "style 은 melee | ranged | caster: " + style);
        String kind = a.str("kind");
        if (kind != null && !ATTACK_KINDS.contains(kind)) err(w + ".attack", "kind 는 physical | magic | hybrid: " + kind);
        if (!a.has("interval") && a.has("speed")) warn(w + ".attack", "speed 대신 interval(초) 로 적을 것");
        double iv = d.attack().interval();
        if (iv < MIN_WEAPON_INTERVAL - 1e-9 || iv > MAX_WEAPON_INTERVAL + 1e-9) {
            err(w + ".attack", "interval 은 " + MIN_WEAPON_INTERVAL + " ~ " + MAX_WEAPON_INTERVAL + "초: " + iv);
        }
        String shape = d.model() == null ? null : d.model().str("shape");
        boolean bowShape = shape != null && shape.endsWith("bow");
        if (shape != null && bowShape != d.attack().ranged()) {
            err(w + ".attack", bowShape ? "활 모양(" + shape + ")인데 style 이 ranged 가 아님" : "ranged 인데 활 모양이 아님: " + shape);
        }
        for (ItemDef.WeaponSkillDef s : d.weaponSkills()) {
            if (d.attack().ranged() && "RIGHT".equals(s.input())) err(w + ".weapon_skills." + s.id(), "활은 RIGHT(바닐라 당기기) 스킬 금지");
        }
    }

    /**
     * 고유 효과 (unique_spec §7·§9.8, review2 A11·A12): 무기만 · 닫힌 목록 26개 · 수치 범위 · 원거리 전용은 attack.style 로.
     * 고유 효과가 없는 무기는 아직 허용한다 (0.3.5 P3 생성기가 모든 무기에 넣는다).
     */
    private void unique(String w, ItemDef d) {
        boolean has = d.raw() != null && d.raw().has("unique");
        if (!has) return;
        if (d.type() != ItemType.WEAPON) {
            err(w + ".unique", "고유 효과는 무기만 — " + d.type().id() + " 에는 넣을 수 없음");
            return;
        }
        if (d.unique() == null) return; // 꼴이 틀린 블록은 파서가 이미 문제로 남김
        String rawId = d.raw().sub("unique").str("id", "");
        if (kr.labyrinth.content.UniqueCatalog.ALIASES.containsKey(rawId.trim())) {
            warn(w + ".unique", "id '" + rawId + "' 는 예전 이름 — '" + d.unique().id() + "' 로 바꿀 것");
        }
        var check = kr.labyrinth.content.UniqueCatalog.check(d.unique(), d.attack());
        for (String e : check.errors()) err(w, e);
        for (String x : check.warnings()) warn(w, x);
    }

    /** Lv.1 시작 포인트 (config level.start_points 기본값 — 검사는 번들 기본 기준). */
    public static final int START_POINTS = 5;

    /**
     * 요구 능력치 (items.yml requires — 0.3.5 '그리고'만): 시작 지급 장비는 요구 없음, 직업마다 처음 받는 시작 무기
     * (classes.yml {@code starter_weapon})는 Lv.1 에 직업 기본 능력치 + 시작 포인트 {@value #START_POINTS} 로 쓸 수 있어야 한다.
     * 무기 (gear_spec §3.1): 합 = T(L) = ceil(2.75(L−1)), L ≤ 2 이면 없음, 능력치 2~3개(셋은 L ≥ 12), 나눔 60/40 · 50/30/20 (±1),
     * 물리 무기는 STR 또는 DEX, 마법 무기는 INT 또는 WIS 하나 이상. 어긋나면 경고 (게임은 돌아감).
     */
    private void requirements() {
        for (ItemDef d : c.items().values()) {
            if (d.isGear() && d.sources().contains("starter") && !d.requirement().isEmpty()) {
                warn("items." + d.id(), "시작 지급 장비인데 요구 능력치가 있음 (" + d.requirement().text() + ")");
            }
            if (d.isWeapon()) weaponRequirement("items." + d.id(), d);
        }
        for (ClassDef cls : c.classes().values()) {
            ItemDef weapon = cls.starterWeapon() == null ? null : c.item(cls.starterWeapon());
            if (weapon == null || !weapon.isWeapon()) continue;
            int need = weapon.requirement().pointsNeeded(StatRequirement.playerStats(cls, Map.of(), Map.of()));
            if (need > START_POINTS) {
                warn("items." + weapon.id(), "직업 " + cls.id() + " 의 시작 무기인데 Lv.1 에 쓸 수 없음 (" + weapon.requirement().text()
                        + " — 시작 포인트 " + START_POINTS + " 로 " + need + " 필요)");
            }
        }
    }

    /** 무기 요구 능력치 규칙 (경고) — {@link #requirements()}. */
    private void weaponRequirement(String w, ItemDef d) {
        StatRequirement r = d.requirement();
        int t = StatRequirement.budget(d.levelReq());
        int sum = r.total();
        if (t == 0) {
            if (sum > 0) warn(w, "아이템 레벨 " + d.levelReq() + " 은 요구 없음인데 " + r.text());
            return;
        }
        if (sum != t) warn(w, "요구 합 " + sum + " ≠ " + t + " (아이템 레벨 " + d.levelReq() + ", T = ceil(2.75(L−1)))");
        int n = r.all().size();
        if (n < 2 || n > 3 || (n == 3 && d.levelReq() < 12)) {
            warn(w, "요구 능력치 " + n + "개 — 무기는 2~3개 (셋은 아이템 레벨 12 부터)");
        } else if (!splitOk(r, t)) {
            warn(w, "요구 나눔 " + r.text() + " — 60 : 40 또는 50 : 30 : 20 (±1)");
        }
        boolean magic = d.attack() != null && d.attack().kind() == kr.labyrinth.combat.DamageKind.MAGIC;
        boolean ok = magic ? r.all().containsKey(Stat.INT) || r.all().containsKey(Stat.WIS)
                : r.all().containsKey(Stat.STR) || r.all().containsKey(Stat.DEX);
        if (!ok) warn(w, (magic ? "마법 무기인데 지능·정신" : "물리 무기인데 힘·민첩") + " 요구가 없음 (" + r.text() + ")");
    }

    /** 요구 나눔이 60/40 또는 50/30/20 (각 몫 ±1) 인가. */
    public static boolean splitOk(StatRequirement r, int total) {
        List<Integer> v = new ArrayList<>();
        for (Map.Entry<Stat, Integer> e : r.ordered()) v.add(e.getValue());
        double[] shares = v.size() == 2 ? new double[] {0.6, 0.4} : v.size() == 3 ? new double[] {0.5, 0.3, 0.2} : null;
        if (shares == null) return v.size() == 1;
        for (int i = 0; i < v.size(); i++) if (Math.abs(v.get(i) - shares[i] * total) > 1.0 + 1e-9) return false;
        return true;
    }

    /**
     * 방어구 겉모습 (look_spec §1.1·§3.1, review2 A3): 모든 방어구가 겉모습을 갖는다 (세트 없는 투구는 {@code look}, 방패는 적지 않음 —
     * 언제나 판금). 요구 능력치는 '모두 채움'만, 합 = T(L) = ceil(2.75(L−1)), 판금·가죽·천은 두 능력치(앞 = 겉모습 능력치 — 판금·방패
     * 체력 · 가죽 민첩 · 천 지능 또는 정신, 가장 큰 몫 60% 안팎), 평상복·any 는 능력치 1~3개 자유. 어긋나면 경고 (게임은 돌아감).
     */
    private void armorLooks() {
        for (ItemDef d : c.items().values()) {
            if (d.type() != ItemType.ARMOR) continue;
            String w = "items." + d.id();
            boolean hasLook = d.raw() != null && d.raw().has("look");
            boolean setless = (d.setBonus() == null || !c.sets().containsKey(d.setBonus()))
                    && (d.armorSet() == null || !c.sets().containsKey(d.armorSet()));
            if (d.isShield() && hasLook) warn(w, "방패에는 look 을 적지 않는다 (언제나 판금)");
            else if (setless && !d.isShield() && !hasLook) warn(w, "세트 없는 방어구인데 look 이 없음 — 평상복(겉모습 효과 없음)으로 다룸");
            else if (!setless && hasLook && !d.isShield()) warn(w, "세트 방어구인데 look 이 적혀 있음 — 세트 겉모습 대신 이 값을 씀");
            armorRequirement(w, d, d.armorLook());
        }
        for (ItemSetDef s : c.sets().values()) {
            ArmorLook l = ArmorLook.byId(s.look());
            if (l == null || !l.real()) err("sets." + s.id(), "look 은 heavy | light | cloth: " + s.look());
        }
    }

    private void armorRequirement(String w, ItemDef d, ArmorLook look) {
        StatRequirement r = d.requirement();
        int t = StatRequirement.budget(d.levelReq());
        int sum = r.all().values().stream().mapToInt(Integer::intValue).sum();
        if (t == 0) {
            if (sum > 0) warn(w, "아이템 레벨 " + d.levelReq() + " 은 요구 없음인데 " + r.text());
            return;
        }
        if (sum != t) warn(w, "요구 합 " + sum + " ≠ " + t + " (아이템 레벨 " + d.levelReq() + ", T = ceil(2.75(L−1)))");
        int n = r.all().size();
        if (look != null && look.real() ? n != 2 : (n < 1 || n > 3)) {
            warn(w, "요구 능력치 " + n + "개 — " + (look != null && look.real() ? "판금·가죽·천은 두 능력치" : "1~3개"));
        }
        if (look == null || !look.real() || r.all().isEmpty()) return;
        Map.Entry<Stat, Integer> lead = null;
        for (Map.Entry<Stat, Integer> e : r.all().entrySet()) if (lead == null || e.getValue() > lead.getValue()) lead = e;
        if (!look.leadStats().contains(lead.getKey())) {
            warn(w, look.id() + " 인데 가장 큰 요구가 " + lead.getKey().displayName() + " — 판금·방패 체력 · 가죽 민첩 · 천 지능 또는 정신");
        }
        if (lead.getValue() > Math.ceil(0.6 * sum) || lead.getValue() * 2 < sum) {
            warn(w, "요구 나눔 " + r.text() + " — 앞 능력치가 합의 50~60%");
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
            else if (!m.isAdd() && !kr.labyrinth.dungeon.treasure.MimicSpec.isMimic(m)) warn(w, "drops 가 없음(소환물이 아닌데)");
            if (!isEntityType(m.base())) err(w, "base 엔티티 타입이 올바르지 않음: " + m.base());
            mobSkills(w, m.skills());
            boolean flies = m.flying() || (m.base() != null && FLYING_BASES.contains(m.base().toUpperCase(java.util.Locale.ROOT)));
            for (MobDef.MobSkillDef s : m.skills()) {
                if ("dive".equals(s.type()) && !flies) err(w + ".skills.dive", "dive 는 비행 몹(flying: true 또는 비행 베이스)만 쓸 수 있음");
                if ("burrow".equals(s.type()) && flies) err(w + ".skills.burrow", "burrow 는 땅 위 몹만 쓸 수 있음");
            }
            if (m.model().parts().isEmpty()) err(w, "model.parts 가 비어 있음");
            mimic(w, m);
        }
    }

    /** 미믹 (mobs.yml {@code mimic:} — dungeon.treasure.MimicSpec): floors 범위 · 배율 · companion. floor 0 은 미믹만. */
    private void mimic(String w, MobDef m) {
        boolean isMimic = kr.labyrinth.dungeon.treasure.MimicSpec.isMimic(m);
        if (!isMimic) {
            if (m.floor() == 0) warn(w, "floor 0(모든 층)은 미믹(mimic: 블록)만 씀");
            return;
        }
        Params k = m.raw().sub("mimic");
        int[] r = kr.labyrinth.dungeon.treasure.MimicSpec.floors(m);
        if (r != null && (r[0] < 1 || r[1] > Math.max(1, c.maxFloor()))) err(w + ".mimic.floors", "층 범위가 1~" + c.maxFloor() + " 밖: " + r[0] + "~" + r[1]);
        for (String key : List.of("hp", "damage", "defense", "xp", "gold")) {
            if (k.has(key) && k.dbl(key, 1) < 0) err(w + ".mimic." + key, "배율은 0 이상");
        }
        if (k.dbl("hp", 1) <= 0) err(w + ".mimic.hp", "hp 배율은 양수");
        String comp = k.str("companion");
        if (comp != null) {
            MobDef d = c.mob(comp);
            if (d == null) err(w + ".mimic.companion", "없는 몹 '" + comp + "'");
            else if (!kr.labyrinth.dungeon.treasure.MimicSpec.isMimic(d)) warn(w + ".mimic.companion", "'" + comp + "' 에 mimic: 블록이 없음 (층 수치가 안 맞음)");
            else if (comp.equals(m.id())) err(w + ".mimic.companion", "자기 자신");
        }
        boolean hasLid = false;
        for (ModelDef.Part p : m.model().parts()) if ("lid".equals(p.anim())) hasLid = true;
        if (!hasLid) warn(w + ".model", "미믹인데 anim lid 파트(뚜껑 턱)가 없음");
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
            case PICK -> {
                if (e.pick().isEmpty()) err(w, "pick 이 비어 있음");
                for (LootTable.Pick p : e.pick()) {
                    requireTable(w + ".pick", p.table());
                    if (p.weight() <= 0) err(w + ".pick", "weight 는 1 이상: " + p.table() + " " + p.weight());
                }
            }
            case BLUEPRINT -> {
                if (kr.labyrinth.items.blueprint.BlueprintRules.candidates(c, e.floor()).isEmpty()) {
                    warn(w, "blueprint 단계 " + e.floor() + " 근처에 도안이 필요한 레시피가 없음");
                }
            }
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
            List<LootTable.Entry> all = new ArrayList<>(t.entries());
            all.addAll(t.guaranteed());
            for (LootTable.Entry e : all) {
                if (e.kind() == LootTable.Kind.TABLE && hasCycle(e.table(), stack)) return true;
                if (e.kind() == LootTable.Kind.PICK) for (LootTable.Pick p : e.pick()) if (hasCycle(p.table(), stack)) return true;
            }
        }
        stack.remove(id);
        return false;
    }

    // ── 장비 획득처 구조 (0.3.5 gear_spec §4 — 단계 tier, 레벨 창 = 이웃 층 셋, 영웅 이상 무기는 획득처 종류 1개) ──────────────

    /** 획득처 종류 이름 (경고 문구용). drop·chest 는 한 종류 '몬스터·상자'. */
    public static final Map<String, String> KIND_NAMES = Map.ofEntries(Map.entry("common", "몬스터·상자"), Map.entry("elite", "정예"),
            Map.entry("boss", "보스"), Map.entry("trial", "시련방"), Map.entry("special", "특별 시련"), Map.entry("hoard", "금고·미믹"),
            Map.entry("craft", "대장간"), Map.entry("reward", "칭호 보상"), Map.entry("shop", "상인"), Map.entry("starter", "시작 지급"));
    private static final List<String> KIND_ORDER = List.of("common", "elite", "boss", "trial", "special", "hoard", "craft", "shop",
            "reward", "starter");

    /** items.yml sources 꼬리표 → 획득처 종류 (drop·chest = common). */
    public static String kindOf(String source) {
        return switch (source) {
            case "drop", "chest" -> "common";
            default -> source;
        };
    }

    /**
     * 층에 묶인 테이블 하나 — 종류(common·elite·boss·trial·special·hoard), items.yml sources 꼬리표, 층(-1 = 여러 층이 같이 씀).
     * 한 테이블을 몹·보스·상자가 같이 쓰면 종류·꼬리표를 모두 모은다 (나중에 묶은 쪽만 남지 않게).
     */
    private record FloorTable(Set<String> kinds, Set<String> tags, int floor) {}

    private static void bind(Map<String, FloorTable> out, String table, String kind, String tag, int floor) {
        FloorTable prev = out.get(table);
        FloorTable ft = prev == null ? new FloorTable(new HashSet<>(), new HashSet<>(), floor)
                : prev.floor() == floor ? prev : new FloorTable(prev.kinds(), prev.tags(), -1);
        ft.kinds().add(kind);
        ft.tags().add(tag);
        out.put(table, ft);
    }

    /**
     * 층에 묶인 테이블(몹·정예·보스·보물방·시련방·특별 시련·금고·미믹·미로 상자)을 펼쳐 (a) 레벨 창 밖 장비 (보스가 아닌 장비는
     * 단계 ±1 층, 보스 장비는 그 층 보스만), (b) 획득처 종류가 3개 이상인 장비 · 영웅 이상인데 2개 이상인 무기,
     * (c) items.yml sources(툴팁·도감 표시)가 실제와 다른 장비, (d) 루팅·제작에도 나오는 시작 지급 장비를 경고한다.
     */
    private void gearHomes() {
        Map<String, FloorTable> bound = new LinkedHashMap<>();
        for (MobDef m : c.mobs().values()) {
            if (m.drops() != null) bind(bound, m.drops(), m.isElite() ? "elite" : "common", m.isElite() ? "elite" : "drop", m.floor());
        }
        for (BossDef b : c.bosses().values()) {
            if (b.drops() != null) bind(bound, b.drops(), "boss", "boss", b.floor());
        }
        for (FloorDef f : c.floors().values()) {
            int n = f.number();
            List<String> chests = new ArrayList<>(List.of("treasure_floor_" + n));
            int bracket = kr.labyrinth.dungeon.treasure.ChestSettings.of(f.raw().sub("chests")).bracket();
            for (kr.labyrinth.dungeon.treasure.ChestTier tier : kr.labyrinth.dungeon.treasure.ChestTier.values()) {
                chests.add(tier.table(n, bracket, c.lootTables()::containsKey)); // Treasures 가 실제로 굴리는 표
            }
            for (String t : chests) if (c.lootTables().containsKey(t)) bind(bound, t, "common", "chest", n);
            String g = "gimmick_floor_" + n;
            if (c.lootTables().containsKey(g)) bind(bound, g, "trial", "trial", n);
            String sp = String.format(java.util.Locale.ROOT, "special_trial_f%02d", n);
            if (c.lootTables().containsKey(sp)) bind(bound, sp, "special", "special", n);
            String h = kr.labyrinth.dungeon.treasure.Treasures.hoardTable(n);
            if (c.lootTables().containsKey(h)) bind(bound, h, "hoard", "hoard", n);
        }
        Map<String, Set<String>> kinds = new HashMap<>();
        Map<String, Set<String>> tags = new HashMap<>();
        bound.forEach((t, ft) -> {
            List<String> leaks = new ArrayList<>();
            for (String id : expand(t)) {
                ItemDef d = c.item(id);
                if (d == null || !d.isGear()) continue;
                kinds.computeIfAbsent(id, k -> new HashSet<>()).addAll(ft.kinds());
                tags.computeIfAbsent(id, k -> new HashSet<>()).addAll(ft.tags());
                if (ft.floor() == -1 || (ft.floor() > 0 && d.tier() > 0 && !inWindow(d, ft))) leaks.add(id + "(단계 " + d.tier() + ")");
            }
            if (!leaks.isEmpty()) {
                warn("loot." + t, (ft.floor() == -1 ? "여러 층이 같이 쓰는 표인데 장비 " : "지하 " + ft.floor() + "층 표인데 레벨 창 밖 장비 ")
                        + leaks.size() + "종 (예: " + String.join(", ", leaks.subList(0, Math.min(3, leaks.size()))) + ")");
            }
        });
        for (RecipeDef r : c.recipes().values()) {
            kinds.computeIfAbsent(r.result(), k -> new HashSet<>()).add("craft");
            tags.computeIfAbsent(r.result(), k -> new HashSet<>()).add("craft");
        }
        for (AchievementDef a : c.achievements().values()) {
            for (String id : a.rewardItems().keySet()) {
                kinds.computeIfAbsent(id, k -> new HashSet<>()).add("reward");
                tags.computeIfAbsent(id, k -> new HashSet<>()).add("reward");
            }
        }
        for (NpcDef n : c.npcs().values()) {
            for (NpcDef.ShopEntry s : n.shop()) {
                kinds.computeIfAbsent(s.item(), k -> new HashSet<>()).add("shop");
                tags.computeIfAbsent(s.item(), k -> new HashSet<>()).add("shop");
            }
        }
        for (ItemDef d : c.items().values()) {
            if (!d.isGear()) continue;
            String w = "items." + d.id();
            Set<String> h = new HashSet<>(kinds.getOrDefault(d.id(), Set.of()));
            Set<String> tg = new HashSet<>(tags.getOrDefault(d.id(), Set.of()));
            if (d.sources().contains("starter")) {
                if (!h.isEmpty()) warn(w, "시작 지급 장비인데 " + kindNames(h) + "에서도 나옴");
                h.add("starter");
                tg.add("starter");
            }
            if (d.isWeapon() && d.rarity().atLeast(Rarity.EPIC) && h.size() > 1) {
                warn(w, "영웅 이상 무기인데 획득처 종류가 " + h.size() + "개 (" + kindNames(h) + ") — 1개여야 함");
            } else if (h.size() > 2) {
                warn(w, "획득처 종류가 " + h.size() + "개 (" + kindNames(h) + ") — 장비는 최대 2개 권장");
            }
            if (!tg.isEmpty() && !tg.equals(new HashSet<>(d.sources()))) {
                warn(w, "sources " + d.sources() + " 가 실제 획득처 " + new TreeSet<>(tg) + " 와 다름 (툴팁·도감 표시가 틀림)");
            }
        }
    }

    /** 층 표가 그 장비의 레벨 창 안인가 — 보스 표는 그 단계 층만, 그 밖은 단계 ±1 층 (gear_spec §4.1). */
    private static boolean inWindow(ItemDef d, FloorTable ft) {
        if (ft.kinds().contains("boss")) return d.tier() == ft.floor();
        return Math.abs(d.tier() - ft.floor()) <= 1;
    }

    private static String kindNames(Set<String> kinds) {
        List<String> out = new ArrayList<>();
        for (String k : KIND_ORDER) if (kinds.contains(k)) out.add(KIND_NAMES.get(k));
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
                case PICK -> { for (LootTable.Pick p : e.pick()) expand(c.lootTable(p.table()), out, visiting); }
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
            String st = r.station() == null || r.station().isBlank() ? kr.labyrinth.mine.MineNames.STATION_BLACKSMITH : r.station();
            if (!RECIPE_STATIONS.contains(st)) err(w, "station 이 올바르지 않음 (blacksmith | smelter): " + st);
            ItemDef res = c.items().get(r.result());
            if (res != null && res.isTool() && !kr.labyrinth.mine.MineNames.STATION_SMELTER.equals(st)) {
                err(w, "곡괭이 레시피는 station: smelter (제련소·광산 관리소)");
            }
            if (kr.labyrinth.mine.MineNames.CATEGORY_TOOL.equals(r.category()) && (res == null || !res.isTool())) {
                err(w, "category: tool 은 곡괭이(type: tool) 결과만");
            }
        }
    }

    /**
     * 0.3.6 광산 재료·곡괭이 (계약 tools/data/036): items.yml {@code mine_kind}·{@code mine_level}·{@code tool} 과 mine.yml 을 맞대어 본다.
     * 광석·보석 id 는 mine.yml ores·gems 와, 등급은 tier 와 같아야 한다. 주괴 = 광석의 ingot. 곡괭이는 tier 1~6, 제 등급 이하마다 speed (한 단계 위는 있으면 쓰고 없으면 제 등급 × 0.6),
     * 레벨 조건·능력치 없음. mine.yml 이 없으면(광산 꺼짐) items.yml 쪽 모양만 본다.
     */
    private void mine() {
        kr.labyrinth.content.MineDef m = c.mine();
        boolean have = m != null && !m.isEmpty();
        for (ItemDef d : c.items().values()) {
            String w = "items." + d.id();
            if (d.mineKind() != null) {
                if (d.type() != ItemType.MATERIAL) err(w, "mine_kind 는 재료(type: material)만");
                if (d.mineLevel() < 1 || d.mineLevel() > kr.labyrinth.content.ToolSpec.MAX_TIER) err(w, "mine_level 은 1~6: " + d.mineLevel());
                if (have) {
                    switch (d.mineKind()) {
                        case ORE -> {
                            var n = m.ores().get(d.id());
                            if (n == null) err(w, "mine_kind: ore 인데 mine.yml ores 에 없음");
                            else if (n.tier() != d.mineLevel()) err(w, "mine_level " + d.mineLevel() + " ≠ mine.yml tier " + n.tier());
                        }
                        case GEM -> {
                            var n = m.gems().get(d.id());
                            if (n == null) err(w, "mine_kind: gem 인데 mine.yml gems 에 없음");
                            else if (n.tier() != d.mineLevel()) err(w, "mine_level " + d.mineLevel() + " ≠ mine.yml tier " + n.tier());
                        }
                        case INGOT -> {
                            var n = m.ores().values().stream().filter(o -> d.id().equals(o.ingot())).findFirst().orElse(null);
                            if (n == null) err(w, "mine_kind: ingot 인데 mine.yml 의 어느 광석 ingot 도 아님");
                            else if (n.tier() != d.mineLevel()) err(w, "mine_level " + d.mineLevel() + " ≠ 광석 " + n.id() + " tier " + n.tier());
                        }
                    }
                }
            } else if (d.mineLevel() > 0) {
                err(w, "mine_level 은 mine_kind 와 함께");
            }
            if (d.type() == ItemType.TOOL) {
                kr.labyrinth.content.ToolSpec t = d.tool();
                if (t == null) {
                    err(w, "type: tool 인데 tool: {kind, tier, speed, bonus} 가 없음");
                    continue;
                }
                if (!t.isPickaxe()) err(w, "tool.kind 는 pickaxe: " + t.kind());
                if (t.tier() < 1) err(w, "tool.tier 는 1~6");
                for (int o = 1; o <= t.tier(); o++) {
                    Double sp = t.speed().get(o);
                    if (sp == null || sp <= 0) err(w, "tool.speed 에 등급 " + o + " 배율이 없음");
                }
                for (Integer k : t.speed().keySet()) if (k < 1 || k > t.maxHardness()) warn(w, "tool.speed 등급 " + k + " 는 캘 수 없는 등급 (무시)");
                int up = t.maxHardness();
                if (up > t.tier()) {
                    Double slow = t.speed().get(up);
                    Double own = t.speed().get(t.tier());
                    if (slow != null && own != null && slow > own) warn(w, "tool.speed 한 단계 위(" + up + ") 배율이 제 등급보다 빠름 — 곡괭이를 올릴 까닭이 줄어듦");
                }
                if (!d.stats().isEmpty()) err(w, "도구에는 능력치(stats)가 없다");
                if (d.raw() != null && d.raw().has("level_req")) warn(w, "도구에 level_req 가 있음 — 광산에는 레벨 조건이 없다 (무시)");
            }
        }
        if (!have) return;
        m.ores().values().forEach(n -> {
            ItemDef d = c.items().get(n.id());
            if (d == null || d.mineKind() != kr.labyrinth.content.MineKind.ORE) err("mine.ores." + n.id(), "items.yml 에 mine_kind: ore 아이템이 없음");
            if (n.ingot() != null && !n.ingot().isBlank()) {
                ItemDef ing = c.items().get(n.ingot());
                if (ing == null || ing.mineKind() != kr.labyrinth.content.MineKind.INGOT) err("mine.ores." + n.id(), "주괴 '" + n.ingot() + "' 가 items.yml 에 없음");
            }
            if (n.gem() != null && !n.gem().isBlank() && !m.gems().containsKey(n.gem())) err("mine.ores." + n.id(), "같은 등급 보석 '" + n.gem() + "' 이 mine.yml gems 에 없음");
        });
        m.gems().values().forEach(n -> {
            ItemDef d = c.items().get(n.id());
            if (d == null || d.mineKind() != kr.labyrinth.content.MineKind.GEM) err("mine.gems." + n.id(), "items.yml 에 mine_kind: gem 아이템이 없음");
        });
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
            if (kr.labyrinth.titles.AchievementRules.CLEAR_TYPES.contains(a.conditionType()) && cond.integer("floor", 0) <= 0) {
                err(w, "돌파 조건에 floor 가 없음");
            }
            if ("SPEED_CLEAR".equals(a.conditionType()) && cond.integer("seconds", 0) <= 0) err(w, "SPEED_CLEAR 에 seconds 가 없음");
            if (a.description().isBlank()) warn(w, "lore(칭호 설명) 없음");
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
