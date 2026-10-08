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

/**
 * 프로필 읽기·쓰기 (12.6). 접속 중인 사람의 프로필을 메모리에 들고 있다가 바꾼 때 PDC (souls:profile) 에 쓴다.
 * PDC 는 플레이어가 저장될 때 디스크에 가므로, 출신·레벨업·관리자 변경 같은 큰일 뒤에는 {@link #save(Player, boolean)} 로
 * player.saveData() 까지 부른다 (인벤토리와 PDC 가 같은 파일이라 시작 아이템과 장부가 함께 저장된다, 5.10).
 * 백업: plugins/Soulslike/profiles/&lt;uuid&gt;.json (쓰기만, 비동기). 깨진 프로필은 profiles/&lt;uuid&gt;.broken-&lt;ms&gt;.json 으로 남긴다.
 */
public final class Profiles implements Listener {
    private final Souls plugin;
    private final Map<UUID, Profile> live = new HashMap<>();
    private final File dir;

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

    /** 프로필을 처음 상태로 (관리자의 출신 지우기). 소울은 keepSouls 면 남긴다. */
    public Profile reset(Player p, boolean keepSouls) {
        Profile old = of(p);
        Profile pr = Profile.fresh();
        if (keepSouls) pr.setSouls(old.souls());
        pr.setSettingsSeen(old.settingsSeen());
        live.put(p.getUniqueId(), pr);
        return pr;
    }

    private void backup(UUID id, String json, String suffix) {
        File f = new File(dir, id + suffix + ".json");
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            try {
                Files.createDirectories(dir.toPath());
                File tmp = new File(dir, id + suffix + ".json.tmp");
                Files.writeString(tmp.toPath(), json, StandardCharsets.UTF_8);
                Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException ex) {
                plugin.getLogger().warning("프로필 백업을 쓰지 못했습니다 (" + f.getName() + "): " + ex.getMessage());
            }
        });
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
