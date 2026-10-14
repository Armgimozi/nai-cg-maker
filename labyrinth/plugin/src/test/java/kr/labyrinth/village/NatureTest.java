package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** 블록 분류 (구조물 판정·땅높이·바이옴 표면). */
class NatureTest {

    @Test
    void classifiesTerrainTreesPlantsAndBuiltBlocks() {
        assertEquals(Nature.Kind.GROUND, Nature.kind("minecraft:grass_block[snowy=false]"));
        assertEquals(Nature.Kind.GROUND, Nature.kind("DEEPSLATE_DIAMOND_ORE"));
        assertEquals(Nature.Kind.GROUND, Nature.kind("white_terracotta"));
        assertEquals(Nature.Kind.GROUND, Nature.kind("mossy_cobblestone"), "숲 바위");
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("white_glazed_terracotta"));
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("cobblestone"), "던전·마을");
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("oak_planks"));
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("dirt_path"), "바닐라 마을 길");
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("stripped_oak_log"));
        assertEquals(Nature.Kind.UNNATURAL, Nature.kind("chest"));
        assertEquals(Nature.Kind.LOG, Nature.kind("minecraft:dark_oak_log[axis=y]"));
        assertEquals(Nature.Kind.LOG, Nature.kind("mushroom_stem"));
        assertEquals(Nature.Kind.LEAVES, Nature.kind("azalea_leaves"));
        assertEquals(Nature.Kind.TREE_PART, Nature.kind("bee_nest"));
        assertEquals(Nature.Kind.TREE_PART, Nature.kind("vine"));
        assertEquals(Nature.Kind.PLANT, Nature.kind("short_grass"));
        assertEquals(Nature.Kind.PLANT, Nature.kind("snow[layers=1]"));
        assertEquals(Nature.Kind.PLANT, Nature.kind("leaf_litter"));
        assertEquals(Nature.Kind.PLANT, Nature.kind("oak_sapling"));
        assertEquals(Nature.Kind.LIQUID, Nature.kind("water[level=0]"));
        assertEquals(Nature.Kind.ICE, Nature.kind("packed_ice"));
        assertEquals(Nature.Kind.AIR, Nature.kind("cave_air"));
    }

    @Test
    void biomeSurfaceIsKept() {
        assertEquals("minecraft:sand", Nature.topFor("sand"));
        assertEquals("minecraft:sand", Nature.subsurface("sand"));
        assertEquals("minecraft:podzol", Nature.topFor("podzol"));
        assertEquals("minecraft:dirt", Nature.subsurface("podzol"));
        assertEquals("minecraft:grass_block", Nature.topFor("dirt"), "흙 맨 위 = 잔디");
        assertEquals("minecraft:grass_block", Nature.topFor("oak_planks"), "비자연 표면은 잔디로");
        assertEquals("minecraft:red_sandstone", Nature.subsurface("red_sandstone"));
    }
}
