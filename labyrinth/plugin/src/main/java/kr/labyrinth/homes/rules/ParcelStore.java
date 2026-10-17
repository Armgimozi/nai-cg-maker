package kr.labyrinth.homes.rules;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 맡긴 짐 {@code <월드>/labyrinth-parcels/<uuid>.yml} (0.3.7, review R3) — 월드 폴더에 두어 월드를 되돌리면 상자와 짐이 같이 맞는다 (R3b).
 * 소유: 묶음 B. 아이템은 {@code ItemStack#serializeAsBytes} 바이트 (이 클래스는 바이트만 다룸 — 서버 없이 시험).
 * <pre>
 * format: 1
 * owner_name: 하린
 * ready: [base64 …]            # 꺼낼 수 있는 짐
 * pending:                      # 비우는 중 (블록을 지우고 월드를 저장한 뒤 ready 로 옮김, R3a)
 *   plot: "3" · reason: vacate|reclaim · created_at · box [x0,z0,x1,z1] · window [y0,y1] · floor · custom · items [base64 …]
 * </pre>
 * 순서 (R3a): ① pending 쓰기 (짐 바이트) → ② 블록·엔티티 지우기 → ③ 주인 기록 풀기 → ④ {@code World#save} → ⑤ {@link #finish} (pending → ready).
 * 시작할 때 pending 이 남아 있으면 ②~⑤ 를 마저 한다 (②는 같은 틀로 다시 해도 같음). 꺼낼 때는 파일에서 먼저 뺀다 ({@link #remove}).
 * 모든 쓰기는 원자적. 메인 스레드에서만 쓴다.
 */
public final class ParcelStore {

    public static final String DIR = "labyrinth-parcels";

    /** 비우는 중인 짐. */
    public record Pending(String plotId, String reason, long createdAt, int x0, int z0, int x1, int z1, int yMin, int yMax, int floorY,
                          boolean custom, List<byte[]> items) {
        public Pending {
            items = items == null ? List.of() : List.copyOf(items);
        }
    }

    private final File dir;
    private final Map<UUID, Entry> cache = new ConcurrentHashMap<>();

    private static final class Entry {
        String ownerName = "";
        final List<byte[]> ready = new ArrayList<>();
        Pending pending;
    }

    public ParcelStore(File dir) { this.dir = dir; }

    public File dir() { return dir; }

    public File file(UUID owner) { return new File(dir, owner + ".yml"); }

    // ── 읽기 ─────────────────────────────────────────────────────────────

    private Entry entry(UUID owner) {
        return cache.computeIfAbsent(owner, this::read);
    }

    private Entry read(UUID owner) {
        Entry e = new Entry();
        File f = file(owner);
        if (!f.isFile()) return e;
        YamlConfiguration y = new YamlConfiguration();
        try {
            y.loadFromString(Files.readString(f.toPath(), StandardCharsets.UTF_8));
        } catch (IOException | InvalidConfigurationException ex) {
            File broken = new File(dir, f.getName() + ".broken-" + System.currentTimeMillis());
            f.renameTo(broken); // 다시 덮어쓰지 않게 비켜 둠 (관리자가 볼 수 있음)
            return e;
        }
        e.ownerName = y.getString("owner_name", "");
        for (String s : y.getStringList("ready")) {
            byte[] b = decode(s);
            if (b != null) e.ready.add(b);
        }
        ConfigurationSection p = y.getConfigurationSection("pending");
        if (p != null) {
            List<Integer> box = p.getIntegerList("box"), win = p.getIntegerList("window");
            List<byte[]> items = new ArrayList<>();
            for (String s : p.getStringList("items")) {
                byte[] b = decode(s);
                if (b != null) items.add(b);
            }
            if (box.size() == 4 && win.size() == 2) {
                e.pending = new Pending(p.getString("plot", ""), p.getString("reason", "vacate"), p.getLong("created_at", 0), box.get(0), box.get(1),
                        box.get(2), box.get(3), win.get(0), win.get(1), p.getInt("floor", win.get(0)), p.getBoolean("custom", false), items);
            } else {
                e.ready.addAll(items); // 틀이 깨진 pending: 짐은 살림 (블록은 손대지 않음)
            }
        }
        return e;
    }

    private void write(UUID owner, Entry e) throws IOException {
        File f = file(owner);
        if (e.ready.isEmpty() && e.pending == null) {
            Files.deleteIfExists(f.toPath());
            return;
        }
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 맡긴 짐 (0.3.7). 고치지 마세요. 이 폴더는 월드와 같이 다닙니다."));
        y.set("format", 1);
        y.set("owner_name", e.ownerName);
        List<String> r = new ArrayList<>();
        for (byte[] b : e.ready) r.add(Base64.getEncoder().encodeToString(b));
        y.set("ready", r);
        if (e.pending != null) {
            Pending p = e.pending;
            y.set("pending.plot", p.plotId());
            y.set("pending.reason", p.reason());
            y.set("pending.created_at", p.createdAt());
            y.set("pending.box", List.of(p.x0(), p.z0(), p.x1(), p.z1()));
            y.set("pending.window", List.of(p.yMin(), p.yMax()));
            y.set("pending.floor", p.floorY());
            y.set("pending.custom", p.custom());
            List<String> it = new ArrayList<>();
            for (byte[] b : p.items()) it.add(Base64.getEncoder().encodeToString(b));
            y.set("pending.items", it);
        }
        y.set("updated_at", System.currentTimeMillis());
        PlotStore.writeAtomic(f.toPath(), y.saveToString());
    }

    /** 꺼낼 수 있는 짐 (복사본). */
    public synchronized List<byte[]> ready(UUID owner) { return owner == null ? List.of() : new ArrayList<>(entry(owner).ready); }

    public synchronized int readyCount(UUID owner) { return owner == null ? 0 : entry(owner).ready.size(); }

    public synchronized Pending pending(UUID owner) { return owner == null ? null : entry(owner).pending; }

    public synchronized String ownerName(UUID owner) { return owner == null ? "" : entry(owner).ownerName; }

    /** 폴더 안 모든 짐 주인 (파일 이름). */
    public synchronized List<UUID> owners() {
        Set<UUID> out = new HashSet<>(cache.keySet());
        File[] fs = dir == null ? null : dir.listFiles((d, n) -> n.endsWith(".yml"));
        if (fs != null) for (File f : fs) {
            try {
                out.add(UUID.fromString(f.getName().substring(0, f.getName().length() - 4)));
            } catch (IllegalArgumentException ignored) {
                // 다른 파일
            }
        }
        List<UUID> l = new ArrayList<>(out);
        l.removeIf(u -> {
            Entry e = entry(u);
            return e.ready.isEmpty() && e.pending == null;
        });
        return l;
    }

    /** pending 이 남은 주인들 (시작 때 마저 함). */
    public synchronized List<UUID> pendingOwners() {
        List<UUID> out = new ArrayList<>();
        for (UUID u : owners()) if (entry(u).pending != null) out.add(u);
        return out;
    }

    // ── 쓰기 ─────────────────────────────────────────────────────────────

    /** ① 비우기 시작: pending 을 먼저 쓴다. 이미 pending 이 있으면 IllegalStateException (한 사람이 동시에 둘을 비울 수 없음). */
    public synchronized void begin(UUID owner, String ownerName, Pending p) throws IOException {
        Entry e = entry(owner);
        if (e.pending != null) throw new IllegalStateException("이미 비우는 중: " + e.pending.plotId());
        Entry next = copy(e);
        next.pending = p;
        if (ownerName != null && !ownerName.isBlank()) next.ownerName = ownerName;
        write(owner, next);
        cache.put(owner, next);
    }

    /** ⑤ 월드를 저장한 뒤: pending 짐을 ready 로. pending 이 없으면 false. */
    public synchronized boolean finish(UUID owner) throws IOException {
        Entry e = entry(owner);
        if (e.pending == null) return false;
        Entry next = copy(e);
        next.ready.addAll(e.pending.items());
        next.pending = null;
        write(owner, next);
        cache.put(owner, next);
        return true;
    }

    /** pending 을 버림 (① 다음 블록을 하나도 안 바꾸고 멈췄을 때만 — 짐은 아직 블록 안에 있음). */
    public synchronized void abort(UUID owner) throws IOException {
        Entry e = entry(owner);
        if (e.pending == null) return;
        Entry next = copy(e);
        next.pending = null;
        write(owner, next);
        cache.put(owner, next);
    }

    /** 꺼내기: 그 번호들 (ready 목록 차례) 을 파일에서 먼저 뺀다. 뺀 바이트를 돌려줌. */
    public synchronized List<byte[]> remove(UUID owner, Collection<Integer> indexes) throws IOException {
        Entry e = entry(owner);
        Set<Integer> idx = new HashSet<>(indexes);
        Entry next = copy(e);
        next.ready.clear();
        List<byte[]> taken = new ArrayList<>();
        for (int i = 0; i < e.ready.size(); i++) {
            if (idx.contains(i)) taken.add(e.ready.get(i));
            else next.ready.add(e.ready.get(i));
        }
        if (taken.isEmpty()) return taken;
        write(owner, next);
        cache.put(owner, next);
        return taken;
    }

    /** 못 준 것을 다시 넣기 · 관리자가 넣기. */
    public synchronized void add(UUID owner, String ownerName, List<byte[]> items) throws IOException {
        if (items == null || items.isEmpty()) return;
        Entry next = copy(entry(owner));
        next.ready.addAll(items);
        if (ownerName != null && !ownerName.isBlank()) next.ownerName = ownerName;
        write(owner, next);
        cache.put(owner, next);
    }

    /** 다시 읽기 (시험 · 관리자가 파일을 고친 뒤). */
    public synchronized void forget() { cache.clear(); }

    private static Entry copy(Entry e) {
        Entry n = new Entry();
        n.ownerName = e.ownerName;
        n.ready.addAll(e.ready);
        n.pending = e.pending;
        return n;
    }

    private static byte[] decode(String s) {
        if (s == null || s.isBlank()) return null;
        try {
            return Base64.getDecoder().decode(s.trim());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }
}
