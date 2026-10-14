package kr.labyrinth.ui.menus;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.party.Party;
import kr.labyrinth.titles.AchievementRules;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.UiTheme;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;

/**
 * /대전 — 파티 대 파티 대전 메뉴 (GDD §18): 내 전적·레이팅·등급, 다른 파티에 도전, 대기열 참가/취소, 받은 도전 수락/거절,
 * 레이팅 순위. 동작은 대전 명령(pvp 담당: {@code /pvp 도전|수락|거절|대기열 참가|대기열 취소})으로 위임한다.
 * <p>
 * 전적 데이터: PlayerData ext {@code pvp.rating · pvp.wins · pvp.losses · pvp.streak · pvp.best_streak · pvp.best_rating}
 * (pvp 담당이 기록) — 없으면 칭호 카운터(PvpMatchEndEvent 로 titles 가 센 값)로 대신 보여 준다.
 */
public final class PvpMenu extends LabMenu {

    public PvpMenu(Services services) {
        super(services, "pvp", 6, "<#ff6b6b>파티 대전");
    }

    /** 전적 한 사람분. */
    record PvpRecord(String name, int rating, long wins, long losses, long streak, long bestStreak, int bestRating) {}

    static long ext(PlayerData d, String key, long fallback) {
        Object v = d.ext().get(key);
        return v instanceof Number n ? n.longValue() : fallback;
    }

    static PvpRecord record(PlayerData d) {
        String P = AchievementRules.P;
        int rating = (int) ext(d, "pvp.rating", d.counter(P + "pvp_rating") > 0 ? d.counter(P + "pvp_rating") : 1000);
        return new PvpRecord(d.name(), rating,
                ext(d, "pvp.wins", d.counter(P + "pvp_wins")),
                ext(d, "pvp.losses", d.counter(P + "pvp_losses")),
                ext(d, "pvp.streak", d.counter(P + "pvp_streak")),
                ext(d, "pvp.best_streak", d.counter(P + "pvp_best_streak")),
                (int) ext(d, "pvp.best_rating", Math.max(rating, d.counter(P + "pvp_best_rating"))));
    }

    /** 등급 (GDD §18.4 기본값). */
    static String tier(int rating) {
        if (rating >= 1800) return "<gradient:#6a3dff:#ff4dd2>심연</gradient>";
        if (rating >= 1600) return "<#9ff0ff>수정";
        if (rating >= 1450) return "<#ffd36b>황금";
        if (rating >= 1300) return "<#dfe6f0>은빛";
        if (rating >= 1150) return "<#d08a4f>청동";
        return "<gray>견습 투사";
    }

    @Override
    protected void draw(Player p) {
        PvpRecord r = record(services.data().get(p));
        long games = r.wins() + r.losses();
        List<String> me = new ArrayList<>();
        me.add("<gray>등급 " + tier(r.rating()) + " <dark_gray>· <gray>레이팅 <white>" + r.rating());
        me.add("<gray>전적 <#7fe07f>" + r.wins() + "승</#7fe07f> <#ff6b6b>" + r.losses() + "패</#ff6b6b>"
                + (games > 0 ? " <dark_gray>(승률 " + Math.round(100.0 * r.wins() / games) + "%)" : ""));
        me.add("<gray>연승 <white>" + r.streak() + " <dark_gray>· <gray>최고 연승 <white>" + r.bestStreak());
        me.add("<gray>최고 레이팅 <white>" + r.bestRating());
        me.add("");
        me.add("<dark_gray>보상은 명예(칭호·등급)뿐 — 장비·골드 손실 없음");
        deco(4, MainMenu.head(p, "<white><b>" + Text.escape(p.getName()) + "</b> <gray>의 대전 기록", me));

        Party party = services.party().partyOf(p).orElse(null);
        boolean leader = party == null || party.isLeader(p.getUniqueId());
        String who = leader ? "" : "<#ffd36b>파티장만 할 수 있습니다.";
        set(20, model("conqueror_emblem", Material.IRON_SWORD, "<#ff6b6b><b>파티에 도전</b>",
                List.of("<gray>다른 파티의 파티장에게 대전을 신청합니다.", "<gray>상대가 60초 안에 수락하면 시작합니다.", who.isEmpty() ? "<#ffd36b>클릭: 상대 고르기" : who)),
                ctx -> { click(ctx.player()); new ChallengePicker(services).open(ctx.player()); });
        set(22, Button.icon(Material.CLOCK, "<#7fd8ff><b>대기열 참가</b>",
                List.of("<gray>비슷한 레이팅의 파티와 자동으로 맞붙습니다.", "<gray>(팀 평균 ±150 → 20초마다 넓어짐)", who.isEmpty() ? "<#ffd36b>클릭: 참가" : who)),
                ctx -> command(ctx, "pvp 대기열 참가", false));
        set(23, Button.icon(Material.BARRIER, "<#ff9a4d>대기열 취소", List.of()),
                ctx -> command(ctx, "pvp 대기열 취소", false));
        set(24, Button.icon(Material.LIME_DYE, "<#7fe07f><b>받은 도전 수락</b>", List.of("<gray>가장 최근에 받은 도전을 수락합니다.")),
                ctx -> command(ctx, "pvp 수락", true));
        set(25, Button.icon(Material.RED_DYE, "<#ff6b6b>받은 도전 거절", List.of()),
                ctx -> command(ctx, "pvp 거절", false));
        set(31, Button.icon(Material.GOLDEN_HELMET, "<#ffd36b><b>레이팅 순위</b>", List.of("<gray>서버 상위 10명")),
                ctx -> { click(ctx.player()); new RankingMenu(services).open(ctx.player()); });
        List<String> rules = new ArrayList<>();
        rules.add("<gray>best-of-3 라운드 · 준비 10초 · 라운드 180초");
        rules.add("<gray>플레이어 간 피해 ×0.6 · 치유 ×0.7 · 제어기 ×0.6");
        rules.add("<gray>소모품·칭호 보너스 사용 불가, 무기 스킬 사용 가능");
        rules.add("<gray>180초가 지나면 서든데스 — 안전 지대가 줄어듭니다");
        deco(40, Button.icon(Material.BOOK, "<#c9a2ff>대전 규칙", rules));
        backButton(45, MainMenu::reopen);
    }

