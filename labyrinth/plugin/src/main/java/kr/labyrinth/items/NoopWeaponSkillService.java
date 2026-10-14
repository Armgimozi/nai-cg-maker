package kr.labyrinth.items;

import org.bukkit.entity.Player;

/** 안전한 기본 구현: 무기 스킬 없음. */
public class NoopWeaponSkillService implements WeaponSkillService {
    @Override
    public boolean handle(Player player, Input input) { return false; }

    @Override
    public double cooldownRemaining(Player player, String itemId, Input input) { return 0; }
}
