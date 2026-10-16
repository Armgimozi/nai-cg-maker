package kr.labyrinth.content;

import java.util.List;
import java.util.Map;
import kr.labyrinth.combat.WeaponAttack;

/**
 * items.yml 의 아이템 하나. stats 는 [최소, 최대] 굴림 범위(GDD §11.7 키).
 * <p>
 * {@code levelReq} (items.yml level_req): 장비는 <b>숨은 내부 레벨</b> — 정렬·강화 골드·드롭 단계에만 쓰고 표시·착용 제한은 없다.
 * 소모품은 그대로 사용 레벨. 장비 착용 조건은 {@code requires}(요구 능력치, {@link #requirement()}).
 * <p>
 * {@code attack} (0.3.5): 무기마다 공격 방식 — 간격·근접/원거리/시전·피해 종류 ({@link WeaponAttack}). 무기 종류(분류)는 없다.
 * 무기가 아니면 null. 무기인데 null 로 만들면 raw 의 attack 블록을 읽는다.
 * <p>
 * {@code unique} (0.3.5, unique_spec): 무기 고유 효과 하나 ({@link UniqueDef}). 무기가 아니면 null. 무기인데 null 로 만들면
 * raw 의 unique 블록을 읽는다 (없으면 null — 효과 없음).
 * <p>
 * {@code look} (0.3.5, look_spec §1.1): 방어구 겉모습 ({@link ArmorLook}). 방어구가 아니면 null. 파서가 정한다 —
 * items.yml {@code look}(세트 없는 투구) → 방패면 판금 → 세트 {@code look}(세트에 {@code look_effects: false} 면 평상복) → 없으면 평상복.
 * null 로 만들면 raw 의 look 키 → 방패면 판금 순으로 읽고, 그래도 없으면 null (파서가 세트에서 채운다, 시험용 정의는 평상복으로 다룸).
 * <p>
 * 광산 (0.3.6, 계약 tools/data/036/): {@code mineLevel} (items.yml {@code mine_level}) = 광물 등급 1~6 (구리·석영 1 … 오리하르콘·용혈석 6,
 * 광석·주괴·보석만, 아니면 0) · {@code mineKind} (items.yml {@code mine_kind}) = ore | ingot | gem · {@code tool} = 곡괭이
 * ({@code type: tool} 의 {@code tool:} 블록, {@link ToolSpec}). 0 / null 로 만들면 raw 에서 읽는다. 등급은 화면에 숫자로 쓰지 않는다.
 */
