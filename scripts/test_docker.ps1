$ErrorActionPreference = "Stop"

$RootDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ImageName = "hermes-test-runtime"

Push-Location $RootDirectory

try {
    Write-Host "[Hermes] Building the isolated test runtime..."
    docker build --tag $ImageName .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker image build failed with exit code $LASTEXITCODE."
    }

    Write-Host "[Hermes] Running the complete test suite with the repository read-only..."
    docker run --rm `
        --mount "type=bind,source=$RootDirectory,target=/app,readonly" `
        --workdir /app `
        --entrypoint sh `
        $ImageName `
        -c 'uv pip install --system pytest pytest-cov && pytest -q -o addopts="" -p no:cacheprovider'
    if ($LASTEXITCODE -ne 0) {
        throw "Hermes tests failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
