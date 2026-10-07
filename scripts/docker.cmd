@echo off
setlocal
where docker >nul 2>&1
if not errorlevel 1 goto docker_on_path

set "DOCKER_BIN=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe"
if not exist "%DOCKER_BIN%" (
    echo Docker Desktop CLI was not found. 1>&2
    exit /b 1
)
"%DOCKER_BIN%" %*
exit /b %errorlevel%

:docker_on_path
docker %*
exit /b %errorlevel%
