package kr.labyrinth.village;

import java.util.Locale;
import java.util.Set;

/**
 * 블록 종류 분류 (블록 id 문자열만 본다 — 서버 없이 테스트 가능, 비동기 스레드에서도 안전).
 * 화이트리스트 방식: 자연 지형·식물·나무가 아니면 전부 {@link Kind#UNNATURAL}(사람/구조물이 만든 블록)로 본다.
 */
public final class Nature {

    public enum Kind {
        AIR,
        /** 물·용암·거품 기둥. */
        LIQUID,
        /** 얼음 — 언 물이라 물처럼 취급(시드 고를 때 피함). */
        ICE,
        /** 땅높이 계산에서 빼는 식물·눈 한 겹 (R 안에서는 지움). */
        PLANT,
        /** 나무 줄기 (원목·목재·버섯 줄기/갓·맹그로브 뿌리). */
        LOG,
        /** 잎 (persistent=false 만 자연 — 호출하는 쪽이 확인). */
        LEAVES,
        /** 나무에 붙는 것 (덩굴·코코아·벌집·창백한 이끼 등). */
        TREE_PART,
        /** 자연 고체 지형 (땅높이 = 이 종류의 맨 위 블록). */
        GROUND,
        UNNATURAL
    }

    private static final Set<String> GROUND = Set.of("stone", "granite", "diorite", "andesite", "deepslate", "tuff", "calcite",
            "dripstone_block", "sandstone", "red_sandstone", "terracotta", "dirt", "coarse_dirt", "rooted_dirt", "grass_block",
            "podzol", "mycelium", "mud", "clay", "gravel", "sand", "red_sand", "snow_block", "powder_snow", "moss_block",
            "pale_moss_block", "amethyst_block", "budding_amethyst", "smooth_basalt", "obsidian", "magma_block", "bedrock",
            "mossy_cobblestone", "sculk", "infested_stone", "infested_deepslate", "raw_iron_block", "raw_copper_block",
            "bone_block", "cinnabar", "sulfur", "potent_sulfur");

    private static final Set<String> PLANT = Set.of("short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "bush",
            "firefly_bush", "short_dry_grass", "tall_dry_grass", "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet",
            "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley",
            "sunflower", "lilac", "rose_bush", "peony", "torchflower", "pitcher_plant", "pink_petals", "wildflowers", "leaf_litter",
            "closed_eyeblossom", "open_eyeblossom", "cactus_flower", "sweet_berry_bush", "snow", "brown_mushroom", "red_mushroom",
            "sugar_cane", "cactus", "bamboo", "bamboo_sapling", "pumpkin", "melon", "azalea", "flowering_azalea", "moss_carpet",
            "pale_moss_carpet", "big_dripleaf", "big_dripleaf_stem", "small_dripleaf", "spore_blossom", "glow_lichen",
            "hanging_roots", "lily_pad", "seagrass", "tall_seagrass", "kelp", "kelp_plant", "pointed_dripstone", "cave_vines",
            "cave_vines_plant", "sculk_vein", "amethyst_cluster", "large_amethyst_bud", "medium_amethyst_bud", "small_amethyst_bud",
            "red_shrub", "sulfur_spike");

    private static final Set<String> TREE_PART = Set.of("vine", "cocoa", "bee_nest", "pale_hanging_moss", "resin_clump",
            "mangrove_propagule", "creaking_heart");

    private Nature() {}

    /** "minecraft:oak_log[axis=y]" / "OAK_LOG" / "oak_log" → 종류. */
    public static Kind kind(String block) {
        String k = key(block);
        if (k.equals("air") || k.equals("cave_air") || k.equals("void_air")) return Kind.AIR;
        if (k.equals("water") || k.equals("lava") || k.equals("bubble_column")) return Kind.LIQUID;
        if (k.equals("ice") || k.equals("packed_ice") || k.equals("blue_ice") || k.equals("frosted_ice")) return Kind.ICE;
        if (k.endsWith("_leaves")) return Kind.LEAVES;
        if (TREE_PART.contains(k)) return Kind.TREE_PART;
        if (isLog(k)) return Kind.LOG;
        if (PLANT.contains(k) || k.endsWith("_sapling")) return Kind.PLANT;
        if (GROUND.contains(k) || isOre(k) || (k.endsWith("_terracotta") && !k.endsWith("glazed_terracotta"))) return Kind.GROUND;
        return Kind.UNNATURAL;
    }

    private static boolean isLog(String k) {
        if (k.startsWith("stripped_")) return false; // 벗긴 원목은 사람이 만든 것
        return k.endsWith("_log") || k.endsWith("_wood") || k.equals("mushroom_stem") || k.equals("brown_mushroom_block")
                || k.equals("red_mushroom_block") || k.equals("mangrove_roots") || k.equals("muddy_mangrove_roots");
    }

    private static boolean isOre(String k) {
        return k.endsWith("_ore") && !k.contains("nether");
    }

    /** 바이옴 표면 블록 아래에 채울 블록 (잔디·포드졸·균사체 등 → 흙, 모래 → 모래, 그 밖 = 그 블록). */
    public static String subsurface(String surface) {
        String k = key(surface);
        return switch (k) {
            case "grass_block", "podzol", "mycelium", "moss_block", "pale_moss_block", "rooted_dirt", "coarse_dirt", "dirt",
                 "snow_block", "powder_snow", "mud" -> "minecraft:dirt";
            case "sand" -> "minecraft:sand";
            case "red_sand" -> "minecraft:red_sand";
            case "gravel" -> "minecraft:gravel";
            case "", "air" -> "minecraft:dirt";
            default -> "minecraft:" + k;
        };
    }

    /** 다듬은 칸 맨 윗블록: 원래 표면이 바이옴 표면(모래·눈 블록·포드졸 등)이면 그것, 흙이면 잔디. */
    public static String topFor(String surface) {
        String k = key(surface);
        if (k.isEmpty() || k.equals("dirt") || k.equals("rooted_dirt") || k.equals("air") || kind(k) != Kind.GROUND) {
            return "minecraft:grass_block";
        }
        if (k.equals("powder_snow")) return "minecraft:snow_block";
        return "minecraft:" + k;
    }

    /** 블록 문자열에서 네임스페이스·속성을 뺀 소문자 id. */
    public static String key(String block) {
        if (block == null) return "";
        String s = block.trim().toLowerCase(Locale.ROOT);
        int b = s.indexOf('[');
        if (b >= 0) s = s.substring(0, b);
        int c = s.indexOf(':');
        if (c >= 0) s = s.substring(c + 1);
        return s;
    }
}
