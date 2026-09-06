import json
import os
import re
from itertools import combinations
from PIL import Image, ImageDraw, ImageFont
import io
from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.message.components import Plain, Image as ImageComponent

class MatrixPlugin(Star):
    def __init__(self, context: Context, *args, **kwargs):
        super().__init__(context)
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, "area.json"), "r", encoding="utf-8") as f:
            self.region_data = json.load(f)
        with open(os.path.join(base_dir, "weapon.json"), "r", encoding="utf-8") as f:
            self.weapon_data = json.load(f)
        self.weapon_data.sort(key=lambda x: 0 if x["star"] == "6星" else 1)
        self.region_groups = {
            "四号谷地": [r["name"] for r in self.region_data if r["group"] == "四号谷地"],
            "武陵": [r["name"] for r in self.region_data if r["group"] == "武陵"]
        }
        self.weapon_name_map = {w["name"]: w for w in self.weapon_data}
        self.weapon_id_map = {w["id"]: w for w in self.weapon_data}

    async def initialize(self):
        logger.info("终末地基质插件已加载")

    async def terminate(self):
        logger.info("终末地基质插件已卸载")

    HELP_TEXT = """📖 基质插件使用帮助
/基质 武器          - 显示所有武器列表（图片）
/基质 <武器名/编号> - 查询单个武器详情及推荐刷取
/基质 <武器1,武器2> - 组合优化（多个武器同时刷取）
/基质 基础/附加/技能 - 按词条查询（三个词条必须匹配）
其他输入           - 显示本帮助"""

    def combos(self, arr, k):
        return list(combinations(arr, k))

    def generate_weapon_image(self):
        try:
            six_star = [w for w in self.weapon_data if w["star"] == "6星"]
            five_star = [w for w in self.weapon_data if w["star"] == "5星"]
            lines = []
            for w in six_star:
                lines.append(f"{w['id']}. {w['name']} ({w['star']} {w['type']})")
            for w in five_star:
                lines.append(f"{w['id']}. {w['name']} ({w['star']} {w['type']})")
            font = ImageFont.load_default()
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
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return img_bytes
        except Exception as e:
            logger.error(f"生成武器图片失败: {e}")
            return None

    def match_weapon(self, text):
        text = text.strip()
        if text.isdigit():
            w = self.weapon_id_map.get(int(text))
            if w:
                return [w]
        matched = []
        for w in self.weapon_data:
            if text in w["name"]:
                matched.append(w)
        return matched

    def parse_multi_weapon(self, text):
        parts = re.split(r'[,，、\s]+', text.strip())
        weapons = []
        for p in parts:
            if not p:
                continue
            matched = self.match_weapon(p)
            if matched:
                weapons.extend(matched)
        seen = set()
        unique = []
        for w in weapons:
            if w["id"] not in seen:
                seen.add(w["id"])
                unique.append(w)
        return unique

    def recommend_single(self, target_weapon):
        result = {}
        for group in ["四号谷地", "武陵"]:
            region_list = [r for r in self.region_data if r["group"] == group]
            candidates = [r for r in region_list if
                          target_weapon["base"] in r["base"] and
                          target_weapon["extra"] in r["extra"] and
                          target_weapon["skill"] in r["skill"]]
            best_extra = None
            best_skill = None
            for region in candidates:
                base_combos = self.combos(region["base"], 3)
                for base_combo in base_combos:
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

    def format_recommend(self, recommend_result):
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
                weapons_sorted = sorted(info["weapons"], key=lambda x: 0 if x["star"] == "6星" else 1)
                weapon_names = [f"{w['name']} {w['star']}" for w in weapons_sorted]
                lines.append("武器列表：" + "、".join(weapon_names))
        return "\n".join(lines)

    def optimize_multi(self, target_weapons):
        if len(target_weapons) == 1:
            return None
        best = None
        for region in self.region_data:
            base_combos = self.combos(region["base"], 3)
            for base_combo in base_combos:
                for extra in region["extra"]:
                    matched = [w for w in self.weapon_data if
                               w["base"] in base_combo and
                               w["extra"] == extra]
                    hit = sum(1 for w in matched if w["id"] in [t["id"] for t in target_weapons])
                    if hit >= 2:
                        total = len(matched)
                        if best is None or hit > best[0] or (hit == best[0] and total > best[1]):
                            best = (hit, total, region, base_combo, "附加", extra, matched)
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        msg = event.message_str
        logger.info(f"[MATRIX] 收到消息: {msg}")
        if not msg.startswith("/基质"):
            return
        cmd = msg[len("/基质"):].strip()
        logger.info(f"[MATRIX] 解析指令: {cmd}")

        # 临时测试指令
        if cmd == "测试":
            yield event.plain_result("基质插件测试成功！")
            return

        if not cmd:
            yield event.plain_result(self.HELP_TEXT)
            return

        if cmd == "武器":
            img_bytes = self.generate_weapon_image()
            if img_bytes:
                yield event.chain_result([
                    ImageComponent.from_bytes(img_bytes),
                    Plain("📜 以上为所有武器列表（6星在前，5星在后）")
                ])
            else:
                text = "📜 武器列表（6星→5星）：\n"
                for w in self.weapon_data:
                    text += f"{w['id']}. {w['name']} ({w['star']} {w['type']})\n"
                yield event.plain_result(text)
            return

        if "/" in cmd:
            parts = cmd.split("/")
            if len(parts) == 3:
                base, extra, skill = parts
                base = base.strip()
                extra = extra.strip()
                skill = skill.strip()
                matched_weapons = [w for w in self.weapon_data if
                                   w["base"] == base and w["extra"] == extra and w["skill"] == skill]
                if matched_weapons:
                    regions = []
                    for r in self.region_data:
                        if base in r["base"] and extra in r["extra"] and skill in r["skill"]:
                            regions.append(r["name"])
                    lines = [f"可刷取地点：{', '.join(regions) if regions else '无'}"]
                    lines.append("可刷取武器：（完全匹配词条）")
                    for w in matched_weapons:
                        lines.append(f"{w['name']} {w['star']}")
                    yield event.plain_result("\n".join(lines))
                else:
                    yield event.plain_result("未找到完全匹配该词条组合的武器")
                return

        if re.search(r'[,，、\s]', cmd):
            weapons = self.parse_multi_weapon(cmd)
            if weapons and len(weapons) > 1:
                best = self.optimize_multi(weapons)
                if best:
                    hit, total, region, base_combo, opt_type, opt_value, matched = best
                    lines = ["推荐刷取组合："]
                    lines.append(f"地点：{region['name']} ({region['group']})")
                    base_str = "、".join(base_combo)
                    lines.append(f"刷取词条：基础：{base_str} ｜ {opt_type}：{opt_value}")
                    lines.append(f"可刷武器（共{total}件）：")
                    sorted_weapons = sorted(matched, key=lambda x: 0 if x["star"] == "6星" else 1)
                    for w in sorted_weapons:
                        star_mark = " ★目标" if any(t["id"] == w["id"] for t in weapons) else ""
                        lines.append(f"  {w['name']} {w['star']}{star_mark}")
                    yield event.plain_result("\n".join(lines))
                    return
                else:
                    yield event.plain_result("无法将这些武器组合在同一个刷取方案中，建议单独查询：")
                    for w in weapons:
                        yield event.plain_result(f"请使用 '/基质 {w['name']}' 查询")
                    return

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
            rec_text = self.format_recommend(recommend_result)
            if rec_text:
                lines.append("推荐同时刷取：")
                lines.append(rec_text)
            else:
                lines.append("推荐同时刷取：无推荐方案")
            yield event.plain_result("\n".join(lines))
            return

        yield event.plain_result(self.HELP_TEXT)