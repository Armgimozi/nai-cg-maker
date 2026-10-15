package kr.labyrinth.titles;

import kr.labyrinth.content.AchievementDef;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/**
 * 칭호 (titles.yml). 칭호마다 서버에서 단 한 명만 가진다 — 조건을 가장 먼저 채운 사람이 주인(records.yml {@code title.<id>}).
 * 구현이 event.* (MobKill/FloorClear/LevelUp/ItemObtain/Craft/Enhance) 와 미로 보물을 듣고 그 사건으로만 판정한다.
 * 조건은 주인이 생기기 전까지 비밀. 방송·보상·칭호 장착(채팅/탭/이름표 접두어)·보너스(StatContributor).
 * 소유: ui+titles 담당. 기본 구현 {@link BasicTitleService}.
 */
public interface TitleService {

    /**
     * 칭호를 이 플레이어에게 준다 (관리자 지급). 이미 다른 사람이 주인이면 false. 보상·알림·방송 포함.
     */
    boolean grant(Player player, String achievementId);

    /** 주인 기록(records.yml)과 플레이어 데이터를 맞추고 접두어·보너스를 다시 건다 (칭호를 새로 주지는 않는다). */
    void recheck(Player player);

    /** 칭호 장착 (주인인 것만). null = 해제. */
    boolean equip(Player player, String achievementId);

    /** 장착 칭호 정의 (없으면 null). */
    AchievementDef equipped(Player player);

    /** 채팅/탭/이름표 접두어 (없으면 Component.empty()). */
    Component prefix(Player player);

    // ── ui+titles 담당 추가 ───────────────────────────────────────────────

    /** 미로 보물 사건 (kind = chest | gold_chest | vault | mimic). 카운터는 부르는 쪽이 이미 올렸다. */
    default void onTreasure(Player player, String kind) {}

    /**
     * 칭호 스탯 보너스를 잠시 끈다/켠다 (이벤트·시험용 — 지금은 부르는 곳 없음). 기본 구현은 아무것도 안 한다.
     */
    default void setBonusSuppressed(Player player, boolean suppressed) {}
}
