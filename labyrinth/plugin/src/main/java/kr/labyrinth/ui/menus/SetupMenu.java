package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 관리자 초기 설정 GUI (ARCHITECTURE §5): 서버 난이도 4개 중 하나 + 오버월드 입구 방식(석문 블록 / NPC 만).
 * 미리 지은 마을 월드면(VILLAGE.md §4.3) 입구 방식 선택은 숨기고 "입구: 마을의 미궁의 아가리" 정보만 보여 준다.
 * 확정 = {@code /labadmin setup <난이도>} (첫 설정이면 미궁 개방 방송) + config {@code entrance.mode} 저장.
 * "확정하고 여기에 입구 설치" = 이어서 {@code /labadmin setentrance <방식>} (지형에 맞춰 설치 — dungeon 담당).
 */
public final class SetupMenu extends LabMenu {

    private static final int[] DIFF_SLOTS = {10, 12, 14, 16}; // glyphs.yml menus.setup.slots (배경 소켓)
    private String difficulty;
    private String mode;

    public SetupMenu(Services services) {
        super(services, "setup", 6, "<#ff6b6b>미궁 라비린스 · 서버 설정");
        Settings s = services.settings();
        this.difficulty = s.isDifficultySet() ? s.difficulty().id() : "normal";
        String m = s.entrance().mode();
        this.mode = m == null || m.isBlank() ? "block" : m;
    }

    private static Material diffIcon(String id) {
        return switch (id) {
            case "easy" -> Material.LIME_CONCRETE;
            case "hard" -> Material.ORANGE_CONCRETE;
            case "nightmare" -> Material.CRIMSON_NYLIUM;
            default -> Material.LIGHT_BLUE_CONCRETE;
        };
    }

    private static String diffColor(String id) {
        return switch (id) {
            case "easy" -> "#7fe07f";
            case "hard" -> "#ff9a4d";
            case "nightmare" -> "#ff4d6d";
            default -> "#7fd8ff";
        };
    }

    private static String diffBlurb(String id) {
        return switch (id) {
            case "easy" -> "처음 해 보는 친구들과 이야기를 즐기기 좋습니다.";
            case "hard" -> "패턴을 익혀야 넘을 수 있습니다. 역할 분담이 중요합니다.";
            case "nightmare" -> "숙련자 전용. 경고 시간이 짧고 한 번의 실수가 치명적입니다.";
            default -> "제작 의도대로의 균형. 처음이라면 이 난이도를 권합니다.";
        };
    }

