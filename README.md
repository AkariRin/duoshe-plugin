# 夺舍插件

定期随机选择活跃用户进行群名片交换的趣味插件。

## 功能描述

该插件会为每个QQ群聊独立注册定时器，在随机的时间间隔内执行"夺舍"操作：

1. 分析最近24小时的群聊活跃用户
2. 使用指数分布算法随机选择一个用户（倾向于选择更活跃的用户）
3. 拍一拍该用户
4. 将机器人的群名片改为该用户的群名片
5. 如果机器人是管理员，将该用户的群名片改为机器人的昵称/别名/原群名片（随机选择）

## 配置说明

编辑 `config.toml` 文件进行配置：

```toml
# 最小间隔时间（分钟）
min_interval_minutes = 30

# 最大间隔时间（分钟）
max_interval_minutes = 120

# 指数分布的λ参数
# 值越大，越倾向于选择活跃度高的用户
# 推荐范围：1.0 - 3.0
lambda_param = 1.5

# Napcat服务器配置
[napcat]
address = "napcat"
port = 3000
```

### 配置项说明

- **min_interval_minutes**: 两次夺舍之间的最小间隔时间（分钟）
- **max_interval_minutes**: 两次夺舍之间的最大间隔时间（分钟）
- **lambda_param**: 指数分布的λ参数，控制用户选择的倾向性
  - 值越大，越倾向于选择活跃度高的用户
  - 值越小，选择更加随机化
  - 推荐范围：1.0 - 3.0
- **napcat.address**: Napcat服务器地址
- **napcat.port**: Napcat服务器端口

## 工作原理

### 活跃用户选择算法

1. 统计最近24小时内每个用户的发言数量（排除机器人自己和命令消息）
2. 按发言数量从高到低排序
3. 使用指数分布随机选择一个用户：
   - 使用Python标准库的 `random.expovariate(λ)` 生成随机值
   - 将随机值映射到用户列表索引
   - 活跃度高的用户（排在前面）有更高概率被选中

### 定时任务管理

- 每个群聊独立运行定时任务
- 使用JSON文件 (`schedule.json`) 持久化存储每个群的下次执行时间
- 即使机器人重启，也能从上次的计划继续执行
- 每分钟检查一次是否到达执行时间

### 夺舍流程

```
选择活跃用户 → 拍一拍 → 获取用户名片 → 修改自己名片 → (如果是管理员)修改对方名片
```

## 依赖说明

本插件依赖以下MaiBot API：

- `chat_api`: 获取群聊列表
- `message_api`: 获取聊天消息记录
- `config_api`: 获取机器人配置（昵称、别名等）

本插件需要Napcat服务器支持以下接口：

- `/group_poke`: 拍一拍
- `/set_group_card`: 修改群名片
- `/get_group_member_info`: 获取群成员信息

## 文件说明

- `plugin.py`: 插件主文件
- `config.toml`: 配置文件
- `schedule.json`: 定时计划存储文件（自动生成）
- `_manifest.json`: 插件元数据
- `requirement.md`: 需求文档

## 使用方法

1. **安装插件**：将插件目录放置在MaiBot的`plugins/`目录下
2. **配置插件**：编辑`config.toml`文件，根据需要调整间隔时间和λ参数
3. **启动机器人**：启动MaiBot，插件会自动加载并开始为所有群聊注册定时任务
4. **查看日志**：通过日志可以看到插件的运行状态和夺舍记录

## 运行示例

插件启动后，日志中会显示类似如下信息：

```
[INFO] [Plugin:duoshe_plugin] 找到 3 个群聊，开始初始化定时任务
[DEBUG] [Plugin:duoshe_plugin] 已为群 123456789 创建定时任务
[DEBUG] [Plugin:duoshe_plugin] 已为群 987654321 创建定时任务
[INFO] [Plugin:duoshe_plugin] 群 123456789 的定时任务已启动
[INFO] [Plugin:duoshe_plugin] 群 123456789 开始执行夺舍任务
[DEBUG] [Plugin:duoshe_plugin] 群 123456789 找到 15 个活跃用户
[INFO] [Plugin:duoshe_plugin] 群 123456789 选择目标用户: 114514
[INFO] [Plugin:duoshe_plugin] 群 123456789 成功拍了拍用户 114514
[INFO] [Plugin:duoshe_plugin] 群 123456789 成功将自己的群名片改为: 张三
[INFO] [Plugin:duoshe_plugin] 群 123456789 成功将目标用户 114514 的群名片改为: 麦麦
[INFO] [Plugin:duoshe_plugin] 群 123456789 夺舍任务完成，下次执行时间: 2026-01-09 15:30:00
```

## 故障排查

### 插件未启动

- 检查插件目录是否正确放置在`plugins/`下
- 检查日志中是否有插件加载失败的错误信息
- 确认`_manifest.json`文件格式正确

### 无法获取活跃用户

- 确认群聊在24小时内有用户发言
- 检查消息数据库是否正常工作
- 查看日志中是否有权限或API错误

### NapCat API调用失败

- 确认`config.toml`中的NapCat地址和端口配置正确
- 检查NapCat服务是否正常运行
- 确认NapCat API版本兼容

### 定时任务未执行

- 检查`schedule.json`文件内容，确认下次执行时间
- 查看日志中是否有异常信息
- 确认机器人有足够的权限执行操作

## 许可证

MIT License

## 作者

梦清 - [GitHub](https://github.com/AkariRin)

