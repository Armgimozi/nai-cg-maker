package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Random;
import kr.labyrinth.content.MineDef;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.generator.BiomeProvider;
import org.bukkit.generator.BlockPopulator;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.generator.WorldInfo;

/**
 * 광산 월드 생성기: 미궁의 공허 월드(dungeon/VoidGenerator)와 같이 블록·구조물·몹이 하나도 없다. 다른 점은 바이옴만 —
 * 층마다 y 띠로 바이옴을 준다 (mine.yml biome · biome_y: 얕은 갱도·종유 갱도 = 점적석 동굴 … 용의 심연 = 현무암 삼각주).
 * 띠 밖은 THE_VOID. 이미 만든 월드는 짓기 때 {@code World#setBiome} 으로 같은 값을 다시 쓴다 (mine.yml 을 바꿔도 맞음).
 */
public final class MineGenerator extends ChunkGenerator {

    /** y 띠 [lo, hi] → 바이옴. */
    record Band(int lo, int hi, Biome biome) {}

    private final List<Band> bands;
    private final Location spawn;

    MineGenerator(MineDef mine) {
        this.bands = bands(mine);
        MineDef.Level top = mine.level(1);
        double y = top == null ? 136 : top.floorY() + 1;
        this.spawn = new Location(null, 0.5, y, 3.5);
    }

    static List<Band> bands(MineDef mine) {
        List<Band> out = new ArrayList<>();
        for (MineDef.Level l : mine.levels()) {
            Biome b = biome(l.biome());
            if (b == null || l.biomeY().size() != 2) continue;
            out.add(new Band(l.biomeY().get(0), l.biomeY().get(1), b));
        }
        return List.copyOf(out);
    }

    static Biome biome(String key) {
        if (key == null) return null;
        try {
            NamespacedKey k = NamespacedKey.fromString(key.trim().toLowerCase(java.util.Locale.ROOT));
            return k == null ? null : Registry.BIOME.get(k);
        } catch (Throwable t) {
            return null;
        }
    }

    Biome biomeAt(int y) {
        for (Band b : bands) if (y >= b.lo() && y <= b.hi()) return b.biome();
        return Biome.THE_VOID;
    }

    @Override public boolean shouldGenerateNoise() { return false; }
    @Override public boolean shouldGenerateSurface() { return false; }
    @Override public boolean shouldGenerateCaves() { return false; }
    @Override public boolean shouldGenerateDecorations() { return false; }
    @Override public boolean shouldGenerateMobs() { return false; }
    @Override public boolean shouldGenerateStructures() { return false; }
    @Override public boolean canSpawn(World world, int x, int z) { return true; }
    @Override public List<BlockPopulator> getDefaultPopulators(World world) { return List.of(); }

    @Override
    public Location getFixedSpawnLocation(World world, Random random) {
        Location l = spawn.clone();
        l.setWorld(world);
        return l;
    }

    @Override
    public BiomeProvider getDefaultBiomeProvider(WorldInfo worldInfo) {
        List<Biome> all = new ArrayList<>(new LinkedHashSet<>(bands.stream().map(Band::biome).toList()));
        all.add(Biome.THE_VOID);
        List<Biome> list = List.copyOf(new LinkedHashSet<>(all));
        return new BiomeProvider() {
            @Override
            public Biome getBiome(WorldInfo info, int x, int y, int z) { return biomeAt(y); }

            @Override
            public List<Biome> getBiomes(WorldInfo info) { return list; }
        };
    }
}
