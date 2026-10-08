package kr.souls.hud;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import kr.souls.Config;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.Pool;
import kr.souls.skill.Combat;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.ShadowColor;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerExpChangeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;

import java.text.NumberFormat;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.ToLongFunction;

/**
 * 다크 소울 HUD (10.2, 2026-10-07 사용자 결정). 화면에 무엇을 띄우는 곳은 여기 한 곳이다 (행동 막대와 HUD 보스 막대를
 * 다른 체계가 덮어쓰지 않게). 다른 체계는 값만 넘긴다.
 *  - 왼쪽 위 막대 셋 (체력 · 마나 · 스태미나): 사람마다 HUD 전용 보스 막대 하나 (WHITE, 리소스팩이 막대 그림을 투명하게 했다)
 *    의 이름에 그림 글자 (souls:hud) 로 그린다. 길이는 최대치에 비례하고 (설정 hud.bars), 맞으면 잃은 몫이 잠깐 바랜 양피지빛으로
 *    남았다가 줄어든다. 바뀐 틱에 보낸다. 진짜 보스는 RED (체력)·YELLOW (자세) 막대를 쓴다.
 *  - 오른쪽 아래 소울 수 상자: 행동 막대. 바뀔 때와 actionbar-refresh 틱마다 보낸다 (바닐라는 3초 뒤 흐려진다).
 *  - 보스 막대 (화면 아래 가운데, 다크 소울처럼 이름은 막대 왼쪽 끝 위): 보스마다 보스 막대 하나 (RED, 팩이 막대 그림을 투명하게
 *    했다). 이름 줄에 [이름 사본][체력·자세 막대 그림 글자][이름][빈칸] 을 쓴다 ({@link #boss}). 바닐라는 이름 줄을 글 폭의 반만큼
 *    가운데에서 왼쪽으로 당겨 그리는데 이름 폭은 그 사람의 언어·글꼴이 정해 서버가 모른다. 같은 이름을 두 번 쓰면 첫 사본이 그
 *    반을 먹어 막대는 늘 가운데에서, 둘째 이름은 늘 가운데 - 막대 반폭에서 시작한다. 첫 사본은 글꼴 셰이더가 지우고 (표식 색
 *    markHidden), 막대·이름은 셰이더가 화면 아래로 내린다 (pack/hud.py boss_bars). 맞으면 잃은 몫이 잠깐 남았다가 줄어든다.
 *  - 자리: 글 전체의 진행 폭을 0 으로 맞춰 (빈칸 글자로 되돌아온다) 화면 가운데에서 시작하게 하고, 거기서 layout.left 왼쪽
 *    (막대) / layout.right 오른쪽 (상자 끝) 에 그린다. 글자색이 표식 색 (layout.markLeft/markRight) 이라 팩의 글꼴 셰이더가
 *    화면 가장자리로 옮긴다 (pack/hud.py). 짜는 차례는 pack/hud.py 의 bar_line·souls_line 과 같다.
 *  - 바닐라 하트·허기·방어·경험치 막대는 팩이 숨긴다. 진짜 경험치는 늘 0 이고 레벨도 0 (형광 초록 숫자가 서지 않는다).
 *  - 죽어 있는 동안은 HUD 를 비운다 (다크 소울처럼 YOU DIED 만).
 *  - 그림 글자는 팩을 실은 사람에게만 쓴다 (팩을 싣기 전 몇 초는 개인 영역 문자가 빈 네모로, HUD 보스 막대가 바닐라 흰 막대로
 *    보인다). 그 전과 glyphs.yml 에 HUD 그림 글자가 없을 때 (옛 팩) 는 막대 없이 행동 막대 글 "소울 N" ("마나 n/m") 으로 대신한다.
 */
public final class Hud implements Listener {
    /** 맞은 뒤 잃은 몫이 그대로 남는 틱. 그 뒤 틱마다 남은 몫의 1/4 씩 줄어든다 */
    private static final int TRAIL_HOLD = 16;
    private static final int[] RUNS = {128, 64, 32, 16, 8, 4, 2, 1};
    private static final Key HUD_FONT = Key.key("souls", "hud");

