package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;
import org.junit.jupiter.api.Test;

/**
 * 배포 월드 지문 맞대기 (0.3.6.1 CONTRACT §2.13 2·4): 그대로 = 같음, 잔디↔흙·꽃·풀·눈 층·잎 = 허용,
 * 높이 차 &gt; 2 · 땅속 새 빈칸·물 · 새 원목 · 비자연 블록 = 막음. 엔티티 (갑옷 거치대 등) = 막음. jar 의 mine.fp 가 배포 월드와 맞는지도.
 */
class DistrictCheckTest {

    /** 가짜 월드: 열마다 땅 높이 + 블록 (없으면 땅 아래 = 돌·흙, 위 = 공기). */
    static final class FakeWorld implements DistrictCheck.Live {
        final Map<Long, Integer> ground = new HashMap<>();
        final Map<String, String> blocks = new HashMap<>();
        final Map<Long, Integer> flags = new HashMap<>();
        final Map<Long, String> notes = new HashMap<>();

        FakeWorld flat(int x0, int z0, int x1, int z1, int h) {
            for (int z = z0; z <= z1; z++) for (int x = x0; x <= x1; x++) ground.put(PathRaster.key(x, z), h);
            return this;
        }

        FakeWorld set(int x, int y, int z, String id) {
            blocks.put(x + "," + y + "," + z, id);
            return this;
        }

        @Override
        public boolean has(int x, int z) { return ground.containsKey(PathRaster.key(x, z)); }

        @Override
        public int ground(int x, int z) {
            // 땅 높이 = Nature GROUND 맨 위 (Scan.columns 규칙): 위에서 내려오며
            int base = ground.get(PathRaster.key(x, z));
            for (int y = base + 30; y >= base - 12; y--) if (Nature.kind(block(x, y, z)) == Nature.Kind.GROUND) return y;
            return base;
        }

        @Override
        public String block(int x, int y, int z) {
            String b = blocks.get(x + "," + y + "," + z);
            if (b != null) return b;
            int h = ground.getOrDefault(PathRaster.key(x, z), 64);
            return y > h ? "air" : y == h ? "grass_block" : y >= h - 3 ? "dirt" : "stone";
        }

        @Override
        public int flags(int x, int z) { return flags.getOrDefault(PathRaster.key(x, z), 0); }

        @Override
        public String note(int x, int z) { return notes.get(PathRaster.key(x, z)); }
    }

    /** 가짜 월드의 지금 모습으로 지문 파일을 굽는다 (district_fingerprint.py 와 같은 형식). */
    static DistrictFingerprint bake(FakeWorld w, int x0, int z0, int sx, int sz, String buildId) throws IOException {
        int under = 10, above = 30;
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        try (DataOutputStream out = new DataOutputStream(new GZIPOutputStream(raw))) {
            out.writeInt(DistrictFingerprint.MAGIC);
            out.writeInt(1);
            out.writeLong(DistrictFingerprint.natureSignatureHash());
            out.writeLong(DistrictFingerprint.probe());
            out.writeInt(under);
            out.writeInt(above);
            out.writeInt(1);
            out.writeInt(1);
            out.writeUTF(buildId);
            out.writeInt(x0);
            out.writeInt(z0);
            out.writeInt(sx);
            out.writeInt(sz);
            for (int z = z0; z < z0 + sz; z++) {
                for (int x = x0; x < x0 + sx; x++) {
                    if (!w.has(x, z)) {
                        out.writeShort(Short.MIN_VALUE);
                        continue;
                    }
                    int h = w.ground(x, z);
                    out.writeShort(h);
                    out.writeLong(DistrictCheck.liveHash(w, x, z, h, under, above));
                    int bits = 0;
                    for (int k = 1; k <= under; k++) if (DistrictFingerprint.solidNorm(DistrictCheck.normAt(w, x, h - k, z))) bits |= 1 << (k - 1);
                    out.writeShort(bits);
                    List<Integer> logs = new ArrayList<>();
                    for (int dy = 1; dy <= above; dy++) if (Nature.kind(w.block(x, h + dy, z)) == Nature.Kind.LOG) logs.add(dy);
                    out.writeByte(logs.size());
                    for (int dy : logs) out.writeByte(dy);
                }
            }
        }
        return DistrictFingerprint.read(raw.toByteArray());
    }

    static List<int[]> cols(int x0, int z0, int x1, int z1) {
        List<int[]> out = new ArrayList<>();
        for (int z = z0; z <= z1; z++) for (int x = x0; x <= x1; x++) out.add(new int[] {x, z});
        return out;
    }

    static DistrictCheck.Result run(DistrictFingerprint fp, FakeWorld w) {
        return DistrictCheck.check(fp.forBuild("ship"), fp.under, fp.above, w, cols(0, 0, 9, 9), 20);
    }

