package kr.labyrinth.homes.rules;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.function.Predicate;
import kr.labyrinth.homes.PlotGeom;

/**
 * 받기·비우기·초대·이름 규칙 (0.3.7, plan §6 · review R13·R18) — 순수. 소유: 묶음 B.
 * <ul>
 *   <li>한 사람 한 집 (convert 집도 1채로 셈).</li>
 *   <li>스스로 비운 뒤 다시 받기는 {@code homes.reclaim_cooldown_minutes} (기본 1440 = 24시간, R13). 관리자 회수는 세지 않음.</li>
 *   <li>"아무 데나" = 빈 구역 집터 (convert 집터 제외) 중 하나.</li>
 *   <li>이름 16자, 꺾쇠·줄바꿈 뺌 (보일 때 Text.escape).</li>
 * </ul>
 */
public final class ClaimRules {

    private ClaimRules() {}

    public static final int NAME_MAX = 16;

    /** 다시 받기까지 남은 ms (0 = 됨). */
    public static long cooldownLeft(long vacatedAt, long now, int cooldownMinutes) {
        if (vacatedAt <= 0 || cooldownMinutes <= 0) return 0;
        long end = vacatedAt + cooldownMinutes * 60_000L;
        return Math.max(0, end - now);
    }

    /** 120000 → "2분" · 5400000 → "1시간 30분". 1분 아래는 "1분". */
    public static String duration(long ms) {
        long min = Math.max(1, (ms + 59_999) / 60_000);
        long h = min / 60, m = min % 60;
        if (h == 0) return m + "분";
        return m == 0 ? h + "시간" : h + "시간 " + m + "분";
    }

    /**
     * 받기 검사.
     *
     * @param plot      고른 집터 (null = 아무 데나 — 빈 집이 없으면 그 글)
     * @param plotOwned 고른 집터에 주인이 있나
     * @param plotBusy  고른 집터를 비우는 중인가
     * @return null = 됨, 아니면 글
     */
    public static String checkClaim(boolean active, boolean inDungeon, boolean hasHome, long cooldownLeftMs, PlotGeom plot, boolean plotOwned,
                                    boolean plotBusy) {
        if (!active) return "아직 집 구역이 없습니다.";
        if (inDungeon) return "미궁 안에서는 집을 받을 수 없습니다.";
        if (hasHome) return "이미 집이 있습니다. 한 사람에 한 집입니다.";
        if (cooldownLeftMs > 0) return "집을 비운 뒤 " + duration(cooldownLeftMs) + " 지나야 다시 받을 수 있습니다.";
        if (plot == null) return "빈 집이 없습니다.";
        if (plot.custom()) return "관리자가 정한 집터는 관리자만 줄 수 있습니다.";
        if (plotOwned) return topic(plot) + " 주인이 있습니다.";
        if (plotBusy) return object(plot) + " 정리하는 중입니다. 잠시 뒤에 다시 하세요.";
        return null;
    }

    /** 빈 구역 집터 하나 (convert 집터 제외, 없으면 null). */
    public static PlotGeom pickAny(List<PlotGeom> plots, Predicate<PlotGeom> free, Random rnd) {
        List<PlotGeom> c = new ArrayList<>();
        for (PlotGeom p : plots) if (!p.custom() && free.test(p)) c.add(p);
        if (c.isEmpty()) return null;
        return c.get(rnd == null ? 0 : rnd.nextInt(c.size()));
    }

    /** 이름 다듬기: 앞뒤 공백 · 꺾쇠·제어 문자 뺌 · 16자 (코드 포인트). 빈 글 = "" (기본 이름으로). */
    public static String cleanName(String raw) {
        if (raw == null) return "";
        StringBuilder sb = new StringBuilder();
        raw.strip().codePoints().forEach(cp -> {
            if (cp == '<' || cp == '>' || cp == '\\' || cp == '§') return;
            sb.appendCodePoint(Character.isISOControl(cp) ? ' ' : cp); // 줄바꿈·탭은 띄어쓰기로
        });
        String s = sb.toString().strip().replaceAll("\\s+", " ");
        if (s.codePointCount(0, s.length()) > NAME_MAX) s = s.substring(0, s.offsetByCodePoints(0, NAME_MAX)).strip();
        return s;
    }

    /** 보일 이름: 정한 이름이 없으면 "<주인>의 집". */
    public static String displayName(String name, String ownerName) {
        if (name != null && !name.isBlank()) return name;
        return ownerName == null || ownerName.isBlank() ? "" : ownerName + "의 집";
    }

    /** 이름 바꾸기까지 남은 ms. */
    public static long renameLeft(long renamedAt, long now, int cooldownMinutes) { return cooldownLeft(renamedAt, now, cooldownMinutes); }

    /** "3번지는" · "c1 집터는". */
    public static String topic(PlotGeom p) { return p.custom() ? p.id() + " 집터는" : p.label() + "는"; }

    /** "3번지를" · "c1 집터를". */
    public static String object(PlotGeom p) { return p.custom() ? p.id() + " 집터를" : p.label() + "를"; }

    /** 초대 검사 (null = 됨). */
    public static String checkInvite(boolean self, boolean already, int trustedCount, int max) {
        if (self) return "자기 자신은 초대할 수 없습니다.";
        if (already) return "이미 초대한 사람입니다.";
        if (trustedCount >= max) return "초대는 " + max + "명까지입니다.";
        return null;
    }
}
