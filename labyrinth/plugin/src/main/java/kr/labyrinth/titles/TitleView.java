package kr.labyrinth.titles;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.Text;

/**
 * 플레이어가 보는 칭호 문구 (순수 함수 — 메뉴·채팅 목록·방송·주인 알림이 모두 여기서 만든다, 단위 테스트 대상).
 * <p>
 * <b>비밀 규칙</b>: 주인이 없는 칭호의 조건은 어디에도 쓰지 않는다 — 언제나 "조건: ???". 주인이 생기면 그때부터 모두에게
 * 조건을 보여 준다({@link AchievementRules#conditionText}). 칭호 설명(titles.yml {@code lore})은 조건을 암시하지 않는 짧은 글.
 */
public final class TitleView {

    /** 칭호의 주인 (records.yml {@code title.<id>}). */
    public record Owner(String name, long time) {}

    public static final String HIDDEN = "<dark_gray>조건: <gray>???";
    public static final String NO_OWNER = "<dark_gray>아직 주인이 없습니다";

    private TitleView() {}

    /** records.yml 키 — 칭호 한 개에 주인 한 명. */
    public static String recordKey(String achievementId) { return "title." + achievementId; }

    /** 주인이 있을 때만 조건 줄, 없으면 ???. */
    public static String conditionLine(AchievementDef a, Owner owner, Content content) {
        if (owner == null) return HIDDEN;
        String cond = AchievementRules.conditionText(a, content);
        return cond.isEmpty() ? HIDDEN : "<gray>조건: <white>" + Text.escape(cond);
    }

    public static String ownerLine(Owner owner) {
        if (owner == null) return NO_OWNER;
        return "<gray>주인: <#ffd36b>" + Text.escape(owner.name()) + "</#ffd36b> <dark_gray>· " + date(owner.time());
    }

    /** /칭호 메뉴 아이콘 설명. mine = 보는 사람이 주인, equipped = 지금 달고 있음. */
    public static List<String> lore(AchievementDef a, Owner owner, boolean mine, boolean equipped, Content content) {
        List<String> lore = new ArrayList<>();
        if (a.description() != null && !a.description().isBlank()) lore.add("<gray><i>" + Text.escape(a.description()));
        lore.add("");
        if (!a.bonus().isEmpty()) lore.add("<#7fe07f>장착 효과: " + bonusText(a.bonus()));
        lore.add(conditionLine(a, owner, content));
        lore.add(ownerLine(owner));
        lore.add("");
        if (mine) lore.add(equipped ? "<#ffd36b>▶ 장착 중 <gray>(클릭: 해제)" : "<#ffd36b>클릭: 장착");
        else if (owner == null) lore.add("<dark_gray>조건을 가장 먼저 채운 단 한 사람의 것이 됩니다.");
        else lore.add("<dark_gray>이미 주인이 있는 칭호입니다.");
        return lore;
    }

    /** /칭호 목록 (채팅) 한 줄. */
    public static String listLine(AchievementDef a, Owner owner, boolean mine, Content content) {
        String head = (mine ? "<#ffd36b>★ </#ffd36b>" : "<dark_gray>· </dark_gray>") + a.title();
        String who = owner == null ? " <dark_gray>— 주인 없음 · 조건 ???" : " <gray>— 주인 <white>" + Text.escape(owner.name())
                + "</white> <dark_gray>· " + Text.escape(AchievementRules.conditionText(a, content));
        return " " + head + who;
    }

    /** 주인이 생겼을 때 서버 전체 방송 (조건 공개). */
    public static String broadcast(AchievementDef a, String ownerName, Content content) {
        String cond = AchievementRules.conditionText(a, content);
        return "<gradient:#ffd36b:#ff8a3d><b>[칭호]</b></gradient> <white>" + Text.escape(ownerName) + "</white> <gray>님이 칭호 「</gray>"
                + a.title() + "<gray>」의 주인이 되었습니다</gray>" + (cond.isEmpty() ? "" : " <dark_gray>— 조건: " + Text.escape(cond));
    }

    /** 주인에게 보내는 알림 (보상 문구 포함, rewardText 는 이미 MiniMessage). */
    public static String ownerMessage(AchievementDef a, Content content, String rewardText) {
        String cond = AchievementRules.conditionText(a, content);
        return "<#ffd36b>칭호의 주인이 되었습니다!</#ffd36b> 「" + a.title() + "」" + (cond.isEmpty() ? "" : " <dark_gray>— " + Text.escape(cond))
                + (rewardText == null || rewardText.isBlank() ? "" : rewardText);
    }

    /** 장착 효과 문구 (스탯 +n · 경험치 +n% · 골드 +n%). */
    public static String bonusText(Map<String, Double> bonus) {
        List<String> parts = new ArrayList<>();
        bonus.forEach((k, v) -> {
            kr.labyrinth.stats.Stat st = kr.labyrinth.stats.Stat.byKey(k);
            if (st != null) parts.add(st.displayName() + " +" + Math.round(v));
            else if ("xp_bonus".equals(k)) parts.add("경험치 +" + Text.pct(v));
            else if ("gold_bonus".equals(k)) parts.add("골드 +" + Text.pct(v));
            else parts.add(k + " +" + v);
        });
        return String.join(" · ", parts);
    }

    /** 메뉴 맨 위 안내 (칭호 수·주인 있는 수·내 칭호 수). */
    public static List<String> summary(int total, int owned, int mine) {
        return List.of("<gray>칭호 <white>" + total + "</white>개 · 주인 있음 <white>" + owned + "</white> · 내 칭호 <#ffd36b>" + mine,
                "",
                "<gray>칭호마다 서버에서 <white>단 한 명</white>만 가질 수 있습니다.",
                "<gray>조건은 주인이 생기기 전까지 <white>비밀</white>입니다.",
                "<gray>주인이 생기면 조건이 모두에게 공개됩니다.");
    }

    static String date(long time) { return new SimpleDateFormat("yyyy-MM-dd").format(new Date(time)); }
}
