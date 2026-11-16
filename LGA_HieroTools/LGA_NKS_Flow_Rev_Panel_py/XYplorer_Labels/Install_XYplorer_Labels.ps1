<#
____________________________________________________________________

  Install_XYplorer_Labels v1.00 | Lega

  Instala en el XYplorer de esta maquina los labels que usa Flow Pull para
  pintar las carpetas de shot segun el estado de Flow (Corrections, Rev_Sup,
  Rev_Lega, Rev Hold, ReviewDir, Approved), y un Color Filter por label para
  que se pinte la fila entera.

  - Solo AGREGA lo que falta: no toca labels ni filtros existentes.
  - Los labels nuevos van al FINAL de la lista: tag.dat guarda el label de
    cada archivo por su posicion, asi que reordenar cambiaria los colores
    de lo que ya esta etiquetado.
  - Antes de escribir, copia tag.dat y XYplorer.ini con un sufijo de fecha.
  - XYplorer tiene que estar cerrado: al salir reescribe los dos archivos.

  v1.00: Primera version.
____________________________________________________________________
#>

param(
    # Carpeta de datos de XYplorer (donde estan XYplorer.ini y tag.dat).
    # Si no se pasa, se busca sola.
    [string]$DataDir = "",
    # Solo para pruebas sobre una copia de los archivos con XYplorer abierto
    [switch]$NoProcessCheck
)

$ErrorActionPreference = "Stop"

# Nombre | color de texto | color de fondo (los mismos de la PC de Lega)
$Labels = @(
    @("Approved",    "FFFFFF", "257A10"),
    @("ReviewDir",   "FFFFFF", "98C054"),
    @("Corrections", "FFFFFF", "2E77D4"),
    @("Rev_Sup",     "FFFFFF", "A3557E"),
    @("Rev_Lega",    "FFFFFF", "69135E"),
    @("Rev Hold",    "FFFFFF", "FF8000")
)

# Labels de fabrica de XYplorer, por si hay que crear tag.dat desde cero
$DefaultLabels = "Red|000000|FC7268;Orange|000000|F6AB46;Yellow|000000|EFDC4A;Green|000000|B5D74A;Blue|000000|5DA4FE;Purple|000000|E29CDC;Grey|000000|B5B5B5"

$Unicode = New-Object System.Text.UnicodeEncoding($false, $true)  # UTF-16 LE con BOM

function Read-XYText([string]$path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        return @{ Text = [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2); Enc = $Unicode }
    }
    return @{ Text = [System.Text.Encoding]::Default.GetString($bytes); Enc = [System.Text.Encoding]::Default }
}

function Write-XYText([string]$path, [string]$text, $enc) {
    [System.IO.File]::WriteAllText($path, $text, $enc)
}

function Find-DataDir {
    $candidates = @()
    foreach ($exeDir in @("$env:ProgramFiles\XYplorer", "${env:ProgramFiles(x86)}\XYplorer")) {
        $startup = Join-Path $exeDir "Startup.ini"
        if (Test-Path -LiteralPath $startup) {
            $line = (Get-Content -LiteralPath $startup | Where-Object { $_ -match '^\s*Path\s*=' } | Select-Object -First 1)
            if ($line) {
                $p = [Environment]::ExpandEnvironmentVariables(($line -split '=', 2)[1].Trim())
                if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $exeDir $p }
                $candidates += $p
            }
        }
        $candidates += $exeDir
    }
    $candidates += (Join-Path $env:APPDATA "XYplorer64")
    $candidates += (Join-Path $env:APPDATA "XYplorer")
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $c "XYplorer.ini")) { return $c }
    }
    return ""
}

Write-Host ""
Write-Host "XYplorer labels for Flow Pull"
Write-Host "-----------------------------"

if (-not $NoProcessCheck -and (Get-Process -Name "XYplorer*" -ErrorAction SilentlyContinue)) {
    Write-Host "XYplorer is open. Close it and run this again." -ForegroundColor Yellow
    exit 1
}

if (-not $DataDir) { $DataDir = Find-DataDir }
if (-not $DataDir -or -not (Test-Path -LiteralPath (Join-Path $DataDir "XYplorer.ini"))) {
    Write-Host "Could not find the XYplorer settings folder (XYplorer.ini)." -ForegroundColor Red
    Write-Host "Run it again passing the folder: Install_XYplorer_Labels.bat ""C:\path\to\XYplorer data"""
    exit 1
}
Write-Host "Settings folder: $DataDir"

