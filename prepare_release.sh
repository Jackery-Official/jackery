#!/bin/bash

# JackeryHome HACS 发布准备脚本
# 此脚本帮助你准备发布到 HACS

set -e

echo "🚀 准备发布 JackeryHome 到 HACS"
echo ""

# 检查是否在正确的目录
if [ ! -f "hacs.json" ]; then
    echo "❌ 错误：未找到 hacs.json 文件"
    echo "请确保在项目根目录运行此脚本"
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
CURRENT_VERSION=$(grep -o '"version": "[^"]*"' custom_components/jackery_home/manifest.json | cut -d'"' -f4)
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
    sed -i.bak "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" custom_components/jackery_home/manifest.json
    rm custom_components/jackery_home/manifest.json.bak
    git add custom_components/jackery_home/manifest.json
    git commit -m "版本更新至 v$NEW_VERSION"
    echo "✅ 版本号已更新"
fi

# 推送到 GitHub
echo ""
echo "📤 推送到 GitHub..."
git push origin main

# 创建 tag
TAG_NAME="v$NEW_VERSION"
echo ""
echo "🏷️  创建 Git tag: $TAG_NAME"
git tag -a "$TAG_NAME" -m "Release $TAG_NAME"
git push origin "$TAG_NAME"

echo ""
echo "✅ 准备完成！"
echo ""
echo "📋 下一步操作："
echo "1. 访问 GitHub 创建 Release:"
echo "   https://github.com/suyulin/jackery_home/releases/new?tag=$TAG_NAME"
echo ""
echo "2. 或者使用以下命令创建 Release (需要 gh CLI):"
echo "   gh release create $TAG_NAME --title \"$TAG_NAME\" --notes \"Release $TAG_NAME\""
echo ""
echo "3. 用户可以通过以下方式添加到 HACS:"
echo "   - 在 HACS 中添加自定义存储库"
echo "   - URL: https://github.com/suyulin/jackery_home"
echo "   - 类别: Integration"
echo ""
echo "4. 查看完整发布指南:"
echo "   cat HACS_PUBLISHING_GUIDE.md"
echo ""

