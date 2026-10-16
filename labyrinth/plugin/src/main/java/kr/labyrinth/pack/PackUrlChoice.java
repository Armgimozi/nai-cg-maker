package kr.labyrinth.pack;

import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 리소스팩 주소 고르기 (0.3.6.1 — 주인이 "팩 1개 중 1개가 다운로드에 실패했습니다" 를 두 번 겪음: 팩이 바뀔 때마다 pack.url·sha1 을
 * 손으로 고쳐야 했다). jar 는 제 팩의 SHA-1 을 안다. 순수 (Bukkit 없음) — {@link PackService} 가 이대로 쓴다.
 * <ol>
 *   <li>(a) pack.url 이 비고 pack.public_host 도 비면: 지금처럼 내장 주소(게임 포트 · 접속한 주소)를 먼저 보낸다. 클라이언트가 그 주소를
 *       받지 못하면(FAILED_DOWNLOAD · INVALID_URL) 이 jar 팩의 공개 사본({@code pack.public_copy}, 시작 때 받아 보고 SHA-1 이 맞을 때만)으로
 *       한 번 더 보낸다.</li>
 *   <li>(b) pack.url 이 {@code …/pack-host/labyrinth-pack-<sha8>.zip} (공개 사본) 인데 sha8 이 jar 팩과 다르면: 옛 팩이므로 jar 팩의 공개 사본
 *       주소로 바꿔 보내고 한 줄 남긴다 (주인 config 는 065e6258 을 가리킨다). 그 사본을 받아 SHA-1 을 맞춰 보기 전에는, 그리고 받을 수 없으면
 *       내장 주소로 보낸다. 사본을 못 받은 사람에게는 내장 주소로 한 번 더.</li>
 *   <li>(c) 공개 사본 꼴이 아닌 pack.url 은 늘 그대로 쓴다 (주인이 직접 올린 곳). 적힌 pack.sha1 이 jar 팩과 다르면 한 줄 남긴다.</li>
 * </ol>
 * {@code pack.public_copy} 의 {@code {sha8}}·{@code {sha1}} 은 jar 팩 SHA-1 의 앞 8글자·전체로 바뀐다. "" 이면 (a) 의 다시 보내기를 끈다
 * ((b) 는 그때 pack.url 의 sha8 만 바꾼 주소를 쓴다).
 */
public final class PackUrlChoice {

    private PackUrlChoice() {}

    /** 기본 공개 사본: 배포 가지의 labyrinth/pack-host/ (release 때 판마다 사본을 올린다 — tools/check_pack_host.py). */
    public static final String DEFAULT_PUBLIC_COPY = kr.labyrinth.core.Settings.DEFAULT_PACK_PUBLIC_COPY;

    /** 공개 사본 주소 꼴: …/pack-host/labyrinth-pack-&lt;sha8&gt;.zip (물음표 뒤는 무시). */
    static final Pattern PACK_HOST = Pattern.compile("^(.*/pack-host/labyrinth-pack-)([0-9a-fA-F]{8})(\\.zip)(\\?.*)?$");

    public enum Mode {
        /** 내장 서버 (게임 포트 · 8163 · public_host) — 받지 못하면 fallbackUrl 로 한 번 더. */
        BUILTIN,
        /** 주인이 적은 pack.url 그대로 (공개 사본 꼴이 아님). */
        CUSTOM_URL,
        /** 공개 사본 (pack.url 이 jar 팩 사본이거나, 옛 사본이라 jar 팩 사본으로 바꿈). */
        PUBLIC_COPY
    }

    /**
     * @param mode        보내는 방식
     * @param url         외부 주소 (BUILTIN 이면 null — 플레이어마다 내장 주소)
     * @param sha1        클라이언트에 알릴 SHA-1 (빈 글이면 알리지 않음)
     * @param fallbackUrl BUILTIN 에서 받지 못했을 때 한 번 더 보낼 공개 사본 (없으면 null)
     * @param verify      이 주소(url 또는 fallbackUrl)를 시작 때 받아 SHA-1 을 맞춰 봐야 하나
     * @param notice      콘솔 한 줄 (없으면 null)
     */
    public record Plan(Mode mode, String url, String sha1, String fallbackUrl, boolean verify, String notice) {
        /** 시작 때 받아 볼 주소 (없으면 null). */
        public String checkUrl() { return !verify ? null : mode == Mode.BUILTIN ? fallbackUrl : url; }
    }

    /** jar 팩 SHA-1 의 공개 사본 주소. 꼴이 비었거나 SHA-1 이 짧으면 null. */
    public static String publicCopyUrl(String template, String sha1) {
        String s = norm(sha1);
        if (template == null || template.isBlank() || s.length() < 8) return null;
        return template.trim().replace("{sha8}", s.substring(0, 8)).replace("{sha1}", s);
    }

    /** 공개 사본 꼴 주소의 sha8 (소문자). 그 꼴이 아니면 null. */
    public static String hostedSha8(String url) {
        if (url == null) return null;
        Matcher m = PACK_HOST.matcher(url.trim());
        return m.matches() ? m.group(2).toLowerCase(Locale.ROOT) : null;
    }

