# 증강 스카이블럭 서버 시작기. start.bat 이 이 파일을 실행합니다.
# 처음 실행하면 Java 21 과 Paper 1.21.4 를 자동으로 내려받습니다.
# 무슨 일이 있었는지는 이 폴더의 start-log.txt 에 그대로 남습니다.
# (윈도우 PowerShell 5.1 에서도 돌아가도록 새 문법은 쓰지 않습니다)

$PaperUrl  = 'https://fill-data.papermc.io/v1/objects/5ee4f542f628a14c644410b08c94ea42e772ef4d29fe92973636b6813d4eaffc/paper-1.21.4-232.jar'
$PaperSize = 51437498
$JavaUrl   = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse'
# 서버 메모리. 비워 두면 PC 메모리를 보고 2G~4G 사이에서 고릅니다. 직접 정하려면 예) $Memory = '6G'
$Memory = ''

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # 5.1 의 다운로드 진행 표시는 매우 느리다
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root
try { $Host.UI.RawUI.WindowTitle = '증강 스카이블럭 서버' } catch {}
try { Start-Transcript -LiteralPath (Join-Path $Root 'start-log.txt') -Force | Out-Null } catch {}

function Say($msg, $color) {
    if ($color) { Write-Host $msg -ForegroundColor $color } else { Write-Host $msg }
}

function Stop-WithMessage($lines) {
    Say ''
    foreach ($l in $lines) { Say $l 'Red' }
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

# java 실행 파일의 주 버전 (21, 17, 1 ...). 실행이 안 되면 0
function Get-JavaMajor($exe) {
    if (-not $exe) { return 0 }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = '-version'
        $psi.UseShellExecute = $false
        $psi.RedirectStandardError = $true
        $psi.RedirectStandardOutput = $true
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $err = $p.StandardError.ReadToEnd()
        $out = $p.StandardOutput.ReadToEnd()
        $p.WaitForExit()
        if (($err + $out) -match 'version "(\d+)') { return [int]$Matches[1] }
    } catch {}
    return 0
}

# java 가 이 메모리 설정으로 뜨는지 (힙을 못 잡으면 바로 오류로 끝난다)
function Test-JavaMemory($exe, $xms, $xmx) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe
        $psi.Arguments = "-Xms$xms -Xmx$xmx -version"
        $psi.UseShellExecute = $false
        $psi.RedirectStandardError = $true
        $psi.RedirectStandardOutput = $true
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $script:JvmSays = $p.StandardError.ReadToEnd() + $p.StandardOutput.ReadToEnd()
        $p.WaitForExit()
        return ($p.ExitCode -eq 0)
    } catch {
        $script:JvmSays = "$_"
        return $false
    }
}

# 내려받기: curl.exe(윈도우 10 이상 기본) → 안 되면 PowerShell 로 한 번 더
function Get-File($url, $file) {
    $part = "$file.part"
    if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
    $curl = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($curl) {
        & $curl.Source -fL --retry 3 --connect-timeout 30 -o $part $url
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $part)) {
            Move-Item -LiteralPath $part -Destination $file -Force
            return $true
        }
        Say "  curl 로 받지 못했습니다 (코드 $LASTEXITCODE). 다른 방법으로 다시 받습니다..." 'Yellow'
    }
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $part
        Move-Item -LiteralPath $part -Destination $file -Force
        return $true
    } catch {
        Say "  내려받기 실패: $_" 'Yellow'
        return $false
    }
}

# zip 이 온전한지 (중간에 끊긴 파일 걸러내기)
function Test-Zip($file) {
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $z = [System.IO.Compression.ZipFile]::OpenRead($file)
        $n = $z.Entries.Count
        $z.Dispose()
        return ($n -gt 0)
    } catch { return $false }
}

