package kr.labyrinth.mine;

import io.papermc.paper.datacomponent.DataComponentTypes;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.event.ItemObtainEvent;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 함께 쓰는 광맥 (계약 §0-3): 진짜 블록이 모두에게 빈 광맥 블록이 되고, 시간이 지나면 다시 찬다.
 * <ul>
 *   <li>다시 차는 시간 = 기본(config mine.regen_minutes[층]) ÷ min(광산 월드 사람 수, regen_players_cap) — {@link VeinState}</li>
 *   <li>수확은 가방에 바로 (가득 차면 캐지지도 비워지지도 않음), 바닐라 드롭·경험치 없음</li>
 *   <li>광석 블록 = 광석 1 + 곡괭이 덤 확률로 +1 · gem_chance 로 같은 등급 보석 1 · 풍부한 광맥이면 ×rich.multiplier</li>
 *   <li>보석 노드 = 보석 1, gem_node_regen_minutes 뒤 다시 참 · 결정 모양 ItemDisplay (빈 동안 없음)</li>
 * </ul>
 * 재시작 때 기록은 없다 — 켤 때 {@link MineBuilder} 가 모든 광맥을 다 찬 블록으로 되돌린다.
 */
final class MineVeins {

    enum Result { OK, NOT_VEIN, DEPLETED, NO_PICKAXE, TOO_WEAK, BAG_FULL, NO_ITEMS }

    /** 수확 결과. amount = 광석(또는 보석 노드면 보석) 수, gem = 덤 보석 id (없으면 null), bagCount = 넣은 뒤 가방의 그 광석 수. */
    record Harvest(Result result, MineLevel.Vein vein, String item, int amount, boolean bonus, boolean rich, String gem, int bagCount) {
        static Harvest of(Result r, MineLevel.Vein v) { return new Harvest(r, v, null, 0, false, false, null, 0); }
    }

    private final MineModule module;
    private final Map<Long, MineLevel.Vein> index = new HashMap<>();
    private final Map<String, MineLevel.Vein> byKey = new HashMap<>();
    private final Map<String, UUID> displays = new HashMap<>();
    private VeinState state;
    final NamespacedKey nodeKey = new NamespacedKey(kr.labyrinth.core.Keys.NS, MineNames.PDC_NODE);

    MineVeins(MineModule module) {
        this.module = module;
        this.state = new VeinState(MineNames.REGEN_PLAYERS_CAP);
    }

    VeinState state() { return state; }

    void reset(List<MineLevel> levels, int cap) {
        index.clear();
        byKey.clear();
        state = new VeinState(cap);
        for (MineLevel l : levels) {
            for (MineLevel.Vein v : l.veins) put(v);
            for (MineLevel.Vein v : l.gems) put(v);
        }
    }

    private void put(MineLevel.Vein v) {
        index.put(MineBlueprint.blockKey(v.x(), v.y(), v.z()), v);
        byKey.put(v.key(), v);
    }

    MineLevel.Vein at(Block b) {
        return b == null ? null : index.get(MineBlueprint.blockKey(b.getX(), b.getY(), b.getZ()));
    }

    MineLevel.Vein byKey(String key) { return byKey.get(key); }

    int total() { return index.size(); }

    void clearLevel(int n) { state.clearLevel(n); }

    /** 지금 광산 월드에서 캐는 사람 수 (관전·크리에이티브 빼고). */
    int miners() {
        World w = module.world();
        if (w == null) return 0;
        int n = 0;
        for (Player p : w.getPlayers()) if (p.getGameMode() == GameMode.ADVENTURE || p.getGameMode() == GameMode.SURVIVAL) n++;
        return n;
    }

    // ── 캐기 ────────────────────────────────────────────────────────────

