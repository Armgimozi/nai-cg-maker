package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** arenas.yml — 파티 PvP 투기장. 세부 파라미터는 raw/Params 에서 읽는다(GDD §18). */
public record ArenaDef(String id, String name, String description, String theme, int sizeX, int sizeZ, int height,
                       Map<String, List<String>> palette, String layout, Params layoutParams, IntRange teamSize,
                       int weight, Params spawns, List<Params> hazards, Params objective, Params ambient, Params raw) {}
