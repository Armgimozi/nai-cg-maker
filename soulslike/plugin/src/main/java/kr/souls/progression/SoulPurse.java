package kr.souls.progression;

import kr.souls.Souls;
import kr.souls.data.Profile;
import org.bukkit.entity.Player;

/**
 * 소울 지갑 (5.4, 5.10): 가진 소울은 프로필의 souls. HUD 오른쪽 아래 소울 상자가 이것을 읽는다 (Hud.setSoulSource).
 * 바뀌면 상자를 다시 그린다. 레벨업·죽음·휴식·나가기 때 저장한다 (적을 잡을 때마다 saveData 하지는 않는다).
 */
public final class SoulPurse {
    private final Souls plugin;

    public SoulPurse(Souls plugin) {
        this.plugin = plugin;
    }

    public long get(Player p) {
        return plugin.profiles().of(p).souls();
    }

    public void set(Player p, long n) {
        plugin.profiles().of(p).setSouls(n);
        plugin.hud().invalidate(p);
    }

    /** 더한다 (0 이상, Profile.SOULS_MAX 에서 멈춘다). */
    public void add(Player p, long n) {
        if (n <= 0) return;
        Profile pr = plugin.profiles().of(p);
        pr.setSouls(pr.souls() + n);
        plugin.hud().invalidate(p);
    }

    /** 쓴다. 모자라면 아무것도 바꾸지 않고 false. */
    public boolean spend(Player p, long n) {
        Profile pr = plugin.profiles().of(p);
        if (n < 0 || pr.souls() < n) return false;
        pr.setSouls(pr.souls() - n);
        plugin.hud().invalidate(p);
        return true;
    }
}
