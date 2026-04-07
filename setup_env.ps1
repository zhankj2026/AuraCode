# Claude Code Python MVP - 快速配置脚本
# 使用方法: .\setup_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Claude Code Python MVP - 环境配置" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 API Key
$apiKey = $env:OPENAI_API_KEY
$baseUrl = $env:OPENAI_BASE_URL

if (-not $apiKey) {
    Write-Host "❌ 未检测到 OPENAI_API_KEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "请输入你的 GLM API Key:" -ForegroundColor Yellow
    Write-Host "获取地址: https://open.bigmodel.cn/" -ForegroundColor Yellow
    $newKey = Read-Host "API Key"
    
    if ($newKey) {
        $env:OPENAI_API_KEY = $newKey
        Write-Host "✅ 已设置 OPENAI_API_KEY (仅当前会话)" -ForegroundColor Green
    }
} else {
    Write-Host "✅ 检测到 OPENAI_API_KEY: $($apiKey.Substring(0, 10))..." -ForegroundColor Green
}

if (-not $baseUrl) {
    Write-Host ""
    Write-Host "❌ 未检测到 OPENAI_BASE_URL" -ForegroundColor Red
    Write-Host ""
    Write-Host "选择 API 提供商:" -ForegroundColor Yellow
    Write-Host "  1. 智谱 GLM (推荐)" -ForegroundColor White
    Write-Host "  2. OpenAI" -ForegroundColor White
    Write-Host "  3. 自定义" -ForegroundColor White
    
    $choice = Read-Host "选择 (1/2/3)"
    
    switch ($choice) {
        "1" {
            $env:OPENAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
            Write-Host "✅ 已设置 OPENAI_BASE_URL (智谱 GLM)" -ForegroundColor Green
        }
        "2" {
            $env:OPENAI_BASE_URL = "https://api.openai.com/v1"
            Write-Host "✅ 已设置 OPENAI_BASE_URL (OpenAI)" -ForegroundColor Green
        }
        "3" {
            $customUrl = Read-Host "输入 Base URL"
            $env:OPENAI_BASE_URL = $customUrl
            Write-Host "✅ 已设置 OPENAI_BASE_URL" -ForegroundColor Green
        }
    }
} else {
    Write-Host "✅ 检测到 OPENAI_BASE_URL: $baseUrl" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "配置完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "当前配置:" -ForegroundColor Yellow
Write-Host "  Model: glm-4-plus" -ForegroundColor White
Write-Host "  Base URL: $env:OPENAI_BASE_URL" -ForegroundColor White
Write-Host ""
Write-Host "测试命令:" -ForegroundColor Yellow
Write-Host '  python cli.py --model glm-4-plus "你好"' -ForegroundColor White
Write-Host ""

# 询问是否测试
$test = Read-Host "是否立即测试? (y/n)"
if ($test -eq "y") {
    Write-Host ""
    Write-Host "正在测试..." -ForegroundColor Cyan
    python cli.py --model glm-4-plus "你好,请介绍一下自己"
}
