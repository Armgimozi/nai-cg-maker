package kr.souls;

import io.papermc.paper.plugin.bootstrap.BootstrapContext;
import io.papermc.paper.plugin.bootstrap.PluginBootstrap;
import io.papermc.paper.plugin.lifecycle.event.types.LifecycleEvents;

import java.net.URI;
import java.net.URL;

/**
 * 부트스트래퍼: 서버가 세계를 읽기 전에 jar 안의 데이터팩(datapack/soulsdp)을 싣는다 (12.2).
 * 지역 바이옴 9개와 피해 종류 souls:hit 가 이 데이터팩에 있다. 바이옴 이름은 청크에 저장되므로
 * souls_world 를 처음 만들 때부터 이 이름들이 등록부에 있어야 한다 (8.1).
 * 데이터팩 찾기는 서버가 팩을 다시 훑을 때마다 불리므로, 그때마다 다시 알려야 한다.
 */
public final class SoulsBootstrap implements PluginBootstrap {
    /** 데이터팩 id. 서버에는 플러그인 이름과 묶인 이름으로 올라간다 (/souls check 가 이 조각으로 찾는다). */
    public static final String DATAPACK_ID = "soulsdp";

    @Override
    public void bootstrap(BootstrapContext context) {
        context.getLifecycleManager().registerEventHandler(LifecycleEvents.DATAPACK_DISCOVERY, event -> {
            try {
                URL url = SoulsBootstrap.class.getResource("/datapack/" + DATAPACK_ID);
                if (url == null) {
                    context.getLogger().error("jar 안에 datapack/" + DATAPACK_ID + " 가 없습니다. 지역 바이옴 없이 켜집니다.");
                    return;
                }
                URI uri = url.toURI();
                var dp = event.registrar().discoverPack(uri, DATAPACK_ID, c -> c.autoEnableOnServerStart(true));
                if (dp == null) context.getLogger().error("데이터팩 " + DATAPACK_ID + " 를 싣지 못했습니다 (pack.mcmeta 형식을 확인하세요).");
                else context.getLogger().info("데이터팩 " + dp.getName() + " 을 실었습니다.");
            } catch (Exception e) {
                context.getLogger().error("데이터팩 " + DATAPACK_ID + " 를 싣다가 오류가 났습니다", e);
            }
        });
    }
}