    private static final class View {
        BossBar bar;
        String barKey;
        long barAt;
        /** 지난 틱의 체력 채움 (픽셀, -1 은 아직 없음), 잃은 몫의 오른쪽 끝, 줄기 시작하는 틱 */
        int hpFill = -1;
        int trailTop;
        long trailHold;
        Component souls;
        String soulsKey;
        long soulsAt;
        boolean blank;
        /** 시험 줄 (/soulstest hud) 에 보일 마지막 값: hp 채움·길이·잃은 몫, fp 채움·길이, st 채움·길이 */
        final int[] last = new int[7];
        /** 띄운 보스 막대 (보스 id → 막대). 띄운 차례대로 화면 아래에서 위로 쌓인다 */
        final Map<String, Boss> bosses = new LinkedHashMap<>();
    }

    /** 보스 막대 하나: 이름 열쇠, 체력·자세 (지금, 최대), 잃은 몫 (체력 막대처럼), 마지막에 보낸 값. */
    private static final class Boss {
        BossBar bar;
        String nameKey;
        double hp, hpMax, post, postMax;
        int fill = -1, trailTop;
        long trailHold, at;
        String key;
    }

    private final Souls plugin;
    private final Map<UUID, View> views = new HashMap<>();
    /** 팩을 실은 사람 (SUCCESSFULLY_LOADED, 설정 단계에서 보낸 판은 들어올 때 이미 실었다) */
    private final Set<UUID> packed = new HashSet<>();
    /** 소울 수 (M2 의 SoulPurse 가 바꿔 끼운다). 그 전에는 0 */
    private ToLongFunction<Player> souls = p -> 0;

    public Hud(Souls plugin) {
        this.plugin = plugin;
        // /reload 뒤: 접속 중인 사람은 이미 팩을 실었다
        for (Player p : Bukkit.getOnlinePlayers()) packed.add(p.getUniqueId());
    }

    public void setSoulSource(ToLongFunction<Player> f) {
        souls = f == null ? p -> 0 : f;
    }

    private View view(Player p) {
        return views.computeIfAbsent(p.getUniqueId(), k -> new View());
    }

    /** 이 사람에게 그림 글자 HUD 를 쓰는가: 팩을 실었고 glyphs.yml 에 HUD 자리 값이 있다. */
    private boolean glyphs(Player p) {
        return hasPack(p) && Glyphs.layout() != null && Glyphs.get("hud_hp_fill_1") != null;
    }

    /**
     * 이 사람이 서버 팩을 실었는가 (SUCCESSFULLY_LOADED, 설정 단계에서 보낸 판은 들어올 때). 팩 글꼴이 없는 사람에게 그림 글자를 보내면
     * 빈 네모 줄이 된다 (HUD, 서서히 나타나는 YOU DIED: DeathFlow).
     */
    public boolean hasPack(Player p) {
        return packed.contains(p.getUniqueId());
    }

    /** 막대와 소울 상자를 다음 틱에 다시 만들어 보낸다. */
    public void invalidate(Player p) {
        View v = view(p);
        v.barKey = null;
        v.soulsKey = null;
        v.souls = null;
        for (Boss b : v.bosses.values()) b.key = null;
    }

    /** 플러그인을 끌 때: 보스 막대를 거둔다 (/reload 뒤 둘이 되지 않게). */
    public void shutdown() {
        for (Map.Entry<UUID, View> e : views.entrySet()) {
            Player p = Bukkit.getPlayer(e.getKey());
            if (p == null) continue;
            if (e.getValue().bar != null) p.hideBossBar(e.getValue().bar);
            for (Boss b : e.getValue().bosses.values()) p.hideBossBar(b.bar);
        }
        views.clear();
    }

    /**
     * 보스 막대를 띄우거나 값을 바꾼다 (M2 의 boss/BossBars 가 부른다. 지금은 시험 명령 /soulstest boss). id 마다 하나.
     * nameKey 는 lang 열쇠 (보스 이름). hp·posture 는 지금 값, 최대는 0 보다 크게. 다음 틱에 그린다.
     */
    public void boss(Player p, String id, String nameKey, double hp, double hpMax, double posture, double postureMax) {
        View v = view(p);
        Boss b = v.bosses.get(id);
        if (b == null) {
            b = new Boss();
            b.bar = BossBar.bossBar(Component.empty(), 0f, BossBar.Color.RED, BossBar.Overlay.PROGRESS);
            v.bosses.put(id, b);
            p.showBossBar(b.bar);
        }
        if (!nameKey.equals(b.nameKey)) b.key = null;
        b.nameKey = nameKey;
        b.hpMax = Math.max(1e-6, hpMax);
        b.hp = Math.max(0, Math.min(hp, b.hpMax));
        b.postMax = Math.max(1e-6, postureMax);
        b.post = Math.max(0, Math.min(posture, b.postMax));
    }

