package kr.labyrinth.village;

import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;

/**
 * 구역 되돌리기 백업 {@code <주 월드>/labyrinth-district-<id>.backup.gz} (0.3.6, CONTRACT §2.13 5·6). 순수 I/O (시험 가능).
 * <ul>
 *   <li>{@link Phase#BEFORE}: 짓기 전에 바꿀 수 있는 모든 칸의 원래 BlockData (짓기 시작 전에 디스크에 먼저 씀).
 *       짓다가 꺼지면 다음 시작 때 이것으로 통째로 되돌린다 (그 동안 구역 상자는 보호되어 사람이 바꾸지 못했다).</li>
 *   <li>{@link Phase#DIFF}: 다 지은 뒤 — 실제로 바뀐 칸만 (원래 · 우리가 놓은 것). {@code district remove} 는 지금 블록이
 *       우리가 놓은 것과 같은 칸만 되돌리고 나머지(그 뒤 사람이 바꾼 칸)는 건너뛴 수를 알린다.</li>
 * </ul>
 * 형식: gzip( "LBDB" · 판 1 · 단계 · 구역 id · 팔레트(BlockData 문자열) · 칸 (x, y, z, 원래, [놓은 것]) ).
 */
public final class DistrictBackup {

    public static final int MAGIC = 0x4C424442; // "LBDB"

    public enum Phase { BEFORE, DIFF }

    /** after = null (BEFORE 단계). */
    public record Entry(int x, int y, int z, String before, String after) {
        public long key() { return pack(x, y, z); }
    }

    /** 칸 → 지금 BlockData 문자열 (없으면 null). */
    public interface Lookup {
        String at(int x, int y, int z);
    }

    /** 되돌리기 계획: apply = before 로 바꿀 칸, skipped = 사람이 바꿔 건너뛴 칸, same = 이미 원래와 같은 칸. */
    public record Restore(List<Entry> apply, int skipped, int same) {}

    public final String district;
    public final Phase phase;
    public final List<Entry> entries;

    public DistrictBackup(String district, Phase phase, List<Entry> entries) {
        this.district = district;
        this.phase = phase;
        this.entries = List.copyOf(entries);
    }

    public static long pack(int x, int y, int z) { return Trees.pack(x, y, z); }

    // ── 쓰기 · 읽기 ───────────────────────────────────────────────────────

    /** raw 는 닫지 않는다 (부르는 쪽이 fsync 할 수 있게). */
    public void write(OutputStream raw) throws IOException {
        OutputStream keep = new java.io.FilterOutputStream(raw) {
            @Override
            public void write(byte[] b, int off, int len) throws IOException { out.write(b, off, len); }

            @Override
            public void close() throws IOException { flush(); }
        };
        DataOutputStream out = new DataOutputStream(new BufferedOutputStream(new GZIPOutputStream(keep), 1 << 16));
        out.writeInt(MAGIC);
        out.writeInt(1);
        out.writeByte(phase == Phase.BEFORE ? 'B' : 'D');
        out.writeUTF(district == null ? "" : district);
        Map<String, Integer> pal = new HashMap<>();
        List<String> order = new ArrayList<>();
        for (Entry e : entries) {
            for (String s : phase == Phase.BEFORE ? new String[] {e.before()} : new String[] {e.before(), e.after()}) {
                if (pal.putIfAbsent(s, order.size()) == null) order.add(s);
            }
        }
        out.writeInt(order.size());
        for (String s : order) out.writeUTF(s);
        out.writeInt(entries.size());
        for (Entry e : entries) {
            out.writeInt(e.x());
            out.writeShort(e.y());
            out.writeInt(e.z());
            out.writeInt(pal.get(e.before()));
            if (phase == Phase.DIFF) out.writeInt(pal.get(e.after()));
        }
        out.flush();
        out.close();
    }

