package kr.labyrinth.items;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.LootTable;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Range;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.Text;
import kr.labyrinth.stats.Stat;

/**
 * 아이템 툴팁(lore) 생성 — MiniMessage 문자열 목록. Bukkit 무관(단위 테스트 가능).
 * 구성: 희귀도·분류·아우라 / 요구 능력치(무기·방어구, 없으면 줄 없음 — 소모품은 사용 레벨) / 스탯(첫 스탯은 범위와 한 줄, 나머지 두 개씩 — 굴림 품질은 표시하지 않음) / 강화 / 무기 스킬 /
 * 세트 효과·사용 효과 / 설명 / 획득처("보스 테오라(9층) · 대장간"). 화면에 다 들어가도록 {@link #MAX_LINES} 를 넘으면 덜 중요한 줄부터 뺀다.
 */
public final class ItemTooltip {

    public static final Map<String, String> STAT_NAMES = new LinkedHashMap<>();
    private static final Map<String, String> WEAPON_TYPES = Map.of("sword_shield", "한손검", "greatsword", "대검",
            "bow", "활", "staff", "지팡이", "scepter", "홀", "dagger", "단검");
    private static final Map<String, String> SLOTS = Map.of("head", "투구", "chest", "흉갑", "legs", "각반",
            "feet", "장화", "offhand", "방패");
    /** items.yml sources 값 → 획득처 이름 (drop+chest 는 "몬스터·상자" 한 집, 보스·정예는 이름을 붙인다 — {@link #sourceLine}). */
    private static final Map<String, String> SOURCES = Map.of("drop", "몬스터", "elite", "정예", "boss", "보스",
            "chest", "보물 상자", "craft", "대장간", "reward", "칭호 보상", "shop", "상인", "starter", "시작 지급");
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

