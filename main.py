"""
由AstrBot 群发言统计插件二次开发
统计群成员发言次数,生成排行榜
"""

# 标准库导入
import asyncio 
import os
import aiofiles
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import json
import os
import datetime
# 第三方库导入
from cachetools import TTLCache

# AstrBot框架导入
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger as astrbot_logger

# 本地模块导入
from .utils.data_manager import DataManager
from .utils.image_generator import ImageGenerator, ImageGenerationError
from .utils.validators import Validators

from .utils.models import (
    UserData, PluginConfig, GroupInfo, MessageDate, 
    RankType
)

# 异常处理装饰器导入
from .utils.exception_handlers import (
    exception_handler,
    data_operation_handler,
    file_operation_handler,
    safe_execute,
    log_exception,
    ExceptionConfig,
    safe_execute_with_context,
    safe_data_operation,
    safe_file_operation,
    safe_cache_operation,
    safe_config_operation,
    safe_calculation,
    safe_generation,
    safe_timer_operation
)
#===========JSON操作导入===========
# JSON处理模块
class JsonHandler:
    @staticmethod
    def 验证文件名(文件名: str) -> bool:
        """验证文件名是否合法"""
        if not 文件名:
            print("错误: 文件名不能为空")
            return False
        
        # 检查文件名是否包含路径分隔符（防止路径遍历攻击）
        if any(c in 文件名 for c in ['/', '\\', './', '../', '.\\', '..\\']):
            print(f"错误: 文件名 '{文件名}' 包含非法字符或路径组件")
            return False
        
        # 检查文件名是否包含非法字符
        invalid_chars = '<>|?*"'
        if any(c in 文件名 for c in invalid_chars):
            print(f"错误: 文件名 '{文件名}' 包含非法字符")
            return False
        
        return True
    
    @staticmethod
    def 读取Json字典(文件名: str) -> dict:
        """从JSON文件读取数据并返回字典"""
        try:
            # 从JSON文件读取完整数据
            文件路径 = JsonHandler.获取文件路径(文件名, True)
            if os.path.exists(文件路径):
                try:
                    with open(文件路径, 'r', encoding='utf-8') as f:
                        return json.load(f) if f.read().strip() else {}
                except Exception as e:
                    print(f"读取JSON文件失败: {e}")
            return {}
        except Exception as e:
            print(f"读取数据错误: {e}")
            return {}
    
    @staticmethod
    def 获取值(数据字典: dict, 键: str, 默认值: any = None) -> any:
        """安全地从字典中获取值"""
        return 数据字典.get(键, 默认值)
    
    @staticmethod
    def 获取文件路径(文件名: str, 确保目录存在: bool = False) -> str:
        """获取文件路径，将数据存储在安全的数据目录中
        
        Args:
            文件名: 要访问的JSON文件名
            确保目录存在: 是否确保目录存在，不存在则创建
            
        Returns:
            文件的绝对路径
        """
        try:
            # 获取插件数据目录
            plugin_data_path = StarTools.get_data_dir()
            # 构建完整路径: data/plugin_data/astrbot_plugin_gouzidingzhi/文件名
            file_path = os.path.join(plugin_data_path, 文件名)
            
            # 确保目录存在
            if 确保目录存在:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            return file_path
        except Exception as e:
            print(f"获取文件路径失败: {e}")
            # 降级方案：使用当前目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 文件名)
            if 确保目录存在:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            return file_path
    
    @staticmethod
    def 写入Json字典(文件名: str, 数据: dict) -> bool:
        """将字典数据写入JSON文件，使用UserData目录下的文件名作为模板
        
        Args:
            文件名: JSON文件名（使用UserData目录下的文件名作为模板）
            数据: 要写入的数据字典
            
        Returns:
            bool: 是否写入成功
        """
        try:
            # 获取文件路径并确保目录存在
            文件路径 = JsonHandler.获取文件路径(文件名, True)
            
            # 检查目录是否存在
            目录 = os.path.dirname(文件路径)
            if not os.path.exists(目录):
                os.makedirs(目录, exist_ok=True)
                print(f"创建目录: {目录}")
            
            # 写入数据
            with open(文件路径, 'w', encoding='utf-8') as f:
                json.dump(数据, f, ensure_ascii=False, indent=2)
            
            print(f"数据已成功写入: {文件路径}")
            return True
        except Exception as e:
            print(f"写入JSON文件失败: {文件名}, 错误: {e}")
            return False
    
    @staticmethod
    def 读取Json字典(文件名: str) -> dict:
        """读取JSON文件为字符串字典，使用UserData目录下的文件名作为模板"""
        try:
            # 获取文件路径并确保目录存在
            文件路径 = JsonHandler.获取文件路径(文件名, True)
            
            # 检查文件是否存在
            if not os.path.exists(文件路径):
                print(f"文件不存在，创建空字典: {文件路径}")
                # 创建空文件
                JsonHandler.写入Json字典(文件名, {})
                return {}
            
            # 读取文件内容
            with open(文件路径, 'r', encoding='utf-8') as f:
                json内容 = f.read().strip()
                if not json内容:
                    return {}
                字典 = json.loads(json内容)
                
                if not isinstance(字典, dict):
                    print(f"JSON文件内容格式不正确: {文件路径}")
                    return {}
                
                return 字典
        except Exception as ex:
            print(f"错误: 读取JSON字典时发生错误 - {ex}")
            return {}
    
    @staticmethod
    def 获取值(字典: dict, 键: str, 默认值: str = None) -> str:
        """根据键获取值，如果键不存在返回默认值"""
        if 字典 is not None and 键 in 字典:
            return 字典[键]
        return 默认值
    
    @staticmethod
    def 添加或更新(文件名: str, 键: str, 值: str) -> bool:
        """向JSON文件添加或更新键值对"""
        try:
            if not 键:
                print("错误: 键名不能为空")
                return False
            
            # 读取现有数据
            data = JsonHandler.读取Json字典(文件名)
            
            # 更新键值对
            data[键] = str(值)
            
            # 写入文件
            return JsonHandler.写入Json字典(文件名, data)
        except Exception as ex:
            print(f"错误: 添加或更新值时发生错误 - {ex}")
            return False
    
# 创建别名方便使用
Json = JsonHandler
# ========== 全局常量定义 ==========

# 缓存配置
CACHE_TTL_SECONDS = 300
USER_NICKNAME_CACHE_TTL = 600
MAX_RANK_COUNT = 100

# 配置键名
RANK_COUNT_KEY = 'rand'
IMAGE_MODE_KEY = 'if_send_pic'

