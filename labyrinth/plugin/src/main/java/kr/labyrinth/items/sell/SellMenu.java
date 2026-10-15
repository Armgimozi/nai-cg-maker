package kr.labyrinth.items.sell;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.ItemLore;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.NpcDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.items.enhance.Enhancement;
import kr.labyrinth.mobs.npc.ShopMenu;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.ClickContext;
import kr.labyrinth.ui.menus.LabMenu;
import net.kyori.adventure.text.Component;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/**
 * 떠돌이 상인 핀 · 판매 창 (6줄). 아래 내 가방에서 클릭한 물건이 위 판매 칸(28칸)으로 올라가고, 위 칸을 누르면 돌려받는다.
 * [판매] 로 한꺼번에 팔고 골드를 한 번 받는다. 영웅 이상·강화 장비가 섞여 있으면 [판매] 를 한 번 더 눌러야 한다.
 * <p>
 * 아이템 안전: 올린 진짜 묶음은 {@link SellBasket} 만 들고 있고, 위 칸에는 PDC 를 지운 그림용 사본만 놓는다(모든 클릭은
 * MenuListener 가 취소). 창이 닫히면(다른 창 열기·접속 종료·추방·텔레포트·죽음·월드 이동·서버 종료 포함) {@link SellService} 가
 * 바구니를 비워 가방으로 돌려준다 — 가방이 꽉 차 못 넣은 것은 발밑에 떨구지 않고 상인이 맡아 두었다가 나중에 돌려준다.
 * [판매] 는 좌·우클릭만 누름으로 치고, 두 번째 누름은 첫 누름 뒤 {@link #CONFIRM_MIN_MS} 가 지나야 센다.
 * <ul>
 *   <li>가방 클릭: 좌클릭·쉬프트+클릭 = 묶음째, 우클릭 = 1개. 숫자 키·버리기·더블클릭·드래그는 아무 일도 하지 않는다.</li>
 *   <li>가방 쪽은 보관함 0~35칸만 (입고 있는 방어구·보조손은 보이지 않으니 올릴 수 없다).</li>
 * </ul>
 */
public final class SellMenu extends LabMenu {

