package kr.labyrinth.dungeon;

import java.awt.Color;
import java.io.File;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.MapMeta;
import org.bukkit.map.MapCanvas;
import org.bukkit.map.MapRenderer;
import org.bukkit.map.MapView;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.Plugin;

/**
 * 손에 드는 탐험 지도 (0.3.7 주인 결정 "진짜 지도 아이템"). 채팅 지도({@link ExplorationMap})와 같은 격자를 128×128 지도에 그린다.
 * 지도 하나(MapView)를 모두가 함께 쓰고, 그리는 것은 보는 사람마다 따로 한다 (그 사람의 층 · 그 사람 위치 · 파티원).
 * 지도 번호는 plugins/Labyrinth/explore-map.yml 에 적어 두고 켤 때마다 그리개를 다시 붙인다. 미궁 밖에서는 빈 양피지.
 */
public final class ExplorationMapItem {

    /** 다시 그리는 간격 (틱). 지도는 바뀐 칸만 보내므로 비용은 그리기 계산뿐이다. */
    static final int REDRAW_TICKS = 10;
    static final int PARCHMENT = 0x2a2431;
    static final int FRAME = 0x6f6979;

    private final Plugin plugin;
    private final NamespacedKey key;
    private final Function<Player, FloorState> floorOf;
    private MapView view;

    public ExplorationMapItem(Plugin plugin, Function<Player, FloorState> floorOf) {
        this.plugin = plugin;
        this.key = new NamespacedKey(plugin, "explore_map");
        this.floorOf = floorOf;
    }

    /** 켤 때: 적어 둔 지도를 불러오거나 새로 만들고, 바닐라 그리개를 떼고 우리 그리개를 붙인다. */
    public void enable() {
        try {
            File f = new File(plugin.getDataFolder(), "explore-map.yml");
            YamlConfiguration y = f.isFile() ? YamlConfiguration.loadConfiguration(f) : new YamlConfiguration();
            int id = y.getInt("map_id", -1);
            MapView v = id >= 0 ? Bukkit.getMap(id) : null;
            if (v == null) {
                World w = Bukkit.getWorlds().get(0);
                v = Bukkit.createMap(w);
                y.set("map_id", v.getId());
                y.save(f);
            }
            for (MapRenderer r : List.copyOf(v.getRenderers())) v.removeRenderer(r);
            v.setTrackingPosition(false);
            v.setUnlimitedTracking(false);
            v.addRenderer(new Renderer());
            view = v;
            Log.info("[탐험 지도] 지도 #" + v.getId() + " 준비");
        } catch (Exception ex) {
            Log.error("탐험 지도 준비 실패 — 채팅 지도만 씁니다", ex);
            view = null;
        }
    }

    public boolean ready() {
        return view != null;
    }

    /** 이 아이템이 탐험 지도인가. */
    public boolean isMap(ItemStack it) {
        return it != null && it.getType() == Material.FILLED_MAP && it.hasItemMeta()
                && it.getItemMeta().getPersistentDataContainer().has(key, PersistentDataType.BYTE);
    }

    /** 가방에 탐험 지도가 없으면 하나 준다. @return 새로 줬으면 true */
    public boolean give(Player p) {
        if (view == null) return false;
        for (ItemStack it : p.getInventory().getContents()) if (isMap(it)) return false;
        ItemStack map = new ItemStack(Material.FILLED_MAP);
        MapMeta meta = (MapMeta) map.getItemMeta();
        meta.setMapView(view);
        meta.displayName(Text.mm("<!italic><#7fd8ff><b>탐험 지도</b>"));
        meta.lore(List.of(Text.mm("<!italic><gray>손에 들면 지금 층에서 파티가 지나온 길이 보입니다."),
                Text.mm("<!italic><white>■</white><gray> 나  <#5ef2ff>■</#5ef2ff><gray> 동료  <#ff2a2a>■</#ff2a2a><gray> 수호자의 문"),
                Text.mm("<!italic><dark_gray>들고 우클릭하면 채팅에 방 이름까지 나옵니다.")));
        meta.getPersistentDataContainer().set(key, PersistentDataType.BYTE, (byte) 1);
        map.setItemMeta(meta);
        Map<Integer, ItemStack> left = p.getInventory().addItem(map);
        if (!left.isEmpty()) {
            Text.error(p, "가방이 가득 차서 탐험 지도를 못 받았습니다.");
            return false;
        }
        Text.send(p, "<#7fd8ff>탐험 지도</#7fd8ff><gray>를 받았습니다. 손에 들면 지금 층이 보입니다.");
        return true;
    }

