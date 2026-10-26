# Download the four NIST inputs; run from Windows PowerShell when WSL TLS fails.
$matrixDownloads = @(@('bcsstruc2','bcsstk17'), @('chemwest','west0479'),
                     @('sherman','sherman3'), @('saylor','saylr4'))
$dataDirectory = Join-Path $PSScriptRoot 'data'
New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null
foreach ($entry in $matrixDownloads) {
    $url = 'https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/' + $entry[0] + '/' + $entry[1] + '.mtx.gz'
    $outputPath = Join-Path $dataDirectory ('nist-' + $entry[1] + '.mtx.gz')
    & curl.exe --fail --location --retry 2 --max-time 60 $url --output $outputPath
    if ($LASTEXITCODE -ne 0) { throw ('Download failed: ' + $entry[1]) }
}
