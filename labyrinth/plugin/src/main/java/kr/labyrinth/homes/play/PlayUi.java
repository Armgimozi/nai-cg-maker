package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesResult;
import kr.labyrinth.homes.HomesService;
import kr.labyrinth.homes.HomesUi;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import kr.labyrinth.homes.PlotRole;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;

/**
 * 묶음 C 의 {@link HomesUi} 구현 (0.3.7): 관리인 메뉴 · 지도 · 초대 · 자재 · 맡긴 짐 · 시작 선물 · 표지판 · 자가 진단 줄.
 * 일(받기·비우기·초대 …)은 {@link HomesService} (묶음 B) 가 하고, 여기서는 묻고 보여 준다.
 */
public final class PlayUi implements HomesUi {

    /** 비우기 확인을 기다리는 시간 (/미궁 집 비우기 → 비우기 확인). */
    static final long VACATE_CONFIRM_MS = 30_000L;

    private final Services services;
    private final HomesService service;
    private final PlayWiring wiring;
    private final HomeTravel travel;
    private final StarterGift gift;
    private final Map<UUID, Long> vacateAsked = new ConcurrentHashMap<>();

    PlayUi(Services services, HomesService service, PlayWiring wiring) {
        this.services = services;
        this.service = service;
        this.wiring = wiring;
        this.travel = new HomeTravel(services, service);
        this.gift = new StarterGift(services, service);
    }

    Services services() { return services; }

    HomesService service() { return service; }

    HomeTravel travel() { return travel; }

    StarterGift gift() { return gift; }

    HousingCatalog catalog() { return wiring.catalog(); }

    // ── HomesUi ──────────────────────────────────────────────────────────

    @Override
    public void openEstate(Player p) {
        if (p == null) return;
        if (!service.enabled()) {
            Text.error(p, "이 서버에서는 집 기능을 쓰지 않습니다.");
            return;
        }
        new EstateMenu(this).open(p);
    }

    @Override
    public void openPlot(Player p, PlotGeom plot) {
        if (p == null) return;
        if (plot == null || !service.enabled()) {
            openEstate(p);
            return;
        }
        if (service.roleIn(p, plot) == PlotRole.OWNER) {
            openEstate(p);
            return;
        }
        new PlotMenu(this, plot).open(p);
    }

    @Override
    public void plotChanged(PlotGeom plot, PlotInfo info) {
        if (plot != null) PlotSigns.write(services.plugin(), mainWorld(), plot, info == null ? service.info(plot) : info);
        refreshOpenMenus();
    }

