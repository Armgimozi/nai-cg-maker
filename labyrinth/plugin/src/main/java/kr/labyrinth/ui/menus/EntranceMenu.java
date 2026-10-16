package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 미궁 입장 — 층 선택(해금 기준: 솔로 = 내 해금층, 파티 = 파티원 중 최소 해금층) + 파티 준비 상태(입구 근처·레벨)
 * + 서버 난이도 표시(선택 없음 — 난이도 배율 한 벌, 층 아이콘마다 그 층 실효 배율·솔로 보정). 클릭 = {@code DungeonService.enter}
 * (검사·안내는 dungeon 담당).
 */
public final class EntranceMenu extends LabMenu {

    private static final int[] FLOOR_SLOTS = {11, 12, 13, 14, 15, 20, 21, 22, 23, 24};
    private static final int[] MEMBER_SLOTS = {37, 38, 39, 40, 41, 42, 43, 28, 34, 46};

    public EntranceMenu(Services services) {
        super(services, "entrance", 6, "<#7fd8ff>미궁 입장 · 층 선택");
    }

    private int allowedFloor(Player p, List<Player> members) {
        int min = Integer.MAX_VALUE;
        for (Player m : members) min = Math.min(min, services.data().get(m).unlockedFloor());
        if (min == Integer.MAX_VALUE) min = services.data().get(p).unlockedFloor();
        return Math.max(1, min);
    }

    private boolean near(Player m) {
        Settings.Entrance e = services.settings().entrance();
        Location at = e.toLocation();
        if (at == null) return true; // 입구 미지정 = 어디서나 (dungeon 이 최종 판단)
        return m.getWorld().equals(at.getWorld()) && m.getLocation().distanceSquared(at) <= e.radius() * e.radius();
    }

