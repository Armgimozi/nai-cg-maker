package kr.augsky.weapon;

import kr.augsky.skill.HitEffect;
import kr.augsky.util.P;
import org.bukkit.Material;

import java.util.List;

public record WeaponDef(
        String id,
        String name,
        String pool,
        String source,
        String type,
        String element,
        double damage,
        double speed,
        double reach,
        double skillPower,
        Material material,
        String skill,
        String skill2,
        String skill3,
        double passiveChance,
        String passiveDesc,
        List<HitEffect> passive,
        List<String> lore,
        P recipe,
        boolean droppable,
        /* 곡괭이: 채굴 등급(stone iron diamond netherite)과 채굴 속도 */
        String miningTier,
        double miningSpeed,
        /* 최대 내구도와 수리 재료 (안 적으면 Gear 의 기본값을 채워 둔다) */
        int durability,
        String repair,
        /* 곡괭이 패시브: 캐낸 광석 바로 제련, 들고 있는 동안 성급함 단계 */
        boolean autoSmelt,
        int haste
) {
    public boolean isBow() {
        return "bow".equals(type);
    }

    public boolean isPickaxe() {
        return "pickaxe".equals(type);
    }

    /** 화살이 줄지 않는 활: 보스·프리즘 활만. 나머지는 바닐라처럼 화살을 쓰고 무한 마법을 붙일 수 있다. */
    public boolean infiniteArrows() {
        return isBow() && ("boss".equals(pool) || "prism".equals(pool));
    }

    /** 슬롯(1~3)에 붙은 스킬 id. 비어 있으면 null. */
    public String skillOf(int slot) {
        return switch (slot) {
            case 1 -> skill;
            case 2 -> skill2;
            case 3 -> skill3;
            default -> null;
        };
    }

    /** 슬롯을 쓰는 조작 이름 (설명·액션바 공통). 활은 우클릭이 활시위라 조작이 다르고 3번 슬롯이 없다. */
    public String inputLabel(int slot) {
        if (isBow()) {
            return switch (slot) {
                case 1 -> "웅크리기+당겨 쏘기";
                case 2 -> "웅크리기+좌클릭";
                default -> null;
            };
        }
        return switch (slot) {
            case 1 -> "우클릭";
            case 2 -> "웅크리기+우클릭";
            case 3 -> "웅크리기+좌클릭";
            default -> null;
        };
    }

    public boolean hasSkills() {
        return skill != null || skill2 != null || skill3 != null;
    }

    public static String typeName(String type) {
        return switch (type) {
            case "sword" -> "검";
            case "greatsword" -> "대검";
            case "dagger" -> "단검";
            case "katana" -> "카타나";
            case "axe" -> "도끼";
            case "hammer" -> "망치";
            case "spear" -> "창";
            case "scythe" -> "낫";
            case "staff" -> "지팡이";
            case "wand" -> "마법봉";
            case "bow" -> "활";
            case "pickaxe" -> "곡괭이";
            default -> type;
        };
    }
}
