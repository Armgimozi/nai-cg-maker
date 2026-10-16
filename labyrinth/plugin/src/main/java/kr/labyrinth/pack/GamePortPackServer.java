package kr.labyrinth.pack;

import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.Channel;
import io.netty.channel.ChannelFutureListener;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.ChannelPipeline;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.util.function.Supplier;
import kr.labyrinth.core.Log;
import net.kyori.adventure.key.Key;

/**
 * 리소스팩을 게임 포트(25565)로도 보낸다 — playit.gg 같은 터널은 게임 포트 하나만 이어 주므로 8163 을 따로 열 필요가 없게.
 * <p>
 * Paper 의 채널 초기화 리스너(서버 내부 {@code io.papermc.paper.network.ChannelInitializeListenerHolder}, 리플렉션)로 새 접속마다
 * 맨 앞쪽에 {@link Sniffer} 를 끼운다. 첫 바이트가 {@code "GET "}/{@code "HEAD"} 면 HTTP 로 보고 팩을 보낸 뒤 연결을 닫고,
 * 아니면 자신을 빼고 받은 바이트를 그대로 마인크래프트 쪽으로 넘긴다. 마인크래프트 핸드셰이크는 둘째 바이트가 패킷 id 0x00
 * 이고 옛 서버 목록 핑은 0xFE 로 시작하므로 "GE"·"HE" 와 겹치지 않는다.
 * 리스너를 못 붙이면(Paper 내부가 바뀐 경우) 경고만 하고 8163 내장 서버만 쓴다.
 */
final class GamePortPackServer {

    private static final String HOLDER = "io.papermc.paper.network.ChannelInitializeListenerHolder";
    private static final String LISTENER = "io.papermc.paper.network.ChannelInitializeListener";
    private static final Key KEY = Key.key("labyrinth", "pack_http");
    static final String HANDLER = "labyrinth_pack_http";
    /** HTTP 요청 머리(요청 줄 + 헤더)를 이만큼까지만 모은다. */
    static final int MAX_HEAD = 8192;

    private final Supplier<byte[]> pack;
    private final String fileName;
    private boolean installed;

    GamePortPackServer(Supplier<byte[]> pack, String fileName) {
        this.pack = pack;
        this.fileName = fileName;
    }

    boolean installed() { return installed; }

    /** 리스너를 붙인다. 성공하면 true. */
    boolean install() {
        if (installed) return true;
        try {
            Class<?> holder = Class.forName(HOLDER);
            Class<?> iface = Class.forName(LISTENER);
            Object listener = Proxy.newProxyInstance(GamePortPackServer.class.getClassLoader(), new Class<?>[] {iface},
                    (proxy, m, args) -> switch (m.getName()) {
                        case "afterInitChannel" -> {
                            inject((Channel) args[0]);
                            yield null;
                        }
                        case "hashCode" -> System.identityHashCode(proxy);
                        case "equals" -> proxy == args[0];
                        case "toString" -> "LabyrinthPackHttpListener";
                        default -> null;
                    });
            Method has = holder.getMethod("hasListener", Key.class);
            if (Boolean.TRUE.equals(has.invoke(null, KEY))) holder.getMethod("removeListener", Key.class).invoke(null, KEY);
            holder.getMethod("addListener", Key.class, iface).invoke(null, KEY, listener);
            installed = true;
            return true;
        } catch (ReflectiveOperationException | LinkageError | RuntimeException e) {
            Log.warn("리소스팩을 게임 포트로 보내는 기능을 켜지 못했습니다 (" + e.getClass().getSimpleName() + ": " + e.getMessage()
                    + ") — 8163 포트만 씁니다.");
            return false;
        }
    }

    void uninstall() {
        if (!installed) return;
        try {
            Class.forName(HOLDER).getMethod("removeListener", Key.class).invoke(null, KEY);
        } catch (ReflectiveOperationException | LinkageError | RuntimeException e) {
            Log.warn("게임 포트 리소스팩 리스너 해제 실패: " + e.getMessage());
        }
        installed = false;
    }

    private void inject(Channel ch) {
        try {
            ChannelPipeline p = ch.pipeline();
            if (p.get(HANDLER) != null) return;
            // PROXY protocol(haproxy) 을 쓰면 그 뒤에, 아니면 timeout 뒤(= 마인크래프트 해석기들 앞)에
            if (p.get("haproxy-handler") != null) p.addAfter("haproxy-handler", HANDLER, new Sniffer());
            else if (p.get("timeout") != null) p.addAfter("timeout", HANDLER, new Sniffer());
            else p.addFirst(HANDLER, new Sniffer());
        } catch (RuntimeException e) {
            // 새 접속 하나에서 실패해도 그 접속은 그대로 마인크래프트로 간다
        }
    }

