#!/usr/bin/env pwsh
Set-Location -Path $PSScriptRoot
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue bin
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue obj
dotnet restore
dotnet build -c Release
dotnet publish -c Release