    public static DistrictBackup read(InputStream raw) throws IOException {
        try (DataInputStream in = new DataInputStream(new GZIPInputStream(raw, 1 << 16))) {
            if (in.readInt() != MAGIC) throw new IOException("구역 백업 파일이 아님");
            int ver = in.readInt();
            if (ver != 1) throw new IOException("구역 백업 형식 " + ver);
            int ph = in.readByte();
            Phase phase = ph == 'B' ? Phase.BEFORE : ph == 'D' ? Phase.DIFF : null;
            if (phase == null) throw new IOException("구역 백업 단계 오류 " + ph);
            String district = in.readUTF();
            int np = in.readInt();
            if (np < 0 || np > 1_000_000) throw new IOException("팔레트 크기 오류 " + np);
            String[] pal = new String[np];
            for (int i = 0; i < np; i++) pal[i] = in.readUTF();
            int n = in.readInt();
            if (n < 0 || n > 50_000_000) throw new IOException("칸 수 오류 " + n);
            List<Entry> out = new ArrayList<>(n);
            for (int i = 0; i < n; i++) {
                int x = in.readInt(), y = in.readShort(), z = in.readInt();
                String b = pal[in.readInt()];
                String a = phase == Phase.DIFF ? pal[in.readInt()] : null;
                out.add(new Entry(x, y, z, b, a));
            }
            return new DistrictBackup(district, phase, out);
        }
    }

    /** 원자적으로 파일에 (임시 파일 → fsync → 이름 바꾸기). 짓기 전 백업이 디스크에 있어야 블록을 바꾼다. */
    public void save(File file) throws IOException {
        File parent = file.getParentFile();
        if (parent != null) parent.mkdirs();
        File tmp = new File(file.getPath() + ".tmp");
        try (FileOutputStream fo = new FileOutputStream(tmp)) {
            write(fo);
            fo.getFD().sync();
        }
        Files.move(tmp.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    public static DistrictBackup load(File file) throws IOException {
        try (InputStream in = Files.newInputStream(file.toPath())) {
            return read(in);
        }
    }

    // ── 계산 ─────────────────────────────────────────────────────────────

    /** 짓기 전 백업 + 다 지은 뒤 블록 → 바뀐 칸만 (DIFF). 같은 칸이 두 번 있으면 처음 것. */
    public DistrictBackup diff(Lookup after) {
        List<Entry> out = new ArrayList<>();
        java.util.Set<Long> seen = new java.util.HashSet<>();
        for (Entry e : entries) {
            if (!seen.add(e.key())) continue;
            String a = after.at(e.x(), e.y(), e.z());
            if (a == null || a.equals(e.before())) continue;
            out.add(new Entry(e.x(), e.y(), e.z(), e.before(), a));
        }
        return new DistrictBackup(district, Phase.DIFF, out);
    }

    /** 칸 하나 되돌리기 판단. */
    public enum Decision { APPLY, SAME, SKIP }

    /**
     * 칸 하나: 지금 == 원래 → 이미 같음. DIFF: 지금 == 놓은 것 → 되돌림, 그 밖 → 건너뜀(사람이 바꿈).
     * BEFORE (짓다 꺼짐): 지금 ≠ 원래 인 칸은 모두 되돌림 (짓는 동안 구역 상자는 보호되어 사람이 바꾼 칸이 없다).
     */
    public Decision decide(Entry e, String now) {
        if (now != null && now.equals(e.before())) return Decision.SAME;
        if (phase == Phase.BEFORE || (now != null && now.equals(e.after()))) return Decision.APPLY;
        return Decision.SKIP;
    }

    /** 되돌리기 계획 ({@link #decide} 를 칸마다, 같은 칸이 두 번 있으면 처음 것). */
    public Restore restorePlan(Lookup current) {
        List<Entry> apply = new ArrayList<>();
        int skipped = 0, same = 0;
        java.util.Set<Long> seen = new java.util.HashSet<>();
        for (Entry e : entries) {
            if (!seen.add(e.key())) continue;
            switch (decide(e, current.at(e.x(), e.y(), e.z()))) {
                case SAME -> same++;
                case APPLY -> apply.add(e);
                case SKIP -> skipped++;
            }
        }
        return new Restore(apply, skipped, same);
    }

    /** 칸들의 xz 상자 [x0, z0, x1, z1] (비었으면 null) — 되돌리기 전에 청크를 불러올 범위. */
    public int[] bounds() {
        if (entries.isEmpty()) return null;
        int x0 = Integer.MAX_VALUE, z0 = Integer.MAX_VALUE, x1 = Integer.MIN_VALUE, z1 = Integer.MIN_VALUE;
        for (Entry e : entries) {
            x0 = Math.min(x0, e.x());
            z0 = Math.min(z0, e.z());
            x1 = Math.max(x1, e.x());
            z1 = Math.max(z1, e.z());
        }
        return new int[] {x0, z0, x1, z1};
    }
}