    static FakeWorld base() {
        FakeWorld w = new FakeWorld().flat(0, 0, 9, 9, 64);
        // 자연 나무 한 그루 (5,5): 원목 4 + 잎
        for (int y = 65; y <= 68; y++) w.set(5, y, 5, "oak_log");
        w.set(5, 69, 5, "oak_leaves").set(4, 68, 5, "oak_leaves");
        w.set(2, 65, 2, "poppy");
        return w;
    }

    @Test
    void untouchedWorldIsSame() throws IOException {
        FakeWorld w = base();
        DistrictFingerprint fp = bake(w, 0, 0, 10, 10, "ship");
        assertTrue(fp.compatible(), "지문 규칙 = 이 jar (Nature 분류·해시)");
        DistrictCheck.Result r = run(fp, w);
        assertTrue(r.ok(), r.problems().toString());
        assertEquals(100, r.checked());
        assertEquals(100, r.same());
        assertNull(fp.forBuild("someone-else"), "다른 마을은 지문 없음");
    }

    @Test
    void naturalChangesAreAllowed() throws IOException {
        FakeWorld w = base();
        DistrictFingerprint fp = bake(w, 0, 0, 10, 10, "ship");
        w.set(1, 64, 1, "dirt");                 // 잔디 → 흙
        w.set(2, 65, 2, "air");                  // 꽃 없어짐
        w.set(3, 65, 3, "dandelion");            // 꽃 생김
        w.set(4, 65, 4, "snow");                 // 눈 한 겹
        w.set(6, 65, 6, "short_grass");          // 풀
        w.set(6, 66, 7, "oak_leaves");           // 잎 (원목 그대로)
        w.set(7, 65, 7, "snow_block");           // 눈 덩이 (높이 +1)
        w.set(8, 64, 8, "air");                  // 1칸 패임 (높이 −1)
        DistrictCheck.Result r = run(fp, w);
        assertTrue(r.ok(), r.problems().toString());
        assertEquals(2, r.allowed(), "높이만 조금 다른 두 열 (눈 덩이 · 1칸 패임) — 나머지는 정규화로 같음");
    }

    @Test
    void humanChangesBlock() throws IOException {
        FakeWorld w = base();
        DistrictFingerprint fp = bake(w, 0, 0, 10, 10, "ship");
        // 흙 기둥 3칸 (쌓은 땅)
        for (int y = 65; y <= 67; y++) w.set(1, y, 1, "dirt");
        // 판 구덩이 3칸
        for (int y = 62; y <= 64; y++) w.set(2, y, 8, "air");
        // 땅속 굴 (5칸 아래)
        w.set(8, 59, 1, "air");
        // 땅속 물
        w.set(8, 61, 3, "water");
        // 심은 나무 (새 원목)
        w.set(3, 65, 6, "birch_log");
        DistrictCheck.Result r = run(fp, w);
        assertFalse(r.ok());
        String all = r.problems().toString();
        assertTrue(all.contains("쌓은 땅"), all);
        assertTrue(all.contains("판 땅"), all);
        assertTrue(all.contains("땅속에 새 빈칸"), all);
        assertTrue(all.contains("땅속에 새 물"), all);
        assertTrue(all.contains("새 원목 birch_log"), all);
        // 나무를 베어 낸 것만으로는 막지 않는다 (원목이 없어짐 = 자연에서도 생김) — 높이·땅속이 같으면 허용
        FakeWorld cut = base();
        DistrictFingerprint fp2 = bake(cut, 0, 0, 10, 10, "ship");
        for (int y = 65; y <= 68; y++) cut.set(5, y, 5, "air");
        assertTrue(run(fp2, cut).ok());
    }

    @Test
    void unnaturalBlocksBlockEvenWithoutFingerprint() throws IOException {
        FakeWorld w = base();
        w.flags.put(PathRaster.key(4, 4), Terrain.UNNATURAL);
        w.notes.put(PathRaster.key(4, 4), "oak_planks@65");
        // 지문 없음 (배포 월드 아님) → 비자연 검사만
        DistrictCheck.Result r = DistrictCheck.check(null, 10, 30, w, cols(0, 0, 9, 9), 20);
        assertFalse(r.ok());
        assertEquals(100, r.uncovered());
        assertEquals("사람이 놓은 블록 oak_planks (4 65 4)", r.problems().get(0).line());
        // 이유는 maxProblems 까지 모으고 나머지는 세기만
        for (int x = 0; x < 10; x++) w.flags.put(PathRaster.key(x, 9), Terrain.UNNATURAL);
        DistrictCheck.Result many = DistrictCheck.check(null, 10, 30, w, cols(0, 0, 9, 9), 3);
        assertEquals(4, many.problems().size());
        assertEquals("그 밖 8건", many.problems().get(3).why());
    }

