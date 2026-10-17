package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Menu;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * 광산 관리소 (R §2-1, 계약 §2.5) — 얕은 갱도 승강기 홀 북쪽 벽감의 우클릭 칸 mine_office · 구역 광부 NPC (miner).
 * 메뉴는 코드로 만든다: npcs.yml 정의가 없어도, 마을·구역이 없어도 열린다. 탭 내용은 Q3 메뉴를 연다
 * (곡괭이 = {@code CraftingService.openMineShop}, 제련·새기기·벼리기 = {@code CraftingService.openSmelter}, 팔기 = SellMenu).
 * 광맥 현황 = {@link #info} (광부 게시판 mine_info 와 같음). 기력 탭은 없다 (계약 §0-1).
 */
final class MineMenus {

    private final MineModule module;

    MineMenus(MineModule module) { this.module = module; }

    void office(Player p) { new Office().open(p); }

    void info(Player p) { new Info().open(p); }

    /** 여기서 바로 승강기를 탈 수 있나: 광산 안, 또는 광산 마을 승강기 가까이 (12칸). */
    private boolean canRide(Player p) { return module.isMineWorld(p.getWorld()) || MineLinks.nearLift(p.getLocation(), 12); }

    /** 층 칸 클릭: 탈 수 있으면 그 층으로, 아니면 어디서 타는지 알려 준다 (예전엔 아무 일도 없었다). */
    private void ride(Player p, MineLevel l) {
        p.closeInventory();
        if (canRide(p)) {
            module.lift().ride(p, l);
            return;
        }
        boolean district = MineLinks.usable(MineLinks.district());
        Text.send(p, "<#e8c58a>[광산]</#e8c58a> <gray>" + (district ? "광산 마을 승강장 안쪽의 구리 문(승강기)에서 내려갈 수 있습니다. 승강장으로 가려면 <white>/미궁 광산</white>"
                : "<white>/미궁 광산</white> 으로 광산에 가서 승강기를 타세요."));
    }

    private final class Office extends Menu {
        Office() { super(6, UiTheme.title("mine_office", 6, "<#e8c58a>광산 관리소")); }

        @Override
        protected void build(Player viewer) {
            UiTheme.frame(this, "mine_office", 6);
            var s = module.services();
            // glyphs.yml menus.mine_office: 탭 1·2·3·5·6·7 = 곡괭이·제련·새기기·벼리기·팔기·현황 · 안내 4 · 지갑 49
            set(1, UiTheme.item("copper_pickaxe", Material.IRON_PICKAXE, "<#e8843f>곡괭이",
                    List.of("<gray>첫 구리 곡괭이는 무료입니다.", "<gray>잃었으면 다시 살 수 있습니다.", "", "<yellow>클릭: 열기")),
                    ctx -> s.crafting().openMineShop(ctx.player()));
            set(2, UiTheme.item("copper_ingot", Material.COPPER_INGOT, "<#ff9a5a>제련",
                    List.of("<gray>광석 둘을 주괴 하나로 녹입니다.", "", "<yellow>클릭: 열기")),
                    ctx -> s.crafting().openSmelter(ctx.player(), "smelt"));
            set(3, UiTheme.item("quartz", Material.QUARTZ, "<#9ccaff>새기기",
                    List.of("<gray>보석과 정수로 강화석을 만듭니다.", "", "<yellow>클릭: 열기")),
                    ctx -> s.crafting().openSmelter(ctx.player(), "carve"));
            set(4, Button.icon(Material.LANTERN, "<#e8c58a>광산 관리소",
                    List.of("<gray>여섯 층 모두 처음부터 열려 있습니다.", "<gray>곡괭이보다 한 단계 단단한 광석도",
                            "<gray>캘 수 있지만 느립니다.", "<gray>좋은 곡괭이일수록 빨리 캡니다.", "<gray>광맥은 모두가 함께 씁니다.")), null);
            set(5, UiTheme.item("iron_pickaxe", Material.DIAMOND_PICKAXE, "<#c9ced6>곡괭이 벼리기",
                    List.of("<gray>쓰던 곡괭이를 더 단단한 곡괭이로", "<gray>다시 벼립니다.", "", "<yellow>클릭: 열기")),
                    ctx -> s.crafting().openSmelter(ctx.player(), "pickaxe"));
            set(6, Button.icon(Material.GOLD_NUGGET, "<#ffd36b>팔기",
                    List.of("<gray>광석·주괴·보석을 팝니다.", "<gray>도구는 팔 수 없습니다.", "", "<yellow>클릭: 열기")),
                    ctx -> {
                        var sell = kr.labyrinth.items.sell.SellService.get();
                        if (sell != null) sell.open(ctx.player());
                        else s.crafting().openMineShop(ctx.player());
                    });
            set(7, Button.icon(Material.MAP, "<#7fd8ff>광맥 현황",
                    List.of("<gray>층마다 다 찬 광맥과 보석 노드.", "", "<yellow>클릭: 보기")),
                    ctx -> info(ctx.player()));
            // 가운데 줄: 층 1~6 + 승강기 (0.3.6.1 — 광산 마을 승강장 앞의 광부 브론 메뉴에서도 바로 탄다)
            boolean canRide = canRide(viewer);
            boolean inMine = module.isMineWorld(viewer.getWorld());
            set(22, Button.icon(Material.IRON_CHAIN, "<#e8c58a>승강기",
                    inMine ? List.of("<gray>다른 층으로 가거나 마을로 올라갑니다.", "", "<yellow>클릭: 열기")
                            : canRide ? List.of("<gray>승강장 안쪽 구리 문이 승강기입니다.", "<gray>층을 골라 광산으로 내려갑니다.", "", "<yellow>클릭: 열기")
                            : List.of("<gray>광산 승강장으로 갑니다.", "<gray>(/미궁 광산 과 같음)", "", "<yellow>클릭: 가기")),
                    ctx -> {
                        if (canRide(ctx.player())) module.lift().open(ctx.player());
                        else {
                            ctx.player().closeInventory();
                            module.openMine(ctx.player());
                        }
                    });
            int[] levelSlots = {19, 20, 21, 23, 24, 25};
            List<MineLevel> levels = module.levels();
            for (int i = 0; i < levels.size() && i < levelSlots.length; i++) {
                MineLevel l = levels.get(i);
                int[] st = module.veins().status(l);
                List<String> lore = new ArrayList<>();
                lore.add("<gray>광맥 <white>" + st[0] + "</white>/" + st[1] + " · 보석 노드 <white>" + st[2] + "</white>/" + st[3]);
                lore.add("<gray>나는 광석: <white>" + Text.escape(module.lift().ores(l)));
                lore.add("");
                lore.add(canRide ? "<yellow>클릭: 이 층으로 내려가기" : "<gray>승강기에서 고를 수 있습니다");
                set(levelSlots[i], Button.icon(MineLift.icon(l.n), l.coloredName(), lore), ctx -> ride(ctx.player(), l));
            }
            set(45, Button.icon(Material.BOOK, "<#e8c58a>처음이라면",
                    List.of("<gray>1. 곡괭이를 받습니다 (첫 구리 곡괭이 무료).", "<gray>2. 승강기로 내려가 광맥을 캡니다.",
                            "<gray>3. 광석은 제련에서 주괴로 녹입니다.", "<gray>4. 남는 것은 팔기에서 팝니다.",
                            "<gray>   깊은 광석·보석일수록 비싸게 팔립니다.",
                            "<gray>좋은 곡괭이일수록 깊은 층 광석을 빨리 캡니다.")), null);
            set(49, Button.icon(Material.GOLD_NUGGET, "<#ffd27a>보유 골드 " + Text.num(s.data().get(viewer).gold()), List.of()), null);
            set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
        }
    }

    private final class Info extends Menu {
        Info() { super(6, UiTheme.title("mine_info", 6, "<#e8c58a>광맥 현황")); }

        @Override
        protected void build(Player viewer) {
            UiTheme.frame(this, "mine_info", 6);
            int[] slots = {11, 13, 15, 29, 31, 33};
            List<MineLevel> levels = module.levels();
            int miners = module.veins().miners();
            for (int i = 0; i < levels.size() && i < slots.length; i++) {
                MineLevel l = levels.get(i);
                int[] st = module.veins().status(l);
                List<String> lore = new ArrayList<>();
                lore.add("<gray>광맥 <white>" + st[0] + "</white>/" + st[1] + " · 보석 노드 <white>" + st[2] + "</white>/" + st[3]);
                lore.add("<gray>나는 광석: <white>" + Text.escape(module.lift().ores(l)));
                double next = module.veins().nextRefill(l);
                if (next > 0) lore.add("<gray>다음 광맥까지 약 <white>" + UiTheme.clock(Math.round(next)));
                lore.add("<gray>다시 차는 데 <white>" + module.config().regenMinutes().get(l.n - 1) + "분</white>");
                int here = module.minersAt(l);
                if (here > 0) lore.add("<gray>지금 캐는 사람 <white>" + here + "명");
                lore.add("");
                lore.add(canRide(viewer) ? "<yellow>클릭: 승강기로 내려가기" : "<gray>승강장의 승강기에서 내려갈 수 있습니다");
                set(slots[i], Button.icon(MineLift.icon(l.n), l.coloredName(), lore), ctx -> ride(ctx.player(), l));
            }
            set(49, Button.icon(Material.CLOCK, "<#7fd8ff>함께 캐기",
                    List.of("<gray>광맥은 모두가 함께 씁니다.", "<gray>누가 캐면 모두에게 빈 광맥이 되고,",
                            "<gray>" + module.config().refillLine(), "<gray>사람 수와는 상관없어요.",
                            "<gray>지금 광산에 <white>" + miners + "명")),
                    null);
            set(53, UiTheme.close(), ctx -> ctx.player().closeInventory());
        }
    }
}
