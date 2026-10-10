package kr.souls.item;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import com.destroystokyo.paper.event.player.PlayerRecipeBookClickEvent;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.data.Profile;
import org.bukkit.Bukkit;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.entity.ItemSpawnEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.CraftItemEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryCreativeEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.inventory.PrepareItemCraftEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerPortalEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.inventory.CraftingInventory;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 반지 칸 (9.4, 2026-10-08 사용자 결정 "반지 칸은 인벤토리의 2×2 제작 칸 자리, B 안: 왼쪽 세로 두 칸"). 그림은 팩이 2×2 자리를 반지
 * 칸 둘로 다시 그렸고 (pack/gui_skin.py), 여기서 그 칸의 일을 한다.
 *
 * 정본은 프로필의 rings (data/Profile, 12.6) 다. 2×2 의 왼쪽 위·왼쪽 아래 칸에 보이는 아이템은 프로필에서 다시 만든 사본
 * (Rings.wornCopy, 표시 souls:ring_worn) 이다. 바닐라는 2×2 의 것을 창을 닫을 때 인벤토리로 돌려주고 (InventoryMenu.removed),
 * 나가거나 죽어서 몸이 치워질 때는 땅에 떨어뜨리고 (Player.remove → dropOrPlaceInInventory), 다른 세계로 갈 때는 인벤토리로
 * 돌려준다. 그래서 그 일이 일어나기 바로 전에 칸을 비우고 (창 닫기 InventoryCloseEvent, 죽음, 나가기, 다른 세계로 가는 순간이동·관문,
 * 플러그인 끄기) 그 뒤 다시 채운다 (다음 틱, 다시 태어남, 접속, 세계 바뀜). 놓친 길이 있어도 사본은 표시가 있어 칸 밖에서 보이면
 * 지운다: 1초마다 인벤토리·커서를 훑고 ({@link #sweep}), 땅에 생기려는 사본은 막는다 (ItemSpawnEvent). 반지는 그 사이에도 프로필에
 * 있으므로 잃지도 겹치지도 않는다. 효과는 프로필만 보므로 창을 닫아도, 나갔다 와도, 죽어도, 서버를 다시 켜도 그대로다.
 *
 * 클릭: 2×2 자리 (날 칸 0..4) 를 건드리는 누르기는 모두 취소하고 판정 ({@link RingRules}) 대로 여기서 옮긴다 (바닐라가 2×2 에
 * 아무것도 넣거나 빼지 않는다). 가방의 반지를 웅크리고 누르면 빈 반지 칸에 낀다. 끌기가 2×2 에 닿으면 거절, 창작 모드의 칸 쓰기도
 * 거절. 결과 칸은 늘 비고 (PrepareItemCraftEvent), 2×2 제작 (CraftItemEvent) 과 제작법 책의 놓기 (PlayerRecipeBookClickEvent:
 * 놓기 전에 바닐라가 2×2 를 인벤토리로 비운다) 는 막는다. 취소한 누르기는 서버가 그 자리에서 바로잡고, 다음 틱에 창 전체를 한 번
 * 더 보낸다 (클라이언트에 남은 헛것이 없게).
 *
 * 제작대 제목: 바닐라는 인벤토리 2×2 의 "제작" 과 제작대 창 제목에 같은 열쇠 container.crafting 을 쓴다. 팩이 그 열쇠를 비워
 * 인벤토리의 글을 지웠으므로 (반지 칸에 글을 넣지 않는다, 사용자 결정) 제작대 창은 여기서 제 제목 (lang 의 container.workbench)
 * 을 단다. 제작대는 짓는 사람 (창작 모드) 만 연다 (world/Protection).
 *
 * 효과 ({@link #worn}): stamina-regen 은 combat/Stamina 가 지금 쓴다. poise·parry-window·soul-guard 는 그 체계가 생길 때 부를 고리다
 * ({@link #poiseBonus}, {@link #parryWindowBonus}, {@link #consumeSoulGuard}).
 */
public final class RingSlots implements Listener {
    /** 훑기와 칸 맞추기의 틈 (틱) */
    private static final int RECONCILE_EVERY = 20;

    private final Souls plugin;
    /** 다음 틱에 칸을 다시 채울 사람 */
    private final Set<UUID> restore = new HashSet<>();
    /** 다음 틱에 창 전체를 다시 보낼 사람 */
    private final Set<UUID> resync = new HashSet<>();
    /** rings.yml 에 없는 반지 id 를 한 번만 알린다 */
    private final Set<String> warned = new HashSet<>();

    public RingSlots(Souls plugin) {
        this.plugin = plugin;
    }

    private Rings rings() {
        return plugin.rings();
    }

    // ------------------------------------------------------------------ 효과

    /** 낀 반지 (프로필) 의 id, 칸마다. */
    public String[] wornIds(Player p) {
        Profile pr = plugin.profiles().of(p);
        String[] out = new String[Profile.RING_SLOTS];
        for (int i = 0; i < out.length; i++) out[i] = pr.ring(i);
        return out;
    }

    /** 낀 반지들의 효과를 합친 것 (rings.yml 에 없는 id 는 건너뛴다). */
    public Rings.Worn worn(Player p) {
        List<Rings.Def> ds = new ArrayList<>(Profile.RING_SLOTS);
        for (String id : wornIds(p)) ds.add(def(id));
        return Rings.combine(ds);
    }

    /** 스태미나 회복 배율 (combat/Stamina 가 틱마다, 능력치 창의 회복 값). 틱마다 불리므로 모으지 않고 바로 곱한다. */
    public double staminaRegen(Player p) {
        Profile pr = plugin.profiles().of(p);
        double m = 1.0;
        for (int i = 0; i < Profile.RING_SLOTS; i++) {
            Rings.Def d = def(pr.ring(i));
            if (d != null) m *= d.staminaRegen();
        }
        return m;
    }

    /** 강인도 덧셈 비율 (0.4 = +40%). 고리: 강인도 체계 (3.8) 가 생기면 부른다. 지금은 부르는 곳이 없다. */
    public double poiseBonus(Player p) {
        return worn(p).poise();
    }

    /** 쳐내기 창 덧셈 틱. 고리: 쳐내기 (3.5) 가 생기면 부른다. 지금은 부르는 곳이 없다. */
    public int parryWindowBonus(Player p) {
        return worn(p).parryWindow();
    }

    /** 소울을 지키는 반지를 꼈나. 고리: 소울 잃기 (5.5, M2) 가 부른다. */
    public boolean soulGuard(Player p) {
        return worn(p).soulGuard();
    }

    /**
     * 소울 잃기 (5.5, M2) 가 죽을 때 부른다: 소울을 지키는 반지를 꼈으면 그 반지가 부서지고 (프로필에서 지운다) true. 지금은 부르는
     * 곳이 없다 (혈흔·소울 잃기는 M2).
     */
    public boolean consumeSoulGuard(Player p) {
        Profile pr = plugin.profiles().of(p);
        for (int i = 0; i < Profile.RING_SLOTS; i++) {
            Rings.Def d = def(pr.ring(i));
            if (d != null && d.soulGuard()) {
                pr.setRing(i, null);
                plugin.profiles().save(p, true);
                later(p);
                plugin.test(p, "RING_BREAK ring=" + (i + 1) + " id=" + d.id());
                return true;
            }
        }
        return false;
    }

    private Rings.Def def(String id) {
        if (id == null) return null;
        Rings.Def d = rings().get(id);
        if (d == null && warned.add(id)) {
            plugin.getLogger().warning("프로필에 낀 반지 " + id + " 가 rings.yml 에 없습니다. 칸에 보이지 않고 효과도 없지만 프로필에는 남겨 둡니다.");
        }
        return d;
    }

    // ------------------------------------------------------------------ 칸

    /** 이 사람의 2×2 (자기 인벤토리 창. 상자 같은 다른 창이 열렸으면 손이 닿지 않아 null). 0 결과, 1..4 2×2. */
    static CraftingInventory own(Player p) {
        Inventory top = p.getOpenInventory().getTopInventory();
        return top instanceof CraftingInventory ci && top.getType() == InventoryType.CRAFTING ? ci : null;
    }

    private static boolean empty(ItemStack it) {
        return it == null || it.isEmpty();
    }

    /**
     * 칸을 프로필에 맞춘다: 반지 칸 둘은 프로필 반지의 사본, 나머지 셋 (결과 칸, 오른쪽 두 칸) 은 빈칸. 2×2 에 다른 것이 들어와 있으면
     * (명령 /item, 다른 플러그인) 인벤토리로 돌려준다 (결과 칸의 것은 돌려주지 않는다: 그것은 만든 것이다). 바꾼 칸 수, 손이 닿지 않으면 -1.
     */
    public int apply(Player p) {
        CraftingInventory ci = own(p);
        if (ci == null || p.isDead()) return -1;
        Profile pr = plugin.profiles().of(p);
        int changed = 0;
        for (int raw = 0; raw <= 4; raw++) {
            ItemStack cur = ci.getItem(raw);
            int ring = RingRules.ringIndex(raw);
            Rings.Def want = ring >= 0 ? def(pr.ring(ring)) : null;
            if (want != null && Rings.isWornCopy(cur) && want.id().equals(Rings.idOf(cur))) continue;
            if (want == null && empty(cur)) continue;
            if (!empty(cur) && !Rings.isWornCopy(cur) && raw != RingRules.RESULT) {
                giveBack(p, cur);
                plugin.test(p, "RING_STRAY slot=" + raw + " item=" + cur.getType().getKey().getKey() + " back=inventory");
            }
            ci.setItem(raw, want == null ? null : rings().wornCopy(want));
            changed++;
        }
        return changed;
    }

    /** 2×2 를 비운다 (바닐라가 돌려주거나 떨어뜨리기 전에). 사본이 아닌 것은 인벤토리로 돌려준다. */
    public void clear(Player p) {
        CraftingInventory ci = own(p);
        if (ci == null) return;
        for (int raw = 0; raw <= 4; raw++) {
            ItemStack cur = ci.getItem(raw);
            if (empty(cur)) continue;
            if (!Rings.isWornCopy(cur) && raw != RingRules.RESULT) giveBack(p, cur);
            ci.setItem(raw, null);
        }
    }

    /** 칸 밖에 나온 사본 (인벤토리, 왼손, 갑옷 칸, 커서) 을 지운다. 지운 수. */
    public int sweep(Player p) {
        int n = 0;
        PlayerInventory inv = p.getInventory();
        ItemStack[] all = inv.getContents();
        for (int i = 0; i < all.length; i++) {
            if (Rings.isWornCopy(all[i])) {
                inv.setItem(i, null);
                n++;
            }
        }
        if (Rings.isWornCopy(p.getItemOnCursor())) {
            p.setItemOnCursor(null);
            n++;
        }
        if (n > 0) plugin.test(p, "RING_SWEEP removed=" + n);
        return n;
    }

    private void giveBack(Player p, ItemStack it) {
        Map<Integer, ItemStack> left = p.getInventory().addItem(it.clone());
        // 넘치면 발밑에 (바닐라 Protection 의 버리기 막기를 지나지 않는 길: 플레이어가 버린 것이 아니다)
        for (ItemStack rest : left.values()) p.getWorld().dropItem(p.getLocation(), rest);
    }

    /** 다음 틱에 칸을 다시 채운다. */
    private void later(Player p) {
        if (restore.add(p.getUniqueId())) {
            Bukkit.getScheduler().runTask(plugin, () -> {
                restore.remove(p.getUniqueId());
                if (p.isOnline()) {
                    sweep(p);
                    apply(p);
                }
            });
        }
    }

    /** 다음 틱에 창 전체를 다시 보낸다 (취소한 누르기의 헛것이 클라이언트에 남지 않게). */
    private void resyncLater(Player p) {
        if (resync.add(p.getUniqueId())) {
            Bukkit.getScheduler().runTask(plugin, () -> {
                resync.remove(p.getUniqueId());
                if (p.isOnline()) p.updateInventory();
            });
        }
    }

    /** Ticker: 1초마다 사본을 훑고 칸을 프로필에 맞춘다 (놓친 길의 안전망). */
    public void tick(long now) {
        if (now % RECONCILE_EVERY != 0) return;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.isDead()) continue;
            sweep(p);
            apply(p);
        }
    }

    /** 플러그인을 켤 때 (/reload 뒤 포함). */
    public void enable() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            sweep(p);
            apply(p);
        }
    }

    /** 플러그인을 끌 때: 칸을 비운다. 서버를 끄면 플러그인이 먼저 꺼지고 그다음 플레이어를 내보내며 몸을 치우는데, 그때 바닐라가 2×2 를 떨어뜨린다. */
    public void disable() {
        for (Player p : Bukkit.getOnlinePlayers()) clear(p);
    }

    // ------------------------------------------------------------------ 누르기

    private static RingRules.Kind kind(ClickType c) {
        return switch (c) {
            case LEFT -> RingRules.Kind.LEFT;
            case RIGHT -> RingRules.Kind.RIGHT;
            case SHIFT_LEFT, SHIFT_RIGHT -> RingRules.Kind.SHIFT;
            case NUMBER_KEY -> RingRules.Kind.NUMBER;
            case SWAP_OFFHAND -> RingRules.Kind.OFFHAND;
            case DROP, CONTROL_DROP -> RingRules.Kind.DROP;
            case DOUBLE_CLICK -> RingRules.Kind.DOUBLE;
            case MIDDLE -> RingRules.Kind.MIDDLE;
            case CREATIVE -> RingRules.Kind.CREATIVE;
            default -> RingRules.Kind.OTHER;
        };
    }

    private RingRules.Thing thing(ItemStack it) {
        if (empty(it)) return RingRules.Thing.EMPTY;
        return rings().of(it) != null ? RingRules.Thing.RING : RingRules.Thing.OTHER;
    }

    /** 자기 인벤토리 창 (2×2 가 보이는 창) 인가. 창작 모드 화면도 같은 창이다. */
    private static boolean ownView(InventoryView v) {
        return v.getTopInventory().getType() == InventoryType.CRAFTING;
    }

    @EventHandler(priority = EventPriority.NORMAL)
    public void onClick(InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof Player p) || !ownView(e.getView())) return;
        int raw = e.getRawSlot();
        if (e instanceof InventoryCreativeEvent) {
            // 창작 모드 화면은 2×2 를 보이지 않지만, "모두 지우기" 는 모든 칸 (2×2 포함) 을 비우라고 보낸다
            if (RingRules.craftArea(raw)) deny(e, p, raw, "creative");
            return;
        }
        RingRules.Kind kind = kind(e.getClick());
        PlayerInventory inv = p.getInventory();
        ItemStack otherItem = switch (kind) {
            case NUMBER -> e.getHotbarButton() >= 0 ? inv.getItem(e.getHotbarButton()) : null;
            case OFFHAND -> inv.getItemInOffHand();
            default -> null;
        };
        String[] worn = wornIds(p);
        RingRules.Decision d = RingRules.decide(raw, kind, thing(e.getCursor()), thing(e.getCurrentItem()), thing(otherItem),
                RingRules.firstFree(worn));
        switch (d.act()) {
            case PASS -> {
                return;
            }
            case DENY -> {
                deny(e, p, raw, kind.name().toLowerCase(Locale.ROOT));
                return;
            }
            default -> {
                e.setCancelled(true);
                if (!perform(p, e, d, worn, otherItem)) deny(e, p, raw, "refused");
                resyncLater(p);
            }
        }
    }

    private void deny(InventoryClickEvent e, Player p, int raw, String why) {
        e.setCancelled(true);
        resyncLater(p);
        if (RingRules.craftArea(raw)) plugin.test(p, "RING_DENY slot=" + raw + " why=" + why);
    }

    /** 판정대로 옮긴다 (누르기는 이미 취소했다). 못 하면 false. */
    private boolean perform(Player p, InventoryClickEvent e, RingRules.Decision d, String[] worn, ItemStack otherItem) {
        Profile pr = plugin.profiles().of(p);
        CraftingInventory ci = (CraftingInventory) e.getView().getTopInventory();
        PlayerInventory inv = p.getInventory();
        int r = d.ring();
        switch (d.act()) {
            case PUT -> {
                Rings.Def in = rings().of(e.getCursor());
                if (!wear(p, worn, r, in)) return false;
                pr.setRing(r, in.id());
                ci.setItem(RingRules.rawOf(r), rings().wornCopy(in));
                p.setItemOnCursor(null);
                done(p, "put", r, in.id());
            }
            case TAKE -> {
                Rings.Def out = def(pr.ring(r));
                if (out == null) return false;
                pr.setRing(r, null);
                ci.setItem(RingRules.rawOf(r), null);
                p.setItemOnCursor(rings().make(out));
                done(p, "take", r, out.id());
            }
            case SWAP_CURSOR -> {
                Rings.Def in = rings().of(e.getCursor());
                Rings.Def out = def(pr.ring(r));
                if (out == null || !wear(p, worn, r, in)) return false;
                pr.setRing(r, in.id());
                ci.setItem(RingRules.rawOf(r), rings().wornCopy(in));
                p.setItemOnCursor(rings().make(out));
                done(p, "swap", r, in.id());
            }
            case TO_STORAGE -> {
                Rings.Def out = def(pr.ring(r));
                int at = freeStorage(inv);
                if (out == null || at < 0) return false;
                pr.setRing(r, null);
                ci.setItem(RingRules.rawOf(r), null);
                inv.setItem(at, rings().make(out));
                done(p, "unequip", r, out.id());
            }
            case SWAP_WITH -> {
                Rings.Def in = rings().of(otherItem);
                Rings.Def out = def(pr.ring(r));
                if (in != null && !wear(p, worn, r, in)) return false;
                if (in == null && out == null) return false;
                pr.setRing(r, in == null ? null : in.id());
                ci.setItem(RingRules.rawOf(r), in == null ? null : rings().wornCopy(in));
                ItemStack back = out == null ? null : rings().make(out);
                if (e.getClick() == ClickType.SWAP_OFFHAND) inv.setItemInOffHand(back);
                else inv.setItem(e.getHotbarButton(), back);
                done(p, e.getClick() == ClickType.SWAP_OFFHAND ? "offhand" : "hotbar", r, in == null ? "-" : in.id());
            }
            case EQUIP_FROM -> {
                Rings.Def in = rings().of(e.getCurrentItem());
                if (!wear(p, worn, r, in)) return false;
                pr.setRing(r, in.id());
                ci.setItem(RingRules.rawOf(r), rings().wornCopy(in));
                e.getView().setItem(e.getRawSlot(), null);
                done(p, "equip", r, in.id());
            }
            default -> {
                return false;
            }
        }
        return true;
    }

    /**
     * 반지 칸 r 에 in 을 껴도 되나 (같은 반지 둘은 끼지 않는다). 안 되면 둔탁한 소리. 그 칸의 프로필에 rings.yml 에서 지운 반지 id 가
     * 남아 있었으면 (칸에는 보이지 않는다) 그것을 덮어쓴다는 것을 서버 기록에 남긴다.
     */
    private boolean wear(Player p, String[] worn, int r, Rings.Def in) {
        if (in == null) return false;
        if (worn[r] != null && rings().get(worn[r]) == null) {
            plugin.getLogger().warning(p.getName() + " 의 반지 칸 " + (r + 1) + " 에 남아 있던 모르는 반지 " + worn[r] + " 를 " + in.id() + " 로 덮어씁니다.");
        }
        if (RingRules.duplicate(worn, r, in.id())) {
            p.playSound(p, Sound.BLOCK_CHAIN_HIT, SoundCategory.PLAYERS, 0.5f, 0.7f);
            plugin.test(p, "RING_SAME ring=" + (r + 1) + " id=" + in.id());
            return false;
        }
        return true;
    }

    /** 가방 (9..35) 의 첫 빈 칸, 없으면 단축 슬롯 (0..8). 바닐라가 2×2 에서 웅크리고 누른 것을 옮기는 차례. 없으면 -1. */
    private static int freeStorage(PlayerInventory inv) {
        for (int i = 9; i < 36; i++) if (empty(inv.getItem(i))) return i;
        for (int i = 0; i < 9; i++) if (empty(inv.getItem(i))) return i;
        return -1;
    }

    private void done(Player p, String act, int r, String id) {
        plugin.profiles().save(p, false);
        p.playSound(p, Sound.ITEM_ARMOR_EQUIP_CHAIN, SoundCategory.PLAYERS, 0.5f, act.equals("take") || act.equals("unequip") ? 1.2f : 1.6f);
        String[] w = wornIds(p);
        plugin.test(p, "RING act=" + act + " ring=" + (r + 1) + " id=" + id + " r1=" + (w[0] == null ? "-" : w[0]) + " r2=" + (w[1] == null ? "-" : w[1]));
    }

    @EventHandler(priority = EventPriority.NORMAL)
    public void onDrag(InventoryDragEvent e) {
        if (!(e.getWhoClicked() instanceof Player p) || !ownView(e.getView())) return;
        for (int raw : e.getRawSlots()) {
            if (RingRules.craftArea(raw)) {
                e.setCancelled(true);
                resyncLater(p);
                plugin.test(p, "RING_DENY slot=" + raw + " why=drag");
                return;
            }
        }
    }

    // ------------------------------------------------------------------ 바닐라가 2×2 를 돌려주는 때

    /** 창을 닫으면 바닐라가 2×2 를 인벤토리로 돌려준다 (넘치면 떨어뜨린다): 그 전에 비우고 다음 틱에 다시 채운다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof Player p)) return;
        if (ownView(e.getView())) clear(p);
        // 상자 같은 다른 창을 닫았을 때도: 그 창이 열려 있는 동안은 2×2 에 손이 닿지 않아 맞추지 못했다
        later(p);
    }

    /** 죽으면 몸이 치워질 때 (다시 태어날 때) 바닐라가 2×2 를 그 자리에 떨어뜨린다: 비워 둔다. 반지는 떨어지지 않는다. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) {
        clear(e.getEntity());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerPostRespawnEvent e) {
        later(e.getPlayer());
    }

    /** 나가면 몸이 치워질 때 바닐라가 2×2 를 떨어뜨린다: 비워 둔다 (프로필은 Profiles 가 MONITOR 에서 쓴다). */
    @EventHandler(priority = EventPriority.LOW)
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        clear(p);
        sweep(p);
        restore.remove(p.getUniqueId());
        resync.remove(p.getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        later(e.getPlayer());
    }

    /** 다른 세계로 가면 바닐라가 2×2 를 인벤토리로 돌려준다: 가기 전에 비우고, 세계가 바뀐 뒤 다시 채운다. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        if (e.getTo().getWorld() != null && !e.getTo().getWorld().equals(e.getFrom().getWorld())) {
            clear(e.getPlayer());
            later(e.getPlayer());
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPortal(PlayerPortalEvent e) {
        if (e.getTo().getWorld() != null && !e.getTo().getWorld().equals(e.getFrom().getWorld())) {
            clear(e.getPlayer());
            later(e.getPlayer());
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        later(e.getPlayer());
    }

    // ------------------------------------------------------------------ 2×2 제작은 없다

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onPrepare(PrepareItemCraftEvent e) {
        if (e.getInventory().getType() == InventoryType.CRAFTING) e.getInventory().setResult(null);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCraft(CraftItemEvent e) {
        if (e.getInventory().getType() == InventoryType.CRAFTING) e.setCancelled(true);
    }

    /** 제작법 책 (단추 그림은 지웠지만 누를 자리는 바닐라 그대로) 의 놓기: 바닐라가 놓기 전에 2×2 를 인벤토리로 비운다. */
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onRecipeBook(PlayerRecipeBookClickEvent e) {
        if (ownView(e.getPlayer().getOpenInventory())) {
            e.setCancelled(true);
            plugin.test(e.getPlayer(), "RING_DENY slot=0 why=recipe_book");
        }
    }

    /** 제작대 창의 제목 (팩이 container.crafting 을 비웠다). */
    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        if (e.getInventory().getType() == InventoryType.WORKBENCH && e.titleOverride() == null && e.getPlayer() instanceof Player p) {
            e.titleOverride(Lang.c(p, "container.workbench"));
        }
    }

    // ------------------------------------------------------------------ 안전망: 칸 밖의 사본

    @EventHandler(priority = EventPriority.LOWEST)
    public void onItemSpawn(ItemSpawnEvent e) {
        if (Rings.isWornCopy(e.getEntity().getItemStack())) e.setCancelled(true);
    }

    /**
     * 사본이 버려지면 (바닐라가 몸을 치우며 떨어뜨린 것) 그대로 사라지게 둔다: 버리기를 막으면 (Protection) CraftBukkit 이 그것을
     * 인벤토리에 도로 넣어 겹친다. 생기려는 물체는 onItemSpawn 이 막는다.
     */
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDropCopy(PlayerDropItemEvent e) {
        if (Rings.isWornCopy(e.getItemDrop().getItemStack())) {
            e.setCancelled(false);
            plugin.test(e.getPlayer(), "RING_SWEEP removed=1 where=drop");
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onPickup(EntityPickupItemEvent e) {
        Item it = e.getItem();
        if (Rings.isWornCopy(it.getItemStack())) {
            e.setCancelled(true);
            it.remove();
        }
    }

    // ------------------------------------------------------------------ 시험 (/soulstest ring)

    /** 시험 줄 RINGS: 프로필, 칸 (2×2 의 다섯), 인벤토리의 반지, 커서, 칸 밖 사본, 효과, 둘레의 반지 물체. */
    public String line(Player p) {
        String[] w = wornIds(p);
        CraftingInventory ci = own(p);
        StringBuilder view = new StringBuilder();
        for (int raw = 0; raw <= 4; raw++) {
            ItemStack it = ci == null ? null : ci.getItem(raw);
            String v = empty(it) ? "-" : Rings.idOf(it) != null ? Rings.idOf(it) + (Rings.isWornCopy(it) ? "*" : "") : it.getType().getKey().getKey();
            view.append(" s").append(raw).append('=').append(ci == null ? "?" : v);
        }
        List<String> inv = new ArrayList<>();
        int strays = 0;
        ItemStack[] all = p.getInventory().getContents();
        for (int i = 0; i < all.length; i++) {
            String id = Rings.idOf(all[i]);
            if (id == null) continue;
            if (Rings.isWornCopy(all[i])) strays++;
            inv.add(i + ":" + id);
        }
        ItemStack cur = p.getItemOnCursor();
        String cursor = empty(cur) ? null : Rings.idOf(cur) != null ? Rings.idOf(cur) + (Rings.isWornCopy(cur) ? "*" : "") : cur.getType().getKey().getKey();
        int ground = 0;
        for (Entity en : p.getNearbyEntities(32, 32, 32)) if (en instanceof Item item && Rings.idOf(item.getItemStack()) != null) ground++;
        Rings.Worn fx = worn(p);
        return String.format(Locale.ROOT, "RINGS r1=%s r2=%s%s inv=%s cursor=%s strays=%d ground=%d regen=%.4f poise=%.2f parry=%d guard=%s",
                w[0] == null ? "-" : w[0], w[1] == null ? "-" : w[1], view, inv.isEmpty() ? "-" : String.join(",", inv),
                cursor == null ? "-" : cursor, strays, ground, fx.staminaRegen(), fx.poise(), fx.parryWindow(), fx.soulGuard());
    }

    /** 시험: 반지 칸 r (0, 1) 에 id 를 바로 낀다 (찍기 준비. 아이템을 쓰지 않는다). null 이면 뺀다 (아이템은 주지 않는다). */
    public boolean set(Player p, int r, String id) {
        if (id != null && rings().get(id) == null) return false;
        String[] w = wornIds(p);
        if (id != null && RingRules.duplicate(w, r, id)) return false;
        plugin.profiles().of(p).setRing(r, id);
        plugin.profiles().save(p, false);
        apply(p);
        return true;
    }
}
