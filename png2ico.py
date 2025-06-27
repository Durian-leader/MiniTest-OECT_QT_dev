from PIL import Image

def remove_white_background(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    datas = img.getdata()

    new_data = []
    for item in datas:
        # 设定白色阈值（可微调）
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))  # 透明
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

def save_as_multi_res_ico(img: Image.Image, ico_path: str):
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (72, 72), (80, 80), (96, 96), (128, 128), (256, 256)]
    img.save(ico_path, format='ICO', sizes=sizes)

if __name__ == "__main__":
    input_path = r"C:\Users\lidon\Downloads\ChatGPT Image 2025年6月27日 13_11_15.png"
    output_path = "my_icon.ico"

    img = Image.open(input_path)
    img = remove_white_background(img)
    save_as_multi_res_ico(img, output_path)

    print(f"✅ 图标已保存为：{output_path}")
