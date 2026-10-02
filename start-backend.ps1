# 一条命令启动后端：
#   检查 Docker 和数据库容器 → 团队数据快照有更新时重新导入 → 数据库迁移到最新 → 启动后端并打开接口文档
# 用法（在仓库根目录）：.\start-backend.ps1

$container = "careerpilot-postgres"
$compose = "$PSScriptRoot/docker-compose.yml"

function Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Fail($message) {
    Write-Host "[错误] $message" -ForegroundColor Red
    exit 1
}

function Wait-Database {
    $deadline = (Get-Date).AddMinutes(1)
    while ((docker inspect -f "{{.State.Health.Status}}" $container) -ne "healthy") {
        if ((Get-Date) -gt $deadline) { Fail "数据库容器 1 分钟内未就绪，可运行 docker compose logs postgres 查看原因" }
        Start-Sleep -Seconds 2
    }
}

# 在容器里执行一条 SQL，返回纯文本结果；SQL 里只用单引号，避免 PowerShell 5.1 传参时吞掉双引号
function Invoke-Sql($sql) {
    $result = docker exec $container psql -U careerpilot -d careerpilot -tAc $sql
    if ($LASTEXITCODE -ne 0) { Fail "执行 SQL 失败：$sql" }
    return $result
}

# 数据库迁移到最新版本（已是最新时什么都不做）；需要先激活 conda 环境
function Update-Database {
    Push-Location "$PSScriptRoot/SystemCode/backend"
    try { python -m alembic upgrade head }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Fail "数据库迁移失败，见上方输出" }
}

# 导入快照前先备份单用户数据（画像 + 简历上传记录），导入后放回，其余数据全部换成快照内容
function Import-Snapshot($snapshot, $marker) {
    $backup = $null
    $hasUserTables = Invoke-Sql "SELECT to_regclass('public.user_profile') IS NOT NULL AND to_regclass('public.resume_uploads') IS NOT NULL"
    if ($hasUserTables -eq "t") {
        # 备份是 --data-only，只有表结构一致才能放回：先把当前库迁到最新，导入快照后也迁到最新再放回
        Update-Database
        # 备份放在系统临时目录而不是仓库里，避免把简历内容误提交
        $backup = Join-Path $env:TEMP "careerpilot-my-data-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
        docker exec $container pg_dump -U careerpilot -d careerpilot --data-only -t user_profile -t resume_uploads -Fc -f /tmp/my-data.dump
        if ($LASTEXITCODE -ne 0) { Fail "备份用户画像和简历记录失败，已中止，数据库没有改动" }
        docker cp "${container}:/tmp/my-data.dump" $backup
        if ($LASTEXITCODE -ne 0) { Fail "备份文件复制到本机失败，已中止，数据库没有改动" }
        Write-Host "已备份你的用户画像和简历记录：$backup"
    }

    Write-Host "清空数据库并重新创建容器……"
    docker compose -f $compose down -v
    if ($LASTEXITCODE -ne 0) { Fail "docker compose down -v 失败" }
    docker compose -f $compose up -d postgres
    if ($LASTEXITCODE -ne 0) { Fail "数据库容器启动失败" }
    Wait-Database

    Write-Host "导入快照 $($snapshot.Name)……"
    docker cp $snapshot.FullName "${container}:/tmp/snapshot.dump"
    if ($LASTEXITCODE -ne 0) { Fail "快照文件复制进容器失败" }
    docker exec $container pg_restore -U careerpilot -d careerpilot --no-owner /tmp/snapshot.dump
    if ($LASTEXITCODE -ne 0) { Fail "pg_restore 导入快照失败，见上方输出" }

    if ($backup) {
        Write-Host "放回你的用户画像和简历记录……"
        Update-Database
        docker cp $backup "${container}:/tmp/my-data.dump"
        if ($LASTEXITCODE -ne 0) { Fail "备份文件复制进容器失败，备份仍在 $backup" }
        Invoke-Sql "TRUNCATE user_profile, resume_uploads" | Out-Null
        docker exec $container pg_restore -U careerpilot -d careerpilot --data-only /tmp/my-data.dump
        if ($LASTEXITCODE -ne 0) { Fail "恢复你的数据失败，备份仍在 $backup" }
        # 自增 id 对齐到已有最大值，避免下次上传简历时主键冲突
        Invoke-Sql "SELECT setval(pg_get_serial_sequence('resume_uploads', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM resume_uploads" | Out-Null
    }

    # 在数据库注释里记下导入的是哪个快照，下次启动据此判断是否需要重新导入
    Invoke-Sql "COMMENT ON DATABASE careerpilot IS '$marker'" | Out-Null
    Write-Host "快照导入完成" -ForegroundColor Green
}