    /** 보스 막대를 거둔다 (쓰러뜨렸거나 싸움에서 벗어났을 때). id 가 없으면 아무것도 하지 않는다. */
    public void bossOff(Player p, String id) {
        View v = views.get(p.getUniqueId());
        Boss b = v == null ? null : v.bosses.remove(id);
        if (b != null) p.hideBossBar(b.bar);
    }

    public void tick(long now) {
        for (Player p : Bukkit.getOnlinePlayers()) {
            View v = view(p);
            if (p.isDead()) {
                if (!v.blank) {
                    if (v.bar != null) v.bar.name(Component.empty());
                    p.sendActionBar(Component.empty());
                    v.blank = true;
                    v.barKey = null;
                    v.soulsKey = null;
                    v.hpFill = -1;
                }
                continue;
            }
            v.blank = false;
            bars(p, v, now);
            souls(p, v, now);
            for (Boss b : v.bosses.values()) boss(p, b, now);
        }
    }

    // ------------------------------------------------------------------ 막대 셋

    private void bars(Player p, View v, long now) {
        if (!glyphs(p)) return;
        Glyphs.Layout lay = Glyphs.layout();
        if (v.bar == null) {
            // HUD 전용 보스 막대 (WHITE: 팩이 막대 그림을 투명하게 했다). 다른 보스 막대보다 먼저 띄워 맨 위 자리를 쓴다
            v.bar = BossBar.bossBar(Component.empty(), 0f, BossBar.Color.WHITE, BossBar.Overlay.PROGRESS);
            p.showBossBar(v.bar);
        }
        Config.HudCfg c = plugin.cfg().hud;
        CombatState st = CombatState.of(p);
        double hpMax = Math.max(1, Combat.maxHealth(p));
        int hpLen = length(hpMax * c.healthPx(), c);
        int hpFill = fill(Math.min(p.getHealth(), hpMax), hpMax, hpLen);
        if (v.hpFill >= 0 && hpFill < v.hpFill) {
            v.trailTop = Math.max(v.trailTop, v.hpFill);
            v.trailHold = now + TRAIL_HOLD;
        }
        if (v.trailTop <= hpFill) v.trailTop = hpFill;
        else if (now >= v.trailHold) v.trailTop = Math.max(hpFill, v.trailTop - Math.max(1, (v.trailTop - hpFill + 3) / 4));
        v.trailTop = Math.min(v.trailTop, hpLen);
        v.hpFill = hpFill;
        int trail = v.trailTop - hpFill;

        Pool mana = st.mana;
        int fpLen = -1, fpFill = 0;
        if (mana != null) {
            fpLen = length(mana.max() * c.warmthPx(), c);
            fpFill = fill(mana.cur(), mana.max(), fpLen);
        } else if (c.warmthPlaceholder() > 0) {
            fpLen = length(c.warmthPlaceholder() * c.warmthPx(), c);
            fpFill = fpLen;
        }
        int stLen = length(st.stamina.max() * c.staminaPx(), c);
        int stFill = fill(st.stamina.cur(), st.stamina.max(), stLen);

        int[] vals = {hpFill, hpLen, trail, fpFill, fpLen, stFill, stLen};
        String key = java.util.Arrays.toString(vals);
        if (key.equals(v.barKey) && now - v.barAt < c.barRefresh()) return;
        System.arraycopy(vals, 0, v.last, 0, vals.length);
        Line l = new Line();
        l.move(-lay.left());
        int x0 = l.pen;
        bar(l, x0, "hp", hpLen, hpFill, trail);
        if (fpLen > 0) bar(l, x0, "fp", fpLen, fpFill, 0);
        bar(l, x0, "st", stLen, stFill, 0);
        l.move(-l.pen);
        v.bar.name(l.component(lay.markLeft()));
        v.barKey = key;
        v.barAt = now;
    }

