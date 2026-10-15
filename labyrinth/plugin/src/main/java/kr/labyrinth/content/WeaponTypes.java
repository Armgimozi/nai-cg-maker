package kr.labyrinth.content;

import java.util.Collection;
import java.util.Map;
import kr.labyrinth.stats.Stat;

/**
 * 무기 종류(items.yml weapon_type) 공통 규칙 — 순수 로직, 단위 테스트 대상 (GDD §4.4, §11.2).
 * <ul>
 *   <li><b>직업 제한 없음</b>: 어느 직업이든 모든 무기·방어구·장신구를 쓰고, 미궁 무기면 무엇을 들어도 직업 스킬이 나간다.</li>
 *   <li>classes.yml {@code weapon_types} = 그 직업의 <b>추천 무기</b>. 추천 무기를 들면 직업 스킬 재사용 대기 −10%.</li>
 *   <li>직업 스킬 피해는 무기 종류 피해 배율을 추천 무기 기준으로 환산한다 — 대검(×1.55)을 든 그림자도 같은 단계 단검(×0.62)을
 *       든 것과 직업 스킬 위력이 같다. 기본 공격·무기 스킬은 든 무기 그대로.</li>
 * </ul>
 */
public final class WeaponTypes {

    /** 추천 무기를 들었을 때 직업 스킬 재사용 대기 감소 비율. */
    public static final double RECOMMENDED_COOLDOWN_CUT = 0.10;

    /** 같은 단계 장검 = 1.0 피해 배율 (GDD §11.2 — items.yml 무기 피해가 이 배율로 만들어졌다). */
    private static final Map<String, Double> DAMAGE_SCALE = Map.of("sword_shield", 1.00, "greatsword", 1.55, "bow", 1.30,
            "staff", 1.10, "scepter", 0.95, "dagger", 0.62);

    private static final Map<String, String> NAMES = Map.of("sword_shield", "검과 방패", "greatsword", "대검", "bow", "활",
            "staff", "지팡이", "scepter", "홀", "dagger", "단검");

    private WeaponTypes() {}

    /** 무기 종류 이름 (검과 방패, 대검 …). 모르는 종류는 id 그대로. */
    public static String name(String type) {
        if (type == null) return "";
        return NAMES.getOrDefault(type, type);
    }

    /** 피해 배율을 아는 종류인가 (ContentValidator 경고용). */
    public static boolean known(String type) { return type != null && DAMAGE_SCALE.containsKey(type); }

    /** 무기 종류 피해 배율 (모르는 종류 1.0). */
    public static double damageScale(String type) {
        return type == null ? 1.0 : DAMAGE_SCALE.getOrDefault(type, 1.0);
    }

    /**
     * 요구 능력치를 못 맞춰 능력치가 안 붙는 무기는 '든 무기 없음'으로 본다 (EquipRules 와 같은 기준).
     * @param stats 판정 능력치 = 직업 기본 + 분배 + 칭호 ({@link StatRequirement#playerStats}, StatService.requirementStats)
     */
    public static ItemDef effective(ItemDef held, Map<Stat, Integer> stats) {
        return held != null && held.isWeapon() && held.requirement().met(stats) ? held : null;
    }

    /** 직업 스킬을 쓸 수 있는가 — 직업만 있으면 무엇을 들었든 (사용자 결정 "언제나"). 무기가 없으면 환산 배율 1. */
    public static boolean canCastClassSkill(ClassDef cls, ItemDef held) {
        return cls != null;
    }

    /** 든 무기가 그 직업의 추천 무기인가. */
    public static boolean recommended(ClassDef cls, ItemDef held) {
        return cls != null && held != null && held.isWeapon() && cls.recommendsWeapon(held.weaponType());
    }

    /** 직업 스킬 기본 재사용 대기 — 추천 무기면 −10% (재사용 감소 스탯은 그다음 {@code CooldownTracker.effective}). */
    public static double classSkillCooldown(ClassDef cls, ItemDef held, double base) {
        return recommended(cls, held) ? base * (1.0 - RECOMMENDED_COOLDOWN_CUT) : base;
    }

    /** 직업 스킬 피해 환산 배율 = 추천 무기 배율 ÷ 든 무기 배율. 미궁 무기를 안 들었거나 추천 무기면 1. */
    public static double classSkillScale(ClassDef cls, ItemDef held) {
        if (cls == null || held == null || !held.isWeapon() || cls.weaponTypes().isEmpty()) return 1.0;
        if (cls.recommendsWeapon(held.weaponType())) return 1.0;
        return damageScale(cls.weaponTypes().get(0)) / damageScale(held.weaponType());
    }

    /** 처음 전직할 때 줄 무기: 추천 무기 중 가장 낮은 등급(희귀도 → 층 → 내부 레벨 순). 없으면 null. */
    public static ItemDef starterWeapon(Collection<ItemDef> items, ClassDef cls) {
        if (cls == null) return null;
        ItemDef best = null;
        for (ItemDef it : items) {
            if (!it.isWeapon() || !cls.recommendsWeapon(it.weaponType()) || !it.suitedFor(cls.id())) continue;
            if (best == null || it.rarity().ordinal() < best.rarity().ordinal()
                    || (it.rarity() == best.rarity() && (it.floor() < best.floor()
                    || (it.floor() == best.floor() && it.levelReq() < best.levelReq())))) best = it;
        }
        return best;
    }
}
