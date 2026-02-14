#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信红包封面生成器 - 极简版
接收AI创作的提示词，生成符合规范的素材文件
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

try:
    import requests
    from PIL import Image
except ImportError:
    print("请先安装依赖: pip install requests Pillow")
    sys.exit(1)


# ============================================================================
# 配置加载
# ============================================================================

def get_config_path() -> Path:
    """获取配置文件路径"""
    return Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    """加载配置文件"""
    config_path = get_config_path()

    # 默认配置
    default_config = {
        "api_key": "",
        "api_url": "https://ai.gitee.com/v1/images/generations",
        "model": "Z-Image",
        "default_params": {
            "guidance_scale": 5,
            "num_inference_steps": 50
        }
    }

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            print(f"[警告] 读取配置文件失败: {e}")

    return default_config


def get_api_key() -> str:
    """获取 API Key（优先级：环境变量 > 配置文件）"""
    # 优先使用环境变量
    env_key = os.environ.get("GITEE_AI_API_KEY", "")
    if env_key:
        return env_key

    # 其次使用配置文件
    config = load_config()
    return config.get("api_key", "")


def is_api_key_configured() -> bool:
    """检查 API Key 是否已配置"""
    return bool(get_api_key())


# 加载配置
CONFIG = load_config()
API_URL = CONFIG.get("api_url", "https://ai.gitee.com/v1/images/generations")
API_KEY = get_api_key()
MODEL = CONFIG.get("model", "Z-Image")
DEFAULT_PARAMS = CONFIG.get("default_params", {"guidance_scale": 5, "num_inference_steps": 50})

# 微信红包封面规范
SPECIFICATIONS = {
    "cover": {
        "name": "封面图",
        "width": 957,
        "height": 1278,
        "max_size_kb": 500,
        "api_size": "768x1024"
    },
    "cover_pendant": {
        "name": "封面挂件",
        "width": 1053,
        "height": 1746,
        "max_size_kb": 300,
        "api_size": "576x1024"
    },
    "bubble_pendant": {
        "name": "气泡挂件",
        "width": 480,
        "height": 384,
        "max_size_kb": 300,
        "api_size": "1024x768"
    },
    "story": {
        "name": "封面故事",
        "width": 750,
        "height": 1250,
        "max_size_kb": 300,
        "api_size": "576x1024"
    }
}


# ============================================================================
# API 调用
# ============================================================================

