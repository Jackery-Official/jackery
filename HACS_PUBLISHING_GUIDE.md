# HACS 发布指南

本指南将帮助您将 JackeryHome 集成发布到 HACS (Home Assistant Community Store)。

## 发布前检查清单

### 1. 项目结构检查
确保项目结构符合 HACS 要求：
```
jackery_home/
├── hacs.json                          # HACS 配置文件
├── README.md                          # 项目主文档
├── LICENSE                            # 许可证文件
└── custom_components/
    └── JackeryHome/
        ├── __init__.py                # 集成入口
        ├── manifest.json              # 集成元数据
        ├── config_flow.py             # 配置流程
        ├── sensor.py                  # 传感器实现
        ├── strings.json               # 本地化字符串
        ├── translations/              # 翻译文件
        │   └── zh-Hans.json
        └── README.md                  # 集成技术文档
```

### 2. 配置文件检查

#### hacs.json
```json
{
    "name": "JackeryHome",
    "content_in_root": false,
    "render_readme": true,
    "domains": [
        "jackery_home"
    ],
    "iot_class": "Local Push",
    "homeassistant": "2024.1.0"
}
```

#### manifest.json
```json
{
    "domain": "jackery_home",
    "name": "JackeryHome",
    "codeowners": [
        "@suyulin"
    ],
    "config_flow": true,
    "dependencies": [
        "mqtt"
    ],
    "documentation": "https://github.com/suyulin/jackery_home",
    "issue_tracker": "https://github.com/suyulin/jackery_home/issues",
    "iot_class": "local_push",
    "requirements": [
        "paho-mqtt>=1.6.0"
    ],
    "version": "1.0.0"
}
```

### 3. 代码质量检查
- [ ] 所有 Python 文件符合 PEP 8 规范
- [ ] 没有语法错误
- [ ] 所有导入都正确
- [ ] 日志记录适当
- [ ] 错误处理完善

## 发布步骤

### 步骤 1: 准备发布
使用提供的发布脚本：
```bash
./prepare_release.sh
```

或手动执行以下步骤：

1. **检查未提交的更改**
   ```bash
   git status
   ```

2. **提交所有更改**
   ```bash
   git add .
   git commit -m "准备发布到 HACS"
   ```

3. **更新版本号**
   编辑 `custom_components/JackeryHome/manifest.json` 中的版本号

4. **提交版本更新**
   ```bash
   git add custom_components/JackeryHome/manifest.json
   git commit -m "版本更新至 v1.0.0"
   ```

### 步骤 2: 推送到 GitHub
```bash
git push origin main
```

### 步骤 3: 创建 Git Tag
```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### 步骤 4: 创建 GitHub Release

#### 方法一：使用 GitHub Web 界面
1. 访问 GitHub 仓库
2. 点击 "Releases" → "Create a new release"
3. 选择刚创建的 tag (v1.0.0)
4. 填写 Release 标题和描述
5. 点击 "Publish release"

#### 方法二：使用 GitHub CLI
```bash
gh release create v1.0.0 --title "v1.0.0" --notes "JackeryHome 集成首次发布"
```

### 步骤 5: 验证发布
1. 检查 GitHub Release 是否创建成功
2. 验证下载链接是否正常
3. 测试从 HACS 安装是否正常

## 用户安装指南

### 通过 HACS 安装
1. **添加自定义存储库**
   - 打开 HACS
   - 点击右上角三个点 → "自定义存储库"
   - 添加仓库 URL：`https://github.com/suyulin/jackery_home`
   - 类别选择：`Integration`
   - 点击"添加"

2. **安装集成**
   - 在 HACS 中搜索 "JackeryHome"
   - 点击"安装"
   - 重启 Home Assistant

3. **配置集成**
   - 进入 **设置** → **设备与服务** → **添加集成**
   - 搜索 "JackeryHome"
   - 按照配置向导完成设置

## 常见问题

### Q: HACS 中找不到我的集成？
A: 检查以下几点：
- 确保 `hacs.json` 文件存在且格式正确
- 确保 `manifest.json` 中的 `domain` 与 `hacs.json` 中的 `domains` 匹配
- 确保 GitHub Release 已创建
- 等待 HACS 缓存更新（通常需要几分钟）

### Q: 安装后集成无法加载？
A: 检查以下几点：
- 查看 Home Assistant 日志中的错误信息
- 确保所有依赖项已安装
- 检查 `manifest.json` 中的 `requirements` 字段
- 确保代码没有语法错误

### Q: 如何更新集成？
A: 更新流程：
1. 修改代码
2. 更新 `manifest.json` 中的版本号
3. 提交更改并推送到 GitHub
4. 创建新的 Git tag 和 Release
5. 用户在 HACS 中会看到更新通知

## 最佳实践

1. **版本管理**
   - 使用语义化版本控制 (SemVer)
   - 每次发布都要更新版本号
   - 在 Release 中详细描述更改内容

2. **文档维护**
   - 保持 README.md 更新
   - 提供清晰的安装和使用说明
   - 包含故障排除指南

3. **代码质量**
   - 定期检查代码质量
   - 添加适当的错误处理
   - 使用类型提示

4. **用户支持**
   - 及时回复 Issues
   - 提供清晰的错误信息
   - 保持文档更新

## 相关链接

- [HACS 官方文档](https://hacs.xyz/)
- [Home Assistant 开发文档](https://developers.home-assistant.io/)
- [HACS 集成要求](https://hacs.xyz/docs/publish/requirements)
- [GitHub Actions 示例](https://github.com/hacs/integration/tree/main/.github/workflows)
