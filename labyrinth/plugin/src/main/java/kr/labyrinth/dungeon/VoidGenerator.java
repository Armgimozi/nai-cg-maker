package kr.labyrinth.dungeon;

import java.util.List;
import java.util.Random;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.generator.BiomeProvider;
import org.bukkit.generator.BlockPopulator;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.generator.WorldInfo;

/** 미궁 전용 공허 월드: 블록·구조물·장식·자연 몹 전부 없음. 생물군계는 THE_VOID 하나. */
public final class VoidGenerator extends ChunkGenerator {

    @Override public boolean shouldGenerateNoise() { return false; }
    @Override public boolean shouldGenerateSurface() { return false; }
    @Override public boolean shouldGenerateBedrock() { return false; }
    @Override public boolean shouldGenerateCaves() { return false; }
    @Override public boolean shouldGenerateDecorations() { return false; }
    @Override public boolean shouldGenerateMobs() { return false; }
    @Override public boolean shouldGenerateStructures() { return false; }
    @Override public boolean isParallelCapable() { return true; }
    @Override public boolean canSpawn(World world, int x, int z) { return true; }
    @Override public List<BlockPopulator> getDefaultPopulators(World world) { return List.of(); }

    @Override
    public Location getFixedSpawnLocation(World world, Random random) {
        return new Location(world, 0.5, 200, 0.5);
    }

    @Override
    public BiomeProvider getDefaultBiomeProvider(WorldInfo worldInfo) {
        return new BiomeProvider() {
            @Override
            public Biome getBiome(WorldInfo info, int x, int y, int z) { return Biome.THE_VOID; }

            @Override
            public List<Biome> getBiomes(WorldInfo info) { return List.of(Biome.THE_VOID); }
        };
    }
}
