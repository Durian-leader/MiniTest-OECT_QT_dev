"""
简单测试脚本：验证翻译系统是否正常工作
"""

import sys
import os

# 添加项目目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qt_app.i18n.translator import _translator, tr

def test_translation_system():
    """测试翻译系统基本功能"""
    print("=" * 60)
    print("翻译系统测试")
    print("=" * 60)

    # 测试1: 检查翻译文件是否加载成功
    print("\n1. 检查翻译文件加载：")
    print(f"   可用语言: {_translator.get_available_languages()}")
    print(f"   当前语言: {_translator.get_current_language()}")
    print(f"   已加载的语言: {list(_translator.translations.keys())}")

    # 测试2: 测试中文翻译
    print("\n2. 测试中文翻译：")
    _translator.set_language("zh_CN")
    print(f"   窗口标题: {tr('main.window_title')}")
    print(f"   应用头部: {tr('main.app_header')}")
    print(f"   刷新按钮: {tr('device_control.refresh_button')}")
    print(f"   测试类型-转移: {tr('workflow.test_type.transfer')}")

    # 测试3: 测试英文翻译
    print("\n3. 测试英文翻译：")
    _translator.set_language("en_US")
    print(f"   窗口标题: {tr('main.window_title')}")
    print(f"   应用头部: {tr('main.app_header')}")
    print(f"   刷新按钮: {tr('device_control.refresh_button')}")
    print(f"   测试类型-转移: {tr('workflow.test_type.transfer')}")

    # 测试4: 测试变量插值
    print("\n4. 测试变量插值：")
    _translator.set_language("zh_CN")
    result_cn = tr('device_control.data_rate_format', rate=123.45, processed=100)
    print(f"   中文: {result_cn}")

    _translator.set_language("en_US")
    result_en = tr('device_control.data_rate_format', rate=123.45, processed=100)
    print(f"   英文: {result_en}")

    # 测试5: 测试缺失键的回退
    print("\n5. 测试缺失键回退：")
    missing_key = tr('non.existent.key')
    print(f"   缺失的键返回: {missing_key}")

    # 测试6: 测试语言切换信号
    print("\n6. 测试语言切换信号：")
    def on_language_changed(locale):
        print(f"   语言已切换到: {locale}")

    _translator.language_changed.connect(on_language_changed)
    _translator.set_language("zh_CN")
    _translator.set_language("en_US")

    print("\n" + "=" * 60)
    print("✅ 翻译系统测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_translation_system()
