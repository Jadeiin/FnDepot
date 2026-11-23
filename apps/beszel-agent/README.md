# Beszel Agent

在飞牛 fnOS 上以专用包用户运行的 NAS 监控代理，支持 x86_64 和 ARM64。监控数据在 Beszel Hub 中查看。Docker 容器指标取决于包用户对 Docker API 的读取权限。 [Beszel Agent 文档](https://beszel.dev/zh/guide/agent-installation)

## 安装

1. 在 Beszel Hub 中打开「添加系统」，复制公钥。使用 WebSocket 时，同时准备 Hub 地址和 Token。
2. 在飞牛应用中心手动安装与 NAS 架构对应的 FPK，按向导选择连接方式。

| 连接方式 | 向导填写方式 |
| --- | --- |
| WebSocket | 填写 Hub 公钥、地址和 Token，SSH 监听端口留空。 |
| SSH | 填写 Hub 公钥和监听端口（例如 `45876`），Hub 地址和 Token 留空。在 Hub 的「添加系统」中填写 NAS 的 IP 和相同端口。 |
| WebSocket 加 SSH 备用 | 四项都填写。Hub 可以在 WebSocket 断开时尝试经 SSH 直连。 |

回到 Hub 保存系统并确认设备上线。使用通用 Token 时，Agent 可以自动注册。 [Beszel 快速入门](https://beszel.dev/zh/guide/getting-started)

连接参数可在飞牛应用设置中修改，重启应用后生效。Agent 指纹和 `service.log` 保存在 `TRIM_PKGVAR`。

## 来源

[上游发布](https://github.com/henrygd/beszel/releases) · [图标](https://github.com/henrygd/beszel/blob/v0.21.2/internal/site/public/static/icon.png) · [YunoHost Beszel](https://github.com/YunoHost-Apps/beszel_ynh) · [Komari Agent FPK](https://github.com/shuangji66/buildbot/tree/main/fnpack/Komari-Agent)
