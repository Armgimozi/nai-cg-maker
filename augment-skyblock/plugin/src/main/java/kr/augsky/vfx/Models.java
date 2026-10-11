package kr.augsky.vfx;

import kr.augsky.AugSky;
import org.bukkit.Color;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.components.CustomModelDataComponent;

import java.io.InputStream;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * 리소스팩에 실제로 들어 있는 이펙트 모델(augsky:vfx/*) 목록과, 색을 입힌 아이템 캐시.
 * 팩에 없는 모델을 띄우면 보라·검정 상자가 보이므로, jar 안 pack.zip 을 열어 있는 것만 쓴다.
 */
public final class Models {
    private final Set<String> have = new HashSet<>();
    private final Map<String, ItemStack> cache = new LinkedHashMap<>(256, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, ItemStack> e) {
            return size() > 600;
        }
    };

    Models(AugSky plugin) {
        try (InputStream in = plugin.getResource("pack.zip")) {
            if (in == null) return;
            try (ZipInputStream zin = new ZipInputStream(in)) {
                ZipEntry e;
                String pre = "assets/augsky/items/vfx/";
                while ((e = zin.getNextEntry()) != null) {
                    String n = e.getName();
                    if (n.startsWith(pre) && n.endsWith(".json")) have.add(n.substring(pre.length(), n.length() - 5));
                }
            }
        } catch (Exception ex) {
            plugin.getLogger().warning("이펙트 모델 목록을 읽지 못했습니다: " + ex.getMessage());
        }
    }

    public boolean has(String id) {
        return id != null && have.contains(id);
    }

    public int count() {
        return have.size();
    }

    /** 앞에서부터 팩에 있는 첫 모델. 없으면 null */
    public String pick(String... ids) {
        for (String id : ids) if (has(id)) return id;
        return null;
    }

    /** 지금보다 level 단계 흐린 모델 (원본 → _dim → _faint). 더 흐린 것이 없으면 null */
    public String dim(String id, int level) {
        if (id == null) return null;
        String base = base(id);
        int cur = id.endsWith("_faint") ? 2 : id.endsWith("_dim") ? 1 : 0;
        for (int want = Math.min(2, cur + level); want > cur; want--) {
            String m = want == 2 ? base + "_faint" : base + "_dim";
            if (has(m)) return m;
        }
        return null;
    }

    static String base(String id) {
        if (id.endsWith("_dim")) return id.substring(0, id.length() - 4);
        if (id.endsWith("_faint")) return id.substring(0, id.length() - 6);
        return id;
    }

    ItemStack stack(String id, Color a, Color b, Color c) {
        String key = id + '/' + a.asRGB() + '/' + b.asRGB() + '/' + c.asRGB();
        ItemStack it = cache.get(key);
        if (it == null) {
            it = new ItemStack(Material.PAPER);
            ItemMeta meta = it.getItemMeta();
            meta.setItemModel(new NamespacedKey("augsky", "vfx/" + id));
            CustomModelDataComponent cmd = meta.getCustomModelDataComponent();
            cmd.setColors(List.of(a, b, c));
            meta.setCustomModelDataComponent(cmd);
            it.setItemMeta(meta);
            cache.put(key, it);
        }
        return it;
    }
}
