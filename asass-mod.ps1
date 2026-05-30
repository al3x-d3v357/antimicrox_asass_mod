param(
    [string]$ProjectRoot = "",
    [string]$Theme = "neo-carbon.qss",
    [string]$ProfileName = "",
    [switch]$Menu,
    [switch]$Run,
    [switch]$Vanilla,
    [switch]$Setup,
    [switch]$CleanMissing,
    [switch]$Audit,
    [switch]$SetProfile,
    [switch]$AllControllers,
    [switch]$Backup,
    [switch]$BuildSingle,
    [switch]$RebuildSingle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not [string]::IsNullOrWhiteSpace($scriptPath)) {
        $ProjectRoot = Split-Path -Parent $scriptPath
    }
    else {
        $ProjectRoot = (Get-Location).Path
    }
}

function Convert-ToForwardSlashes {
    param([string]$Path)
    return ($Path -replace "\\", "/")
}

function Invoke-SetupPortable {
    param([string]$Root, [bool]$ShouldClean)

    $settingsPath = Join-Path $Root "bin\antimicrox_settings.ini"
    $ps1Dir = Join-Path $Root "ps1"
    $ps3Dir = Join-Path $Root "ps3"

    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Arquivo nao encontrado: $settingsPath"
    }

    $backupDir = Join-Path $Root "bin\backups"
    if (-not (Test-Path -LiteralPath $backupDir)) {
        New-Item -Path $backupDir -ItemType Directory | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $backupDir ("antimicrox_settings.ini." + $timestamp + ".bak")
    Copy-Item -LiteralPath $settingsPath -Destination $backupPath -Force

    $ps1DirFwd = Convert-ToForwardSlashes $ps1Dir
    $ps3DirFwd = Convert-ToForwardSlashes $ps3Dir

    $updated = New-Object System.Collections.Generic.List[string]
    $lines = Get-Content -LiteralPath $settingsPath

    foreach ($line in $lines) {
        if ($line -notmatch "^(?<key>[^=]+)=(?<value>.*)$") {
            $updated.Add($line)
            continue
        }

        $key = $matches["key"]
        $value = $matches["value"]

        if ($key -eq "LastProfileDir") {
            $updated.Add("$key=$ps1DirFwd")
            continue
        }

        if ($key -notmatch "(LastSelected|ConfigFile\d+)$") {
            $updated.Add($line)
            continue
        }

        if ([string]::IsNullOrWhiteSpace($value)) {
            $updated.Add($line)
            continue
        }

        $fileName = Split-Path -Leaf $value
        if ([string]::IsNullOrWhiteSpace($fileName)) {
            $updated.Add($line)
            continue
        }

        $ps1Candidate = Join-Path $ps1Dir $fileName
        $ps3Candidate = Join-Path $ps3Dir $fileName

        if (Test-Path -LiteralPath $ps1Candidate) {
            $newValue = Convert-ToForwardSlashes $ps1Candidate
            $updated.Add("$key=$newValue")
            continue
        }

        if (Test-Path -LiteralPath $ps3Candidate) {
            $newValue = Convert-ToForwardSlashes $ps3Candidate
            $updated.Add("$key=$newValue")
            continue
        }

        if ($value -match "/ps1/") {
            $updated.Add("$key=$ps1DirFwd/$fileName")
            continue
        }

        if ($value -match "/ps3/") {
            $updated.Add("$key=$ps3DirFwd/$fileName")
            continue
        }

        if ($ShouldClean -and $key -match "(LastSelected|ConfigFile\d+)$") {
            Write-Warning "Referencia ausente em '$key'. Limpando valor para evitar caminho quebrado."
            $updated.Add("$key=")
            continue
        }

        Write-Warning "Nao foi possivel inferir o destino de '$key=$value'. Mantido como esta."
        $updated.Add($line)
    }

    Set-Content -LiteralPath $settingsPath -Value $updated -Encoding UTF8
    Write-Host "Portabilidade aplicada com sucesso."
    Write-Host "Settings: $settingsPath"
    Write-Host "Backup:   $backupPath"
}

