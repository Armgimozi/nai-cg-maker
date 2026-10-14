package kr.labyrinth.items;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.content.WeaponTypes;
import kr.labyrinth.core.Text;

/**
 * 아이템 툴팁(lore) 생성 — MiniMessage 문자열 목록. Bukkit 무관(단위 테스트 가능).
 * 구성: 희귀도·분류 / 요구 레벨·추천 직업 / 스탯(굴림값 + 범위) / 굴림 품질 / 무기 스킬 / 세트 효과 / 아우라 / 사용 효과 / 설명 / 획득처.
 */
public final class ItemTooltip {

    public static final Map<String, String> STAT_NAMES = new LinkedHashMap<>();
    private static final Map<String, String> WEAPON_TYPES = Map.of("sword_shield", "한손검", "greatsword", "대검",
            "bow", "활", "staff", "지팡이", "scepter", "홀", "dagger", "단검");
    private static final Map<String, String> SLOTS = Map.of("head", "투구", "chest", "흉갑", "legs", "각반",
            "feet", "장화", "offhand", "방패");
    private static final Map<String, String> SOURCES = Map.of("drop", "몬스터", "elite", "엘리트", "boss", "보스",
            "chest", "보물 상자", "craft", "제작", "reward", "업적 보상", "shop", "상인");
    private static final Map<String, String> BUFFS = Map.of("damage", "주는 피해", "damage_reduction", "받는 피해 감소",
            "attack_speed", "공격 속도", "move_speed", "이동 속도", "crit_chance", "치명타 확률", "crit_damage", "치명타 피해",
            "lifesteal", "흡혈", "evasion", "회피", "cooldown_reduction", "재사용 대기 감소", "skill_damage", "스킬 피해");

    static {
        STAT_NAMES.put("damage", "피해");
        STAT_NAMES.put("STR", "힘");
        STAT_NAMES.put("DEX", "민첩");
        STAT_NAMES.put("INT", "지능");
        STAT_NAMES.put("VIT", "체력");
        STAT_NAMES.put("WIS", "정신");
        STAT_NAMES.put("LUK", "행운");
        STAT_NAMES.put("hp", "최대 HP");
        STAT_NAMES.put("mp", "최대 MP");
        STAT_NAMES.put("defense", "방어");
        STAT_NAMES.put("crit_chance", "치명타 확률");
        STAT_NAMES.put("crit_damage", "치명타 피해");
        STAT_NAMES.put("attack_speed", "공격 속도");
        STAT_NAMES.put("move_speed", "이동 속도");
        STAT_NAMES.put("cooldown_reduction", "재사용 대기 감소");
        STAT_NAMES.put("skill_damage", "스킬 피해");
        STAT_NAMES.put("mana_regen", "초당 MP 재생");
        STAT_NAMES.put("hp_regen", "초당 HP 재생");
        STAT_NAMES.put("heal_power", "치유력");
        STAT_NAMES.put("lifesteal", "흡혈");
        STAT_NAMES.put("damage_reduction", "받는 피해 감소");
        STAT_NAMES.put("evasion", "회피");
        STAT_NAMES.put("block_chance", "막기 확률");
        STAT_NAMES.put("gold_bonus", "골드 획득");
        STAT_NAMES.put("xp_bonus", "경험치 획득");
        STAT_NAMES.put("craft_discount", "제작 비용 할인");
    }

    private ItemTooltip() {}

    public static String statName(String key) { return STAT_NAMES.getOrDefault(key, key); }

    /** 스탯 값 표시 ("+12", "+4.5%", "+0.8"). */
    public static String formatStat(String key, double v) {
        String sign = v >= 0 ? "+" : "-";
        double a = Math.abs(v);
        if (ItemRolls.PERCENT_KEYS.contains(key)) return sign + Text.pct(a);
        if (ItemRolls.INT_KEYS.contains(key)) return sign + Math.round(a);
        return sign + trim(a);
    }

    static String trim(double v) {
        if (Math.abs(v - Math.rint(v)) < 1e-9) return String.valueOf((long) Math.rint(v));
        String s = String.format(java.util.Locale.ROOT, "%.2f", v);
        return s.replaceAll("0+$", "").replaceAll("\\.$", "");
    }

    private static String rangeText(String key, Range r) {
        if (ItemRolls.PERCENT_KEYS.contains(key)) return Text.pct(r.min()) + "~" + Text.pct(r.max());
        if (ItemRolls.INT_KEYS.contains(key)) return Math.round(r.min()) + "~" + Math.round(r.max());
        return trim(r.min()) + "~" + trim(r.max());
    }

