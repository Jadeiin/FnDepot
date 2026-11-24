# Stump

支持 OPDS 的漫画和电子书阅读服务器。安装后从飞牛桌面打开 Stump，或访问 `http://NAS-IP:10801/`，在首次设置中创建管理员账号。给 Stump 授权书库目录后，在 Web 界面用 NAS 上的绝对路径添加书库。 [上游使用文档](https://www.stumpapp.dev/docs)

服务以 `stump` 包用户运行，使用系统的 OpenSSL 3 运行库。配置 `Stump.toml`、SQLite 数据库 `stump.db`、封面和缓存保存在 `TRIM_PKGVAR/config`，覆盖升级时保留。启停日志见 `TRIM_PKGVAR/service.log`。 [上游配置文档](https://www.stumpapp.dev/docs/guides/configuration/server-config)

FPK 包含 Stump 的原生服务器、Web 前端和 PDFium 渲染库。PDFium 固定在 Stump v0.1.14 使用的 `chromium/7763`。 [上游发布](https://github.com/stumpapp/stump/releases/tag/v0.1.14) · [PDFium 版本来源](https://github.com/stumpapp/stump/blob/v0.1.14/docker/Dockerfile) · [图标来源](https://github.com/stumpapp/stump/blob/v0.1.14/apps/desktop/src-tauri/icons/128x128%402x.png)
