package kr.labyrinth.pack;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 리소스팩 주소 자동 (주인이 "팩 1개 중 1개가 다운로드에 실패했습니다" 를 두 번 겪음):
 * (a) 내장 먼저 + 받지 못하면 공개 사본 · (b) 옛 사본 pack.url → jar 팩 사본 · (c) 직접 적은 주소는 그대로.
 */
class PackUrlChoiceTest {

    static final String JAR = "c4f8c56eddeabd49100f9f6c51681d777d98ce36";
    static final String OLD = "065e6258aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    static final String TPL = PackUrlChoice.DEFAULT_PUBLIC_COPY;
    static final String OWNER_URL = "https://raw.githubusercontent.com/Armgimozi/nai-cg-maker/claude/bold-darwin-nwa5vk/labyrinth/pack-host/labyrinth-pack-065e6258.zip";

    @Test
    void builtinFirstThenPublicCopy() {
        PackUrlChoice.Plan p = PackUrlChoice.decide("", "", "", TPL, JAR);
        assertEquals(PackUrlChoice.Mode.BUILTIN, p.mode());
        assertNull(p.url(), "내장 주소는 플레이어마다");
        assertEquals(JAR, p.sha1());
        assertEquals("https://raw.githubusercontent.com/Armgimozi/nai-cg-maker/claude/bold-darwin-nwa5vk/labyrinth/pack-host/labyrinth-pack-c4f8c56e.zip",
                p.fallbackUrl());
        assertTrue(p.verify(), "시작 때 사본을 받아 보고 맞을 때만 다시 보냄");
        assertEquals(p.fallbackUrl(), p.checkUrl());
        assertNull(p.notice());
    }

    @Test
    void publicHostServersKeepTheirTunnelOnly() {
        PackUrlChoice.Plan p = PackUrlChoice.decide("", "", "abc.playit.gg", TPL, JAR);
        assertEquals(PackUrlChoice.Mode.BUILTIN, p.mode());
        assertNull(p.fallbackUrl(), "public_host 를 쓰면 (a) 다시 보내기 없음");
        assertFalse(p.verify());
    }

    @Test
    void emptyTemplateDisablesFallback() {
        PackUrlChoice.Plan p = PackUrlChoice.decide("", "", "", "", JAR);
        assertNull(p.fallbackUrl());
        assertFalse(p.verify());
        assertNull(PackUrlChoice.decide("  ", null, null, "   ", JAR).fallbackUrl());
    }

    @Test
    void staleHostedCopyIsReplacedByTheJarsCopy() {
        // 주인 config: pack.url = 0.3.6 사본 (065e6258), sha1 = 그때 값
        PackUrlChoice.Plan p = PackUrlChoice.decide(OWNER_URL, OLD, "", TPL, JAR);
        assertEquals(PackUrlChoice.Mode.PUBLIC_COPY, p.mode());
        assertEquals(PackUrlChoice.publicCopyUrl(TPL, JAR), p.url());
        assertEquals(JAR, p.sha1(), "옛 sha1 이 아니라 jar 팩 sha1");
        assertTrue(p.verify(), "그 사본을 받을 수 없으면 내장으로 돌아가게 확인");
        assertNotNull(p.notice());
        assertTrue(p.notice().contains("065e6258") && p.notice().contains("c4f8c56e"), p.notice());
        assertFalse(p.notice().matches(".*[A-Za-z]{12,}.*"), "한국어 한 줄: " + p.notice());
    }

    @Test
    void staleCopyWithoutTemplateKeepsTheOwnersHost() {
        String url = "https://example.org/x/pack-host/labyrinth-pack-065e6258.zip?v=1";
        PackUrlChoice.Plan p = PackUrlChoice.decide(url, OLD, "", "", JAR);
        assertEquals("https://example.org/x/pack-host/labyrinth-pack-c4f8c56e.zip", p.url());
        assertEquals(JAR, p.sha1());
    }

    @Test
    void matchingHostedCopyIsUsedAsIs() {
        String url = PackUrlChoice.publicCopyUrl(TPL, JAR);
        PackUrlChoice.Plan p = PackUrlChoice.decide(url, "", "", TPL, JAR);
        assertEquals(PackUrlChoice.Mode.PUBLIC_COPY, p.mode());
        assertEquals(url, p.url());
        assertFalse(p.verify());
        assertNull(p.notice());
        PackUrlChoice.Plan wrongSha = PackUrlChoice.decide(url, OLD, "", TPL, JAR);
        assertEquals(JAR, wrongSha.sha1(), "주소가 jar 팩 사본이면 sha1 도 jar 팩 것");
        assertNotNull(wrongSha.notice());
    }