    public static String trim(double v) {
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
     * 이름 줄을 뺀 툴팁 최대 줄 수. GUI 크기를 크게 쓴 1080p 화면에 툴팁이 약 23줄 들어가므로 이름 포함 21줄로 맞춘다.
     * 넘치면 덜 중요한 것부터 뺀다: 설명(이야기) → 획득처 한 줄 → 빈 줄 → 무기 스킬 설명을 첫 줄만
     * (보스 고유 장비는 어느 보스 것인지가 보여야 하므로 빈 줄을 먼저 빼고 획득처를 남긴다).
     */
    public static final int MAX_LINES = 20;
    /** 획득처 한 줄 요약의 앞부분 (도감은 자세한 목록을 따로 붙이므로 이 줄 없이 그린다 — withSource = false). */
    public static final String SOURCE_PREFIX = "<dark_gray>획득처: ";
    /** 설명·스킬 설명 줄바꿈 글자 수 (툴팁 폭이 화면 절반을 넘지 않게). */
    static final int WRAP = 34;

    /**
     * @param rolls   굴린 스탯 (null 이면 범위만 보여 주는 미리보기)
     */
    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls) {
        return lines(content, def, rolls, Map.of(), List.of(), 0);
    }

    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls,
                                     Map<String, Double> enhanceBonus, List<String> enhanceLines) {
        return lines(content, def, rolls, enhanceBonus, enhanceLines, 0);
    }

    /**
     * @param rolls        기본 굴림값 (null 이면 범위만 보여 주는 미리보기)
     * @param enhanceBonus 강화로 늘어난 몫 (키 → 증가량) — 값에 더해 보여 주고 금색 "(+n)" 을 붙인다
     * @param enhanceLines 강화 단계·다음 확률·비용 줄 (스탯 바로 아래, 비어 있으면 생략)
     * @param reserve      호출자가 아래에 덧붙일 줄 수 (도감 획득처·대장간 재료) — 그만큼 {@link #MAX_LINES} 에서 비운다
     */
    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls,
                                     Map<String, Double> enhanceBonus, List<String> enhanceLines, int reserve) {
        return lines(content, def, rolls, enhanceBonus, enhanceLines, reserve, true);
    }

    /** @param withSource 획득처 한 줄을 넣을지 (도감은 자세한 획득처 목록을 따로 붙이므로 false) */
    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls,
                                     Map<String, Double> enhanceBonus, List<String> enhanceLines, int reserve,
                                     boolean withSource) {
        return lines(content, def, rolls, enhanceBonus, enhanceLines, reserve, withSource, null);
    }

    /**
     * @param viewer 보는 사람의 요구치 판정 능력치 ({@code StatService.requirementStats}) — 알면 요구 능력치 줄을 맞춤 초록 /
     *               모자람 빨강 "(현재 22)" 로, null(아이템에 박히는 설명)이면 "요구 힘 30" 그대로
     */
    public static List<String> lines(Content content, ItemDef def, Map<String, Double> rolls,
                                     Map<String, Double> enhanceBonus, List<String> enhanceLines, int reserve,
                                     boolean withSource, Map<Stat, Integer> viewer) {
        Rarity r = def.rarity();
        String c = "<" + r.color() + ">";

        // 머리: 희귀도·분류·층·아우라 / 요구 능력치
        List<String> head = new ArrayList<>();
        StringBuilder top = new StringBuilder(c + r.displayName() + " " + category(def) + "</" + r.color() + ">");
        if (def.floor() > 0 && def.isGear()) top.append(" <dark_gray>· 지하 ").append(def.floor()).append("층</dark_gray>");
        if (def.aura() != null && content.auras().containsKey(def.aura())) {
            boolean mythic = "mythic".equals(content.auras().get(def.aura()).tier());
            top.append(" <dark_gray>·</dark_gray> ").append(c).append("✦ ").append(mythic ? "2겹 아우라" : "아우라").append("</").append(r.color()).append(">");
        }
        head.add(top.toString());
        if (def.isGear()) {
            // 직업 표시는 하지 않는다 (어느 직업이든 모든 장비 — 직업별 추천 무기는 직업 메뉴에서만).
            // 레벨 제한은 없다 — level_req 는 숨은 내부 레벨. 요구 능력치가 없으면(장신구·초반 장비) 줄 자체가 없다.
            String req = requirementLine(def, viewer);
            if (req != null) head.add(req);
        } else if (def.levelReq() > 1) {
            head.add("<gray>사용 레벨 <white>" + def.levelReq());
        }

        // 스탯: 첫 스탯(무기 피해·방어구 방어 등)은 범위와 한 줄, 나머지는 두 개씩 한 줄 (굴림 품질 %는 보여 주지 않는다)
        List<String> stats = new ArrayList<>();
        List<String> cells = new ArrayList<>();
        boolean first = true;
        for (Map.Entry<String, Range> e : def.stats().entrySet()) {
            String key = e.getKey();
            Range range = e.getValue();
            if (range == null) continue;
            String cell;
            if (rolls == null) {
                cell = statLine(key, rangeText(key, range), true);
            } else {
                double v = rolls.getOrDefault(key, ItemRolls.round(key, range.lerp(0.5)));
                Double plus = enhanceBonus.get(key);
                cell = plus != null && plus != 0
                        ? statLine(key, formatStat(key, ItemRolls.round(key, v + plus)), false) + " <#ffd36b>(" + formatStat(key, plus) + ")</#ffd36b>"
                        : statLine(key, formatStat(key, v), false);
            }
            if (first) {
                first = false;
                StringBuilder line = new StringBuilder(cell);
                if (rolls != null && range.max() - range.min() > 1e-9) line.append(" <dark_gray>(").append(rangeText(key, range)).append(")");
                stats.add(line.toString());
            } else {
                cells.add(cell);
            }
        }
        for (int i = 0; i < cells.size(); i += 2) {
            stats.add(i + 1 < cells.size() ? cells.get(i) + " <dark_gray>·</dark_gray> " + cells.get(i + 1) : cells.get(i));
        }

        // 무기 스킬 (머리 줄 + 설명)
        List<String> skillHeads = new ArrayList<>();
        List<List<String>> skillDescs = new ArrayList<>();
        for (ItemDef.WeaponSkillDef s : def.weaponSkills()) {
            StringBuilder h = new StringBuilder("<#ffd27a>◆ " + inputName(def, s.input()) + "</#ffd27a> <white>"
                    + Text.escape(s.name()) + "</white> <dark_gray>(");
            h.append("재사용 ").append(trim(s.cooldown())).append("초");
            if (s.mana() > 0) h.append(" · MP ").append(trim(s.mana()));
            h.append(")");
            skillHeads.add(h.toString());
            List<String> d = new ArrayList<>();
            if (s.description() != null && !s.description().isBlank()) {
                for (String l : wrap(s.description(), WRAP)) d.add("  <gray>" + Text.escape(l));
            }
            skillDescs.add(d);
        }

        // 세트·사용 효과
        List<String> extra = new ArrayList<>();
        ItemSetDef set = content.setOf(def);
        if (set != null) {
            extra.add("<#7fd8ff>세트: " + Text.escape(set.name()) + " <dark_gray>(" + set.pieces().size() + "부위)");
            set.bonuses().forEach((count, bonus) -> {
                List<String> parts = new ArrayList<>();
                bonus.forEach((k, v) -> parts.add(statName(k) + " " + formatStat(k, v)));
                extra.add("  <gray>(" + count + ") " + String.join(", ", parts));
            });
        }
        if (def.use() != null && !def.use().isEmpty()) {
            double cd = def.use().dbl("cooldown", 0);
            extra.add("<#9be89b>사용: " + useText(def.use()) + (cd > 0 ? " <dark_gray>(재사용 " + trim(cd) + "초)" : ""));
        }

        // 설명(이야기)·획득처 — 자리가 남을 때만
        List<String> flavor = new ArrayList<>();
        if (def.lore() != null && !def.lore().isBlank()) {
            for (String l : wrap(def.lore(), WRAP)) flavor.add("<#8a8a9a><i>" + Text.escape(l));
        }
        String source = withSource ? sourceLine(content, def) : null;

        int budget = Math.max(6, MAX_LINES - Math.max(0, reserve));
        List<String> out = null;
        // 0: 전부 · 1: 설명 뺌 · 2: 획득처도 뺌 · 3: 빈 줄 뺌 · 4: 스킬 설명 첫 줄만 (보스 고유 장비는 2·3 순서가 반대)
        boolean bossGear = def.isGear() && def.sources().contains("boss");
        for (int tier = 0; tier <= 4; tier++) {
            boolean keepSource = bossGear ? tier <= 2 : tier <= 1;
            boolean blanks = bossGear ? tier <= 1 : tier <= 2;
            out = assemble(head, stats, enhanceLines, skillHeads, skillDescs, extra,
                    tier == 0 ? flavor : List.of(), keepSource ? source : null, blanks, tier >= 4);
            if (out.size() <= budget) break;
        }
        return out;
    }

    /** 요구 능력치 한 줄 ("요구 힘 30", 보는 사람을 알면 초록/빨강) — 무기·방어구·방패만, 요구 없음 = null. */
    public static String requirementLine(ItemDef def, Map<Stat, Integer> viewer) {
        return def.requirement().tooltipLine(viewer);
    }

    // ── 획득처 한 줄 ──────────────────────────────────────────────────────

    /** 획득처 줄의 최대 폭 (TooltipFitTest 와 같은 근사 — 한글 9 · 영문·숫자 6 · 공백 4 · 기호 8 px). */
    static final int SOURCE_MAX_PX = 330;

    /**
     * "획득처: 보스 테오라(9층) · 대장간", "획득처: 지하 3층 몬스터·상자", "획득처: 시작 지급" (sources 가 비면 null).
     * 보스·정예는 그 아이템을 주는 보스·정예가 하나뿐일 때만 이름을 붙이고, 줄이 넘치면 이름을 뺀다.
     */
    public static String sourceLine(Content content, ItemDef def) {
        if (def.sources().isEmpty()) return null;
        String full = sourceLine(content, def, true);
        return width(full) <= SOURCE_MAX_PX ? full : sourceLine(content, def, false);
    }

    private static String sourceLine(Content content, ItemDef def, boolean named) {
        Set<String> parts = new LinkedHashSet<>();
        boolean drop = def.sources().contains("drop"), chest = def.sources().contains("chest");
        SourceNames names = named ? names(content) : null;
        for (String s : def.sources()) {
            switch (s) {
                case "drop", "chest" -> {
                    if (drop && chest) parts.add(def.isGear() && def.floor() > 0 ? "지하 " + def.floor() + "층 몬스터·상자" : "몬스터·상자");
                    else parts.add(SOURCES.get(s));
                }
                case "boss" -> parts.add(names == null ? SOURCES.get(s) : names.boss().getOrDefault(def.id(), SOURCES.get(s)));
                case "elite" -> parts.add(names == null ? SOURCES.get(s) : names.elite().getOrDefault(def.id(), SOURCES.get(s)));
                default -> parts.add(SOURCES.getOrDefault(s, s));
            }
        }
        return SOURCE_PREFIX + String.join(" · ", parts);
    }

    /** 아이템 id → "보스 테오라(9층)" / "정예 대시계 집행관(9층)" — 그 아이템을 주는 보스·정예가 하나뿐일 때만. */
    private record SourceNames(Content content, Map<String, String> boss, Map<String, String> elite) {}

    private static volatile SourceNames sourceNames;

    /** 콘텐츠를 다시 읽을 때(= 새 Content 스냅샷)만 루팅 테이블을 펼쳐 다시 계산한다. */
    private static SourceNames names(Content c) {
        SourceNames n = sourceNames;
        if (n != null && n.content() == c) return n;
        Map<String, Set<String>> boss = new HashMap<>();
        Map<String, Set<String>> elite = new HashMap<>();
        for (BossDef b : c.bosses().values()) {
            String label = "보스 " + bossShortName(b) + "(" + b.floor() + "층)";
            for (String id : items(c, b.drops())) boss.computeIfAbsent(id, k -> new LinkedHashSet<>()).add(label);
        }
        for (MobDef m : c.mobs().values()) {
            if (!m.isElite() || m.drops() == null) continue;
            String label = "정예 " + Text.strip(m.name()).trim() + "(" + m.floor() + "층)";
            for (String id : items(c, m.drops())) elite.computeIfAbsent(id, k -> new LinkedHashSet<>()).add(label);
        }
        n = new SourceNames(c, single(boss), single(elite));
        sourceNames = n;
        return n;
    }

    private static Map<String, String> single(Map<String, Set<String>> labels) {
        Map<String, String> out = new HashMap<>();
        labels.forEach((id, l) -> { if (l.size() == 1) out.put(id, l.iterator().next()); });
        return out;
    }

    /** 보스 짧은 이름 ("시계탑의 간수 테오라" → "테오라") — 몇 층인지와 함께면 충분하다. */
    public static String bossShortName(BossDef b) {
        String full = Text.strip(b.name()).trim();
        return full.contains(" ") ? full.substring(full.lastIndexOf(' ') + 1) : full;
    }

    /** 테이블이 줄 수 있는 아이템 id (하위 테이블·one_of·guaranteed 포함, rarity_pool 은 후보 풀). */
    private static Set<String> items(Content c, String tableId) {
        Set<String> out = new HashSet<>();
        collect(c, c.lootTable(tableId), out, new HashSet<>());
        return out;
    }

    private static void collect(Content c, LootTable t, Set<String> out, Set<String> visiting) {
        if (t == null || !visiting.add(t.id())) return;
        List<LootTable.Entry> all = new ArrayList<>(t.entries());
        all.addAll(t.guaranteed());
        for (LootTable.Entry e : all) {
            switch (e.kind()) {
                case ITEM -> { if (e.item() != null) out.add(e.item()); }
                case ONE_OF -> { if (e.oneOf() != null) out.addAll(e.oneOf()); }
                case TABLE -> collect(c, c.lootTable(e.table()), out, visiting);
                case RARITY_POOL -> {
                    if (e.rarityPool() != null) for (ItemDef d : c.poolCandidates(e.floor(), e.rarityPool())) out.add(d.id());
                }
            }
        }
        visiting.remove(t.id());
    }

    /** 대략적인 픽셀 폭 (MiniMessage 태그 제외). */
    static int width(String mm) {
        int w = 0;
        for (char ch : mm.replaceAll("<[^>]+>", "").toCharArray()) {
            if (ch == ' ') w += 4;
            else if (ch >= 0xAC00 && ch <= 0xD7A3) w += 9;
            else if (ch < 128) w += 6;
            else w += 8;
        }
        return w;
    }

    private static List<String> assemble(List<String> head, List<String> stats, List<String> enhance, List<String> skillHeads,
                                         List<List<String>> skillDescs, List<String> extra, List<String> flavor, String source,
                                         boolean blanks, boolean shortDescs) {
        List<String> out = new ArrayList<>(head);
        if (!stats.isEmpty() || !enhance.isEmpty()) {
            if (blanks) out.add("");
            out.addAll(stats);
            out.addAll(enhance);
        }
        if (!skillHeads.isEmpty()) {
            if (blanks) out.add("");
            for (int i = 0; i < skillHeads.size(); i++) {
                out.add(skillHeads.get(i));
                List<String> d = skillDescs.get(i);
                if (d.isEmpty()) continue;
                if (shortDescs && d.size() > 1) out.add(d.get(0) + "…");
                else out.addAll(d);
            }
        }
        if (!extra.isEmpty()) {
            if (blanks) out.add("");
            out.addAll(extra);
        }
        if (!flavor.isEmpty()) {
            out.add("");
            out.addAll(flavor);
        }
        if (source != null) out.add(source);
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