    @Test
    void entitiesThatMeanPeople() {
        assertEquals("갑옷 거치대", DistrictCheck.entityBlocks("ARMOR_STAND", false, false, false, false));
        assertEquals("액자", DistrictCheck.entityBlocks("GLOW_ITEM_FRAME", false, false, false, false));
        assertEquals("그림", DistrictCheck.entityBlocks("PAINTING", false, false, false, false));
        assertEquals("수레", DistrictCheck.entityBlocks("CHEST_MINECART", false, false, false, false));
        assertEquals("보트", DistrictCheck.entityBlocks("OAK_BOAT", false, false, false, false));
        assertEquals("보트", DistrictCheck.entityBlocks("BAMBOO_RAFT", false, false, false, false));
        assertEquals("끈 매듭", DistrictCheck.entityBlocks("LEASH_KNOT", false, false, false, false));
        assertEquals("주민", DistrictCheck.entityBlocks("VILLAGER", false, false, false, false));
        assertEquals("길들인 동물", DistrictCheck.entityBlocks("WOLF", false, true, false, false));
        assertEquals("이름표 붙은 동물", DistrictCheck.entityBlocks("COW", true, false, false, false));
        assertEquals("끈에 묶인 동물", DistrictCheck.entityBlocks("HORSE", false, false, true, false));
        assertNull(DistrictCheck.entityBlocks("COW", false, false, false, false), "그냥 다니는 동물은 막지 않음 (밖으로 옮김)");
        assertNull(DistrictCheck.entityBlocks("ARMOR_STAND", false, false, false, true), "이 플러그인의 NPC·연출");
        assertNull(DistrictCheck.entityBlocks("ITEM", false, false, false, false));
    }

    // ── jar 의 지문 (배포 월드 두 판) ─────────────────────────────────────

    static DistrictFingerprint jarFp() throws IOException {
        byte[] raw = DistrictLayoutTest.bin("village/districts/mine.fp");
        assertNotNull(raw, "jar village/districts/mine.fp");
        return DistrictFingerprint.read(raw);
    }

    @Test
    void jarFingerprintCoversBothShippedWorldsAndMatchesTerrain() throws Exception {
        DistrictFingerprint fp = jarFp();
        assertTrue(fp.compatible(), "district_fingerprint.py 와 Java 의 분류·해시가 같아야 (다르면 지문을 다시 굽기)");
        // 0.2.0 과 0.3.x 배포 월드는 마스크 범위 지형이 열 단위로 같다 → 지문 하나에 build_id 둘
        DistrictFingerprint.World a = fp.forBuild("a06800d8-7a5d-452d-b3eb-79364ebfac99");
        DistrictFingerprint.World b = fp.forBuild("c99c3fb3-4621-4037-b7dd-26f71e3edfce");
        assertNotNull(a, "0.3.0~0.3.6 배포 월드 (서버장 월드)");
        assertNotNull(b, "0.2.0 배포 월드");
        VillageMeta v = DistrictLayoutTest.shipped();
        assertNotNull(fp.forBuild(v.buildId), "픽스처 마을 = 배포 월드");
        // east 자리 계획 영역의 모든 열이 지문 안에 있고, 지문 땅 높이 = 배포 월드 지형 픽스처 (같은 world.zip 에서)
        DistrictLibrary.Entry e = DistrictLayoutTest.library().get("mine");
        TerrainGrid g = DistrictLayoutTest.terrain(v);
        Plan p = DistrictLayoutTest.plan(e, e.layout().site("east"), v, g);
        int n = 0;
        for (int lz = 0; lz < p.gn; lz++) {
            for (int lx = 0; lx < p.gn; lx++) {
                int x = p.gx0 + lx, z = p.gz0 + lz;
                if (!p.inRegion(x, z) || p.isFrozen(x, z)) continue;
                DistrictFingerprint.Column c = a.at(x, z);
                assertNotNull(c, "지문이 덮지 않는 열 (" + x + ", " + z + ")");
                assertEquals(g.ground(x, z), c.h(), "땅 높이 (" + x + ", " + z + ")");
                n++;
            }
        }
        assertTrue(n > 1500, "검사한 열 " + n);
    }

