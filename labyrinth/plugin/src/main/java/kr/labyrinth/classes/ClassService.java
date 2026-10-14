package kr.labyrinth.classes;

import kr.labyrinth.content.ClassDef;
import org.bukkit.entity.Player;

/**
 * 직업·직업 스킬·마나·쿨다운 (classes.yml, classes/skills/*). 소유: classes 담당.
 * 기본 구현 {@link BasicClassService}: 직업 저장 + 마나 풀(시간 경과 재생)만, 스킬 없음.
 * 구현은 F/Q(손 바꾸기·버리기) 입력을 직접 듣는다(미궁 무기를 들었을 때만 가로채기).
 */
public interface ClassService {

    /** 플레이어 직업 (없으면 null). */
    ClassDef classOf(Player player);

    /** 전직/변경: PlayerData 저장 + 스탯 재계산 + 마나 가득. classId null = 직업 없음. */
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
}
