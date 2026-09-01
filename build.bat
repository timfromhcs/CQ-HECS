@echo off
setlocal enabledelayedexpansion

echo =================================================================
echo  CQ-HECS v4.0: Monolithic Unified Binary and Shared Library Build
echo =================================================================

:: Step 1: Compile GLSL Shaders and Embed into Static C++ Headers
echo [1/4] Embedding Compute Shaders into Static C++ Headers...
python scripts\embed_shaders.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to embed shaders into src/shaders_embedded.hpp
    exit /b %ERRORLEVEL%
)
echo [PASS] All shaders embedded cleanly (Zero runtime file dependency).

:: Step 2: Configure CMake Project
echo [2/4] Configuring CMake with MSVC (C++20) and Vulkan SDK...
cmake -B build -G "Visual Studio 17 2022" -A x64 -S .
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed.
    exit /b %ERRORLEVEL%
)

:: Step 3: Build C++ Targets (Standalone Executable & Shared DLL)
echo [3/4] Building C++20 Monolithic Executable and Shared Library (Release)...
cmake --build build --config Release --parallel
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed.
    exit /b %ERRORLEVEL%
)

:: Step 4: Run Embedded Self-Test & Verification
echo [4/4] Running Embedded Self-Test Suite...
.\bin\Release\cq_hecs.exe test
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Embedded self-test failed.
    exit /b %ERRORLEVEL%
)

echo.
echo =================================================================
echo  BUILD AND VERIFICATION SUCCESSFUL!
echo  Artifacts:
echo    Executable: bin/Release/cq_hecs.exe
echo    Library:    bin/Release/cq_hecs.dll
echo    Header:     include/cq_hecs_api.h
echo =================================================================
exit /b 0
