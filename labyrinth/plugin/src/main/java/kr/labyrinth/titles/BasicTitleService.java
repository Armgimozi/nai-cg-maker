package kr.labyrinth.titles;

import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/** 최소 기본 구현: 주인 기록·지급·장착 저장과 알림만 (사건 판정·방송·보너스는 titles 담당 구현이 대체). */
public class BasicTitleService implements TitleService {

    protected final Services services;

    public BasicTitleService(Services services) { this.services = services; }

    @Override
    public boolean grant(Player player, String achievementId) {
        AchievementDef def = services.content().achievements().get(achievementId);
        if (def == null) return false;
        PlayerData d = services.data().get(player);
        if (d.hasAchievement(achievementId)) return false;
        if (!services.records().claim(TitleView.recordKey(achievementId), List.of(player.getUniqueId()),
                List.of(player.getName()), Map.of("achievement", achievementId))) return false;
        d.grantAchievement(achievementId);
        if (def.rewardGold() > 0) d.addGold(def.rewardGold());
        def.rewardItems().forEach((id, n) -> services.items().give(player, id, n, "reward"));
        Text.send(player, TitleView.ownerMessage(def, services.content(), ""));
        return true;
    }

    @Override
    public void recheck(Player player) {}

    @Override
    public boolean equip(Player player, String achievementId) {
        PlayerData d = services.data().get(player);
        if (achievementId != null && !d.hasAchievement(achievementId)) return false;
        d.equippedTitle(achievementId);
        return true;
    }

    @Override
    public AchievementDef equipped(Player player) {
        String id = services.data().get(player).equippedTitle();
        return id == null ? null : services.content().achievements().get(id);
    }

    @Override
    public Component prefix(Player player) {
        AchievementDef def = equipped(player);
        return def == null ? Component.empty() : Text.mm("<dark_gray>[</dark_gray>" + def.title() + "<dark_gray>]</dark_gray> ");
    }
}
