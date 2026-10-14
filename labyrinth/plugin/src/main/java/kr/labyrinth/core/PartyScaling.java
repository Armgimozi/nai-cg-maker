package kr.labyrinth.core;

/**
 * 파티 인원 배율 (config.yml party, GDD §2.5). n = 인스턴스 인원.
 * 몹 HP ×(1 + hpPerMember×(n−1)), 몹 피해 ×(1 + dmgPerMember×(n−1)), 보상 ×(1 + rewardPerMember×(n−1)).
 */
public record PartyScaling(int maxSize, double hpPerMember, double dmgPerMember, double rewardPerMember) {

    public static final PartyScaling DEFAULT = new PartyScaling(10, 0.6, 0.08, 0.05);

    public double hp(int n) { return 1.0 + hpPerMember * (Math.max(1, n) - 1); }
    public double damage(int n) { return 1.0 + dmgPerMember * (Math.max(1, n) - 1); }
    public double reward(int n) { return 1.0 + rewardPerMember * (Math.max(1, n) - 1); }
}
