package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.classes.ClassChangeGate;
import kr.labyrinth.classes.ClassChangeRule;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * /직업 — 6직업 목록 (역할군·주로 쓰는 능력치·설명) → 클릭하면 상세(스킬 4개·패시브·전직).
 * 안내 칸(4)과 전직 버튼(상세 40)에 직업 변경 규칙({@link ClassChangeGate} — 첫 선택 무료·전직의 두루마리·대기 시간)과
 * 지금 상태(남은 시간·가진 두루마리)를 보여 준다. 판정은 클릭 때 {@code changeClass} 가 같은 관문으로 다시 한다.
 */
public final class ClassMenu extends LabMenu {

    private static final int[] SLOTS = {10, 13, 16, 28, 31, 34}; // glyphs.yml menus.class.slots.classes (배경 아치)

    public ClassMenu(Services services) {
        super(services, "class", 6, "<#7fb2ff>직업 선택");
    }

    static String roleName(String role) {
        return switch (role == null ? "" : role) {
            case "tank" -> "탱커";
            case "melee" -> "근접 딜러";
            case "ranged" -> "원거리 딜러";
            case "magic" -> "마법 딜러";
            case "healer" -> "힐러 · 지원";
            case "assassin" -> "암살자";
            default -> role == null ? "" : role;
        };
    }

    /** "주로 쓰는 능력치 민첩 · 힘" 한 줄 (classes.yml main_stats). */
    static String mainStatsLine(ClassDef c) {
        return "<gray>주로 쓰는 능력치 " + kr.labyrinth.classes.LabyrinthClassService.mainStatsText(c);
    }

    static String inputName(String input) {
        return kr.labyrinth.core.InputKeys.label(input);
    }

    /** 직업 변경 규칙 + 지금 상태 (직업이 있을 때: 남은 대기 시간·가진 두루마리). */
    static List<String> changeRuleLines(ClassChangeGate gate, Player p, ClassDef cur) {
        Settings.ClassChange r = gate.rule();
        List<String> out = new ArrayList<>();
        out.add("<#ffd36b>직업 변경 규칙");
        out.add("<gray>첫 직업은 무료로 고릅니다.");
        if (r.requireItem()) {
            out.add("<gray>바꿀 때마다 <white>" + gate.itemName() + "</white> 1장");
            String hint = gate.shopHint();
            if (!hint.isEmpty()) out.add("<dark_gray>  (" + hint + ")");
        }
        if (r.cooldownHours() > 0) out.add("<gray>바꾼 뒤 <white>" + ClassChangeRule.hours(r.cooldownHours()) + "</white> 동안은 못 바꿈");
        out.add("<gray>미궁 공략 중에는 바꿀 수 없습니다.");
        if (cur == null) return out;
        ClassChangeRule.Verdict v = gate.check(p, cur.id(), null);
        if (v.block() == ClassChangeRule.Block.IN_RUN) out.add("<#ff8a8a>지금은 미궁 공략 중입니다");
        else if (v.cooldownLeftMs() > 0) out.add("<#ff8a8a>다음 변경까지 " + ClassChangeRule.duration(v.cooldownLeftMs()));
        else out.add("<#7fe07f>지금 바꿀 수 있습니다");
        if (v.needsItem()) out.add((v.missingItem() ? "<#ff8a8a>" : "<gray>") + "가진 " + gate.itemName() + " <white>" + gate.scrolls(p) + "장");
        return out;
    }

