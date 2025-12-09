"""
翻译管理器模块

提供轻量级的JSON翻译系统，支持：
- 运行时语言切换
- 嵌套键访问
- 变量插值
- 智能回退机制
"""

import json
import os
from typing import Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QSettings


class TranslationManager(QObject):
    """
    翻译管理器 - 单例模式

    负责加载、管理和提供翻译功能
    """

    # 语言切换信号，参数为新语言代码
    language_changed = pyqtSignal(str)

    _instance = None

    def __new__(cls):
        """确保单例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化翻译管理器"""
        if self._initialized:
            return

        super().__init__()
        self._initialized = True

        # 默认语言设置
        self.current_locale = "zh_CN"
        self.fallback_locale = "zh_CN"
        self.translations: Dict[str, Dict[str, Any]] = {}

        # 定位翻译文件目录
        # 从 qt_app/i18n/translator.py 向上两级到项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        self.locales_dir = os.path.join(project_root, "locales")

        # 加载所有翻译文件
        self._load_translations()

        # 从设置中恢复上次的语言选择
        self._load_saved_language()

    def _load_translations(self):
        """加载所有语言的翻译文件"""
        for locale in ["zh_CN", "en_US"]:
            filepath = os.path.join(self.locales_dir, f"{locale}.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.translations[locale] = json.load(f)
                    print(f"[i18n] Loaded translation: {locale}")
                except Exception as e:
                    print(f"[i18n] Failed to load {locale}: {e}")
            else:
                print(f"[i18n] Translation file not found: {filepath}")

    def _load_saved_language(self):
        """从QSettings加载保存的语言偏好"""
        settings = QSettings("OECT", "TestApp")
        saved_locale = settings.value("language", "zh_CN")

        # 验证保存的语言是否有效
        if saved_locale in self.translations:
            self.current_locale = saved_locale
            print(f"[i18n] Restored language: {saved_locale}")
        else:
            print(f"[i18n] Invalid saved language '{saved_locale}', using default: {self.current_locale}")

    def set_language(self, locale: str) -> bool:
        """
        切换语言

        Args:
            locale: 语言代码（如 'zh_CN', 'en_US'）

        Returns:
            bool: 切换是否成功
        """
        if locale not in self.translations:
            print(f"[i18n] Language '{locale}' not available")
            return False

        old_locale = self.current_locale
        self.current_locale = locale

        # 持久化用户选择
        settings = QSettings("OECT", "TestApp")
        settings.setValue("language", locale)

        # 触发更新信号
        if old_locale != locale:
            print(f"[i18n] Language changed: {old_locale} -> {locale}")
            self.language_changed.emit(locale)

        return True

    def tr(self, key: str, **kwargs) -> str:
        """
        翻译函数 - 支持变量插值

        Args:
            key: 翻译键，支持嵌套（如 'main.window_title'）
            **kwargs: 格式化参数，用于字符串插值

        Returns:
            str: 翻译后的字符串

        Examples:
            tr('main.window_title')
            tr('device_control.device_testing_prefix', device='COM3')
        """
        # 尝试从当前语言获取翻译
        translation = self._get_nested(
            self.translations.get(self.current_locale, {}),
            key
        )

        # 回退到默认语言
        if translation is None and self.current_locale != self.fallback_locale:
            translation = self._get_nested(
                self.translations.get(self.fallback_locale, {}),
                key
            )

        # 最终回退到键名（方便调试缺失的翻译）
        if translation is None:
            print(f"[i18n] Missing translation: {key}")
            translation = key

        # 应用变量插值
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError) as e:
                print(f"[i18n] Format error for key '{key}': {e}")

        return translation

    def _get_nested(self, data: Dict, key: str) -> Optional[str]:
        """
        获取嵌套键的值

        Args:
            data: 翻译数据字典
            key: 嵌套键（如 'main.dialog.confirm_close.title'）

        Returns:
            str or None: 翻译字符串，如果不存在则返回None
        """
        keys = key.split('.')
        value = data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return value if isinstance(value, str) else None

    def get_available_languages(self) -> Dict[str, str]:
        """
        获取可用语言列表

        Returns:
            Dict[str, str]: {语言代码: 显示名称}
        """
        return {
            "zh_CN": "简体中文",
            "en_US": "English"
        }

    def get_current_language(self) -> str:
        """获取当前语言代码"""
        return self.current_locale

    def reload_translations(self):
        """重新加载所有翻译文件（用于开发调试）"""
        self.translations.clear()
        self._load_translations()
        print("[i18n] Translations reloaded")


# 全局单例实例
_translator = TranslationManager()


def tr(key: str, **kwargs) -> str:
    """
    全局翻译函数快捷方式

    Args:
        key: 翻译键
        **kwargs: 格式化参数

    Returns:
        str: 翻译后的字符串

    Examples:
        from qt_app.i18n.translator import tr

        label.setText(tr('main.window_title'))
        info = tr('device_control.data_rate_format', rate=123.4, processed=100)
    """
    return _translator.tr(key, **kwargs)
