package kr.labyrinth.items;

import org.bukkit.entity.Player;

/**
 * 방어구 겉모습 4부위 효과 창구 ({@code services.looks()}, look_spec §1.3). 다른 모듈은 이것만 부른다 — 실제 구현은
 * {@link ArmorLookService} (items 모듈이 켬). 기본 {@link #NONE} 은 아무 효과 없음.
 * 판금 버팀(밀려남·발 묶기 줄이기)은 파생 능력치({@code DerivedStats.knockbackResistance · ccResist})로 바로 든다.
 */
public interface LookEffects {

    LookEffects NONE = new LookEffects() {};

    /** 가죽 4부위 구르기 중인가 (그동안 피할 수 있는 공격은 모두 회피). */
    default boolean tumbling(Player player) { return false; }

    /** 직업 스킬·무기 스킬을 썼다 — 웅크린 채 썼으면 잠깐 구르기를 막는다 (웅크리기 조합 스킬 오입력 방지). */
    default void onSkill(Player player) {}
}
