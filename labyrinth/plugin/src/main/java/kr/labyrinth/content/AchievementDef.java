package kr.labyrinth.content;

import java.util.Map;

/**
 * titles.yml achievements. conditionType = FIRST_CLEAR | CLEAR | SOLO_CLEAR | NO_DEATH_CLEAR | DIFFICULTY_CLEAR |
 * SPEED_CLEAR | KILL | BOSS_KILL | LEVEL | OBTAIN_RARITY | CRAFT | PVP_WIN | PVP_STREAK | PVP_RATING | PVP_FIRST_WIN | ENHANCE.
 * condition 에는 type 외 파라미터(floor, count, mob, boss, rarity …)가 들어 있다.
 */
public record AchievementDef(String id, String name, String description, String category, String conditionType,
                             Params condition, String title, Map<String, Double> bonus, boolean broadcast,
                             boolean hidden, int rewardGold, Map<String, Integer> rewardItems) {}
