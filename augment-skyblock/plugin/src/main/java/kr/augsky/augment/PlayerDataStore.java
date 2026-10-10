package kr.augsky.augment;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.io.File;
import java.io.IOException;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Logger;

public final class PlayerDataStore {
    private final File dir;
    private final Logger log;
    private final Map<UUID, PlayerData> cache = new HashMap<>();

    public PlayerDataStore(File dataFolder, Logger log) {
        this.dir = new File(dataFolder, "players");
        this.log = log;
        if (!dir.exists() && !dir.mkdirs()) log.warning("players 폴더를 만들 수 없습니다");
    }

    public PlayerData get(UUID id) {
        return cache.computeIfAbsent(id, this::load);
    }

    public Collection<PlayerData> loaded() {
        return cache.values();
    }

    private PlayerData load(UUID id) {
        PlayerData d = new PlayerData(id);
        File f = new File(dir, id + ".yml");
        if (!f.exists()) return d;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        d.lastName = y.getString("name", "");
        ConfigurationSection aug = y.getConfigurationSection("augments");
        if (aug != null) for (String k : aug.getKeys(false)) d.augments.put(k, aug.getInt(k, 1));
        d.soul = y.getDouble("soul", 0);
        d.tank = y.getDouble("tank-engine", 0);
        d.starterGiven = y.getBoolean("starter-given", false);
        d.picks = y.getInt("picks", 0);
        d.usedAltars.addAll(y.getStringList("used-altars"));
        Tier t = Tier.parse(y.getString("offer.tier"));
        if (t != null) {
            d.offerTier = t;
            d.offer.addAll(y.getStringList("offer.options"));
            d.rerolls = y.getInt("offer.rerolls", 0);
        }
        return d;
    }

    public void save(PlayerData d) {
        YamlConfiguration y = new YamlConfiguration();
        y.set("name", d.lastName);
        for (var en : d.augments.entrySet()) y.set("augments." + en.getKey(), en.getValue());
        y.set("soul", d.soul);
        if (d.tank > 0) y.set("tank-engine", d.tank);
        y.set("starter-given", d.starterGiven);
        y.set("picks", d.picks);
        if (!d.usedAltars.isEmpty()) y.set("used-altars", new java.util.ArrayList<>(d.usedAltars));
        if (d.hasOffer()) {
            y.set("offer.tier", d.offerTier.name());
            y.set("offer.options", d.offer);
            y.set("offer.rerolls", d.rerolls);
        }
        try {
            y.save(new File(dir, d.id + ".yml"));
            d.dirty = false;
        } catch (IOException e) {
            log.warning("플레이어 데이터 저장 실패: " + d.id + " " + e.getMessage());
        }
    }

    public void unload(UUID id) {
        PlayerData d = cache.remove(id);
        if (d != null) save(d);
    }

    public void saveAll() {
        for (PlayerData d : cache.values()) save(d);
    }
}