    @Override
    protected void draw(Player p) {
        ClassDef cur = services.classes().classOf(p);
        List<String> info = new ArrayList<>(List.of("<gray>현재 직업: " + (cur == null ? "<dark_gray>없음" : "<" + cur.color() + ">" + cur.name()),
                "<gray>직업 스킬은 무엇을 들었든",
                "<gray>" + kr.labyrinth.core.InputKeys.CLASS_KEYS + " 로 씁니다.",
                "<gray>무기·방어구·장신구는 어느 직업이든 쓸 수 있습니다."));
        info.add("");
        info.addAll(changeRuleLines(new ClassChangeGate(services), p, cur));
        deco(4, Button.icon(Material.BOOK, "<#7fb2ff><b>역할군을 골라 파티를 꾸리세요</b>", info));
        int i = 0;
        for (ClassDef c : services.content().classes().values()) {
            if (i >= SLOTS.length) break;
            boolean mine = cur != null && cur.id().equals(c.id());
            List<String> lore = new ArrayList<>();
            lore.add("<gray>역할 <white>" + roleName(c.role()));
            lore.add(mainStatsLine(c));
            lore.add("");
            lore.addAll(wrap(c.description(), 26, "<gray>"));
            lore.add("");
            lore.add(mine ? "<#7fe07f>▶ 현재 직업" : "<#ffd36b>클릭: 스킬 보기 · 전직");
            final ClassDef def = c;
            set(SLOTS[i++], UiTheme.glint(model(c.iconItem(), Material.PAPER, "<" + c.color() + "><b>" + c.name() + "</b>", lore), mine),
                    ctx -> {
                        click(ctx.player());
                        new ClassDetailMenu(services, def.id()).open(ctx.player());
                    });
        }
        set(49, model("berserker_emblem", Material.BLAZE_POWDER, "<#ffd84f>스탯 분배", List.of("<gray>스탯 메뉴로 이동")),
                ctx -> { click(ctx.player()); services.menus().openStats(ctx.player()); });
        backButton(45, MainMenu::reopen);
    }

    /** 직업 상세: 패시브 + 스킬 4개(키·해금 레벨·MP·재사용·설명) + 전직 버튼. */
    public static final class ClassDetailMenu extends LabMenu {

        private final String classId;

        ClassDetailMenu(Services services, String classId) {
            super(services, "class_detail", 6, "<#7fb2ff>" + Text.strip(nameOf(services, classId)));
            this.classId = classId;
        }

        private static String nameOf(Services s, String id) {
            ClassDef c = s.content().classDef(id);
            return c == null ? "직업" : c.name();
        }