    @Test
    void customUrlIsAlwaysRespected() {
        String url = "https://cdn.example.com/my-pack.zip";
        PackUrlChoice.Plan p = PackUrlChoice.decide(url, "deadbeef", "", TPL, JAR);
        assertEquals(PackUrlChoice.Mode.CUSTOM_URL, p.mode());
        assertEquals(url, p.url());
        assertEquals("deadbeef", p.sha1(), "주인이 적은 sha1 그대로");
        assertFalse(p.verify());
        assertNull(p.fallbackUrl());
        // 시각 검토 5: 적힌 sha1 이 jar 팩과 다르면 (옛 팩일 수 있음) 한 줄 남기되 주소·sha1 은 그대로
        assertNotNull(p.notice(), "옛 팩일 수 있다는 한 줄");
        assertTrue(p.notice().contains("deadbeef") && p.notice().contains(JAR.substring(0, 8)), p.notice());
        PackUrlChoice.Plan same = PackUrlChoice.decide(url, JAR.toUpperCase(), "", TPL, JAR);
        assertNull(same.notice(), "jar 팩과 같은 sha1 이면 조용히");
        PackUrlChoice.Plan noSha = PackUrlChoice.decide(url, "", "", TPL, JAR);
        assertEquals(JAR, noSha.sha1(), "sha1 이 비면 jar 팩 것");
        assertNull(noSha.notice());
        // 이름만 비슷한 주소 (pack-host 아님) 도 직접 적은 주소
        assertEquals(PackUrlChoice.Mode.CUSTOM_URL, PackUrlChoice.decide("https://x/labyrinth-pack-065e6258.zip", "", "", TPL, JAR).mode());
        // jar 팩을 모르면 (팩 없음) 바꾸지 않는다
        assertEquals(OWNER_URL, PackUrlChoice.decide(OWNER_URL, OLD, "", TPL, "").url());
    }

    @Test
    void ownersOldCopyIsTheFallbackWhenTheNewCopyIsMissing() {
        // 이 jar 팩 사본이 아직 GitHub 에 없음 (404) → 0.3.6 에서 잘 받던 config 의 065e6258 사본 (터널 친구는 내장 서버로 못 받음)
        String ownerSha = "065e62586c00f77c43b40384029ac443b19c8645";
        PackUrlChoice.Plan p = PackUrlChoice.decide(OWNER_URL, ownerSha, "", TPL, JAR);
        PackUrlChoice.Fallback fb = PackUrlChoice.staleFallback(p, " " + OWNER_URL + " ", ownerSha.toUpperCase());
        assertNotNull(fb);
        assertEquals(OWNER_URL, fb.url());
        assertEquals(ownerSha, fb.sha1(), "주인이 적은 sha1 (소문자)");
        assertEquals("065e6258", fb.sha8());
        // (b) 가 아니면 없음: 비운 pack.url · 직접 올린 주소 · 이미 jar 팩 사본
        assertNull(PackUrlChoice.staleFallback(PackUrlChoice.decide("", "", "", TPL, JAR), "", ""));
        String custom = "https://cdn.example.com/my-pack.zip";
        assertNull(PackUrlChoice.staleFallback(PackUrlChoice.decide(custom, "deadbeef", "", TPL, JAR), custom, "deadbeef"));
        String same = PackUrlChoice.publicCopyUrl(TPL, JAR);
        assertNull(PackUrlChoice.staleFallback(PackUrlChoice.decide(same, "", "", TPL, JAR), same, ""));
        // 주소의 sha8 과 sha1 이 다른 팩이면 믿지 않음
        assertNull(PackUrlChoice.staleFallback(p, OWNER_URL, JAR));
        assertNull(PackUrlChoice.staleFallback(null, OWNER_URL, ownerSha));
    }