    /** 막대 한 줄: [왼쪽 마구리][채움][잃은 몫][빈 몫][오른쪽 마구리] 를 그리고 x0 으로 돌아온다 (다음 막대는 아래 줄 그림). */
    private static void bar(Line l, int x0, String name, int len, int fill, int trail) {
        l.glyph("hud_" + name + "_cap_l");
        l.runs("hud_" + name + "_fill_", fill);
        l.runs("hud_" + name + "_trail_", trail);
        l.runs("hud_" + name + "_empty_", len - fill - trail);
        l.glyph("hud_" + name + "_cap_r");
        l.move(x0 - l.pen);
    }

    private static int length(double px, Config.HudCfg c) {
        return (int) Math.max(c.minPx(), Math.min(c.maxPx(), Math.round(px)));
    }

    /** 채움 픽셀: 0 이면 0, 조금이라도 있으면 1 이상, 가득이 아니면 길이보다 1 짧게까지. */
    private static int fill(double cur, double max, int len) {
        if (cur <= 0 || max <= 0) return 0;
        if (cur >= max) return len;
        return (int) Math.max(1, Math.min(len - 1, Math.round(len * cur / max)));
    }

    // ------------------------------------------------------------------ 보스 막대

    private void boss(Player p, Boss b, long now) {
        Glyphs.Layout lay = Glyphs.layout();
        boolean glyph = glyphs(p) && Glyphs.get("boss_hp_fill_1") != null && Glyphs.get("boss_cap_l") != null;
        int w = lay == null ? 200 : lay.bossWidth();
        int fill = fill(b.hp, b.hpMax, w);
        if (b.fill >= 0 && fill < b.fill) {
            b.trailTop = Math.max(b.trailTop, b.fill);
            b.trailHold = now + TRAIL_HOLD;
        }
        if (b.trailTop <= fill) b.trailTop = fill;
        else if (now >= b.trailHold) b.trailTop = Math.max(fill, b.trailTop - Math.max(1, (b.trailTop - fill + 3) / 4));
        b.trailTop = Math.min(b.trailTop, w);
        b.fill = fill;
        int trail = b.trailTop - fill;
        int post = fill(b.post, b.postMax, w);
        String key = (glyph ? "g" : "t") + fill + "/" + trail + "/" + post + "@" + Lang.langOf(p);
        if (key.equals(b.key) && now - b.at < plugin.cfg().hud.barRefresh()) return;
        b.key = key;
        b.at = now;
        Component name = Lang.c(p, b.nameKey); // lang-dyn: boss.*.name
        if (!glyph) {
            // 팩이 없으면 바닐라 보스 막대 (이름과 진행)
            b.bar.name(name);
            b.bar.progress((float) Math.max(0, Math.min(1, b.hp / b.hpMax)));
            return;
        }
        b.bar.progress(0f);
        b.bar.name(bossLine(lay, name, w, fill, trail, post));
    }

    /**
     * 보스 막대 이름 줄: [이름 사본 (지운다)][왼쪽 마구리][체력][오른쪽 마구리][자세][이름][빈칸]. 진행 폭 = 이름 폭 × 2 라 바닐라는
     * 가운데 - 이름 폭 에서 시작하고, 사본 뒤 = 가운데 에서 막대를 그린다: 왼쪽 마구리 (넓은 단조 장식이라 그 폭만큼 앞으로 당겨
     * 체력 막대가 늘 가운데 - w/2 에서 시작한다), 체력 (채움·잃은 몫·빈 몫), 오른쪽 마구리, 그 밑 줄 자세 (채움·빈 몫), 그리고
     * 가운데 - w/2 에서 이름, 마지막에 w/2 오른쪽으로. 마구리는 표식 색 markBossCap 이라 셰이더가 늘이지 않고 늘인 막대 끝을 따라
     * 통째로 옮긴다. 짜는 차례는 pack/hud.py boss_line 과 같다.
     */
    private static Component bossLine(Glyphs.Layout lay, Component name, int w, int fill, int trail, int post) {
        int half = w / 2;
        Glyphs.Glyph capL = Glyphs.get("boss_cap_l");
        int capW = capL == null ? 2 : capL.width() - 1;
        Line c1 = new Line();
        c1.move(-half - capW);
        c1.glyph("boss_cap_l");
        int pen = c1.pen;
        Line b1 = new Line();
        b1.runs("boss_hp_fill_", fill);
        b1.runs("boss_hp_trail_", trail);
        b1.runs("boss_hp_empty_", w - fill - trail);
        pen += b1.pen;
        Line c2 = new Line();
        c2.glyph("boss_cap_r");
        pen += c2.pen;
        Line b2 = new Line();
        b2.move(-half - pen);
        b2.runs("boss_post_fill_", post);
        b2.runs("boss_post_empty_", w - post);
        b2.move(-half - (pen + b2.pen));
        Line tail = new Line();
        tail.move(half);
        ShadowColor shadow = ShadowColor.shadowColor(0xFF000000 | lay.markBossShadow().value());
        return Component.text()
                .append(name.color(lay.markHidden()).shadowColor(ShadowColor.none()))
                .append(c1.component(lay.markBossCap()))
                .append(b1.component(lay.markBoss()))
                .append(c2.component(lay.markBossCap()))
                .append(b2.component(lay.markBoss()))
                .append(name.color(lay.markBossName()).shadowColor(shadow))
                .append(tail.component(lay.markBoss()))
                .build();
    }

