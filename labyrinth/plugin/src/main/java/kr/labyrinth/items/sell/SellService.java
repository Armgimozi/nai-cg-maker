package kr.labyrinth.items.sell;

import com.mojang.brigadier.Command;
import io.papermc.paper.command.brigadier.Commands;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryAction;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 떠돌이 상인 핀에게 물건 팔기 — 판매 창({@link SellMenu}) 열기·명령·안전장치. 값은 {@link SellPrices} (config.yml {@code sell:}).
 * <p>
 * 명령: {@code /미궁 판매} ({@code /lab sell}) — 미궁 공략 중(미궁 월드 포함)에는 열리지 않는다. 상점 창의 [물건 팔기] 도 같은 창.
 * <p>
 * 올려 둔 물건이 사라지거나 늘어나지 않게 — 돌려줄 때는 언제나 {@link #giveOrKeep}: 가방에 넣고, 넘친 것은 발밑에 떨구지 않고
 * PlayerData ext {@value #PENDING} 에 맡긴다 (닫힌 까닭이 무엇이든 — 텔레포트·다른 플러그인의 창 닫기 뒤 이동처럼 그 자리를 떠나도
 * 두고 간 물건이 5분 뒤 사라지거나 남이 줍는 일이 없게).
 * <ul>
 *   <li>창 닫힘(직접 닫기·다른 창 열기·플러그인 닫기·사용 불가 등) → {@link SellMenu#onClose} → 바구니를 닫고 돌려준다</li>
 *   <li>접속 종료·추방 → 닫힘(DISCONNECT)·종료 이벤트에서 먼저(LOWEST, 플레이어 저장 전) 돌려준다</li>
 *   <li>죽음 → 최종 keepInventory 를 본 뒤(MONITOR): 지니면 가방으로(넘치면 맡김), 아니면 다른 소지품처럼 그 자리에 떨군다</li>
 *   <li>월드 이동 → 아직 열려 있으면 닫고 돌려준다 (Paper 26.3 은 텔레포트로 창을 닫지 않는다 — Reason.TELEPORT 는 더 쓰이지 않음).
 *       서버 종료·플러그인 끄기 → {@link #stop} 이 모두 돌려주고 창을 닫는다</li>
 *   <li>맡긴 물건은 접속할 때 · 미궁 밖 월드로 돌아왔을 때 · 판매 창을 열 때 가방에 들어가는 만큼 돌려준다 (넘치는 것은 계속 맡김)</li>
 *   <li>창이 열린 동안 위 칸 돌려받기도 가방에 들어가는 만큼만 (나머지는 칸에 그대로)</li>
 *   <li>드래그는 위·아래 모두 취소, 쉬프트+클릭은 여기서 받아 '묶음째 올리기' 로만 처리</li>
 * </ul>
 * 바구니는 닫힌 뒤 아무것도 받지 않고, 판매는 바구니를 먼저 비운 다음 합계를 한 번만 더한다 ({@link SellBasket}).
 */
public final class SellService implements Listener {

    private static volatile SellService active;

    /** 돌려줄 때 가방이 꽉 차 못 넣은 물건 (PlayerData ext — Base64 직렬화 목록). 나중에 들어가는 만큼 돌려준다. */
    static final String PENDING = "sell.pending";

    /** 켜져 있는 판매 서비스 (mobs 모듈이 켜기 전·끈 뒤에는 null). */
    public static SellService get() { return active; }

    private final Services services;
    private final Map<UUID, SellMenu> open = new HashMap<>();

    public SellService(Services services) { this.services = services; }

    public void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        registerCommands();
        active = this;
        checkSmelt();
    }

    /** 켤 때 한 번 (경고만): sell.mine 을 고쳐 어떤 등급이든 녹여 팔면 이득이 되면 로그에 알린다 (제련으로 골드가 생기지 않게). */
    private void checkSmelt() {
        try {
            var c = services.content();
            Map<Integer, int[]> smelt = new HashMap<>();
            for (kr.labyrinth.content.RecipeDef r : c.recipes().values()) {
                kr.labyrinth.content.ItemDef d = c.item(r.result());
                if (d == null || !d.isMineMaterial() || d.mineKind() != kr.labyrinth.content.MineKind.INGOT) continue;
                int ores = r.materials().values().stream().mapToInt(Integer::intValue).sum();
                smelt.merge(d.mineLevel(), new int[] {ores, r.gold()}, (x, y) -> x[1] <= y[1] ? x : y);
            }
            for (String w : config().mine().smeltWarnings(smelt)) Log.warn("[판매] " + w);
        } catch (Throwable t) {
            Log.warn("[판매] 녹여 팔기 검사를 건너뜀: " + t.getMessage());
        }
    }

    /** 플러그인 끄기·서버 종료: 열린 판매 창을 전부 돌려주고 닫는다. */
    public void stop() {
        if (active == this) active = null;
        for (Map.Entry<UUID, SellMenu> e : new ArrayList<>(open.entrySet())) {
            Player p = Bukkit.getPlayer(e.getKey());
            SellMenu m = e.getValue();
            List<ItemStack> items = m.closeBasket();
            if (p != null) {
                giveOrKeep(p, items, false); // 서버가 곧 꺼진다 — 발밑에 떨구지 않고 넘치면 맡김
                if (p.getOpenInventory().getTopInventory().getHolder(false) == m) p.closeInventory();
            } else if (!items.isEmpty()) {
                Log.warn("[판매] 오프라인 플레이어 " + e.getKey() + " 의 판매 대기 물건 " + items.size() + "묶음을 돌려주지 못했습니다.");
            }
        }
        open.clear();
        HandlerList.unregisterAll(this);
    }

    private void registerCommands() {
        for (String n : new String[] {"sell", "판매"}) {
            services.commands().addSubcommand("lab", Commands.literal(n).executes(ctx -> {
                CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), this::open));
                return Command.SINGLE_SUCCESS;
            }));
        }
    }

    // ── 열기 ─────────────────────────────────────────────────────────────

    /** 미궁 공략 중이거나 미궁 월드에 있으면 팔 수 없다. */
    public boolean blocked(Player p) {
        try {
            return services.dungeon().currentInstance(p).isPresent() || services.dungeon().isInLabyrinth(p);
        } catch (Throwable t) {
            return true;
        }
    }

    /** npcs.yml 의 첫 상인(role: merchant, shop 있음). 없으면 null. */
    public NpcDef merchant() {
        for (NpcDef n : services.content().npcs().values()) {
            if ("merchant".equals(n.role()) && n.shop() != null && !n.shop().isEmpty()) return n;
        }
        return null;
    }

    /** /미궁 판매 — 첫 상인 기준. */
    public void open(Player p) { open(p, merchant()); }

    /** 판매 창 열기 (npc = [사러 가기] 가 돌아갈 상인, null 이면 그 버튼 없음). */
    public void open(Player p, NpcDef npc) {
        if (active != this) { // 켜다 실패했거나 꺼진 서비스 (안전장치 리스너가 없음) — 남은 명령이 불러도 열지 않는다
            Text.error(p, SellPrices.Block.DISABLED.message());
            return;
        }
        if (blocked(p)) {
            Text.error(p, "미궁 안에서는 물건을 팔 수 없습니다. 마을로 돌아온 뒤 <white>/미궁 판매</white>");
            return;
        }
        deliverPending(p, true); // 맡아 둔 물건이 있으면 먼저 (판매를 꺼 두었어도 돌려준다)
        SellPrices prices = prices();
        if (!prices.config().enabled()) {
            Text.error(p, SellPrices.Block.DISABLED.message());
            return;
        }
        new SellMenu(services, this, npc, prices).open(p);
    }

    /** config.yml {@code sell:} ({@code sell: false} = 끔 — 다른 섹션과 같은 관례). */
    public SellPrices.Config config() {
        return SellPrices.Config.of(services.plugin().getConfig().get("sell"));
    }

    /** 판매가 켜져 있나 (상점 창 [물건 팔기] 버튼 모양). */
    public boolean enabled() { return config().enabled(); }

    /** 지금 설정·콘텐츠로 값 계산기 (창을 열 때마다 새로 — /labadmin reload 반영). */
    public SellPrices prices() {
        SellPrices.Config c = config();
        List<String> extra = new ArrayList<>();
        try {
            extra.add(services.settings().classChange().item());
        } catch (Throwable ignored) {
            // 설정이 없으면 기본(class_change_scroll)만
        }
        return new SellPrices(c, SellPrices.buyPrices(services.content().npcs().values()), extra);
    }

    // ── 세션 ─────────────────────────────────────────────────────────────

    void track(Player p, SellMenu m) {
        SellMenu prev = open.put(p.getUniqueId(), m);
        if (prev != null && prev != m) giveOrKeep(p, prev.closeBasket(), true);
    }

    /** 창이 닫혔다 (어떤 까닭이든) → 돌려주고(넘치면 맡김) 세션 정리. 두 번째부터는 바구니가 비어 아무 일 없음. */
    void closed(Player p, SellMenu m) {
        giveOrKeep(p, m.closeBasket(), true);
        open.remove(p.getUniqueId(), m);
    }

    /**
     * 돌려주기: 가방으로, 넘치면 발밑 대신 PlayerData 에 맡긴다 (떠나는 자리에 떨군 물건은 5분 뒤 사라지고 남이 주울 수 있으므로).
     * @param notify 접속해 있는 플레이어에게 맡겼다고 알릴까 (접속 종료·서버 종료는 false)
     */
    void giveOrKeep(Player p, List<ItemStack> items, boolean notify) {
        List<String> keep = addOrEncode(p, items);
        if (keep.isEmpty()) return;
        PlayerData d = services.data().get(p);
        pushPending(d.ext(), keep);
        d.markDirty();
        Log.info("[판매] " + p.getName() + " 의 가방이 꽉 차 판매 대기 물건 " + keep.size() + "묶음을 맡아 둡니다.");
        if (notify && p.isOnline()) {
            Text.send(p, "<gray>가방이 꽉 차 판매 창에 올려 두었던 물건 <white>" + keep.size() + "묶음</white>을 상인이 맡아 둡니다. "
                    + "가방을 비운 뒤 마을에서 <white>/미궁 판매</white> 를 열면 돌려받습니다.");
        }
    }

    /** 가방에 넣고, 들어가지 않은 것은 직렬화해 돌려준다 (직렬화가 안 되는 물건만 어쩔 수 없이 발밑에 — 주인만 줍게). */
    private List<String> addOrEncode(Player p, List<ItemStack> items) {
        List<String> keep = new ArrayList<>();
        for (ItemStack s : items) {
            if (s == null || s.isEmpty()) continue;
            for (ItemStack left : p.getInventory().addItem(s).values()) {
                try {
                    keep.add(Base64.getEncoder().encodeToString(left.serializeAsBytes()));
                } catch (Throwable t) {
                    Log.error("[판매] 돌려줄 물건을 저장하지 못해 발밑에 떨굽니다: " + p.getName(), t);
                    p.getWorld().dropItem(p.getLocation(), left, it -> it.setOwner(p.getUniqueId()));
                }
            }
        }
        return keep;
    }

    /**
     * 맡아 둔 물건 돌려주기 — 미궁 밖에서만, 가방에 들어가는 만큼만 (넘치는 것과 풀지 못한 줄은 계속 맡아 둔다. 떨구지 않음).
     * @param announceKept 아직 남은 것이 있으면 알릴까 (조용한 재시도는 false)
     */
    void deliverPending(Player p, boolean announceKept) {
        if (p == null || !p.isOnline() || blocked(p)) return;
        PlayerData d = services.data().get(p);
        if (!d.ext().containsKey(PENDING)) return;
        List<String> list = takePending(d.ext());
        List<String> keep = new ArrayList<>();
        List<ItemStack> items = new ArrayList<>();
        for (String b64 : list) {
            try {
                items.add(ItemStack.deserializeBytes(Base64.getDecoder().decode(b64)));
            } catch (Throwable t) {
                Log.error("[판매] 맡아 둔 물건을 풀지 못했습니다 (" + p.getName() + ") — ext " + PENDING + " 에 남겨 둡니다", t);
                keep.add(b64);
            }
        }
        List<String> left = addOrEncode(p, items);
        keep.addAll(left);
        pushPending(d.ext(), keep);
        d.markDirty();
        int back = items.size() - left.size();
        if (back > 0) Text.send(p, "<gray>판매 창에 올려 두었던 물건 <white>" + back + "묶음</white>을 돌려받았습니다.");
        if (!keep.isEmpty() && (announceKept || back > 0)) {
            Text.send(p, "<gray>가방에 자리가 없어 <white>" + keep.size() + "묶음</white>은 상인이 계속 맡아 둡니다. "
                    + "가방을 비운 뒤 <white>/미궁 판매</white>");
        }
    }

    /** 잠시 뒤 맡긴 물건 돌려주기 (접속·월드 이동 직후 — 데이터·공략 상태가 자리 잡은 뒤). */
    private void deliverLater(Player p, long ticks, boolean announceKept) {
        if (!services.data().get(p).ext().containsKey(PENDING)) return;
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (active == this) deliverPending(p, announceKept);
        }, ticks);
    }

    /** ext 의 맡긴 물건 목록에 덧붙인다 (순수). */
    static void pushPending(Map<String, Object> ext, List<String> encoded) {
        if (encoded == null || encoded.isEmpty()) return;
        List<String> all = new ArrayList<>(readPending(ext));
        all.addAll(encoded);
        ext.put(PENDING, all);
    }

    /** ext 의 맡긴 물건 목록을 꺼내고 지운다 (순수). 없으면 빈 목록. */
    static List<String> takePending(Map<String, Object> ext) {
        List<String> out = readPending(ext);
        ext.remove(PENDING);
        return out;
    }

    private static List<String> readPending(Map<String, Object> ext) {
        List<String> out = new ArrayList<>();
        if (ext.get(PENDING) instanceof List<?> l) {
            for (Object o : l) if (o != null && !String.valueOf(o).isBlank()) out.add(String.valueOf(o));
        }
        return out;
    }

    // ── 안전장치 ─────────────────────────────────────────────────────────

    /** 접속이 끊겨 창이 닫힘 (종료 이벤트보다 먼저 온다) — MenuListener 의 일반 닫기보다 먼저, 알림 없이. */
    @EventHandler(priority = EventPriority.LOWEST)
    public void onDisconnectClose(InventoryCloseEvent e) {
        if (e.getReason() != InventoryCloseEvent.Reason.DISCONNECT) return;
        if (!(e.getInventory().getHolder(false) instanceof SellMenu m) || !(e.getPlayer() instanceof Player p)) return;
        giveOrKeep(p, m.closeBasket(), false);
        open.remove(p.getUniqueId(), m);
    }

    /** 접속 종료·추방 (닫힘 이벤트를 못 받았어도). 데이터 저장(MONITOR)보다 먼저. */
    @EventHandler(priority = EventPriority.LOWEST)
    public void onQuit(PlayerQuitEvent e) {
        SellMenu m = open.remove(e.getPlayer().getUniqueId());
        if (m != null) giveOrKeep(e.getPlayer(), m.closeBasket(), false);
    }

    /** 지난번에 맡아 둔 물건 돌려주기 (데이터는 LOWEST 에서 읽힘 — 1초 뒤 안전하게). */
    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        deliverLater(e.getPlayer(), 20L, true);
    }

    /** 최종 keepInventory 를 본다 (DeathKeep 은 HIGHEST). 드롭 목록은 모든 처리기가 끝난 뒤에 떨어진다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent e) {
        Player p = e.getPlayer();
        SellMenu m = open.remove(p.getUniqueId());
        if (m == null) return;
        List<ItemStack> items = m.closeBasket();
        if (items.isEmpty()) return;
        if (e.getKeepInventory()) {
            giveOrKeep(p, items, true); // 소지품을 지니는 죽음 — 넘친 것도 남이 줍는 드롭으로 만들지 않고 맡김
        } else {
            e.getDrops().addAll(items); // 다른 소지품과 똑같이 그 자리에
        }
    }

    /** 월드 이동: 아직 열려 있으면(가방 유지 텔레포트 등) 닫고 돌려준다(넘치면 맡김). 미궁 밖으로 돌아왔으면 맡긴 물건도. */
    @EventHandler
    public void onWorldChange(PlayerChangedWorldEvent e) {
        Player p = e.getPlayer();
        SellMenu m = open.remove(p.getUniqueId());
        if (m != null) {
            giveOrKeep(p, m.closeBasket(), true);
            if (p.getOpenInventory().getTopInventory().getHolder(false) == m) p.closeInventory();
        }
        deliverLater(p, 20L, true); // 공략이 끝나 마을로 돌아온 경우 — 돌려줄 때 미궁 밖인지 다시 본다
    }

    /** 쉬프트+클릭(가방 → 위)은 MenuListener 가 취소만 하고 넘기지 않는다 → 여기서 '묶음째 올리기' 로. */
    @EventHandler(priority = EventPriority.NORMAL)
    public void onShiftClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder(false) instanceof SellMenu m)) return;
        e.setCancelled(true);
        if (e.getAction() != InventoryAction.MOVE_TO_OTHER_INVENTORY) return;
        if (!(e.getWhoClicked() instanceof Player p) || !(e.getClickedInventory() instanceof PlayerInventory)) return;
        m.shiftStage(p, e.getSlot());
    }

    /** 판매 창이 열려 있으면 어느 쪽 드래그든 취소 (커서 물건을 칸에 흘리는 길 차단). */
    @EventHandler(priority = EventPriority.LOWEST)
    public void onDrag(InventoryDragEvent e) {
        if (e.getView().getTopInventory().getHolder(false) instanceof SellMenu) e.setCancelled(true);
    }
}
