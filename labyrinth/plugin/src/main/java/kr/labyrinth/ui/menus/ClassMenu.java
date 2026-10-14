package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.stats.Stat;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/** /직업 — 6직업 목록 (역할군·주 스탯·무기·설명) → 클릭하면 상세(스킬 4개·패시브·전직). */
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

    static String weaponName(String type) {
        return switch (type == null ? "" : type) {
            case "sword_shield" -> "검과 방패";
            case "greatsword" -> "대검";
            case "bow" -> "활";
            case "staff" -> "지팡이";
            case "scepter" -> "홀";
            case "dagger" -> "단검";
            default -> type;
        };
    }

    static String inputName(String input) {
        return kr.labyrinth.core.InputKeys.label(input);
    }

    @Override
    protected void draw(Player p) {
        ClassDef cur = services.classes().classOf(p);
        deco(4, Button.icon(Material.BOOK, "<#7fb2ff><b>역할군을 골라 파티를 꾸리세요</b>",
                List.of("<gray>현재 직업: " + (cur == null ? "<dark_gray>없음" : "<" + cur.color() + ">" + cur.name()),
                        "<gray>직업 스킬은 무엇을 들었든",
                        "<gray>" + kr.labyrinth.core.InputKeys.CLASS_KEYS + " 로 씁니다.")));
        int i = 0;
        for (ClassDef c : services.content().classes().values()) {
            if (i >= SLOTS.length) break;
            boolean mine = cur != null && cur.id().equals(c.id());
            List<String> lore = new ArrayList<>();
            lore.add("<gray>역할 <white>" + roleName(c.role()) + "  <gray>주 스탯 <" + (c.primaryStat() == null ? "white" : c.primaryStat().color())
                    + ">" + (c.primaryStat() == null ? "-" : c.primaryStat().displayName()));
            lore.add("<gray>무기 <white>" + String.join(", ", c.weaponTypes().stream().map(ClassMenu::weaponName).toList()));
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
            head.add("<gray>무기 <white>" + String.join(", ", c.weaponTypes().stream().map(ClassMenu::weaponName).toList()));
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
                List<String> lore = new ArrayList<>();
                lore.add("<gray>직업을 <" + c.color() + ">" + c.name() + "</" + c.color() + ">(으)로 바꿉니다.");
                if (cur != null) lore.add("<gray>레벨·장비·스탯 포인트는 그대로 유지됩니다.");
                lore.add("<dark_gray>미궁 진행 중에는 바꿀 수 없습니다.");
                lore.add("");
                lore.add("<#ffd36b>클릭: 전직");
                set(40, Button.icon(Material.EMERALD_BLOCK, "<#7fe07f><b>" + (cur == null ? "이 직업 선택" : "이 직업으로 전직") + "</b>", lore),
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
