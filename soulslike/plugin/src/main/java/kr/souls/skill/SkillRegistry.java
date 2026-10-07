package kr.souls.skill;

import kr.souls.util.P;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

public final class SkillRegistry {
    private final Map<String, SkillDef> skills = new LinkedHashMap<>();
    private final Logger log;

    public SkillRegistry(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml) {
        skills.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            List<Mechanic> mech = Mechanics.parseList(p.maps("mechanics"));
            if (mech.isEmpty()) log.warning("스킬 " + id + " 에 mechanics 가 없습니다");
            skills.put(id, new SkillDef(id, p.s("name", id), p.strings("description"), p.d("cooldown", 5), mech));
        }
        log.info("스킬 " + skills.size() + "개 불러옴");
    }

    public SkillDef get(String id) {
        return id == null ? null : skills.get(id);
    }

    public Map<String, SkillDef> all() {
        return skills;
    }
}
