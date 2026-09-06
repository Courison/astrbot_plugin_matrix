import json
import os
import re
from itertools import combinations
from PIL import Image, ImageDraw, ImageFont
import io
from astrbot.api.all import *  # 包含 Plain, Image 等
# 注意：不再导入 Plugin

# 注册插件 - 直接使用 @register 装饰器，类不需要继承 Plugin
@register("matrix_plugin", "Matrix", "淤积点查询插件", "1.0.0")
class MatrixPlugin:  # 不再继承 Plugin
    def __init__(self, context):
        self.context = context
        # 加载数据
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, "area.json"), "r", encoding="utf-8") as f:
            self.region_data = json.load(f)
        with open(os.path.join(base_dir, "weapon.json"), "r", encoding="utf-8") as f:
            self.weapon_data = json.load(f)
        # 按星级排序（6星在前）
        self.weapon_data.sort(key=lambda x: 0 if x["star"] == "6星" else 1)
        self.region_groups = {
            "四号谷地": [r["name"] for r in self.region_data if r["group"] == "四号谷地"],
            "武陵": [r["name"] for r in self.region_data if r["group"] == "武陵"]
        }
        # 用于模糊匹配的索引
        self.weapon_name_map = {w["name"]: w for w in self.weapon_data}
        self.weapon_id_map = {w["id"]: w for w in self.weapon_data}

    # 帮助文档
    HELP_TEXT = """📖 基质插件使用帮助
/基质 武器          - 显示所有武器列表（图片）
/基质 <武器名/编号> - 查询单个武器详情及推荐刷取
/基质 <武器1,武器2> - 组合优化（多个武器同时刷取）
/基质 基础/附加/技能 - 按词条查询（三个词条必须匹配）
其他输入           - 显示本帮助"""

    # 辅助函数：组合生成
    def combos(self, arr, k):
        return list(combinations(arr, k))

    # 获取某个地区能刷的武器
    def get_weapons_for_region(self, region):
        return [w for w in self.weapon_data if
                w["base"] in region["base"] and
                w["extra"] in region["extra"] and
                w["skill"] in region["skill"]]

    # 生成武器列表图片
    def generate_weapon_image(self):
        try:
            # 按星级分组
            six_star = [w for w in self.weapon_data if w["star"] == "6星"]
            five_star = [w for w in self.weapon_data if w["star"] == "5星"]
            lines = []
            for w in six_star:
                lines.append(f"{w['id']}. {w['name']} ({w['star']} {w['type']})")
            for w in five_star:
                lines.append(f"{w['id']}. {w['name']} ({w['star']} {w['type']})")
            # 使用PIL生成图片
            font = ImageFont.load_default()
            # 计算图片大小
            max_len = max(len(line) for line in lines) if lines else 0
            char_width = 12
            char_height = 20
            padding = 20
            img_width = max_len * char_width + padding * 2
            img_height = len(lines) * char_height + padding * 2
            img = Image.new("RGB", (img_width, img_height), color="white")
            draw = ImageDraw.Draw(img)
            y = padding
            for line in lines:
                draw.text((padding, y), line, fill="black", font=font)
                y += char_height
            # 保存到内存
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return img_bytes
        except Exception:
            return None

    # 模糊匹配武器（名称或id）
    def match_weapon(self, text):
        text = text.strip()
        # 尝试数字id
        if text.isdigit():
            w = self.weapon_id_map.get(int(text))
            if w:
                return [w]
        # 模糊名称匹配（包含）
        matched = []
        for w in self.weapon_data:
            if text in w["name"]:
                matched.append(w)
        return matched

    # 解析多个武器输入（逗号、顿号、空格分隔）
    def parse_multi_weapon(self, text):
        parts = re.split(r'[,，、\s]+', text.strip())
        weapons = []
        for p in parts:
            if not p:
                continue
            matched = self.match_weapon(p)
            if matched:
                weapons.extend(matched)
        # 去重
        seen = set()
        unique = []
        for w in weapons:
            if w["id"] not in seen:
                seen.add(w["id"])
                unique.append(w)
        return unique

    # 推荐单个武器（返回两个区域的最佳附加和最佳技能）
    def recommend_single(self, target_weapon):
        result = {}
        for group in ["四号谷地", "武陵"]:
            region_list = [r for r in self.region_data if r["group"] == group]
            # 可刷目标武器的地区
            candidates = [r for r in region_list if
                          target_weapon["base"] in r["base"] and
                          target_weapon["extra"] in r["extra"] and
                          target_weapon["skill"] in r["skill"]]
            best_extra = None
            best_skill = None
            for region in candidates:
                base_combos = self.combos(region["base"], 3)
                for base_combo in base_combos:
                    # 附加
                    for extra in region["extra"]:
                        matched = [w for w in self.weapon_data if
                                   w["base"] in base_combo and
                                   w["extra"] == extra]
                        if any(w["id"] == target_weapon["id"] for w in matched):
                            count = len(matched) - 1
                            if best_extra is None or count > best_extra["count"]:
                                best_extra = {
                                    "region": region,
                                    "base": base_combo,
                                    "opt_type": "附加",
                                    "opt_value": extra,
                                    "weapons": matched,
                                    "count": count
                                }
                    # 技能
                    for skill in region["skill"]:
                        matched = [w for w in self.weapon_data if
                                   w["base"] in base_combo and
                                   w["skill"] == skill]
                        if any(w["id"] == target_weapon["id"] for w in matched):
                            count = len(matched) - 1
                            if best_skill is None or count > best_skill["count"]:
                                best_skill = {
                                    "region": region,
                                    "base": base_combo,
                                    "opt_type": "技能",
                                    "opt_value": skill,
                                    "weapons": matched,
                                    "count": count
                                }
            result[group] = {"extra": best_extra, "skill": best_skill}
        return result

    # 格式化单个武器推荐结果
    def format_recommend(self, recommend_result, target_name):
        lines = []
        for group in ["四号谷地", "武陵"]:
            for opt_type in ["extra", "skill"]:
                info = recommend_result.get(group, {}).get(opt_type)
                if not info:
                    continue
                region = info["region"]
                base = "、".join(info["base"])
                opt_label = info["opt_type"] + "：" + info["opt_value"]
                lines.append(f"————{region['name']} ({group}) · {info['opt_type']}最佳————")
                lines.append(f"刷取词条：基础：{base} ｜ {opt_label}")
                lines.append(f"附带武器：{info['count']}件")
                # 武器列表按星级排序
                weapons_sorted = sorted(info["weapons"], key=lambda x: 0 if x["star"] == "6星" else 1)
                weapon_names = [f"{w['name']} {w['star']}" for w in weapons_sorted]
                lines.append("武器列表：" + "、".join(weapon_names))
        return "\n".join(lines)

    # 多武器组合优化
    def optimize_multi(self, target_weapons):
        if len(target_weapons) == 1:
            return None
        best = None  # (命中数, 附带总数, 地区, base_combo, opt_type, opt_value, matched_weapons)
        for region in self.region_data:
            base_combos = self.combos(region["base"], 3)
            for base_combo in base_combos:
                # 附加
                for extra in region["extra"]:
                    matched = [w for w in self.weapon_data if
                               w["base"] in base_combo and
                               w["extra"] == extra]
                    hit = sum(1 for w in matched if w["id"] in [t["id"] for t in target_weapons])
                    if hit >= 2:  # 至少命中2个才考虑组合
                        total = len(matched)
                        if best is None or hit > best[0] or (hit == best[0] and total > best[1]):
                            best = (hit, total, region, base_combo, "附加", extra, matched)
                # 技能
                for skill in region["skill"]:
                    matched = [w for w in self.weapon_data if
                               w["base"] in base_combo and
                               w["skill"] == skill]
                    hit = sum(1 for w in matched if w["id"] in [t["id"] for t in target_weapons])
                    if hit >= 2:
                        total = len(matched)
                        if best is None or hit > best[0] or (hit == best[0] and total > best[1]):
                            best = (hit, total, region, base_combo, "技能", skill, matched)
        return best

    # 处理消息 - 使用 async def on_message 是 AstrBot 的标准事件处理方法
    async def on_message(self, context):
        msg = context.message_str
        if not msg.startswith("/基质"):
            return
        # 去掉前缀
        cmd = msg[len("/基质"):].strip()
        if not cmd:
            await context.send_message(Plain(self.HELP_TEXT))
            return

        # 1. /基质 武器
        if cmd == "武器":
            # 生成图片
            img_bytes = self.generate_weapon_image()
            if img_bytes:
                # 发送图片
                from astrbot.api.message_components import Image as ImageComponent
                await context.send_message(ImageComponent.from_bytes(img_bytes))
                await context.send_message(Plain("📜 以上为所有武器列表（6星在前，5星在后）"))
            else:
                # 降级为文本
                text = "📜 武器列表（6星→5星）：\n"
                for w in self.weapon_data:
                    text += f"{w['id']}. {w['name']} ({w['star']} {w['type']})\n"
                await context.send_message(Plain(text))
            return

        # 2. 尝试匹配词条查询（包含 '/' 且只有三个部分）
        if "/" in cmd:
            parts = cmd.split("/")
            if len(parts) == 3:
                base, extra, skill = parts
                base = base.strip()
                extra = extra.strip()
                skill = skill.strip()
                # 查找完全匹配的武器
                matched_weapons = [w for w in self.weapon_data if
                                   w["base"] == base and w["extra"] == extra and w["skill"] == skill]
                if matched_weapons:
                    # 找出可刷地点
                    regions = []
                    for r in self.region_data:
                        if base in r["base"] and extra in r["extra"] and skill in r["skill"]:
                            regions.append(r["name"])
                    lines = [f"可刷取地点：{', '.join(regions) if regions else '无'}"]
                    lines.append("可刷取武器：（完全匹配词条）")
                    for w in matched_weapons:
                        lines.append(f"{w['name']} {w['star']}")
                    await context.send_message(Plain("\n".join(lines)))
                else:
                    await context.send_message(Plain("未找到完全匹配该词条组合的武器"))
                return

        # 3. 尝试匹配多个武器（包含逗号、顿号、空格）
        if re.search(r'[,，、\s]', cmd):
            weapons = self.parse_multi_weapon(cmd)
            if weapons:
                if len(weapons) == 1:
                    # 只有一个武器，按单个处理
                    pass
                else:
                    # 尝试组合优化
                    best = self.optimize_multi(weapons)
                    if best:
                        hit, total, region, base_combo, opt_type, opt_value, matched = best
                        lines = [f"推荐刷取组合："]
                        lines.append(f"地点：{region['name']} ({region['group']})")
                        base_str = "、".join(base_combo)
                        lines.append(f"刷取词条：基础：{base_str} ｜ {opt_type}：{opt_value}")
                        lines.append(f"可刷武器（共{total}件）：")
                        sorted_weapons = sorted(matched, key=lambda x: 0 if x["star"] == "6星" else 1)
                        for w in sorted_weapons:
                            star_mark = " ★目标" if any(t["id"] == w["id"] for t in weapons) else ""
                            lines.append(f"  {w['name']} {w['star']}{star_mark}")
                        await context.send_message(Plain("\n".join(lines)))
                        return
                    else:
                        await context.send_message(Plain("无法将这些武器组合在同一个刷取方案中，建议单独查询："))
                        for w in weapons:
                            await context.send_message(Plain(f"请使用 '/基质 {w['name']}' 查询"))
                        return

        # 4. 单个武器查询
        matched = self.match_weapon(cmd)
        if matched:
            w = matched[0]
            regions = [r["name"] for r in self.region_data if
                       w["base"] in r["base"] and
                       w["extra"] in r["extra"] and
                       w["skill"] in r["skill"]]
            lines = [f"{w['name']} {w['type']} {w['star']}"]
            lines.append(f"基质属性：{w['base']}/{w['extra']}/{w['skill']}")
            lines.append(f"刷取地点：{', '.join(regions) if regions else '无'}")
            recommend_result = self.recommend_single(w)
            rec_text = self.format_recommend(recommend_result, w["name"])
            if rec_text:
                lines.append("推荐同时刷取：")
                lines.append(rec_text)
            else:
                lines.append("推荐同时刷取：无推荐方案")
            await context.send_message(Plain("\n".join(lines)))
            return

        # 5. 未知指令
        await context.send_message(Plain(self.HELP_TEXT))