    /**
     * 수확 한 번 (BlockBreakEvent 를 취소한 뒤 서버가 다시 본다): 광맥인가 · 비지 않았나 · 곡괭이 tier ≥ 광석 tier ·
     * 가방 자리. 통과하면 가방에 넣고 블록을 빈 광맥으로 바꾼다 (모두에게).
     * @param who  보상·안내를 받을 사람 (시험 고리에서는 null)
     * @param bag  넣을 가방 (플레이어 인벤토리 또는 시험용)
     */
    Harvest harvest(Player who, MineLevel.Vein v, ToolSpec tool, Inventory bag, Random rnd, boolean testItems) {
        if (v == null) return Harvest.of(Result.NOT_VEIN, null);
        World w = module.world();
        Block b = w.getBlockAt(v.x(), v.y(), v.z());
        if (state.isDepleted(v.key()) || !b.getBlockData().equals(v.full())) return Harvest.of(Result.DEPLETED, v);
        TierRule.Verdict t = TierRule.check(tool, v.node().tier());
        if (t == TierRule.Verdict.NO_PICKAXE) return Harvest.of(Result.NO_PICKAXE, v);
        if (t == TierRule.Verdict.TOO_WEAK) return Harvest.of(Result.TOO_WEAK, v);
        MineConfig cfg = module.config();
        int amount = MineMath.baseYield(v.gem(), tool.bonus(), rnd.nextDouble());
        boolean bonus = amount > 1;
        boolean rich = state.isRich(v.key());
        if (rich) amount *= cfg.richMultiplier();
        String gem = !v.gem() && v.node().gem() != null && !v.node().gem().isBlank() && rnd.nextDouble() < cfg.gemChance() ? v.node().gem() : null;
        String item = v.node().id();
        List<ItemStack> stacks = new ArrayList<>();
        ItemStack main = make(item, amount, testItems);
        if (main == null) return Harvest.of(Result.NO_ITEMS, v);
        stacks.add(main);
        if (gem != null) {
            ItemStack g = make(gem, 1, testItems);
            if (g != null) stacks.add(g);
            else gem = null;
        }
        if (!fits(bag, stacks)) return Harvest.of(Result.BAG_FULL, v);
        // 여기서부터 확정
        if (rich) state.takeRich(v.key());
        for (ItemStack s : stacks) {
            bag.addItem(s.clone());
            if (who != null) {
                ItemDef def = module.services().items().defOf(s).orElse(null);
                if (def != null) Bukkit.getPluginManager().callEvent(new ItemObtainEvent(who, def, s, MineNames.SOURCE_MINE));
            }
        }
        double regen = v.gem() ? cfg.gemRegenSeconds() : cfg.regenSeconds(v.level().n);
        state.deplete(v.key(), regen);
        b.setBlockData(v.level().depleted, false);
        if (v.gem()) removeDisplay(v.key());
        int count = 0;
        for (ItemStack s : bag.getStorageContents()) if (s != null && s.isSimilar(main)) count += s.getAmount();
        module.stats().add(who, v.level().n);
        return new Harvest(Result.OK, v, item, amount, bonus, rich, gem, count);
    }

    /** 수확할 아이템 (items.yml 정의). 시험 고리에서 정의가 없으면 이름 붙은 종이로 대신한다. */
    private ItemStack make(String id, int amount, boolean testItems) {
        ItemStack s = module.services().items().create(id, amount);
        if (s != null) return s;
        Log.warnOnce("mine-item:" + id, "[광산] items.yml 에 광산 아이템 " + id + " 이(가) 없어 수확하지 않습니다 (Q3 재료).");
        if (!testItems) return null;
        ItemStack p = ItemStack.of(Material.PAPER, Math.max(1, amount));
        p.setData(DataComponentTypes.ITEM_NAME, Text.item("<white>" + id));
        p.setData(DataComponentTypes.MAX_STACK_SIZE, 64);
        return p;
    }

    /** 가방(저장 칸 36)에 stacks 가 모두 들어가나 — 바닐라 addItem 과 같은 겹치기. */
    static boolean fits(Inventory bag, List<ItemStack> stacks) {
        ItemStack[] slots = bag instanceof org.bukkit.inventory.PlayerInventory pi ? pi.getStorageContents() : bag.getContents();
        List<BagFit.Slot> s = new ArrayList<>();
        for (int i = 0; i < slots.length; i++) {
            ItemStack it = slots[i];
            if (it == null || it.getType().isAir() || it.getAmount() <= 0) {
                s.add(new BagFit.Slot(null, 0, 64));
                continue;
            }
            String key = "x" + i;
            for (int j = 0; j < stacks.size(); j++) {
                if (it.isSimilar(stacks.get(j))) {
                    key = "n" + j;
                    break;
                }
            }
            s.add(new BagFit.Slot(key, it.getAmount(), it.getMaxStackSize()));
        }
        List<BagFit.Add> adds = new ArrayList<>();
        for (int j = 0; j < stacks.size(); j++) adds.add(new BagFit.Add("n" + j, stacks.get(j).getAmount(), stacks.get(j).getMaxStackSize()));
        return BagFit.fits(s, adds);
    }

