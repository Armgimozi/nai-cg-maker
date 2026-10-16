package kr.labyrinth.pack;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

/** 게임 포트로 팩 보내기: HTTP 와 마인크래프트 첫 바이트 가르기, 경로 읽기, 접속 포트 읽기. */
class GamePortPackServerTest {

    private static int kind(String s) {
        byte[] b = s.getBytes(StandardCharsets.ISO_8859_1);
        return GamePortPackServer.classify(b, b.length);
    }

    private static int kind(byte... b) { return GamePortPackServer.classify(b, b.length); }

    @Test
    void httpIsRecognised() {
        assertEquals(1, kind("GET /labyrinth-pack.zip HTTP/1.1"));
        assertEquals(1, kind("HEAD "));
        assertEquals(-1, kind("GE"), "바이트가 모자라면 더 기다림");
        assertEquals(-1, kind("HEA"));
        assertEquals(-1, kind(new byte[0]));
    }

    @Test
    void minecraftIsPassedThrough() {
        // 핸드셰이크: VarInt 길이 + 패킷 id 0x00 — 'G'(71) 길이여도 둘째 바이트가 0x00
        assertEquals(0, kind((byte) 71, (byte) 0x00, (byte) 0xF8, (byte) 0x05));
        assertEquals(0, kind((byte) 72, (byte) 0x00));
        assertEquals(0, kind((byte) 0xFE, (byte) 0x01));            // 옛 서버 목록 핑
        assertEquals(0, kind((byte) 0x10, (byte) 0x00));
        assertEquals(0, kind("POST /x"));
        assertEquals(0, kind("GETX"));
        assertEquals(0, kind("PROXY TCP4 1.2.3.4"));                // PROXY 머리는 그대로 넘김
    }

    @Test
    void pathAndHead() {
        assertEquals("/labyrinth-pack.zip", GamePortPackServer.path("GET /labyrinth-pack.zip?v=abcd1234 HTTP/1.1\r\nHost: x\r\n\r\n"));
        assertEquals("/", GamePortPackServer.path("HEAD / HTTP/1.0\r\n\r\n"));
        assertNull(GamePortPackServer.path("GET"));
        assertTrue(GamePortPackServer.headComplete("GET / HTTP/1.1\r\nHost: a\r\n\r\n"));
        assertFalse(GamePortPackServer.headComplete("GET / HTTP/1.1\r\nHost: a\r\n"));
    }

    @Test
    void joinPortParsing() {
        assertEquals(12345, PackService.parsePort("12345"));
        assertEquals(-1, PackService.parsePort("0"));
        assertEquals(-1, PackService.parsePort("70000"));
        assertEquals(-1, PackService.parsePort("abc"));
    }
}
