"""
图片生成模块
负责将HTML模板转换为排行榜图片
"""

import asyncio
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import tempfile
import os
import traceback
import hashlib
import json
import uuid


from astrbot.api import logger as astrbot_logger

# 常量定义
IMAGE_WIDTH = 1200
VIEWPORT_HEIGHT = 1
BROWSER_TIMEOUT = 10000  # 毫秒
DEFAULT_FONT_SIZE = 14
ROW_HEIGHT = 30

# Jinja2模板引擎
try:
    from jinja2 import Template, Environment, select_autoescape, FileSystemLoader
    import html  # 用于HTML转义安全防护
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    astrbot_logger.warning("Jinja2未安装，将使用不安全的字符串拼接方式")

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    astrbot_logger.warning("Playwright未安装，图片生成功能将不可用")

from .models import UserData, GroupInfo, PluginConfig
from .exception_handlers import safe_generation, safe_file_operation




class ImageGenerationError(Exception):
    """图片生成异常
    
    当图片生成过程中发生错误时抛出的自定义异常。
    
    Attributes:
        message (str): 异常消息，描述具体的错误原因
        
    Example:
        >>> raise ImageGenerationError("Playwright未安装，无法生成图片")
    """
    pass


class ImageGenerator:
    """图片生成器
    
    负责将HTML模板转换为排行榜图片。支持Playwright浏览器自动化和Jinja2模板渲染。
    
    主要功能:
        - 使用Playwright浏览器生成高质量排行榜图片
        - 支持Jinja2模板引擎进行安全的HTML渲染
        - 自动调整页面高度和截图尺寸
        - 包含多层回退机制，确保在各种环境下都能正常工作
        - 支持当前用户高亮显示
        - 提供默认模板作为备用方案
        - 模板缓存机制，提高重复渲染效率
        
    Attributes:
        config (PluginConfig): 插件配置对象，包含生成参数
        browser (Optional[Browser]): Playwright浏览器实例
        page (Optional[Page]): Playwright页面实例
        playwright: Playwright实例
        logger: 日志记录器
        width (int): 图片宽度，默认1200像素
        timeout (int): 页面加载超时时间，默认10秒
        viewport_height (int): 视口高度，默认1像素
        template_path (Path): HTML模板文件路径
        jinja_env (Optional[Environment]): Jinja2环境对象
        _template_cache (Dict): 模板缓存字典
        _cache_lock (Lock): 缓存锁，确保线程安全
        
    Example:
        >>> generator = ImageGenerator(config)
        >>> await generator.initialize()
        >>> image_path = await generator.generate_rank_image(users, group_info, "排行榜")
    """
    
    def __init__(self, config: PluginConfig):
        """初始化图片生成器
        
        Args:
            config (PluginConfig): 插件配置对象，包含生成参数和设置
        """
        self.config = config
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.logger = astrbot_logger
        
        # 图片生成配置
        self.width = IMAGE_WIDTH
        self.timeout = BROWSER_TIMEOUT
        self.viewport_height = VIEWPORT_HEIGHT
        
        # 模板路径
        self.template_path = Path(__file__).parent.parent / "templates" / "rank_template.html"
        
        # 模板缓存机制
        self._template_cache: Dict[str, Any] = {}
        self._cache_lock = asyncio.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Jinja2环境将在initialize方法中初始化
        self.jinja_env = None
    

    
    async def _init_jinja2_env(self):
        """初始化Jinja2环境
        
        创建Jinja2模板环境，启用自动转义以防止XSS攻击。
        如果Jinja2不可用，将使用不安全的字符串拼接方式作为备用。
        添加模板缓存机制以提高性能。
        
        Returns:
            None: 无返回值，初始化结果通过日志输出
            
        Example:
            >>> await self._init_jinja2_env()
            # 将初始化Jinja2环境或记录警告信息
        """
        if JINJA2_AVAILABLE:
            try:
                # 创建Jinja2环境，启用自动转义和缓存，但不启用异步
                self.jinja_env = Environment(
                    autoescape=select_autoescape(['html', 'xml']),
                    trim_blocks=True,
                    lstrip_blocks=True,
                    cache_size=400  # 启用模板缓存，但不启用异步
                )
                
                # 预加载模板文件
                await self._preload_templates()
                
                self.logger.info("Jinja2环境初始化成功，模板缓存已启用")
            except Exception as e:
                self.logger.error(f"Jinja2环境初始化失败: {e}")
                self.jinja_env = None
        else:
            self.jinja_env = None
            self.logger.warning("Jinja2不可用，将使用不安全的字符串拼接")
    
    async def _preload_templates(self):
        """预加载模板文件到缓存"""
        try:
            if await aiofiles.os.path.exists(self.template_path):
                # 使用异步文件读取优化
                async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
                    template_content = await f.read()
                
                # 缓存模板内容
                template_hash = self._get_template_hash(template_content)
                async with self._cache_lock:
                    self._template_cache['main_template'] = {
                        'content': template_content,
                        'hash': template_hash,
                        'template': self.jinja_env.from_string(template_content) if self.jinja_env else None
                    }
                
                self.logger.info(f"模板预加载完成，缓存键: main_template")
            else:
                self.logger.warning(f"模板文件不存在: {self.template_path}")
        except Exception as e:
            self.logger.error(f"模板预加载失败: {e}")
    
    def _get_template_hash(self, content: str) -> str:
        """获取模板内容的哈希值，用于缓存验证"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def _get_cached_template(self) -> Optional[Union[str, Template]]:
        """获取缓存的模板"""
        async with self._cache_lock:
            cached = self._template_cache.get('main_template')
            if cached:
                self._cache_hits += 1
                return cached.get('template') if self.jinja_env else cached.get('content')
            else:
                self._cache_misses += 1
                return None
    
    async def _update_template_cache(self, content: str):
        """更新模板缓存"""
        try:
            template_hash = self._get_template_hash(content)
            async with self._cache_lock:
                self._template_cache['main_template'] = {
                    'content': content,
                    'hash': template_hash,
                    'template': self.jinja_env.from_string(content) if self.jinja_env else None
                }

        except Exception as e:
            self.logger.error(f"更新模板缓存失败: {e}")
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        async with self._cache_lock:
            return {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'total_requests': self._cache_hits + self._cache_misses,
                'hit_rate': self._cache_hits / max(1, self._cache_hits + self._cache_misses)
            }
    
    @safe_generation(default_return=None)
    async def initialize(self):
        """初始化图片生成器
        
        异步初始化Playwright浏览器和相关的渲染环境。
        包括启动浏览器实例和配置渲染参数。
        
        Raises:
            ImageGenerationError: 当Playwright未安装或初始化失败时抛出
            OSError: 当浏览器启动失败时抛出
            
        Returns:
            None: 无返回值，初始化成功后浏览器实例可用
            
        Example:
            >>> generator = ImageGenerator(config)
            >>> await generator.initialize()
            >>> print(generator.browser is not None)
            True
        """
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright未安装，图片生成功能将不可用")
            raise ImageGenerationError("Playwright未安装，无法生成图片")
        
        try:
            self.logger.info("开始初始化图片生成器...")
            
            # 首先初始化Jinja2环境
            await self._init_jinja2_env()
            
            self.playwright = await async_playwright().start()
            self.logger.info("Playwright启动成功")
            
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-extensions"
                ]
            )
            self.logger.info("Chromium浏览器启动成功")
            
            self.logger.info("图片生成器初始化完成")
        except FileNotFoundError as e:
            self.logger.error(f"浏览器可执行文件未找到: {e}")
            self.logger.error("💡 提示: 请运行 'playwright install' 命令安装浏览器")
            raise ImageGenerationError(f"浏览器未安装或路径错误: {e}")
        except PermissionError as e:
            self.logger.error(f"启动浏览器权限不足: {e}")
            raise ImageGenerationError(f"权限不足，无法启动浏览器: {e}")
        except ConnectionError as e:
            self.logger.error(f"浏览器连接失败: {e}")
            raise ImageGenerationError(f"浏览器连接失败: {e}")
        except OSError as e:
            # 捕获操作系统相关错误，如系统资源不足、进程启动失败等
            self.logger.error(f"初始化图片生成器失败: {e}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            # 检查是否是Playwright浏览器未安装的错误
            if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
                self.logger.error("💡 提示: 请运行 'playwright install' 命令安装浏览器")
                self.logger.error("📝 安装完成后重启机器人即可使用图片生成功能")
            raise ImageGenerationError(f"初始化失败: {e}")
    
    async def cleanup(self):
        """清理资源
        
        异步清理图片生成器的所有资源，包括浏览器实例、页面和Playwright对象。
        确保资源正确释放，避免内存泄漏。
        
        Raises:
            Exception: 当清理过程中发生错误时抛出
            
        Returns:
            None: 无返回值，清理完成后所有资源将被释放
            
        Example:
            >>> await generator.cleanup()
            >>> print(generator.browser is None)
            True
        """
        try:
            if self.page:
                await self.page.close()
                self.page = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            
            self.logger.info("图片生成器资源已清理")
        
        except ConnectionError as e:
            self.logger.error(f"浏览器连接错误: {e}")
        except Exception as e:
            self.logger.error(f"清理图片生成器资源失败: {e}")
    
    @safe_generation(default_return=None)
    async def generate_rank_image(self, 
                                 users: List[UserData], 
                                 group_info: GroupInfo, 
                                 title: str,
                                 current_user_id: Optional[str] = None) -> str:
        """生成排行榜图片"""
        if not self.browser:
            await self.initialize()
        
        temp_path = None
        
        try:
            # 创建页面
            self.page = await self.browser.new_page()
            
            # 设置视口
            await self.page.set_viewport_size({"width": self.width, "height": self.viewport_height})
            
            # 生成HTML内容
            html_content = await self._generate_html(users, group_info, title, current_user_id)
            
            # 设置页面内容
            await self.page.set_content(html_content, wait_until="networkidle")
            
            # 等待页面加载完成
            await self.page.wait_for_timeout(2000)
            
            # 动态调整页面高度
            body_height = await self.page.evaluate("document.body.scrollHeight")
            await self.page.set_viewport_size({"width": self.width, "height": body_height})
            
            # 生成临时文件路径（异步方式）
            temp_filename = f"rank_image_{uuid.uuid4().hex}.png"
            temp_path = Path(tempfile.gettempdir()) / temp_filename
            
            # 截图
            await self.page.screenshot(path=temp_path, full_page=True)
            
            return str(temp_path)
        
        except FileNotFoundError as e:
            self.logger.error(f"临时文件或资源未找到: {e}")
            raise ImageGenerationError(f"文件资源未找到: {e}")
        except PermissionError as e:
            self.logger.error(f"权限错误: {e}")
            raise ImageGenerationError(f"权限不足: {e}")
        except TimeoutError as e:
            self.logger.error(f"浏览器操作超时: {e}")
            raise ImageGenerationError(f"操作超时: {e}")
        except RuntimeError as e:
            # 捕获浏览器运行时错误，如页面渲染失败、JavaScript执行错误等
            self.logger.error(f"生成排行榜图片失败: {e}")
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            raise ImageGenerationError(f"生成图片失败: {e}")
        
        finally:
            if self.page:
                await self.page.close()
                self.page = None
            
            # 注意：不在这里删除临时文件，让调用方负责清理
            # 以避免在返回路径后立即删除文件的问题
    
    @safe_generation(default_return="")
    async def _generate_html(self, 
                      users: List[UserData], 
                      group_info: GroupInfo, 
                      title: str,
                      current_user_id: Optional[str] = None) -> str:
        """生成HTML内容（优化版本）"""
        if not users:
            return await self._generate_empty_html(group_info, title)
        
        # 使用批量处理优化性能
        processed_data = self._process_user_data_batch(users, current_user_id)
        
        # 计算统计数据
        total_messages = processed_data['total_messages']
        
        # 生成完整HTML
        html_template = await self._load_html_template()
        
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备模板数据（使用字典构建优化）
        template_data = {
            'group_name': self._escape_html_safe(group_info.group_name or f"群{group_info.group_id}"),
            'group_id': self._escape_html_safe(str(group_info.group_id)),
            'title': self._escape_html_safe(title),
            'total_messages': self._escape_html_safe(str(total_messages)),
            'user_count': self._escape_html_safe(str(len(users))),
            'current_time': self._escape_html_safe(current_time)
        }
        
        # 生成HTML内容（优化渲染逻辑）
        return await self._render_html_template(html_template, template_data, processed_data['user_items'])
    
    def _process_user_data_batch(self, users: List[UserData], current_user_id: Optional[str]) -> Dict[str, Any]:
        """批量处理用户数据，优化性能"""
        if not users:
            return {'total_messages': 0, 'user_items': []}
        
        # 预计算统计数据 - 使用时间段内的发言数
        total_messages = sum(getattr(user, 'display_total', user.message_count) for user in users)
        
        # 批量生成用户项目
        user_items = []
        current_user_found = False
        
        # 使用列表推导式优化性能
        for i, user in enumerate(users):
            is_current_user = current_user_id and user.user_id == current_user_id
            if is_current_user:
                current_user_found = True
            
            # 使用时间段内的发言数
            user_messages = getattr(user, 'display_total', user.message_count)
            user_items.append({
                'rank': i + 1,
                'nickname': user.nickname,
                'avatar_url': self._get_avatar_url(user.user_id, "qq"),
                'total': user_messages,
                'percentage': (user_messages / total_messages * 100) if total_messages > 0 else 0,
                'last_date': user.last_date or "未知",
                'is_current_user': is_current_user,
                'is_separator': False
            })
        
        # 如果当前用户不在排行榜中，添加到末尾
        if current_user_id and not current_user_found:
            current_user_data = next((user for user in users if user.user_id == current_user_id), None)
            if current_user_data:
                # 使用时间段内的发言数计算排名
                current_user_messages = getattr(current_user_data, 'display_total', current_user_data.message_count)
                current_rank = sum(1 for user in users if getattr(user, 'display_total', user.message_count) > current_user_messages) + 1
                user_items.append({
                    'rank': current_rank,
                    'nickname': current_user_data.nickname,
                    'avatar_url': self._get_avatar_url(current_user_data.user_id, "qq"),
                    'total': current_user_messages,
                    'percentage': (current_user_messages / total_messages * 100) if total_messages > 0 else 0,
                    'last_date': current_user_data.last_date or "未知",
                    'is_current_user': True,
                    'is_separator': True
                })
        
        return {
            'total_messages': total_messages,
            'user_items': user_items
        }
    
    async def _render_html_template(self, template_content: str, template_data: Dict[str, Any], user_items: List[Dict[str, Any]]) -> str:
        """优化的HTML模板渲染方法"""
        try:
            if JINJA2_AVAILABLE and self.jinja_env:
                # 使用缓存的模板
                cached_template = await self._get_cached_template()
                if cached_template and isinstance(cached_template, Template):
                    template_data['user_items'] = user_items
                    return cached_template.render(**template_data)
                else:
                    # 动态创建模板
                    template = self.jinja_env.from_string(template_content)
                    template_data['user_items'] = user_items
                    return template.render(**template_data)
            else:
                # Jinja2不可用时，使用纯占位符回退模板
                fallback_template = await self._get_fallback_template()
                return self._render_fallback_template(fallback_template, template_data, user_items)
        except ValueError as e:
            self.logger.error(f"HTML模板渲染失败，模板数据值错误: {e}")
            # 使用安全的备用方法
            fallback_template = await self._get_fallback_template()
            return self._render_fallback_template(fallback_template, template_data, user_items)
        except TypeError as e:
            self.logger.error(f"HTML模板渲染失败，模板数据类型错误: {e}")
            # 使用安全的备用方法
            fallback_template = await self._get_fallback_template()
            return self._render_fallback_template(fallback_template, template_data, user_items)
        except KeyError as e:
            self.logger.error(f"HTML模板渲染失败，模板键错误: {e}")
            # 使用安全的备用方法
            fallback_template = await self._get_fallback_template()
            return self._render_fallback_template(fallback_template, template_data, user_items)
        except PermissionError as e:
            self.logger.error(f"HTML模板渲染失败，权限错误: {e}")
            # 使用安全的备用方法
            fallback_template = await self._get_fallback_template()
            return self._render_fallback_template(fallback_template, template_data, user_items)
        except UnicodeDecodeError as e:
            # 捕获模板文件编码错误，如UTF-8解码失败、字符编码问题等
            self.logger.error(f"HTML模板渲染失败，编码错误: {e}")
            # 使用安全的备用方法
            fallback_template = await self._get_fallback_template()
            return self._render_fallback_template(fallback_template, template_data, user_items)
    
    def _render_fallback_template(self, template_content: str, template_data: Dict[str, Any], user_items: List[Dict[str, Any]]) -> str:
        """回退模板渲染方法（安全版本）
        
        当Jinja2不可用时的安全回退方案。
        使用简单的字符串替换而不是format()，避免Jinja2语法冲突。
        """
        # 使用生成器表达式优化内存使用
        user_items_html = ''.join(self._generate_user_item_html_safe(item) for item in user_items)
        
        # 安全替换：避免Jinja2语法冲突
        safe_content = template_content
        for key, value in template_data.items():
            if isinstance(value, str):
                # 对字符串值进行HTML转义
                safe_value = self._escape_html_safe(value)
                safe_content = safe_content.replace('{{' + key + '}}', safe_value)
            else:
                # 对于非字符串值，直接替换
                safe_content = safe_content.replace('{{' + key + '}}', str(value))
        
        # 替换user_items
        safe_content = safe_content.replace('{{user_items}}', user_items_html)
        
        return safe_content
    
    async def _generate_empty_html(self, group_info: GroupInfo, title: str) -> str:
        """生成空数据HTML（优化版本）"""
        # 尝试从缓存获取空数据模板
        empty_template_cache_key = 'empty_template'
        async with self._cache_lock:
            cached_empty = self._template_cache.get(empty_template_cache_key)
        
        if cached_empty:
            template_content = cached_empty['content']
            template_obj = cached_empty.get('template')
        else:
            # 创建空数据模板
            template_content = await self._get_empty_template()
            async with self._cache_lock:
                self._template_cache[empty_template_cache_key] = {
                    'content': template_content,
                    'template': self.jinja_env.from_string(template_content) if self.jinja_env else None
                }
            template_obj = self._template_cache[empty_template_cache_key].get('template')
        
        # 准备模板数据
        template_data = {
            'group_name': self._escape_html_safe(group_info.group_name or f"群{group_info.group_id}"),
            'group_id': self._escape_html_safe(str(group_info.group_id)),
            'title': self._escape_html_safe(title)
        }
        
        try:
            if JINJA2_AVAILABLE and self.jinja_env and template_obj:
                return template_obj.render(**template_data)
            else:
                # 使用安全的字符串替换而不是format()
                safe_content = template_content
                for key, value in template_data.items():
                    if isinstance(value, str):
                        safe_value = self._escape_html_safe(value)
                        safe_content = safe_content.replace('{{' + key + '}}', safe_value)
                    else:
                        safe_content = safe_content.replace('{{' + key + '}}', str(value))
                return safe_content
        except ValueError as e:
            self.logger.error(f"空数据HTML模板渲染失败，模板数据值错误: {e}")
            # 回退到最简单的HTML
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""
        except TypeError as e:
            self.logger.error(f"空数据HTML模板渲染失败，模板数据类型错误: {e}")
            # 回退到最简单的HTML
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""
        except KeyError as e:
            self.logger.error(f"空数据HTML模板渲染失败，模板键错误: {e}")
            # 回退到最简单的HTML
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""
        except PermissionError as e:
            self.logger.error(f"空数据HTML模板渲染失败，权限错误: {e}")
            # 回退到最简单的HTML
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""
        except UnicodeDecodeError as e:
            # 捕获空数据模板编码错误，如UTF-8解码失败、字符编码问题等
            self.logger.error(f"空数据HTML模板渲染失败，编码错误: {e}")
            # 回退到最简单的HTML
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""
    
    async def _get_empty_template(self) -> str:
        """获取空数据模板（简化版本）"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            margin: 0;
            padding: 40px;
            text-align: center;
        }
        .container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 60px;
            max-width: 600px;
            margin: 0 auto;
        }
        .title {
            font-size: 32px;
            color: #1F2937;
            margin-bottom: 20px;
        }
        .subtitle {
            font-size: 24px;
            color: #6B7280;
            margin-bottom: 40px;
        }
        .empty-text {
            font-size: 18px;
            color: #9CA3AF;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="title">{{ group_name }}[{{ group_id }}]</div>
        <div class="subtitle">{{ title }}</div>
        <div class="empty-text">
            暂无发言数据
            <br>
            期待大家的活跃发言！
        </div>
    </div>
</body>
</html>"""
    
    def _generate_user_item_html_safe(self, item_data: Dict[str, Any]) -> str:
        """生成安全的用户条目HTML（使用Jinja2模板）"""
        # 使用元组和字典预构建减少字符串操作
        css_classes = self._get_css_classes(item_data)
        styles = self._get_item_styles(item_data)
        safe_content = self._get_safe_content(item_data)
        
        # 准备模板数据
        template_data = {
            'rank': item_data['rank'],
            'total': item_data['total'],
            'percentage': item_data['percentage'],
            'css_classes': css_classes,
            'styles': styles,
            'safe_content': safe_content
        }
        
        # 使用Jinja2模板渲染，确保所有动态内容都经过转义
        if JINJA2_AVAILABLE:
            try:
                if not hasattr(self, '_user_item_macro_template'):
                    self._user_item_macro_template = self._load_user_item_macro_template()
                
                if self._user_item_macro_template:
                    return self._user_item_macro_template.render(item_data=template_data)
            except Exception as e:
                self.logger.warning(f"Jinja2模板渲染失败，使用备用方案: {e}")
        
        # 备用方案：使用更安全的字符串拼接方式
        # 对所有动态内容进行HTML转义
        safe_nickname = html.escape(safe_content['nickname'])
        safe_avatar_url = html.escape(safe_content['avatar_url'])
        safe_last_date = html.escape(safe_content['last_date'])
        safe_separator_style = html.escape(styles['separator'])
        safe_rank_color = html.escape(styles['rank_color'])
        safe_avatar_border = html.escape(styles['avatar_border'])
        
        # 使用字符串拼接而不是f-string，提高安全性
        # 根据当前用户状态选择合适的排名样式类
        rank_class = "rank-current" if item_data['is_current_user'] else "rank"
        
        html_parts = [
            f'<div class="{css_classes["item"]}" style="{safe_separator_style}">',
            f'    <div class="{rank_class}">#{item_data["rank"]}</div>',
            f'    <img class="avatar" src="{safe_avatar_url}" style="border-color: {safe_avatar_border};" />',
            '    <div class="info">',
            '        <div class="name-date">',
            f'            <div class="nickname">{safe_nickname}</div>',
            f'            <div class="date">最近发言: {safe_last_date}</div>',
            '        </div>',
            '        <div class="stats">',
            f'            <div class="count">{item_data["total"]} 次</div>',
            f'            <div class="percentage">({item_data["percentage"]:.2f}%)</div>',
            '        </div>',
            '    </div>',
            '</div>'
        ]
        return '\n'.join(html_parts)
    
    def _get_css_classes(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取CSS类名（优化版本）"""
        return {
            'item': "user-item-current" if item_data['is_current_user'] else "user-item"
        }
    
    def _get_item_styles(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取样式信息（优化版本）"""
        return {
            'separator': "margin-top: 20px; border-top: 2px dashed #bdc3c7;" if item_data['is_separator'] else "margin-top: 10px;",
            'rank_color': "#EF4444" if item_data['is_current_user'] else "#3B82F6",
            'avatar_border': "#ffffff"
        }
    
    def _get_safe_content(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取安全的内容（优化版本）"""
        # 批量转义提高性能
        safe_nickname = self._escape_html_safe(str(item_data.get('nickname', '未知用户')))
        safe_last_date = self._escape_html_safe(str(item_data.get('last_date', '未知')))
        safe_avatar_url = self._validate_url_safe(str(item_data.get('avatar_url', '')))
        
        # 如果头像URL无效，使用默认头像
        if not safe_avatar_url:
            safe_avatar_url = self._get_avatar_url(str(item_data.get('user_id', '0')), "qq")
        
        return {
            'nickname': safe_nickname,
            'last_date': safe_last_date,
            'avatar_url': safe_avatar_url
        }

    def _escape_html_safe(self, text: str) -> str:
        """安全的HTML转义"""
        if not isinstance(text, str):
            text = str(text)
        return html.escape(text, quote=True)
    
    def _validate_url_safe(self, url: str) -> str:
        """验证并清理URL"""
        if not isinstance(url, str):
            url = str(url)
        
        # 基本URL验证
        if not url or not url.startswith(('http://', 'https://')):
            return ""
        
        # 移除潜在的恶意字符
        url = url.replace('<', '').replace('>', '').replace('"', '').replace("'", '')
        return url

    def _get_avatar_url(self, user_id: str, platform: str = "qq") -> str:
        """获取用户头像URL
        
        Args:
            user_id (str): 用户ID
            platform (str): 平台类型，支持 'qq', 'telegram', 'discord' 等
            
        Returns:
            str: 头像URL
        """
        # 支持多种平台的头像服务
        avatar_services = {
            "qq": "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
            "telegram": "https://telegram.org/img/t_logo.png",  # Telegram默认头像
            "discord": "https://cdn.discordapp.com/embed/avatars/{avatar_id}.png",  # Discord默认头像
            "default": "https://via.placeholder.com/640x640?text=Avatar"  # 通用默认头像
        }
        
        service_url = avatar_services.get(platform, avatar_services["default"])
        return service_url.format(user_id=user_id, avatar_id=int(user_id) % 5)
    
    @safe_file_operation(default_return="")
    async def _load_html_template(self) -> str:
        """加载HTML模板（简化缓存逻辑）"""
        try:
            # 尝试从缓存获取
            cached_template = await self._get_cached_template()
            if cached_template:
                if isinstance(cached_template, str):
                    return cached_template
                elif hasattr(cached_template, 'source'):
                    # Jinja2模板对象，返回源代码
                    return cached_template.source
                else:
                    return str(cached_template)
            
            # 缓存未命中，从文件加载
            if await aiofiles.os.path.exists(self.template_path):
                async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                # 更新缓存
                await self._update_template_cache(content)
                return content
            else:
                self.logger.warning(f"模板文件不存在: {self.template_path}")
                # 使用默认模板
                default_template = await self._get_default_template()
                await self._update_template_cache(default_template)
                return default_template
        except FileNotFoundError as e:
            self.logger.warning(f"模板文件未找到: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
        except PermissionError as e:
            self.logger.error(f"模板文件权限错误: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
        except UnicodeDecodeError as e:
            self.logger.error(f"模板文件编码错误: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
    
    async def _get_fallback_template(self) -> str:
        """获取纯占位符回退模板（不含Jinja2语法）
        
        当Jinja2不可用时使用的安全模板，只使用简单的{{ key }}占位符，
        不包含任何Jinja2特有的语法（如循环、过滤器等）。
        """
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            padding: 30px;
            min-height: 100vh;
        }
        .title {
            text-align: center;
            font-size: 28px;
            color: #1F2937;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        .user-list {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.9);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .user-item {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .user-item:hover {
            transform: translateX(10px);
            background-color: rgba(59, 130, 246, 0.05);
        }
        .user-item-current {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            background: linear-gradient(135deg, #F3E8FF 0%, #EDE9FE 100%);
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.1);
        }
        .user-item-current:hover {
            transform: translateX(10px);
            box-shadow: 0 4px 8px rgba(139, 92, 246, 0.2);
        }
        .rank {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank:hover {
            transform: scale(1.1);
        }
        .rank-current {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank-current:hover {
            transform: scale(1.1);
        }
        .avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            margin-right: 20px;
            border: 3px solid #ffffff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .avatar:hover {
            transform: scale(1.05);
        }
        .info {
            flex: 1;
        }
        .name-date {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .nickname {
            font-size: 18px;
            font-weight: bold;
            color: #1F2937;
        }
        .date {
            font-size: 14px;
            color: #6B7280;
        }
        .stats {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .count {
            font-size: 16px;
            font-weight: bold;
            color: #3B82F6;
        }
        .percentage {
            font-size: 14px;
            color: #6B7280;
        }
    </style>
</head>
<body>
    <div class="title">{{ group_name }}[{{ group_id }}]</div>
    <div class="title">{{ title }}</div>
    <div class="user-list">
        {{ user_items }}
    </div>
</body>
</html>"""

    async def _get_default_template(self) -> str:
        """获取默认HTML模板（优化版本）"""
        # 尝试从缓存获取默认模板
        default_cache_key = 'default_template'
        async with self._cache_lock:
            cached_default = self._template_cache.get(default_cache_key)
        
        if cached_default:
            return cached_default['content']
        
        # 创建优化的默认模板（使用简单占位符）
        default_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            padding: 30px;
            min-height: 100vh;
        }
        .title {
            text-align: center;
            font-size: 28px;
            color: #1F2937;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        .user-list {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.9);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .user-item {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .user-item:hover {
            transform: translateX(10px);
            background-color: rgba(59, 130, 246, 0.05);
        }
        .user-item-current {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            background: linear-gradient(135deg, #F3E8FF 0%, #EDE9FE 100%);
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.1);
        }
        .user-item-current:hover {
            transform: translateX(10px);
            box-shadow: 0 4px 8px rgba(139, 92, 246, 0.2);
        }
        .rank {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank:hover {
            transform: scale(1.1);
        }
        .rank-current {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
            transition: transform 0.2s ease;
        }
        .rank-current:hover {
            transform: scale(1.1);
        }
        .avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            margin: 0 20px;
            border: 3px solid #3B82F6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .info {
            flex: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .name-date {
            display: flex;
            flex-direction: column;
        }
        .nickname {
            font-size: 20px;
            color: #1F2937;
            font-weight: 500;
            line-height: 1.2;
        }
        .date {
            color: #6B7280;
            font-size: 14px;
            margin-top: 4px;
        }
        .stats {
            text-align: right;
            font-size: 18px;
            min-width: 120px;
        }
        .count {
            color: #EF4444;
            font-weight: bold;
        }
        .percentage {
            color: #22C55E;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="title">{{ group_name }}[{{ group_id }}]</div>
    <div class="title">{{ title }}</div>
    <div class="user-list">
        {{ user_items }}
    </div>
</body>
</html>
"""
        
        # 缓存默认模板
        async with self._cache_lock:
            self._template_cache[default_cache_key] = {
                'content': default_template,
                'template': self.jinja_env.from_string(default_template) if self.jinja_env else None
            }
        
        return default_template
    
    async def test_browser_connection(self) -> bool:
        """测试浏览器连接"""
        try:
            if not self.browser:
                await self.initialize()
            
            # 创建一个测试页面
            test_page = await self.browser.new_page()
            
            # 设置基本内容
            await test_page.set_content("<html><body><h1>Test</h1></body></html>")
            
            # 验证页面可以正常加载
            title = await test_page.title()
            
            await test_page.close()
            
            return title == "Test"
        
        except FileNotFoundError as e:
            self.logger.error(f"浏览器可执行文件未找到: {e}")
            return False
        except PermissionError as e:
            self.logger.error(f"测试浏览器连接权限不足: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"浏览器连接失败: {e}")
            return False
        except RuntimeError as e:
            # 捕获浏览器运行时错误，如页面操作失败、JavaScript执行错误等
            self.logger.error(f"测试浏览器连接失败: {e}")
            return False
    
    async def get_browser_info(self) -> Dict[str, Any]:
        """获取浏览器信息"""
        try:
            if not self.browser:
                return {"status": "not_initialized"}
            
            return {
                "status": "ready",
                "user_agent": await self.browser.user_agent(),
                "viewport": {"width": self.width, "height": self.viewport_height}
            }
        
        except FileNotFoundError as e:
            return {"status": "error", "error": f"浏览器文件未找到: {e}"}
        except PermissionError as e:
            return {"status": "error", "error": f"权限不足: {e}"}
        except ConnectionError as e:
            return {"status": "error", "error": f"连接失败: {e}"}
        except RuntimeError as e:
            # 捕获浏览器信息获取时的运行时错误，如页面操作失败、资源访问错误等
            return {"status": "error", "error": str(e)}
    
    async def clear_cache(self):
        """清理模板缓存"""
        async with self._cache_lock:
            self._template_cache.clear()
            self.logger.info("模板缓存已清理")
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        cache_stats = await self.get_cache_stats()
        
        return {
            'cache_stats': cache_stats,
            'cached_templates': list(self._template_cache.keys()),
            'jinja2_enabled': JINJA2_AVAILABLE and self.jinja_env is not None,
            'playwright_enabled': PLAYWRIGHT_AVAILABLE,
            'template_path': str(self.template_path),
            'template_exists': await aiofiles.os.path.exists(self.template_path) if self.template_path else False
        }
    
    async def optimize_for_batch_generation(self):
        """为批量生成优化配置"""
        # 预热缓存
        await self._preload_templates()
        
        # 启用更激进的缓存策略
        if self.jinja_env:
            # Jinja2环境已经配置了缓存
            self.logger.info("批量生成优化已启用")
    
    async def _load_user_item_macro_template(self):
        """加载用户条目宏模板（异步版本）"""
        try:
            macro_path = Path(__file__).parent.parent / "templates" / "user_item_macro.html"
            if await aiofiles.os.path.exists(macro_path):
                async with aiofiles.open(macro_path, 'r', encoding='utf-8') as f:
                    macro_content = await f.read()
                
                # 创建环境并加载宏模板
                env = Environment(
                    loader=FileSystemLoader(str(macro_path.parent)),
                    autoescape=select_autoescape(['html', 'xml'])
                )
                return env.from_string(macro_content)
        except Exception as e:
            self.logger.warning(f"加载用户条目宏模板失败: {e}")
        
        return None

