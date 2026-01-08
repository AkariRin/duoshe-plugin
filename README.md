# 夺舍

定期随机选择活跃用户进行群名片交换的趣味插件

## 功能

- 每个群聊独立定时执行"夺舍"操作
- 基于24小时活跃度选择用户（使用指数分布算法）
- 拍一拍目标用户并交换群名片

## 配置napcat

在napcat的网络配置中添加一个HTTP服务器：

1. 打开napcat的配置界面（WebUI或配置文件）
2. 在"网络配置"中点击"添加"，选择"HTTP服务器"
3. 配置以下参数：
   - **主机地址**: `0.0.0.0`（允许外部访问）或 `127.0.0.1`（仅本机访问）
   - **端口**: `3000`（与插件配置中的 `napcat.port` 保持一致）
   - **启用CORS**: ✅ 开启
   - **Token**: 留空（不设置鉴权）
4. 保存配置并重启napcat

> ⚠️ 注意：如果napcat和插件不在同一台机器上，请确保防火墙放行对应端口。

## 配置说明

插件配置文件位于 `config.toml`：

```toml
[plugin]
enabled = true                 # 是否启用插件
config_version = "1.0.0"       # 配置文件版本

[napcat]
address = "napcat"             # Napcat服务器地址
port = 3000                    # Napcat服务器端口

[schedule]
min_interval = 360             # 最小间隔时间（分钟）
max_interval = 480             # 最大间隔时间（分钟）

[selection]
lambda_param = 1.5             # 指数分布的λ参数，值越大越倾向于选择活跃度高的用户
```

## 使用

1. 将插件目录放置在 `plugins/` 下
2. 调整 `config.toml` 配置
3. 重启麦麦
