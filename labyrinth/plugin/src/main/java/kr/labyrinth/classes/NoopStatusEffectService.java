package kr.labyrinth.classes;

import java.util.Map;
import kr.labyrinth.core.Log;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/** 안전한 기본 구현: 효과 없음. */
public class NoopStatusEffectService implements StatusEffectService {
    @Override
    public void apply(LivingEntity target, String effectId, double durationSeconds, double potency, LivingEntity source) {
        Log.notImplemented("StatusEffectService.apply");
    }

    @Override
    public boolean has(LivingEntity target, String effectId) { return false; }

    @Override
    public int stacks(LivingEntity target, String effectId) { return 0; }

    @Override
    public void clear(LivingEntity target, String effectId) {}

    @Override
    public void cleanse(LivingEntity target) {}

    @Override
    public void applyBuff(Player player, Map<String, Double> buff, double durationSeconds, String sourceId) {
        Log.notImplemented("StatusEffectService.applyBuff");
    }
}