$iniPath = Join-Path $DataDir "XYplorer.ini"
$iniCustom = (Get-Content -LiteralPath $iniPath | Where-Object { $_ -match '^TagDatCustom=' } | Select-Object -First 1)
$tagPath = Join-Path $DataDir "tag.dat"
if ($iniCustom) {
    $custom = ($iniCustom -split '=', 2)[1].Trim()
    if ($custom) {
        $custom = [Environment]::ExpandEnvironmentVariables($custom.Replace("<xydata>", $DataDir))
        if (-not [System.IO.Path]::IsPathRooted($custom)) { $custom = Join-Path $DataDir $custom }
        $tagPath = $custom
    }
}

# Copias de seguridad
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item -LiteralPath $iniPath -Destination "$iniPath.bak_$stamp"
if (Test-Path -LiteralPath $tagPath) { Copy-Item -LiteralPath $tagPath -Destination "$tagPath.bak_$stamp" }
Write-Host "Backups saved with suffix .bak_$stamp"

# ---------------------------------------------------------------- tag.dat
if (Test-Path -LiteralPath $tagPath) {
    $tag = Read-XYText $tagPath
    $nl = if ($tag.Text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines = [System.Collections.Generic.List[string]]($tag.Text -split "\r?\n")
    $idx = $lines.IndexOf("Labels:")
    if ($idx -lt 0) {
        # Cabecera sin bloque de labels: se agrega despues de la primera linea
        $lines.Insert(1, "")
        $lines.Insert(2, "Labels:")
        $lines.Insert(3, $DefaultLabels)
        $idx = 2
    }
    $current = $lines[$idx + 1]
    $names = @($current -split ';' | ForEach-Object { ($_ -split '\|')[0].Trim().ToLower() })
    $added = @()
    foreach ($l in $Labels) {
        if ($names -notcontains $l[0].ToLower()) {
            $current = $current.TrimEnd(';') + ";" + ($l -join '|')
            $added += $l[0]
        }
    }
    if ($added.Count) {
        $lines[$idx + 1] = $current
        Write-XYText $tagPath ($lines -join $nl) $tag.Enc
        Write-Host "Labels added: $($added -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "Labels: all already defined."
    }
} else {
    $all = $DefaultLabels + ";" + (($Labels | ForEach-Object { $_ -join '|' }) -join ';')
    $extra = (1..16 | ForEach-Object { "|0|0|0|||||" }) -join "`r`n"
    $text = "XYplorer File Tags v5`r`n`r`nLabels:`r`n$all`r`n`r`nExtra Tags:`r`n$extra`r`n`r`nStorage: 0 (Absolute paths)`r`n`r`nData:`r`n"
    Write-XYText $tagPath $text $Unicode
    Write-Host "tag.dat created with the labels." -ForegroundColor Green
}

# ---------------------------------------------------------- Color filters
$ini = Read-XYText $iniPath
$nl = if ($ini.Text.Contains("`r`n")) { "`r`n" } else { "`n" }
$lines = [System.Collections.Generic.List[string]]($ini.Text -split "\r?\n")
$sec = $lines.IndexOf("[ColorFilter]")
$existing = @()
if ($sec -lt 0) {
    $lines.Add("")
    $lines.Add("[ColorFilter]")
    $lines.Add("Count=0")
    $sec = $lines.Count - 2
}
# Entradas actuales de la seccion (hasta la proxima seccion)
$end = $sec + 1
while ($end -lt $lines.Count -and -not $lines[$end].StartsWith("[")) {
    if ($lines[$end] -match '^\d+=(.*)$') { $existing += $Matches[1] }
    $end++
}
$new = @()
foreach ($l in $Labels) {
    $already = $existing | Where-Object { $_ -like "*#label:$($l[0])>*" }
    if (-not $already) { $new += "+t:prop:#label:$($l[0])>$($l[1]),$($l[2])" }
}
if ($new.Count) {
    # Los filtros de label van primero, como en la PC de Lega
    $all = @($new) + @($existing)
    $block = @("Count=$($all.Count)")
    for ($i = 0; $i -lt $all.Count; $i++) { $block += "$($i + 1)=$($all[$i])" }
    # Se conserva la linea en blanco que separa de la seccion siguiente
    $tail = @()
    $j = $end - 1
    while ($j -gt $sec -and $lines[$j] -eq "") { $tail += ""; $j-- }
    $lines.RemoveRange($sec + 1, $end - $sec - 1)
    $lines.InsertRange($sec + 1, [string[]]($block + $tail))
    Write-XYText $iniPath ($lines -join $nl) $ini.Enc
    Write-Host "Color filters added: $($new.Count)" -ForegroundColor Green
} else {
    Write-Host "Color filters: all already defined."
}

Write-Host ""
Write-Host "Done. Open XYplorer and run Flow Pull again." -ForegroundColor Green
exit 0
