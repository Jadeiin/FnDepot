# slskd

带 Web 界面的 Soulseek 客户端。安装时填写 Web 和 Soulseek 登录信息，修改后重启应用以重新读取。Web 入口是 `http://NAS-IP:5030/`，默认 Soulseek 入站端口为 TCP `50300`。 [上游发布](https://github.com/slskd/slskd/releases)

安装向导将登录信息保存到 `TRIM_PKGETC/credentials`，`TRIM_PKGVAR` 保存 `slskd.yml` 和下载数据。使用 NAS 共享目录时先在应用设置授权，再按上游文档配置 `slskd.yml`。 [上游配置](https://github.com/slskd/slskd/blob/master/docs/config.md) · [图标来源](https://github.com/slskd/slskd/blob/0.26.2/src/web/public/favicon.ico)
