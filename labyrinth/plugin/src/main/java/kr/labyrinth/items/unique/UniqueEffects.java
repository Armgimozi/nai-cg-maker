package kr.labyrinth.items.unique;

import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.UniqueDef;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 무기 고유 효과 창구 ({@code services.unique()}, unique_spec §7). 다른 모듈은 이것만 부른다 — 실제 구현은
 * {@link UniqueEffectService} (items 모듈이 켬). 기본 {@link #NONE} 은 아무 효과 없음.
 */
public interface UniqueEffects {

    UniqueEffects NONE = new UniqueEffects() {};

    /** 플레이어가 지금 쓰는 고유 효과 (손에 든 무기 · 요구 능력치 충족). 없으면 null. */
    default UniqueDef current(Player player) { return null; }

    /** 장비 재계산 때 (EquipmentListener): 손에 든 무기(없으면 null)와 요구 능력치를 채웠는지. */
    default void held(Player player, ItemDef weapon, boolean usable) {}

    /** 직업 스킬·무기 스킬을 썼다 (과부하 충전). */
    default void onSkill(Player player) {}

    /** 대상 방어 깎기 비율 (갑옷 부수기 중첩 × pct, 0 ~ 0.4). DamageService 가 방어에 곱한다. */
    default double defenseShred(LivingEntity target) { return 0; }
}
