<div align="center">

![RF4S][rf4s_logo]
<h1 align="center">RF4S: Russian Fishing 4 Script</h1>

**一个简洁的 Russian Fishing 4 自动钓鱼脚本，支持路亚、水底、海钓、浮漂等多种钓法。**

![GitHub License](https://img.shields.io/github/license/dereklee0310/RussianFishing4Script)
[![Discord](https://img.shields.io/badge/discord-join-rf44.svg?labelColor=191937&color=6F6FF7&logo=discord)](https://discord.gg/BZQWQnAMbY)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat)](http://makeapullrequest.com)
[![Python: 3.11 | 3.12](https://img.shields.io/badge/python-3.11_%7C_3.12-blue)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

> [!TIP]
> 加入 [Discord 服务器][discord]来反馈建议、报告 Bug 或获取使用帮助。

## 功能一览

| 功能 | 说明 | 命令 |
|------|------|------|
| 自动钓鱼 | 支持路亚、水底、海钓（pirk/elevator）、浮漂（手杆/波伦）多种模式 | `bot` |
| 自动制作 | 批量制作鱼饵、打窝料、假饵等 | `craft` |
| 自动前进 | 切换 `W`（或 `Shift+W` 加速）移动 | `move` |
| 自动挖饵 | 挂机自动挖饵 | `harvest` |
| 智能抛力卸力 | 根据鱼竿数据自动调整卸力器 | `frictionbrake` |
| 渔具计算器 | 计算渔具属性和推荐卸力值 | `calculate` |
| **拖钓巡航** | OCR 坐标识别 + 向量计算自动纠正航向（多航点循环） | `bot -T` |

## 安装

> [!IMPORTANT]
> Python 3.13+ 不支持，需要版本 >=3.11, <=3.12。

### pip
```bash
git clone https://github.com/dereklee0310/RussianFishing4Script.git
cd RussianFishing4Script
pip install -r requirements.txt
```

### uv
```bash
git clone https://github.com/dereklee0310/RussianFishing4Script.git
cd RussianFishing4Script
uv sync
```

### 可执行文件 (.exe)
从 [Releases][releases] 下载 `rf4s.zip` 解压即可。

> [!WARNING]
> 1. 下载路径不能包含中文或特殊字符。
> 2. `.exe` 版本容易被杀毒软件误报，建议使用 Python 运行。

## 游戏设置

### 显示设置
- 系统缩放和游戏界面缩放都设为 **1x**
- 游戏窗口模式选 **窗口模式** 或 **无边框窗口**

### 收线检测
默认监测线杯（红框）判断收线进度，确保线杯满线。
如果装备了彩虹线，使用 `-R` 参数改为检测米数（绿框），精度更高。

![status]

### Windows 鼠标单击锁定
如果启用了 ClickLock，需要将时间设置为 **长**。

![click_lock]

## 使用方法

### 启动方式

```bash
# Python
python main.py

# uv
uv run main.py

# 可执行文件
.\main.exe
```

### 各模式说明

**路亚 / 海钓 / 浮漂**：拿起要使用的鱼竿，选择对应的 Profile 启动。

**水底钓**：将鱼竿放入快捷栏（1~3），抛竿后放好位置再启动脚本。

> [!NOTE]
> 目前只有水底模式支持多竿。

**拖钓巡航**：需要先校准数字模板，然后在 `config.yaml` 中配置航点。

```bash
# 1. 校准数字模板（首次使用）
python -m rf4s.controller.calibrate

# 2. 配置 config.yaml 中的 BOT.CRUISE 段

# 3. 启动拖钓
python main.py bot -p SPIN -T forward
```

> [!TIP]
> 更多高级用法和配置选项详见 **[CONFIGURATION][configuration]**。

## 项目结构

```
RussianFishing4Script/
├── main.py                    # 入口文件
├── rf4s/                      # 核心包
│   ├── app/                   # 各功能应用（BotApp、CraftApp 等）
│   ├── config/                # 配置系统（defaults.py + config.yaml）
│   ├── controller/            # 控制器层
│   │   ├── player.py          # 钓鱼主循环
│   │   ├── detection.py       # 图像检测（mss + OpenCV）
│   │   ├── cruise.py          # 拖钓巡航控制器
│   │   ├── calibrate.py       # 数字模板校准工具
│   │   ├── timer.py           # 计时器
│   │   ├── window.py          # 游戏窗口控制
│   │   └── notification.py    # 通知推送
│   ├── component/             # 组件层（Tackle、FrictionBrake）
│   └── i18n/                  # 国际化
├── static/                    # 静态资源（模板图片、数字模板等）
├── config.yaml                # 用户配置（自动生成）
└── requirements.txt           # Python 依赖
```

## 常见问题

<details>
<summary>被杀毒软件误报为病毒？</summary>

这是 Nuitka/PyInstaller 打包的常见误报，参见 [Nuitka 官方说明][malware]。
</details>

<details>
<summary>无法停止脚本？</summary>

某些按键可能处于按下状态（如 `Ctrl`、`Shift`、鼠标键等），
手动按一下释放后再按 `Ctrl-C` 即可。
</details>

<details>
<summary>卡在抛竿 12x%？</summary>

- 检查游戏语言和脚本语言设置是否一致
- 确保线杯满线，或装备彩虹线并使用 `-R` 参数
</details>

<details>
<summary>鱼到脚边了但不起竿？</summary>

- 确保线杯满线，或装备彩虹线并使用 `-R` 参数
- 调整游戏窗口大小
- 降低 `config.yaml` 中 `BOT.SPOOL_CONFIDENCE` 的值
- 避免强光源（如直射阳光），关闭船上灯光
</details>

<details>
<summary>脚本在运行但游戏没有反应？</summary>

以管理员身份运行脚本。
</details>

## 更新日志

详见 **[CHANGELOG][changelog]**。

## 许可证

**[GNU General Public License v3][license]**

## 贡献

欢迎任何贡献、Bug 报告或新功能建议。

## 联系

dereklee0310@gmail.com

[rf4s_logo]: /static/readme/RF4S.png
[click_lock]: /static/readme/clicklock.png
[status]: /static/readme/status.png
[malware]: https://nuitka.net/user-documentation/common-issue-solutions.html#windows-virus-scanners
[discord]: https://discord.gg/BZQWQnAMbY
[releases]: https://github.com/dereklee0310/RussianFishing4Script/releases
[configuration]: /docs/en/CONFIGURATION.md
[changelog]: /docs/en/CHANGELOG.md
[license]: /LICENSE