    // ── 다시 차기 (1초마다) ─────────────────────────────────────────────

    void tick() { tickWith(1.0, miners()); }

    /** dt 초를 사람 수 players 로 흘림 (시험 고리도 이 길). @return 다시 찬 수 */
    int tickWith(double dt, int players) {
        World w = module.world();
        if (w == null) return 0;
        List<String> done = state.tick(dt, players);
        MineConfig cfg = module.config();
        for (String key : done) {
            MineLevel.Vein v = byKey.get(key);
            if (v == null) continue;
            refill(w, v, cfg.richChance() > 0 && !v.gem() && ThreadLocalRandom.current().nextDouble() < cfg.richChance());
        }
        return done.size();
    }

    /** 다시 찬 광맥을 진짜 블록으로 + 연출. */
    void refill(World w, MineLevel.Vein v, boolean rich) {
        state.refill(v.key());
        Block b = w.getBlockAt(v.x(), v.y(), v.z());
        b.setBlockData(v.full(), false);
        if (rich) state.markRich(v.key());
        if (v.gem()) spawnDisplay(w, v);
        Location c = face(v);
        try {
            Particle p = Particle.valueOf(v.level().def.regenFx());
            w.spawnParticle(p, c, 6, 0.25, 0.25, 0.25, 0.01);
        } catch (Throwable ignored) {
            w.spawnParticle(Particle.WAX_ON, c, 6, 0.25, 0.25, 0.25, 0.01);
        }
        w.playSound(c, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.35f, 1.0f + 0.1f * (v.level().n - 1));
    }

    /** 풍부한 광맥 반짝임 (2초마다, 누구에게나 보임). */
    void sparkle() {
        World w = module.world();
        if (w == null) return;
        for (String key : state.richKeys()) {
            MineLevel.Vein v = byKey.get(key);
            if (v != null) w.spawnParticle(Particle.ELECTRIC_SPARK, face(v), 4, 0.3, 0.3, 0.3, 0.02);
        }
    }

    /** 블록 보이는 면 가운데 조금 바깥. */
    static Location face(MineLevel.Vein v) {
        MineBlueprint.Node a = v.at();
        return new Location(null, a.x() + 0.5 + a.fx() * 0.55, a.y() + 0.5 + a.fy() * 0.55, a.z() + 0.5 + a.fz() * 0.55);
    }

    /** 모두 다 찬 상태로 (끌 때 — 월드 파일에 빈 광맥이 남지 않게). */
    int refillAll() {
        World w = module.world();
        int n = 0;
        if (w != null) {
            for (String key : state.depleted()) {
                MineLevel.Vein v = byKey.get(key);
                if (v == null) continue;
                Block b = w.getBlockAt(v.x(), v.y(), v.z());
                b.setBlockData(v.full(), false);
                n++;
            }
        }
        state.clear();
        return n;
    }

    // ── 보석 결정 (ItemDisplay, persistent false) ───────────────────────

    void respawnDisplays(MineLevel l) {
        World w = module.world();
        if (w == null) return;
        String prefix = "L" + l.n + ":";
        for (ItemDisplay d : w.getEntitiesByClass(ItemDisplay.class)) {
            String tag = d.getPersistentDataContainer().get(nodeKey, PersistentDataType.STRING);
            if (tag != null && tag.startsWith(prefix)) d.remove();
        }
        displays.keySet().removeIf(k -> k.startsWith(prefix));
        for (MineLevel.Vein g : l.gems) if (!state.isDepleted(g.key())) spawnDisplay(w, g);
    }

    void removeAllDisplays() {
        World w = module.world();
        if (w != null) {
            for (ItemDisplay d : w.getEntitiesByClass(ItemDisplay.class)) {
                if (d.getPersistentDataContainer().has(nodeKey, PersistentDataType.STRING)) d.remove();
            }
        }
        displays.clear();
    }

