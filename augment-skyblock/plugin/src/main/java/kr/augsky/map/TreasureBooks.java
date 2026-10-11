package kr.augsky.map;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.Fx;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.Chest;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.world.LootGenerateEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;

/**
 * 맵에 숨겨 둔 마법서. 수선은 보스·바닐라 낚시·주민으로도 얻지만, 보스 전에도 몇 권은 손에 들어오게
 * 몇몇 섬의 상자를 처음 열 때 한 권씩 넣는다 (폐허·보라 폐허·난파선은 수선, 거미 굴은 무한).
 * 섬 상자는 맵을 지을 때 채워져 바닐라 전리품 표가 없어서 LootGenerateEvent 가 오지 않으므로,
 * 이미 지어진 맵에도 들어가도록 여는 순간 넣는다. 섬마다 한 번뿐: 표시를 상자가 아니라 월드에 남겨서 상자를 부수고 다시 놓아도 또 나오지 않는다.
 * <p>
 * 상자 자리: 맵 배치(MapBuilder.plan)는 판이 바뀌면 달라지는데 이미 지은 맵의 섬은 그대로라, 지금 배치로만 계산하면 예전 맵에서는 못 찾는다.
 * 그래서 지금 친구들이 쓰는 맵의 자리를 고정해 두고(LEGACY), 서버를 켤 때 두 후보 중 실제로 상자가 있는 쪽을 월드에 적어 둔다.
 * 한 번 적은 뒤에는 배치가 또 바뀌어도 그 월드는 적어 둔 자리를 쓴다. 아직 못 정했으면(맵을 짓기 전) 두 후보를 다 본다.
 */
public final class TreasureBooks implements Listener {
    /** 책을 넣을 상자 하나: 섬 종류와 섬 중심(표시 키), 상자 블록 자리. */
    private record Spot(String kind, int ix, int iz, int x, int y, int z) {
        NamespacedKey mark() {
            return Keys.of("book_" + kind + "_" + ix + "_" + iz);
        }

        String island() {
            return kind + "_" + ix + "_" + iz;
        }

        long key() {
            return Block.getBlockKey(x, y, z);
        }

        String book() {
            return kind.equals("spider_den") ? "infinity" : "mending";
        }

        String msg() {
            return kind.equals("spider_den") ? INFINITY : MENDING;
        }

        static Spot parse(String s) {
            String[] p = s.split(":");
            if (p.length != 6) return null;
            try {
                return new Spot(p[0], Integer.parseInt(p[1]), Integer.parseInt(p[2]),
                        Integer.parseInt(p[3]), Integer.parseInt(p[4]), Integer.parseInt(p[5]));
            } catch (NumberFormatException e) {
                return null;
            }
        }

        @Override
        public String toString() {
            return kind + ":" + ix + ":" + iz + ":" + x + ":" + y + ":" + z;
        }
    }

    private static final String MENDING = "<#9ad8ff>✦ 낡은 책 사이에 수선 마법서가 끼어 있다";
    private static final String INFINITY = "<#c8b8ff>✦ 거미줄에 얽힌 무한 마법서가 끼어 있다";
    private static final NamespacedKey BASTION = NamespacedKey.minecraft("chests/bastion_treasure");
    /** 이 월드에서 쓰기로 정한 상자 자리 ("종류:섬x:섬z:x:y:z;..."). */
    private static final NamespacedKey PINNED = Keys.of("book_spots");

    /**
     * 지금 친구들이 쓰는 맵(제단 배치를 바꾸기 전 배치로 지음)의 상자 자리. 그 맵에서 직접 확인한 좌표다.
     * 배치 코드가 바뀌면 plan() 으로는 이 자리가 다시 나오지 않으므로 고정해 둔다.
     */
    private static final List<Spot> LEGACY = List.of(
            new Spot("ruin", 288, -519, 288, 69, -518),
            new Spot("purpur_ruin", -446, -360, -447, 104, -361),
            new Spot("purpur_ruin", -204, -370, -205, 93, -371),
            new Spot("shipwreck", -366, 499, -366, 61, 495),
            new Spot("spider_den", -87, -117, -88, 67, -118),
            new Spot("spider_den", 312, 295, 311, 70, 294));

    private final AugSky plugin;
    /** 상자 블록 키 → 자리. 처음 쓸 때 한 번 계산한다 */
    private Map<Long, Spot> spots;

    public TreasureBooks(AugSky plugin) {
        this.plugin = plugin;
        // 월드가 다 불러와진 뒤에 자리를 정한다
        Bukkit.getScheduler().runTask(plugin, this::pin);
    }

    /** 지금 맵 배치로 계산한 상자 자리 (이 판의 MapBuilder 로 지은 맵). */
    private static List<Spot> current() {
        List<Spot> out = new ArrayList<>();
        for (MapBuilder.Isle is : MapBuilder.plan()) {
            int x = is.x(), y = IslandKinds.buildY(is), z = is.z();
            switch (is.kind()) {
                // 상자 위치는 IslandKinds 의 ruin(), purpurRuin(), spiderDen(), shipwreck() 와 같아야 한다
                case "ruin" -> out.add(new Spot(is.kind(), x, z, x, y + 1, z + 1));
                case "purpur_ruin", "spider_den" -> out.add(new Spot(is.kind(), x, z, x - 1, y + 1, z - 1));
                case "shipwreck" -> {
                    // 고물 상자: 시작 섬 반대쪽(u)으로 t0+1 칸. 선체 길이 9~11 이라 t 는 -4 또는 -3
                    int[] u = Math.abs(x) >= Math.abs(z) ? new int[]{x > 0 ? 1 : -1, 0} : new int[]{0, z > 0 ? 1 : -1};
                    for (int t : new int[]{-4, -3}) out.add(new Spot(is.kind(), x, z, x + u[0] * t, y + 1, z + u[1] * t));
                }
                default -> {
                }
            }
        }
        return out;
    }

