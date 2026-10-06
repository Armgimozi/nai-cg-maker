package kr.augsky.nether;

import kr.augsky.map.NetherMap;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Biome;
import org.bukkit.generator.BiomeProvider;
import org.bukkit.generator.ChunkGenerator;
import org.bukkit.generator.WorldInfo;

import java.util.List;
import java.util.Random;

/**
 * 하늘 네더의 생성기: 블록은 하나도 만들지 않는다 (should* 가 모두 기본 false). 섬은 NetherService 가 처음 한 번 짓는다.
 * 생물군계만 섬 자리마다 정해 준다 (안개 색, 입자, 나오는 몹이 섬마다 달라진다).
 * 청크는 여러 스레드에서 만들어지므로 생물군계는 굳힌 섬 목록만 읽는 순수 함수로 정한다.
 */
public final class VoidNether extends ChunkGenerator {
    private static final BiomeProvider BIOMES = new BiomeProvider() {
        @Override
        public Biome getBiome(WorldInfo info, int x, int y, int z) {
            return NetherMap.biomeAt(x, z);
        }

        @Override
        public List<Biome> getBiomes(WorldInfo info) {
            return NetherMap.BIOMES;
        }
    };

    @Override
    public BiomeProvider getDefaultBiomeProvider(WorldInfo info) {
        return BIOMES;
    }

    /** 월드를 만드는 도중에 불린다. 그때 받은 world 로 만들어야 한다 (다른 World 를 넘기면 월드 만들기가 실패한다). */
    @Override
    public Location getFixedSpawnLocation(World world, Random random) {
        return NetherMap.hubSpawn(world);
    }
}
