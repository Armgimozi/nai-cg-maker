package kr.souls.world;

import io.papermc.paper.registry.RegistryAccess;
import io.papermc.paper.registry.RegistryKey;
import net.kyori.adventure.key.Key;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.generator.BiomeProvider;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.generator.WorldInfo;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.function.Supplier;
import java.util.logging.Logger;

/**
 * souls_world 의 생성기. M0~M2 는 덩어리 없는 공허다: 블록은 하나도 만들지 않는다 (should* 가 모두 기본 false).
 * 바이옴만 지역 상자(8.4)마다 정해 준다. 바이옴 이름은 청크가 처음 만들어질 때 청크에 저장되므로,
 * 첫 세계부터 지역 이름(souls:redin 등)을 쓴다. 꾸밈(안개·하늘·입자)은 M4 에 데이터팩만 바꾼다.
 * 청크는 여러 스레드에서 만들어지므로 바이옴은 굳힌 표만 읽는 순수 함수로 정한다 (skyblock VoidNether 방식).
 */
public final class SoulsGenerator extends ChunkGenerator {
    /**
     * 바이옴 경계의 판. 아래 표를 바꾸면 올린다. 이미 만든 청크의 바이옴은 바뀌지 않으므로,
     * 판이 다르면 WorldService 가 "세계를 새로 만들어야 한다" 고 크게 알린다 (8.1).
     */
    public static final int BIOME_LAYOUT = 1;

    /** 지역 상자 하나 (x·z 는 반열림 [min, max), y 는 H/R7 처럼 같은 x·z 위아래로 겹칠 때만 본다). */
    record Box(String biome, int x0, int x1, int z0, int z1, int y0, int y1) {
        boolean inXZ(int x, int z) {
            return x >= x0 && x < x1 && z >= z0 && z < z1;
        }

        double distXZ(int x, int z) {
            double dx = Math.max(Math.max(x0 - x, 0), x - (x1 - 1));
            double dz = Math.max(Math.max(z0 - z, 0), z - (z1 - 1));
            return dx * dx + dz * dz;
        }
    }

    /** 8.4 의 지역 상자 (x / z / y). 사당(H)과 식은 가마(R7)는 같은 x·z 의 위아래라 y 로 가른다. */
    static final List<Box> REGIONS = List.of(
            new Box("hub", -40, 40, -40, 40, 95, 130),
            new Box("kiln", -40, 40, -40, 40, 30, 85),
            new Box("prison", 0, 80, -280, -240, 140, 180),
            new Box("redin", -40, 120, -240, -80, 95, 175),
            new Box("parish", 120, 280, -80, 80, 70, 165),
            new Box("mire", 80, 280, 120, 240, 30, 75),
            new Box("spire", -280, -120, -240, -80, 150, 270),
            new Box("ossuary", -280, -80, -40, 160, 20, 90),
            new Box("forge", -80, 80, 200, 320, 5, 60));
    /** 사당과 가마 사이 (가마 꼭대기 85, 사당 바닥 95) 를 가르는 높이 */
    static final int HUB_KILN_SPLIT = 90;
    static final List<String> NAMES = List.of("hub", "prison", "redin", "parish", "mire", "spire", "ossuary", "forge", "kiln");

    private final Map<String, Biome> biomes;
    private final List<Biome> all;
    private final Supplier<Location> spawn;

    /**
     * 메인 스레드에서 만든다 (등록부를 읽는다). 데이터팩이 실리지 않아 지역 바이옴이 없으면 공허 바이옴으로 대신하고 크게 알린다.
     * @param spawn 고정 스폰 자리 (세계를 만드는 도중에 불린다)
     */
    public SoulsGenerator(Logger log, Supplier<Location> spawn) {
        this.spawn = spawn;
        Map<String, Biome> m = new LinkedHashMap<>();
        var reg = RegistryAccess.registryAccess().getRegistry(RegistryKey.BIOME);
        List<String> missing = new ArrayList<>();
        for (String n : NAMES) {
            Biome b = reg.get(Key.key(kr.souls.Keys.NS, n));
            if (b == null) {
                missing.add(n);
                b = Biome.THE_VOID;
            }
            m.put(n, b);
        }
        if (!missing.isEmpty()) {
            log.severe("데이터팩 지역 바이옴이 등록부에 없습니다: " + missing + ". souls_world 의 새 청크가 공허 바이옴으로 만들어집니다."
                    + " 이대로 지은 청크는 나중에 바이옴을 바꿀 수 없으니 데이터팩을 고친 뒤 세계를 새로 만드세요.");
        }
        biomes = Map.copyOf(m);
        all = List.copyOf(new java.util.LinkedHashSet<>(m.values()));
    }

    /** 그 자리의 지역 이름 (hub, redin ...). 상자 밖이면 x·z 로 가장 가까운 상자. */
    public static String regionAt(int x, int y, int z) {
        Box best = null;
        double bd = Double.MAX_VALUE;
        for (Box b : REGIONS) {
            double d = b.inXZ(x, z) ? 0 : b.distXZ(x, z);
            if (d < bd) {
                bd = d;
                best = b;
            }
        }
        String id = best == null ? "hub" : best.biome();
        // 사당과 가마는 같은 기둥이다 (표의 앞쪽 hub 가 먼저 잡힌다)
        if (id.equals("hub") || id.equals("kiln")) return y >= HUB_KILN_SPLIT ? "hub" : "kiln";
        return id;
    }

    public Biome biomeAt(int x, int y, int z) {
        return biomes.get(regionAt(x, y, z));
    }

    private final BiomeProvider provider = new BiomeProvider() {
        @Override
        public Biome getBiome(WorldInfo info, int x, int y, int z) {
            return biomeAt(x, y, z);
        }

        @Override
        public List<Biome> getBiomes(WorldInfo info) {
            return all;
        }
    };

    @Override
    public BiomeProvider getDefaultBiomeProvider(WorldInfo info) {
        return provider;
    }

    /** 세계를 만드는 도중에 불린다. 그때 받은 world 로 만들어야 한다 (다른 World 를 넘기면 세계 만들기가 실패한다). */
    @Override
    public Location getFixedSpawnLocation(World world, Random random) {
        Location s = spawn.get();
        return new Location(world, s.getX(), s.getY(), s.getZ(), s.getYaw(), s.getPitch());
    }
}