    @Override
    protected void draw(Player p) {
        Settings s = services.settings();
        deco(4, Button.icon(Material.COMMAND_BLOCK, "<#ff6b6b><b>서버 초기 설정</b>",
                List.of("<gray>미궁 전체에 적용되는 <white>서버 난이도</white>를 정합니다.",
                        "<gray>플레이어는 입장할 때 난이도를 고르지 않습니다.",
                        "<gray>나중에 <white>/labadmin difficulty</white> 로 바꿀 수 있습니다.",
                        "",
                        "<gray>현재: " + (s.isDifficultySet() ? "<white>" + s.difficulty().name() : "<#ff6b6b>미설정 (미궁 입장이 막혀 있음)"))));
        int i = 0;
        for (Difficulty d : s.difficulties().values()) {
            if (i >= DIFF_SLOTS.length) break;
            boolean sel = d.id().equals(difficulty);
            String col = diffColor(d.id());
            List<String> lore = new ArrayList<>();
            lore.add("<gray>몬스터 HP <white>×" + d.hp() + "  <gray>피해 <white>×" + d.damage());
            lore.add("<gray>드롭 <white>×" + d.drop() + "  <gray>경험치 <white>×" + d.xp());
            lore.add("<gray>경고 시간 <white>×" + d.telegraph());
            lore.add("");
            lore.addAll(wrap(diffBlurb(d.id()), 24, "<" + col + ">"));
            lore.add("");
            lore.add(sel ? "<#7fe07f>▶ 선택됨" : "<#ffd36b>클릭: 선택");
            ItemStack icon = UiTheme.glint(Button.icon(diffIcon(d.id()), "<" + col + "><b>" + d.name() + "</b>", lore), sel);
            final String id = d.id();
            set(DIFF_SLOTS[i++], icon, ctx -> {
                difficulty = id;
                click(ctx.player());
                refresh();
            });
        }
        boolean village = kr.labyrinth.village.VillageService.present();
        boolean block = "block".equals(mode);
        Difficulty chosen = s.difficulty(difficulty);
        String dn = chosen == null ? difficulty : chosen.name();
        if (village) {
            // 미리 지은 마을 월드: 입구는 마을 게이트로 정해져 있다 (VILLAGE.md §4.3)
            deco(40, Button.icon(Material.CRYING_OBSIDIAN, "<#c79bff><b>입구: 마을의 미궁의 아가리</b>",
                    List.of("<gray>이 월드에는 미리 지은 마을이 있습니다.", "<gray>광장에서 계단을 오른 큰 아치가 미궁 입구입니다.",
                            "<gray>게이트 문을 우클릭하거나 안내인 벨라에게", "<gray>말을 걸면 입장 메뉴가 열립니다.")));
            set(49, Button.icon(Material.LIME_CONCRETE, "<#7fe07f><b>확정</b>",
                    List.of("<gray>난이도 <white>" + dn + "</white> · 입구 <white>마을 게이트")),
                    ctx -> confirm(ctx.player(), false));
        } else {
            set(38, UiTheme.glint(Button.icon(Material.CHISELED_STONE_BRICKS, "<white><b>입구: 석문</b>",
                    List.of("<gray>관리자가 고른 자리에 작은 석문을 세웁니다.",
                            "<gray>경사·바닥 높이에 맞추고 나무·물 위는 피합니다.",
                            "<gray>바꾼 블록은 기록했다가 <white>removeentrance</white> 로 복원.",
                            "", block ? "<#7fe07f>▶ 선택됨" : "<#ffd36b>클릭: 선택")), block),
                    ctx -> { mode = "block"; click(ctx.player()); refresh(); });
            set(42, UiTheme.glint(Button.icon(Material.ARMOR_STAND, "<white><b>입구: NPC 만</b>",
                    List.of("<gray>블록을 하나도 바꾸지 않고", "<gray>안내인 NPC 만 세웁니다.",
                            "", !block ? "<#7fe07f>▶ 선택됨" : "<#ffd36b>클릭: 선택")), !block),
                    ctx -> { mode = "npc"; click(ctx.player()); refresh(); });

            set(49, Button.icon(Material.LIME_CONCRETE, "<#7fe07f><b>확정</b>",
                    List.of("<gray>난이도 <white>" + dn + "</white> · 입구 <white>" + (block ? "석문" : "NPC 만"),
                            "<gray>입구 위치는 나중에 <white>/labadmin setentrance</white>")),
                    ctx -> confirm(ctx.player(), false));
            set(51, Button.icon(Material.ENDER_PEARL, "<#7fd8ff><b>확정 + 지금 이 자리에 입구 설치</b>",
                    List.of("<gray>난이도 <white>" + dn + "</white> · 입구 <white>" + (block ? "석문" : "NPC 만"),
                            "<gray>서 있는 자리(바라보는 방향)에 입구를 만듭니다.",
                            "<dark_gray>미궁 월드 밖의 블록은 석문 방식일 때만, 기록 후 바꿉니다.")),
                    ctx -> confirm(ctx.player(), true));
        }
        set(45, UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private void confirm(Player p, boolean placeHere) {
        if (!kr.labyrinth.core.ServerSetup.canSetDifficulty(p)) {
            deny(p);
            return;
        }
        boolean admin = p.hasPermission(CommandService.PERM_ADMIN);
        boolean village = kr.labyrinth.village.VillageService.present();
        String m = mode;
        if (admin && !village) services.updateConfig(c -> c.set("entrance.mode", m));
        p.closeInventory();
        if (!kr.labyrinth.core.ServerSetup.applyDifficulty(p, difficulty)) return;
        p.playSound(p.getLocation(), Sound.BLOCK_BEACON_ACTIVATE, 0.8f, 1.2f);
        if (village) return; // 입구 = 마을 게이트 (이미 설정됨)
        if (!admin) {
            Text.send(p, "<gray>입구(석문/NPC) 설치는 op 가 <white>/labadmin setentrance</white> 로 할 수 있습니다. "
                    + "입구가 없어도 파티장 근처에 모여 <white>/미궁</white> 으로 입장할 수 있어요.");
            return;
        }
        if (placeHere) {
            p.performCommand("labadmin setentrance " + m);
        } else if (!services.settings().entrance().isSet()) {
            Text.send(p, "<gray>입구를 세울 자리에서 <white>/labadmin setentrance " + m + "</white> 를 입력하세요.");
        }
    }
}