# 1. Docker Desktop：没运行就自动打开，并等待引擎就绪
Step "检查 Docker Desktop"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) { Fail "找不到 docker 命令：请确认已安装 Docker Desktop，并新开一个终端再试" }
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    # docker.exe 位于 <安装目录>\resources\bin\，往上三级就是 Docker Desktop.exe 所在的安装目录
    $desktopExe = Join-Path (Split-Path (Split-Path (Split-Path $docker.Source))) "Docker Desktop.exe"
    if (-not (Test-Path $desktopExe)) { Fail "Docker Desktop 未运行，且找不到 $desktopExe，请手动打开 Docker Desktop" }
    Write-Host "Docker Desktop 未运行，正在启动……"
    Start-Process $desktopExe
    $deadline = (Get-Date).AddMinutes(2)
    do {
        if ((Get-Date) -gt $deadline) { Fail "等待 Docker 引擎启动超时（2 分钟），请打开 Docker Desktop 查看状态" }
        Start-Sleep -Seconds 2
        docker info *> $null
    } while ($LASTEXITCODE -ne 0)
}
Write-Host "Docker 引擎已运行"

# 2. 数据库容器：up -d 对已在运行的容器不做任何改动，所以可以每次都执行
Step "启动数据库容器并等待就绪"
docker compose -f $compose up -d postgres
if ($LASTEXITCODE -ne 0) { Fail "数据库容器启动失败，见上方 docker 输出" }
Wait-Database
Write-Host "数据库容器已就绪（healthy）"

# 3. 激活后端环境：导入快照时也要跑数据库迁移，所以放在快照检查之前
if ($env:CONDA_DEFAULT_ENV -ne "careerpilot-backend") { conda activate careerpilot-backend }
if ($env:CONDA_DEFAULT_ENV -ne "careerpilot-backend") { Fail "无法激活 conda 环境 careerpilot-backend" }

# 4. 团队数据快照：取仓库里文件名最新的 .dump（文件名带日期），和数据库注释里记录的快照比较
Step "检查团队数据快照"
$snapshot = Get-ChildItem "$PSScriptRoot/SystemCode/backend/data/database/*.dump" | Sort-Object Name | Select-Object -Last 1
if (-not $snapshot) {
    Write-Host "仓库里没有数据快照，跳过"
}
else {
    $marker = "$($snapshot.Name)|$((Get-FileHash $snapshot.FullName -Algorithm SHA256).Hash)"
    $imported = Invoke-Sql "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = 'careerpilot'"
    $tableCount = Invoke-Sql "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"

    if ($imported -eq $marker) {
        Write-Host "数据已是最新快照：$($snapshot.Name)"
    }
    elseif ($tableCount -eq "0") {
        # 空库没有可丢失的数据，直接导入
        Write-Host "数据库是空的，导入最新快照"
        Import-Snapshot $snapshot $marker
    }
    else {
        if ($imported) {
            Write-Host "团队数据快照有更新：当前库来自 $($imported.Split('|')[0])，最新是 $($snapshot.Name)" -ForegroundColor Yellow
        }
        else {
            Write-Host "数据库里没有记录导入过哪个快照（手动导入的库会这样），无法判断是否最新" -ForegroundColor Yellow
        }
        $answer = Read-Host "是否重新导入 $($snapshot.Name)？会清空数据库，但保留你的用户画像和简历上传记录 [y/N]"
        if ($answer -eq "y") {
            Import-Snapshot $snapshot $marker
        }
        elseif (-not $imported) {
            # 没有记录时选 N，视为当前数据就是最新快照，之后只在快照再次更新时提醒
            Invoke-Sql "COMMENT ON DATABASE careerpilot IS '$marker'" | Out-Null
            Write-Host "已把当前数据记为 $($snapshot.Name)，之后快照再更新时会提醒"
        }
        else {
            Write-Host "本次跳过，下次启动会再提醒"
        }
    }
}

Push-Location "$PSScriptRoot/SystemCode/backend"
try {
    # 5. 数据库迁移：快照可能比代码旧，导入后也要检查；当前版本带 (head) 标记说明已是最新
    Step "检查数据库迁移"
    $current = python -m alembic current 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "无法读取数据库版本，请检查根目录 .env 里的 DATABASE_URL" }
    if ("$current" -match "\(head\)") {
        Write-Host "数据库已是最新版本：$current"
    }
    else {
        Write-Host "数据库版本落后（当前：$(if ($current) { $current } else { '无版本记录' })），正在升级到最新……" -ForegroundColor Yellow
        python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Fail "数据库迁移失败，见上方输出" }
    }

    # 6. 后台等待 8000 端口可连接再打开 /docs，避免浏览器先于后端打开而报错
    Start-Job {
        while ($true) {
            $client = [Net.Sockets.TcpClient]::new()
            try { $client.Connect("127.0.0.1", 8000); break }
            catch { Start-Sleep -Milliseconds 500 }
            finally { $client.Dispose() }
        }
        Start-Process "http://127.0.0.1:8000/docs"
    } | Out-Null

    Step "启动后端（Ctrl + C 停止）"
    python -m uvicorn app.main:app --reload --port 8000
}
finally { Pop-Location }
