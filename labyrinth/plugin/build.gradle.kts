plugins {
    java
}

group = "kr.labyrinth"
version = "0.3.2"

repositories {
    maven("https://repo.papermc.io/repository/maven-public/")
    mavenCentral()
}

dependencies {
    compileOnly("io.papermc.paper:paper-api:26.3.build.181-stable")
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("io.papermc.paper:paper-api:26.3.build.181-stable")
}

java {
    toolchain.languageVersion = JavaLanguageVersion.of(25)
}

tasks.withType<JavaCompile> {
    options.encoding = "UTF-8"
    options.release = 25
    options.compilerArgs.add("-Xlint:deprecation")
}

tasks.test {
    useJUnitPlatform()
}

tasks.processResources {
    filteringCharset = "UTF-8"
    // 버전을 입력으로 등록해야 버전만 바뀌었을 때도 plugin.yml 을 다시 만든다 (아니면 예전 버전 문자열이 남음)
    inputs.property("version", project.version)
    filesMatching("plugin.yml") {
        expand("version" to project.version)
    }
    // 리소스팩 생성기 결과물이 있으면 jar 에 포함 → PackService 가 첫 실행 때 꺼내 서빙 (jar 하나로 배포)
    from("../resourcepack/dist") {
        include("labyrinth-pack.zip")
        into("pack")
    }
    inputs.files(fileTree("../resourcepack/dist") { include("labyrinth-pack.zip") })
}
