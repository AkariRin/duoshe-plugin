import asyncio
import json
import random
import time
from pathlib import Path
from typing import Type, Tuple, List, Union, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from collections import defaultdict

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
    chat_api,
    message_api,
    config_api,
    get_logger
)

logger = get_logger("duoshe-plugin")

# Napcat API调用类
class NapcatAPI:
    @staticmethod
    def _make_request(url: str, payload: dict) -> Tuple[bool, Union[dict, str]]:
        """发送HTTP POST请求到napcat

        Args:
            url: 请求URL
            payload: 请求数据

        Returns:
            (True, response_data) 成功时
            (False, error_message) 失败时
        """
        try:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            request = Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return True, result
        except HTTPError as e:
            return False, f"HTTP错误: {e.code}"
        except URLError as e:
            return False, f"网络错误: {e.reason}"
        except json.JSONDecodeError as e:
            return False, f"JSON解析错误: {e}"
        except Exception as e:
            return False, f"请求错误: {str(e)}"

    @staticmethod
    def group_poke(address: str, port: int, group_id: str, user_id: str) -> Tuple[bool, Union[dict, str]]:
        """拍一拍群成员

        Args:
            address: napcat服务器地址
            port: napcat服务器端口
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            (True, response_data) 成功时
            (False, error_msg) 失败时
        """
        url = f"http://{address}:{port}/group_poke"
        payload = {"group_id": group_id, "user_id": user_id}

        success, result = NapcatAPI._make_request(url, payload)
        if not success:
            return False, result

        return True, result

    @staticmethod
    def set_group_card(address: str, port: int, group_id: str, user_id: str, card: str) -> Tuple[bool, Union[dict, str]]:
        """修改群成员名片

        Args:
            address: napcat服务器地址
            port: napcat服务器端口
            group_id: 群号
            user_id: 用户QQ号
            card: 新的群名片

        Returns:
            (True, response_data) 成功时
            (False, error_msg) 失败时
        """
        url = f"http://{address}:{port}/set_group_card"
        payload = {"group_id": group_id, "user_id": user_id, "card": card}

        success, result = NapcatAPI._make_request(url, payload)
        if not success:
            return False, result

        data = result.get("data")
        if result.get("status") != "ok":
            return False, f"设置群名片失败: {result.get('message', '未知错误')}"
        return True, result

    @staticmethod
    def get_group_member_info(address: str, port: int, group_id: str, user_id: str) -> Tuple[bool, Union[dict, str]]:
        """获取群成员信息

        Args:
            address: napcat服务器地址
            port: napcat服务器端口
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            (True, member_info) 成功时返回群成员信息字典
            (False, error_msg) 失败时返回错误信息
        """
        url = f"http://{address}:{port}/get_group_member_info"
        payload = {"group_id": group_id, "user_id": user_id, "no_cache": True}

        success, result = NapcatAPI._make_request(url, payload)
        if not success:
            return False, result

        data = result.get("data")
        if data is None:
            return False, "获取群成员信息失败：返回数据为空"
        return True, data


