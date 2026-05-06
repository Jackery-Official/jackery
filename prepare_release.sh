#!/bin/bash

# Jackery HACS 发布准备脚本
# 此脚本帮助你准备发布到 HACS 并支持自动创建 GitHub Release

set -e

# 配置路径
COMPONENT_PATH="custom_components/jackery"
MANIFEST_FILE="$COMPONENT_PATH/manifest.json"

echo "🚀 准备发布 Jackery 到 HACS"
echo ""

# 检查是否在正确的目录
if [ ! -f "hacs.json" ]; then
    echo "❌ 错误：未找到 hacs.json 文件"
    echo "请确保在项目根目录运行此脚本"
    exit 1
fi

# 检查 manifest 文件是否存在
if [ ! -f "$MANIFEST_FILE" ]; then
     echo "❌ 错误：未找到 $MANIFEST_FILE"
     echo "请确认文件路径是否正确"
     exit 1
fi

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  检测到未提交的更改"
    echo ""
    git status --short
    echo ""
    read -p "是否要提交这些更改？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "请输入提交信息: " commit_msg
        git add .
        git commit -m "$commit_msg"
        echo "✅ 更改已提交"
    else
        echo "❌ 请先提交或暂存你的更改"
        exit 1
    fi
fi

# 获取当前版本
if [ -f "$MANIFEST_FILE" ]; then
    CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$MANIFEST_FILE'))['version'])")
else
    echo "❌ 无法读取文件: $MANIFEST_FILE"
    exit 1
fi

echo "📦 当前版本: $CURRENT_VERSION"
echo ""

# 询问新版本
read -p "请输入新版本号 (当前: $CURRENT_VERSION): " NEW_VERSION

if [ -z "$NEW_VERSION" ]; then
    NEW_VERSION=$CURRENT_VERSION
    echo "使用当前版本: $NEW_VERSION"
fi

# 更新 manifest.json 中的版本号
if [ "$NEW_VERSION" != "$CURRENT_VERSION" ]; then
    echo "📝 更新 manifest.json 中的版本号..."
    # 使用正则匹配替换，更稳健
    sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$MANIFEST_FILE"
    rm "$MANIFEST_FILE.bak"
    
    git add "$MANIFEST_FILE"
    
    # 仅在有变更时提交
    if ! git diff-index --quiet HEAD --; then
        git commit -m "版本更新至 v$NEW_VERSION"
        echo "✅ 版本号已更新"
    else
        echo "⚠️  版本号未发生实际变化或无法提交"
    fi
fi

# 推送到 GitHub
echo ""
echo "📤 推送到 GitHub..."
git push origin main

# 处理 Tag
TAG_NAME="v$NEW_VERSION"

# 检查本地 tag 是否存在
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo "⚠️  Tag $TAG_NAME 本地已存在"
    read -p "是否删除旧 Tag 并重新创建? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d "$TAG_NAME"
        # 尝试删除远程 tag (如果存在)
        git push origin :refs/tags/"$TAG_NAME" 2>/dev/null || true
        echo "🗑️  旧 Tag 已清除"
    else
        echo "❌ 停止发布：Tag 已存在且未选择覆盖"
        exit 1
    fi
fi

echo ""
echo "🏷️  创建 Git tag: $TAG_NAME"
git tag -a "$TAG_NAME" -m "Release $TAG_NAME"
git push origin "$TAG_NAME"

echo ""
echo "✅ 代码和 Tag 推送完成！"
echo ""

# GitHub Release 自动化
RELEASE_CREATED=false

if command -v gh &> /dev/null; then
    echo "🤖 检测到 GitHub CLI (gh)"
    read -p "是否使用 gh 立即创建 GitHub Release? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        
        RELEASE_TITLE="$TAG_NAME"
        read -p "请输入 Release 标题 (默认: $TAG_NAME): " input_title
        if [ -n "$input_title" ]; then
            RELEASE_TITLE="$input_title"
        fi

        echo "您可以选择 Release Notes 来源:"
        echo "1) 自动生成 (gh --generate-notes)"
        echo "2) 使用简单的 'Release v...'"
        echo "3) 取消自动发布"
        read -p "请选择 (1/2/3, 默认 1): " note_choice
        note_choice=${note_choice:-1}

        case $note_choice in
            1)
                echo "⏳ 正在创建 Release (自动生成日志)..."
                if gh release create "$TAG_NAME" --title "$RELEASE_TITLE" --generate-notes; then
                    RELEASE_CREATED=true
                fi
                ;;
            2)
                echo "⏳ 正在创建 Release..."
                if gh release create "$TAG_NAME" --title "$RELEASE_TITLE" --notes "Release $TAG_NAME"; then
                    RELEASE_CREATED=true
                fi
                ;;
            *)
                echo "已取消 gh 发布。"
                ;;
        esac

        if [ "$RELEASE_CREATED" = true ]; then
             echo "🎉 GitHub Release 创建成功！"
             # 尝试获取 release url
             gh release view "$TAG_NAME" --json url --template '{{.url}}' || echo ""
             echo ""
        fi
    fi
fi

if [ "$RELEASE_CREATED" = false ]; then
    echo "📋 下一步操作 (手动发布):"
    echo "1. 访问 GitHub 创建 Release:"
    echo "   https://github.com/ht-it-lab/jackery/releases/new?tag=$TAG_NAME"
    echo ""
    echo "2. 如果尚未安装，推荐安装 GitHub CLI (gh) 以便下次自动发布。"
fi

echo "✅ 流程结束"