    /** 첫 바이트가 HTTP 인지 본다: 1 = HTTP, 0 = 아님, -1 = 아직 모름(바이트 부족). */
    static int classify(byte[] head, int len) {
        if (len <= 0) return -1;
        if (head[0] != 'G' && head[0] != 'H') return 0;
        String want = head[0] == 'G' ? "GET " : "HEAD ";
        for (int i = 0; i < want.length(); i++) {
            if (i >= len) return -1;
            if (head[i] != want.charAt(i)) return 0;
        }
        return 1;
    }

    /** 요청 머리에서 경로를 꺼낸다 ("GET /a.zip?v=1 HTTP/1.1" → "/a.zip"). 못 읽으면 null. */
    static String path(String head) {
        int eol = head.indexOf('\r');
        String line = eol >= 0 ? head.substring(0, eol) : head;
        String[] parts = line.split(" ");
        if (parts.length < 2) return null;
        String target = parts[1];
        int q = target.indexOf('?');
        return q >= 0 ? target.substring(0, q) : target;
    }

    static boolean headComplete(String head) { return head.contains("\r\n\r\n") || head.contains("\n\n"); }

    final class Sniffer extends ChannelInboundHandlerAdapter {

        private ByteBuf buf;
        private boolean http;

        @Override
        public void channelRead(ChannelHandlerContext ctx, Object msg) {
            if (!(msg instanceof ByteBuf in)) {
                ctx.fireChannelRead(msg);
                return;
            }
            if (buf == null) buf = ctx.alloc().buffer(Math.max(64, in.readableBytes()));
            buf.writeBytes(in);
            in.release();
            if (!http) {
                int n = Math.min(buf.readableBytes(), 5);
                byte[] head = new byte[n];
                buf.getBytes(buf.readerIndex(), head);
                int kind = classify(head, n);
                if (kind < 0) return;                    // 더 받아야 앎
                if (kind == 0) {                         // 마인크래프트 — 나를 빼고 그대로 넘김
                    ByteBuf pass = buf;
                    buf = null;
                    ctx.pipeline().remove(this);
                    ctx.fireChannelRead(pass);
                    return;
                }
                http = true;
                // 큰 팩을 느린 터널로 보내는 동안 읽기 시간 초과로 끊기지 않게
                if (ctx.pipeline().get("timeout") != null) ctx.pipeline().remove("timeout");
            }
            String head = buf.toString(buf.readerIndex(), Math.min(buf.readableBytes(), MAX_HEAD), StandardCharsets.ISO_8859_1);
            if (!headComplete(head)) {
                if (buf.readableBytes() >= MAX_HEAD) respond(ctx, 431, "text/plain", "too large".getBytes(StandardCharsets.US_ASCII), false);
                return;
            }
            boolean headOnly = head.startsWith("HEAD ");
            String path = path(head);
            byte[] data = pack.get();
            if (data == null || path == null || !path.equals("/" + fileName)) {
                respond(ctx, 404, "text/plain", "not found".getBytes(StandardCharsets.US_ASCII), headOnly);
            } else {
                respond(ctx, 200, "application/zip", data, headOnly);
            }
        }

        private void respond(ChannelHandlerContext ctx, int code, String type, byte[] body, boolean headOnly) {
            if (buf != null) {
                buf.release();
                buf = null;
            }
            String reason = code == 200 ? "OK" : code == 404 ? "Not Found" : "Request Header Fields Too Large";
            String header = "HTTP/1.1 " + code + " " + reason + "\r\n"
                    + "Content-Type: " + type + "\r\n"
                    + "Content-Length: " + body.length + "\r\n"
                    + "Cache-Control: no-cache\r\n"
                    + "Connection: close\r\n\r\n";
            ByteBuf out = headOnly
                    ? Unpooled.wrappedBuffer(header.getBytes(StandardCharsets.US_ASCII))
                    : Unpooled.wrappedBuffer(header.getBytes(StandardCharsets.US_ASCII), body);
            ctx.writeAndFlush(out).addListener(ChannelFutureListener.CLOSE);
        }

        @Override
        public void channelInactive(ChannelHandlerContext ctx) throws Exception {
            if (buf != null) {
                buf.release();
                buf = null;
            }
            super.channelInactive(ctx);
        }

        @Override
        public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) throws Exception {
            if (http) {
                ctx.close();
                return;
            }
            super.exceptionCaught(ctx, cause);
        }
    }
}
