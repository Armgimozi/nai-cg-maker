package kr.souls.combat;

import com.destroystokyo.paper.profile.PlayerProfile;
import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.DyedItemColor;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.ItemStack;
import org.bukkit.profile.PlayerTextures;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.URL;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 구르기 대역의 옷 색 (3.3 "보이는 모습"). 대역 몸 모형 (팩 souls:roll_*) 은 밝은 바탕에 다섯 칸을 물들인다:
 * 0 몸통, 1 소매 (윗팔), 2 손 (아랫팔), 3 바지, 4 신. 그 색을 그 사람 스킨에서 고르고, 갑옷을 입었으면 그 칸은 갑옷 색.
 *
 * <ul>
 *   <li>스킨: 들어올 때 (Roll 의 접속 처리, 플러그인을 다시 켜면 접속 중인 사람 모두) 프로필의 스킨 주소에서 PNG 를 비동기로 받아 고른다 (정품 접속). 주소가 없으면 (오프라인 접속, 스킨을
 *       고르지 않은 계정) 클라이언트가 그리는 바닐라 기본 스킨 18 개 가운데 UUID 로 고른 것: 그 18 개의 색은 팩 생성기가
 *       클라이언트 jar 에서 뽑아 둔 자원 roll_skins.yml (pack/roll_figure.py skin_table). 받기 전이나 실패하면 그 표, 표도 없으면
 *       팩 정의의 기본색 (팔레트).</li>
 *   <li>고르는 셈 (pack/roll_figure.py skin_colors 와 같다): 그 부위를 네 옆면으로 두른 띠의 불투명 픽셀 (덧옷 층이 불투명하면
 *       그것) 을 채널마다 8 단위로 묶어 가장 많은 묶음의 평균. 채도 × 0.8, 밝기가 77/255 보다 어두우면 끌어올린다 (심층암 바닥과
 *       갈리게). 정수 셈이라 파이썬 표와 같은 값이 나온다.</li>
 *   <li>갑옷: 가슴 → 몸통·소매, 다리 → 바지, 신 → 신, 머리 → 투구 껍데기 (대역 souls:roll_helm). 물들인 가죽은 그 색, 나머지는
 *       재료마다 팔레트에 가까운 색 (쇠는 화면에서 재 3 의 회색이 되게).</li>
 * </ul>
 */
public final class SkinTint {
    /** 기본 스킨 차례 (클라이언트 DefaultPlayerSkin: UUID.hashCode() floorMod 18 [확인 (클라이언트 jar)]). 표가 이 차례로 적혀 있다 */
    static final int DEFAULT_SKINS = 18;
    /** 칸: x0, y0, x1, y1 (64×64 스킨). 덧옷 층은 y + 16 */
    private static final int[][] REGIONS = {{16, 20, 40, 32}, {40, 20, 56, 26}, {40, 26, 56, 32}, {0, 20, 16, 28}, {0, 28, 16, 32}};
    private static final int MIN_VALUE = 77;

