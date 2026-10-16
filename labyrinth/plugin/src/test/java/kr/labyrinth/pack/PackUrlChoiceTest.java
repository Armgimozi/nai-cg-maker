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
        PackUrlChoice.Plan noSha = PackUrlChoice.decide(url, "", "", TPL, JAR);
        assertEquals(JAR, noSha.sha1(), "sha1 이 비면 jar 팩 것");
        // 이름만 비슷한 주소 (pack-host 아님) 도 직접 적은 주소
        assertEquals(PackUrlChoice.Mode.CUSTOM_URL, PackUrlChoice.decide("https://x/labyrinth-pack-065e6258.zip", "", "", TPL, JAR).mode());
        // jar 팩을 모르면 (팩 없음) 바꾸지 않는다
        assertEquals(OWNER_URL, PackUrlChoice.decide(OWNER_URL, OLD, "", TPL, "").url());
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
