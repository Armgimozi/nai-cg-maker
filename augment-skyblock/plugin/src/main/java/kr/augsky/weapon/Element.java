package kr.augsky.weapon;

import java.util.Map;

/** 무기 속성. 이름 색과 설명에 쓴다. (등급이 아니라 무기의 '재질/속성'일 뿐이다) */
public final class Element {
    private record E(String korean, String color) {}

    private static final Map<String, E> MAP = Map.ofEntries(
            Map.entry("iron", new E("철", "#d8dde3")),
            Map.entry("stone", new E("돌", "#b8b8b8")),
            Map.entry("wood", new E("나무", "#d9a86a")),
            Map.entry("bone", new E("뼈", "#ece6c8")),
            Map.entry("copper", new E("구리", "#e8916a")),
            Map.entry("flame", new E("화염", "#ff8a3d")),
            Map.entry("frost", new E("서리", "#9ad8ff")),
            Map.entry("storm", new E("번개", "#c8b8ff")),
            Map.entry("venom", new E("독", "#a8e060")),
            Map.entry("ocean", new E("바다", "#5ad0e8")),
            Map.entry("earth", new E("대지", "#d0a868")),
            Map.entry("wind", new E("바람", "#b8f0e0")),
            Map.entry("holy", new E("빛", "#fff0a8")),
            Map.entry("nature", new E("숲", "#8ad870")),
            Map.entry("blood", new E("피", "#ff5a6e")),
            Map.entry("abyss", new E("심연", "#b06bff")),
            Map.entry("shadow", new E("그림자", "#a0a0c0")),
            Map.entry("star", new E("별", "#a8b8ff")),
            Map.entry("crystal", new E("수정", "#d0a0ff")),
            Map.entry("prism", new E("프리즘", "gradient")),
            Map.entry("gold", new E("황금", "#ffd84d")),
            Map.entry("ender", new E("엔더", "#5ae8c0")),
            Map.entry("sun", new E("태양", "#ffd04a")),
            Map.entry("doom", new E("종말", "#ff3a6a"))
    );

    private Element() {}

    public static String korean(String element) {
        E e = MAP.get(element);
        return e == null ? element : e.korean();
    }

    /** MiniMessage 로 색을 입힌다. */
    public static String wrap(String element, String text) {
        E e = MAP.get(element);
        if (e == null) return "<white>" + text;
        if (e.color().equals("gradient")) return "<gradient:#ff6b9d:#ffd36b:#6bffb0:#6bc8ff:#c86bff>" + text + "</gradient>";
        return "<" + e.color() + ">" + text + "</" + e.color() + ">";
    }

    /** 무기를 얻는 곳(pool) 의 한글 설명. weapons.yml 의 source 로 덮어쓸 수 있다. */
    public static String poolSource(String pool) {
        return switch (pool) {
            case "basic", "island" -> "섬의 재료로 작업대에서 만든다";
            case "frost" -> "서리 정수로 만든다 (서리 균열)";
            case "flame" -> "화염 정수로 만든다 (화염 균열)";
            case "void" -> "공허 정수로 만든다 (공허 균열)";
            case "boss" -> "프리즘 결정으로 만든다";
            case "prism" -> "프리즘 결정 4개로 만든다";
            default -> "";
        };
    }

    public static String poolName(String pool) {
        return switch (pool) {
            case "basic" -> "섬 초반";
            case "island" -> "섬 재료";
            case "frost" -> "서리 균열";
            case "flame" -> "화염 균열";
            case "void" -> "공허 균열";
            case "boss" -> "보스";
            case "prism" -> "프리즘";
            default -> pool;
        };
    }
}