    /** 분류 이름 (대검, 흉갑, 장신구, 재료 …). */
    public static String category(ItemDef def) {
        return switch (def.type()) {
            case WEAPON -> WEAPON_TYPES.getOrDefault(def.weaponType(), "무기");
            case ARMOR -> SLOTS.getOrDefault(def.armorSlot(), "방어구");
            case ACCESSORY -> "장신구";
            case MATERIAL -> "재료";
            case CONSUMABLE -> "소모품";
            case KEY -> "열쇠";
        };
    }

    public static String inputName(String input) { return kr.labyrinth.core.InputKeys.label(input); }

    /** 무기별 입력 이름 — 활의 SNEAK_RIGHT 는 "웅크리고 당겨 쏘기" (GDD §17.5). */
    public static String inputName(ItemDef def, String input) {
        if (def != null && "bow".equals(def.weaponType()) && "SNEAK_RIGHT".equals(input)) return kr.labyrinth.core.InputKeys.SNEAK + " 누른 채 당겨 쏘기";
        return inputName(input);
    }

    /**
     * 추천 직업 이름 (착용 제한 아님). 무기 = classes.yml weapon_types 에 그 종류가 있는 직업(재사용 대기 보너스 기준),
     * 그 밖의 장비 = items.yml {@code classes}.
     */
    static List<String> suitedClassNames(Content content, ItemDef def) {
        List<String> names = new ArrayList<>();
        if (def.isWeapon()) {
            for (ClassDef cd : content.classes().values()) if (cd.recommendsWeapon(def.weaponType())) names.add(cd.name());
            return names;
        }
        for (String id : def.classes()) {
            ClassDef cd = content.classDef(id);
            names.add(cd == null ? id : cd.name());
        }
        return names;
    }

