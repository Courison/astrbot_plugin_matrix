# astrbot_plugin_matrix

_淤积点武器与地区查询插件_  ·  v1.0.1

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)

## 介绍

查询《终末地》中武器基质与地区

内置 12 个地区、65 件武器。功能：

- 武器列表（按类型分组，合并转发）
- 单个武器查询（含推荐刷取方案）
- 多武器组合优化（若无法组合，会列出每把武器的编号、名称和词条，供单独查询；若有组合但部分武器未包含，也会单独列出）
- 词条匹配（基础/附加模糊，技能精确）
- 词条说明图片（`/基质 词条`）

## 安装

### 方法一：插件市场

1. 打开 AstrBot WebUI -> 插件管理。
2. 搜索 `astrbot_plugin_matrix`。
3. 点击安装。

### 方法二：手动

1. 克隆仓库： git clone https://github.com/Courison/astrbot_plugin_matrix.git
2. 将 `astrbot_plugin_matrix` 放入 `plugins` 目录。
3. 重启 AstrBot。

## 指令

- `/基质 武器`：显示所有武器列表（按类型分组，合并转发）。
- `/基质 词条`：发送词条说明图片，附查询格式提示。
- `/基质 <武器名/编号>`：查询单个武器详情及推荐刷取方案（含附加最佳/技能最佳）。
- `/基质 <武器1,武器2>`：多武器组合优化，寻找能同时刷取最多目标武器的地点和词条（可读编号）。若无法组合，会列出每把武器的编号、名称和词条；若有组合但部分武器未包含，也会单独列出这些武器。
- `/基质 基础/附加/技能`：按三个词条精确匹配武器，返回可刷地点和武器列表（基础和附加支持模糊匹配，技能精确匹配）。
- 其他输入：显示本帮助。

## 数据文件

- `area.json`：地区数据（name, group, base, extra, skill）。
- `weapon.json`：武器数据（id, name, star, type, base, extra, skill）。

详见仓库示例。

## 扩展

修改 JSON 文件即可添加新武器或地区，无需重启。

## 更新日志

### v1.0.1 (2026-09-07)
- 优化多武器组合输出：推荐组合中可刷武器列表显示词条，目标武器前加 ★ 标记。
- 若组合中遗漏部分目标武器，会在末尾单独列出这些武器的编号、名称和词条。

## 许可证

MIT