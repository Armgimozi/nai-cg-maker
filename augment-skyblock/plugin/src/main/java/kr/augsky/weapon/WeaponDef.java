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
        boolean droppable
) {
    public boolean isBow() {
        return "bow".equals(type);
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
            default -> type;
        };
    }
}
