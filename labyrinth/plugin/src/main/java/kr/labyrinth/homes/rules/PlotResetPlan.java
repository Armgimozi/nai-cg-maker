package kr.labyrinth.homes.rules;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 비우기·회수 때 집터를 처음 틀로 되돌리는 계획과 맡긴 짐 규칙 (0.3.7, plan §11 · review R3) — 순수. 소유: 묶음 B.
 * <p>
 * 틀 (구역 계획기 plot_pad 와 같음): 바닥 = 잔디, 바닥 −1..−3 = 흙, −4..−8 = 돌, 바닥 위 = 공기. 높이 창 (바닥 −6 ~ +24) 안만 되돌린다
 * (창 밖은 잠겨 있어 아무도 못 바꿈). 틀과 다른 칸만 손댄다.
 * <p>
 * 맡긴 짐 (R3):
 * <ul>
 *   <li>셜커 상자 = 블록 아이템 하나 (내용 포함) — 내용을 따로 꺼내지 않음 (두 배 막기, R3c)</li>
 *   <li>다른 상자류 = 내용을 꺼내고 비운 뒤 블록 드롭</li>
 *   <li>드롭은 섬세한 손길 도구로 (유리·잎·책장·잔디가 그대로, 겹 반블록 2·초 n, R3d). 드롭이 비면 그 블록 아이템 하나 ({@link #fallbackCount})</li>
 *   <li>두 칸 블록의 둘째 칸 (문·큰 꽃 윗칸 · 침대 발치 · 피스톤 머리) 은 아무것도 주지 않음 (한 번만)</li>
 *   <li>엔티티: 액자 (+ 든 것) · 그림 · 갑옷 거치대 (+ 입힌 것) · 보트·수레 (+ 상자 내용) · 떨어진 아이템</li>
 *   <li>짐을 진 동물 (말·당나귀·라마·낙타 안장·갑옷·상자 내용 · 돼지·스트라이더 안장 · 늑대 갑옷 …): 동물은 그대로 두고 짐만 (0.3.7 fix, exploit L6)</li>
 *   <li>장식 항아리: 도구 없이 깬 드롭 (항아리 그대로 — 섬세한 손길 곡괭이로는 조각이 나옴, exploit L5)</li>
 * </ul>
 */
public final class PlotResetPlan {

    private PlotResetPlan() {}

    public static final int DIRT_LAYERS = 3;

    /** 그 높이의 틀 블록 id. */
    public static String template(int y, int floorY) {
        if (y > floorY) return "air";
        if (y == floorY) return "grass_block";
        if (y >= floorY - DIRT_LAYERS) return "dirt";
        return "stone";
    }

    /** 그 칸이 이미 틀인가 (공기 종류는 모두 공기로 봄). */
    public static boolean isTemplate(String block, int y, int floorY) {
        String k = PlotRules.key(block);
        String t = template(y, floorY);
        if (t.equals("air")) return k.equals("air") || k.equals("cave_air") || k.equals("void_air");
        return k.equals(t);
    }

    /** 그 칸에서 무엇을 맡긴 짐으로. */
    public enum Take {
        /** 공기·물·불·차원문 — 아무것도 없음. */
        NOTHING,
        /** 두 칸 블록의 둘째 칸 — 아무것도 없음 (첫 칸이 줌). */
        SECOND_HALF,
        /** 블록 드롭 (섬세한 손길). */
        DROPS,
        /** 상자류: 내용 꺼내 비움 → 블록 드롭. */
        CONTENTS_AND_DROPS,
        /** 셜커 상자: 내용이 든 블록 아이템 하나. */
        SHULKER_ITEM
    }

    private static final Set<String> NOTHING = Set.of("air", "cave_air", "void_air", "water", "lava", "bubble_column", "fire", "soul_fire",
            "nether_portal", "end_portal", "end_gateway", "moving_piston", "light", "structure_void", "barrier");

    /**
     * @param props     블록 속성 (half · part · type · candles …, 없으면 빈 맵)
     * @param container BlockState 가 InventoryHolder 인가
     */
    public static Take take(String block, Map<String, String> props, boolean container) {
        String k = PlotRules.key(block);
        Map<String, String> p = props == null ? Map.of() : props;
        if (NOTHING.contains(k)) return Take.NOTHING;
        if (k.equals("piston_head")) return Take.SECOND_HALF;
        if ("upper".equals(p.get("half")) && !k.endsWith("_stairs") && !k.endsWith("_trapdoor")) return Take.SECOND_HALF; // 문·큰 꽃·키 큰 풀
        if (k.endsWith("_bed") && "foot".equals(p.get("part"))) return Take.SECOND_HALF;
        if (k.equals("shulker_box") || k.endsWith("_shulker_box")) return Take.SHULKER_ITEM;
        if (container) return Take.CONTENTS_AND_DROPS;
        return Take.DROPS;
    }

    /** 드롭이 비었을 때 그 블록 아이템 몇 개 (겹 반블록 2 · 초 n · 바다 피클 n · 거북알 n · 눈 겹 n · 그 밖 1, 줄 수 없는 것 0). */
    public static int fallbackCount(String block, Map<String, String> props) {
        String k = PlotRules.key(block);
        Map<String, String> p = props == null ? Map.of() : props;
        if (NO_ITEM.contains(k)) return 0;
        if (k.endsWith("_slab") && "double".equals(p.get("type"))) return 2;
        if (k.equals("candle") || k.endsWith("_candle")) return num(p.get("candles"), 1);
        if (k.equals("sea_pickle")) return num(p.get("pickles"), 1);
        if (k.equals("turtle_egg")) return num(p.get("eggs"), 1);
        if (k.equals("snow")) return num(p.get("layers"), 1);
        if (k.equals("pink_petals") || k.equals("wildflowers") || k.equals("leaf_litter")) return num(p.get("flower_amount"), num(p.get("segment_amount"), 1));
        return 1;
    }

    /** 아이템이 없는 블록 (드롭이 없어도 주지 않음). */
    private static final Set<String> NO_ITEM = Set.of("spawner", "trial_spawner", "vault", "budding_amethyst", "reinforced_deepslate",
            "bedrock", "frosted_ice", "farmland", "dirt_path", "infested_stone", "command_block", "chain_command_block",
            "repeating_command_block", "structure_block", "jigsaw", "end_portal_frame", "piston_head", "moving_piston");

    private static int num(String s, int def) {
        if (s == null) return def;
        try {
            return Math.max(1, Integer.parseInt(s.trim()));
        } catch (NumberFormatException e) {
            return def;
        }
    }

    /** "minecraft:oak_slab[type=double,waterlogged=false]" → {type=double, waterlogged=false}. */
    public static Map<String, String> props(String blockData) {
        Map<String, String> out = new HashMap<>();
        if (blockData == null) return out;
        int a = blockData.indexOf('['), b = blockData.lastIndexOf(']');
        if (a < 0 || b <= a) return out;
        for (String kv : blockData.substring(a + 1, b).split(",")) {
            int e = kv.indexOf('=');
            if (e > 0) out.put(kv.substring(0, e).trim().toLowerCase(Locale.ROOT), kv.substring(e + 1).trim().toLowerCase(Locale.ROOT));
        }
        return out;
    }

    /** 맡긴 짐으로 가져갈 엔티티 종류. */
    public enum EntityTake { ITEM_FRAME, PAINTING, ARMOR_STAND, VEHICLE, ITEM, ANIMAL_GEAR, NONE }

    /** 안장·갑옷·상자를 지는 동물 (동물은 그대로, 짐만 맡긴 짐으로). */
    private static final Set<String> GEAR_ANIMALS = Set.of("horse", "donkey", "mule", "llama", "trader_llama", "camel", "camel_husk",
            "skeleton_horse", "zombie_horse", "pig", "strider", "wolf", "happy_ghast", "nautilus", "zombie_nautilus");

    /** EntityType 이름 → 가져갈 것 (동물·몹·플레이어 = NONE — 그대로 둠). */
    public static EntityTake entity(String type) {
        String t = type == null ? "" : type.trim().toLowerCase(Locale.ROOT);
        return switch (t) {
            case "item_frame", "glow_item_frame" -> EntityTake.ITEM_FRAME;
            case "painting" -> EntityTake.PAINTING;
            case "armor_stand" -> EntityTake.ARMOR_STAND;
            case "item" -> EntityTake.ITEM;
            case "horse", "donkey", "mule", "llama", "trader_llama", "camel", "camel_husk", "skeleton_horse", "zombie_horse", "pig", "strider", "wolf",
                 "happy_ghast", "nautilus", "zombie_nautilus" -> EntityTake.ANIMAL_GEAR;
            case "minecart", "chest_minecart", "hopper_minecart", "furnace_minecart", "tnt_minecart" -> EntityTake.VEHICLE;
            default -> t.endsWith("_boat") || t.endsWith("_raft") || t.endsWith("_chest_boat") || t.endsWith("_chest_raft") || t.equals("boat")
                    || t.equals("chest_boat") ? EntityTake.VEHICLE : EntityTake.NONE;
        };
    }

    /** 그 블록은 도구 없이 깬 드롭을 쓰는가 (장식 항아리 — 곡괭이로 깨면 조각으로 부서짐). */
    public static boolean dropsWithoutTool(String block) { return PlotRules.key(block).equals("decorated_pot"); }

    /** 짐을 지는 동물인가 (시험용). */
    public static boolean gearAnimal(String type) { return GEAR_ANIMALS.contains(type == null ? "" : type.trim().toLowerCase(Locale.ROOT)); }

    /** 높이 창의 칸 수 (가로 × 세로 × 높이). */
    public static long volume(int x0, int z0, int x1, int z1, int yMin, int yMax) {
        return (long) (Math.abs(x1 - x0) + 1) * (Math.abs(z1 - z0) + 1) * (Math.abs(yMax - yMin) + 1);
    }
}
