package kr.labyrinth.core;

/**
 * 파티 인원 배율 (config.yml party, GDD §2.5). n = 인스턴스 인원.
 * 몹 HP ×(1 + hpPerMember×(n−1)), 몹 피해 ×(1 + dmgPerMember×(n−1)), 보상 ×(1 + rewardPerMember×(n−1)).
 * 혼자(n = 1)일 때만 몹·보스 HP ×soloHp, 피해 ×soloDamage (솔로 보정 — 보상은 그대로).
 */
public record PartyScaling(int maxSize, double hpPerMember, double dmgPerMember, double rewardPerMember,
                           double soloHp, double soloDamage) {

    /** 솔로 보정 코드 기본값 (= jar 의 config.yml party.solo_hp / solo_damage). */
    public static final double DEFAULT_SOLO = 0.85;
    public static final PartyScaling DEFAULT = new PartyScaling(5, 0.6, 0.08, 0.05, DEFAULT_SOLO, DEFAULT_SOLO);

    /** 솔로 보정 없음 (×1.0). */
    public PartyScaling(int maxSize, double hpPerMember, double dmgPerMember, double rewardPerMember) {
        this(maxSize, hpPerMember, dmgPerMember, rewardPerMember, 1.0, 1.0);
    }

    public double hp(int n) { return n <= 1 ? soloHp : 1.0 + hpPerMember * (n - 1); }
    public double damage(int n) { return n <= 1 ? soloDamage : 1.0 + dmgPerMember * (n - 1); }
    public double reward(int n) { return 1.0 + rewardPerMember * (Math.max(1, n) - 1); }
}
