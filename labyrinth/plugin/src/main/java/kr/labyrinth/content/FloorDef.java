package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** floors.yml 의 층 하나 (1~10). palette 값은 Material 이름 목록. */
public record FloorDef(
        int number,
        String name,
        String subtitle,
        String theme,
        IntRange levelRange,
        String description,
        Map<String, List<String>> palette,
        List<Params> decor,
        String liquid,
        int roomHeight,
        int cells,
        Map<String, Integer> rooms,
        IntRange mobDensity,
        List<String> mobs,
        String elite,
        String boss,
        String gimmick,
        Params gimmickParams,
        Params ambient,
        Params raw) {

    public List<String> palette(String key) { return palette.getOrDefault(key, List.of()); }
    public int rooms(String type) { return rooms.getOrDefault(type, 0); }
}
