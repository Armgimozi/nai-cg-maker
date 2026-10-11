package kr.souls.enemy;

import org.bukkit.entity.Mob;

/**
 * 우리 적 하나 (M1 P1-0 계약). 몸은 바닐라 몹 (보이지 않게 하는 것은 M2 의 자체 제작 몸), 체력은 가상 체력 (6.1, P1b 의
 * VirtualHealth). 읽는 쪽은 P1a (HitQuery·MoveRunner), P3 (치명타), P7 (화살). 바꾸는 것은 Foes.hit 만이다.
 * 나중 묶음이 채우는 것: {@link #inStartupOrActive} (P2b 의 두뇌, 그때까지 거짓), {@link #yawDelta} (P3 의 등 뒤 치명타, 그때까지 0).
 */
public interface Foe {
    /** 몸 (바닐라 몹, 태그 souls_foe) */
    Mob entity();

    /** enemies.yml 의 id (dummy, post, mob_bare …) */
    String id();

    /** 남은 가상 체력 */
    double hp();

    /** 가상 체력 최대치 (생길 때 enemies.yml hp × 난이도 enemy-health) */
    double max();

    /** 방어력 (3.7 의 방어 공식) */
    double def();

    /** 흡수율 (0..1) 과 약점 배율 (1 이면 보통): 피해 종류마다. 기본은 흡수 없음, 약점 없음 (enemies.yml 이 생기면 P1b·P5a) */
    default double absorb(kr.souls.combat.Hit.Type type) {
        return 0;
    }

    default double weak(kr.souls.combat.Hit.Type type) {
        return 1;
    }

    /** 가상 체력을 깎는다 (Foes.hit 만 부른다). 남은 체력을 돌려준다 (0 밑으로 내려가지 않는다). */
    double hurt(double amount);

    /** 준비·판정 중인가 (맞받아치기, 등 뒤 치명타 금지). P2b 의 두뇌 전에는 늘 거짓 */
    default boolean inStartupOrActive() {
        return false;
    }

    /** 지난 틱에 돈 각도 (도, 절댓값). P3 의 등 뒤 치명타 ("30° 넘게 돌면 안 된다") 전에는 0 */
    default double yawDelta() {
        return 0;
    }

    /** 살아 있는가 (몸이 세계에 있고 가상 체력이 남았다) */
    default boolean alive() {
        Mob m = entity();
        return m != null && m.isValid() && !m.isDead() && hp() > 0;
    }
}
