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
import java.util.function.Predicate;

/**
 * 큰 글씨와 잠깐 알림의 차례 (10.2). 큰 글씨(사망, 화톳불, 보스 처치)는 제목으로, 잠깐 알림은 빈 제목 + 부제목으로 보낸다
 * (바닐라는 제목이 있어야 부제목을 그린다). 큰 글씨가 떠 있는 동안 온 알림은 기다렸다 보낸다. 행동 막대에는 쓰지 않는다.
 * 우리 창 (Dialog) 이 열려 있는 동안에는 알림을 보내지 않고 기다렸다가 창이 닫히면 보낸다. 알림이 떠 있는 채 창이 열리면 걷어 두었다가
 * 다시 보낸다 (부제목이 창 뒤에 흐리게 비치지 않게, 검토 provisional-subtitle-bleed). 기다리는 알림은 사람마다 셋까지 (새것을 남긴다).
 */
public final class Titles {
    /** 기다리는 알림의 끝 (창이 오래 열려 있어도 쌓이지 않게) */
    private static final int MAX_WAITING = 3;
    /** 알림 하나가 떠 있는 틱 (5 + 40 + 15) */
    private static final int NOTICE_TICKS = 60;

    private static final class Q {
        long bigUntil;
        long noticeUntil;
        Component current;
        final ArrayDeque<Component> notices = new ArrayDeque<>();
    }

    private final Map<UUID, Q> queues = new HashMap<>();
    /** 이 사람에게 우리 창이 열려 있나 (Souls 가 Ui 로 건다) */
    private Predicate<Player> busy = p -> false;

    public void setBusy(Predicate<Player> busy) {
        this.busy = busy == null ? p -> false : busy;
    }

    private Q q(Player p) {
        return queues.computeIfAbsent(p.getUniqueId(), k -> new Q());
    }

    /** 큰 글씨. 틱 단위. */
    public void big(Player p, long now, Component title, Component sub, int fadeIn, int stay, int fadeOut) {
        Q q = q(p);
        q.bigUntil = now + fadeIn + stay + fadeOut;
        q.current = null;
        q.noticeUntil = now;
        p.showTitle(Title.title(title, sub == null ? Component.empty() : sub, times(fadeIn, stay, fadeOut)));
    }

    /** 잠깐 알림 (부제목). 큰 글씨가 떠 있거나 앞 알림이 기다리거나 창이 열려 있으면 기다린다. */
    public void notice(Player p, long now, Component text) {
        Q q = q(p);
        if (now < q.bigUntil || !q.notices.isEmpty() || busy.test(p)) {
            wait(q, text);
            return;
        }
        show(p, q, now, text);
    }

    /** 알림 둘을 잇달아 (둘째는 첫째가 진 뒤). 부제목은 한 줄이라 "두 줄" 알림은 이렇게 보낸다. */
    public void notices(Player p, long now, Component first, Component then) {
        notice(p, now, first);
        wait(q(p), then);
    }

    private static void wait(Q q, Component text) {
        q.notices.add(text);
        while (q.notices.size() > MAX_WAITING) q.notices.poll();
    }

    /** 우리 창이 열린다 (Ui.show): 떠 있는 알림을 걷고 기다리는 줄 맨 앞에 되돌린다. 큰 글씨는 그대로 둔다. */
    public void onDialog(Player p, long now) {
        Q q = queues.get(p.getUniqueId());
        if (q == null || now >= q.noticeUntil || now < q.bigUntil || q.current == null) return;
        p.clearTitle();
        q.notices.addFirst(q.current);
        while (q.notices.size() > MAX_WAITING) q.notices.pollLast();
        q.current = null;
        q.noticeUntil = now;
    }

    /** 떠 있는 글씨를 지우고 기다리던 알림도 버린다 (부활할 때). */
    public void clear(Player p) {
        Q q = queues.remove(p.getUniqueId());
        if (q != null) q.notices.clear();
        p.clearTitle();
    }

    private static void show(Player p, Q q, long now, Component text) {
        q.current = text;
        q.noticeUntil = now + NOTICE_TICKS;
        p.showTitle(Title.title(Component.empty(), text, times(5, 40, 15)));
    }

    private static Title.Times times(int in, int stay, int out) {
        return Title.Times.times(Duration.ofMillis(in * 50L), Duration.ofMillis(stay * 50L), Duration.ofMillis(out * 50L));
    }

    /** Ticker: 큰 글씨와 앞 알림이 끝났고 창이 닫혀 있으면 기다리던 알림을 하나씩. */
    public void tick(long now) {
        if (queues.isEmpty()) return;
        queues.entrySet().removeIf(en -> {
            Player p = Bukkit.getPlayer(en.getKey());
            if (p == null) return true;
            Q q = en.getValue();
            if (now >= q.bigUntil && now >= q.noticeUntil && !q.notices.isEmpty() && !busy.test(p)) {
                show(p, q, now, q.notices.poll());
            }
            return false;
        });
    }

    public void forget(UUID id) {
        queues.remove(id);
    }
}
