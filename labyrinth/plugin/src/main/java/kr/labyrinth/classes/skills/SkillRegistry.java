package kr.labyrinth.classes.skills;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** classes.yml 스킬 id → 구현. 6직업 × 4스킬 = 24개 (GDD §4.2). */
public final class SkillRegistry {

    private final Map<String, Skill> skills = new LinkedHashMap<>();

    public SkillRegistry() {
        GuardianSkills.all().forEach(this::register);
        BerserkerSkills.all().forEach(this::register);
        HunterSkills.all().forEach(this::register);
        ArcanistSkills.all().forEach(this::register);
        PriestSkills.all().forEach(this::register);
        ShadowSkills.all().forEach(this::register);
    }

    public void register(Skill s) { skills.put(s.id(), s); }

    public Skill get(String id) { return id == null ? null : skills.get(id); }

    public Map<String, Skill> all() { return Collections.unmodifiableMap(skills); }
}
