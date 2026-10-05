package kr.augsky.mob;

import kr.augsky.util.P;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.EntityType;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

public final class MobRegistry {
    private final Map<String, MobDef> mobs = new LinkedHashMap<>();
    private final Map<String, MobDef.Rift> rifts = new LinkedHashMap<>();
    private final Logger log;

    public MobRegistry(Logger log) {
        this.log = log;
    }

    public void load(YamlConfiguration yml) {
        mobs.clear();
        rifts.clear();
        ConfigurationSection ms = yml.getConfigurationSection("mobs");
        if (ms != null) {
            for (String id : ms.getKeys(false)) {
                ConfigurationSection sec = ms.getConfigurationSection(id);
                if (sec == null) continue;
                try {
                    mobs.put(id, parse(id, P.of(sec)));
                } catch (Exception e) {
                    log.warning("몬스터 " + id + " 해석 실패: " + e.getMessage());
                }
            }
        }
        ConfigurationSection rs = yml.getConfigurationSection("rifts");
        if (rs != null) {
            for (String id : rs.getKeys(false)) {
                P p = P.of(rs.getConfigurationSection(id));
                rifts.put(id, new MobDef.Rift(id, p.s("name", id), p.strings("mobs"), p.i("max_alive", 6),
                        p.d("interval", 6), p.d("radius", 9), p.s("boss", null), p.s("summon_item", null)));
            }
        }
        long bosses = mobs.values().stream().filter(MobDef::boss).count();
        log.info("몬스터 " + mobs.size() + "종 (보스 " + bosses + "), 균열 " + rifts.size() + "곳 불러옴");
    }

    private MobDef parse(String id, P p) {
        EntityType type = EntityType.valueOf(p.s("type", "ZOMBIE").toUpperCase(Locale.ROOT));
        Map<String, String> eq = new LinkedHashMap<>();
        P e = p.sub("equipment");
        if (e != null) for (var en : e.m.entrySet()) eq.put(en.getKey(), String.valueOf(en.getValue()));
        List<MobDef.Potion> effects = new ArrayList<>();
        for (Map<?, ?> m : p.maps("effects")) {
            P q = new P(m);
            effects.add(new MobDef.Potion(q.s("effect", "speed"), q.i("amplifier", 0)));
        }
        List<MobDef.Ability> abilities = new ArrayList<>();
        for (Map<?, ?> m : p.maps("abilities")) {
            P q = new P(m);
            abilities.add(new MobDef.Ability(q.s("skill", ""), q.s("trigger", "timer"), q.d("cooldown", 6),
                    q.d("range", 12), q.d("chance", 1), q.d("threshold", 0.5)));
        }
        List<MobDef.Drop> drops = new ArrayList<>();
        for (Map<?, ?> m : p.maps("drops")) {
            P q = new P(m);
            int min = q.i("min", q.i("amount", 1));
            drops.add(new MobDef.Drop(q.s("item", "shard"), min, Math.max(min, q.i("max", min)), q.d("chance", 1)));
        }
        MobDef.Natural nat = null;
        P n = p.sub("natural");
        if (n != null) {
            Set<EntityType> rep = new HashSet<>();
            for (String s : n.strings("replace")) rep.add(EntityType.valueOf(s.toUpperCase(Locale.ROOT)));
            nat = new MobDef.Natural(rep, n.d("chance", 0.05), new HashSet<>(n.strings("worlds")));
        }
        return new MobDef(id, p.s("name", id), type, p.d("health", 20), p.d("damage", -1), p.d("speed", -1),
                p.d("armor", 0), p.d("scale", 1), p.d("knockback_resistance", 0), p.d("follow_range", 24),
                p.d("skill_power", 1), p.b("boss", false), p.s("boss_color", "RED"), p.b("burn_in_day", false),
                p.b("glowing", false), p.b("baby", false), p.i("size", 0), eq, effects, abilities, drops,
                p.i("xp", 10), p.b("vanilla_drops", true), nat);
    }

    public MobDef get(String id) {
        return id == null ? null : mobs.get(id);
    }

    public Map<String, MobDef> all() {
        return mobs;
    }

    public Map<String, MobDef.Rift> rifts() {
        return rifts;
    }
}