def call_ai(prompt: str, size: str) -> str:
    """调用 AI 绘图 API"""
    if not API_KEY:
        print("  [错误] API Key 未配置！")
        print("  [提示] 请在 config.json 中设置 api_key，或设置环境变量 GITEE_AI_API_KEY")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "prompt": prompt,
        "model": MODEL,
        "size": size,
        "guidance_scale": DEFAULT_PARAMS.get("guidance_scale", 5),
        "num_inference_steps": DEFAULT_PARAMS.get("num_inference_steps", 50)
    }

    try:
        print(f"  [AI] 正在生成...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            if result.get("data") and len(result["data"]) > 0:
                return result["data"][0].get("b64_json")

        print(f"  [错误] API返回: {response.status_code}")
        print(f"  [错误] 响应: {response.text[:300]}")
        return None

    except Exception as e:
        print(f"  [错误] {e}")
        return None


# ============================================================================
# 图片处理
# ============================================================================

def process_and_save(b64_data: str, output_path: str, spec: dict) -> bool:
    """处理图片并保存"""
    try:
        # 解码
        image_data = base64.b64decode(b64_data)
        image = Image.open(BytesIO(image_data))
        print(f"  [处理] 原始尺寸: {image.size[0]}x{image.size[1]}")

        # 调整尺寸
        resized = image.resize((spec["width"], spec["height"]), Image.Resampling.LANCZOS)

        # 确保RGBA模式
        if resized.mode != "RGBA":
            resized = resized.convert("RGBA")

        # 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        resized.save(output_path, format="PNG", optimize=True)

        # 检查大小
        file_size_kb = Path(output_path).stat().st_size / 1024

        if file_size_kb <= spec["max_size_kb"]:
            print(f"  [完成] {spec['name']} - {spec['width']}x{spec['height']}, {file_size_kb:.1f}KB")
            return True

        # 需要压缩
        print(f"  [优化] 文件过大 ({file_size_kb:.1f}KB)，正在压缩...")
        converted = resized.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        converted.save(output_path, format="PNG", optimize=True)

        file_size_kb = Path(output_path).stat().st_size / 1024
        print(f"  [完成] {spec['name']} - {spec['width']}x{spec['height']}, {file_size_kb:.1f}KB")
        return True

    except Exception as e:
        print(f"  [错误] 处理失败: {e}")
        return False


# ============================================================================
# 生成函数
# ============================================================================

def generate(prompts: dict, output_dir: str, show_prompt: bool = False) -> dict:
    """生成全套素材"""

    # 检查 API Key
    if not is_api_key_configured():
        print("\n" + "="*60)
        print("⚠️  API Key 未配置！")
        print("="*60)
        print("请在以下位置之一配置您的 Gitee AI API Key：")
        print(f"  1. 配置文件: {get_config_path()}")
        print("  2. 环境变量: GITEE_AI_API_KEY")
        print("="*60 + "\n")
        return {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) if output_dir else Path(__file__).parent.parent / "output" / f"cover_{timestamp}"

    print(f"\n{'='*60}")
    print(f"微信红包封面生成器")
    print(f"{'='*60}")
    print(f"输出目录: {output_path}")
    print(f"{'='*60}\n")

    results = {}

    # 生成顺序
    order = ["cover", "cover_pendant", "bubble_pendant", "story"]
    filenames = {
        "cover": "cover.png",
        "cover_pendant": "cover_pendant.png",
        "bubble_pendant": "bubble_pendant.png",
        "story": "story_1.png"
    }

    for i, asset_type in enumerate(order, 1):
        spec = SPECIFICATIONS[asset_type]
        prompt = prompts.get(asset_type, "")

        if not prompt:
            print(f"\n[{i}/4] 跳过 {spec['name']} - 未提供提示词")
            results[asset_type] = False
            continue

        print(f"\n[{i}/4] 生成 {spec['name']} ({spec['width']}x{spec['height']})...")

        if show_prompt:
            print(f"  [提示词] {prompt[:100]}...")

        # 调用API
        b64_data = call_ai(prompt, spec["api_size"])

        if b64_data:
            # 处理保存
            file_path = output_path / filenames[asset_type]
            success = process_and_save(b64_data, str(file_path), spec)
            results[asset_type] = success
        else:
            print(f"  [失败] API调用失败")
            results[asset_type] = False

    # 保存信息
    info = {
        "prompts": prompts,
        "generated_at": datetime.now().isoformat(),
        "results": results
    }

    info_path = output_path / "info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # 总结
    print(f"\n{'='*60}")
    success_count = sum(1 for v in results.values() if v)
    print(f"生成完成: {success_count}/4 成功")
    print(f"输出目录: {output_path}")
    print(f"{'='*60}\n")

    return results


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='微信红包封面生成器 - 接收提示词，生成符合规范的素材',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate.py --prompts '{"cover": "...", "cover_pendant": "...", "bubble_pendant": "...", "story": "..."}'

  python generate.py --prompts '{"cover": "festive artwork"}' --show-prompt

API Key 配置:
  方式1: 在 config.json 中设置 api_key
  方式2: 设置环境变量 GITEE_AI_API_KEY
        """
    )

    parser.add_argument('--prompts', '-p', type=str, required=True,
                        help='JSON格式的提示词，包含 cover, cover_pendant, bubble_pendant, story')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出目录')
    parser.add_argument('--show-prompt', action='store_true',
                        help='显示提示词')
    parser.add_argument('--check-config', action='store_true',
                        help='检查配置状态')

    args = parser.parse_args()

    # 检查配置
    if args.check_config:
        print("\n配置状态:")
        print(f"  配置文件: {get_config_path()}")
        print(f"  API Key: {'已配置 ✓' if is_api_key_configured() else '未配置 ✗'}")
        print(f"  API URL: {API_URL}")
        print(f"  Model: {MODEL}")
        return

    # 解析提示词
    try:
        prompts = json.loads(args.prompts)
    except json.JSONDecodeError:
        print("[错误] 提示词格式错误，请提供有效的JSON")
        sys.exit(1)

    # 生成
    results = generate(prompts, args.output, args.show_prompt)

    # 返回状态
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