    /**
     * @param url        config pack.url
     * @param cfgSha1    config pack.sha1
     * @param publicHost config pack.public_host
     * @param template   config pack.public_copy ("" = 끔)
     * @param packSha1   jar 팩(꺼낸 plugins/Labyrinth/pack/labyrinth-pack.zip) 의 SHA-1 — 모르면 ""
     */
    public static Plan decide(String url, String cfgSha1, String publicHost, String template, String packSha1) {
        String u = url == null ? "" : url.trim();
        String jar = norm(packSha1);
        String cfg = norm(cfgSha1);
        if (!u.isEmpty()) {
            String sha8 = hostedSha8(u);
            if (sha8 == null || jar.length() < 8) {
                // (c) 주인이 직접 올린 주소 (또는 jar 팩을 모름) — 그대로. 적힌 sha1 이 jar 팩과 다르면 옛 팩일 수 있어 한 줄 남긴다
                // (0.3.6 팩이면 보석 노드가 그냥 석재 벽돌·조약돌·심층암으로 보인다 — 주소는 그래도 바꾸지 않음)
                String note = !cfg.isEmpty() && jar.length() >= 8 && !cfg.equals(jar)
                        ? "[리소스팩] pack.url 의 팩(sha1 " + cfg.substring(0, Math.min(8, cfg.length())) + ")이 이 jar 팩(" + jar.substring(0, 8)
                          + ")과 달라 새 광석 그림이 안 보일 수 있습니다 — 새 팩을 올리고 pack.sha1 을 고치거나, pack.url 을 비우세요."
                        : null;
                return new Plan(Mode.CUSTOM_URL, u, cfg.isEmpty() ? jar : cfg, null, false, note);
            }
            String jar8 = jar.substring(0, 8);
            if (sha8.equals(jar8)) {
                String note = !cfg.isEmpty() && !cfg.equals(jar)
                        ? "[리소스팩] config 의 pack.sha1 이 이 팩과 달라 jar 팩의 sha1(" + jar8 + ")을 씁니다." : null;
                return new Plan(Mode.PUBLIC_COPY, u, jar, null, false, note);
            }
            // (b) 옛 팩 사본 — jar 팩 사본으로 (PackService 는 그 사본을 받아 SHA-1 을 맞춰 본 뒤에야 그 주소로 보낸다 — 그 전에는 내장 서버)
            String fixed = publicCopyUrl(template, jar);
            if (fixed == null) {
                Matcher m = PACK_HOST.matcher(u);
                fixed = m.matches() ? m.group(1) + jar8 + m.group(3) : u;
            }
            String note = "[리소스팩] config 의 pack.url 이 예전 팩(" + sha8 + ") 사본이라 이 jar 팩(" + jar8 + ") 사본으로 보냅니다 — config 는 고치지 않아도 됩니다.";
            return new Plan(Mode.PUBLIC_COPY, fixed, jar, null, true, note);
        }
        // (a) 내장 주소 먼저, 받지 못하면 공개 사본으로 한 번 더 (public_host 를 쓰는 서버는 그 주소만)
        boolean noHost = publicHost == null || publicHost.isBlank();
        String fb = noHost ? publicCopyUrl(template, jar) : null;
        return new Plan(Mode.BUILTIN, null, jar, fb, fb != null, null);
    }

    /** 받지 못한 사람에게 한 번 더 보낼 곳. */
    public enum Retry { COPY, BUILTIN, NONE }

    /**
     * 클라이언트가 팩을 받지 못했을 때 (FAILED_DOWNLOAD · INVALID_URL) 한 번 더 보낼 곳 — 접속마다 한 번만 ({@link PackService}).
     * 내장 주소를 못 받았으면 확인을 마친 공개 사본, 공개 사본을 못 받았으면 내장 주소(열려 있으면). 직접 적은 pack.url 은 다시 보내지 않는다.
     */
    public static Retry retry(Mode planMode, boolean failedWasBuiltin, boolean failedWasCopy, boolean copyVerified, boolean builtinUp) {
        if (planMode == null || planMode == Mode.CUSTOM_URL) return Retry.NONE;
        if (failedWasCopy) return builtinUp ? Retry.BUILTIN : Retry.NONE;
        if (failedWasBuiltin) return copyVerified ? Retry.COPY : Retry.NONE;
        return Retry.NONE;
    }

    /** 받은 파일이 그 팩인가 (SHA-1 이 같다). */
    public static boolean matches(byte[] body, String sha1) {
        if (body == null || body.length == 0) return false;
        String want = norm(sha1);
        return !want.isEmpty() && want.equals(sha1Hex(body));
    }

    static String sha1Hex(byte[] data) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-1").digest(data));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String norm(String s) { return s == null ? "" : s.trim().toLowerCase(Locale.ROOT); }

    /** 방식 이름 (labadmin pack). */
    public static String label(Mode m) {
        return switch (m) {
            case BUILTIN -> "내장 서버";
            case CUSTOM_URL -> "직접 적은 주소 (pack.url)";
            case PUBLIC_COPY -> "공개 사본";
        };
    }
}
