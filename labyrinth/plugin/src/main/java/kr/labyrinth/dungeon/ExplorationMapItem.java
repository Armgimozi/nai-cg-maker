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
import net.kyori.adventure.text.Component;
import org.bukkit.map.MapCanvas;
import org.bukkit.map.MapCursor;
import org.bukkit.map.MapCursorCollection;
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
    /** 0.3.7.1 가독성: 밝은 종이 · 진한 잉크 테두리 · 방 사이 통로 막대 · 내 위치는 바닐라 화살표 (주인 의견 "가독성이 후져"). */
    static final int PARCHMENT = 0xe6d8b0;
    static final int INK = 0x3b2a1a;
    static final int HINT_INK = 0xa08c64;
    static final int PASS = 0x6b5338;
    static final int DOOR = 0xc01818;

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
                Text.mm("<!italic><white>▲</white><gray> 나 (보는 쪽)  <#5ea8ff>◆</#5ea8ff><gray> 동료  <#ff2a2a>■</#ff2a2a><gray> 수호자의 문"),
                Text.mm("<!italic><#ff6b6b>■</#ff6b6b><gray>전투 <#ffd36b>■</#ffd36b><gray>보물 <#c79bff>■</#c79bff><gray>시련 <#7fe07f>■</#7fe07f><gray>휴식 · 흐린 색 = 정리한 방"),
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

    /** 셀 n×n 을 128×128 안에: 방 = 3k 칸, 방 사이 = k 칸, 맨 아래에 보스 문 자리 (k + k). */
    record Fit(int k, int offX, int offY) {
        static Fit of(int n) {
            int m = Math.max(1, n);
            int k = Math.max(1, 118 / (4 * m + 1));
            int span = k * (4 * m - 1);
            return new Fit(k, (128 - span) / 2, (128 - span - 2 * k) / 2);
        }

        int cell() { return 3 * k; }

        int left(int x) { return offX + x * 4 * k; }

        int top(int z) { return offY + z * 4 * k; }
    }

    /** 층 모양을 지도 칸(128×128, 0xRRGGBB)으로 — 시험할 수 있게 따로 둔다. null = 빈 종이. */
    static int[] pixels(ExplorationMap.Shape sh) {
        int[] px = new int[128 * 128];
        java.util.Arrays.fill(px, PARCHMENT);
        if (sh == null || sh.n() <= 0) return px;
        int n = sh.n();
        Fit f = Fit.of(n);
        int cs = f.cell(), k = f.k(), bar = Math.max(1, cs / 3), mid = (cs - bar) / 2;
        for (int c = 0; c < n * n; c++) {
            int x = c % n, z = c / n, l = f.left(x), t = f.top(z);
            if (x + 1 < n && sh.east()[c] != 0) rect(px, l + cs, t + mid, k, bar, sh.east()[c] == 2 ? PASS : HINT_INK);
            if (z + 1 < n && sh.south()[c] != 0) rect(px, l + mid, t + cs, bar, k, sh.south()[c] == 2 ? PASS : HINT_INK);
        }
        for (int c = 0; c < n * n; c++) {
            int x = c % n, z = c / n, l = f.left(x), t = f.top(z), v = sh.fill()[c];
            if (v == -1) continue;
            if (v == -2) {
                outline(px, l, t, cs, cs, HINT_INK);
                continue;
            }
            rect(px, l, t, cs, cs, v);
            outline(px, l, t, cs, cs, INK);
        }
        if (sh.bossCell() >= 0 && sh.bossCell() < n * n) {
            int x = sh.bossCell() % n, z = sh.bossCell() / n, l = f.left(x), t = f.top(z) + cs;
            rect(px, l + mid, t, bar, k, PASS);
            int w = Math.max(3, cs * 2 / 3), h = Math.max(2, k + k / 2);
            rect(px, l + (cs - w) / 2, t + k, w, h, DOOR);
            outline(px, l + (cs - w) / 2, t + k, w, h, INK);
        }
        return px;
    }

    private static void rect(int[] px, int x0, int y0, int w, int h, int color) {
        for (int y = Math.max(0, y0); y < Math.min(128, y0 + h); y++) {
            for (int x = Math.max(0, x0); x < Math.min(128, x0 + w); x++) px[y * 128 + x] = color;
        }
    }

    private static void outline(int[] px, int x0, int y0, int w, int h, int color) {
        rect(px, x0, y0, w, 1, color);
        rect(px, x0, y0 + h - 1, w, 1, color);
        rect(px, x0, y0, 1, h, color);
        rect(px, x0 + w - 1, y0, 1, h, color);
    }

    /** 지도 위 점 (칸 0~127) → 표시 좌표 (-128 ~ 127). */
    static byte cursorCoord(double pixel) {
        return (byte) Math.max(-128, Math.min(127, Math.round(pixel * 2 - 128)));
    }

    /** 바닐라 화살표 방향 (0 = 위 = 북쪽, 시계 방향 16칸) ← 마인크래프트 yaw (0 = 남쪽). */
    static byte direction(float yaw) {
        double d = ((yaw + 180.0) % 360.0 + 360.0) % 360.0;
        return (byte) (Math.round(d / 22.5) & 15);
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
            ExplorationMap.Shape sh = null;
            try {
                FloorState fs = floorOf.apply(player);
                if (fs != null && fs.ready()) sh = ExplorationMap.shape(fs, player);
            } catch (RuntimeException ex) {
                sh = null;
            }
            cursors(canvas, sh);
            int[] px = pixels(sh);
            int h = java.util.Arrays.hashCode(px);
            Integer prev = lastHash.put(player.getUniqueId(), h);
            if (prev != null && prev == h) return;
            for (int y = 0; y < 128; y++) {
                for (int x = 0; x < 128; x++) canvas.setPixelColor(x, y, new Color(px[y * 128 + x]));
            }
        }

        /** 내 위치 = 바닐라 흰 화살표 (보는 쪽), 동료 = 파란 표 + 이름. */
        private void cursors(MapCanvas canvas, ExplorationMap.Shape sh) {
            MapCursorCollection cur = canvas.getCursors();
            while (cur.size() > 0) cur.removeCursor(cur.getCursor(0));
            if (sh == null) return;
            Fit f = Fit.of(sh.n());
            for (int i = 0; i < sh.allies().size(); i++) {
                int[] a = sh.allies().get(i);
                double x = f.left(a[0] % sh.n()) + f.cell() * a[1] / 1000.0, y = f.top(a[0] / sh.n()) + f.cell() * a[2] / 1000.0;
                cur.addCursor(new MapCursor(cursorCoord(x), cursorCoord(y), (byte) 0, MapCursor.Type.BLUE_MARKER, true,
                        Component.text(sh.allyNames().get(i))));
            }
            if (sh.me() >= 0) {
                double x = f.left(sh.me() % sh.n()) + f.cell() * sh.meX(), y = f.top(sh.me() / sh.n()) + f.cell() * sh.meZ();
                cur.addCursor(new MapCursor(cursorCoord(x), cursorCoord(y), direction(sh.yaw()), MapCursor.Type.PLAYER, true));
            }
        }
    }
}
