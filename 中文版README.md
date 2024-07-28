<div align="center">

![RF4S](static/readme/RF4S.png)
<h1 align="center">RF4S</h1>

**俄钓4钓鱼脚本，支持手竿、水底、路亚以及海钓模式**

<a target="_blank" href="https://opensource.org/license/gpl-3-0" style="background:none">
    <img src="https://img.shields.io/badge/License-GPLv3-blue.svg" style="height: 22px;" />
</a>
<a target="_blank" href="https://discord.gg/BZQWQnAMbY" style="background:none">
    <img src="https://img.shields.io/badge/discord-join-rf44.svg?labelColor=191937&color=6F6FF7&logo=discord" style="height: 22px;" />
</a>
<a target="_blank" href="http://makeapullrequest.com" style="background:none">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat" style="height: 22px;" />
</a>
<a target="_blank" href="https://github.com/pylint-dev/pylint" style="background:none">
    <img src="https://img.shields.io/badge/linting-pylint-yellowgreen" style="height: 22px;" />
</a>
<a target="_blank" href="https://github.com/psf/black" style="background:none">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg" style="height: 22px;" />
</a>
<!-- <a target="_blank" href="link_to_docs, tbd" style="background:none">
    <img src="https://img.shields.io/badge/docs-%23BE1B55" style="height: 22px;" />
</a> -->  

![python][Python badge]
![windows][Windows badge]
</div>

## [更新日志][Release notes]
> [!TIP]
> 加入我们的 [Discord 伺服器][Discord] 以取得最新消息。

## 准备工作
### 前提
- [Python3.10+][Python]


### 安装脚本
[下载][Download]此项目并解压缩，或:
```
git clone https://github.com/dereklee0310/RussianFishing4Script
```

### 安装依赖库并初始化设定
```
cd "项目路径"
.\setup.bat
```
> [!TIP]
> 如果你之前下载过Python，请建立一个新的虚拟环境以避免版本衝突。

## 使用方式
### 前提
- 启用 **[滑鼠锁定][Clicklock]**  并将按下时间设定为"长"
- 更改游戏语言为英文
- 将游戏缩放倍率设为"1x"
- 将游戏视窗显示模式设为"视窗化或"无边框模式"
- 将线杯装满线，或是装备彩虹线并在执行脚本时使用`-R`参数
- 把茶、咖啡和胡萝卜加到 **[最爱][Favorite food]**
- 如果想使用自动替换损坏拟饵的功能，请将用于替换的拟饵加到 **[最爱][Favorite lure]**
### 在启动脚本前...
- 移动游戏人物至钓点
- 手竿/路亚/海钓/维基钓组模式: 将钓竿拿在手上
- 水底模式: 将钓竿添加至快捷键 (1 ~ 3)，并在抛竿后将所有钓竿放置于脚色前方

> [!NOTE]
> 目前手竿及维基钓组模式只支援单竿作钓。

> [!IMPORTANT]
> 在使用手竿模式时，请将`config.ini`中的`window_size`设为你的游戏视窗大小。

### 1. 变更当前工作目录
```
cd "项目路径"
cd src
```

### 2. 执行脚本
以下是一些范例:
- 以预设设定执行脚本
```
python app.py
```
> [!WARNING]
> 如果脚本没有自动切换至游戏视窗或是无动作，请使用管理者权限执行终端。
- 显示帮助讯息 (参数使用教学)
```
python app.py -h
```
- 执行脚本，并将渔户内鱼的数量设为32 (脚本会在捕获68条后结束)
```
python app.py -n 32
```
- 使用模式3，拉大鱼时喝咖啡，并在脚本结束后寄一封通知到你的信箱
```
python app.py -p 3 --coffee --email
```
- 释放未达标鱼，自动补充饱食度和体温，并绘制一张鱼获/时间关係图
```
python app.py -mrP
```
### 命令行参数
- `-m`: 只保留达标鱼
- `-c`: 跟鱼缠斗时自动喝咖啡补充体力
- `-A`: 定时喝酒
- `-r`: 在抛竿前自动消耗胡萝卜/茶补充饱食及体温
- `-H`: 抛竿前自动挖饵，仅适用于水底模式
- `-e`: 执行完毕后寄信通知用户，需配置邮箱相关设定
- `-P`: 绘制鱼获/时间关係图并保存于logs/资料夹
- `-s`: 执行完毕后自动关机
- `-l`: 中鱼后收线时频繁抬杆
- `-g`: 自动切换传送比
- `-R`: 使用彩虹线米数侦测是否收线完毕
- `-S`: 上鱼后截图并储存至`screenshots/`资料夹
- `-n 数量`: 指定当前渔户内的鱼数量以便在满户时自动退出，预设为0
- `-p 模式id`: 指定欲使用的模式id
## 其他脚本
### 开启/关闭前进模式
- 执行后自动按住W键控制脚色前进，按w暂停，按s退出
```
python move.py
```

### 制作物品
- 可搭配`-n 数量`参数指定欲制作的物品数量，预设为材料用完后停止
- 使用`-d`即可丢弃所有制作的物品，用于冲技能
```
python craft.py
```
> [!IMPORTANT]
> 请选择欲制作的物品，材料和工具后再执行脚本

### 计算钓组可用的最大摩擦
- 根据提示输入钓组参数即可
```
python calculate.py
```

### 原地挂机自动挖饵+自动补充体力
- 使用`-s`以在等待间隔切换至设定介面，节省不必要的画面渲染
- `-n 秒数`可以自定义等待间隔的时间
```
python harvest.py
```

## 脚本设定
- **[视频教程(旧)][Video]**
- 请参考 **[中文版template.ini][Template]** 中的说明, 并在 **[config.ini][Config]** 中修改设定。
- 你可以在 **[config.ini][Config]** 中修改`language`以变更语言，
  并根据 **[图片添加指南][Integrity guide]** 添加缺失的图片
- 欲使用邮件功能的话，请在`.env`中配置邮箱以及SMTP伺服器等资讯

## 疑难排解
**如何停止脚本运行?**
- 在终端输入`Ctrl + C`.
   
**无法退出?**
- Shift键可能被脚本按下了，再按一次将其鬆开后即可正常退出

**收线卡住了?**
- 将线杯装满，或使用`-R`参数以及彩虹主线
- 更改游戏视窗大小
- 降低`config.ini`中`retrieval_detect_confidence`的值
- 远离光源(e.g, 露营灯、船灯)

## 授权条款
[GNU General Public License version 3][license]

## 贡献
如果你觉得这个脚本有帮助到你的话，请给这个repo一个星星 :)  
欢迎任何形式的贡献，包含但不限于bug回报、功能建议、PR

## 联繫方式
### Email
dereklee0310@gmail.com
### WeChat
<img src="static/readme/wechat.jpg" width="240">

[RF4S logo]: static/readme/RF4S.png

[Python badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Windows badge]: https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white

[Release notes]: release_notes.md
[Discord]: https://discord.gg/BZQWQnAMbY
[Python]: https://www.python.org/downloads/
[Download]: https://github.com/dereklee0310/RussianFishing4Script/archive/refs/heads/main.zip
[Clicklock]: /static/readme/clicklock.png
[Favorite food]: /static/readme/favorites.png
[Favorite lure]: /static/readme/favorites_2.png
[Video]: https://www.youtube.com/watch?v=znLBYoXHxkw
[Template]: 中文版template.ini
[Config]: config.ini
[Integrity guide]: integrity_guide.md

[license]: LICENSE
