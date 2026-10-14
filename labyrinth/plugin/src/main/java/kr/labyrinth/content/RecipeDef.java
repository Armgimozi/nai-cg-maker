package kr.labyrinth.content;

import java.util.Map;

/** recipes.yml. materials 는 순서 보존(아이템 id → 개수). */
public record RecipeDef(String id, String result, String category, String station, Map<String, Integer> materials,
                        int gold, int levelReq, int amount) {}
