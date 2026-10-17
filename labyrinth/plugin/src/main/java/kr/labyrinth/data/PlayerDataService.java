package kr.labyrinth.data;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.scheduler.BukkitTask;

/**
 * 플레이어 데이터 로드/저장. 접속 전(AsyncPlayerPreLogin)에 비동기로 읽어 두고, 나갈 때·자동저장(기본 5분) 때
 * 메인 스레드에서 YAML 문자열로 스냅샷을 떠서 전용 스레드가 파일에 쓴다(임시 파일 → 원자적 교체).
 */
public final class PlayerDataService implements Module, Listener {

    private final Services services;
    private final Path dir;
    private final Map<UUID, PlayerData> cache = new ConcurrentHashMap<>();
    /** 나간·오프라인 사람의 아직 안 쓴 스냅샷 — 그 사이 다시 들어오면 파일 대신 읽는다 ({@link PendingWrites}). */
    private final PendingWrites unwritten = new PendingWrites();
    private ExecutorService io;
    private BukkitTask autosave;

    public PlayerDataService(Services services) {
        this.services = services;
        this.dir = services.plugin().getDataFolder().toPath().resolve("players");
    }

    @Override
    public String name() { return "data"; }

    @Override
    public void enable() throws IOException {
        Files.createDirectories(dir);
        io = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "Labyrinth-PlayerData");
            t.setDaemon(true);
            return t;
        });
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        for (Player p : Bukkit.getOnlinePlayers()) cache.computeIfAbsent(p.getUniqueId(), id -> loadSync(id, p.getName()));
        scheduleAutosave();
    }

    private void scheduleAutosave() {
        if (autosave != null) autosave.cancel();
        long period = services.settings().autosaveMinutes() * 60L * 20L;
        autosave = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::saveDirtyAsync, period, period);
    }

    @Override
    public void reload() { scheduleAutosave(); }

    @Override
    public void disable() {
        if (autosave != null) autosave.cancel();
        HandlerList.unregisterAll(this);
        // 남은 비동기 작업을 끝낸 뒤 전원 동기 저장
        if (io != null) {
            io.shutdown();
            try {
                io.awaitTermination(10, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        for (PlayerData d : cache.values()) {
            d.touch();
            write(d.uuid(), d.toYaml());
        }
        cache.clear();
    }

    /** 온라인 플레이어 데이터 (항상 존재). */
    public PlayerData get(Player p) {
        return cache.computeIfAbsent(p.getUniqueId(), id -> loadSync(id, p.getName()));
    }

    /** 캐시에 있으면 반환, 없으면 null (오프라인). */
    public PlayerData getIfLoaded(UUID uuid) { return cache.get(uuid); }

    /** 오프라인 플레이어 데이터를 동기로 읽기 (관리 명령용, 캐시에 넣지 않음). 수정했다면 {@link #saveOffline}. */
    public PlayerData loadOffline(OfflinePlayer p) {
        PlayerData d = cache.get(p.getUniqueId());
        return d != null ? d : loadSync(p.getUniqueId(), p.getName() == null ? p.getUniqueId().toString() : p.getName());
    }

    public void saveOffline(PlayerData d) {
        if (cache.containsKey(d.uuid())) return; // 온라인이면 평소대로 저장됨
        writeLater(d.uuid(), d.toYaml());
    }

    /** 캐시 밖 사람의 스냅샷 쓰기: 다 쓸 때까지 {@link #unwritten} 에 두어 그 사이 읽기가 파일의 예전 값을 보지 않게. */
    private void writeLater(UUID id, String yaml) {
        unwritten.put(id, yaml);
        io.execute(() -> {
            try {
                write(id, yaml);
            } finally {
                unwritten.done(id, yaml);
            }
        });
    }

    /** 즉시 비동기 저장 (중요한 진행 직후 — 층 클리어 등). */
    public void saveAsync(Player p) {
        PlayerData d = cache.get(p.getUniqueId());
        if (d == null) return;
        d.clearDirty();
        String yaml = d.toYaml();
        io.execute(() -> write(d.uuid(), yaml));
    }

    private void saveDirtyAsync() {
        int n = 0;
        for (PlayerData d : cache.values()) {
            if (!d.isDirty()) continue;
            d.clearDirty();
            String yaml = d.toYaml();
            io.execute(() -> write(d.uuid(), yaml));
            n++;
        }
        if (n > 0) Log.get().fine("자동 저장: " + n + "명");
    }

    private Path file(UUID uuid) { return dir.resolve(uuid + ".yml"); }

    private PlayerData loadSync(UUID uuid, String name) {
        Path f = file(uuid);
        String pending = unwritten.get(uuid);
        if (pending != null) {
            try {
                PlayerData d = PlayerData.fromYaml(uuid, name, pending);
                d.name(name);
                return d;
            } catch (Exception e) {
                Log.error("플레이어 데이터 (아직 안 쓴 스냅샷) 읽기 실패(" + uuid + ") — 파일을 읽습니다", e);
            }
        }
        if (Files.exists(f)) {
            try {
                PlayerData d = PlayerData.fromYaml(uuid, name, Files.readString(f, StandardCharsets.UTF_8));
                d.name(name);
                return d;
            } catch (Exception e) {
                Log.error("플레이어 데이터 읽기 실패(" + uuid + ") — 백업 후 새로 시작합니다", e);
                try {
                    Files.copy(f, dir.resolve(uuid + ".broken-" + System.currentTimeMillis() + ".yml"));
                } catch (IOException ignored) {
                    // 백업 실패는 무시
                }
            }
        }
        PlayerData d = new PlayerData(uuid, name);
        d.markDirty();
        return d;
    }

    private void write(UUID uuid, String yaml) {
        try {
            Path tmp = dir.resolve(uuid + ".yml.tmp");
            Files.writeString(tmp, yaml, StandardCharsets.UTF_8);
            Files.move(tmp, file(uuid), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            Log.error("플레이어 데이터 저장 실패(" + uuid + ")", e);
        }
    }

    // ── 이벤트 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPreLogin(AsyncPlayerPreLoginEvent e) {
        if (e.getLoginResult() != AsyncPlayerPreLoginEvent.Result.ALLOWED) return;
        cache.computeIfAbsent(e.getUniqueId(), id -> loadSync(id, e.getName()));
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onJoin(PlayerJoinEvent e) {
        PlayerData d = get(e.getPlayer());
        d.name(e.getPlayer().getName());
        d.touch();
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        PlayerData d = cache.get(id);
        if (d == null) return;
        d.touch();
        String yaml = d.toYaml();
        // 다른 MONITOR 리스너가 끝난 다음 틱에 캐시에서 뺀다 (재접속 경합 방지: 다시 들어왔으면 유지)
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (Bukkit.getPlayer(id) == null) cache.remove(id);
        });
        // 빨리 다시 들어와 캐시에서 빠진 뒤 파일을 읽어도 (쓰기가 늦으면) 이 스냅샷을 읽는다
        writeLater(id, yaml);
    }
}