    /** 도전할 상대 파티 고르기: 다른 파티의 파티장(또는 솔로 플레이어). */
    public static final class ChallengePicker extends LabMenu {
        ChallengePicker(Services services) { super(services, "players", 6, "<#ff6b6b>도전할 상대"); }

        @Override
        protected void draw(Player p) {
            List<Player> leaders = new ArrayList<>();
            for (Player o : Bukkit.getOnlinePlayers()) {
                if (o.equals(p) || services.party().sameParty(p, o)) continue;
                Player lead = services.party().leader(o);
                if (lead != null && !lead.equals(o)) continue;
                leaders.add(o);
            }
            leaders.sort(Comparator.comparing(Player::getName, String.CASE_INSENSITIVE_ORDER));
            int k = 0;
            for (int r = 1; r <= 4 && k < leaders.size(); r++) {
                for (int c = 1; c <= 7 && k < leaders.size(); c++) {
                    Player o = leaders.get(k++);
                    int size = services.party().size(o);
                    PvpRecord rec = record(services.data().get(o));
                    List<String> lore = new ArrayList<>();
                    lore.add("<gray>" + (size > 1 ? "파티 " + size + "명" : "솔로") + " <dark_gray>· <gray>등급 " + tier(rec.rating()) + " <white>" + rec.rating());
                    lore.add("<gray>전적 " + rec.wins() + "승 " + rec.losses() + "패");
                    lore.add(services.dungeon().currentInstance(o).isPresent() ? "<#ff6b6b>미궁 공략 중" : "<#ffd36b>클릭: 도전 신청");
                    final String name = o.getName();
                    set(r * 9 + c, MainMenu.head(o, "<white>" + Text.escape(name), lore), ctx -> command(ctx, "pvp 도전 " + name, true));
                }
            }
            if (leaders.isEmpty()) deco(22, Button.icon(Material.BARRIER, "<gray>도전할 수 있는 파티가 없습니다", List.of()));
            backButton(45, pl -> new PvpMenu(services).open(pl));
        }
    }

    /** 레이팅 상위 10명 (접속 안 한 플레이어도 데이터 파일에서). */
    public static final class RankingMenu extends LabMenu {
        private static final int[] SLOTS = {13, 21, 22, 23, 29, 30, 31, 32, 33, 40};

        RankingMenu(Services services) { super(services, "pvp_ranking", 6, "<#ffd36b>대전 순위"); }

        @Override
        protected void draw(Player p) {
            List<PvpRecord> all = new ArrayList<>();
            List<UUID> seen = new ArrayList<>();
            for (Player o : Bukkit.getOnlinePlayers()) {
                all.add(record(services.data().get(o)));
                seen.add(o.getUniqueId());
            }
            int scanned = 0;
            for (OfflinePlayer op : Bukkit.getOfflinePlayers()) {
                if (seen.contains(op.getUniqueId()) || scanned++ > 200) continue;
                try {
                    PlayerData d = services.data().getIfLoaded(op.getUniqueId());
                    if (d == null) d = services.data().loadOffline(op);
                    if (d != null) all.add(record(d));
                } catch (Throwable ignored) {
                    // 손상된 파일은 건너뜀
                }
            }
            all.removeIf(r -> r.wins() + r.losses() == 0);
            all.sort(Comparator.comparingInt(PvpRecord::rating).reversed().thenComparing(PvpRecord::wins, Comparator.reverseOrder()));
            Material[] medals = {Material.GOLD_BLOCK, Material.IRON_BLOCK, Material.COPPER_BLOCK};
            for (int i = 0; i < SLOTS.length && i < all.size(); i++) {
                PvpRecord r = all.get(i);
                List<String> lore = new ArrayList<>();
                lore.add("<gray>등급 " + tier(r.rating()) + " <white>" + r.rating());
                lore.add("<gray>" + r.wins() + "승 " + r.losses() + "패 · 최고 연승 " + r.bestStreak());
                deco(SLOTS[i], Button.icon(i < 3 ? medals[i] : Material.PAPER, "<#ffd36b><b>" + (i + 1) + "위</b> <white>"
                        + Text.escape(r.name() == null ? "?" : r.name()), lore));
            }
            if (all.isEmpty()) deco(22, Button.icon(Material.BARRIER, "<gray>아직 대전 기록이 없습니다", List.of("<gray>첫 승리의 주인공이 되어 보세요!")));
            backButton(45, pl -> new PvpMenu(services).open(pl));
        }
    }
}
