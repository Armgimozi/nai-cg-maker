package kr.labyrinth.content;

import java.util.Map;

/**
 * titles.yml achievements (칭호마다 서버에서 단 한 명). conditionType = FIRST_CLEAR | CLEAR | SOLO_CLEAR | NO_DEATH_CLEAR |
 * DIFFICULTY_CLEAR | SPEED_CLEAR | KILL | BOSS_KILL | LEVEL | OBTAIN_RARITY | CRAFT | ENHANCE | TREASURE.
 * condition 에는 type 외 파라미터(floor, count, mob, boss, rarity …)가 들어 있다. description = titles.yml {@code lore}
 * (조건을 암시하지 않는 짧은 글 — 예전 키 description 도 읽음). category·hidden 은 예전 키 (지금은 안 씀).
 */
public record AchievementDef(String id, String name, String description, String category, String conditionType,
                             Params condition, String title, Map<String, Double> bonus, boolean broadcast,
                             boolean hidden, int rewardGold, Map<String, Integer> rewardItems) {}
