package kr.augsky.vfx;

/**
 * 시전한 무기의 등급(pool)별 연출 크기. 수만 늘리지 않고 등급마다 새로운 종류가 하나씩 붙는다:
 * 초반 = 입자, 섬 = 속성색 빛 조각, 균열 = 속성 재질(얼음 조각·불꽃 혀·공허 틈), 보스 = 구조물(마법진·기둥·파편),
 * 프리즘 = 전용 연출 + 모든 조각에 무지개 갈라짐. 몬스터는 MOB / 보스 몬스터는 BOSS_MOB.
 */
public enum Tier {
    //        rank sprite packet density debris yamlKeep sfx
    BASIC(0, 3, 30, 1.00, 0, 1.00, 0),
    ISLAND(1, 8, 45, 1.15, 0, 1.00, 1),
    RIFT(2, 14, 60, 1.35, 3, 0.6, 1),
    BOSS(3, 28, 80, 1.60, 6, 0.55, 2),
    PRISM(4, 40, 100, 1.90, 10, 0.45, 3),
    MOB(1, 6, 30, 1.00, 0, 1.00, 0),
    BOSS_MOB(3, 24, 80, 1.50, 6, 0.80, 2);

    public final int rank;
    /** 한 번 시전에 동시에 떠 있을 수 있는 표시 엔티티 수 */
    public final int sprites;
    /** 받는 사람 한 명에게 한 틱에 보내는 입자 패킷 수 (YAML 입자 포함) */
    public final int packets;
    public final double density;
    public final int debris;
    /** 원래 YAML 입자를 얼마나 남기는지 (팩을 받은 사람 기준). 높은 등급은 조각이 대신하므로 줄인다 */
    public final double yamlKeep;
    public final int sfxLayers;

    Tier(int rank, int sprites, int packets, double density, int debris, double yamlKeep, int sfxLayers) {
        this.rank = rank;
        this.sprites = sprites;
        this.packets = packets;
        this.density = density;
        this.debris = debris;
        this.yamlKeep = yamlKeep;
        this.sfxLayers = sfxLayers;
    }

    public boolean mob() {
        return this == MOB || this == BOSS_MOB;
    }

    public static Tier ofPool(String pool) {
        if (pool == null) return BASIC;
        return switch (pool) {
            case "island" -> ISLAND;
            case "frost", "flame", "void" -> RIFT;
            case "boss" -> BOSS;
            case "prism" -> PRISM;
            default -> BASIC;
        };
    }

    /** 같은 등급 안의 무게: 짧은 재사용 기술 / 무거운 기술 / 궁극기. 섬광·하늘 연출·큰 별은 궁극기만 쓴다 */
    public enum Weight {
        LIGHT(0.6, 0.75), HEAVY(1.0, 1.0), ULT(1.35, 1.3);

        public final double sprites, packets;

        Weight(double sprites, double packets) {
            this.sprites = sprites;
            this.packets = packets;
        }

        public static Weight of(int slot, double cooldown) {
            if (slot == 3 || cooldown >= 30) return ULT;
            if (cooldown >= 8) return HEAVY;
            return LIGHT;
        }
    }
}
