package kr.labyrinth.classes;

import kr.labyrinth.content.ClassDef;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/**
 * 직업·직업 스킬·마나·쿨다운 (classes.yml, classes/skills/*). 소유: classes 담당.
 * 기본 구현 {@link BasicClassService}: 직업 저장 + 마나 풀(시간 경과 재생)만, 스킬 없음.
 * 실제 구현 {@link LabyrinthClassService}: F/Q(손 바꾸기·버리기) 입력을 직접 듣는다(직업이 있으면 항상 가로채기).
 */
public interface ClassService {

    /** 플레이어 직업 (없으면 null). */
    ClassDef classOf(Player player);

    /** 전직/변경: PlayerData 저장 + 스탯 재계산 + 마나 가득. classId null = 직업 없음. 검사·안내 없음(관리자용). */
    void setClass(Player player, String classId);

    double mana(Player player);

    double maxMana(Player player);

    /** 마나가 충분하면 소모하고 true. */
    boolean useMana(Player player, double amount);

    void restoreMana(Player player, double amount);

    /** 직업 스킬 입력 처리. input = SWAP | SNEAK_SWAP | DROP | SNEAK_DROP. @return 소비했으면 true */
    boolean handleSkillInput(Player player, String input);

    /** 남은 재사용 대기(초). */
    double cooldownRemaining(Player player, String skillId);

    // ── 확장 (classes 담당 추가) ──────────────────────────────────────────

    /**
     * 플레이어가 고른 전직/직업 변경 (전직관 NPC·직업 메뉴·/직업 선택). 검사(존재·미궁 진행 중 금지·같은 직업) + 안내 메시지
     * + 연출까지 하고 {@link #setClass} 를 부른다. @return 바뀌었으면 true
     */
    default boolean changeClass(Player player, String classId) {
        if (classId == null || classId.equals(classOf(player) == null ? null : classOf(player).id())) return false;
        setClass(player, classId);
        return true;
    }

    /** HUD 용 직업 스킬 한 줄 (키·이름·쿨다운). 직업이 없으면 빈 컴포넌트. */
    default Component skillBar(Player player) { return Component.empty(); }

    /** 채널링(부활의 성가 등) 중인가. */
    default boolean isChanneling(Player player) { return false; }
}
