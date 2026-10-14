package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.party.Party;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;

/**
 * /파티 — 파티원(머리·레벨·직업·HP·역할 균형), 파티장 조작(초대·위임·추방·해산), 탈퇴, 파티 채팅, 초대 수락/거절.
 * 실제 동작은 파티 명령(dungeon+party 담당)으로 위임해 검사·메시지를 그쪽과 같게 유지한다.
 */
public final class PartyMenu extends LabMenu {

    private static final int[] MEMBER_SLOTS = {9, 11, 13, 15, 17, 27, 29, 31, 33, 35}; // glyphs.yml menus.party.slots.members

    public PartyMenu(Services services) {
        super(services, "party", 6, "<#c9a2ff>파티");
    }

    @Override
    protected void draw(Player p) {
        Party party = services.party().partyOf(p).orElse(null);
        int max = services.settings().party().maxSize();
        if (party == null) {
            deco(4, Button.icon(Material.CAKE, "<#c9a2ff><b>파티가 없습니다</b>",
                    List.of("<gray>혼자 들어가거나, 친구를 초대해 함께 공략하세요.",
                            "<gray>인원이 늘면 몬스터가 강해지고 보상도 조금 늘어납니다.",
                            "<gray>최대 <white>" + max + "명")));
            set(11, Button.icon(Material.LIME_BANNER, "<#7fe07f><b>파티 만들기</b>", List.of("<gray>내가 파티장이 됩니다.")),
                    ctx -> command(ctx, "party create", false));
            set(13, Button.icon(Material.PLAYER_HEAD, "<#7fd8ff><b>친구 초대</b>", List.of("<gray>접속 중인 플레이어 목록에서 고릅니다.", "<dark_gray>(파티가 없으면 자동으로 만들어집니다)")),
                    ctx -> { click(ctx.player()); new InvitePicker(services).open(ctx.player()); });
            set(15, Button.icon(Material.WRITABLE_BOOK, "<#ffd36b><b>받은 초대 수락</b>", List.of("<gray>가장 최근 초대를 수락합니다.")),
                    ctx -> command(ctx, "party accept", false));
            set(31, Button.icon(Material.RED_DYE, "<#ff6b6b>받은 초대 거절", List.of()),
                    ctx -> command(ctx, "party decline", false));
            backButton(45, MainMenu::reopen);
            return;
        }
        boolean leader = party.isLeader(p.getUniqueId());
        List<String> roles = new ArrayList<>();
        java.util.Map<String, Integer> roleCount = new java.util.LinkedHashMap<>();
        for (UUID u : party.members()) {
            Player m = Bukkit.getPlayer(u);
            ClassDef c = m == null ? null : services.classes().classOf(m);
            roleCount.merge(c == null ? "없음" : ClassMenu.roleName(c.role()), 1, Integer::sum);
        }
        roleCount.forEach((k, v) -> roles.add("<gray>· <white>" + k + " <dark_gray>×" + v));
        List<String> head = new ArrayList<>();
        head.add("<gray>인원 <white>" + party.size() + "</white> / " + max);
        head.add("<gray>몬스터 HP ×" + String.format("%.2f", services.settings().party().hp(party.size()))
                + " · 피해 ×" + String.format("%.2f", services.settings().party().damage(party.size())));
        head.add("");
        head.add("<#c9a2ff>역할 구성");
        head.addAll(roles);
        head.add("");
        head.add("<#c9a2ff>클릭: 파티 채팅 켜기/끄기 <dark_gray>(켜면 채팅이 파티원에게만)");
        set(4, Button.icon(Material.CAKE, "<#c9a2ff><b>내 파티</b>", head), ctx -> command(ctx, "party chat", false));

        List<UUID> ordered = new ArrayList<>(party.members());
        ordered.sort(Comparator.comparing((UUID u) -> !party.isLeader(u)));
        int i = 0;
        for (UUID u : ordered) {
            if (i >= MEMBER_SLOTS.length) break;
            Player m = Bukkit.getPlayer(u);
            boolean isLead = party.isLeader(u);
            List<String> lore = new ArrayList<>();
            String name;
            if (m != null) {
                name = m.getName();
                ClassDef c = services.classes().classOf(m);
                double ratio = services.stats().currentHp(m) / Math.max(1, services.stats().maxHp(m));
                lore.add("<gray>Lv.<white>" + services.data().get(m).level() + "</white> " + (c == null ? "<dark_gray>직업 없음"
                        : "<" + c.color() + ">" + c.name() + " <dark_gray>(" + ClassMenu.roleName(c.role()) + ")"));
                lore.add("<gray>HP <#ff5f6d>" + UiTheme.bar(ratio, 10, "▮", "▯") + " " + Math.round(ratio * 100) + "%");
                lore.add("<gray>해금 <white>지하 " + services.data().get(m).unlockedFloor() + "층");
                lore.add(services.dungeon().currentInstance(m).isPresent() ? "<#ffd36b>미궁 안" : "<gray>마을");
            } else {
                OfflinePlayer op = Bukkit.getOfflinePlayer(u);
                name = op.getName() == null ? "?" : op.getName();
                lore.add("<dark_gray>접속 안 함");
            }
            if (leader && !u.equals(p.getUniqueId())) {
                lore.add("");
                lore.add("<#ffd36b>우클릭: 파티장 위임");
                lore.add("<#ff6b6b>Shift + 클릭: 추방");
            }
            String title = (isLead ? "<#ffd36b>★ " : "<white>") + Text.escape(name);
            final String target = name;
            if (m != null) {
                set(MEMBER_SLOTS[i++], MainMenu.head(m, title, lore), ctx -> {
                    if (!leader || target.equals(ctx.player().getName())) return;
                    if (ctx.isShift()) command(ctx, "party kick " + target, false);
                    else if (ctx.isRight()) command(ctx, "party promote " + target, false);
                });
            } else {
                set(MEMBER_SLOTS[i++], Button.icon(Material.SKELETON_SKULL, title, lore), ctx -> {
                    if (leader && ctx.isShift()) command(ctx, "party kick " + target, false);
                });
            }
        }
        if (leader) {
            set(47, Button.icon(Material.PLAYER_HEAD, "<#7fd8ff><b>친구 초대</b>", List.of("<gray>접속 중인 플레이어에게 초대를 보냅니다.")),
                    ctx -> { click(ctx.player()); new InvitePicker(services).open(ctx.player()); });
            set(51, Button.icon(Material.TNT, "<#ff6b6b><b>파티 해산</b>", List.of("<gray>모든 파티원이 솔로가 됩니다.", "<dark_gray>Shift + 클릭으로 실행")),
                    ctx -> { if (ctx.isShift()) command(ctx, "party disband", false); else deny(ctx.player()); });
        }
        set(49, Button.icon(Material.ENDER_EYE, "<#7fd8ff><b>미궁 입장</b>", List.of("<gray>층 선택 · 파티 준비 상태")),
                ctx -> { click(ctx.player()); services.menus().openEntrance(ctx.player()); });
        set(53, Button.icon(Material.OAK_DOOR, "<#ff9a4d>파티 탈퇴", List.of("<dark_gray>Shift + 클릭으로 실행")),
                ctx -> { if (ctx.isShift()) command(ctx, "party leave", false); else deny(ctx.player()); });
        backButton(45, MainMenu::reopen);
    }

