package kr.labyrinth.content;

import java.util.List;
import java.util.Map;
import java.util.NavigableMap;

/** items.yml sets: 세트 효과. bonuses 키 = 착용 개수(이상), 값 = 스탯 키 → 수치. */
public record ItemSetDef(String id, String name, String look, List<String> pieces,
                         NavigableMap<Integer, Map<String, Double>> bonuses) {}