public record ItemDef(
        String id,
        String name,
        ItemType type,
        WeaponAttack attack,
        String armorSlot,
        String armorSet,
        Rarity rarity,
        int levelReq,
        StatRequirement requires,
        List<String> classes,
        Map<String, Range> stats,
        String setBonus,
        String aura,
        List<WeaponSkillDef> weaponSkills,
        int floor,
        boolean pool,
        List<String> sources,
        Params use,
        Params model,
        Params texture,
        String lore,
        Params raw,
        UniqueDef unique,
        ArmorLook look,
        int mineLevel,
        MineKind mineKind,
        ToolSpec tool) {

    /**
     * 무기 스킬. input = LEFT | RIGHT | SNEAK_LEFT | SNEAK_RIGHT.
     * pvpMult = 플레이어에게 주는 피해 배율 (items.yml {@code weapon_skills[].pvp_mult}, 기본 1, 0.1~1.0 — pvp_spec §6).
     */
    public record WeaponSkillDef(String id, String name, String input, double cooldown, double mana, Params params,
                                 String description, double pvpMult) {

        public WeaponSkillDef(String id, String name, String input, double cooldown, double mana, Params params,
                              String description) {
            this(id, name, input, cooldown, mana, params, description, 1.0);
        }
    }

    public ItemDef {
        if (type != ItemType.WEAPON) {
            attack = null;
            unique = null;
        } else {
            if (attack == null) attack = WeaponAttack.parse(raw);
            if (unique == null) unique = UniqueDef.parse(raw);
        }
        if (type != ItemType.ARMOR) {
            look = null;
        } else if (look == null) {
            look = raw == null ? null : ArmorLook.byId(raw.str("look"));
            if (look == null && "offhand".equals(armorSlot)) look = ArmorLook.HEAVY;
        }
        if (mineLevel <= 0 && raw != null) mineLevel = raw.integer("mine_level", 0);
        mineLevel = Math.max(0, mineLevel);
        if (mineKind == null && raw != null) mineKind = MineKind.byId(raw.str("mine_kind"));
        if (type != ItemType.TOOL) {
            tool = null;
        } else if (tool == null && raw != null) {
            tool = ToolSpec.parse(raw.sub("tool"));
        }
    }

    /** 광산 칸을 raw 에서 읽는다 (0.3.5 까지의 꼴). */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, StatRequirement requires, List<String> classes, Map<String, Range> stats,
                   String setBonus, String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool,
                   List<String> sources, Params use, Params model, Params texture, String lore, Params raw, UniqueDef unique,
                   ArmorLook look) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus, aura,
                weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique, look, 0, null, null);
    }

    /** 겉모습을 raw·방패에서 읽는다 (0.3.5 P1 까지의 꼴). */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, StatRequirement requires, List<String> classes, Map<String, Range> stats,
                   String setBonus, String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool,
                   List<String> sources, Params use, Params model, Params texture, String lore, Params raw, UniqueDef unique) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus, aura,
                weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique, null);
    }

    /** 고유 효과를 raw 에서 읽는다 (0.3.4 까지의 꼴 — 시험·도구용). */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, StatRequirement requires, List<String> classes, Map<String, Range> stats,
                   String setBonus, String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool,
                   List<String> sources, Params use, Params model, Params texture, String lore, Params raw) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus, aura,
                weaponSkills, floor, pool, sources, use, model, texture, lore, raw, null, null);
    }

    /**
     * 요구 능력치 없이 만든다 ({@link StatRequirement#NONE}) — 시험·도구용. 요구치가 필요하면 {@link #withRequires}.
     * attack 이 null 인 무기는 raw 의 attack 블록을 읽는다.
     */
    public ItemDef(String id, String name, ItemType type, WeaponAttack attack, String armorSlot, String armorSet,
                   Rarity rarity, int levelReq, List<String> classes, Map<String, Range> stats, String setBonus,
                   String aura, List<WeaponSkillDef> weaponSkills, int floor, boolean pool, List<String> sources,
                   Params use, Params model, Params texture, String lore, Params raw) {
        this(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, StatRequirement.NONE, classes, stats,
                setBonus, aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw);
    }

    public boolean isWeapon() { return type == ItemType.WEAPON; }
    /** 광산 곡괭이 ({@code type: tool} + tool 블록). */
    public boolean isTool() { return type == ItemType.TOOL && tool != null; }
    /** 광석·주괴·보석 (mine_kind 가 있는 재료). */
    public boolean isMineMaterial() { return type == ItemType.MATERIAL && mineKind != null && mineLevel > 0; }
    public boolean isGear() { return type.isGear(); }
    public boolean isShield() { return "offhand".equals(armorSlot); }

    /** 방어구 겉모습 (방어구가 아니면 null, 정하지 못했으면 평상복). */
    public ArmorLook armorLook() {
        if (type != ItemType.ARMOR) return null;
        return look == null ? ArmorLook.PLAIN : look;
    }

    /** 활처럼 당겨 쏘는 무기 ({@code attack.style: ranged}). */
    public boolean isRanged() { return attack != null && attack.ranged(); }

    /**
     * 착용 요구 능력치 — 무기·방어구(방패 포함)만. 장신구·재료·소모품은 언제나 요구 없음
     * (items.yml 에 적혀 있어도 무시 — ContentValidator 가 경고).
     */
    public StatRequirement requirement() {
        return (type == ItemType.WEAPON || type == ItemType.ARMOR) && requires != null ? requires : StatRequirement.NONE;
    }

    /** 요구 능력치만 바꾼 사본 (시험·도구용). */
    public ItemDef withRequires(StatRequirement r) {
        return new ItemDef(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, r == null ? StatRequirement.NONE : r,
                classes, stats, setBonus, aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique, look,
                mineLevel, mineKind, tool);
    }

    /** 곡괭이 구성만 바꾼 사본 (파서가 한 단계 위 빠르기를 채울 때). */
    public ItemDef withTool(ToolSpec t) {
        return new ItemDef(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus,
                aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique, look, mineLevel, mineKind, t);
    }

    /** 겉모습만 바꾼 사본 (파서가 세트 겉모습을 정할 때). */
    public ItemDef withLook(ArmorLook l) {
        return new ItemDef(id, name, type, attack, armorSlot, armorSet, rarity, levelReq, requires, classes, stats, setBonus,
                aura, weaponSkills, floor, pool, sources, use, model, texture, lore, raw, unique, l, mineLevel, mineKind, tool);
    }

    /**
     * 장비 단계 (0.3.5 items.yml {@code tier}, 숨김) = 그 장비를 만든 레벨 구간 Lv 5N−5 ~ 5N. 보스가 아닌 장비는 이웃 층 셋이
     * 나눠 주고(loot.yml band_tNN_*), 보스 장비는 그 단계 층 보스만. 화면에는 층이 나오지 않는다. 장비가 아니면 0.
     * ({@link #floor()} 는 같은 값 — 재료는 그 층 재료라는 뜻으로 그대로 쓴다.)
     */
    public int tier() { return isGear() ? floor : 0; }

    /** 직업 제한 없음 — 어느 직업이든(직업 없음 포함) 모든 장비를 쓴다 (GDD §4.4). */
    public boolean usableBy(String classId) { return true; }

    /**
     * {@code classes} 에 그 직업이 있는가 (비우면 모두). 0.3.5 부터 장비에는 classes 가 없다 (직업 문장만) —
     * 드롭 편향은 요구 능력치로 ({@code loot.yml own_build_bias}, LootRoller). 툴팁·대장간에는 표시하지 않는다.
     */
    public boolean suitedFor(String classId) {
        return classes.isEmpty() || (classId != null && classes.contains(classId));
    }

    /** 고유 효과가 있는 무기인가. */
    public boolean hasUnique() { return unique != null; }

    public WeaponSkillDef weaponSkill(String input) {
        for (WeaponSkillDef s : weaponSkills) if (s.input().equalsIgnoreCase(input)) return s;
        return null;
    }
}