    /** 초대할 플레이어 고르기 (접속 중 · 내 파티원이 아닌 사람). */
    public static final class InvitePicker extends LabMenu {
        private int page;

        InvitePicker(Services services) { super(services, "players", 6, "<#7fd8ff>초대할 플레이어"); }

        @Override
        protected void draw(Player p) {
            List<Player> list = new ArrayList<>();
            for (Player o : Bukkit.getOnlinePlayers()) {
                if (o.equals(p) || services.party().sameParty(p, o)) continue;
                list.add(o);
            }
            list.sort(Comparator.comparing(Player::getName, String.CASE_INSENSITIVE_ORDER));
            int per = 28;
            int pages = Math.max(1, (list.size() + per - 1) / per);
            page = Math.min(page, pages - 1);
            int[] slots = new int[per];
            int k = 0;
            for (int r = 1; r <= 4; r++) for (int c = 1; c <= 7; c++) slots[k++] = r * 9 + c;
            for (int i = 0; i < per && page * per + i < list.size(); i++) {
                Player o = list.get(page * per + i);
                boolean inParty = services.party().partyOf(o).isPresent();
                ClassDef c = services.classes().classOf(o);
                List<String> lore = new ArrayList<>();
                lore.add("<gray>Lv.<white>" + services.data().get(o).level() + "</white> " + (c == null ? "<dark_gray>직업 없음" : "<" + c.color() + ">" + c.name()));
                lore.add(inParty ? "<#ff6b6b>다른 파티에 속해 있음" : "<#7fe07f>클릭: 초대 보내기");
                final String name = o.getName();
                set(slots[i], MainMenu.head(o, "<white>" + Text.escape(name), lore), ctx -> {
                    if (inParty) {
                        deny(ctx.player());
                        return;
                    }
                    command(ctx, "party invite " + name, false);
                });
            }
            if (list.isEmpty()) {
                deco(22, Button.icon(Material.BARRIER, "<gray>초대할 수 있는 플레이어가 없습니다", List.of()));
            }
            if (page > 0) set(48, UiTheme.prev(page, pages), ctx -> { page--; click(ctx.player()); refresh(); });
            if (page < pages - 1) set(50, UiTheme.next(page, pages), ctx -> { page++; click(ctx.player()); refresh(); });
            backButton(45, pl -> new PartyMenu(services).open(pl));
        }
    }
}
