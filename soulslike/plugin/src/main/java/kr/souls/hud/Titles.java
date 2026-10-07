package kr.souls.hud;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 큰 글씨와 잠깐 알림의 차례 (10.2). 큰 글씨(사망, 화톳불, 보스 처치)는 제목으로, 잠깐 알림은 빈 제목 + 부제목으로 보낸다
 * (바닐라는 제목이 있어야 부제목을 그린다). 큰 글씨가 떠 있는 동안 온 알림은 기다렸다 보낸다. 행동 막대에는 쓰지 않는다.
 */
public final class Titles {
    private static final class Q {
        long bigUntil;
        final ArrayDeque<Component> notices = new ArrayDeque<>();
    }

    private final Map<UUID, Q> queues = new HashMap<>();

    private Q q(Player p) {
        return queues.computeIfAbsent(p.getUniqueId(), k -> new Q());
    }

    /** 큰 글씨. 틱 단위. */
    public void big(Player p, long now, Component title, Component sub, int fadeIn, int stay, int fadeOut) {
        Q q = q(p);
        q.bigUntil = now + fadeIn + stay + fadeOut;
        p.showTitle(Title.title(title, sub == null ? Component.empty() : sub, times(fadeIn, stay, fadeOut)));
    }

    /** 잠깐 알림 (부제목). */
    public void notice(Player p, long now, Component text) {
        Q q = q(p);
        if (now < q.bigUntil) {
            q.notices.add(text);
            return;
        }
        show(p, text);
    }

    /** 떠 있는 글씨를 지우고 기다리던 알림도 버린다 (부활할 때). */
    public void clear(Player p) {
        Q q = queues.remove(p.getUniqueId());
        if (q != null) q.notices.clear();
        p.clearTitle();
    }

    private static void show(Player p, Component text) {
        p.showTitle(Title.title(Component.empty(), text, times(5, 40, 15)));
    }

    private static Title.Times times(int in, int stay, int out) {
        return Title.Times.times(Duration.ofMillis(in * 50L), Duration.ofMillis(stay * 50L), Duration.ofMillis(out * 50L));
    }

    /** Ticker: 큰 글씨가 끝났으면 기다리던 알림을 하나씩. */
    public void tick(long now) {
        if (queues.isEmpty()) return;
        queues.entrySet().removeIf(en -> {
            Player p = Bukkit.getPlayer(en.getKey());
            if (p == null) return true;
            Q q = en.getValue();
            if (now >= q.bigUntil && !q.notices.isEmpty()) {
                show(p, q.notices.poll());
                q.bigUntil = now + 60;
            }
            return false;
        });
    }

    public void forget(UUID id) {
        queues.remove(id);
    }
}
