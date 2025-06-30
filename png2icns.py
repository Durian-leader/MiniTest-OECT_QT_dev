import os
import shutil
from PIL import Image

def remove_white_background(img: Image.Image) -> Image.Image:
    """将近似白色背景转为透明"""
    img = img.convert("RGBA")
    datas = img.getdata()

    new_data = []
    for item in datas:
        # 白色阈值（RGB每个通道 > 240）
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))  # 转透明
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

# ==== 配置部分 ====
input_png = "ChatGPT Image 2025年6月27日 13_11_15.png"           # 原始图标（建议 1024x1024）
iconset_dir = "my_icon.iconset"     # 中间目录
icns_path = "my_icon.icns"          # 输出文件名
icon_sizes = [
    (16, False), (16, True),
    (32, False), (32, True),
    (64, False),
    (128, False), (128, True),
    (256, False), (256, True),
    (512, False), (512, True),
    (1024, False),
]

# ==== 步骤 1：准备 iconset 文件夹 ====
if os.path.exists(iconset_dir):
    shutil.rmtree(iconset_dir)
os.makedirs(iconset_dir)

# ==== 步骤 2：处理原始图片 ====
with Image.open(input_png) as img:
    img = remove_white_background(img)

    # 生成各个尺寸图标
    for size, retina in icon_sizes:
        suffix = "" if not retina else "@2x"
        filename = f"icon_{size}x{size}{suffix}.png"
        path = os.path.join(iconset_dir, filename)
        scale = 2 if retina else 1
        resized = img.resize((size * scale, size * scale), Image.LANCZOS)
        resized.save(path)

# ==== 步骤 3：调用 iconutil 合并为 icns ====
os.system(f"iconutil -c icns {iconset_dir} -o {icns_path}")

# ==== 步骤 4（可选）：清理 iconset ====
shutil.rmtree(iconset_dir)

print(f"✅ 已成功生成：{icns_path}")