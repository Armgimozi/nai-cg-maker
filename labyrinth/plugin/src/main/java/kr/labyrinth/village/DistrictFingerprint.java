package kr.labyrinth.village;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.zip.GZIPInputStream;

/**
 * 배포 월드 지문 (0.3.6, CONTRACT §2.13 · district.json fingerprint) — jar {@code village/districts/<id>.fp}.
 * tools/village/district_fingerprint.py 가 두 배포 world.zip 에서 굽는다. 순수 데이터 (서버 없이 시험 가능).
 * <p>
 * 열(x, z)마다: 땅 높이 h (위에서 내려오며 처음 만나는 {@link Nature.Kind#GROUND}), h−10 ~ h+30 정규화 블록 해시,
 * 땅속 10칸 단단한 칸 비트, h+1 ~ h+30 원목 자리. 정규화 = {@link #norm} (잔디·흙 = dirt, 식물·눈 층·잎·원목 = air, 얼음 = water).
 * 두 배포 월드가 열 단위로 같으면 지문 하나에 build_id 둘 (지금 그렇다), 다르면 월드마다 따로.
 */
public final class DistrictFingerprint {

    public static final int MAGIC = 0x4C424650; // "LBFP"
    static final Set<String> DIRT = Set.of("grass_block", "dirt", "coarse_dirt", "podzol", "mycelium", "rooted_dirt");
    /** 시험 표본 (district_fingerprint.py PROBE). */
    static final List<String> PROBE = List.of("stone", "dirt", "air", "water", "granite");

    /** 열 지문. logs = 원목 dy (h 위로 1..30). */
    public record Column(int h, long hash, int under, byte[] logs) {
        public boolean hasLogAt(int dy) {
            for (byte b : logs) if (b == dy) return true;
            return false;
        }
    }

    /** 한 배포 월드 (또는 열이 같은 여럿): build_id 들 + 사각형 범위 + 열들. */
    public record World(List<String> buildIds, int x0, int z0, int sx, int sz, Column[] cols) {
        public boolean covers(int x, int z) { return x >= x0 && z >= z0 && x < x0 + sx && z < z0 + sz; }

        /** 그 열 지문 (범위 밖·청크 없음 = null). */
        public Column at(int x, int z) { return covers(x, z) ? cols[(z - z0) * sx + (x - x0)] : null; }
    }

    public final long natureHash, probeHash;
    public final int under, above;
    public final List<World> worlds;

    private DistrictFingerprint(long natureHash, long probeHash, int under, int above, List<World> worlds) {
        this.natureHash = natureHash;
        this.probeHash = probeHash;
        this.under = under;
        this.above = above;
        this.worlds = List.copyOf(worlds);
    }

    /** 이 마을(build_id)에 맞는 지문, 없으면 null (배포 월드가 아님 → 비자연 검사만). */
    public World forBuild(String buildId) {
        if (buildId == null || buildId.isBlank()) return null;
        for (World w : worlds) if (w.buildIds().contains(buildId)) return w;
        return null;
    }

    /** jar 의 지문 파일 (gzip). 형식 오류는 IOException. */
    public static DistrictFingerprint read(byte[] gz) throws IOException {
        try (DataInputStream in = new DataInputStream(new GZIPInputStream(new ByteArrayInputStream(gz)))) {
            if (in.readInt() != MAGIC) throw new IOException("지문 파일이 아님");
            int ver = in.readInt();
            if (ver != 1) throw new IOException("지문 형식 " + ver + " (1 만 읽음)");
            long nh = in.readLong(), ph = in.readLong();
            int under = in.readInt(), above = in.readInt();
            int nw = in.readInt();
            List<World> worlds = new ArrayList<>();
            for (int w = 0; w < nw; w++) {
                int ni = in.readInt();
                List<String> ids = new ArrayList<>();
                for (int i = 0; i < ni; i++) ids.add(in.readUTF());
                int x0 = in.readInt(), z0 = in.readInt(), sx = in.readInt(), sz = in.readInt();
                if (sx <= 0 || sz <= 0 || (long) sx * sz > 4_000_000) throw new IOException("지문 범위 오류 " + sx + "×" + sz);
                Column[] cols = new Column[sx * sz];
                for (int i = 0; i < cols.length; i++) {
                    short h = in.readShort();
                    if (h == Short.MIN_VALUE) continue;
                    long hash = in.readLong();
                    int bits = in.readShort() & 0xFFFF;
                    int n = in.readUnsignedByte();
                    byte[] logs = new byte[n];
                    in.readFully(logs);
                    cols[i] = new Column(h, hash, bits, logs);
                }
                worlds.add(new World(ids, x0, z0, sx, sz, cols));
            }
            return new DistrictFingerprint(nh, ph, under, above, worlds);
        }
    }

    // ── 정규화 · 해시 (district_fingerprint.py 와 같은 규칙) ─────────────────

    /** 블록 id (네임스페이스·속성 없이, 소문자) → 지문 이름. */
    public static String norm(String id) {
        Nature.Kind k = Nature.kind(id);
        return switch (k) {
            case AIR, PLANT, LEAVES, LOG, TREE_PART -> "air";
            case LIQUID -> "lava".equals(Nature.key(id)) ? "lava" : "water";
            case ICE -> "water";
            default -> {
                String key = Nature.key(id);
                yield DIRT.contains(key) ? "dirt" : key;
            }
        };
    }

    /** 단단한 칸 (공기·물·용암이 아님). */
    public static boolean solidNorm(String n) {
        return !n.equals("air") && !n.equals("water") && !n.equals("lava") && !n.equals("void");
    }

    static final long FNV_OFFSET = 0xcbf29ce484222325L, FNV_PRIME = 0x100000001b3L;

    public static long fnv(byte[] data) {
        long h = FNV_OFFSET;
        for (byte b : data) {
            h ^= (b & 0xFF);
            h *= FNV_PRIME;
        }
        return h;
    }

    /** 아래에서 위로 정규화 이름들 → 해시 (줄마다 "\n"). */
    public static long hash(List<String> names) {
        StringBuilder sb = new StringBuilder();
        for (String n : names) sb.append(n).append('\n');
        return fnv(sb.toString().getBytes(StandardCharsets.UTF_8));
    }

    /** 이 jar 의 Nature 분류 서명 해시 — 지문의 natureHash 와 같아야 한다. */
    public static long natureSignatureHash() { return fnv(Nature.signature().getBytes(StandardCharsets.UTF_8)); }

    public static long probe() { return hash(PROBE); }

    /** 지문과 이 jar 의 규칙이 맞는가 (분류 목록·해시 방식). */
    public boolean compatible() { return natureHash == natureSignatureHash() && probeHash == probe(); }
}