    private final Souls plugin;
    private final Map<UUID, int[]> fetched = new ConcurrentHashMap<>();
    private final List<int[]> defaults = new ArrayList<>();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5))
            .followRedirects(HttpClient.Redirect.NORMAL).build();

    public SkinTint(Souls plugin) {
        this.plugin = plugin;
        try (InputStream in = plugin.getResource("roll_skins.yml")) {
            if (in != null) {
                YamlConfiguration y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
                for (Object row : y.getList("skins", List.of())) {
                    if (!(row instanceof List<?> l) || l.size() != REGIONS.length) continue;
                    int[] c = new int[l.size()];
                    for (int i = 0; i < c.length; i++) c[i] = Integer.parseInt(String.valueOf(l.get(i)).trim(), 16);
                    defaults.add(c);
                }
            }
        } catch (Exception e) {
            plugin.getLogger().warning("roll_skins.yml 을 읽지 못했습니다: " + e);
        }
        if (defaults.size() != DEFAULT_SKINS) {
            plugin.getLogger().warning("기본 스킨 색 표가 " + defaults.size() + "줄이라 쓰지 않습니다 (구르기 대역은 팩 기본색).");
            defaults.clear();
        }
    }

    /** 대역 몸의 다섯 색 (갑옷 색이 위). 하나도 모르면 null (팩 정의의 기본색). */
    public List<Color> body(Player p) {
        int[] base = fetched.get(p.getUniqueId());
        if (base == null && !defaults.isEmpty()) base = defaults.get(Math.floorMod(p.getUniqueId().hashCode(), DEFAULT_SKINS));
        int[] c = base == null ? null : base.clone();
        EntityEquipment eq = p.getEquipment();
        Integer chest = armor(eq.getChestplate()), legs = armor(eq.getLeggings()), feet = armor(eq.getBoots());
        if (c == null && chest == null && legs == null && feet == null) return null;
        if (c == null) c = new int[]{0x6e5a48, 0x6e5a48, 0x8a8270, 0x4a3f36, 0x2b2622};   // 팩 기본색과 같다 (rust2 rust2 bone0 rust1 rust0)
        if (chest != null) c[0] = c[1] = chest;
        if (legs != null) c[3] = legs;
        if (feet != null) c[4] = feet;
        List<Color> out = new ArrayList<>(c.length);
        for (int v : c) out.add(Color.fromRGB(neutral(v & 0xffffff)));
        return out;
    }

    /** 투구 색 (투구가 없으면 null). */
    public Color helm(Player p) {
        Integer h = armor(p.getEquipment().getHelmet());
        return h == null ? null : Color.fromRGB(neutral(h));
    }

    /**
     * 물들이는 바탕 (뼈 계열, 평균 bone2 = #d6cbb0) 의 누른빛을 덜어 낸다: 물들이기는 곱하기라 회색 쇠도 누른 갈색으로, 붉은 겉옷도
     * 밤색으로 보였다 (2026-10-08 비평). 채널마다 바탕의 밝기 / 그 채널 (빨강 0.95, 초록 1.00, 파랑 1.155) 을 곱해 바탕을 곱한 결과가
     * 그 색과 같은 색상이 되게 한다 (밝기는 그대로).
     */
    static int neutral(int rgb) {
        int r = (rgb >> 16) & 255, g = (rgb >> 8) & 255, b = rgb & 255;
        r = Math.min(255, Math.round(r * 0.950f));
        b = Math.min(255, Math.round(b * 1.155f));
        return (r << 16) | (g << 8) | b;
    }

    /** 갑옷 한 점의 색. 없거나 갑옷이 아니면 null. */
    static Integer armor(ItemStack it) {
        if (it == null || it.isEmpty()) return null;
        DyedItemColor dyed = it.getData(DataComponentTypes.DYED_COLOR);
        if (dyed != null) return grade(dyed.color().asRGB());
        String m = it.getType().name();
        // 물들이는 바탕이 뼈 계열 (밝기 0.54~0.91) 이라 화면에서는 이보다 한두 단 어둡다
        if (m.startsWith("LEATHER_")) return grade(0xa06540);        // 바닐라 물들이지 않은 가죽
        if (m.startsWith("CHAINMAIL_")) return 0x8a8680;
        if (m.startsWith("IRON_")) return 0xb0aca4;                  // 화면에서 재 3 (#858079) 남짓
        if (m.startsWith("GOLDEN_")) return 0xb89a5c;                // 청동 3 보다 한 단 밝게
        if (m.startsWith("COPPER_")) return 0xa06a48;
        if (m.startsWith("DIAMOND_")) return 0x7f9a95;
        if (m.startsWith("NETHERITE_")) return 0x5c5955;             // 재 2
        if (m.equals("TURTLE_HELMET")) return 0x7a8550;
        // 그 밖에 머리·몸에 쓰는 것 (호박, 해골 머리) 은 갑옷이 아니다
        return null;
    }

    /** 나간 사람의 받은 색을 버린다. */
    public void forget(UUID id) {
        fetched.remove(id);
    }

    /** 프로필의 스킨 주소에서 받는다 (비동기, Roll 이 들어올 때 부른다). 주소가 없으면 기본 스킨 표를 쓴다. */
    public void fetch(Player p) {
        PlayerProfile prof = p.getPlayerProfile();
        PlayerTextures tex = prof.getTextures();
        URL url = tex.getSkin();
        if (url == null) return;
        boolean slim = tex.getSkinModel() == PlayerTextures.SkinModel.SLIM;
        UUID id = p.getUniqueId();
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            try {
                HttpResponse<InputStream> r = http.send(HttpRequest.newBuilder(URI.create(url.toString()))
                        .timeout(Duration.ofSeconds(8)).GET().build(), HttpResponse.BodyHandlers.ofInputStream());
                if (r.statusCode() != 200) return;
                BufferedImage img;
                try (InputStream in = r.body()) {
                    img = ImageIO.read(in);
                }
                if (img == null || img.getWidth() != 64 || (img.getHeight() != 64 && img.getHeight() != 32)) return;
                int[] c = colors(img, slim);
                if (c != null) fetched.put(id, c);
            } catch (Exception ex) {
                plugin.getLogger().fine("스킨을 받지 못했습니다 (" + id + "): " + ex);
            }
        });
    }

    /** 스킨 → 다섯 색. 어느 칸이 비면 (투명) 그 칸은 이웃 칸 색. 모두 비면 null. */
    static int[] colors(BufferedImage img, boolean slim) {
        boolean layer2 = img.getHeight() >= 64;
        int[] out = new int[REGIONS.length];
        boolean any = false;
        for (int k = 0; k < REGIONS.length; k++) {
            int[] r = REGIONS[k];
            int x1 = slim && r[0] == 40 ? 54 : r[2];
            Map<Integer, int[]> groups = new LinkedHashMap<>();   // 묶음 → {수, r 합, g 합, b 합}
            for (int y = r[1]; y < r[3]; y++) {
                for (int x = r[0]; x < x1; x++) {
                    int p = img.getRGB(x, y);
                    if (layer2) {
                        int o = img.getRGB(x, y + 16);
                        if ((o >>> 24) >= 128) p = o;
                    }
                    if ((p >>> 24) < 128) continue;
                    int rr = (p >> 16) & 255, gg = (p >> 8) & 255, bb = p & 255;
                    int key = ((rr >> 3) << 10) | ((gg >> 3) << 5) | (bb >> 3);
                    int[] g = groups.computeIfAbsent(key, q -> new int[4]);
                    g[0]++;
                    g[1] += rr;
                    g[2] += gg;
                    g[3] += bb;
                }
            }
            int[] best = null;
            for (int[] g : groups.values()) if (best == null || g[0] > best[0]) best = g;
            if (best == null) {
                out[k] = -1;
                continue;
            }
            any = true;
            out[k] = grade(((best[1] / best[0]) << 16) | ((best[2] / best[0]) << 8) | (best[3] / best[0]));
        }
        if (!any) return null;
        for (int k = 0; k < out.length; k++) {
            if (out[k] >= 0) continue;
            int n = -1;
            for (int d = 1; d < out.length && n < 0; d++) {
                if (k - d >= 0 && out[k - d] >= 0) n = out[k - d];
                else if (k + d < out.length && out[k + d] >= 0) n = out[k + d];
            }
            out[k] = n;
        }
        return out;
    }

    /** 채도 × 0.8 (채널마다 가장 밝은 채널 쪽으로 2/10 당긴다, 반올림), 밝기가 MIN_VALUE 보다 낮으면 끌어올린다. */
    static int grade(int rgb) {
        int r = (rgb >> 16) & 255, g = (rgb >> 8) & 255, b = rgb & 255;
        int mx = Math.max(r, Math.max(g, b));
        r += ((mx - r) * 2 + 5) / 10;
        g += ((mx - g) * 2 + 5) / 10;
        b += ((mx - b) * 2 + 5) / 10;
        if (mx < MIN_VALUE) {
            if (mx == 0) {
                r = g = b = MIN_VALUE;
            } else {
                r = (r * MIN_VALUE + mx / 2) / mx;
                g = (g * MIN_VALUE + mx / 2) / mx;
                b = (b * MIN_VALUE + mx / 2) / mx;
            }
        }
        return (r << 16) | (g << 8) | b;
    }
}