    @Override
    protected void draw(Player p) {
        Settings s = services.settings();
        List<Player> members = services.party().onlineMembers(p);
        boolean party = members.size() > 1;
        Player leader = services.party().leader(p);
        boolean isLeader = leader == null || leader.equals(p);
        int allowed = allowedFloor(p, members);

        Difficulty d = s.difficulty();
        int size = Math.max(1, members.size());
        List<String> info = new ArrayList<>();
        info.add("<gray>서버 난이도 " + (s.isDifficultySet() ? "<white><b>" + d.name() + "</b>" : "<#ff6b6b>미설정 — 관리자가 정하기 전엔 입장 불가"));
        if (s.isDifficultySet()) {
            // 기본은 모든 층 같은 배율 한 벌. 관리자가 층 램프를 직접 적었을 때만 1층 값→원래 값 범위 (층마다 실제 값은 아래 층 아이콘)
            Difficulty first = d.atFloor(1);
            info.add("<dark_gray>몬스터 HP ×" + range(first.hp(), d.hp()) + " · 피해 ×" + range(first.damage(), d.damage())
                    + (d.drop() != 1.0 ? " · 드롭 ×" + MainMenu.decimal(d.drop()) : ""));
            info.add(d.ramp() != null ? "<dark_gray>깊이 내려갈수록 강해져 지하 " + d.ramp().fullFloor() + "층부터 최대"
                    : "<dark_gray>1층부터 모든 층 같은 배율");
        }
        info.add("");
        double soloHp = s.party().hp(1), soloDmg = s.party().damage(1);
        if (party) {
            info.add("<gray>파티 <white>" + members.size() + "명</white> — 몬스터 HP ×" + String.format("%.2f", s.party().hp(members.size()))
                    + " · 피해 ×" + String.format("%.2f", s.party().damage(members.size())));
        } else if (soloHp != 1.0 || soloDmg != 1.0) {
            info.add("<gray>솔로 입장 — 솔로 보정 HP ×" + MainMenu.decimal(soloHp) + " · 피해 ×" + MainMenu.decimal(soloDmg));
        } else {
            info.add("<gray>솔로 입장");
        }
        info.add(party ? "<gray>입장 가능: 파티원 중 가장 낮은 해금층 <white>지하 " + allowed + "층" : "<gray>입장 가능: <white>지하 " + allowed + "층까지");
        if (party && !isLeader) info.add("<#ffd36b>파티장(" + Text.escape(leader.getName()) + ")만 입장을 시작할 수 있습니다.");
        deco(4, Button.icon(Material.ENDER_EYE, "<#7fd8ff><b>미궁 라비린스</b>", info));

        int myClears;
        for (int i = 0; i < FLOOR_SLOTS.length; i++) {
            int n = i + 1;
            FloorDef f = services.content().floor(n);
            if (f == null) continue;
            boolean open = n <= allowed;
            myClears = (int) services.data().get(p).counter("dungeon.clear_floor_" + n);
            List<String> lore = new ArrayList<>();
            if (f.subtitle() != null && !f.subtitle().isBlank()) lore.add("<gray>" + Text.escape(Text.strip(f.subtitle())));
            BossDef boss = services.content().bossOfFloor(n);
            if (boss != null && open) lore.add("<gray>수호자 <#ff9a4d>" + Text.escape(Text.strip(boss.name())));
            if (open && s.isDifficultySet()) {
                // 이 층 실효 배율 = 난이도(직접 적은 층 램프가 있으면 그 층 값) × 인원 (솔로 보정 포함) — 입장 안내문과 같은 값
                Difficulty fd = d.atFloor(n);
                lore.add("<dark_gray>몬스터 HP ×" + String.format("%.2f", fd.hp() * s.party().hp(size))
                        + " · 피해 ×" + String.format("%.2f", fd.damage() * s.party().damage(size)));
            }
            lore.add("");
            if (open) lore.addAll(wrap(f.description(), 26, "<dark_gray>"));
            else lore.add("<dark_gray>지하 " + (n - 1) + "층을 돌파하면 열립니다.");
            lore.add("");
            services.records().get("first_clear.floor_" + n).ifPresent(r ->
                    lore.add("<#ffd36b>최초 돌파 <white>" + Text.escape(String.join(", ", r.names()))));
            services.records().get("speed.floor_" + n).ifPresent(r -> {
                Object sec = r.extra().get("seconds");
                if (sec instanceof Number num) lore.add("<#7fd8ff>최단 기록 <white>" + UiTheme.clock(Math.round(num.doubleValue())));
            });
            if (myClears > 0) lore.add("<gray>내 클리어 <white>" + myClears + "회");
            lore.add(open ? (isLeader ? "<#7fe07f>클릭: 입장" : "<#ffd36b>파티장이 입장을 시작합니다") : "<#ff6b6b>잠김");
            ItemStack icon = open ? Button.icon(floorBlock(f), "<#7fd8ff><b>지하 " + n + "층</b> <white>" + Text.escape(Text.strip(f.name())), lore)
                    : Button.icon(Material.IRON_BARS, "<dark_gray><b>지하 " + n + "층</b> <gray>" + Text.escape(Text.strip(f.name())), lore);
            final int floor = n;
            set(FLOOR_SLOTS[i], icon, ctx -> {
                Player pl = ctx.player();
                if (!open || !isLeader) {
                    deny(pl);
                    return;
                }
                ok(pl);
                pl.closeInventory();
                services.dungeon().enter(pl, floor);
            });
        }

        // 파티 준비 상태
        int idx = 0;
        for (Player m : members) {
            if (idx >= MEMBER_SLOTS.length) break;
            boolean close = near(m);
            boolean inside = services.dungeon().currentInstance(m).isPresent();
            ClassDef cls = services.classes().classOf(m);
            List<String> lore = new ArrayList<>();
            lore.add("<gray>Lv.<white>" + services.data().get(m).level() + "</white> " + (cls == null ? "<dark_gray>직업 없음" : "<" + cls.color() + ">" + cls.name()));
            lore.add("<gray>해금 <white>지하 " + services.data().get(m).unlockedFloor() + "층");
            lore.add(inside ? "<#ff6b6b>이미 미궁 안" : close ? "<#7fe07f>✔ 입구 근처 — 준비됨" : "<#ffd36b>입구에서 멀리 있음");
            boolean lead = leader != null && leader.equals(m);
            deco(MEMBER_SLOTS[idx++], MainMenu.head(m, (lead ? "<#ffd36b>★ " : "<white>") + Text.escape(m.getName()), lore));
        }
        if (services.dungeon().currentInstance(p).isPresent()) {
            List<String> back = new ArrayList<>(List.of("<gray>미궁을 나와 입구로 돌아갑니다."));
            double cast = services.settings().deathPenalty().combatExitSeconds();
            if (cast > 0 && kr.labyrinth.core.DeathPenaltyRules.plan(services.settings().deathPenalty(),
                    kr.labyrinth.core.DeathPenaltyRules.Where.DUNGEON_RUN, false).any()) {
                back.add("<dark_gray>싸우는 중이면 " + kr.labyrinth.core.DeathPenaltyRules.seconds(cast) + "초 걸립니다.");
            }
            set(53, Button.icon(Material.RECOVERY_COMPASS, "<#ff9a4d><b>귀환</b>", back),
                    ctx -> { click(ctx.player()); ctx.player().closeInventory(); services.dungeon().leaveByChoice(ctx.player()); });
        }
        set(49, Button.icon(Material.CAKE, "<#c9a2ff>파티 관리", List.of("<gray>파티 메뉴로 이동")),
                ctx -> { click(ctx.player()); services.menus().openParty(ctx.player()); });
        backButton(45, MainMenu::reopen);
    }

    /** 직접 적은 층 램프 범위 "1.5→1.8" (램프가 없어 같으면 하나). */
    private static String range(double from, double to) {
        String a = MainMenu.decimal(from), b = MainMenu.decimal(to);
        return a.equals(b) ? b : a + "→" + b;
    }

    private static Material floorBlock(FloorDef f) {
        List<String> pal = f.palette("floor");
        for (String name : pal) {
            Material m = Material.matchMaterial(name);
            if (m != null && m.isItem() && m.isBlock()) return m;
        }
        return Material.STONE_BRICKS;
    }
}
