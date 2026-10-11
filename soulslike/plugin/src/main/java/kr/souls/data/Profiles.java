package kr.souls.data;

import kr.souls.Keys;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.persistence.PersistentDataType;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 프로필 읽기·쓰기 (12.6). 접속 중인 사람의 프로필을 메모리에 들고 있다가 바꾼 때 PDC (souls:profile) 에 쓴다.
 * PDC 는 플레이어가 저장될 때 디스크에 가므로, 출신·레벨업·관리자 변경 같은 큰일 뒤에는 {@link #save(Player, boolean)} 로
 * player.saveData() 까지 부른다 (인벤토리와 PDC 가 같은 파일이라 시작 아이템과 장부가 함께 저장된다, 5.10).
 * 백업: plugins/Soulslike/profiles/&lt;uuid&gt;.json (쓰기만). 쓰기는 플러그인의 쓰레드 하나가 차례대로 한다: 잇달아 저장해도 (출신 고르기와
 * 그 뒤의 저장, 레벨업 뒤 나가기) 두 쓰기가 같은 임시 파일을 함께 쓰거나 옛 JSON 이 나중에 덮지 않는다 (검토 backup-tmp-race). 임시 파일
 * 이름도 쓰기마다 다르다. 끌 때 남은 쓰기를 기다린다 (shutdown). 깨진 프로필은 profiles/&lt;uuid&gt;.broken-&lt;ms&gt;.json 으로 남긴다.
 */
public final class Profiles implements Listener {
    private final Souls plugin;
    private final Map<UUID, Profile> live = new HashMap<>();
    private final File dir;
    /** 백업 쓰기 (차례대로 하나씩) */
    private final ExecutorService writer = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "souls-profile-backup");
        t.setDaemon(true);
        return t;
    });

    public Profiles(Souls plugin) {
        this.plugin = plugin;
        this.dir = new File(plugin.getDataFolder(), "profiles");
        // /reload 뒤: 접속 중인 사람을 다시 읽는다
        for (Player p : Bukkit.getOnlinePlayers()) load(p);
    }

    /** 이 사람의 프로필 (없으면 PDC 에서 읽는다). */
    public Profile of(Player p) {
        Profile pr = live.get(p.getUniqueId());
        return pr != null ? pr : load(p);
    }

    /** 접속 중인 사람만 (없으면 null). */
    public Profile peek(UUID id) {
        return live.get(id);
    }

    private Profile load(Player p) {
        String json = p.getPersistentDataContainer().get(Keys.PROFILE, PersistentDataType.STRING);
        Profile pr = Profile.parseStrict(json);
        if (pr == null) {
            plugin.getLogger().warning(p.getName() + " 의 프로필이 깨져 새로 시작합니다 (깨진 것은 profiles/ 에 남깁니다).");
            backup(p.getUniqueId(), json, ".broken-" + System.currentTimeMillis());
            pr = Profile.fresh();
        }
        live.put(p.getUniqueId(), pr);
        return pr;
    }

    /** PDC 에 쓴다. flush 면 player.saveData() 까지 (출신·레벨업·관리자 변경). 백업 JSON 도 쓴다. */
    public void save(Player p, boolean flush) {
        Profile pr = live.get(p.getUniqueId());
        if (pr == null) return;
        String json = pr.toJson();
        p.getPersistentDataContainer().set(Keys.PROFILE, PersistentDataType.STRING, json);
        if (flush) p.saveData();
        backup(p.getUniqueId(), json, "");
    }

    /**
     * 프로필을 처음 상태로. keepSouls (출신 다시 고르기) 면 소울과 "다시 골랐다" 표시를 남기고, 아니면 (관리자의 출신 지우기) 둘 다 지운다.
     * 낀 반지는 어느 쪽이든 남는다: 반지는 출신의 시작 아이템이 아니라 그 사람이 가진 아이템이고, 칸에 보이는 것은 프로필의 사본이라
     * 프로필에서 지우면 아이템이 사라진다 (item/RingSlots, 9.4).
     */
    public Profile reset(Player p, boolean keepSouls) {
        Profile old = of(p);
        Profile pr = Profile.fresh();
        if (keepSouls) {
            pr.setSouls(old.souls());
            pr.setRepicked(old.repicked());
        }
        for (int i = 0; i < Profile.RING_SLOTS; i++) pr.setRing(i, old.ring(i));
        pr.setSettingsSeen(old.settingsSeen());
        live.put(p.getUniqueId(), pr);
        return pr;
    }

    private void backup(UUID id, String json, String suffix) {
        File f = new File(dir, id + suffix + ".json");
        try {
            writer.execute(() -> {
                File tmp = new File(dir, id + suffix + ".json." + System.nanoTime() + ".tmp");
                try {
                    Files.createDirectories(dir.toPath());
                    Files.writeString(tmp.toPath(), json, StandardCharsets.UTF_8);
                    Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
                } catch (IOException ex) {
                    plugin.getLogger().warning("프로필 백업을 쓰지 못했습니다 (" + f.getName() + "): " + ex.getMessage());
                    try {
                        Files.deleteIfExists(tmp.toPath());
                    } catch (IOException ignored) {
                        // 지우지 못한 임시 파일은 다음 쓰기와 상관없다 (이름이 다르다)
                    }
                }
            });
        } catch (java.util.concurrent.RejectedExecutionException ex) {
            // 끄는 중 (shutdown 뒤): 백업은 쓰기만 하는 사본이라 건너뛴다. 정본은 PDC
        }
    }

    /** 끌 때: 남은 백업 쓰기를 기다린다 (길어도 5초). */
    public void shutdown() {
        writer.shutdown();
        try {
            if (!writer.awaitTermination(5, TimeUnit.SECONDS)) plugin.getLogger().warning("프로필 백업 쓰기가 끝나지 않아 두고 끕니다.");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onJoin(PlayerJoinEvent e) {
        load(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        // 나갈 때는 Paper 가 곧 플레이어를 저장하므로 PDC 에만 쓴다
        save(p, false);
        live.remove(p.getUniqueId());
    }

    /** 끌 때: 접속 중인 사람을 모두 PDC 에 쓴다 (서버가 끄면서 저장한다). */
    public void saveAll() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            Profile pr = live.get(p.getUniqueId());
            if (pr != null) p.getPersistentDataContainer().set(Keys.PROFILE, PersistentDataType.STRING, pr.toJson());
        }
    }
}
