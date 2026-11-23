# Kavita

漫画和电子书阅读服务。首次打开 `http://NAS-IP:5000/` 后创建管理员并添加授权书库路径。包 ID、运行用户和组均为 `Kavita`。账号、书库数据库、封面和设置保存在 `TRIM_PKGVAR/config`。Moo 的一些应用操作会将 `Kavita` 和 Docker 版的 `kavita` 按同名匹配，使用 Moo 管理时请只安装其中一版。 [上游原生安装说明](https://wiki.kavitareader.com/installation/native/) · [Moo 匹配代码](https://github.com/Blue-Mink/moo/blob/v0.6.566/internal/api/store_ops.go#L70-L105)

GitHub Release 标签和文件名保留完整的四段上游版本。`v0.9.1.4-r1` 补齐服务启动时的系统命令搜索路径，防止 Kavita 找不到 `uname`。包内版本为 `0.9.100401`，可从首发的 `0.9.1004` 就地升级。 [上游发布](https://github.com/Kareadita/Kavita/releases) · [图标来源](https://github.com/Kareadita/Kavita/blob/v0.9.1.4/UI/Web/src/assets/icons/android-chrome-256x256.png)

如果装过早期 `kavita-native` 调试包，先停止旧服务并备份其 `TRIM_PKGVAR/config`。安装新包后先停止它，再将备份恢复到新包的 `TRIM_PKGVAR/config`，将文件归属设为 `Kavita:Kavita`，并为新应用重新授权书库目录。