function Invoke-AuditSettings {
    param([string]$Root)

    $settingsPath = Join-Path $Root "bin\antimicrox_settings.ini"
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Arquivo nao encontrado: $settingsPath"
    }

    $lines = Get-Content -LiteralPath $settingsPath
    $results = New-Object System.Collections.Generic.List[object]

    foreach ($line in $lines) {
        if ($line -notmatch "^(?<key>[^=]+)=(?<value>.*)$") {
            continue
        }

        $key = $matches["key"]
        $value = $matches["value"]

        if ($key -ne "LastProfileDir" -and $key -notmatch "(LastSelected|ConfigFile\d+)$") {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($value)) {
            $results.Add([pscustomobject]@{ Key = $key; Value = $value; Exists = $false; Status = "empty" })
            continue
        }

        $normalized = $value -replace "/", "\\"
        $exists = Test-Path -LiteralPath $normalized
        $results.Add([pscustomobject]@{ Key = $key; Value = $value; Exists = $exists; Status = $(if ($exists) { "ok" } else { "missing" }) })
    }

    $total = $results.Count
    $okCount = ($results | Where-Object { $_.Status -eq "ok" } | Measure-Object).Count
    $missingCount = ($results | Where-Object { $_.Status -eq "missing" } | Measure-Object).Count
    $emptyCount = ($results | Where-Object { $_.Status -eq "empty" } | Measure-Object).Count

    Write-Host "Total de referencias: $total"
    Write-Host "OK: $okCount"
    Write-Host "Missing: $missingCount"
    Write-Host "Empty: $emptyCount"

    if ($missingCount -gt 0 -or $emptyCount -gt 0) {
        Write-Host "`nDetalhes (nao OK):"
        $results | Where-Object { $_.Status -ne "ok" } | Format-Table -AutoSize
    }

    $docDir = Join-Path $Root "docs"
    if (-not (Test-Path -LiteralPath $docDir)) {
        New-Item -Path $docDir -ItemType Directory | Out-Null
    }

    $docPath = Join-Path $docDir "settings-audit.md"
    $date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $nonOkRows = @($results | Where-Object { $_.Status -ne "ok" })

    $markdown = @()
    $markdown += "# Settings Audit"
    $markdown += ""
    $markdown += "Gerado em: $date"
    $markdown += ""
    $markdown += "- Total: $total"
    $markdown += "- OK: $okCount"
    $markdown += "- Missing: $missingCount"
    $markdown += "- Empty: $emptyCount"
    $markdown += ""
    $markdown += "## Referencias nao OK"
    $markdown += ""
    $markdown += "| Key | Status | Value |"
    $markdown += "| --- | --- | --- |"

    foreach ($row in $nonOkRows) {
        $escaped = ($row.Value -replace "\|", "\\|")
        $markdown += "| $($row.Key) | $($row.Status) | $escaped |"
    }

    if ($nonOkRows.Count -eq 0) {
        $markdown += "| - | - | Nenhuma pendencia |"
    }

    Set-Content -LiteralPath $docPath -Value $markdown -Encoding UTF8
    Write-Host "`nRelatorio markdown salvo em: $docPath"
}

function Test-GamepadConnected {
    # 1. Tenta usar Get-PnpDevice (disponivel no Win10/11)
    if (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue) {
        $devices = Get-PnpDevice -Class "Gamepad", "Joystick" -Status "OK" -ErrorAction SilentlyContinue
        if ($devices) {
            return $true
        }
    }
    
    # 2. Alternativa com WMI/CIM pesquisando por termos comuns na PNPClass
    $wmiDevices = Get-CimInstance Win32_PNPEntity -Filter "PNPClass = 'Gamepad' OR PNPClass = 'Joystick'" -ErrorAction SilentlyContinue
    if ($wmiDevices) {
        return $true
    }
    
    # 3. Busca secundaria na classe HID por nomes comuns se as anteriores falharem
    $hidDevices = Get-CimInstance Win32_PNPEntity -Filter "PNPClass = 'HIDClass'" -ErrorAction SilentlyContinue
    if ($hidDevices) {
        $matchingHid = $hidDevices | Where-Object { $_.Name -match "controller|gamepad|joystick|direção|manche|controlador de jogo" }
        if ($matchingHid) {
            return $true
        }
    }

    return $false
}

