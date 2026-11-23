# FnDepot

FnDepot 是飞牛 fnOS 原生 FPK 的打包与维护仓库。每个应用独立定义上游资产、目标架构和运行方式，共用版本跟踪、打包校验和发布流程。应用直接在 fnOS 上以专用包用户运行，无需 Docker。

## 当前应用

| 应用 | 应用 ID | 支持架构 | Web 端口 |
| --- | --- | --- | --- |
| [slskd](apps/slskd/README.md) | `slskd` | x86_64、ARM64 | `5030` |
| [Kavita](apps/kavita/README.md) | `kavita-native` | x86_64、ARM64 | `5000` |

## 本地打包

用 Python 3.9+。构建脚本会固定并校验 `fnpack` 1.3.3，在 Linux x86_64 和 macOS ARM64 上自动下载。其他构建主机可通过 `--fnpack /path/to/fnpack` 提供对应版本。产物和校验清单默认保存到 `dist/<应用目录名>-v<上游版本>/`。 [fnpack 官方文档](https://developer.fnnas.com/docs/cli/fnpack/)

```sh
python3 scripts/fpk.py list
app=slskd
plan=$(mktemp)
python3 scripts/fpk.py resolve "$app" > "$plan" && python3 scripts/fpk.py build "$plan"
rm -f "$plan"
```

`resolve` 默认取 GitHub 的最新稳定 Release。用 `--tag` 可指定完整的上游 Tag。`build` 默认构建应用声明的所有架构，也可用 `--arch x86` 或 `--arch arm` 选择其中一个。`resolve --metadata` 和 `build --asset-dir` 可以复用已下载的 Release JSON 和产物，构建仍校验每个资产的大小和 SHA-256。

## 自动跟版

工作流从 `apps/*/app.json` 生成构建矩阵，每天检查已登记的上游。相关变更推送到 `main` 时也会触发。手动运行时可以输入应用目录名，默认 `all`。指定上游 Tag 时需要选择单个应用。默认以调试模式打包，将 FPK 和 `SHA256SUMS` 上传为保留 14 天的 Actions Artifact。定时任务会复用同一提交、同一上游资产的有效 Artifact。 [GitHub Actions 工作流](.github/workflows/fpk.yml)

签名发布需要 fnOS 开发者的 PEM 私钥和证书。将两者分别设置为仓库 Actions Secrets `FNPACK_SIGNING_KEY`、`FNPACK_SIGNING_CERT`，然后在手动运行时开启 `publish`，或设置仓库变量 `FNPACK_PUBLISH=true` 启用定时发布。每个应用的上游版本对应一个 GitHub Release，标签为 `<应用目录名>-v<上游版本>`。已有正式 Release 会跳过，草稿可以在重跑时补齐。也可在本地 `build` 时传入 `--key` 和 `--cert`。

## 在 Moo 中订阅

1. 将仓库推送到 GitHub，配置签名 Secrets，开启 `publish` 运行一次打包工作流。工作流发布签名 FPK 后，将默认分支根目录的 [fnpack.json](fnpack.json) 更新为 V2 应用源。工作流需要有权限向默认分支推送索引提交。
2. 在 Moo 的应用源设置中添加这个 GitHub 仓库地址，或直接粘贴默认分支下 `fnpack.json` 的 Raw 链接。首次发布前索引为空。 [Moo 应用源协议](https://github.com/Blue-Mink/moo/blob/v0.6.566/docs/Moo%E5%BA%94%E7%94%A8%E6%BA%90%E5%8D%8F%E8%AE%AE.md)
3. 源同步后，在 Moo 中查看可用更新。已安装应用按 FPK 的 `appname` 和包内版本匹配。例如 Kavita 使用应用 ID `kavita-native`，上游 `v0.9.1.4` 对应包内版本 `0.9.1004`。

索引从仓库的正式 Release 读取各架构包的下载地址、SHA-256 和字节大小。重跑发布工作流也会同步已有 Release。启用 `FNPACK_PUBLISH=true` 后，定时任务会跟进各应用的稳定上游版本并刷新索引。

## 添加应用

1. 在 `apps/<名称>/` 新建 `app.json`，填写 GitHub 上游仓库、稳定且唯一的 `package_id`、应用信息、Web 端口和 Linux 可执行文件名。`assets` 按 `x86` 或 `arm` 声明可用的 ZIP 或 TAR.GZ 文件名，可用 `{tag}` 引用完整 Tag，用 `{version}` 引用去掉 `v` 前缀的版本。四段版本的上游设 `version_parts` 为 `4`，包内版本按 `major.minor.(patch * 1000 + revision)` 转成三段。`categories` 可选，默认是 `["系统工具"]`。 [应用配置示例](apps/slskd/app.json) · [FnDepot V2 分类](https://github.com/EWEDLCM/FnDepot/blob/main/README.md#42-固定分类)
2. 放入 `service.sh`、`icon-64.png`、`icon-256.png`。`service.sh` 设置 `binary` 并定义 `start_service`，用共享的 `launch` 启动原生程序。需要向导或自定义生命周期回调时，按 fnOS 文件名放到应用目录的 `wizard/` 或 `cmd/`。 [运行适配示例](apps/slskd/service.sh) · [共享生命周期脚本](packaging/main)
3. 用 `python3 scripts/fpk.py list` 确认应用已发现，按本地打包流程生成 FPK，再到测试设备验证安装和升级。可添加 `README.md` 作为 Moo 应用详情页的安装说明。

## 安装验证

在测试设备上用飞牛应用中心手动安装与设备匹配的架构。默认产物是 `fnpack --nosign` 生成的本地调试包。 [飞牛测试应用文档](https://developer.fnnas.com/docs/quick-started/test-application/)

共享启动脚本将日志写到各应用的 `TRIM_PKGVAR/service.log`。测试时检查启停和覆盖升级后数据是否保留。应用专属配置见收录列表中的安装说明。

## 来源

打包保留上游归档中的许可文件，并在 `UPSTREAM.txt` 记录源码、二进制资产和 SHA-256。图标来源见各应用说明。