    /** 판매 칸: 2~5줄 안쪽 7칸 × 4줄. */
    static final int[] STAGE = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34,
            37, 38, 39, 40, 41, 42, 43};
    static final int S_INFO = 4, S_BUY = 45, S_TABLE = 46, S_BULK = 48, S_SELL = 49, S_RETURN = 50, S_CLOSE = 53;
    /** 첫 [판매] 뒤 이 시간이 지나야 두 번째 누름을 확인으로 센다 (빠른 연타·더블클릭으로 건너뛰기 방지). */
    static final long CONFIRM_MIN_MS = 600;
    /** 첫 [판매] 뒤 이 시간 안에 한 번 더 눌러야 판다. */
    static final long CONFIRM_MS = 8_000;

    /** ItemStack 묶음 다루기. */
    static final SellBasket.Stacks<ItemStack> STACKS = new SellBasket.Stacks<>() {
        @Override
        public int amount(ItemStack s) { return s == null ? 0 : s.getAmount(); }

        @Override
        public ItemStack withAmount(ItemStack s, int amount) { return s.asQuantity(amount); }

        @Override
        public boolean similar(ItemStack a, ItemStack b) { return a != null && a.isSimilar(b); }

        @Override
        public int maxStack(ItemStack s) { return s.getMaxStackSize(); }
    };

    private final SellService service;
    private final NpcDef npc;
    private final SellPrices prices;
    private final SellBasket<ItemStack> basket = new SellBasket<>(STACKS, STAGE.length, CONFIRM_MIN_MS, CONFIRM_MS);

    SellMenu(Services services, SellService service, NpcDef npc, SellPrices prices) {
        super(services, "merchant", 6, "<dark_gray>" + (npc == null ? "떠돌이 상인" : Text.strip(npc.name())) + " · 판매");
        this.service = service;
        this.npc = npc;
        this.prices = prices;
    }

    @Override
    protected boolean allowBottomClicks() { return true; }

    /** 이 창이 지금 이 플레이어 화면에 열려 있고 아직 닫히지 않았나 (늦게 온 클릭·예약 작업 거르기). */
    boolean live(Player p) {
        return !basket.closed() && p != null && p.isOnline() && p.getOpenInventory().getTopInventory().getHolder(false) == this;
    }

    // ── 그리기 ───────────────────────────────────────────────────────────

    @Override
    protected void draw(Player viewer) {
        PlayerData d = services.data().get(viewer);
        long now = System.currentTimeMillis();
        long total = basket.total();
        List<String> info = new ArrayList<>();
        info.add("<yellow>" + Text.num(d.gold()) + " G");
        if (total > 0) info.add("<gray>판매 후: <gold>" + Text.num(d.gold() + total) + " G");
        info.add("");
        info.add("<gray>아래 가방 클릭: <white>묶음째 올리기");
        info.add("<gray>우클릭: <white>1개만 올리기");
        info.add("<gray>위 칸 클릭: <white>가방으로 돌려받기");
        info.add("<dark_gray>창을 닫으면 올린 물건은 모두 돌아옵니다.");
        deco(S_INFO, Button.icon(Material.GOLD_INGOT, "<gold><b>보유 골드</b></gold>", info));

        List<SellBasket.Entry<ItemStack>> entries = basket.entries();
        for (int i = 0; i < entries.size() && i < STAGE.length; i++) {
            final int idx = i;
            set(STAGE[i], display(entries.get(i)), ctx -> unstage(ctx, idx));
        }

        if (npc != null) {
            set(S_BUY, Button.icon(Material.EMERALD, "<green>◀ 사러 가기",
                    List.of("<gray>" + Text.strip(npc.name()) + " 의 상점(구매)으로", "<dark_gray>올린 물건은 가방으로 돌아옵니다.")), ctx -> {
                click(ctx.player());
                new ShopMenu(services, npc).open(ctx.player());
            });
        }
        deco(S_TABLE, Button.icon(Material.BOOK, "<#e8d9b0><b>판매 가격표</b>", prices.tableLore()));
        set(S_BULK, Button.icon(Material.HOPPER, "<#7fd8ff>재료 모두 올리기",
                List.of("<gray>가방의 미궁 재료 중", "<gray>" + prices.config().confirmRarity().displayName() + " 아래 등급을 전부 올립니다.",
                        "<dark_gray>(보스 핵 같은 귀한 재료는 직접 골라 올리세요)")), this::bulk);
        set(S_SELL, sellButton(now), this::sell);
        set(S_RETURN, Button.icon(Material.CHEST, "<gray>모두 돌려받기",
                List.of("<dark_gray>올린 물건을 전부 가방으로")), ctx -> {
            Player p = ctx.player();
            if (!live(p)) return;
            if (!returnAll(p)) services.hud().actionBar(p, Text.mm("<#ffd36b>가방에 자리가 없어 일부는 판매 칸에 남겨 두었습니다."), 40);
            click(p);
            refresh();
        });
        set(S_CLOSE, kr.labyrinth.ui.UiTheme.close(), ctx -> ctx.player().closeInventory());
    }

    private ItemStack sellButton(long now) {
        if (basket.isEmpty()) {
            return Button.icon(Material.GRAY_DYE, "<gray><b>판매</b>", List.of("<dark_gray>아래 가방에서 팔 물건을 올리세요."));
        }
        List<String> lore = new ArrayList<>();
        lore.add("<gray>" + Text.num(basket.count()) + "개 · <gold>" + Text.num(basket.total()) + " G");
        boolean armed = basket.armed(now);
        if (basket.needsConfirm()) {
            lore.add("");
            lore.add("<#ff8a8a>⚠ 귀한 물건이 있습니다:");
            int shown = 0;
            for (SellBasket.Entry<ItemStack> e : basket.entries()) {
                if (!e.risky()) continue;
                if (shown++ >= 4) {
                    lore.add("<dark_gray>  …");
                    break;
                }
                lore.add("<gray>  · " + label(e.stack()));
            }
            lore.add(armed ? "<#ff6b6b><b>▶ 한 번 더 누르면 팝니다</b>" : "<yellow>▶ 클릭 후 한 번 더 눌러 판매");
        } else {
            lore.add("<yellow>▶ 클릭해서 판매");
        }
        return Button.icon(armed ? Material.REDSTONE_BLOCK : Material.GOLD_BLOCK,
                (armed ? "<#ff6b6b><b>정말 팔까요?</b> " : "<gold><b>판매</b> ") + "<white>" + Text.num(basket.total()) + " G", lore);
    }

    /** 판매 칸에 놓을 그림용 사본: 진짜 툴팁 + 판매가 줄. PDC 를 지워 혹시 빠져나가도 미궁 아이템으로 쓰이지 않게. */
    private ItemStack display(SellBasket.Entry<ItemStack> e) {
        ItemStack s = e.stack().clone();
        s.editPersistentDataContainer(pdc -> {
            for (NamespacedKey k : new ArrayList<>(pdc.getKeys())) pdc.remove(k);
        });
        List<Component> lore = new ArrayList<>();
        ItemLore existing = s.getData(DataComponentTypes.LORE);
        if (existing != null) lore.addAll(existing.lines());
        lore.add(Component.empty());
        int n = e.stack().getAmount();
        lore.add(Text.item("<gray>판매가 <gold>" + Text.num(e.unitPrice()) + " G</gold>"
                + (n > 1 ? " × " + n + " = <gold>" + Text.num((long) e.unitPrice() * n) + " G" : "")));
        if (e.risky()) lore.add(Text.item("<#ff8a8a>⚠ 귀한 물건 — [판매] 를 두 번 눌러야 팝니다"));
        lore.add(Text.item("<yellow>▶ 클릭: 가방으로 돌려받기"));
        s.setData(DataComponentTypes.LORE, ItemLore.lore(lore));
        return s;
    }

    private String label(ItemStack s) {
        ItemDef def = services.items().defOf(s).orElse(null);
        String name = def == null ? s.getType().name() : "<" + def.rarity().color() + ">" + Text.escape(Text.strip(def.name()))
                + "</" + def.rarity().color() + ">";
        int enh = Enhancement.level(s);
        return name + (enh > 0 ? " <#ffd36b>+" + enh : "") + (s.getAmount() > 1 ? " <gray>×" + s.getAmount() : "");
    }

    // ── 올리기 · 돌려받기 ─────────────────────────────────────────────────

    @Override
    protected void onBottomClick(ClickContext ctx) {
        int want = switch (ctx.click()) {
            case LEFT, SHIFT_LEFT, SHIFT_RIGHT -> Integer.MAX_VALUE;
            case RIGHT -> 1;
            default -> 0; // 숫자 키·버리기·더블클릭·가운데 버튼 등은 무시 (이벤트는 이미 취소됨)
        };
        if (want <= 0) return;
        if (!(ctx.event().getClickedInventory() instanceof PlayerInventory)) return;
        if (stage(ctx.player(), ctx.slot(), want, true) > 0) refresh();
    }

    /** 쉬프트+클릭 (MenuListener 가 넘기지 않는 MOVE_TO_OTHER_INVENTORY) — SellService 가 부른다. */
    void shiftStage(Player p, int slot) {
        if (stage(p, slot, Integer.MAX_VALUE, true) > 0) refresh();
    }

    /**
     * 가방 slot 칸에서 want 개를 올린다. 순서: 값 확인 → 받을 자리 계산 → 가방에서 먼저 빼고 → 바구니에 넣기 (한 틱 안).
     * @return 올린 개수
     */
    int stage(Player p, int slot, int want, boolean feedback) {
        if (!live(p) || slot < 0 || slot > 35) return 0;
        if (service.blocked(p)) {
            if (feedback) Text.error(p, "미궁 안에서는 물건을 팔 수 없습니다.");
            p.closeInventory();
            return 0;
        }
        PlayerInventory inv = p.getInventory();
        ItemStack cur = inv.getItem(slot);
        if (cur == null || cur.isEmpty()) return 0;
        ItemDef def = services.items().defOf(cur).orElse(null);
        int enh = Enhancement.level(cur);
        SellPrices.Quote q = prices.quote(def, enh);
        if (!q.sellable()) {
            if (feedback) {
                deny(p);
                services.hud().actionBar(p, Text.mm("<#ff6b6b>" + q.block().message()), 40);
            }
            return 0;
        }
        int n = Math.min(Math.min(want, cur.getAmount()), basket.room(cur, q.unit()));
        if (n <= 0) {
            if (feedback) {
                deny(p);
                services.hud().actionBar(p, Text.mm("<#ff6b6b>판매 칸이 가득 찼습니다. 먼저 파세요."), 40);
            }
            return 0;
        }
        ItemStack taken = cur.asQuantity(n);
        int left = cur.getAmount() - n;
        inv.setItem(slot, left > 0 ? cur.asQuantity(left) : null);
        int got = basket.add(taken, q.unit(), prices.risky(def, enh));
        if (got != n) {
            // 일어나면 안 되지만(자리를 미리 셈) 혹시라도 — 뺀 것을 그대로 되돌린다 (방금 비운 칸이라 들어감, 넘치면 맡김)
            service.giveOrKeep(p, List.of(taken), true);
            return 0;
        }
        if (feedback) p.playSound(p.getLocation(), Sound.ITEM_BUNDLE_INSERT, 0.7f, 1.2f);
        return n;
    }

    private void unstage(ClickContext ctx, int index) {
        Player p = ctx.player();
        switch (ctx.click()) {
            case LEFT, RIGHT, SHIFT_LEFT, SHIFT_RIGHT -> { }
            default -> { return; } // 숫자 키·더블클릭·버리기 등은 무시 (더블클릭이 다음 칸까지 빼지 않게)
        }
        if (!live(p)) return;
        List<SellBasket.Entry<ItemStack>> all = basket.entries();
        if (index < 0 || index >= all.size()) return;
        SellBasket.Entry<ItemStack> e = all.get(index);
        if (basket.remove(index) == null) return;
        int back = toBag(p, e);
        if (back <= 0) {
            deny(p);
            services.hud().actionBar(p, Text.mm("<#ff6b6b>가방에 자리가 없습니다."), 40);
        } else {
            p.playSound(p.getLocation(), Sound.ITEM_BUNDLE_REMOVE_ONE, 0.7f, 1.1f);
        }
        refresh();
    }

    /**
     * 바구니에서 막 꺼낸 칸을 가방에 들어가는 만큼 넣고, 남은 것은 같은 값으로 판매 칸에 되돌린다 (발밑에 떨구지 않음).
     * @return 가방에 넣은 개수
     */
    private int toBag(Player p, SellBasket.Entry<ItemStack> e) {
        ItemStack s = e.stack();
        int want = s.getAmount();
        int left = 0;
        for (ItemStack rest : p.getInventory().addItem(s).values()) {
            int n = rest.getAmount();
            left += n;
            // 방금 비운 칸이라 언제나 들어간다 — 혹시라도 안 되면 맡김
            if (basket.add(rest.clone(), e.unitPrice(), e.risky()) != n) service.giveOrKeep(p, List.of(rest), true);
        }
        return want - left;
    }

    /** 재료(확인 등급 아래)를 가방 0~35칸에서 전부 올린다. */
    private void bulk(ClickContext ctx) {
        Player p = ctx.player();
        if (!live(p)) return;
        int moved = 0;
        boolean full = false;
        for (int slot = 0; slot <= 35; slot++) {
            ItemStack cur = p.getInventory().getItem(slot);
            if (cur == null || cur.isEmpty()) continue;
            ItemDef def = services.items().defOf(cur).orElse(null);
            if (def == null || def.type() != ItemType.MATERIAL || prices.risky(def, Enhancement.level(cur))) continue;
            if (!prices.quote(def, 0).sellable()) continue;
            int n = stage(p, slot, Integer.MAX_VALUE, false);
            moved += n;
            if (n < cur.getAmount() && basket.size() >= basket.capacity()) {
                full = true;
                break;
            }
        }
        if (moved > 0) {
            p.playSound(p.getLocation(), Sound.ITEM_BUNDLE_INSERT, 0.8f, 1.0f);
            if (full) services.hud().actionBar(p, Text.mm("<#ffd36b>판매 칸이 가득 차 일부만 올렸습니다."), 40);
        } else {
            deny(p);
            services.hud().actionBar(p, Text.mm("<gray>올릴 재료가 없습니다."), 40);
        }
        refresh();
    }

    // ── 판매 ─────────────────────────────────────────────────────────────

    private void sell(ClickContext ctx) {
        Player p = ctx.player();
        switch (ctx.click()) {
            case LEFT, RIGHT -> { }
            default -> { return; } // 더블클릭·쉬프트·숫자 키 등은 누름으로 치지 않는다 (두 번 확인을 한 동작으로 넘기지 않게)
        }
        if (!live(p)) return;
        if (service.blocked(p)) {
            Text.error(p, "미궁 안에서는 물건을 팔 수 없습니다.");
            p.closeInventory();
            return;
        }
        switch (basket.press(System.currentTimeMillis())) {
            case EMPTY -> {
                deny(p);
                services.hud().actionBar(p, Text.mm("<gray>아래 가방에서 팔 물건을 먼저 올리세요."), 40);
                return;
            }
            case ARMED -> {
                p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.7f, 0.8f);
                services.hud().actionBar(p, Text.mm("<#ff8a8a>귀한 물건이 있습니다 — 확인했으면 잠시 뒤 [판매] 를 한 번 더 누르세요."), 60);
                refresh();
                return;
            }
            case SELL -> { }
        }
        SellBasket.Sale<ItemStack> sale = basket.sell();
        if (sale == null) return;
        // 바구니가 이미 비었다 → 골드는 여기서 정확히 한 번
        PlayerData d = services.data().get(p);
        d.addGold(sale.total());
        Text.send(p, "<green>판매 완료</green> <gray>" + Text.num(sale.count()) + "개 <dark_gray>→</dark_gray> <gold>+"
                + Text.num(sale.total()) + " G <dark_gray>(보유 " + Text.num(d.gold()) + " G)");
        Log.info("[판매] " + p.getName() + ": " + summary(sale) + " → " + sale.total() + " G");
        p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_YES, 0.7f, 1.1f);
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.7f, 1.3f);
        services.hud().refresh(p);
        refresh();
    }

    private String summary(SellBasket.Sale<ItemStack> sale) {
        StringBuilder sb = new StringBuilder();
        for (SellBasket.Entry<ItemStack> e : sale.entries()) {
            if (sb.length() > 0) sb.append(", ");
            String id = services.items().defOf(e.stack()).map(ItemDef::id).orElse(e.stack().getType().name());
            int enh = Enhancement.level(e.stack());
            sb.append(id).append(enh > 0 ? "+" + enh : "").append("×").append(e.stack().getAmount()).append("@").append(e.unitPrice());
        }
        return sb.toString();
    }

    // ── 닫기 · 돌려받기 ───────────────────────────────────────────────────

    /** 올린 물건을 가방에 들어가는 만큼 전부 돌려준다 (창은 그대로, 못 넣은 것은 칸에 남김). @return 전부 돌려줬나 */
    boolean returnAll(Player p) {
        List<SellBasket.Entry<ItemStack>> all = basket.entries();
        basket.takeAll();
        boolean every = true;
        for (SellBasket.Entry<ItemStack> e : all) {
            int amount = e.stack().getAmount();
            if (toBag(p, e) < amount) every = false;
        }
        return every;
    }

    /** 창이 닫혔다 (어떤 까닭이든): 바구니를 닫고 꺼낸 것을 돌려준다. 두 번째부터는 빈 목록. */
    List<ItemStack> closeBasket() { return basket.close(); }

    @Override
    protected void onOpen(Player player) { service.track(player, this); }

    @Override
    protected void onClose(Player player) { service.closed(player, this); }
}