@register_plugin
class DuoshePlugin(BasePlugin):
    plugin_name = "duoshe-plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = []
    config_file_name = "config.toml"

    config_section_descriptions = {
        "plugin": "插件启用配置",
        "schedule": "夺舍任务调度配置",
        "selection": "用户选择策略配置",
        "napcat": "Napcat服务器连接配置"
    }

    config_schema = {
        "plugin": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用插件"
            ),
            "config_version": ConfigField(
                type=str,
                default="1.0.0",
                description="配置文件版本"
            )
        },
        "napcat": {
            "address": ConfigField(
                type=str,
                default="napcat",
                description="Napcat服务器地址"
            ),
            "port": ConfigField(
                type=int,
                default=3000,
                description="Napcat服务器端口"
            )
        },
        "schedule": {
            "min_interval": ConfigField(
                type=int,
                default=360,
                description="最小间隔时间（分钟）"
            ),
            "max_interval": ConfigField(
                type=int,
                default=480,
                description="最大间隔时间（分钟）"
            )
        },
        "selection": {
            "lambda_param": ConfigField(
                type=float,
                default=1.5,
                description="指数分布的λ参数，值越大越倾向于选择活跃度高的用户"
            )
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schedule_file = Path(__file__).parent / "schedule.json"
        self.tasks: Dict[str, asyncio.Task] = {}
        self.bot_qq = None

        # 启动所有群聊的定时任务
        asyncio.create_task(self._initialize_tasks())

    async def _initialize_tasks(self):
        """初始化所有群聊的定时任务"""
        try:
            # 获取机器人QQ号
            self.bot_qq = str(config_api.get_global_config("bot.qq_account", ""))
            if not self.bot_qq:
                logger.error(f"初始化定时任务失败：无法获取机器人QQ号")
                return

            # 获取所有QQ群聊
            group_streams = chat_api.get_group_streams(platform="qq")
            logger.info(f"找到 {len(group_streams)} 个群聊，开始初始化定时任务")

            # 为每个群聊创建定时任务
            for stream in group_streams:
                if stream.group_info:
                    group_id = str(stream.group_info.group_id)
                    task = asyncio.create_task(self._schedule_task(group_id, stream.stream_id))
                    self.tasks[group_id] = task
                    logger.debug(f"已为群 {group_id} 创建定时任务")

        except Exception as e:
            logger.error(f"初始化定时任务失败: {e}", exc_info=True)

    def _load_schedule(self) -> Dict[str, float]:
        """从JSON文件加载定时计划

        Returns:
            Dict[group_id, next_run_timestamp]
        """
        if not self.schedule_file.exists():
            return {}

        try:
            with open(self.schedule_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载定时计划失败: {e}")
            return {}

    def _save_schedule(self, schedule_data: Dict[str, float]):
        """保存定时计划到JSON文件

        Args:
            schedule_data: Dict[group_id, next_run_timestamp]
        """
        try:
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存定时计划失败: {e}")

    async def _schedule_task(self, group_id: str, chat_id: str):
        """单个群聊的定时任务循环

        Args:
            group_id: 群号
            chat_id: 聊天流ID
        """
        # 获取群名称
        chat_stream = chat_api.get_stream_by_group_id(group_id)
        group_name = chat_stream.group_info.group_name if chat_stream and chat_stream.group_info and chat_stream.group_info.group_name else "未知群"
        group_display = f"{group_name}({group_id})"

        logger.info(f"群 {group_display} 的定时任务已启动")

        while True:
            try:
                # 加载定时计划
                schedule_data = self._load_schedule()

                current_time = time.time()
                next_run = schedule_data.get(group_id, current_time)

                # 检查是否到达执行时间
                if current_time >= next_run:
                    logger.info(f"群 {group_display} 开始执行夺舍任务")

                    # 执行夺舍任务
                    await self._execute_duoshe(group_id, chat_id)

                    # 计算下次执行时间（随机间隔）
                    min_minutes = self.config.get("schedule", {}).get("min_interval", 360)
                    max_minutes = self.config.get("schedule", {}).get("max_interval", 480)
                    interval_minutes = random.uniform(min_minutes, max_minutes)
                    interval = interval_minutes * 60
                    next_run = current_time + interval

                    # 保存更新后的计划
                    schedule_data[group_id] = next_run
                    self._save_schedule(schedule_data)

                    logger.info(f"群 {group_display} 夺舍任务完成，下次执行时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_run))}")

                # 等待到下次检查时间（每分钟检查一次）
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info(f"群 {group_display} 的定时任务已取消")
                break
            except Exception as e:
                logger.error(f"群 {group_display} 定时任务出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                await asyncio.sleep(300)

    async def _execute_duoshe(self, group_id: str, chat_id: str):
        """执行夺舍操作

        Args:
            group_id: 群号
            chat_id: 聊天流ID
        """
        # 获取群名称
        chat_stream = chat_api.get_stream_by_group_id(group_id)
        group_name = chat_stream.group_info.group_name if chat_stream and chat_stream.group_info and chat_stream.group_info.group_name else "未知群"
        group_display = f"{group_name}({group_id})"

        try:
            # ============ Step 1: 获取并统计活跃用户 ============
            try:
                # 获取最近24小时的消息
                end_time = time.time()
                start_time = end_time - 24 * 3600

                messages = message_api.get_messages_by_time_in_chat(
                    chat_id=chat_id,
                    start_time=start_time,
                    end_time=end_time,
                    filter_mai=True,  # 过滤机器人自己的消息
                    filter_command=True  # 过滤命令消息
                )

                # 统计每个用户的消息数量
                user_message_count: Dict[str, int] = defaultdict(int)
                for msg in messages:
                    if msg.user_info and msg.user_info.user_id:
                        user_id = msg.user_info.user_id
                        user_message_count[user_id] += 1

                # 按消息数量降序排序
                sorted_users = sorted(user_message_count.items(), key=lambda x: x[1], reverse=True)

                # 只保留用户ID列表
                active_users = [user_id for user_id, _ in sorted_users]

            except Exception as e:
                logger.error(f"获取活跃用户失败: {e}", exc_info=True)
                active_users = []

            if not active_users:
                logger.warning(f"群 {group_display} 没有活跃用户，跳过本次夺舍")
                return

            logger.debug(f"群 {group_display} 找到 {len(active_users)} 个活跃用户")

            # ============ Step 2: 使用指数分布选择目标用户 ============
            if len(active_users) == 1:
                target_user_id = active_users[0]
            else:
                try:
                    lambda_param = self.config.get("selection", {}).get("lambda_param", 1.5)

                    # 使用指数分布生成一个[0, 1)区间的随机数
                    # 然后映射到用户列表的索引
                    random_value = random.expovariate(lambda_param)

                    # 将随机值映射到[0, len(active_users))区间
                    # 指数分布的值域是[0, +∞)，我们需要将其映射到有限区间
                    # 使用反向累积分布函数的思想，较小的值（对应活跃度高的用户）被选中的概率更大
                    index = int(random_value * len(active_users))

                    # 确保索引在有效范围内
                    index = min(index, len(active_users) - 1)

                    target_user_id = active_users[index]

                except Exception as e:
                    logger.error(f"使用指数分布选择用户失败: {e}，使用随机选择")
                    target_user_id = random.choice(active_users)

            if not target_user_id:
                logger.warning(f"群 {group_display} 选择用户失败，跳过本次夺舍")
                return

            logger.info(f"群 {group_display} 选择目标用户: {target_user_id}")

            # 获取napcat配置
            napcat_address = self.config.get("napcat", {}).get("address", "napcat")
            napcat_port = self.config.get("napcat", {}).get("port", 3000)

            # ============ Step 3: 拍一拍目标用户（失败也继续） ============
            success, result = NapcatAPI.group_poke(napcat_address, napcat_port, group_id, target_user_id)
            if success:
                logger.debug(f"群 {group_display} 成功拍了拍用户 {target_user_id}")
            else:
                logger.warning(f"群 {group_display} 拍一拍失败: {result}，继续执行")

            # ============ Step 4: 获取目标用户和机器人的群成员信息 ============
            success, target_info = NapcatAPI.get_group_member_info(napcat_address, napcat_port, group_id, target_user_id)
            if not success:
                logger.error(f"群 {group_display} 获取目标用户信息失败: {target_info}，跳过本次夺舍")
                return

            target_card = target_info.get("card", "") or target_info.get("nickname", "")
            logger.debug(f"群 {group_display} 目标用户群名片: {target_card}")

            # 获取机器人自己的群成员信息
            success, bot_info = NapcatAPI.get_group_member_info(napcat_address, napcat_port, group_id, self.bot_qq)
            if not success:
                logger.error(f"群 {group_display} 获取机器人信息失败: {bot_info}，跳过本次夺舍")
                return

            bot_card = bot_info.get("card", "") or bot_info.get("nickname", "")
            bot_role = bot_info.get("role", "member")

            logger.debug(f"群 {group_display} 机器人当前群名片: {bot_card}, 角色: {bot_role}")

            # ============ Step 5: 将自己的群名片改成目标用户的群名片 ============
            success, result = NapcatAPI.set_group_card(napcat_address, napcat_port, group_id, self.bot_qq, target_card)
            if success:
                logger.debug(f"群 {group_display} 成功将自己的群名片改为: {target_card}")
            else:
                logger.error(f"群 {group_display} 修改自己群名片失败: {result}")

            # ============ Step 6: 如果是管理员，修改目标用户的群名片 ============
            if bot_role in ["admin", "owner"]:
                # 获取机器人的昵称和别名
                bot_nickname = config_api.get_global_config("bot.nickname", "")
                bot_aliases = config_api.get_global_config("bot.alias_names", [])

                # 构建候选名片列表：昵称、别名、当前群名片
                candidates = []
                if bot_nickname:
                    candidates.append(bot_nickname)
                if bot_aliases:
                    candidates.extend(bot_aliases)
                if bot_card:
                    candidates.append(bot_card)

                if candidates:
                    # 随机选择一个名片
                    new_card = random.choice(candidates)

                    success, result = NapcatAPI.set_group_card(napcat_address, napcat_port, group_id, target_user_id, new_card)
                    if success:
                        logger.debug(f"群 {group_display} 成功将目标用户 {target_user_id} 的群名片改为: {new_card}")
                    else:
                        logger.error(f"群 {group_display} 修改目标用户群名片失败: {result}")
                else:
                    logger.warning(f"群 {group_display} 没有可用的候选名片")
            else:
                logger.debug(f"群 {group_display} 机器人不是管理员，跳过修改目标用户名片")

        except Exception as e:
            logger.error(f"群 {group_display} 执行夺舍任务失败: {e}", exc_info=True)

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return []