    private static Map<Long, Spot> index(List<Spot> list) {
        Map<Long, Spot> m = new HashMap<>();
        for (Spot s : list) m.putIfAbsent(s.key(), s);
        return m;
    }

    private static World world() {
        return Bukkit.getWorlds().get(0);
    }

    private Map<Long, Spot> spots() {
        if (spots != null) return spots;
        String saved = world().getPersistentDataContainer().get(PINNED, PersistentDataType.STRING);
        if (saved != null) {
            List<Spot> list = new ArrayList<>();
            for (String s : saved.split(";")) {
                Spot sp = Spot.parse(s);
                if (sp != null) list.add(sp);
            }
            spots = index(list);
        } else {
            // 아직 못 정했다: 두 후보를 다 본다 (다른 맵의 그 좌표에 마침 상자가 있을 일은 거의 없다)
            List<Spot> both = new ArrayList<>(current());
            both.addAll(LEGACY);
            spots = index(both);
        }
        return spots;
    }

    /**
     * 두 후보(지금 배치, LEGACY) 중 실제 상자가 있는 섬이 많은 쪽을 이 월드의 자리로 적어 둔다.
     * 청크는 비동기로 불러오고 새로 만들지 않는다. 둘 다 없으면(맵을 아직 안 지었거나 상자를 다 부쉈다) 다음에 켤 때 다시 본다.
     */
    private void pin() {
        World w = world();
        if (w.getPersistentDataContainer().has(PINNED, PersistentDataType.STRING)) return;
        List<Spot> now = current();
        Map<Long, List<Spot>> byChunk = new LinkedHashMap<>();
        for (List<Spot> list : List.of(now, LEGACY))
            for (Spot s : list) byChunk.computeIfAbsent(Chunk.getChunkKey(s.x() >> 4, s.z() >> 4), k -> new ArrayList<>()).add(s);
        Set<Long> chests = new HashSet<>();
        List<CompletableFuture<?>> loads = new ArrayList<>();
        for (List<Spot> in : byChunk.values()) {
            Spot first = in.get(0);
            // 결과는 메인 스레드에서 온다
            loads.add(w.getChunkAtAsync(first.x() >> 4, first.z() >> 4, false).thenAccept(ch -> {
                if (ch == null) return;
                for (Spot s : in)
                    if (ch.getBlock(s.x() & 15, s.y(), s.z() & 15).getType() == Material.CHEST) chests.add(s.key());
            }));
        }
        CompletableFuture.allOf(loads.toArray(new CompletableFuture[0])).whenComplete((v, err) -> Bukkit.getScheduler().runTask(plugin, () -> {
            if (err != null) {
                plugin.getLogger().warning("마법서 상자 자리를 확인하지 못했습니다: " + err);
                return;
            }
            int hitNow = islandsWithChest(now, chests), hitOld = islandsWithChest(LEGACY, chests);
            if (hitNow == 0 && hitOld == 0) return;
            boolean useNow = hitNow >= hitOld;
            List<Spot> chosen = useNow ? now : LEGACY;
            List<String> parts = new ArrayList<>();
            for (Spot s : chosen) parts.add(s.toString());
            w.getPersistentDataContainer().set(PINNED, PersistentDataType.STRING, String.join(";", parts));
            spots = index(chosen);
            plugin.getLogger().info("마법서 상자 자리: " + (useNow ? "지금 맵 배치" : "예전 맵 배치(고정 좌표)") + "로 정함 (상자가 남은 섬 "
                    + Math.max(hitNow, hitOld) + "곳)");
        }));
    }

    private static int islandsWithChest(List<Spot> list, Set<Long> chests) {
        Set<String> isles = new HashSet<>();
        for (Spot s : list) if (chests.contains(s.key())) isles.add(s.island());
        return isles.size();
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent e) {
        if (!(e.getPlayer() instanceof Player p) || p.getGameMode() == GameMode.SPECTATOR) return;
        if (!(e.getInventory().getHolder(false) instanceof Chest chest)) return;
        World w = chest.getWorld();
        if (!w.equals(world())) return;
        Spot s = spots().get(Block.getBlockKey(chest.getX(), chest.getY(), chest.getZ()));
        if (s == null) return;
        var pdc = w.getPersistentDataContainer();
        if (pdc.has(s.mark(), PersistentDataType.BYTE)) return;
        ItemStack book = plugin.items().book(s.book(), false);
        if (book == null) return;
        pdc.set(s.mark(), PersistentDataType.BYTE, (byte) 1);
        // 상자가 꽉 찼으면 여는 사람에게 준다
        if (!e.getInventory().addItem(book).isEmpty()) Items.give(p, book);
        p.sendActionBar(Text.mm(s.msg()));
        Fx.sound(chest.getLocation().add(0.5, 0.5, 0.5), "item.book.page_turn", 1f, 1f);
    }

    /** 네더의 보루 보물 상자(바닐라 전리품 표)에는 수선 마법서를 하나 더 넣는다. */
    @EventHandler(ignoreCancelled = true)
    public void onLoot(LootGenerateEvent e) {
        if (!BASTION.equals(e.getLootTable().getKey())) return;
        ItemStack book = plugin.items().book("mending", false);
        if (book != null) e.getLoot().add(book);
    }
}
