package kr.souls.progression;

import kr.souls.combat.DamageCalc;

/**
 * 능력치에서 나온 값 (5.2, 5.9 의 표). 능력치 창·레벨 올리기 창·출신 확인 창·시험 줄 STATS 가 같은 셈을 쓴다. 순수 클래스
 * (13.1 의 StatsTest 가 5.1 의 "시작 때의 값" 표를 본다).
 *
 * @param attack      든 근접 무기의 공격력 (없으면 0). twoHanded 면 양손 잡기 (왼손이 빈 근접 무기, 근력 ×1.5)
 * @param attackSpeed 공격 속도 배율 (1.0 = 그대로). 민첩 하나로 정해지고 모든 무기에 같다 (든 무기가 없어도 보인다)
 * @param spellPower  든 촉매 (없으면 왼손, 단축 슬롯의 첫 촉매) 의 술법 세기, 없으면 0
 * @param regenPerSec 스태미나 초당 회복 (그 무게 단계에서)
 * @param move        이동 속도 덧셈 몫 (0.04 = +4%, 무게 단계의 걷기 배율은 따로)
 * @param ailment     상태 이상 저항 (0.18 = 해로운 효과 길이 ×0.82)
 */
public record Derived(double maxHp, double defense, double maxMana, double magicRes, int slots, double maxStamina, double regenPerSec,
                      double attack, boolean twoHanded, double attackSpeed, double weight, double cap, LoadTiers.Tier tier, double move,
                      double spellPower, double ailment) {

    /**
     * @param melee      든 근접 무기 (없으면 null 또는 BARE)
     * @param twoHanded  양손 잡기 (왼손이 비었다)
     * @param catalyst   술 세기를 셈할 촉매 (없으면 null)
     * @param weight     장비 무게 (5.8)
     * @param regenTick  스태미나 틱당 기본 회복 (combat.stamina.regen-per-tick, 2.2)
     */
    public static Derived of(StatBlock s, StatCurves c, LoadTiers tiers, DamageCalc.Arms melee, boolean twoHanded, DamageCalc.Arms catalyst,
                             double weight, double regenTick) {
        int lv = s.level();
        double cap = c.equipLoad.at(s.str());
        LoadTiers.Tier tier = tiers.of(weight, cap);
        double regen = regenTick * c.regenScale.at(s.end()) * tier.regen() * 20;
        boolean hasMelee = melee != null && melee.attack() > 0;
        return new Derived(c.maxHealth.at(s.vig()), DamageCalc.defense(c, lv, s.vig()), c.maxMana.at(s.mnd()),
                DamageCalc.magicRes(c, lv, s.mnd()), c.memorySlots.at(s.mnd()), c.maxStamina.at(s.end()), regen,
                hasMelee ? DamageCalc.ar(c, melee, s.str(), twoHanded) : 0, hasMelee && twoHanded,
                DamageCalc.attackSpeed(c, s.dex()), weight, cap, tier, c.moveSpeed.at(s.dex()),
                catalyst == null ? 0 : DamageCalc.spellPower(c, catalyst, s.intel()), c.statusResist.at(s.intel()));
    }
}