# 백신이 방금 푼 파일을 검사하는 동안 폴더 이동이 잠깐 막힐 수 있어 몇 번 다시 시도한다
function Move-Retry($from, $to) {
    for ($i = 0; $i -lt 10; $i++) {
        try { Move-Item -LiteralPath $from -Destination $to -Force; return $true }
        catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

try {
    Say '[증강 스카이블럭 시작기 4판]' 'Cyan'
    Say "폴더: $Root"

    # ── 압축을 풀었는지 ──
    if (-not (Test-Path -LiteralPath 'plugins\AugmentSkyblock.jar') -or -not (Test-Path -LiteralPath 'world\level.dat')) {
        Stop-WithMessage @(
            '압축을 먼저 모두 풀어 주세요.',
            'zip 파일을 연 상태에서 바로 start.bat 을 실행하면 플러그인과 맵이 없어 서버가 켜지지 않습니다.',
            'zip 파일을 마우스 오른쪽 버튼으로 눌러 "압축 풀기" 를 한 뒤, 풀린 폴더 안의 start.bat 을 실행하세요.')
    }

    # ── Java 21 ──
    Say ''
    Say 'Java 확인 중...'
    $java = $null
    $local = Join-Path $Root 'runtime\bin\java.exe'
    if ((Test-Path -LiteralPath $local) -and ((Get-JavaMajor $local) -ge 21)) { $java = $local }
    if (-not $java) {
        $cmd = Get-Command java.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and ((Get-JavaMajor $cmd.Source) -ge 21)) { $java = $cmd.Source }
    }
    if (-not $java) {
        Say '[1/2] Java 21 을 내려받는 중입니다... (처음 한 번만, 50MB 정도, 1~2분)' 'Cyan'
        $zip = Join-Path $Root 'java21.zip'
        if (-not (Get-File $JavaUrl $zip) -or -not (Test-Zip $zip)) {
            Stop-WithMessage @(
                'Java 21 을 자동으로 받지 못했습니다. 인터넷 연결을 확인하고 다시 실행하거나,',
                'https://adoptium.net 에서 "Temurin 21" (Windows x64, .msi) 을 설치한 뒤 다시 실행하세요.')
        }
        Say '  압축 푸는 중...'
        $tmp = Join-Path $Root 'runtime_tmp'
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)
        $inner = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
        $rt = Join-Path $Root 'runtime'
        if (Test-Path -LiteralPath $rt) { Remove-Item -LiteralPath $rt -Recurse -Force }
        if (-not $inner -or -not (Move-Retry $inner.FullName $rt)) {
            Stop-WithMessage @('받은 Java 를 runtime 폴더로 옮기지 못했습니다. 백신이 막았을 수 있습니다.',
                               '잠시 뒤 다시 실행해 보세요.')
        }
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        if ((Get-JavaMajor $local) -lt 21) {
            Stop-WithMessage @('받은 Java 가 실행되지 않습니다. runtime 폴더를 지우고 다시 실행하거나,',
                               'https://adoptium.net 에서 "Temurin 21" 을 설치하세요.')
        }
        $java = $local
    }
    Say "  Java: $java"

    # ── Paper 서버 파일 ──
    $paper = Join-Path $Root 'paper.jar'
    if (-not ((Test-Path -LiteralPath $paper) -and (Test-Zip $paper))) {
        Say '[2/2] Paper 1.21.4 서버 파일을 내려받는 중입니다... (50MB 정도)' 'Cyan'
        $ok = Get-File $PaperUrl $paper
        if (-not $ok -or (Get-Item -LiteralPath $paper).Length -ne $PaperSize -or -not (Test-Zip $paper)) {
            Remove-Item -LiteralPath $paper -Force -ErrorAction SilentlyContinue
            Stop-WithMessage @(
                'Paper 서버 파일을 받지 못했습니다. 인터넷 연결을 확인하고 다시 실행하거나,',
                'https://papermc.io/downloads/all 에서 1.21.4 를 받아 이 폴더에 paper.jar 라는 이름으로 넣어 주세요.')
        }
    }
    Say '  Paper: paper.jar'

    # ── 메모리 ──
    if (-not $Memory) {
        $gb = 8
        try { $gb = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch {}
        if ($gb -ge 12) { $Memory = '4G' } elseif ($gb -ge 7) { $Memory = '3G' } else { $Memory = '2G' }
        Say "  PC 메모리 약 ${gb}GB → 서버 메모리 $Memory"
    }
    $xms = '1G'
    if (-not (Test-JavaMemory $java $xms $Memory)) {
        Say "  메모리 $Memory 로 Java 가 뜨지 않아 2G 로 낮춥니다." 'Yellow'
        $Memory = '2G'; $xms = '512M'
        if (-not (Test-JavaMemory $java $xms $Memory)) {
            Stop-WithMessage @('Java 가 시작되지 않습니다. Java 가 남긴 말:', $script:JvmSays,
                               '이 창을 사진으로 찍어 보내 주세요.')
        }
    }

    # ── EULA ──
    $eula = Join-Path $Root 'eula.txt'
    $agreed = (Test-Path -LiteralPath $eula) -and ((Get-Content -LiteralPath $eula -Raw) -match 'eula\s*=\s*true')
    if (-not $agreed) {
        Say ''
        Say '================================================================' 'Cyan'
        Say ' 마인크래프트 서버를 열려면 Mojang 의 최종 사용자 계약(EULA)에'
        Say ' 동의해야 합니다.  내용: https://aka.ms/MinecraftEULA'
        Say '================================================================' 'Cyan'
        while ($true) {
            $a = Read-Host '동의하면 Y 를 입력하고 Enter 를 누르세요'
            # 한글 입력 상태에서 Y 를 누르면 'ㅛ' 가 들어간다
            if ($a -and ($a.Trim() -match '^(y|yes|ㅛ|예|네)$')) { break }
            Say ' Y 를 입력해야 서버를 켤 수 있습니다. (한/영 키를 눌러 영어로 바꿔도 됩니다)' 'Yellow'
        }
        Set-Content -LiteralPath $eula -Value 'eula=true' -Encoding ASCII
        Say ' 동의했습니다.'
    }

    # ── 서버 켜기 ──
    Say ''
    Say '서버를 켭니다. 아래에 "Done" 이 나오면 마인크래프트 1.21.4 에서 localhost 로 접속하세요.' 'Green'
    Say '처음에는 마인크래프트 서버 파일을 한 번 더 받느라 1분쯤 걸립니다.'
    Say '서버를 끌 때는 이 창에 stop 을 입력하세요.'
    Say ''
    Say "실행: `"$java`" -Xms$xms -Xmx$Memory -jar paper.jar nogui"
    & $java "-Xms$xms" "-Xmx$Memory" -jar paper.jar nogui
    $code = $LASTEXITCODE
    Say ''
    if ($code -eq 0) {
        Say '서버가 꺼졌습니다.' 'Green'
    } else {
        Say "서버가 오류로 꺼졌습니다 (코드 $code). 위쪽의 ERROR 줄을 확인하세요." 'Red'
        Say ' - "FAILED TO BIND TO PORT" 가 보이면: 서버가 이미 하나 켜져 있습니다. 다른 서버 창을 닫으세요.'
        Say ' - 자세한 기록: logs\latest.log'
    }
} catch {
    Say ''
    Say "예상하지 못한 오류가 났습니다: $_" 'Red'
    Say ($_.ScriptStackTrace) 'DarkGray'
    Say '이 창을 사진으로 찍어 보내 주세요.' 'Red'
}
try { Stop-Transcript | Out-Null } catch {}
