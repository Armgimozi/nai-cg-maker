package kr.labyrinth.titles;

import kr.labyrinth.content.AchievementDef;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/**
 * 업적·칭호 (titles.yml). 구현이 event.* (MobKill/FloorClear/LevelUp/ItemObtain/Craft/PvpMatchEnd) 를 듣고
 * 조건을 판정, 서버 최초는 ServerRecords 로 확정, 방송·보상·칭호 장착(채팅/탭/이름표 접두어)·보너스(StatContributor).
 * 소유: ui+titles 담당. 기본 구현 {@link BasicTitleService}.
 */
public interface TitleService {

    /**
     * 업적 지급 (이미 있으면 false). 보상·알림·방송 포함.
     */
    boolean grant(Player player, String achievementId);

    /** 레벨·누적 통계처럼 상태로 판정되는 업적을 다시 검사 (접속 시 등). */
    void recheck(Player player);

    /** 칭호 장착 (달성한 것만). null = 해제. */
    boolean equip(Player player, String achievementId);

    /** 장착 칭호 정의 (없으면 null). */
    AchievementDef equipped(Player player);

    /** 채팅/탭/이름표 접두어 (없으면 Component.empty()). */
    Component prefix(Player player);

    // ── ui+titles 담당 추가 ───────────────────────────────────────────────

    /**
     * 칭호 스탯 보너스를 잠시 끈다/켠다 (PvP 매치 규칙 §18.3 "칭호 보너스 꺼짐" — pvp 모듈이 매치 시작/종료 때 호출).
     * 기본 구현은 아무것도 안 한다.
     */
    default void setBonusSuppressed(Player player, boolean suppressed) {}

    /** 업적 진행도 [현재, 목표] (UI 용). 기본: 달성했으면 [1,1] 아니면 [0,1]. */
    default long[] progress(Player player, String achievementId) {
        return new long[] {kr.labyrinth.Services.get().data().get(player).hasAchievement(achievementId) ? 1 : 0, 1};
    }
}