@register("stats", "xiaoruange39", "群发言统计插件", "1.6.0")
class MessageStatsPlugin(Star):
    """群发言统计插件
    
    该插件用于统计群组成员的发言次数,并生成多种类型的排行榜.
    支持自动监听群消息、手动记录、总榜/日榜/周榜/月榜等功能.
    
    主要功能:
        - 自动监听和记录群成员发言统计
        - 支持多种排行榜类型(总榜、日榜、周榜、月榜)
        - 提供图片和文字两种显示模式
        - 完整的配置管理系统
        - 权限控制和安全管理
        - 群成员昵称智能获取
        - 高效的缓存机制
        
    Attributes:
        data_manager (DataManager): 数据管理器,负责数据的存储和读取
        plugin_config (PluginConfig): 插件配置对象
        image_generator (ImageGenerator): 图片生成器,用于生成排行榜图片
        group_members_cache (TTLCache): 群成员列表缓存,5分钟TTL
        logger: 日志记录器
        initialized (bool): 插件初始化状态
        
    Example:
        >>> plugin = MessageStatsPlugin(context)
        >>> await plugin.initialize()
        >>> # 插件将自动开始监听群消息并记录统计
    """
    
    def __init__(self, context: Context, config: 'AstrBotConfig' = None):
        """初始化插件实例
        
        Args:
            context (Context): AstrBot上下文对象,包含插件运行环境信息
            config (AstrBotConfig): AstrBot配置的插件配置对象,通过Web界面设置
        """
        super().__init__(context)
        self.logger = astrbot_logger
        
        # 使用StarTools获取插件数据目录
        data_dir = StarTools.get_data_dir('message_stats')
        
        # 初始化组件
        self.data_manager = DataManager(data_dir)
        
        # 使用AstrBot的标准配置系统
        self.config = config
        self.plugin_config = self._convert_to_plugin_config()
        self.image_generator = None
        
        # 群组unified_msg_origin映射表 - 用于主动消息发送
        self.group_unified_msg_origins = {}
        
        # 群成员列表缓存 - 5分钟TTL,减少API调用
        self.group_members_cache = TTLCache(maxsize=100, ttl=CACHE_TTL_SECONDS)
        
        # 群成员字典缓存 - 用于快速查找群成员信息
        self.group_members_dict_cache = {}
        
        # 用户昵称缓存 - 缓存用户ID到昵称的映射，减少重复查找
        self.user_nickname_cache = TTLCache(maxsize=500, ttl=USER_NICKNAME_CACHE_TTL)
        
        # 定时任务管理器 - 延迟初始化
        self.timer_manager = None
    
    def _convert_to_plugin_config(self) -> PluginConfig:
        """将AstrBot配置转换为插件配置对象"""
        try:
            # 如果没有配置，使用默认配置
            if not self.config:
                self.logger.info("没有配置，使用默认配置")
                return PluginConfig()
            
            # 确保config是字典类型
            config_dict = dict(self.config) if hasattr(self.config, 'items') else {}
            
            # 使用PluginConfig.from_dict()方法进行安全的配置转换
            config = PluginConfig.from_dict(config_dict)
            
            # 记录配置转换情况
            if config.timer_enabled and config.timer_target_groups:
                self.logger.info(f"配置转换完成: 定时功能已启用, 目标群组: {config.timer_target_groups}")
                # 如果有unified_msg_origin信息，通知定时任务更新
                if hasattr(self, 'group_unified_msg_origins') and self.group_unified_msg_origins:
                    self.logger.info(f"当前unified_msg_origin映射表: {list(self.group_unified_msg_origins.keys())}")
            
            return config
        except Exception as e:
            self.logger.error(f"配置转换失败: {e}")
            self.logger.info("使用默认配置继续运行")
            return PluginConfig()
        
    async def _collect_group_unified_msg_origin(self, event: AstrMessageEvent):
        """收集群组的unified_msg_origin
        
        Args:
            event: 消息事件对象
        """
        try:
            group_id = event.get_group_id()
            unified_msg_origin = event.unified_msg_origin
            
            if group_id and unified_msg_origin:
                # 检查是否是新的unified_msg_origin
                old_origin = self.group_unified_msg_origins.get(str(group_id))
                self.group_unified_msg_origins[str(group_id)] = unified_msg_origin
                
                if old_origin != unified_msg_origin:
                    self.logger.info(f"已收集群组 {group_id} 的 unified_msg_origin")
                    
                    # 如果定时任务正在运行且需要此群组，重新启动定时任务
                    if self.timer_manager:
                        # 记录当前unified_msg_origin状态
                        self.logger.info(f"群组 {group_id} 的 unified_msg_origin: {unified_msg_origin[:20]}...")
                        
                        if self.plugin_config.timer_enabled and str(group_id) in self.plugin_config.timer_target_groups:
                            self.logger.info(f"检测到目标群组 {group_id} 的 unified_msg_origin 已更新，重新启动定时任务...")
                            # 确保unified_msg_origin映射表是最新的
                            self.timer_manager.push_service.group_unified_msg_origins = self.group_unified_msg_origins
                            success = await self.timer_manager.update_config(self.plugin_config, self.group_unified_msg_origins)
                            if success:
                                self.logger.info(f"定时任务重新启动成功")
                            else:
                                self.logger.warning(f"定时任务重新启动失败")
                

        except (AttributeError, KeyError, TypeError) as e:
            self.logger.error(f"收集群组unified_msg_origin失败: {e}")
        except (RuntimeError, OSError, IOError, ImportError, ValueError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"收集群组unified_msg_origin失败(系统错误): {e}")
    
    async def _collect_group_unified_msg_origins(self):
        """收集所有群组的unified_msg_origin（从缓存中获取）"""
        # 这个方法用于初始化时的批量收集
        # 由于没有event对象，我们先返回空字典
        # 实际的收集将在命令执行时进行
        return self.group_unified_msg_origins.copy()
    
    # ========== 类常量定义 ==========
    
    # 排行榜数量限制常量
    RANK_COUNT_MIN = 1
    MAX_RANK_COUNT = 100
    
    # 图片模式别名常量
    IMAGE_MODE_ENABLE_ALIASES = {'1', 'true', '开', 'on', 'yes'}
    IMAGE_MODE_DISABLE_ALIASES = {'0', 'false', '关', 'off', 'no'}
    
    async def initialize(self):
        """初始化插件
        
        异步初始化插件的所有组件,包括数据管理器、配置和图片生成器.
        
        Raises:
            OSError: 当数据目录创建失败时抛出
            IOError: 当配置文件读写失败时抛出
            Exception: 其他初始化相关的异常
            
        Returns:
            None: 无返回值,初始化成功后设置initialized状态
            
        Example:
            >>> plugin = MessageStatsPlugin(context)
            >>> await plugin.initialize()
            >>> print(plugin.initialized)
            True
        """
        try:
            self.logger.info("群发言统计插件初始化中...")
            
            # 步骤1: 初始化数据管理器
            await self._initialize_data_manager()
            
            # 步骤2: 加载插件配置和创建图片生成器
            await self._load_plugin_config()
            
            # 步骤3: 设置数据管理器的配置引用
            self.data_manager.set_plugin_config(self.plugin_config)
            
            # 步骤4: 初始化定时任务管理器
            await self._initialize_timer_manager()
            
            # 步骤5: 初始化Rbot功能定时任务
            await self._initialize_rbot_timers()
            
            # 步骤6: 设置缓存和最终初始化状态
            await self._setup_caches()
            
            self.logger.info("群发言统计插件初始化完成")
            
        except (OSError, IOError) as e:
            self.logger.error(f"插件初始化失败: {e}")
            raise
    
    async def _initialize_data_manager(self):
        """初始化数据管理器
        
        负责初始化数据管理器的核心功能，包括目录创建和基础设置。
        
        Raises:
            OSError: 当数据目录创建失败时抛出
            IOError: 当文件操作失败时抛出
            
        Returns:
            None: 无返回值
        """
        await self.data_manager.initialize()
    
    async def _load_plugin_config(self):
        """更新插件配置和创建图片生成器
        
        从AstrBot配置更新插件配置，并创建和初始化图片生成器。
        
        Raises:
            ImportError: 当导入图片生成器相关模块失败时抛出
            
        Returns:
            None: 无返回值
        """
        # 更新插件配置（从AstrBot配置转换）
        self.plugin_config = self._convert_to_plugin_config()
        
        # 创建图片生成器
        self.image_generator = ImageGenerator(self.plugin_config)
        
        # 初始化图片生成器
        try:
            await self.image_generator.initialize()
            self.logger.info("图片生成器初始化成功")
        except ImageGenerationError as e:
            self.logger.warning(f"图片生成器初始化失败: {e}")
            self.logger.warning("💡 提示: 如果需要图片功能，请运行 'playwright install' 命令安装浏览器")
            self.logger.warning("📝 注意: 即使图片功能不可用，排行榜仍会以文字模式显示")
        
        # 记录当前配置状态
        self.logger.info(f"当前配置: 图片模式={self.plugin_config.if_send_pic}, 显示人数={self.plugin_config.rand}, 自动记录={self.plugin_config.auto_record_enabled}")
    
    async def _initialize_timer_manager(self):
        """初始化定时任务管理器
        
        创建并初始化定时任务管理器，尝试启动定时任务（不阻塞初始化过程）。
        
        Raises:
            ImportError: 当导入定时任务管理器模块失败时抛出
            OSError: 当系统操作失败时抛出
            IOError: 当文件操作失败时抛出
            RuntimeError: 当运行时错误发生时抛出
            AttributeError: 当属性访问错误时抛出
            ValueError: 当参数值错误时抛出
            TypeError: 当类型错误时抛出
            ConnectionError: 当连接错误时抛出
            asyncio.TimeoutError: 当异步操作超时时抛出
            
        Returns:
            None: 无返回值
        """
        try:
            from .utils.timer_manager import TimerManager
            self.timer_manager = TimerManager(self.data_manager, self.image_generator, self.context, self.group_unified_msg_origins)
            self.logger.info("定时任务管理器初始化成功")
            
            # 尝试启动定时任务（不阻塞初始化过程）
            if self.plugin_config.timer_enabled:
                self.logger.info("检测到定时功能已启用，尝试启动定时任务...")
                try:
                    # 使用update_config启动，确保group_unified_msg_origins被正确传递
                    success = await self.timer_manager.update_config(self.plugin_config, self.group_unified_msg_origins)
                    if success:
                        self.logger.info("定时任务启动成功")
                    else:
                        self.logger.warning("定时任务启动失败，可能是因为群组unified_msg_origin尚未收集")
                except (ImportError, AttributeError) as timer_error:
                    self.logger.warning(f"定时任务启动失败: {timer_error}")
                    # 即使定时任务启动失败，也不影响TimerManager的创建
                    
        except (ImportError, OSError, IOError) as e:
            self.logger.warning(f"定时任务管理器初始化失败: {e}")
            self.timer_manager = None
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.warning(f"定时任务管理器初始化失败(运行时错误): {e}")
            self.timer_manager = None
    
    async def _initialize_rbot_timers(self):
        """初始化Rbot功能的定时任务
        
        创建并启动每周重置阅历和每日重置签到状态的定时任务。
        
        Returns:
            None: 无返回值
        """
        try:
            # 创建每周重置阅历的定时任务
            import asyncio
            
            async def weekly_reset_task():
                """每周重置阅历的循环任务"""
                while True:
                    try:
                        # 每小时检查一次是否需要重置阅历
                        await self._weekly_experience_reset()
                        # 等待1小时
                        await asyncio.sleep(3600)
                    except Exception as e:
                        self.logger.error(f"每周阅历重置任务出错: {e}")
                        # 出错后等待1小时再重试
                        await asyncio.sleep(3600)
            
            async def daily_sign_in_reset_task():
                """每日重置签到状态的循环任务"""
                while True:
                    try:
                        # 每小时检查一次是否需要重置签到状态
                        await self._daily_sign_in_reset()
                        # 等待1小时
                        await asyncio.sleep(3600)
                    except Exception as e:
                        self.logger.error(f"每日签到状态重置任务出错: {e}")
                        # 出错后等待1小时再重试
                        await asyncio.sleep(3600)
            
            # 启动定时任务（不阻塞初始化过程）
            asyncio.create_task(weekly_reset_task())
            asyncio.create_task(daily_sign_in_reset_task())
            self.logger.info("Rbot定时任务已启动（每周阅历重置 + 每日签到状态重置）")
            
        except Exception as e:
            self.logger.error(f"初始化Rbot定时任务失败: {e}")
    
    async def _setup_caches(self):
        """设置缓存和最终初始化状态
        
        完成插件初始化后的最终设置，包括缓存配置和状态标记。
        
        Raises:
            无特定异常抛出
            
        Returns:
            None: 无返回值
        """
        self.initialized = True
        
        # 插件初始化完成后，尝试启动定时任务
        if self.timer_manager and self.plugin_config.timer_enabled:
            try:
                self.logger.info("插件初始化完成，尝试启动定时任务...")
                # 确保unified_msg_origin映射表被正确传递
                if hasattr(self.timer_manager, 'push_service'):
                    self.timer_manager.push_service.group_unified_msg_origins = self.group_unified_msg_origins
                    self.logger.info(f"定时任务管理器已更新unified_msg_origin映射表: {list(self.group_unified_msg_origins.keys())}")
                else:
                    self.logger.warning("定时任务管理器未完全初始化，无法更新unified_msg_origin映射表")
                
                success = await self.timer_manager.update_config(self.plugin_config, self.group_unified_msg_origins)
                if success:
                    self.logger.info("定时任务启动成功")
                else:
                    self.logger.warning("定时任务启动失败，可能是因为群组unified_msg_origin尚未收集")
                    if self.plugin_config.timer_target_groups:
                        missing_groups = [g for g in self.plugin_config.timer_target_groups if g not in self.group_unified_msg_origins]
                        if missing_groups:
                            self.logger.info(f"缺少unified_msg_origin的群组: {missing_groups}")
                            self.logger.info("💡 提示: 在这些群组中发送任意消息以收集unified_msg_origin")
            except (ImportError, AttributeError, RuntimeError) as e:
                self.logger.warning(f"定时任务启动失败: {e}")
                # 不影响插件的正常使用
            except (ValueError, TypeError, ConnectionError, asyncio.TimeoutError, KeyError) as e:
                # 修复：替换过于宽泛的Exception为具体异常类型
                self.logger.warning(f"定时任务启动失败(参数错误): {e}")
                # 不影响插件的正常使用
    
    async def terminate(self):
        """插件卸载清理
        
        异步清理插件的所有资源,包括浏览器实例、缓存和临时文件.
        确保插件卸载时不会留下资源泄漏.
        
        Raises:
            OSError: 当清理文件或目录失败时抛出
            IOError: 当文件操作失败时抛出
            Exception: 其他清理相关的异常
            
        Returns:
            None: 无返回值,清理完成后设置initialized状态为False
            
        Example:
            >>> await plugin.terminate()
            >>> print(plugin.initialized)
            False
        """
        try:
            self.logger.info("群发言统计插件卸载中...")
            
            # 清理图片生成器
            if self.image_generator:
                await self.image_generator.cleanup()
            
            # 清理数据缓存
            await self.data_manager.clear_cache()
            
            # 清理群成员列表缓存
            self.group_members_cache.clear()
            self.logger.info("群成员列表缓存已清理")
            
            self.initialized = False
            self.logger.info("群发言统计插件卸载完成")
            
        except (OSError, IOError) as e:
            self.logger.error(f"插件卸载失败: {e}")
    
    # ========== 消息监听 ==========
    
    @filter.event_message_type(EventMessageType.ALL)
    async def auto_message_listener(self, event: AstrMessageEvent):
        """自动消息监听器 - 监听所有消息并记录群成员发言统计和Rbot功能"""
        # 检查是否启用了自动记录功能
        if not self.plugin_config or not getattr(self.plugin_config, 'auto_record_enabled', True):
            return
            
        # 获取基本信息
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        
        # 跳过非群聊或无效用户
        if not group_id or not user_id:
            return
        
        # 转换为字符串并跳过机器人
        group_id, user_id = str(group_id), str(user_id)
        if self._is_bot_message(event, user_id):
            return
        
        # 收集群组的unified_msg_origin（重要：用于定时推送）
        await self._collect_group_unified_msg_origin(event)
        
        # 获取消息内容
        message_str = getattr(event, 'message_str', '')
        
        # 检查是否是Rbot命令（不艾特机器人的情况）
        if self._is_rbot_enabled_for_group(group_id):
            # 处理Rbot命令
            await self._process_rbot_commands(event, group_id, user_id, message_str)
        
        # 跳过命令消息（以%或/开头）
        if message_str.startswith(('%', '/')):
            return
        
        # 获取用户昵称并记录统计
        nickname = await self._get_user_display_name(event, group_id, user_id)
        await self._record_message_stats(group_id, user_id, nickname)
        
        # Rbot功能：处理修为和阅历增加（仅在配置的群组中生效）
        if self._is_rbot_enabled_for_group(group_id):
            await self._process_rbot_message_rewards(group_id, user_id, nickname)
    
    def _is_bot_message(self, event: AstrMessageEvent, user_id: str) -> bool:
        """检查是否为机器人消息"""
        try:
            self_id = event.get_self_id()
            return self_id and user_id == str(self_id)
        except (AttributeError, KeyError, TypeError):
            return False
    
    async def _record_message_stats(self, group_id: str, user_id: str, nickname: str):
        """记录消息统计
        
        内部方法,用于记录群成员的消息统计数据.会自动验证输入参数并更新数据.
        
        Args:
            group_id (str): 群组ID,必须是5-12位数字字符串
            user_id (str): 用户ID,必须是1-20位数字字符串
            nickname (str): 用户昵称,会进行HTML转义和安全验证
            
        Raises:
            ValueError: 当参数验证失败时抛出
            TypeError: 当参数类型错误时抛出
            KeyError: 当数据格式错误时抛出
            
        Returns:
            None: 无返回值,记录结果通过日志输出
            
        Example:
            >>> await self._record_message_stats("123456789", "987654321", "用户昵称")
            # 将在数据管理器中更新该用户的发言统计
        """
        try:
            # 步骤1: 验证输入数据
            validated_data = await self._validate_message_data(group_id, user_id, nickname)
            group_id, user_id, nickname = validated_data
            
            # 步骤2: 处理消息统计和记录
            await self._process_message_stats(group_id, user_id, nickname)
            
        except ValueError as e:
            self.logger.error(f"记录消息统计失败(参数验证错误): {e}", exc_info=True)
        except TypeError as e:
            self.logger.error(f"记录消息统计失败(类型错误): {e}", exc_info=True)
        except KeyError as e:
            self.logger.error(f"记录消息统计失败(数据格式错误): {e}", exc_info=True)
        except asyncio.TimeoutError as e:
            self.logger.error(f"记录消息统计失败(超时错误): {e}", exc_info=True)
        except ConnectionError as e:
            self.logger.error(f"记录消息统计失败(连接错误): {e}", exc_info=True)
        except asyncio.CancelledError as e:
            self.logger.error(f"记录消息统计失败(操作取消): {e}", exc_info=True)
        except (IOError, OSError) as e:
            self.logger.error(f"记录消息统计失败(系统错误): {e}", exc_info=True)
        except AttributeError as e:
            self.logger.error(f"记录消息统计失败(属性错误): {e}", exc_info=True)
        except RuntimeError as e:
            self.logger.error(f"记录消息统计失败(运行时错误): {e}", exc_info=True)
        except ImportError as e:
            self.logger.error(f"记录消息统计失败(导入错误): {e}", exc_info=True)
        except (FileNotFoundError, PermissionError, UnicodeError, MemoryError, SystemError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"记录消息统计失败(系统资源错误): {e}", exc_info=True)
    
    async def _process_rbot_message_rewards(self, group_id: str, user_id: str, nickname: str):
        """处理Rbot功能的消息奖励（修为和阅历）
        
        Args:
            group_id (str): 群组ID
            user_id (str): 用户ID
            nickname (str): 用户昵称
        """
        try:
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                return
            
            # 获取用户数据
            user = await self.data_manager.get_user_in_group(group_id, user_id)
            
            if not user:
                # 如果用户不存在，创建新用户
                from .utils.models import UserData
                user = UserData(
                    user_id=user_id,
                    nickname=nickname,
                    message_count=0
                )
                # 保存新用户
                users = await self.data_manager.get_group_data(group_id)
                users.append(user)
                await self.data_manager.save_group_data(group_id, users)
            else:
                # 增加修为和阅历
                user.add_cultivation(1)  # 修为+1
                user.add_experience(1)   # 阅历+1
                
                # 保存用户数据 - 直接使用当前的用户列表，避免数据不一致
                users = await self.data_manager.get_group_data(group_id)
                await self.data_manager.save_group_data(group_id, users)
            
            # 只在开启详细日志时记录Rbot奖励
            if self.plugin_config and getattr(self.plugin_config, 'detailed_logging_enabled', True):
                self.logger.info(f"Rbot奖励: {nickname} 修为+1, 阅历+1")
                
        except Exception as e:
            self.logger.error(f"处理Rbot消息奖励失败: {e}", exc_info=True)
    
    @data_operation_handler('validate', '消息数据参数')
    async def _validate_message_data(self, group_id: str, user_id: str, nickname: str) -> tuple:
        """验证消息数据参数
        
        验证输入的群组ID、用户ID和昵称参数，确保数据格式正确。
        
        Args:
            group_id (str): 群组ID
            user_id (str): 用户ID
            nickname (str): 用户昵称
            
        Returns:
            tuple: 验证后的 (group_id, user_id, nickname) 元组
            
        Raises:
            ValueError: 当参数验证失败时抛出
            TypeError: 当参数类型错误时抛出
        """
        # 验证数据
        group_id = Validators.validate_group_id(group_id)
        user_id = Validators.validate_user_id(user_id)
        nickname = Validators.validate_nickname(nickname)
        
        return group_id, user_id, nickname
    
    async def _process_message_stats(self, group_id: str, user_id: str, nickname: str):
        """处理消息统计和记录
        
        执行实际的消息统计更新操作，并记录结果日志。
        
        Args:
            group_id (str): 验证后的群组ID
            user_id (str): 验证后的用户ID
            nickname (str): 验证后的用户昵称
            
        Raises:
            KeyError: 当数据格式错误时抛出
            asyncio.TimeoutError: 当异步操作超时时抛出
            ConnectionError: 当连接错误时抛出
            asyncio.CancelledError: 当操作取消时抛出
            IOError: 当文件操作错误时抛出
            OSError: 当系统操作错误时抛出
            AttributeError: 当属性访问错误时抛出
            RuntimeError: 当运行时错误时抛出
            ImportError: 当导入错误时抛出
            FileNotFoundError: 当文件未找到时抛出
            PermissionError: 当权限错误时抛出
            UnicodeError: 当编码错误时抛出
            MemoryError: 当内存错误时抛出
            SystemError: 当系统错误时抛出
        """
        # 直接使用data_manager更新用户消息
        success = await self.data_manager.update_user_message(group_id, user_id, nickname)
        
        if success:
            # 只在开启详细日志时记录消息统计
            if self.plugin_config.detailed_logging_enabled:
                self.logger.info(f"记录消息统计: {nickname}")
        else:
            self.logger.error(f"记录消息统计失败: {nickname}")
    
    # ========== 排行榜命令 ==========
    
    @filter.command("更新发言统计")
    async def update_message_stats(self, event: AstrMessageEvent):
        """手动更新发言统计"""
        try:
            # 使用AstrBot官方API获取群组ID和用户ID
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
                
            if not user_id:
                yield event.plain_result("无法获取用户信息！")
                return
            
            group_id = str(group_id)
            user_id = str(user_id)
            
            # 获取用户显示名称(优先使用群昵称)
            user_name = await self._get_user_display_name(event, group_id, user_id)
            
            # 记录当前用户的发言
            await self.data_manager.update_user_message(group_id, user_id, user_name)
            
            yield event.plain_result(f"已记录 {user_name} 的发言统计！")
            
        except AttributeError as e:
            self.logger.error(f"更新发言统计失败(属性错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except KeyError as e:
            self.logger.error(f"更新发言统计失败(数据格式错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except TypeError as e:
            self.logger.error(f"更新发言统计失败(类型错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error(f"更新发言统计失败(文件操作错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except ValueError as e:
            self.logger.error(f"更新发言统计失败(参数错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except RuntimeError as e:
            self.logger.error(f"更新发言统计失败(运行时错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
        except (ConnectionError, asyncio.TimeoutError, ImportError, PermissionError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"更新发言统计失败(网络或系统错误): {e}", exc_info=True)
            yield event.plain_result("更新发言统计失败,请稍后重试")
    
    @filter.command("发言榜")
    async def show_full_rank(self, event: AstrMessageEvent):
        """显示总排行榜"""
        async for result in self._show_rank(event, RankType.TOTAL):
            yield result
    
    @filter.command("水群榜")
    async def show_water_group_rank(self, event: AstrMessageEvent):
        """显示水群排行榜(发言榜别名)"""
        async for result in self._show_rank(event, RankType.TOTAL):
            yield result
    
    @filter.command("B话榜")
    async def show_bhua_rank(self, event: AstrMessageEvent):
        """显示B话排行榜(发言榜别名)"""
        async for result in self._show_rank(event, RankType.TOTAL):
            yield result
    
    @filter.command("今日发言榜")
    async def show_daily_rank(self, event: AstrMessageEvent):
        """显示今日排行榜"""
        async for result in self._show_rank(event, RankType.DAILY):
            yield result
    
    @filter.command("本周发言榜")
    async def show_weekly_rank(self, event: AstrMessageEvent):
        """显示本周排行榜"""
        async for result in self._show_rank(event, RankType.WEEKLY):
            yield result
    
    @filter.command("本月发言榜")
    async def show_monthly_rank(self, event: AstrMessageEvent):
        """显示本月排行榜"""
        async for result in self._show_rank(event, RankType.MONTHLY):
            yield result
    
    # ========== 设置命令 ==========
    
    @filter.command("设置发言榜数量")
    async def set_rank_count(self, event: AstrMessageEvent):
        """设置排行榜显示人数"""
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            if not args:
                yield event.plain_result("请指定数量！用法:#设置发言榜数量 10")
                return
            
            # 验证数量
            try:
                count = int(args[0])
                if count < self.RANK_COUNT_MIN or count > self.MAX_RANK_COUNT:
                    yield event.plain_result(f"数量必须在{self.RANK_COUNT_MIN}-{self.MAX_RANK_COUNT}之间！")
                    return
            except ValueError:
                yield event.plain_result("数量必须是数字！")
                return
            
            # 保存配置
            config = await self.data_manager.get_config()
            config.rand = count
            await self.data_manager.save_config(config)
            
            yield event.plain_result(f"排行榜显示人数已设置为 {count} 人！")
            
        except ValueError as e:
            self.logger.error(f"设置排行榜数量失败(参数错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except TypeError as e:
            self.logger.error(f"设置排行榜数量失败(类型错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except KeyError as e:
            self.logger.error(f"设置排行榜数量失败(数据格式错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error(f"设置排行榜数量失败(文件操作错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except AttributeError as e:
            self.logger.error(f"设置排行榜数量失败(属性错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except RuntimeError as e:
            self.logger.error(f"设置排行榜数量失败(运行时错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except (ConnectionError, asyncio.TimeoutError, ImportError, PermissionError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"设置排行榜数量失败(网络或系统错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")

    @filter.command("设置发言榜图片")
    async def set_image_mode(self, event: AstrMessageEvent):
        """设置排行榜的显示模式（图片或文字）
        
        根据用户输入的参数设置排行榜的显示模式：
        - 1/true/开/on/yes: 设置为图片模式
        - 0/false/关/off/no: 设置为文字模式
        
        返回相应的设置成功提示信息。
        """
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            if not args:
                yield event.plain_result("请指定模式！用法:#设置发言榜图片 1")
                return
            
            # 验证模式
            mode = args[0].lower()
            if mode in self.IMAGE_MODE_ENABLE_ALIASES:
                send_pic = 1
                mode_text = "图片模式"
            elif mode in self.IMAGE_MODE_DISABLE_ALIASES:
                send_pic = 0
                mode_text = "文字模式"
            else:
                yield event.plain_result("模式参数错误！可用:1/true/开 或 0/false/关")
                return
            
            # 保存配置
            config = await self.data_manager.get_config()
            config.if_send_pic = send_pic
            await self.data_manager.save_config(config)
            
            yield event.plain_result(f"排行榜显示模式已设置为 {mode_text}！")
            
        except ValueError as e:
            self.logger.error(f"设置图片模式失败(参数错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except TypeError as e:
            self.logger.error(f"设置图片模式失败(类型错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except KeyError as e:
            self.logger.error(f"设置图片模式失败(数据格式错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error(f"设置图片模式失败(文件操作错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except AttributeError as e:
            self.logger.error(f"设置图片模式失败(属性错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except RuntimeError as e:
            self.logger.error(f"设置图片模式失败(运行时错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
        except (ConnectionError, asyncio.TimeoutError, ImportError, PermissionError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"设置图片模式失败(网络或系统错误): {e}", exc_info=True)
            yield event.plain_result("设置失败,请稍后重试")
    
    @filter.command("清除发言榜单")
    async def clear_message_ranking(self, event: AstrMessageEvent):
        """清除发言榜单"""
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            group_id = str(group_id)
            
            success = await self.data_manager.clear_group_data(group_id)
            
            if success:
                yield event.plain_result("本群发言榜单已清除！")
            else:
                yield event.plain_result("清除榜单失败,请稍后重试！")
            
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error(f"清除榜单失败: {e}")
            yield event.plain_result("清除榜单失败,请稍后重试！")
    
    @filter.command("刷新发言榜群成员缓存")
    async def refresh_group_members_cache(self, event: AstrMessageEvent):
        """刷新群成员列表缓存"""
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            group_id = str(group_id)
            
            # 清除特定群的成员缓存
            cache_key = f"group_members_{group_id}"
            if cache_key in self.group_members_cache:
                del self.group_members_cache[cache_key]
                self.logger.info(f"刷新群 {group_id} 成员缓存")
                yield event.plain_result("群成员缓存已刷新！")
            else:
                yield event.plain_result("该群没有缓存的成员信息！")
            
        except AttributeError as e:
            self.logger.error(f"刷新群成员缓存失败(属性错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
        except KeyError as e:
            self.logger.error(f"刷新群成员缓存失败(数据格式错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
        except TypeError as e:
            self.logger.error(f"刷新群成员缓存失败(类型错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
        except (IOError, OSError) as e:
            self.logger.error(f"刷新群成员缓存失败(系统错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
        except RuntimeError as e:
            self.logger.error(f"刷新群成员缓存失败(运行时错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
        except (ConnectionError, asyncio.TimeoutError, ImportError, PermissionError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"刷新群成员缓存失败(网络或系统错误): {e}", exc_info=True)
            yield event.plain_result("刷新缓存失败,请稍后重试！")
    
    @filter.command("发言榜缓存状态")
    async def show_cache_status(self, event: AstrMessageEvent):
        """显示缓存状态"""
        try:
            # 获取数据管理器缓存统计
            cache_stats = await self.data_manager.get_cache_stats()
            
            # 获取群成员缓存信息
            members_cache_size = len(self.group_members_cache)
            members_cache_maxsize = self.group_members_cache.maxsize
            
            status_msg = [
                "📊 缓存状态报告",
                "━━━━━━━━━━━━━━",
                f"💾 数据缓存: {cache_stats['data_cache_size']}/{cache_stats['data_cache_maxsize']}",
                f"⚙️ 配置缓存: {cache_stats['config_cache_size']}/{cache_stats['config_cache_maxsize']}",
                f"👥 群成员缓存: {members_cache_size}/{members_cache_maxsize}",
                "━━━━━━━━━━━━━━",
                "🕐 数据缓存TTL: 5分钟",
                "🕐 配置缓存TTL: 1分钟", 
                "🕐 群成员缓存TTL: 5分钟"
            ]
            
            yield event.plain_result('\n'.join(status_msg))
            
        except ValueError as e:
            self.logger.error(f"显示缓存状态失败(参数错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except TypeError as e:
            self.logger.error(f"显示缓存状态失败(类型错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except KeyError as e:
            self.logger.error(f"显示缓存状态失败(数据格式错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except (IOError, OSError) as e:
            self.logger.error(f"显示缓存状态失败(系统错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except AttributeError as e:
            self.logger.error(f"显示缓存状态失败(属性错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except RuntimeError as e:
            self.logger.error(f"显示缓存状态失败(运行时错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
        except (ConnectionError, asyncio.TimeoutError, ImportError, PermissionError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"显示缓存状态失败(网络或系统错误): {e}", exc_info=True)
            yield event.plain_result("获取缓存状态失败,请稍后重试！")
    
    # ========== 私有方法 ==========
    
    async def _get_user_display_name(self, event: AstrMessageEvent, group_id: str, user_id: str) -> str:
        """获取用户的群昵称,优先使用群昵称,其次使用QQ昵称（重构版 - 跨平台兼容）"""
        # 优先使用统一的昵称获取逻辑
        nickname = await self._get_user_nickname_unified(event, group_id, user_id)
        
        # 如果统一逻辑失败，使用备用方案
        if nickname == f"用户{user_id}":
            return await self._get_fallback_nickname(event, user_id)
        
        return nickname
    
    @data_operation_handler('extract', '群成员昵称数据')
    def _get_display_name_from_member(self, member: Dict[str, Any]) -> Optional[str]:
        """从群成员信息中提取显示昵称
        
        提取用户昵称的辅助函数，避免重复的逻辑
        
        Args:
            member (Dict[str, Any]): 群成员信息字典
            
        Returns:
            Optional[str]: 用户的显示昵称，如果获取失败则返回None
        """
        return member.get("card") or member.get("nickname")

    async def _get_user_nickname_unified(self, event: AstrMessageEvent, group_id: str, user_id: str) -> str:
        """统一的用户昵称获取方法 - 重构版本
        
        使用扁平化的逻辑，拆分为独立的辅助方法：
        1. 从昵称缓存获取
        2. 从群成员字典缓存获取
        3. 从API获取并缓存
        4. 返回默认昵称
        
        Args:
            event (AstrMessageEvent): 消息事件对象
            group_id (str): 群组ID
            user_id (str): 用户ID
            
        Returns:
            str: 用户的显示昵称，如果都失败则返回 "用户{user_id}"
        """
        # 步骤1: 从昵称缓存获取
        nickname = await self._get_from_nickname_cache(user_id)
        if nickname:
            return nickname
        
        # 步骤2: 从群成员字典缓存获取
        nickname = await self._get_from_dict_cache(group_id, user_id)
        if nickname:
            return nickname
        
        # 步骤3: 从API获取并缓存
        nickname = await self._fetch_and_cache_from_api(event, group_id, user_id)
        if nickname:
            return nickname
        
        # 步骤4: 返回默认昵称
        return f"用户{user_id}"
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    async def _get_from_nickname_cache(self, user_id: str) -> Optional[str]:
        """从昵称缓存获取昵称"""
        nickname_cache_key = f"nickname_{user_id}"
        return self.user_nickname_cache.get(nickname_cache_key)
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    async def _get_from_dict_cache(self, group_id: str, user_id: str) -> Optional[str]:
        """从群成员字典缓存获取昵称"""
        dict_cache_key = f"group_members_dict_{group_id}"
        if dict_cache_key in self.group_members_cache:
            members_dict = self.group_members_cache[dict_cache_key]
            if user_id in members_dict:
                member = members_dict[user_id]
                display_name = self._get_display_name_from_member(member)
                if display_name:
                    # 缓存到昵称缓存
                    nickname_cache_key = f"nickname_{user_id}"
                    self.user_nickname_cache[nickname_cache_key] = display_name
                    return display_name
        return None
    
    async def _fetch_and_cache_from_api(self, event: AstrMessageEvent, group_id: str, user_id: str) -> Optional[str]:
        """从API获取群成员信息并缓存"""
        try:
            members_info = await self._fetch_group_members_from_api(event, group_id)
            if members_info:
                # 重建字典缓存
                dict_cache_key = f"group_members_dict_{group_id}"
                members_dict = {str(m.get("user_id", "")): m for m in members_info if m.get("user_id")}
                self.group_members_dict_cache[dict_cache_key] = members_dict
                
                # 查找用户
                if user_id in members_dict:
                    member = members_dict[user_id]
                    display_name = self._get_display_name_from_member(member)
                    if display_name:
                        # 缓存到昵称缓存
                        nickname_cache_key = f"nickname_{user_id}"
                        self.user_nickname_cache[nickname_cache_key] = display_name
                        return display_name
        except (AttributeError, KeyError, TypeError) as e:
            self.logger.warning(f"获取群成员信息失败(数据格式错误): {e}")
        except (ConnectionError, TimeoutError, OSError) as e:
            self.logger.warning(f"获取群成员信息失败(网络错误): {e}")
        except (ImportError, RuntimeError) as e:
            self.logger.warning(f"获取群成员信息失败(系统错误): {e}")
        
        return None
    
    async def _get_fallback_nickname(self, event: AstrMessageEvent, user_id: str) -> str:
        """获取备用昵称
        
        当无法从群成员列表获取昵称时的备用方案,使用事件对象中的发送者名称.
        
        Args:
            event (AstrMessageEvent): AstrBot消息事件对象
            user_id (str): 用户ID
            
        Returns:
            str: 用户的显示名称,如果获取失败则返回 "用户{user_id}" 格式
            
        Raises:
            AttributeError: 当事件对象缺少必要属性时抛出
            KeyError: 当数据格式错误时抛出
            TypeError: 当参数类型错误时抛出
            
        Example:
            >>> nickname = await self._get_fallback_nickname(event, "123456")
            >>> print(nickname)
            '用户123456'
        """
        try:
            nickname = event.get_sender_name()
            return nickname or f"用户{user_id}"
        except (AttributeError, KeyError, TypeError) as e:
            self.logger.error(f"获取备用昵称失败: {e}")
            return f"用户{user_id}"

    @exception_handler(ExceptionConfig(log_exception=True, reraise=False))
    def clear_user_cache(self, user_id: str = None):
        """清理用户缓存"""
        if user_id:
            # 清理特定用户的缓存
            nickname_cache_key = f"nickname_{user_id}"
            if nickname_cache_key in self.user_nickname_cache:
                del self.user_nickname_cache[nickname_cache_key]
        else:
            # 清理所有用户缓存
            self.user_nickname_cache.clear()
        
        self.logger.info(f"清理用户缓存: {user_id or '全部'}")
    
    async def _get_group_members_cache(self, event: AstrMessageEvent, group_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取群成员缓存"""
        cache_key = f"group_members_{group_id}"
        
        if cache_key in self.group_members_cache:
            cache_data = self.group_members_cache[cache_key]
            
            # 检查缓存是否过期
            import time
            if isinstance(cache_data, dict) and 'timestamp' in cache_data and 'ttl' in cache_data:
                if time.time() - cache_data['timestamp'] < cache_data['ttl']:
                    return cache_data['members']
                else:
                    # 缓存过期，删除
                    del self.group_members_cache[cache_key]
            else:
                # 兼容旧格式缓存
                return cache_data
        
        # 缓存未命中或已过期,从API获取
        return await self._fetch_group_members_from_api(event, group_id)
    
    async def _fetch_group_members_from_api(self, event: AstrMessageEvent, group_id: str) -> Optional[List[Dict[str, Any]]]:
        """从API获取群成员"""
        client = event.bot
        params = {"group_id": group_id}
        
        try:
            members_info = await client.api.call_action('get_group_member_list', **params)
            if members_info:
                # 缓存群成员列表,根据群大小设置不同的过期时间
                cache_key = f"group_members_{group_id}"
                
                # 对于大群(成员数>500),使用更长的缓存时间
                if len(members_info) > 500:
                    # 大群使用30分钟缓存，记录缓存时间戳
                    import time
                    cache_data = {
                        'members': members_info,
                        'timestamp': time.time(),
                        'ttl': 1800  # 30分钟
                    }
                    self.group_members_cache[cache_key] = cache_data
                    self.logger.info(f"群 {group_id} 成员数较多({len(members_info)}),已启用30分钟缓存策略")
                else:
                    # 普通群组使用5分钟缓存，记录缓存时间戳
                    import time
                    cache_data = {
                        'members': members_info,
                        'timestamp': time.time(),
                        'ttl': 300  # 5分钟
                    }
                    self.group_members_cache[cache_key] = cache_data
                
                return members_info
        except (AttributeError, KeyError, TypeError) as e:
            self.logger.warning(f"获取群成员列表失败(数据格式错误): {e}")
        except (ConnectionError, TimeoutError, OSError) as e:
            self.logger.warning(f"获取群成员列表失败(网络错误): {e}")
        except ImportError as e:
            self.logger.warning(f"获取群成员列表失败(导入错误): {e}")
        except RuntimeError as e:
            self.logger.warning(f"获取群成员列表失败(运行时错误): {e}")
        except ValueError as e:
            self.logger.warning(f"获取群成员列表失败(数据格式错误): {e}")
        
        return None

    async def _get_group_name(self, event: AstrMessageEvent, group_id: str) -> str:
        """获取群名称 - 改进版本"""
        try:
            # 首先尝试通过事件对象获取群组信息
            group_data = await event.get_group(group_id)
            if group_data:
                # 简化群名获取逻辑，直接尝试常用属性
                return getattr(group_data, 'group_name', None) or \
                       getattr(group_data, 'name', None) or \
                       getattr(group_data, 'title', None) or \
                       getattr(group_data, 'group_title', None) or \
                       f"群{group_id}"
            
            # 如果事件对象获取失败，尝试通过API获取
            try:
                if hasattr(event, 'bot') and hasattr(event.bot, 'api'):
                    group_info = await event.bot.api.call_action('get_group_info', group_id=group_id)
                    if group_info and isinstance(group_info, dict):
                        group_name = group_info.get('group_name') or group_info.get('group_title') or group_info.get('name')
                        if group_name:
                            return str(group_name).strip()
            except (ConnectionError, asyncio.TimeoutError, ValueError, TypeError, AttributeError) as api_error:
                # 修复：替换过于宽泛的Exception为具体异常类型
                self.logger.warning(f"通过API获取群组 {group_id} 名称失败: {api_error}")
            
            return f"群{group_id}"
        except (AttributeError, KeyError, TypeError, OSError) as e:
            self.logger.warning(f"获取群名称失败，使用默认名称: {e}")
            return f"群{group_id}"
    
    async def _show_rank(self, event: AstrMessageEvent, rank_type: RankType):
        """显示排行榜 - 重构版本"""
        try:
            # 准备数据
            rank_data = await self._prepare_rank_data(event, rank_type)
            if rank_data is None:
                yield event.plain_result("无法获取排行榜数据,请检查群组信息或稍后重试")
                return
            
            group_id, current_user_id, filtered_data, config, title, group_info = rank_data
            
            # 根据配置选择显示模式
            if config.if_send_pic:
                async for result in self._render_rank_as_image(event, filtered_data, group_info, title, current_user_id, config):
                    yield result
            else:
                async for result in self._render_rank_as_text(event, filtered_data, group_info, title, config):
                    yield result
        
        except (IOError, OSError) as e:
            self.logger.error(f"文件操作失败: {e}")
            yield event.plain_result("文件操作失败,请检查权限")
        except (AttributeError, KeyError, TypeError) as e:
            self.logger.error(f"数据格式错误: {e}")
            yield event.plain_result("数据格式错误,请联系管理员")
        except (ConnectionError, TimeoutError) as e:
            self.logger.error(f"网络请求失败: {e}")
            yield event.plain_result("网络请求失败,请稍后重试")
        except ImportError as e:
            self.logger.error(f"导入错误: {e}")
            yield event.plain_result("系统错误,请联系管理员")
        except RuntimeError as e:
            self.logger.error(f"运行时错误: {e}")
            yield event.plain_result("系统错误,请联系管理员")
        except ValueError as e:
            self.logger.error(f"数据格式错误: {e}")
            yield event.plain_result("数据格式错误,请联系管理员")
    
    async def _prepare_rank_data(self, event: AstrMessageEvent, rank_type: RankType):
        """准备排行榜数据"""
        # 获取群组ID和用户ID
        group_id = event.get_group_id()
        current_user_id = event.get_sender_id()
        
        if not group_id:
            return None
            
        if not current_user_id:
            return None
        
        group_id = str(group_id)
        current_user_id = str(current_user_id)
        
        # 获取群组数据
        group_data = await self.data_manager.get_group_data(group_id)
        
        if not group_data:
            return None
        
        # 根据类型筛选数据并获取排序值
        filtered_data_with_values = await self._filter_data_by_rank_type(group_data, rank_type)
        
        if not filtered_data_with_values:
            return None
        
        # 对数据进行排序
        filtered_data = sorted(filtered_data_with_values, key=lambda x: x[1], reverse=True)
        
        # 获取配置
        config = self.plugin_config
        
        # 生成标题
        title = self._generate_title(rank_type)
        
        # 创建群组信息
        group_info = GroupInfo(group_id=group_id)
        
        # 获取群名称
        group_name = await self._get_group_name(event, group_id)
        group_info.group_name = group_name
        
        return group_id, current_user_id, filtered_data, config, title, group_info
    
    async def _render_rank_as_image(self, event: AstrMessageEvent, filtered_data: List[tuple],
                                  group_info: GroupInfo, title: str, current_user_id: str, config: PluginConfig):
        """渲染排行榜为图片模式"""
        temp_path = None
        try:
            # 检查图片生成器是否可用
            if not self.image_generator or not hasattr(self.image_generator, 'browser') or not self.image_generator.browser:
                self.logger.warning("图片生成器未初始化或浏览器不可用，回退到文字模式")
                text_msg = self._generate_text_message(filtered_data, group_info, title, config)
                yield event.plain_result(text_msg)
                return
            
            # 提取用户数据用于图片生成，并应用人数限制
            # 先限制数量，再提取用户数据
            limited_data = filtered_data[:config.rand]
            users_for_image = []
            
            # 为用户数据设置display_total属性，确保图片生成器使用正确的数据
            # 修复：直接命令版排行榜图片显示错误数据的问题
            for user_data, count in limited_data:
                # 设置display_total属性（时间段内的发言数）
                user_data.display_total = count
                users_for_image.append(user_data)
            
            # 使用图片生成器
            temp_path = await self.image_generator.generate_rank_image(
                users_for_image, group_info, title, current_user_id
            )
            
            # 检查图片文件是否存在
            if await aiofiles.os.path.exists(temp_path):
                yield event.image_result(str(temp_path))
            else:
                # 回退到文字模式
                text_msg = self._generate_text_message(filtered_data, group_info, title, config)
                yield event.plain_result(text_msg)
                
        except (IOError, OSError, FileNotFoundError) as e:
            self.logger.error(f"生成图片失败: {e}")
            # 回退到文字模式
            text_msg = self._generate_text_message(filtered_data, group_info, title, config)
            yield event.plain_result(text_msg)
        except ImportError as e:
            self.logger.error(f"图片渲染失败(导入错误): {e}")
            # 回退到文字模式
            text_msg = self._generate_text_message(filtered_data, group_info, title, config)
            yield event.plain_result(text_msg)
        except RuntimeError as e:
            self.logger.error(f"图片渲染失败(运行时错误): {e}")
            # 回退到文字模式
            text_msg = self._generate_text_message(filtered_data, group_info, title, config)
            yield event.plain_result(text_msg)
        except ValueError as e:
            self.logger.error(f"图片渲染失败(数据格式错误): {e}")
            # 回退到文字模式
            text_msg = self._generate_text_message(filtered_data, group_info, title, config)
            yield event.plain_result(text_msg)
        except Exception as e:
            self.logger.error(f"图片渲染失败(未知错误): {e}")
            # 回退到文字模式
            text_msg = self._generate_text_message(filtered_data, group_info, title, config)
            yield event.plain_result(text_msg)
        finally:
            # 清理临时文件，避免资源泄漏
            if temp_path and await aiofiles.os.path.exists(temp_path):
                try:
                    await aiofiles.os.unlink(temp_path)
                except OSError as e:
                    self.logger.warning(f"清理临时图片文件失败: {temp_path}, 错误: {e}")
    
    async def _render_rank_as_text(self, event: AstrMessageEvent, filtered_data: List[tuple], 
                                 group_info: GroupInfo, title: str, config: PluginConfig):
        """渲染排行榜为文字模式"""
        text_msg = self._generate_text_message(filtered_data, group_info, title, config)
        yield event.plain_result(text_msg)
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _get_time_period_for_rank_type(self, rank_type: RankType) -> tuple:
        """获取排行榜类型对应的时间段
        
        Args:
            rank_type (RankType): 排行榜类型
            
        Returns:
            tuple: (start_date, end_date, period_name)，如果不需要时间段过滤则返回(None, None, None)
        """
        current_date = datetime.now().date()
        
        if rank_type == RankType.TOTAL:
            return None, None, "total"
        elif rank_type == RankType.DAILY:
            return current_date, current_date, "daily"
        elif rank_type == RankType.WEEKLY:
            # 获取本周开始日期(周一)
            days_since_monday = current_date.weekday()
            week_start = current_date - timedelta(days=days_since_monday)
            return week_start, current_date, "weekly"
        elif rank_type == RankType.MONTHLY:
            # 获取本月开始日期
            month_start = current_date.replace(day=1)
            return month_start, current_date, "monthly"
        else:
            return None, None, "unknown"
    
    async def _filter_data_by_rank_type(self, group_data: List[UserData], rank_type: RankType) -> List[tuple]:
        """根据排行榜类型筛选数据并计算时间段内的发言次数 - 性能优化版本"""
        start_date, end_date, period_name = self._get_time_period_for_rank_type(rank_type)
        
        if rank_type == RankType.TOTAL:
            # 总榜：返回每个用户及其总发言数的元组，但过滤掉从未发言的用户
            return [(user, user.message_count) for user in group_data if user.message_count > 0]
        
        # 时间段过滤：优化版本，使用预聚合策略减少双重循环
        # 策略：如果时间段较短（日榜），直接计算；如果时间段较长（周榜/月榜），使用缓存
        
        # 对于日榜，直接计算（因为时间段短，性能影响小）
        if rank_type == RankType.DAILY:
            return self._calculate_daily_rank(group_data, start_date, end_date)
        
        # 对于周榜和月榜，使用优化策略（现在是异步方法）
        elif rank_type in [RankType.WEEKLY, RankType.MONTHLY]:
            return await self._calculate_period_rank_optimized(group_data, start_date, end_date)
        
        return []
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _calculate_daily_rank(self, group_data: List[UserData], start_date, end_date) -> List[tuple]:
        """计算日榜（直接计算策略）"""
        filtered_users = []
        for user in group_data:
            if not user.history:
                continue
            
            # 计算指定时间段的发言次数
            period_count = user.get_message_count_in_period(start_date, end_date)
            if period_count > 0:
                filtered_users.append((user, period_count))
        
        return filtered_users
    
    async def _calculate_period_rank_optimized(self, group_data: List[UserData], start_date, end_date) -> List[tuple]:
        """计算周榜/月榜（优化策略）"""
        # 优化策略：先筛选出有历史记录的用户，然后批量计算
        active_users = [user for user in group_data if user.history]
        
        if not active_users:
            return []
        
        # 批量计算，减少函数调用开销
        filtered_users = []
        for user in active_users:
            # 使用更高效的计算方法（现在是异步方法）
            period_count = await self._count_messages_in_period_fast(user.history, start_date, end_date)
            if period_count > 0:
                filtered_users.append((user, period_count))
        
        return filtered_users
    
    async def _count_messages_in_period_fast(self, history: List, start_date, end_date) -> int:
        """快速计算指定时间段内的消息数量（优化版本）
        
        如果历史记录未排序，将自动排序后进行计算。
        对于已排序的记录，使用高效的早停算法。
        """
        # 如果历史记录为空，直接返回0
        if not history:
            return 0
        
        # 完整遍历检查列表是否真正有序，避免采样检查的误判问题
        is_sorted = True
        if len(history) > 1:
            try:
                # 完整遍历检查：确保列表真正有序（优化版本）
                for current_item, next_item in zip(history[:-1], history[1:]):
                    current_date = current_item.to_date() if hasattr(current_item, 'to_date') else current_item
                    next_date = next_item.to_date() if hasattr(next_item, 'to_date') else next_item
                    if current_date > next_date:
                        is_sorted = False
                        break
                        
            except (AttributeError, TypeError):
                # 如果无法比较，假设未排序
                is_sorted = False
        
        # 如果检测到列表确实有序，使用早停算法
        if is_sorted:
            count = 0
            for hist_date in history:
                # 转换为日期对象
                hist_date_obj = hist_date.to_date() if hasattr(hist_date, 'to_date') else hist_date
                
                # 检查是否在指定时间段内
                if hist_date_obj < start_date:
                    continue
                if hist_date_obj > end_date:
                    # 已排序，可以提前跳出循环
                    break
                count += 1
            
            return count
        
        # 如果检测到列表无序，直接使用无序版本计算
        else:
            return self._count_messages_in_period_unordered(history, start_date, end_date)
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _count_messages_in_period_unordered(self, history: List, start_date, end_date) -> int:
        """计算指定时间段内的消息数量（适用于未排序的历史记录）"""
        if not history:
            return 0
        
        count = 0
        for hist_date in history:
            hist_date_obj = hist_date.to_date() if hasattr(hist_date, 'to_date') else hist_date
            if start_date <= hist_date_obj <= end_date:
                count += 1
        
        return count
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _generate_title(self, rank_type: RankType) -> str:
        """生成标题"""
        now = datetime.now()
        
        if rank_type == RankType.TOTAL:
            return "总发言排行榜"
        elif rank_type == RankType.DAILY:
            return f"今日[{now.year}年{now.month}月{now.day}日]发言榜单"
        elif rank_type == RankType.WEEKLY:
            # 计算周数
            week_num = now.isocalendar().week
            return f"本周[{now.year}年{now.month}月第{week_num}周]发言榜单"
        elif rank_type == RankType.MONTHLY:
            return f"本月[{now.year}年{now.month}月]发言榜单"
        else:
            return "发言榜单"
    
    def _generate_text_message(self, users_with_values: List[tuple], group_info: GroupInfo, title: str, config: PluginConfig) -> str:
        """生成文字消息
        
        Args:
            users_with_values: 包含(UserData, sort_value)元组的列表
            group_info: 群组信息
            title: 排行榜标题
            config: 插件配置
            
        Returns:
            str: 格式化的文字消息
        """
        # 计算时间段内的总发言数
        total_messages = sum(sort_value for _, sort_value in users_with_values)
        
        # 数据已经在_show_rank中排好序，直接使用并限制数量
        top_users = users_with_values[:config.rand]
        
        msg = [f"{title}\n发言总数: {total_messages}\n━━━━━━━━━━━━━━\n"]
        
        for i, (user, user_messages) in enumerate(top_users):
            # 使用时间段内的发言数计算百分比
            percentage = ((user_messages / total_messages) * 100) if total_messages > 0 else 0
            msg.append(f"第{i + 1}名:{user.nickname}·{user_messages}次(占比{percentage:.2f}%)\n")
        
        return ''.join(msg)
    
    # ========== 定时功能管理命令 ==========
    
    @filter.command("发言榜定时状态")
    async def timer_status(self, event: AstrMessageEvent):
        """查看定时任务状态"""
        try:
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            
            # 构建状态信息
            status_lines = [
                "📊 定时任务状态",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "🔧 基础设置",
                f"┌─ 定时功能: {'✅ 已启用' if config.timer_enabled else '❌ 已禁用'}",
                f"├─ 推送时间: {config.timer_push_time}",
                f"├─ 排行榜类型: {self._get_rank_type_text(config.timer_rank_type)}",
                f"├─ 推送模式: {'图片' if config.if_send_pic else '文字'}",
                f"└─ 显示人数: {config.rand} 人",
                "",
                "🎯 目标群组"
            ]
            
            # 添加目标群组信息
            if config.timer_target_groups:
                for i, group_id in enumerate(config.timer_target_groups, 1):
                    origin_status = "✅" if str(group_id) in self.group_unified_msg_origins else "❌"
                    status_lines.append(f"┌─ {i}. {group_id} {origin_status}")
                
                # 添加unified_msg_origin说明
                status_lines.append("└─ 💡 unified_msg_origin状态: ✅已收集/❌未收集")
                status_lines.append("   (❌状态需在群组发送消息收集)")
            else:
                status_lines.append("┌─ ⚠️ 未设置任何目标群组")
                status_lines.append("└─ 💡 使用 #设置定时群组 添加群组")
            
            # 添加定时任务状态
            if self.timer_manager:
                timer_status = await self.timer_manager.get_status()
                status_lines.extend([
                    "",
                    "⏰ 任务状态",
                    f"┌─ 运行状态: {self._get_status_text(timer_status['status'])}",
                    f"├─ 下次推送: {timer_status['next_push_time'] or '未设置'}",
                    f"└─ 剩余时间: {timer_status['time_until_next'] or 'N/A'}"
                ])
            
            yield event.plain_result('\n'.join(status_lines))
            
        except (IOError, OSError, KeyError) as e:
            self.logger.error(f"获取定时状态失败: {e}")
            yield event.plain_result("获取定时状态失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"获取定时状态失败(运行时错误): {e}")
            yield event.plain_result("获取定时状态失败，请稍后重试！")
    
    @filter.command("手动推送发言榜")
    async def manual_push(self, event: AstrMessageEvent):
        """手动推送排行榜"""
        try:
            if not self.timer_manager:
                yield event.plain_result("定时管理器未初始化，无法执行手动推送！")
                return
            
            # 检查TimerManager是否有有效的context
            if not hasattr(self.timer_manager, 'context') or not self.timer_manager.context:
                yield event.plain_result("❌ 定时管理器未完全初始化！\n\n💡 可能的原因：\n• 插件初始化过程中出现异常\n• 上下文信息缺失\n\n🔧 解决方案：\n• 重启机器人或重新加载插件\n• 检查插件配置是否正确")
                return
            
            # 使用当前转换的配置而不是从文件读取
            config = self.plugin_config
            
            if not config.timer_target_groups:
                yield event.plain_result("未设置目标群组，请先使用 #设置定时群组 设置目标群组！")
                return
            
            # 执行手动推送
            yield event.plain_result("正在执行手动推送，请稍候...")
            
            success = await self.timer_manager.manual_push(config)
            
            if success:
                yield event.plain_result("✅ 手动推送执行成功！")
            else:
                yield event.plain_result("❌ 手动推送执行失败！\n\n💡 可能的原因：\n• 缺少 unified_msg_origin\n• 群组权限不足\n\n🔧 解决方案：\n• 在群组中发送任意消息以收集 unified_msg_origin\n• 检查机器人是否有群组发言权限")
            
        except (AttributeError, TypeError) as e:
            self.logger.error(f"处理手动推送请求失败: {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
        except (RuntimeError, ValueError, KeyError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理手动推送请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("设置发言榜定时时间")
    async def set_timer_time(self, event: AstrMessageEvent):
        """设置定时推送时间
        
        自动设置当前群组为定时群组并启用定时功能
        """
        try:
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            if not args:
                yield event.plain_result("请指定时间！用法:#设置定时时间 16:12")
                return
            
            time_str = args[0]
            
            # 验证时间格式
            if not self._validate_time_format(time_str):
                yield event.plain_result("时间格式错误！请使用 HH:MM 格式，例如：16:12")
                return
            
            # 获取当前群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取当前群组ID！")
                return
            
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            config.timer_push_time = time_str
            
            # 自动设置当前群组为定时群组
            if str(group_id) not in config.timer_target_groups:
                config.timer_target_groups.append(str(group_id))
            
            # 自动启用定时功能
            config.timer_enabled = True
            
            # 更新定时任务
            rank_type_text = self._get_rank_type_text(config.timer_rank_type)
            if self.timer_manager:
                success = await self.timer_manager.update_config(config, self.group_unified_msg_origins)
                if success:
                    yield event.plain_result(
                        f"✅ 定时推送设置完成！\n"
                        f"• 推送时间：{time_str}\n"
                        f"• 目标群组：{group_id}\n"
                        f"• 排行榜类型：{rank_type_text}\n"
                        f"• 状态：已启用\n\n"
                        f"💡 提示：如果推送失败，请在群组中发送任意消息以收集unified_msg_origin"
                    )
                else:
                    yield event.plain_result(
                        f"⚠️ 定时推送设置部分完成！\n"
                        f"• 推送时间：{time_str}\n"
                        f"• 目标群组：{group_id}\n"
                        f"• 排行榜类型：{rank_type_text}\n"
                        f"• 状态：配置保存成功，但定时任务启动失败\n\n"
                        f"💡 提示：如果推送失败，请在群组中发送任意消息以收集unified_msg_origin"
                    )
            else:
                yield event.plain_result(f"✅ 定时推送配置已保存！\n• 推送时间：{time_str}\n• 目标群组：{group_id}\n• 排行榜类型：{rank_type_text}\n• 状态：配置保存成功\n\n💡 提示：定时管理器未初始化，请检查插件配置")
            
        except ValueError as e:
            self.logger.error(f"处理设置定时时间请求失败: {e}")
            yield event.plain_result("时间格式错误，请使用 HH:MM 格式！")
        except (IOError, OSError) as e:
            self.logger.error(f"处理设置定时时间请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理设置定时时间请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("设置发言榜定时群组")
    async def set_timer_groups(self, event: AstrMessageEvent):
        """设置定时推送目标群组"""
        try:
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            if not args:
                yield event.plain_result("请指定群组ID！用法:#设置发言榜定时群组 123456789 987654321")
                return
            
            # 验证群组ID
            valid_groups = []
            for group_id in args:
                if group_id.isdigit() and len(group_id) >= 5:
                    valid_groups.append(group_id)
                else:
                    yield event.plain_result(f"群组ID格式错误: {group_id}，必须是5位以上数字")
                    return
            
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            config.timer_target_groups = valid_groups
            
            # 更新定时任务
            if self.timer_manager and config.timer_enabled:
                await self.timer_manager.update_config(config, self.group_unified_msg_origins)
            
            groups_text = "\n".join([f"   • {group_id}" for group_id in valid_groups])
            yield event.plain_result(f"✅ 定时推送目标群组已设置：\n{groups_text}")
            
        except ValueError as e:
            self.logger.error(f"处理设置定时群组请求失败: {e}")
            yield event.plain_result("群组ID格式错误，请输入有效的群组ID！")
        except (IOError, OSError) as e:
            self.logger.error(f"处理设置定时群组请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理设置定时群组请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("删除发言榜定时群组")
    async def remove_timer_groups(self, event: AstrMessageEvent):
        """删除定时推送目标群组"""
        try:
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            current_groups = config.timer_target_groups
            
            if not args:
                # 清空所有定时群组
                config.timer_target_groups = []
                
                # 更新定时任务
                if self.timer_manager and config.timer_enabled:
                    await self.timer_manager.update_config(config, self.group_unified_msg_origins)
                
                yield event.plain_result("✅ 已清空所有定时推送目标群组")
                return
            
            # 删除指定群组
            groups_to_remove = []
            invalid_groups = []
            
            for group_id in args:
                if group_id.isdigit() and len(group_id) >= 5:
                    groups_to_remove.append(group_id)
                else:
                    invalid_groups.append(group_id)
            
            if invalid_groups:
                yield event.plain_result(f"群组ID格式错误: {', '.join(invalid_groups)}，必须是5位以上数字")
                return
            
            # 从当前群组列表中移除指定群组
            remaining_groups = [group for group in current_groups if group not in groups_to_remove]
            
            # 保存配置
            config.timer_target_groups = remaining_groups
            await self.data_manager.save_config(config)
            
            # 更新定时任务
            if self.timer_manager and config.timer_enabled:
                await self.timer_manager.update_config(config, self.group_unified_msg_origins)
            
            if groups_to_remove:
                removed_text = "\n".join([f"   • {group_id}" for group_id in groups_to_remove])
                remaining_text = "\n".join([f"   • {group_id}" for group_id in remaining_groups]) if remaining_groups else "   无"
                yield event.plain_result(f"✅ 已删除定时推送目标群组：\n{removed_text}\n\n📋 剩余群组：\n{remaining_text}")
            else:
                yield event.plain_result("⚠️ 未找到要删除的群组")
            
        except ValueError as e:
            self.logger.error(f"处理删除定时群组请求失败: {e}")
            yield event.plain_result("群组ID格式错误，请输入有效的群组ID！")
        except (IOError, OSError) as e:
            self.logger.error(f"处理删除定时群组请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理删除定时群组请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("启用发言榜定时")
    async def enable_timer(self, event: AstrMessageEvent):
        """启用定时推送功能"""
        try:
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            
            # 检查配置
            if not config.timer_target_groups:
                yield event.plain_result("请先设置目标群组！用法:#设置定时群组 群组ID")
                return
            
            # 启用定时功能
            config.timer_enabled = True
            
            # 更新定时任务（使用update_config确保group_unified_msg_origins被正确传递）
            if self.timer_manager:
                # 检查TimerManager是否有有效的context
                if not hasattr(self.timer_manager, 'context') or not self.timer_manager.context:
                    yield event.plain_result("⚠️ 定时管理器未完全初始化！\n\n💡 可能的原因：\n• 插件初始化过程中出现异常\n• 上下文信息缺失\n\n🔧 解决方案：\n• 重启机器人或重新加载插件\n• 检查插件配置是否正确")
                    return
                
                success = await self.timer_manager.update_config(config, self.group_unified_msg_origins)
                if success:
                    yield event.plain_result("✅ 定时推送功能已启用！")
                else:
                    yield event.plain_result("⚠️ 定时推送功能启用失败，请检查配置！")
            else:
                yield event.plain_result("⚠️ 定时管理器未初始化！")
            
        except (IOError, OSError) as e:
            self.logger.error(f"处理启用定时请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理启用定时请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("禁用发言榜定时")
    async def disable_timer(self, event: AstrMessageEvent):
        """禁用定时推送功能"""
        try:
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            
            # 禁用定时功能
            config.timer_enabled = False
            
            # 停止定时任务
            if self.timer_manager:
                await self.timer_manager.stop_timer()
            
            yield event.plain_result("✅ 定时推送功能已禁用！")
            
        except (IOError, OSError) as e:
            self.logger.error(f"处理禁用定时请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理禁用定时请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    @filter.command("设置发言榜定时类型")
    async def set_timer_type(self, event: AstrMessageEvent):
        """设置定时推送的排行榜类型"""
        try:
            # 获取参数
            args = event.message_str.split()[1:] if hasattr(event, 'message_str') else []
            
            if not args:
                yield event.plain_result("请指定排行榜类型！用法:#设置定时类型 total/daily/week/month")
                return
            
            rank_type = args[0].lower()
            
            # 验证排行榜类型
            valid_types = ['total', 'daily', 'week', 'weekly', 'month', 'monthly']
            if rank_type not in valid_types:
                yield event.plain_result(f"排行榜类型错误！可用类型: {', '.join(valid_types)}")
                return
            
            # 获取当前配置（使用转换后的配置）
            config = self.plugin_config
            config.timer_rank_type = rank_type
            
            # 更新定时任务
            if self.timer_manager and config.timer_enabled:
                await self.timer_manager.update_config(config, self.group_unified_msg_origins)
            
            type_text = self._get_rank_type_text(rank_type)
            yield event.plain_result(f"✅ 定时推送排行榜类型已设置为 {type_text}！")
            
        except ValueError as e:
            self.logger.error(f"处理设置定时类型请求失败: {e}")
            yield event.plain_result("排行榜类型错误，请使用：total/daily/weekly/monthly")
        except (IOError, OSError) as e:
            self.logger.error(f"处理设置定时类型请求失败: {e}")
            yield event.plain_result("保存配置失败，请稍后重试！")
        except (RuntimeError, AttributeError, ValueError, TypeError, ConnectionError, asyncio.TimeoutError) as e:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"处理设置定时类型请求失败(运行时错误): {e}")
            yield event.plain_result("处理请求失败，请稍后重试！")
    
    # ========== 辅助方法 ==========
    
    def _handle_command_exception(self, event: AstrMessageEvent, operation_name: str, exception: Exception) -> bool:
        """公共的异常处理方法，减少代码重复
        
        Args:
            event: 消息事件对象
            operation_name: 操作名称，用于日志记录
            exception: 异常对象
            
        Returns:
            bool: 是否成功处理了异常
        """
        try:
            if isinstance(exception, (KeyError, TypeError)):
                self.logger.error(f"{operation_name}失败(数据格式错误): {exception}", exc_info=True)
                event.plain_result(f"{operation_name}失败，请稍后重试")
                return True
            elif isinstance(exception, (IOError, OSError, FileNotFoundError)):
                self.logger.error(f"{operation_name}失败(文件操作错误): {exception}", exc_info=True)
                event.plain_result(f"{operation_name}失败，请稍后重试")
                return True
            elif isinstance(exception, ValueError):
                self.logger.error(f"{operation_name}失败(参数错误): {exception}", exc_info=True)
                event.plain_result(f"{operation_name}失败，请稍后重试")
                return True
            elif isinstance(exception, RuntimeError):
                self.logger.error(f"{operation_name}失败(运行时错误): {exception}", exc_info=True)
                event.plain_result(f"{operation_name}失败，请稍后重试")
                return True
            else:
                self.logger.error(f"{operation_name}失败(未预期的错误类型 {type(exception).__name__}): {exception}", exc_info=True)
                event.plain_result(f"{operation_name}失败，请稍后重试")
                return True
        except (RuntimeError, AttributeError, ValueError, TypeError, KeyError) as handler_error:
            # 修复：替换过于宽泛的Exception为具体异常类型
            self.logger.error(f"异常处理器本身出错: {handler_error}", exc_info=True)
            return False
    
    def _log_operation_result(self, operation_name: str, success: bool, details: str = ""):
        """公共的操作结果日志记录方法，减少代码重复
        
        Args:
            operation_name: 操作名称
            success: 是否成功
            details: 详细信息
        """
        if success:
            self.logger.info(f"{operation_name}成功{details}")
        else:
            self.logger.warning(f"{operation_name}失败{details}")
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        status_mapping = {
            'stopped': '已停止',
            'running': '运行中',
            'error': '错误',
            'paused': '已暂停'
        }
        return status_mapping.get(status, status)
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _format_datetime(self, dt_str: str) -> str:
        """格式化日期时间"""
        if not dt_str:
            return '未设置'
        
        try:
            # 解析ISO格式的时间字符串
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%m月%d日 %H:%M')
        except (ValueError, TypeError):
            # 修复：替换过于宽泛的except:为具体异常类型
            return dt_str
    
    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _validate_time_format(self, time_str: str) -> bool:
        """验证时间格式"""
        import re
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))
    

    @exception_handler(ExceptionConfig(log_exception=True, reraise=True))
    def _get_rank_type_text(self, rank_type: str) -> str:
        """获取排行榜类型的中文描述
        
        Args:
            rank_type: 排行榜类型字符串
            
        Returns:
            str: 排行榜类型的中文描述
        """
        type_mapping = {
            'total': '总排行榜',
            'daily': '今日排行榜', 
            'week': '本周排行榜',
            'weekly': '本周排行榜',
            'month': '本月排行榜',
            'monthly': '本月排行榜'
        }
        return type_mapping.get(rank_type, rank_type)
    
    # ========== Rbot功能相关 ==========
    
    def _is_rbot_enabled_for_group(self, group_id: str) -> bool:
        """检查群组是否启用了Rbot功能
        
        Args:
            group_id (str): 群组ID
            
        Returns:
            bool: 是否启用Rbot功能
        """
        if not self.plugin_config.rbot_enabled:
            return False
        
        # 如果没有指定生效群组，则所有群组都启用
        if not self.plugin_config.rbot_enabled_groups:
            return True
        
        # 检查当前群组是否在生效群组列表中
        return str(group_id) in self.plugin_config.rbot_enabled_groups
    
    def _is_rbot_admin(self, user_id: str) -> bool:
        """检查用户是否是Rbot管理员
        
        Args:
            user_id (str): 用户ID
            
        Returns:
            bool: 是否是Rbot管理员
        """
        return str(user_id) in self.plugin_config.rbot_admin_users
    
    @filter.command("我要签到")
    async def rbot_sign_in(self, event: AstrMessageEvent):
        """Rbot签到功能"""
        try:
            # 获取群组ID和用户ID
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
                
            if not user_id:
                yield event.plain_result("无法获取用户信息！")
                return
            
            group_id = str(group_id)
            user_id = str(user_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                return  # 不响应，不显示错误信息
            
            # 获取用户显示名称
            user_name = await self._get_user_display_name(event, group_id, user_id)
            
            # 检查用户今天是否已经签到过
            has_signed_today = await self._get_sign_in_status(group_id, user_id)
            
            if has_signed_today:
                yield event.plain_result(f"{user_name} 今天已经签到过了，请明天再来！")
                return
            
            # 获取用户数据
            user = await self.data_manager.get_user_in_group(group_id, user_id)
            
            if not user:
                # 如果用户不存在，创建新用户
                from .utils.models import UserData
                user = UserData(
                    user_id=user_id,
                    nickname=user_name,
                    message_count=0
                )
                # 保存新用户
                users = await self.data_manager.get_group_data(group_id)
                users.append(user)
                await self.data_manager.save_group_data(group_id, users)
            
            # 执行签到
            success, message, stones_gain, cultivation_gain = user.sign_today()
            
            if success:
                # 标记用户今天已签到
                await self._set_sign_in_status(group_id, user_id, True)
                
                # 保存用户数据
                users = await self.data_manager.get_group_data(group_id)
                # 找到当前用户并更新
                for i, u in enumerate(users):
                    if u.user_id == user_id:
                        users[i] = user  # 使用更新后的用户对象
                        break
                await self.data_manager.save_group_data(group_id, users)
                
                yield event.plain_result(f"{user_name} {message}")
            else:
                yield event.plain_result(f"{user_name} {message}")
                
        except Exception as e:
            self.logger.error(f"Rbot签到功能出错: {e}", exc_info=True)
            yield event.plain_result("签到失败，请稍后重试")
    
    @filter.command("为狗子打call")
    async def rbot_sign_in_alt(self, event: AstrMessageEvent):
        """Rbot签到功能（别名）"""
        async for result in self.rbot_sign_in(event):
            yield result
    
    @filter.command("排行信息")
    async def rbot_rank_info(self, event: AstrMessageEvent):
        """查看排行信息"""
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                yield event.plain_result("本群未启用Rbot功能！")
                return
            
            # 排行信息不需要管理员权限，所有群成员都可以查看
            
            # 获取群组数据
            users = await self.data_manager.get_group_data(group_id)
            
            if not users:
                yield event.plain_result("本群暂无用户数据！")
                return
            
            # 按修为排序
            cultivation_sorted = sorted(users, key=lambda x: x.cultivation, reverse=True)
            
            # 按阅历排序
            experience_sorted = sorted(users, key=lambda x: x.experience, reverse=True)
            
            # 生成排行榜消息
            rank_msg = "🏆 修为排行榜 🏆\n━━━━━━━━━━━━━━\n"
            for i, user in enumerate(cultivation_sorted[:10], 1):
                rank_msg += f"🥇 第{i}名：{user.nickname} - {user.cultivation}修为\n"
            
            rank_msg += "\n📚 阅历排行榜 📚\n━━━━━━━━━━━━━━\n"
            for i, user in enumerate(experience_sorted[:10], 1):
                rank_msg += f"📖 第{i}名：{user.nickname} - {user.experience}阅历\n"
            
            yield event.plain_result(rank_msg)
            
        except Exception as e:
            self.logger.error(f"查看排行信息失败: {e}", exc_info=True)
            yield event.plain_result("查看排行信息失败，请稍后重试")
    
    @filter.command("查看修为排名")
    async def rbot_cultivation_rank(self, event: AstrMessageEvent):
        """查看修为排名"""
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                yield event.plain_result("本群未启用Rbot功能！")
                return
            
            # 检查是否是群管理员
            if not event.is_admin():
                yield event.plain_result("只有群管理员可以查看修为排名！")
                return
            
            # 获取群组数据
            users = await self.data_manager.get_group_data(group_id)
            
            if not users:
                yield event.plain_result("本群暂无用户数据！")
                return
            
            # 按修为排序
            sorted_users = sorted(users, key=lambda x: x.cultivation, reverse=True)
            
            # 生成排行榜消息
            rank_msg = "🏆 修为排行榜 🏆\n━━━━━━━━━━━━━━\n"
            for i, user in enumerate(sorted_users[:10], 1):
                # 添加排名图标
                if i == 1:
                    icon = "🥇"
                elif i == 2:
                    icon = "🥈"
                elif i == 3:
                    icon = "🥉"
                else:
                    icon = f"第{i}名"
                
                rank_msg += f"{icon}：{user.nickname} - {user.cultivation}修为\n"
            
            yield event.plain_result(rank_msg)
            
        except Exception as e:
            self.logger.error(f"查看修为排名失败: {e}", exc_info=True)
            yield event.plain_result("查看修为排名失败，请稍后重试")
    
    @filter.command("查看阅历排行")
    async def rbot_experience_rank(self, event: AstrMessageEvent):
        """查看阅历排行"""
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                yield event.plain_result("本群未启用Rbot功能！")
                return
            
            # 检查是否是群管理员
            if not event.is_admin():
                yield event.plain_result("只有群管理员可以查看阅历排行！")
                return
            
            # 获取群组数据
            users = await self.data_manager.get_group_data(group_id)
            
            if not users:
                yield event.plain_result("本群暂无用户数据！")
                return
            
            # 按阅历排序
            sorted_users = sorted(users, key=lambda x: x.experience, reverse=True)
            
            # 生成排行榜消息
            rank_msg = "📚 阅历排行榜 📚\n━━━━━━━━━━━━━━\n"
            for i, user in enumerate(sorted_users[:10], 1):
                # 添加排名图标
                if i == 1:
                    icon = "🥇"
                elif i == 2:
                    icon = "🥈"
                elif i == 3:
                    icon = "🥉"
                else:
                    icon = f"第{i}名"
                
                rank_msg += f"{icon}：{user.nickname} - {user.experience}阅历\n"
            
            yield event.plain_result(rank_msg)
            
        except Exception as e:
            self.logger.error(f"查看阅历排行失败: {e}", exc_info=True)
            yield event.plain_result("查看阅历排行失败，请稍后重试")
    
    @filter.command("查看个人信息")
    async def rbot_user_info(self, event: AstrMessageEvent):
        """查看个人信息"""
        try:
            # 获取群组ID和用户ID
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
                
            if not user_id:
                yield event.plain_result("无法获取用户信息！")
                return
            
            group_id = str(group_id)
            user_id = str(user_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                yield event.plain_result("本群未启用Rbot功能！")
                return
            
            # 获取用户数据
            user = await self.data_manager.get_user_in_group(group_id, user_id)
            
            if not user:
                # 如果用户不存在，创建新用户
                from .utils.models import UserData
                user = UserData(
                    user_id=user_id,
                    nickname=await self._get_user_display_name(event, group_id, user_id),
                    message_count=0
                )
                # 保存新用户
                users = await self.data_manager.get_group_data(group_id)
                users.append(user)
                await self.data_manager.save_group_data(group_id, users)
            
            # 生成个人信息消息
            info_msg = f"👤 {user.nickname} 的个人信息 👤\n"
            info_msg += "━━━━━━━━━━━━━━\n"
            info_msg += f"⚔️ 修为：{user.cultivation}\n"
            info_msg += f"📚 阅历：{user.experience}\n"
            info_msg += f"💎 积分：{user.points}\n"
            info_msg += f"💰 灵石：{user.spirit_stones}\n"
            info_msg += f"📅 签到天数：{user.total_sign_days}\n"
            info_msg += "━━━━━━━━━━━━━━\n"
            info_msg += "📖 功能帮助 📖\n"
            info_msg += "━━━━━━━━━━━━━━\n"
            info_msg += "✨ 签到功能：发送「我要签到」或「为狗子打call」\n"
            info_msg += "🔍 查询信息：发送「查看个人信息」\n"
            info_msg += "🏆 排行榜：发送「排行信息」\n"
            info_msg += "⚙️ 管理员功能：@用户 修为+100（设置修为）\n"
            info_msg += "⚙️ 管理员功能：@用户 阅历+100（设置阅历）\n"
            info_msg += "⚙️ 管理员功能：@用户 积分+100（设置积分）"
            
            yield event.plain_result(info_msg)
            
        except Exception as e:
            self.logger.error(f"查看个人信息失败: {e}", exc_info=True)
            yield event.plain_result("查看个人信息失败，请稍后重试")
    
    @filter.command("帮助")
    async def rbot_help(self, event: AstrMessageEvent):
        """Rbot功能帮助"""
        try:
            # 获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("无法获取群组信息,请在群聊中使用此命令！")
                return
            
            group_id = str(group_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                yield event.plain_result("本群未启用Rbot功能！")
                return
            
            # 生成帮助消息
            help_msg = "🤖 Rbot功能帮助 🤖\n"
            help_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            help_msg += "【群签到功能】\n"
            help_msg += "触发方式：任何群员发送「我要签到」或「为狗子打call」\n"
            help_msg += "功能效果：签到后灵石+5~10，修为+10\n"
            help_msg += "成功回复：本次签到成功，灵石+X，修为+X\n"
            help_msg += "失败回复：签到失败，请第二天再签到\n\n"
            
            help_msg += "【群回复记录】\n"
            help_msg += "触发方式：任何群员发一条信息\n"
            help_msg += "功能效果：修为+1，阅历+1（每周清理一次）\n"
            help_msg += "注意：Rbot不进行任何回复\n\n"
            
            help_msg += "【排行信息】\n"
            help_msg += "触发方式：群管理发送「查看修为排名」或「查看阅历排行」\n"
            help_msg += "功能效果：显示排行榜，每周阅历排行榜给予1~10名不同的灵石\n\n"
            
            help_msg += "【查询个人信息】\n"
            help_msg += "触发方式：任何群员发送「查看个人信息」\n"
            help_msg += "功能效果：显示个人修为、阅历、积分、灵石等信息\n\n"
            
            help_msg += "【修改修为阅历积分】\n"
            help_msg += "触发方式：@某个群员 修为XXX（如：@狗子 修为-1000）\n"
            help_msg += "设置方式：@某个群员 设置修为XXX（如：@狗子 设置修为1000）\n"
            help_msg += "权限要求：只能指定人员操作\n"
            help_msg += "回复示例：修改XX群员，修为XXX，当前修为XXX\n\n"
            
            help_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            help_msg += "💡 提示：所有功能都支持艾特机器人触发和关键词触发两种方式"
            
            yield event.plain_result(help_msg)
            
        except Exception as e:
            self.logger.error(f"显示Rbot帮助失败: {e}", exc_info=True)
            yield event.plain_result("显示帮助失败，请稍后重试")
    
    @filter.event_message_type(EventMessageType.ALL)
    async def rbot_admin_command_listener(self, event: AstrMessageEvent):
        """Rbot管理员命令监听器 - 处理@用户 修为/阅历/积分操作"""
        try:
            # 获取基本信息
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            # 跳过非群聊或无效用户
            if not group_id or not user_id:
                return
            
            group_id = str(group_id)
            user_id = str(user_id)
            
            # 检查群组是否启用了Rbot功能
            if not self._is_rbot_enabled_for_group(group_id):
                return
            
            # 获取消息内容
            message_str = getattr(event, 'message_str', '')
            
            # 跳过命令消息（以%或/开头）
            if message_str.startswith(('%', '/')):
                return
            
            # 检查是否包含@用户和修为/阅历/积分操作
            if '@' not in message_str or not any(keyword in message_str for keyword in ['修为', '阅历', '积分']):
                return
            
            # 获取消息中的@用户信息
            at_users = getattr(event, 'at_users', [])
            if not at_users:
                # 如果没有at_users属性，尝试从消息中解析
                import re
                at_matches = re.findall(r'@([^\s]+)', message_str)
                if not at_matches:
                    return
            else:
                # 使用at_users中的用户ID
                at_user_ids = [str(user.get('user_id', '')) for user in at_users if user.get('user_id')]
                if not at_user_ids:
                    return
            
            # 解析@用户和操作指令
            async for result in self._parse_admin_command(event, group_id, user_id, message_str):
                yield result
            
        except Exception as e:
            self.logger.error(f"Rbot管理员命令处理失败: {e}", exc_info=True)
    
    async def _parse_admin_command(self, event: AstrMessageEvent, group_id: str, admin_id: str, message_str: str):
        """解析管理员命令
        
        Args:
            event: 消息事件对象
            group_id: 群组ID
            admin_id: 管理员用户ID
            message_str: 消息内容
        """
        try:
            # 解析@用户和操作
            import re
            
            # 匹配模式：@用户名 修为+100 或 @用户名 设置修为100
            patterns = [
                r'@([^\s]+)\s+修为([+-]\d+)',  # @用户 修为+100
                r'@([^\s]+)\s+阅历([+-]\d+)',  # @用户 阅历+100
                r'@([^\s]+)\s+积分([+-]\d+)',  # @用户 积分+100
                r'@([^\s]+)\s+设置修为(\d+)',  # @用户 设置修为100
                r'@([^\s]+)\s+设置阅历(\d+)',  # @用户 设置阅历100
                r'@([^\s]+)\s+设置积分(\d+)',  # @用户 设置积分100
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message_str)
                if match:
                    target_name = match.group(1)
                    operation = match.group(0)
                    
                    # 执行操作
                    async for result in self._execute_admin_operation(event, group_id, target_name, operation):
                        yield result
                    break
                    
        except Exception as e:
            self.logger.error(f"解析管理员命令失败: {e}", exc_info=True)
    
    async def _execute_admin_operation(self, event: AstrMessageEvent, group_id: str, target_name: str, operation: str):
        """执行管理员操作
        
        Args:
            event: 消息事件对象
            group_id: 群组ID
            target_name: 目标用户名
            operation: 操作内容
        """
        try:
            # 获取操作者ID
            admin_id = event.get_sender_id()
            
            # 检查权限：只有群管理员或Rbot管理员才能执行操作
            if not event.is_admin() and not self._is_rbot_admin(str(admin_id)):
                yield event.plain_result("只有群管理员或Rbot管理员可以执行此操作！")
                return
            
            # 获取群组数据
            users = await self.data_manager.get_group_data(group_id)
            
            # 尝试获取@用户的用户ID
            at_users = getattr(event, 'at_users', [])
            target_user_id = None
            
            if at_users:
                # 从at_users中获取用户ID
                for user in at_users:
                    if user.get('user_id'):
                        target_user_id = str(user.get('user_id'))
                        break
            
            # 查找目标用户（优先使用用户ID，其次使用昵称）
            target_user = None
            if target_user_id:
                # 使用用户ID查找
                for user in users:
                    if user.user_id == target_user_id:
                        target_user = user
                        break
            
            if not target_user:
                # 使用昵称模糊匹配
                for user in users:
                    if target_name in user.nickname or user.nickname in target_name:
                        target_user = user
                        break
            
            if not target_user:
                yield event.plain_result(f"未找到用户：{target_name}")
                return
            
            # 解析操作类型和数值
            import re
            
            if '修为' in operation:
                if '+' in operation or '-' in operation:
                    # 增加或减少修为
                    match = re.search(r'修为([+-]\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.cultivation
                        target_user.add_cultivation(amount)
                        new_value = target_user.cultivation
                        action = "增加" if amount > 0 else "减少"
                        yield event.plain_result(f"⚔️ 修为调整：{target_user.nickname} {action}{abs(amount)}修为，当前修为：{new_value}")
                elif '设置修为' in operation:
                    # 设置修为
                    match = re.search(r'设置修为(\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.cultivation
                        target_user.cultivation = amount
                        new_value = target_user.cultivation
                        yield event.plain_result(f"⚔️ 修为设置：{target_user.nickname} 修为设置为{new_value}")
                        
            elif '阅历' in operation:
                if '+' in operation or '-' in operation:
                    # 增加或减少阅历
                    match = re.search(r'阅历([+-]\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.experience
                        target_user.add_experience(amount)
                        new_value = target_user.experience
                        action = "增加" if amount > 0 else "减少"
                        yield event.plain_result(f"📚 阅历调整：{target_user.nickname} {action}{abs(amount)}阅历，当前阅历：{new_value}")
                elif '设置阅历' in operation:
                    # 设置阅历
                    match = re.search(r'设置阅历(\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.experience
                        target_user.experience = amount
                        new_value = target_user.experience
                        yield event.plain_result(f"📚 阅历设置：{target_user.nickname} 阅历设置为{new_value}")
                        
            elif '积分' in operation:
                if '+' in operation or '-' in operation:
                    # 增加或减少积分
                    match = re.search(r'积分([+-]\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.points
                        target_user.add_points(amount)
                        new_value = target_user.points
                        action = "增加" if amount > 0 else "减少"
                        yield event.plain_result(f"💎 积分调整：{target_user.nickname} {action}{abs(amount)}积分，当前积分：{new_value}")
                elif '设置积分' in operation:
                    # 设置积分
                    match = re.search(r'设置积分(\d+)', operation)
                    if match:
                        amount = int(match.group(1))
                        old_value = target_user.points
                        target_user.points = amount
                        new_value = target_user.points
                        yield event.plain_result(f"💎 积分设置：{target_user.nickname} 积分设置为{new_value}")
            
            # 保存用户数据
            await self.data_manager.save_group_data(group_id, users)
            
        except Exception as e:
            self.logger.error(f"执行管理员操作失败: {e}", exc_info=True)
            yield event.plain_result("执行操作失败，请稍后重试")
    
    async def _get_sign_in_status(self, group_id: str, user_id: str) -> bool:
        """获取用户今天的签到状态
        
        Args:
            group_id (str): 群组ID
            user_id (str): 用户ID
            
        Returns:
            bool: 今天是否已签到
        """
        try:
            # 获取今天的日期字符串
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 获取签到状态文件
            sign_in_data = JsonHandler.读取Json字典("sign_in_status.json")
            
            # 构建键名：群组ID_用户ID_日期
            key = f"{group_id}_{user_id}_{today}"
            
            # 检查键是否存在或值为空
            if key not in sign_in_data or sign_in_data[key] is None:
                # 如果为空则存一个用户的false
                sign_in_data[key] = False
                JsonHandler.写入Json字典("sign_in_status.json", sign_in_data)
                return False
            
            # 返回签到状态，确保是布尔值
            return bool(sign_in_data[key])
            
        except Exception as e:
            self.logger.error(f"获取签到状态失败: {e}", exc_info=True)
            return False
    
    async def _set_sign_in_status(self, group_id: str, user_id: str, status: bool):
        """设置用户今天的签到状态
        
        Args:
            group_id (str): 群组ID
            user_id (str): 用户ID
            status (bool): 签到状态
        """
        try:
            # 获取今天的日期字符串
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 获取签到状态文件
            sign_in_data = JsonHandler.读取Json字典("sign_in_status.json")
            
            # 构建键名：群组ID_用户ID_日期
            key = f"{group_id}_{user_id}_{today}"
            
            # 设置签到状态
            sign_in_data[key] = status
            
            # 保存到文件
            JsonHandler.写入Json字典("sign_in_status.json", sign_in_data)
            
            self.logger.info(f"设置签到状态: {group_id}_{user_id} -> {status}")
            
        except Exception as e:
            self.logger.error(f"设置签到状态失败: {e}", exc_info=True)
    
    async def _daily_sign_in_reset(self):
        """每日重置签到状态的定时任务"""
        try:
            from datetime import datetime
            
            # 获取今天的日期字符串
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 检查是否已经执行过重置（避免一天内多次执行）
            reset_key = "last_sign_in_reset"
            
            # 从配置中获取上次重置日期
            config = await self.data_manager.get_config()
            last_reset_date = getattr(config, reset_key, None)
            
            if last_reset_date == today:
                return  # 今天已经重置过了
            
            # 清理过期的签到状态（保留最近7天的记录）
            sign_in_data = JsonHandler.读取Json字典("sign_in_status.json")
            
            # 计算保留的日期范围
            from datetime import timedelta
            keep_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            # 创建新的签到状态字典，只保留最近7天的记录
            new_sign_in_data = {}
            for key, value in sign_in_data.items():
                # 键格式：群组ID_用户ID_日期
                parts = key.split('_')
                if len(parts) >= 3:
                    date_part = parts[-1]
                    if date_part >= keep_date:
                        new_sign_in_data[key] = value
            
            # 保存清理后的签到状态
            JsonHandler.写入Json字典("sign_in_status.json", new_sign_in_data)
            
            # 更新最后重置日期
            setattr(config, reset_key, today)
            await self.data_manager.save_config(config)
            
            self.logger.info(f"每日签到状态重置完成，清理了过期数据")
            
        except Exception as e:
            self.logger.error(f"每日签到状态重置失败: {e}", exc_info=True)
    
    async def _weekly_experience_reset(self):
        """每周重置阅历的定时任务"""
        try:
            from datetime import datetime, timedelta
            
            # 获取当前星期几（0-6，0是周一）
            now = datetime.now()
            current_weekday = now.weekday()
            
            # 检查是否是重置日
            if current_weekday == self.plugin_config.rbot_weekly_reset_day:
                # 检查是否已经执行过重置（避免一天内多次执行）
                today_str = now.strftime("%Y-%m-%d")
                last_reset_key = "last_experience_reset"
                
                # 从配置中获取上次重置日期
                config = await self.data_manager.get_config()
                last_reset_date = getattr(config, last_reset_key, None)
                
                if last_reset_date == today_str:
                    return  # 今天已经重置过了
                
                # 获取所有群组
                all_groups = await self.data_manager.get_all_groups()
                
                reset_count = 0
                for group_id in all_groups:
                    # 检查群组是否启用了Rbot功能
                    if not self._is_rbot_enabled_for_group(group_id):
                        continue
                    
                    # 获取群组用户数据
                    users = await self.data_manager.get_group_data(group_id)
                    
                    if not users:
                        continue
                    
                    # 重置所有用户的阅历
                    for user in users:
                        if user.experience > 0:
                            user.reset_experience()
                            reset_count += 1
                    
                    # 保存群组数据
                    await self.data_manager.save_group_data(group_id, users)
                
                # 更新最后重置日期
                setattr(config, last_reset_key, today_str)
                await self.data_manager.save_config(config)
                
                self.logger.info(f"每周阅历重置完成，共重置 {reset_count} 个用户的阅历")
                
                # 给阅历排行榜前10名发放灵石奖励
                await self._give_weekly_rewards()
                
        except Exception as e:
            self.logger.error(f"每周阅历重置失败: {e}", exc_info=True)
    
    async def _give_weekly_rewards(self):
        """给阅历排行榜前10名发放灵石奖励"""
        try:
            # 获取所有启用了Rbot功能的群组
            all_groups = await self.data_manager.get_all_groups()
            
            for group_id in all_groups:
                # 检查群组是否启用了Rbot功能
                if not self._is_rbot_enabled_for_group(group_id):
                    continue
                
                # 获取群组用户数据
                users = await self.data_manager.get_group_data(group_id)
                
                if not users:
                    continue
                
                # 按阅历排序（重置前的值）
                sorted_users = sorted(users, key=lambda x: x.experience, reverse=True)
                
                # 给前10名发放灵石奖励
                rewards = [100, 80, 60, 50, 40, 30, 20, 15, 10, 5]  # 第1名100灵石，第10名5灵石
                
                # 准备获奖名单消息
                reward_msg = "🎉 每周阅历排行榜奖励发放 🎉\n━━━━━━━━━━━━━━\n"
                
                for i, user in enumerate(sorted_users[:10]):
                    if i < len(rewards):
                        user.add_spirit_stones(rewards[i])
                        # 添加排名图标
                        if i == 0:
                            rank_icon = "🥇"
                        elif i == 1:
                            rank_icon = "🥈"
                        elif i == 2:
                            rank_icon = "🥉"
                        else:
                            rank_icon = f"第{i+1}名"
                        
                        reward_msg += f"{rank_icon}：{user.nickname} 获得灵石+{rewards[i]} 💰\n"
                        self.logger.info(f"阅历奖励：{user.nickname} 获得灵石+{rewards[i]}（第{i+1}名）")
                
                # 保存群组数据
                await self.data_manager.save_group_data(group_id, users)
                
                # 发送获奖名单消息到群组
                await self._send_weekly_reward_message(group_id, reward_msg)
                
        except Exception as e:
            self.logger.error(f"发放每周阅历奖励失败: {e}", exc_info=True)
    
    async def _send_weekly_reward_message(self, group_id: str, message: str):
        """发送每周奖励消息到群组
        
        Args:
            group_id (str): 群组ID
            message (str): 要发送的消息
        """
        try:
            # 检查是否有该群组的unified_msg_origin
            if str(group_id) not in self.group_unified_msg_origins:
                self.logger.warning(f"无法发送奖励消息到群组 {group_id}：缺少unified_msg_origin")
                return
            
            # 获取unified_msg_origin
            unified_msg_origin = self.group_unified_msg_origins[str(group_id)]
            
            # 创建一个模拟的事件对象用于发送消息
            # 使用context.send_message发送消息
            await self.context.send_message(unified_msg_origin, message)
            
            self.logger.info(f"已发送每周奖励消息到群组 {group_id}")
            
        except Exception as e:
            self.logger.error(f"发送每周奖励消息失败: {e}", exc_info=True)
    
    async def _process_rbot_commands(self, event: AstrMessageEvent, group_id: str, user_id: str, message_str: str):
        """处理Rbot命令（不艾特机器人的情况）
        
        Args:
            event: 消息事件对象
            group_id: 群组ID
            user_id: 用户ID
            message_str: 消息内容
        """
        try:
            # 检查是否是Rbot命令
            if message_str in ["我要签到", "为狗子打call"]:
                # 处理签到命令
                # 检查用户今天是否已经签到过
                has_signed_today = await self._get_sign_in_status(group_id, user_id)
                
                if has_signed_today:
                    # 获取用户显示名称
                    user_name = await self._get_user_display_name(event, group_id, user_id)
                    # 使用主动消息发送API发送已签到消息
                    await self._send_active_message(event, f"{user_name} 今天已经签到过了，请明天再来！")
                else:
                    # 直接执行签到逻辑，避免重复调用导致延迟
                    await self._execute_sign_in(event, group_id, user_id)
                    
            elif message_str == "查看个人信息":
                # 处理查看个人信息命令
                async for result in self.rbot_user_info(event):
                    # 使用主动消息发送API
                    await self._send_active_message(event, result)
                    
            elif message_str == "查看修为排名":
                # 检查是否是群管理员
                if event.is_admin():
                    # 处理查看修为排名命令
                    async for result in self.rbot_cultivation_rank(event):
                        # 使用主动消息发送API
                        await self._send_active_message(event, result)
                        
            elif message_str == "查看阅历排行":
                # 检查是否是群管理员
                if event.is_admin():
                    # 处理查看阅历排行命令
                    async for result in self.rbot_experience_rank(event):
                        # 使用主动消息发送API
                        await self._send_active_message(event, result)
                        
            elif message_str == "帮助":
                # 处理帮助命令
                async for result in self.rbot_help(event):
                    # 使用主动消息发送API
                    await self._send_active_message(event, result)
                        
        except Exception as e:
            self.logger.error(f"处理Rbot命令失败: {e}", exc_info=True)
    
    async def _execute_sign_in(self, event: AstrMessageEvent, group_id: str, user_id: str):
        """执行签到操作（优化版本，提高响应速度）
        
        Args:
            event: 消息事件对象
            group_id: 群组ID
            user_id: 用户ID
        """
        try:
            # 获取用户显示名称
            user_name = await self._get_user_display_name(event, group_id, user_id)
            
            # 获取用户数据
            user = await self.data_manager.get_user_in_group(group_id, user_id)
            
            if not user:
                # 如果用户不存在，创建新用户
                from .utils.models import UserData
                user = UserData(
                    user_id=user_id,
                    nickname=user_name,
                    message_count=0
                )
                # 保存新用户
                users = await self.data_manager.get_group_data(group_id)
                users.append(user)
                await self.data_manager.save_group_data(group_id, users)
            
            # 执行签到
            success, message, stones_gain, cultivation_gain = user.sign_today()
            
            if success:
                # 标记用户今天已签到
                await self._set_sign_in_status(group_id, user_id, True)
                
                # 保存用户数据
                users = await self.data_manager.get_group_data(group_id)
                # 找到当前用户并更新
                for i, u in enumerate(users):
                    if u.user_id == user_id:
                        users[i] = user  # 使用更新后的用户对象
                        break
                await self.data_manager.save_group_data(group_id, users)
                
                # 直接发送消息，避免额外的处理延迟
                await self.context.send_message(event.unified_msg_origin, f"{user_name} {message}")
            else:
                # 直接发送消息，避免额外的处理延迟
                await self.context.send_message(event.unified_msg_origin, f"{user_name} {message}")
                
        except Exception as e:
            self.logger.error(f"执行签到操作失败: {e}", exc_info=True)
            # 直接发送消息，避免额外的处理延迟
            await self.context.send_message(event.unified_msg_origin, "签到失败，请稍后重试")
    
    async def _send_active_message(self, event: AstrMessageEvent, message_generator):
        """发送主动消息
        
        Args:
            event: 消息事件对象
            message_generator: 消息生成器
        """
        try:
            # 获取unified_msg_origin
            unified_msg_origin = event.unified_msg_origin
            
            # 检查message_generator是否是异步生成器
            if hasattr(message_generator, '__aiter__'):
                # 如果是异步生成器，遍历它
                async for result in message_generator:
                    # 处理每个结果
                    await self._process_message_result(result, unified_msg_origin)
            else:
                # 如果不是异步生成器，直接处理
                await self._process_message_result(message_generator, unified_msg_origin)
                
        except Exception as e:
            self.logger.error(f"发送主动消息失败: {e}", exc_info=True)
    
    async def _process_message_result(self, result, unified_msg_origin):
        """处理消息结果并发送
        
        Args:
            result: 消息结果对象
            unified_msg_origin: 消息发送目标
        """
        try:
            # 获取消息内容
            message_content = None
            
            # 检查result的类型并提取消息内容
            if hasattr(result, 'message_chain'):
                # 如果是消息链对象
                message_content = result.message_chain
            elif hasattr(result, 'chain'):
                # 如果有chain属性
                message_content = result.chain
            elif isinstance(result, str):
                # 如果是字符串
                message_content = result
            elif isinstance(result, list):
                # 如果是列表，尝试转换为字符串
                try:
                    # 尝试将列表中的元素连接成字符串
                    message_content = ''.join(str(item) for item in result)
                except Exception:
                    # 如果连接失败，转换为字符串
                    message_content = str(result)
            else:
                # 尝试转换为字符串
                message_content = str(result)
            
            # 使用context.send_message发送消息
            # 确保message_content是正确的消息链格式
            if isinstance(message_content, str):
                # 如果是字符串，直接发送字符串
                await self.context.send_message(unified_msg_origin, message_content)
            elif isinstance(message_content, list):
                # 如果是列表，尝试转换为字符串
                try:
                    message_str = ''.join(str(item) for item in message_content)
                    await self.context.send_message(unified_msg_origin, message_str)
                except Exception:
                    # 如果转换失败，尝试发送第一个元素
                    if message_content:
                        await self.context.send_message(unified_msg_origin, str(message_content[0]))
            else:
                # 如果是消息链对象，直接发送
                await self.context.send_message(unified_msg_origin, message_content)
                
        except Exception as e:
            self.logger.error(f"处理消息结果失败: {e}", exc_info=True)