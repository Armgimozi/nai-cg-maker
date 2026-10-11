package kr.augsky.augment;

import kr.augsky.util.P;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

public final class AugmentRegistry {
    private final Map<String, AugmentDef> augments = new LinkedHashMap<>();
    private final Logger log;

    public AugmentRegistry(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml) {
        augments.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            Tier tier = Tier.parse(p.s("tier", "SILVER"));
            if (tier == null) {
                log.warning("증강 " + id + " 의 tier 를 알 수 없음");
                continue;
            }
            Material icon = Material.matchMaterial(p.s("icon", "PAPER"));
            if (icon == null) icon = Material.PAPER;
            List<AugmentDef.Effect> effects = new ArrayList<>();
            for (Map<?, ?> m : p.maps("effects")) {
                P ep = new P(m);
                effects.add(new AugmentDef.Effect(ep.s("type", "").toLowerCase(), ep));
            }
            augments.put(id, new AugmentDef(id, tier, p.s("name", id), icon, p.strings("description"),
                    Math.max(1, p.i("max_stacks", 1)), Math.max(1, p.i("weight", 10)), effects));
        }
        int s = 0, g = 0, pr = 0;
        for (AugmentDef d : augments.values()) {
            switch (d.tier()) {
                case SILVER -> s++;
                case GOLD -> g++;
                case PRISM -> pr++;
            }
        }
        log.info("증강 " + augments.size() + "개 불러옴 (실버 " + s + ", 골드 " + g + ", 프리즘 " + pr + ")");
    }

    public AugmentDef get(String id) {
        return id == null ? null : augments.get(id);
    }

    public Map<String, AugmentDef> all() {
        return augments;
    }

    public List<AugmentDef> ofTier(Tier t) {
        List<AugmentDef> out = new ArrayList<>();
        for (AugmentDef d : augments.values()) if (d.tier() == t) out.add(d);
        return out;
    }
}