function Get-AvailableProfiles {
    param([string]$Root)
    $ps1Dir = Join-Path $Root "ps1"
    $ps3Dir = Join-Path $Root "ps3"
    
    $profiles = @()
    if (Test-Path -LiteralPath $ps1Dir) {
        $profiles += Get-ChildItem -LiteralPath $ps1Dir -Filter "*.amgp" | ForEach-Object {
            [pscustomobject]@{ Name = $_.Name; Folder = "ps1" }
        }
    }
    if (Test-Path -LiteralPath $ps3Dir) {
        $profiles += Get-ChildItem -LiteralPath $ps3Dir -Filter "*.amgp" | ForEach-Object {
            [pscustomobject]@{ Name = $_.Name; Folder = "ps3" }
        }
    }
    
    return $profiles
}

function Start-App {
    param([string]$Root, [string]$SelectedTheme, [bool]$UseVanilla)

    $exeName = "asass-mod.exe"
    $exePath = Join-Path $Root ("bin\" + $exeName)
    if (-not (Test-Path -LiteralPath $exePath)) {
        $exeName = "antimicrox.exe"
        $exePath = Join-Path $Root ("bin\" + $exeName)
    }

    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Executavel nao encontrado em bin/: asass-mod.exe ou antimicrox.exe"
    }

    # Alerta se nao houver controle ativo
    if (-not (Test-GamepadConnected)) {
        Write-Warning "Aviso: Nenhum controle ou joystick ativo foi detectado via USB. O AntiMicroX pode abrir sem reconhecer dispositivos de entrada."
    }

    if ($UseVanilla) {
        Write-Host "Abrindo asass mod (modo vanilla)"
        Start-Process -FilePath $exePath
        return
    }

    $themePath = Join-Path $Root ("themes\" + $SelectedTheme)
    if (-not (Test-Path -LiteralPath $themePath)) {
        throw "Tema nao encontrado: $themePath"
    }

    $env:QT_AUTO_SCREEN_SCALE_FACTOR = "1"
    $themePathForward = Convert-ToForwardSlashes $themePath

    Write-Host "Abrindo asass mod com tema: $SelectedTheme"
    Start-Process -FilePath $exePath -ArgumentList @("-style", "Fusion", "-stylesheet", $themePathForward)
}

function Set-ActiveProfile {
    param([string]$Root, [string]$Profile, [bool]$ForceAll)

    if ([string]::IsNullOrWhiteSpace($Profile)) {
        throw "Informe -ProfileName para usar -SetProfile."
    }

    $settingsPath = Join-Path $Root "bin\antimicrox_settings.ini"
    $ps1Candidate = Join-Path $Root ("ps1\" + $Profile)
    $ps3Candidate = Join-Path $Root ("ps3\" + $Profile)

    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Arquivo nao encontrado: $settingsPath"
    }

    $targetProfile = $null
    if (Test-Path -LiteralPath $ps1Candidate) {
        $targetProfile = $ps1Candidate
    }
    elseif (Test-Path -LiteralPath $ps3Candidate) {
        $targetProfile = $ps3Candidate
    }
    else {
        throw "Perfil nao encontrado em ps1/ ou ps3/: $Profile"
    }

    $targetProfileFwd = Convert-ToForwardSlashes $targetProfile
    $targetDirFwd = Convert-ToForwardSlashes (Split-Path -Parent $targetProfile)

    $backupDir = Join-Path $Root "bin\backups"
    if (-not (Test-Path -LiteralPath $backupDir)) {
        New-Item -Path $backupDir -ItemType Directory | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $backupDir ("antimicrox_settings.ini.profile-switch." + $timestamp + ".bak")
    Copy-Item -LiteralPath $settingsPath -Destination $backupPath -Force

    $lines = Get-Content -LiteralPath $settingsPath
    $updated = New-Object System.Collections.Generic.List[string]

    foreach ($line in $lines) {
        if ($line -notmatch "^(?<key>[^=]+)=(?<value>.*)$") {
            $updated.Add($line)
            continue
        }

        $key = $matches["key"]
        $value = $matches["value"]

        if ($key -eq "LastProfileDir") {
            $updated.Add("$key=$targetDirFwd")
            continue
        }

        if ($key -match "LastSelected$") {
            if ($ForceAll -or -not [string]::IsNullOrWhiteSpace($value)) {
                $updated.Add("$key=$targetProfileFwd")
                continue
            }
        }

        if ($key -match "ConfigFile1$") {
            if ($ForceAll -or -not [string]::IsNullOrWhiteSpace($value)) {
                $updated.Add("$key=$targetProfileFwd")
                continue
            }
        }

        $updated.Add($line)
    }

    Set-Content -LiteralPath $settingsPath -Value $updated -Encoding UTF8
    Write-Host "Perfil ativo atualizado para: $Profile"
    Write-Host "Settings: $settingsPath"
    Write-Host "Backup:   $backupPath"
}

function Backup-Pack {
    param([string]$Root)

    $outDir = Join-Path $Root "archives"
    if (-not (Test-Path -LiteralPath $outDir)) {
        New-Item -Path $outDir -ItemType Directory | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $zipPath = Join-Path $outDir ("asass-mod-pack-" + $timestamp + ".zip")

    $includePaths = @(
        (Join-Path $Root "bin\antimicrox_settings.ini"),
        (Join-Path $Root "ps1"),
        (Join-Path $Root "ps3"),
        (Join-Path $Root "themes")
    )

    $validPaths = @($includePaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($validPaths.Count -eq 0) {
        throw "Nenhum caminho valido para backup foi encontrado."
    }

    Compress-Archive -Path $validPaths -DestinationPath $zipPath -CompressionLevel Optimal -Force
    Write-Host "Backup criado com sucesso: $zipPath"
}

function Build-SingleFilePack {
    param([string]$Root)

    $distDir = Join-Path $Root "dist"
    if (-not (Test-Path -LiteralPath $distDir)) {
        New-Item -Path $distDir -ItemType Directory | Out-Null
    }

    $singleFile = Join-Path $distDir "asass-mod-single.zip"

    $includePaths = @(
        (Join-Path $Root "asass-mod.ps1"),
        (Join-Path $Root "asass-mod.cmd"),
        (Join-Path $Root "run.cmd"),
        (Join-Path $Root "README.md"),
        (Join-Path $Root "bin"),
        (Join-Path $Root "ps1"),
        (Join-Path $Root "ps3"),
        (Join-Path $Root "themes")
    )

    $validPaths = @($includePaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($validPaths.Count -eq 0) {
        throw "Nada para empacotar."
    }

    if (Test-Path -LiteralPath $singleFile) {
        Remove-Item -LiteralPath $singleFile -Force
    }

    Compress-Archive -Path $validPaths -DestinationPath $singleFile -CompressionLevel Optimal -Force
    Write-Host "Arquivo unico ZIP gerado: $singleFile"
}

function Build-SingleExePack {
    param([string]$Root)

    $distDir = Join-Path $Root "dist"
    if (-not (Test-Path -LiteralPath $distDir)) {
        New-Item -Path $distDir -ItemType Directory | Out-Null
    }

    $targetExe = Join-Path $distDir "asass-mod.exe"
    $tempZip = Join-Path $distDir "app.zip"
    $tempCs = Join-Path $distDir "bootstrap.cs"

    Write-Host "Preparando arquivos para empacotamento do executavel..." -ForegroundColor Cyan

    $includePaths = @(
        (Join-Path $Root "asass-mod.ps1"),
        (Join-Path $Root "asass-mod.cmd"),
        (Join-Path $Root "run.cmd"),
        (Join-Path $Root "README.md"),
        (Join-Path $Root "bin"),
        (Join-Path $Root "ps1"),
        (Join-Path $Root "ps3"),
        (Join-Path $Root "themes")
    )

    $validPaths = @($includePaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($validPaths.Count -eq 0) {
        throw "Nada para empacotar."
    }

    if (Test-Path -LiteralPath $tempZip) {
        Remove-Item -LiteralPath $tempZip -Force
    }

    Write-Host "Criando arquivo compactado temporario..."
    Compress-Archive -Path $validPaths -DestinationPath $tempZip -CompressionLevel Optimal -Force

    Write-Host "Gerando codigo do compilador bootstrap..."
    $csCode = @"
using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.IO.Compression;

class Program
{
    static void Main(string[] args)
    {
        string tempDir = Path.Combine(Path.GetTempPath(), "asass_mod_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        
        try
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            string resourceName = null;
            foreach (string name in assembly.GetManifestResourceNames())
            {
                if (name.EndsWith("app.zip", StringComparison.OrdinalIgnoreCase))
                {
                    resourceName = name;
                    break;
                }
            }
            
            if (resourceName == null)
            {
                Console.WriteLine("Erro interno: Recurso do aplicativo nao encontrado.");
                return;
            }
            
            string zipPath = Path.Combine(tempDir, "app.zip");
            using (Stream resourceStream = assembly.GetManifestResourceStream(resourceName))
            using (FileStream fileStream = new FileStream(zipPath, FileMode.Create, FileAccess.Write))
            {
                resourceStream.CopyTo(fileStream);
            }
            
            ZipFile.ExtractToDirectory(zipPath, tempDir);
            File.Delete(zipPath);
            
            string scriptPath = Path.Combine(tempDir, "asass-mod.ps1");
            string psArgs = "-ExecutionPolicy Bypass -File \"" + scriptPath + "\"";
            if (args.Length > 0)
            {
                psArgs += " " + string.Join(" ", args);
            }
            
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "powershell.exe";
            psi.Arguments = psArgs;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = false;
            
            using (Process process = Process.Start(psi))
            {
                process.WaitForExit();
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Erro ao inicializar o asass-mod portatil:");
            Console.WriteLine(ex.Message);
            Console.WriteLine("Pressione qualquer tecla para sair...");
            Console.ReadKey();
        }
        finally
        {
            try
            {
                if (Directory.Exists(tempDir))
                {
                    Directory.Delete(tempDir, true);
                }
            }
            catch
            {
                // Ignorar se algum arquivo ainda estiver em uso
            }
        }
    }
}
"@

    Set-Content -LiteralPath $tempCs -Value $csCode -Encoding UTF8

    Write-Host "Compilando executavel unico (SFX)..."
    $cscPath = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if (-not (Test-Path -LiteralPath $cscPath)) {
        throw "Compilador csc.exe nao encontrado em $cscPath."
    }

    $arguments = @(
        "/nologo",
        "/out:$targetExe",
        "/r:System.IO.Compression.FileSystem.dll",
        "/r:System.IO.Compression.dll",
        "/resource:$tempZip",
        $tempCs
    )

    $proc = Start-Process -FilePath $cscPath -ArgumentList $arguments -Wait -NoNewWindow -PassThru
    
    if (Test-Path -LiteralPath $tempZip) { Remove-Item -LiteralPath $tempZip -Force }
    if (Test-Path -LiteralPath $tempCs) { Remove-Item -LiteralPath $tempCs -Force }

    if ($proc.ExitCode -ne 0) {
        throw "Erro durante a compilacao do executavel. Codigo de saida: $($proc.ExitCode)"
    }

    Write-Host "`n[SUCESSO] Executavel portatil unico criado com sucesso!" -ForegroundColor Green
    Write-Host "Arquivo gerado: $targetExe" -ForegroundColor Green
}

function Show-Menu {
    param([string]$Root, [string]$SelectedTheme)

    $hasGamepad = Test-GamepadConnected
    $gamepadStatus = if ($hasGamepad) {
        " [Controle USB: Detectado]"
    } else {
        " [Controle USB: Nao detectado (Reconecte se necessario)]"
    }
    $gamepadColor = if ($hasGamepad) { "Green" } else { "Yellow" }

    Write-Host ""
    Write-Host "=== asass mod :: arquivo unico ==="
    Write-Host -NoNewline "Status:"
    Write-Host $gamepadStatus -ForegroundColor $gamepadColor
    Write-Host ""
    Write-Host "1) Abrir app (tema custom)"
    Write-Host "2) Abrir app (vanilla)"
    Write-Host "3) Setup portatil"
    Write-Host "4) Setup portatil + limpar referencias ausentes"
    Write-Host "5) Auditar settings"
    Write-Host "6) Trocar perfil ativo"
    Write-Host "7) Backup pack (.zip)"
    Write-Host "8) Build arquivo unico (.zip e .exe)"
    Write-Host "9) Sair"
    Write-Host ""

    $choice = Read-Host "Escolha uma opcao"
    switch ($choice) {
        "1" { Start-App -Root $Root -SelectedTheme $SelectedTheme -UseVanilla $false }
        "2" { Start-App -Root $Root -SelectedTheme $SelectedTheme -UseVanilla $true }
        "3" { Invoke-SetupPortable -Root $Root -ShouldClean $false }
        "4" { Invoke-SetupPortable -Root $Root -ShouldClean $true }
        "5" { Invoke-AuditSettings -Root $Root }
        "6" {
            $profiles = Get-AvailableProfiles -Root $Root
            if ($profiles.Count -eq 0) {
                Write-Warning "Nenhum perfil .amgp encontrado em ps1/ ou ps3/."
            }
            else {
                Write-Host "`nPerfis disponiveis:" -ForegroundColor Cyan
                for ($i = 0; $i -lt $profiles.Count; $i++) {
                    $p = $profiles[$i]
                    Write-Host ("{0,2}) [{1}] {2}" -f ($i + 1), $p.Folder, $p.Name)
                }
                Write-Host ""
                $sel = Read-Host "Escolha o numero do perfil para ativar (ou pressione Enter para cancelar)"
                if ([string]::IsNullOrWhiteSpace($sel)) {
                    Write-Host "Troca de perfil cancelada."
                }
                elseif ([int]::TryParse($sel, [ref]$index) -and $index -ge 1 -and $index -le $profiles.Count) {
                    $chosen = $profiles[$index - 1].Name
                    Set-ActiveProfile -Root $Root -Profile $chosen -ForceAll $false
                }
                else {
                    Write-Host "Opcao invalida." -ForegroundColor Yellow
                }
            }
        }
        "7" { Backup-Pack -Root $Root }
        "8" {
            Build-SingleFilePack -Root $Root
            Build-SingleExePack -Root $Root
        }
        default { Write-Host "Saindo." }
    }
}

if ($Menu) {
    Show-Menu -Root $ProjectRoot -SelectedTheme $Theme
    exit 0
}

if ($Setup) {
    Invoke-SetupPortable -Root $ProjectRoot -ShouldClean $CleanMissing
}

if ($Audit) {
    Invoke-AuditSettings -Root $ProjectRoot
}

if ($SetProfile) {
    Set-ActiveProfile -Root $ProjectRoot -Profile $ProfileName -ForceAll $AllControllers
}

if ($Backup) {
    Backup-Pack -Root $ProjectRoot
}

if ($BuildSingle -or $RebuildSingle) {
    Build-SingleFilePack -Root $ProjectRoot
    Build-SingleExePack -Root $ProjectRoot
}

if ($Run -or $Vanilla) {
    Start-App -Root $ProjectRoot -SelectedTheme $Theme -UseVanilla $Vanilla
}

if (-not ($Menu -or $Setup -or $Audit -or $SetProfile -or $Backup -or $BuildSingle -or $RebuildSingle -or $Run -or $Vanilla)) {
    Show-Menu -Root $ProjectRoot -SelectedTheme $Theme
}