        @Override
        protected void draw(Player p) {
            ClassDef c = services.content().classDef(classId);
            if (c == null) {
                backButton(45, pl -> new ClassMenu(services).open(pl));
                return;
            }
            ClassDef cur = services.classes().classOf(p);
            boolean mine = cur != null && cur.id().equals(c.id());
            int level = services.data().get(p).level();
            List<String> head = new ArrayList<>();
            head.add("<gray>역할 <white>" + roleName(c.role()));
            head.add(mainStatsLine(c));
            head.add("<gray>기본 HP <#ff5f6d>" + Text.num(c.baseHp()) + " <gray>(+" + Text.num(c.hpPerLevel()) + "/레벨)  MP <#6fc3ff>"
                    + Text.num(c.baseMp()) + " <gray>(+" + Text.num(c.mpPerLevel()) + "/레벨)");
            StringBuilder base = new StringBuilder("<gray>기본 스탯 ");
            for (Stat s : Stat.values()) base.append("<").append(s.color()).append(">").append(s.displayName()).append(" ").append(c.baseStat(s)).append(" ");
            head.add(base.toString());
            head.add("");
            head.addAll(wrap(c.description(), 28, "<gray>"));
            deco(4, model(c.iconItem(), Material.PAPER, "<" + c.color() + "><b>" + c.name() + "</b>", head));

            if (c.passive() != null) {
                List<String> pl = new ArrayList<>();
                pl.add("<#c9a2ff>패시브 — 항상 적용");
                pl.add("");
                pl.addAll(wrap(c.passive().description(), 28, "<gray>"));
                deco(13, Button.icon(Material.ENCHANTED_BOOK, "<#c9a2ff><b>" + c.passive().name() + "</b>", pl));
            }
            int[] slots = {19, 21, 23, 25};
            Material[] mats = {Material.IRON_INGOT, Material.GOLD_INGOT, Material.DIAMOND, Material.NETHER_STAR};
            for (int i = 0; i < c.skills().size() && i < slots.length; i++) {
                ClassDef.SkillDef sk = c.skills().get(i);
                boolean unlocked = level >= sk.unlockLevel();
                boolean ult = i == 3 || "SNEAK_DROP".equalsIgnoreCase(sk.input());
                List<String> lore = new ArrayList<>();
                lore.add("<gray>키 <#ffd36b>" + inputName(sk.input()) + (ult ? "  <#ff6b6b>궁극기" : ""));
                lore.add("<gray>MP <#6fc3ff>" + Text.num(sk.mana()) + "  <gray>재사용 <white>" + trim(sk.cooldown()) + "초");
                lore.add(unlocked ? "<#7fe07f>해금됨 (Lv." + sk.unlockLevel() + ")" : "<#ff6b6b>Lv." + sk.unlockLevel() + " 에 해금");
                lore.add("");
                lore.addAll(wrap(sk.description(), 28, "<gray>"));
                deco(slots[i], Button.icon(unlocked ? mats[i] : Material.GRAY_DYE,
                        (unlocked ? "<" + c.color() + ">" : "<dark_gray>") + "<b>" + sk.name() + "</b>", lore));
            }

            if (mine) {
                deco(40, UiTheme.glint(Button.icon(Material.LIME_STAINED_GLASS_PANE, "<#7fe07f><b>현재 직업입니다</b>",
                        List.of("<gray>스탯을 분배해 성장시키세요.")), true));
            } else {
                ClassChangeGate gate = new ClassChangeGate(services);
                Settings.ClassChange rule = gate.rule();
                ClassChangeRule.Verdict v = gate.check(p, cur == null ? null : cur.id(), c.id());
                List<String> lore = new ArrayList<>();
                lore.add("<gray>직업을 <" + c.color() + ">" + c.name() + "</" + c.color() + ">(으)로 바꿉니다.");
                if (cur != null) lore.add("<gray>레벨·장비·스탯 포인트는 그대로 유지됩니다.");
                lore.add("");
                if (v.first()) {
                    lore.add("<#7fe07f>첫 직업 선택 — 무료");
                } else if (v.needsItem()) {
                    lore.add((v.missingItem() ? "<#ff8a8a>✘ " : "<#9be89b>✔ ") + "<white>" + gate.itemName() + "</white> 1장 <dark_gray>(가진 수 "
                            + gate.scrolls(p) + ")");
                    if (v.missingItem() && !gate.shopHint().isEmpty()) lore.add("<dark_gray>  " + gate.shopHint());
                }
                if (v.cooldownLeftMs() > 0) lore.add("<#ff8a8a>✘ 다음 변경까지 " + ClassChangeRule.duration(v.cooldownLeftMs()));
                if (rule.cooldownHours() > 0) {
                    lore.add("<dark_gray>" + (v.first() ? "고른" : "바꾼") + " 뒤 " + ClassChangeRule.hours(rule.cooldownHours()) + " 동안은 다시 못 바꿉니다.");
                }
                lore.add(v.block() == ClassChangeRule.Block.IN_RUN ? "<#ff8a8a>✘ 미궁 공략 중에는 바꿀 수 없습니다."
                        : "<dark_gray>미궁 공략 중에는 바꿀 수 없습니다.");
                lore.add("");
                lore.add(v.allowed() ? "<#ffd36b>클릭: " + (v.consumesItem() ? "두루마리 1장을 쓰고 전직" : "전직") : "<#ff6b6b>지금은 바꿀 수 없습니다");
                set(40, Button.icon(v.allowed() ? Material.EMERALD_BLOCK : Material.REDSTONE_BLOCK,
                                (v.allowed() ? "<#7fe07f>" : "<#ff8a8a>") + "<b>" + (cur == null ? "이 직업 선택" : "이 직업으로 전직") + "</b>", lore),
                        ctx -> {
                            Player pl = ctx.player();
                            boolean changed = services.classes().changeClass(pl, classId);
                            if (changed) ok(pl);
                            else deny(pl);
                            refresh();
                        });
            }
            backButton(45, pl -> new ClassMenu(services).open(pl));
        }

        private static String trim(double v) {
            return v == Math.floor(v) ? String.valueOf((long) v) : String.format("%.1f", v);
        }
    }
}