    // ------------------------------------------------------------------ 소울 상자

    private void souls(Player p, View v, long now) {
        Config.HudCfg c = plugin.cfg().hud;
        Glyphs.Layout lay = Glyphs.layout();
        boolean glyph = glyphs(p) && Glyphs.get("hud_soulbox") != null && Glyphs.get("hud_digit_0") != null;
        long n = Math.max(0, souls.applyAsLong(p));
        Pool mana = CombatState.of(p).mana;
        if (!c.showSouls() && (glyph || mana == null)) return;
        // 언어도 넣는다: 글 판의 대체 글이 그 사람의 언어라 (10.9) 클라이언트 언어를 바꾸면 다시 만든다
        String key = glyph ? "g" + n : "t" + n + (mana == null ? "" : "/" + Math.round(mana.cur()) + "/" + Math.round(mana.max()))
                + "@" + Lang.langOf(p);
        boolean changed = !key.equals(v.soulsKey) || v.souls == null;
        if (changed) {
            v.souls = glyph ? soulBox(lay, n) : soulText(p, n, mana, c.showSouls());
            v.soulsKey = key;
        }
        if (v.souls != null && (changed || now - v.soulsAt >= c.actionbarRefresh())) {
            p.sendActionBar(v.souls);
            v.soulsAt = now;
        }
    }

    /** 상자 오른쪽 끝이 가운데 + layout.right. 소울 표식은 상자 왼쪽 안 (5), 숫자 (고정폭) 는 오른쪽 안 (6) 에 붙인다. */
    private static Component soulBox(Glyphs.Layout lay, long n) {
        String digits = Long.toString(n);
        int dw = Glyphs.get("hud_digit_0").width() - 1;
        Line l = new Line();
        int box = lay.soulBox();
        l.move(lay.right() - box);
        int x0 = l.pen;
        l.glyph("hud_soulbox");
        l.move(x0 + 5 - l.pen);
        l.glyph("soul_mark");
        l.move(x0 + box - 6 - dw * digits.length() - l.pen);
        for (int i = 0; i < digits.length(); i++) l.glyph("hud_digit_" + digits.charAt(i));
        l.move(-l.pen);
        return l.component(lay.markRight());
    }

    /** 그림 글자가 없을 때 (옛 팩): 행동 막대 글 "마나 n/m   소울 N" (10.3 의 hud.warmth, hud.souls). */
    private static Component soulText(Player p, long n, Pool mana, boolean showSouls) {
        Component out = Component.empty();
        boolean any = false;
        if (mana != null) {
            out = out.append(Lang.c(p, "hud.warmth", "n", String.valueOf(Math.round(mana.cur())), "m", String.valueOf(Math.round(mana.max()))));
            any = true;
        }
        if (showSouls) {
            if (any) out = out.append(Component.text("   "));
            out = out.append(Lang.c(p, "hud.souls", "n", NumberFormat.getIntegerInstance(Locale.US).format(n)));
            any = true;
        }
        return any ? out : null;
    }

    /**
     * 그림 글자 한 줄을 짠다. pen 은 글 시작에서 지금 자리까지의 진행 폭 (글꼴 픽셀). 그림 글자는 폭 + 1 만큼 나아가므로
     * glyph 는 1 을 되돌린다. 잇단 move 는 모았다가 빈칸 글자 (±1, 2, 4 … 128) 로 한 번에 쓴다.
     */
    private static final class Line {
        final StringBuilder sb = new StringBuilder();
        int pen;
        int pending;