    @Test
    void oldCopyIsSentOnlyWhenItsShaMatches() {
        byte[] body = "old pack".getBytes(StandardCharsets.UTF_8);
        String sha = PackUrlChoice.sha1Hex(body);
        String url = "https://h/pack-host/labyrinth-pack-" + sha.substring(0, 8) + ".zip";
        PackUrlChoice.Plan p = PackUrlChoice.decide(url, sha, "", TPL, JAR);
        PackUrlChoice.Fallback fb = PackUrlChoice.staleFallback(p, url, sha);
        assertEquals(sha, PackUrlChoice.acceptFallback(body, fb));
        assertNull(PackUrlChoice.acceptFallback("other".getBytes(StandardCharsets.UTF_8), fb), "sha1 다름 → 내장 서버");
        assertNull(PackUrlChoice.acceptFallback(new byte[0], fb));
        // config sha1 이 비면 주소의 sha8 로만 맞춰 보고, 받은 파일의 sha1 을 알린다
        PackUrlChoice.Fallback noSha = PackUrlChoice.staleFallback(PackUrlChoice.decide(url, "", "", TPL, JAR), url, "");
        assertEquals("", noSha.sha1());
        assertEquals(sha, PackUrlChoice.acceptFallback(body, noSha));
        assertNull(PackUrlChoice.acceptFallback("other".getBytes(StandardCharsets.UTF_8), noSha));
    }

    @Test
    void retryGoesToTheOtherAddressOnce() {
        // (a) 내장 주소를 못 받음 → 확인된 사본 · 사본 확인 실패면 다시 보내지 않음
        assertEquals(PackUrlChoice.Retry.COPY, PackUrlChoice.retry(PackUrlChoice.Mode.BUILTIN, true, false, true, true));
        assertEquals(PackUrlChoice.Retry.NONE, PackUrlChoice.retry(PackUrlChoice.Mode.BUILTIN, true, false, false, true));
        // 사본을 못 받음 → 내장 주소 (열려 있으면) — (b) 사본으로 보낸 뒤 GitHub 를 못 쓰는 손님
        assertEquals(PackUrlChoice.Retry.BUILTIN, PackUrlChoice.retry(PackUrlChoice.Mode.PUBLIC_COPY, false, true, true, true));
        assertEquals(PackUrlChoice.Retry.NONE, PackUrlChoice.retry(PackUrlChoice.Mode.PUBLIC_COPY, false, true, true, false));
        // (b) 확인 전 내장 주소를 받은 사람이 못 받음 → 확인된 사본
        assertEquals(PackUrlChoice.Retry.COPY, PackUrlChoice.retry(PackUrlChoice.Mode.PUBLIC_COPY, true, false, true, true));
        // (c) 직접 적은 주소는 다시 보내지 않음 · 모르는 팩 id 도
        assertEquals(PackUrlChoice.Retry.NONE, PackUrlChoice.retry(PackUrlChoice.Mode.CUSTOM_URL, false, false, true, true));
        assertEquals(PackUrlChoice.Retry.NONE, PackUrlChoice.retry(PackUrlChoice.Mode.BUILTIN, false, false, true, true));
    }

    @Test
    void hostedShaAndVerify() {
        assertEquals("065e6258", PackUrlChoice.hostedSha8(OWNER_URL));
        assertEquals("065e6258", PackUrlChoice.hostedSha8("https://h/pack-host/labyrinth-pack-065E6258.zip?v=2"), "대문자·물음표 뒤 무시");
        assertNull(PackUrlChoice.hostedSha8("https://x/y.zip"));
        assertNull(PackUrlChoice.publicCopyUrl(TPL, "abc"), "sha1 이 짧으면 주소 없음");
        assertEquals("https://h/" + JAR + ".zip", PackUrlChoice.publicCopyUrl("https://h/{sha1}.zip", JAR));
        byte[] body = "pack".getBytes(StandardCharsets.UTF_8);
        String sha = PackUrlChoice.sha1Hex(body);
        assertTrue(PackUrlChoice.matches(body, sha.toUpperCase()));
        assertFalse(PackUrlChoice.matches(body, JAR));
        assertFalse(PackUrlChoice.matches(new byte[0], sha));
    }

    @Test
    void configDefaultMatchesCode() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new java.io.File("src/main/resources/config.yml"));
        assertEquals(PackUrlChoice.DEFAULT_PUBLIC_COPY, y.getString("pack.public_copy"));
        assertEquals("", y.getString("pack.url"));
        assertTrue(PackUrlChoice.DEFAULT_PUBLIC_COPY.contains("{sha8}"));
        assertNotNull(PackUrlChoice.hostedSha8(PackUrlChoice.publicCopyUrl(PackUrlChoice.DEFAULT_PUBLIC_COPY, JAR)),
                "기본 사본 주소는 (b) 의 꼴과 같다 — 사본을 pack.url 에 적어도 다음 판에 바로잡힘");
    }
}