    /**
     * @param rolls   굴린 스탯 (null 이면 범위만 보여 주는 미리보기)
     */
    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls) {
        List<String> out = new ArrayList<>();
        Rarity r = def.rarity();
        String c = "<" + r.color() + ">";
        out.add(c + r.displayName() + " " + category(def) + "</" + r.color() + ">"
                + (def.floor() > 0 && def.isGear() ? " <dark_gray>· 지하 " + def.floor() + "층" : ""));

        if (def.isGear()) {
            StringBuilder req = new StringBuilder("<gray>요구 레벨 <white>" + def.levelReq() + "</white>");
            List<String> names = suitedClassNames(content, def);
            if (!names.isEmpty()) {
                req.append(" <dark_gray>·</dark_gray> 추천 직업 <white>").append(String.join(", ", names)).append("</white>");
            }
            out.add(req.toString());
            if (def.isWeapon() && !names.isEmpty()) {
                out.add("<dark_gray>모든 직업 사용 가능 · 추천 직업이 들면 직업 스킬 재사용 대기 −"
                        + Text.pct(WeaponTypes.RECOMMENDED_COOLDOWN_CUT));
            }
        } else if (def.levelReq() > 1) {
            out.add("<gray>사용 레벨 <white>" + def.levelReq());
        }

        // 스탯
        if (!def.stats().isEmpty()) {
            out.add("");
            for (Map.Entry<String, Range> e : def.stats().entrySet()) {
                String key = e.getKey();
                Range range = e.getValue();
                if (range == null) continue;
                String rangeTxt = range.max() - range.min() > 1e-9 ? " <dark_gray>(" + rangeText(key, range) + ")" : "";
                if (rolls == null) {
                    out.add(statLine(key, rangeText(key, range), true) + "");
                } else {
                    double v = rolls.getOrDefault(key, ItemRolls.round(key, range.lerp(0.5)));
                    out.add(statLine(key, formatStat(key, v), false) + rangeTxt);
                }
            }
            if (rolls != null) {
                double q = ItemRolls.quality(def, rolls);
                if (q >= 0) {
                    String qc = q >= 0.9 ? "#ffd27a" : q >= 0.6 ? "#9be89b" : q >= 0.3 ? "#cfcfcf" : "#9a9a9a";
                    out.add("<dark_gray>굴림 품질 <" + qc + ">" + Math.round(q * 100) + "%");
                }
            }
        }

        // 무기 스킬
        if (!def.weaponSkills().isEmpty()) {
            out.add("");
            for (ItemDef.WeaponSkillDef s : def.weaponSkills()) {
                StringBuilder head = new StringBuilder("<#ffd27a>◆ " + inputName(def, s.input()) + "</#ffd27a> <white>"
                        + Text.escape(s.name()) + "</white> <dark_gray>(");
                head.append("재사용 ").append(trim(s.cooldown())).append("초");
                if (s.mana() > 0) head.append(" · MP ").append(trim(s.mana()));
                head.append(")");
                out.add(head.toString());
                if (s.description() != null && !s.description().isBlank()) {
                    for (String l : wrap(s.description(), 30)) out.add("  <gray>" + Text.escape(l));
                }
            }
        }

        // 세트
        ItemSetDef set = content.setOf(def);
        if (set != null) {
            out.add("");
            out.add("<#7fd8ff>세트: " + Text.escape(set.name()) + " <dark_gray>(" + set.pieces().size() + "부위)");
            set.bonuses().forEach((count, bonus) -> {
                List<String> parts = new ArrayList<>();
                bonus.forEach((k, v) -> parts.add(statName(k) + " " + formatStat(k, v)));
                out.add("  <gray>(" + count + ") " + String.join(", ", parts));
            });
        }

        // 아우라
        if (def.aura() != null && content.auras().containsKey(def.aura())) {
            out.add("");
            boolean mythic = "mythic".equals(content.auras().get(def.aura()).tier());
            out.add(c + "✦ " + (mythic ? "2겹 아우라" : "아우라") + "</" + r.color() + "> <gray>— 손에 들면 빛난다");
        }

        // 사용 효과
        if (def.use() != null && !def.use().isEmpty()) {
            out.add("");
            out.add("<#9be89b>사용: " + useText(def.use()));
            double cd = def.use().dbl("cooldown", 0);
            if (cd > 0) out.add("<dark_gray>재사용 대기 " + trim(cd) + "초");
        }

        // 설명
        if (def.lore() != null && !def.lore().isBlank()) {
            out.add("");
            for (String l : wrap(def.lore(), 30)) out.add("<#8a8a9a><i>" + Text.escape(l));
        }

        if (!def.sources().isEmpty()) {
            List<String> names = new ArrayList<>();
            for (String s : def.sources()) names.add(SOURCES.getOrDefault(s, s));
            out.add("<dark_gray>획득처: " + String.join(" · ", names));
        }
        return out;
    }

    private static String statLine(String key, String value, boolean preview) {
        String color = switch (key) {
            case "damage" -> "#ff9a6b";
            case "STR", "DEX", "INT", "VIT", "WIS", "LUK" -> "#ffffff";
            default -> "#c8d6ff";
        };
        String icon = "damage".equals(key) ? "⚔ " : "";
        String v = preview ? value : value;
        return "<" + color + ">" + icon + statName(key) + " " + v;
    }

    /** 소모품 use 설명 (GDD §11.9). */
    public static String useText(Params u) {
        String action = u.str("action", "");
        return switch (action) {
            case "heal" -> "최대 HP의 " + Text.pct(u.dbl("amount", 0)) + " 회복";
            case "mana" -> "최대 MP의 " + Text.pct(u.dbl("amount", 0)) + " 회복";
            case "restore" -> "HP·MP를 각각 " + Text.pct(u.dbl("amount", 0)) + " 회복";
            case "cleanse" -> "해로운 효과를 모두 제거";
            case "buff" -> {
                List<String> parts = new ArrayList<>();
                Params b = u.sub("buff");
                for (String k : b.keys()) parts.add(BUFFS.getOrDefault(k, statName(k)) + " " + formatStat("crit_chance", b.dbl(k, 0)));
                yield trim(u.dbl("duration", 0)) + "초 동안 " + String.join(", ", parts);
            }
            case "return" -> "미궁 입구로 귀환 (시전 " + trim(u.dbl("cast_time_safe", 1)) + "초, 전투 중 "
                    + trim(u.dbl("cast_time", 5)) + "초)";
            case "stat_reset" -> "투자한 스탯 포인트를 모두 돌려받음";
            case "revive" -> "쓰러지는 순간 자동으로 HP " + Text.pct(u.dbl("amount", 0.3)) + "로 부활";
            default -> action;
        };
    }

    /** 한국어 기준 단순 줄바꿈 (공백 우선, 없으면 글자 수로 자름). */
    public static List<String> wrap(String text, int width) {
        List<String> out = new ArrayList<>();
        if (text == null) return out;
        String rest = text.trim();
        while (rest.length() > width) {
            int cut = rest.lastIndexOf(' ', width);
            if (cut <= width / 2) cut = width;
            out.add(rest.substring(0, cut).trim());
            rest = rest.substring(cut).trim();
        }
        if (!rest.isEmpty()) out.add(rest);
        return out;
    }
}