        void move(int d) {
            pen += d;
            pending += d;
        }

        void glyph(String name) {
            Glyphs.Glyph g = Glyphs.get(name);
            if (g == null) return;
            flush();
            sb.append(g.ch());
            pen += g.width();
            move(-1);
        }

        /** 길이 n 을 128, 64 … 1 조각으로 */
        void runs(String prefix, int n) {
            for (int step : RUNS) {
                while (n >= step) {
                    glyph(prefix + step);
                    n -= step;
                }
            }
        }

        void flush() {
            int d = pending;
            pending = 0;
            String sign = d < 0 ? "space_neg" : "space_pos";
            int left = Math.abs(d);
            while (left > 0) {
                int step = 128;
                while (step > left) step >>= 1;
                Glyphs.Glyph g = Glyphs.get(sign + step);
                if (g == null) return;
                sb.append(g.ch());
                left -= step;
            }
        }

        Component component(net.kyori.adventure.text.format.TextColor mark) {
            flush();
            return Component.text(sb.toString()).font(HUD_FONT).color(mark).shadowColor(ShadowColor.none());
        }
    }

    // ------------------------------------------------------------------ 시험 줄

    /** /soulstest hud: 지금 보낸 막대 값 (픽셀) 과 소울 수. 봇이 읽는다 (13.2). */
    public String testLine(Player p) {
        View v = view(p);
        int[] a = v.last;
        StringBuilder bosses = new StringBuilder();
        for (Map.Entry<String, Boss> e : v.bosses.entrySet()) {
            Boss b = e.getValue();
            if (!bosses.isEmpty()) bosses.append(',');
            bosses.append(e.getKey()).append(':').append(Math.max(0, b.fill)).append('+').append(b.trailTop - Math.max(0, b.fill));
        }
        return String.format(Locale.ROOT, "HUD mode=%s bossbar=%s hp=%d/%d trail=%d fp=%d/%d st=%d/%d souls=%d blank=%s bosses=%s",
                glyphs(p) ? "glyph" : "text", v.bar != null, a[0], a[1], a[2], a[3], a[4], a[5], a[6],
                Math.max(0, souls.applyAsLong(p)), v.blank, bosses.isEmpty() ? "-" : bosses);
    }

    // ------------------------------------------------------------------ 사건

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        p.setLevel(0);
        p.setExp(0);
        p.setTotalExperience(0);
        // 설정 단계에서 팩을 보낸 판 (pack.send-at: configure) 은 세계에 들어오기 전에 이미 실었다
        if ("configure".equals(plugin.cfg().pack.sendAt())) packed.add(p.getUniqueId());
        invalidate(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPack(PlayerResourcePackStatusEvent e) {
        if (e.getStatus() != PlayerResourcePackStatusEvent.Status.SUCCESSFULLY_LOADED) return;
        packed.add(e.getPlayer().getUniqueId());
        invalidate(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        View v = views.remove(e.getPlayer().getUniqueId());
        packed.remove(e.getPlayer().getUniqueId());
        if (v != null && v.bar != null) e.getPlayer().hideBossBar(v.bar);
        if (v != null) for (Boss b : v.bosses.values()) e.getPlayer().hideBossBar(b.bar);
    }

    /**
     * 부활·세계 이동 뒤에는 막대와 소울 상자를 다시 보낸다. 보스 막대는 거뒀다 다시 띄우지 않는다: 클라이언트는 부활·세계 이동에도
     * 보스 막대를 그대로 두고 [확인 (클라)], Paper 는 거둔 막대를 다시 띄울 때 새 보스 막대 (새 UUID) 를 만들어 그때 떠 있는
     * 진짜 보스 막대 밑으로 내려 보낸다.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerPostRespawnEvent e) {
        invalidate(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorld(PlayerChangedWorldEvent e) {
        invalidate(e.getPlayer());
    }

    /** 진짜 경험치는 쌓이지 않는다 (레벨 숫자가 서지 않게. 경험치 막대 그림은 팩이 숨긴다). */
    @EventHandler(priority = EventPriority.HIGH)
    public void onExp(PlayerExpChangeEvent e) {
        e.setAmount(0);
    }
}