    @Override
    public void claimed(Player p, PlotGeom plot, boolean firstHome) {
        if (p == null || plot == null) return;
        // 받기 결과 글·메뉴 닫기가 끝난 뒤에 연다
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (p.isOnline() && gift.available(p, plot)) new StarterMenu(this, plot).open(p);
        }, 4L);
    }

    @Override
    public String selfTestLine() {
        int ex = 0;
        String catalog = "?", banned = "?", npc = "?", menus = "?", tp = "?";
        try {
            HousingCatalog c = catalog();
            catalog = String.valueOf(c.size());
            banned = String.valueOf(c.banned() + c.unknown());
        } catch (Throwable t) {
            ex++;
        }
        try {
            boolean def = false;
            for (NpcDef n : services.content().npcs().values()) if (HomesNames.ROLE_ESTATE.equals(n.role())) def = true;
            npc = def ? "ok" : "없음(메뉴는 열림)";
        } catch (Throwable t) {
            ex++;
        }
        try {
            menus = menusCheck();
        } catch (Throwable t) {
            ex++;
        }
        try {
            tp = travel.toggleLine(service.config().homeTeleport());
        } catch (Throwable t) {
            ex++;
        }
        return "[집 메뉴 자가 진단] 결과: 예외 " + ex + " · catalog=" + catalog + " · banned=" + banned + " · npc_def=" + npc + " · menus=" + menus
                + " · home_tp=" + tp;
    }

    /** 메뉴가 그릴 수 있나 (구역 집터가 모두 지도 칸을 가짐 · 자재 탭 9 이하·빈 탭 없음). */
    String menusCheck() {
        List<String> bad = new ArrayList<>();
        for (PlotGeom g : service.plots()) if (!g.custom() && !ClaimMap.DESIGN.containsKey(g.id())) bad.add("지도에 없는 집터 " + g.id());
        HousingCatalog c = catalog();
        if (c.tabs().size() > 9) bad.add("자재 탭 " + c.tabs().size());
        for (HousingCatalog.Tab t : c.tabs()) if (t.items().isEmpty()) bad.add("빈 탭 " + t.id());
        return bad.isEmpty() ? "ok" : "bad(" + String.join(", ", bad) + ")";
    }

    // ── 메뉴 열기 ─────────────────────────────────────────────────────────

    void openClaim(Player p) { new ClaimMenu(this).open(p); }

    void openShop(Player p) { new BuildShopMenu(this).open(p); }

    void openParcel(Player p) { new ParcelMenu(this).open(p); }

    void openTrust(Player p) { new TrustMenu(this).open(p); }

    void openStarter(Player p, PlotGeom home) {
        if (!gift.available(p, home)) {
            Text.error(p, "시작 선물은 이미 받았습니다.");
            return;
        }
        new StarterMenu(this, home).open(p);
    }

    /** 받기 전에 한 번 더 묻기 (plot null = 아무 데나). */
    void confirmClaim(Player p, PlotGeom plot) {
        HomesConfig c = service.config();
        List<String> lines = new ArrayList<>();
        lines.add("<gray>" + (c.claimCost() > 0 ? Text.num(c.claimCost()) + "G 를 냅니다." : "값은 받지 않습니다."));
        lines.add("<gray>한 사람에 한 집입니다.");
        lines.add("<gray>비우면 " + duration(c.reclaimCooldownMinutes()) + " 뒤에 다시 받을 수 있습니다.");
        String q = plot == null ? "빈 집 아무 데나 받을까요?" : object(plot.label()) + " 받을까요?";
        new ConfirmMenu(this, q, lines, "받기", pl -> claim(pl, plot == null ? null : plot.id()), this::openClaim).open(p);
    }

    void claim(Player p, String plotId) {
        HomesResult r = service.claim(p, plotId);
        send(p, r);
    }

    /** 비우기 한 번 더 묻기 (메뉴). */
    void confirmVacate(Player p) {
        PlotGeom home = service.homeOf(p.getUniqueId());
        if (home == null) {
            Text.error(p, "집이 없습니다.");
            return;
        }
        HomesConfig c = service.config();
        List<String> lines = new ArrayList<>();
        if (home.custom()) {
            lines.add("<gray>지은 것은 그대로 남고 집만 내놓습니다.");
        } else {
            lines.add("<gray>집 안 블록과 상자 속 물건은 맡긴 짐으로 갑니다.");
            lines.add("<gray>집터는 처음 모습으로 돌아갑니다.");
        }
        lines.add("<gray>골드는 돌려받지 않습니다.");
        lines.add("<gray>다시 받기는 " + duration(c.reclaimCooldownMinutes()) + " 뒤에 됩니다.");
        new ConfirmMenu(this, object(home.label()) + " 비울까요?", lines, "비우기", pl -> send(pl, service.vacate(pl, true)), this::openEstate).open(p);
    }

    /** /미궁 집 비우기 → 확인 안내를 받고 30초 안 /미궁 집 비우기 확인. */
    void vacateCommand(Player p, boolean confirm) {
        if (service.homeOf(p.getUniqueId()) == null) {
            Text.error(p, "집이 없습니다.");
            return;
        }
        long now = System.currentTimeMillis();
        if (!confirm) {
            vacateAsked.put(p.getUniqueId(), now);
            HomesResult r = service.vacate(p, false);
            String msg = r.message() == null || r.message().isBlank() ? "정말 비우려면 30초 안에 <white>/미궁 집 비우기 확인</white>" : r.message();
            if (r.ok()) send(p, r);
            else Text.send(p, "<gray>" + msg);
            return;
        }
        Long asked = vacateAsked.remove(p.getUniqueId());
        if (asked == null || now - asked > VACATE_CONFIRM_MS) {
            Text.error(p, "먼저 <white>/미궁 집 비우기</white> 로 안내를 보세요. 30초 안에 확인해야 합니다.");
            return;
        }
        send(p, service.vacate(p, true));
    }

    /** 채팅창에 명령을 넣어 주는 글 (채팅 입력 도구가 없어서). */
    void suggest(Player p, String command, String hint) {
        Text.send(p, "<gray>" + hint + " <click:suggest_command:'" + command + "'><#ffd36b><u>[여기를 눌러 쓰기]</u></#ffd36b></click>");
    }

    void send(Player p, HomesResult r) {
        if (r == null || r.message() == null || r.message().isBlank()) return;
        if (r.ok()) Text.send(p, "<gray>" + r.message());
        else Text.error(p, r.message());
    }

    // ── 도움 ─────────────────────────────────────────────────────────────

    int vacantCount() {
        int n = 0;
        for (PlotGeom g : service.plots()) if (!g.custom() && service.ownerOf(g) == null && !service.busy(g)) n++;
        return n;
    }

    int parcelCount(Player p) {
        try {
            int n = 0;
            for (ItemStack s : service.parcel(p.getUniqueId())) if (s != null && !s.isEmpty()) n++;
            return n;
        } catch (Throwable t) {
            return 0;
        }
    }

    boolean inDungeon(Player p) {
        try {
            return services.dungeon().isInLabyrinth(p) || services.dungeon().currentInstance(p).isPresent();
        } catch (Throwable t) {
            return false;
        }
    }

    static World mainWorld() { return Bukkit.getWorlds().isEmpty() ? null : Bukkit.getWorlds().get(0); }

    /** 열린 집 메뉴를 모두 새로 그림 (소유가 바뀜). */
    void refreshOpenMenus() {
        for (Player o : Bukkit.getOnlinePlayers()) {
            try {
                InventoryHolder h = o.getOpenInventory().getTopInventory().getHolder(false);
                if (h instanceof HomeMenu m && !(h instanceof ConfirmMenu)) m.refresh();
            } catch (Throwable t) {
                Log.warn("[집] 메뉴 새로 고침 실패: " + t.getMessage());
            }
        }
    }

    /** 모든 집 표지판을 지금 소유대로 (켤 때 한 번 — 꺼져 있는 동안 바뀐 것). */
    void refreshAllSigns() {
        World w = mainWorld();
        if (w == null || !service.active()) return;
        for (PlotGeom g : service.plots()) if (!g.custom()) PlotSigns.write(services.plugin(), w, g, service.info(g));
    }

    /** 분 → "24시간" · "30분" · "1시간 30분". */
    static String duration(int minutes) {
        if (minutes <= 0) return "바로";
        int h = minutes / 60, m = minutes % 60;
        if (h == 0) return m + "분";
        return m == 0 ? h + "시간" : h + "시간 " + m + "분";
    }

    /** 목적격 조사 붙이기: "3번지" → "3번지를", "c1" → "c1을". */
    static String object(String word) {
        if (word == null || word.isEmpty()) return "";
        return word + (hasFinal(word) ? "을" : "를");
    }

    /** 끝 글자에 받침이 있나 (한글 · 숫자 읽는 소리 · 영문은 대략). */
    static boolean hasFinal(String word) {
        char c = word.charAt(word.length() - 1);
        if (c >= 0xAC00 && c <= 0xD7A3) return (c - 0xAC00) % 28 != 0;
        if (c >= '0' && c <= '9') return "013678".indexOf(c) >= 0; // 영·일·삼·육·칠·팔 받침, 이·사·오·구 없음
        return "lmnrLMNR".indexOf(c) >= 0;
    }
}