    /** 격자 [줄][칸] 을 128×128 안에 맞추는 칸 크기와 여백. */
    record Fit(int px, int offX, int offY) {
        static Fit of(int rows, int cols) {
            int px = Math.max(1, Math.min(124 / Math.max(1, cols), 124 / Math.max(1, rows)));
            return new Fit(px, (128 - px * cols) / 2, (128 - px * rows) / 2);
        }
    }

    /** 격자 색을 지도 칸(128×128, 0xRRGGBB)으로 — 시험할 수 있게 따로 둔다. */
    static int[] pixels(int[][] grid) {
        int[] px = new int[128 * 128];
        java.util.Arrays.fill(px, PARCHMENT);
        if (grid == null || grid.length == 0) return px;
        Fit fit = Fit.of(grid.length, grid[0].length);
        int x0 = fit.offX() - 1, y0 = fit.offY() - 1, x1 = fit.offX() + fit.px() * grid[0].length, y1 = fit.offY() + fit.px() * grid.length;
        for (int x = Math.max(0, x0); x <= Math.min(127, x1); x++) {
            if (y0 >= 0) px[y0 * 128 + x] = FRAME;
            if (y1 <= 127) px[y1 * 128 + x] = FRAME;
        }
        for (int y = Math.max(0, y0); y <= Math.min(127, y1); y++) {
            if (x0 >= 0) px[y * 128 + x0] = FRAME;
            if (x1 <= 127) px[y * 128 + x1] = FRAME;
        }
        for (int r = 0; r < grid.length; r++) {
            for (int q = 0; q < grid[r].length; q++) {
                int c = grid[r][q];
                for (int dy = 0; dy < fit.px(); dy++) {
                    int y = fit.offY() + r * fit.px() + dy;
                    if (y < 0 || y > 127) continue;
                    for (int dx = 0; dx < fit.px(); dx++) {
                        int x = fit.offX() + q * fit.px() + dx;
                        if (x >= 0 && x <= 127) px[y * 128 + x] = c;
                    }
                }
            }
        }
        return px;
    }

    private final class Renderer extends MapRenderer {
        private final Map<UUID, Integer> lastTick = new HashMap<>();
        private final Map<UUID, Integer> lastHash = new HashMap<>();

        Renderer() {
            super(true);
        }

        @Override
        public void render(MapView map, MapCanvas canvas, Player player) {
            int now = Bukkit.getCurrentTick();
            Integer last = lastTick.get(player.getUniqueId());
            if (last != null && now - last < REDRAW_TICKS) return;
            lastTick.put(player.getUniqueId(), now);
            int[][] grid = null;
            try {
                FloorState fs = floorOf.apply(player);
                if (fs != null && fs.ready()) grid = ExplorationMap.colors(fs, player);
            } catch (RuntimeException ex) {
                grid = null;
            }
            int[] px = pixels(grid);
            int h = java.util.Arrays.hashCode(px);
            Integer prev = lastHash.put(player.getUniqueId(), h);
            if (prev != null && prev == h) return;
            for (int y = 0; y < 128; y++) {
                for (int x = 0; x < 128; x++) canvas.setPixelColor(x, y, new Color(px[y * 128 + x]));
            }
        }
    }
}