    /** 사라진 결정을 다시 놓기 (30초 정리 때). */
    int ensureDisplays() {
        World w = module.world();
        if (w == null) return 0;
        int n = 0;
        for (MineLevel.Vein g : byKey.values()) {
            if (!g.gem() || state.isDepleted(g.key())) continue;
            UUID id = displays.get(g.key());
            Entity e = id == null ? null : Bukkit.getEntity(id);
            if (e == null || !e.isValid()) {
                spawnDisplay(w, g);
                n++;
            }
        }
        return n;
    }

    int displayCount() {
        int n = 0;
        for (UUID id : displays.values()) {
            Entity e = Bukkit.getEntity(id);
            if (e != null && e.isValid()) n++;
        }
        return n;
    }

    private void spawnDisplay(World w, MineLevel.Vein g) {
        removeDisplay(g.key());
        MineBlueprint.Node a = g.at();
        Location at = new Location(w, a.x() + 0.5 + a.fx() * 0.5, a.y() + 0.5 + a.fy() * 0.5, a.z() + 0.5 + a.fz() * 0.5);
        String model = g.node().nodeModel();
        ItemStack item = ItemStack.of(Material.AMETHYST_SHARD);
        if (model != null && !model.isBlank()) item.setData(DataComponentTypes.ITEM_MODEL, Key.key(model));
        Quaternionf q = rotation(a.fx(), a.fy(), a.fz());
        try {
            ItemDisplay d = w.spawn(at, ItemDisplay.class, e -> {
                e.setItemStack(item);
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.NONE);
                e.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(1.25f, 1.25f, 1.25f), new Quaternionf()));
                e.setBrightness(new Display.Brightness(11, 0));
                e.setViewRange(0.6f);
                e.setShadowRadius(0f);
                e.setPersistent(false);
                e.getPersistentDataContainer().set(nodeKey, PersistentDataType.STRING, "L" + g.level().n + ":" + a.index());
            });
            displays.put(g.key(), d.getUniqueId());
        } catch (Throwable t) {
            Log.warnOnce("mine-display", "[광산] 보석 결정을 놓지 못했습니다: " + t.getMessage());
        }
    }

    /** 모델 +y → 바깥면 법선. */
    static Quaternionf rotation(int fx, int fy, int fz) {
        if (fy > 0) return new Quaternionf();
        if (fy < 0) return new Quaternionf(new AxisAngle4f((float) Math.PI, 1, 0, 0));
        if (fz > 0) return new Quaternionf(new AxisAngle4f((float) (Math.PI / 2), 1, 0, 0));
        if (fz < 0) return new Quaternionf(new AxisAngle4f((float) (-Math.PI / 2), 1, 0, 0));
        if (fx > 0) return new Quaternionf(new AxisAngle4f((float) (-Math.PI / 2), 0, 0, 1));
        return new Quaternionf(new AxisAngle4f((float) (Math.PI / 2), 0, 0, 1));
    }

    private void removeDisplay(String key) {
        UUID id = displays.remove(key);
        if (id == null) return;
        Entity e = Bukkit.getEntity(id);
        if (e != null) e.remove();
    }

    // ── 현황 ────────────────────────────────────────────────────────────

    /** 층 n: [광맥 다 참, 광맥 전체, 보석 다 참, 보석 전체]. */
    int[] status(MineLevel l) {
        int vFull = 0, gFull = 0;
        for (MineLevel.Vein v : l.veins) if (!state.isDepleted(v.key())) vFull++;
        for (MineLevel.Vein g : l.gems) if (!state.isDepleted(g.key())) gFull++;
        return new int[] {vFull, l.veins.size(), gFull, l.gems.size()};
    }

    /** 층 n 에서 가장 먼저 다시 찰 광맥까지 초 (빈 광맥이 없으면 0). */
    double nextRefill(MineLevel l) {
        int miners = miners();
        double best = 0;
        for (MineLevel.Vein v : l.veins) {
            double s = state.etaSeconds(v.key(), miners);
            if (s > 0 && (best == 0 || s < best)) best = s;
        }
        return best;
    }

    static String name(MineDef.Node n) { return n == null ? "?" : n.name(); }
}