    @Test
    void fixtureIsTheShippedWorld() throws IOException {
        try (var in = new GZIPInputStream(DistrictCheckTest.class.getClassLoader().getResourceAsStream("village/shipped-terrain.txt.gz"))) {
            String head = new String(in.readNBytes(200), StandardCharsets.UTF_8);
            assertTrue(head.startsWith("# world.zip"), head);
        }
    }
    /** 큰길과 만나는 얼린 칸 (0.3.6.1 리뷰 #6): 지문과 같으면 통과, 다르고 y ~ y+2 에 비자연 블록 → 막음. 풀·꽃·흙은 통과. */
    @Test
    void junctionCellsBlockPlayerBlocksOnly() throws IOException {
        FakeWorld w = new FakeWorld().flat(-104, 14, -100, 18, 64);
        DistrictFingerprint fp = bake(w, -104, 14, 5, 5, "b1");
        DistrictFingerprint.World fw = fp.forBuild("b1");
        List<int[]> cells = List.of(new int[] {-103, 15, 64}, new int[] {-102, 16, 64}, new int[] {-101, 17, 64});
        assertTrue(DistrictCheck.junction(fw, fp.under, fp.above, w, cells, 10).isEmpty(), "그대로");
        assertTrue(DistrictCheck.junction(null, 10, 30, w, cells, 10).isEmpty(), "지문 없는 월드도 자연 블록뿐이면 통과");
        w.set(-102, 65, 16, "poppy").set(-101, 64, 17, "dirt");
        assertTrue(DistrictCheck.junction(fw, fp.under, fp.above, w, cells, 10).isEmpty(), "꽃·흙은 사람 손 아님");
        w.set(-103, 65, 15, "oak_planks");
        List<DistrictCheck.Problem> p = DistrictCheck.junction(fw, fp.under, fp.above, w, cells, 10);
        assertEquals(1, p.size());
        assertTrue(p.get(0).line().contains("oak_planks"), p.get(0).line());
        assertEquals(1, DistrictCheck.junction(null, 10, 30, w, cells, 10).size(), "지문이 없어도 비자연 블록은 막음");
        w.set(-101, 64, 17, "cobblestone");
        assertEquals(2, DistrictCheck.junction(fw, fp.under, fp.above, w, cells, 10).size(), "겉 블록 자리의 조약돌");
    }

    /** 짓기 직전 다시 보기 (0.3.6.1 리뷰 #7): 비자연 블록·새 원목이 끼면 사람 손, 잔디↔흙·잎 떨어짐·물 흐름은 자연. */
    @Test
    void handChangeSeparatesPlayerEditsFromNature() {
        assertTrue(DistrictJob.handChange(org.bukkit.Material.AIR, org.bukkit.Material.OAK_PLANKS));
        assertTrue(DistrictJob.handChange(org.bukkit.Material.GRASS_BLOCK, org.bukkit.Material.COBBLESTONE));
        assertTrue(DistrictJob.handChange(org.bukkit.Material.AIR, org.bukkit.Material.OAK_LOG), "새 원목");
        assertTrue(DistrictJob.handChange(org.bukkit.Material.TORCH, org.bukkit.Material.AIR), "횃불을 치움");
        assertFalse(DistrictJob.handChange(org.bukkit.Material.GRASS_BLOCK, org.bukkit.Material.DIRT));
        assertFalse(DistrictJob.handChange(org.bukkit.Material.OAK_LEAVES, org.bukkit.Material.AIR));
        assertFalse(DistrictJob.handChange(org.bukkit.Material.AIR, org.bukkit.Material.WATER));
        assertFalse(DistrictJob.handChange(org.bukkit.Material.AIR, org.bukkit.Material.SHORT_GRASS));
        assertFalse(DistrictJob.handChange(org.bukkit.Material.OAK_LOG, org.bukkit.Material.AIR), "나무 베기는 허용 (지문 검사와 같음)");
    }

    /** 막힘 이유 글 (0.3.6.1 리뷰 #4): 이유마다 안내가 다르고, 파일의 '이유: … [코드]' 를 다시 읽는다. 을/를. */
    @Test
    void blockedReasonsRoundTripAndParticles(@org.junit.jupiter.api.io.TempDir java.io.File dir) throws IOException {
        for (DistrictService.Blocked b : DistrictService.Blocked.values()) {
            java.io.File f = new java.io.File(dir, b.code + ".txt");
            java.nio.file.Files.write(f.toPath(), List.of("머리", "이유: " + b.notice + " [" + b.code + "]", "", "본문"), StandardCharsets.UTF_8);
            assertEquals(b, DistrictService.blockedReason(f));
        }
        java.io.File old = new java.io.File(dir, "old.txt");
        java.nio.file.Files.write(old.toPath(), List.of("미궁 라비린스 — 광산 마을을 짓지 않았습니다", "", "모든 자리 …"), StandardCharsets.UTF_8);
        assertEquals(DistrictService.Blocked.PLAYER_MADE, DistrictService.blockedReason(old), "0.3.6.1 첫 판 파일");
        assertTrue(DistrictService.Blocked.NOT_SHIPPED.notice.contains("서버팩 월드가 아니어서"));
        assertFalse(DistrictService.Blocked.NOT_SHIPPED.last.contains("다시 켜면 다시 살펴봅니다"));
        assertEquals("을", DistrictService.objectParticle("광산 마을"));
        assertEquals("를", DistrictService.objectParticle("광산 마당 가게"));
    }
}
