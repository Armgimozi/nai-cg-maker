package kr.labyrinth.classes;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Log;
import org.bukkit.entity.Player;

/**
 * 최소 기본 구현: 직업은 PlayerData 에 저장, 마나는 마지막 갱신 이후 경과 시간 × 초당 재생으로 지연 계산
 * (틱 작업 없음). 직업 스킬은 classes 담당 구현이 대체.
 */
public class BasicClassService implements ClassService {

    protected final Services services;
    private final Map<UUID, double[]> mana = new ConcurrentHashMap<>(); // [현재, 마지막 갱신 ms]

    public BasicClassService(Services services) { this.services = services; }

    @Override
    public ClassDef classOf(Player player) {
        return services.content().classDef(services.data().get(player).classId());
    }

    @Override
    public void setClass(Player player, String classId) {
        if (classId != null && services.content().classDef(classId) == null) return;
        services.data().get(player).classId(classId);
        services.stats().recalc(player);
        mana.put(player.getUniqueId(), new double[] {maxMana(player), System.currentTimeMillis()});
    }

    @Override
    public double maxMana(Player player) { return services.stats().get(player).maxMp(); }

    @Override
    public double mana(Player player) {
        double max = maxMana(player);
        long now = System.currentTimeMillis();
        double[] m = mana.computeIfAbsent(player.getUniqueId(), u -> new double[] {max, now});
        double regen = services.stats().get(player).manaRegen();
        m[0] = Math.min(max, m[0] + regen * (now - m[1]) / 1000.0);
        m[1] = now;
        return m[0];
    }

    @Override
    public boolean useMana(Player player, double amount) {
        double cur = mana(player);
        if (cur + 1e-9 < amount) return false;
        mana.get(player.getUniqueId())[0] = cur - amount;
        return true;
    }

    @Override
    public void restoreMana(Player player, double amount) {
        double cur = mana(player);
        mana.get(player.getUniqueId())[0] = Math.min(maxMana(player), cur + amount);
    }

    @Override
    public boolean handleSkillInput(Player player, String input) {
        Log.notImplemented("ClassService.handleSkillInput(직업 스킬)");
        return false;
    }

    @Override
    public double cooldownRemaining(Player player, String skillId) { return 0; }
}
