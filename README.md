# 学习终端 · Learning Terminal

**v0.0.1 · 从学习材料到可持续修改的讲解**

学习中的解释通常散落在聊天记录里，后续追问很难回到同一份材料和同一版笔记。学习终端用本地会话、来源记录和版本管理，把材料、讲解、追问与修订联系起来。项目同时包含供 Codex 使用的插件，以及仍在开发中的本地工作台前端。

## 两个组成部分

| 模块 | 位置 | 当前能力 |
| --- | --- | --- |
| 插件和工具 | `.codex-plugin/`、`skills/learning-terminal/` | 导入材料、来源提取、会话、讲解版本、支线、需要记录、阅读视图与 Obsidian 操作 |
| 本地工作台 | `frontend/` | 待办、依赖、明确派发、结果验收、事件历史、只读学习记录、Taber 连接及外部工具服务适配 |

`learn.py` 本身不生成 AI 回答；讲解由使用该技能的助手撰写。保存讲解、读过材料和独立掌握分别记录，不把生成一份笔记视为学会。

## 快速运行：工作台

需要 Python 3.10+。工作台基础功能只用标准库。

```sh
python frontend/launch.py
```

Windows 可双击 `frontend/start.cmd`。服务仅监听 `127.0.0.1:8790`，启动器打开带本次访问凭证的本地页面。任务数据库写入 `frontend/data/`；通过页面“停止本地服务”结束服务。

新克隆没有学习数据库，学习记录区域可能提示数据库不存在。先用下方命令创建自己的学习会话即可。也可通过环境变量 `LEARNING_TERMINAL_WORKSPACE` 指向已有状态目录，通过 `TABER_BRIDGE_SCRIPT` 指向 Taber 的 `scripts/taber.mjs`。不要把个人数据库提交到 Git。

## 快速运行：学习工具

在仓库根目录执行：

```sh
python skills/learning-terminal/scripts/learn.py --workspace .learning-terminal doctor
python skills/learning-terminal/scripts/learn.py --workspace .learning-terminal init --title "我的学习会话" --goal "理解材料的核心推导"
```

导入文本和维护会话可先使用标准库。PDF 提取需要 `pypdf`；音视频转录需要 `faster-whisper` 和模型，属于可选功能，首次下载模型可能较大。完整可选依赖列在 `requirements.txt`。

离线公式阅读视图需要 Node.js 22.12+：

```sh
cd skills/learning-terminal/scripts
npm ci --ignore-scripts
npm test
```

插件入口是 [SKILL.md](skills/learning-terminal/SKILL.md)，准确命令见 [工具协议](skills/learning-terminal/references/commands.md)。仓库保留插件清单；宿主加载方式需按所用 Codex 客户端配置，本次不宣称已验证所有客户端的插件安装流程。

## 建议演示路线

1. 初始化学习会话并导入一份自己编写的 Markdown 材料。
2. 由助手根据来源编写讲解，使用带预期版本的 `commit` 保存。
3. 围绕一个疑问建立支线，再把补充合回新版本。
4. 在工作台建立关联待办，演示派发、结果登记与验收。
5. 配置 [Taber](https://github.com/whatisrive2-gif/taber) 后，演示阅读已保存讲解。

## 尚未完成

- 前端仍是开发中的本地工作台，不是完整的自主学习 Agent。
- Agent 当前以人工交接为主，未实现自动额度路由。
- 工具中心适配外部 `127.0.0.1:8787` 服务；该服务源码不在本仓库。离线时相关操作不可用。
- 已支持显式任务/结果交接包；远端在线探测、自动同步和完整跨平台发布未完成。

测试和本次验证范围见 [VALIDATION.md](VALIDATION.md)，详细工作台行为见 [frontend/README.md](frontend/README.md)。本次采用当前维护的本地技能与工作台源码；`0.0.1` 是统一仓库的首次展示版本，区别于安装缓存和内部阅读器包的既有版本。提交按整理模块分组，不回填历史开发日期。许可证尚未选定，第三方依赖遵循各自许可证。


## 2026-10-26 工作台与双端协作更新

工作台同步当前任务、学习配置、提交渠道和协作区域。两台主机地位平等：每项任务独立选择单端主导或共同协作，登记执行主机、汇总 Agent 和责任约定。Agent 通过固定入口 `frontend/agent-client.py` 注册；心跳过期显示离线，不自动接管任务。

交接包经自己的文件通道传递，由目标端核对后显式导入；重复包不重复执行，旧版本结果不能覆盖新任务，结果仍需验收。详细操作见 [Agent 接入与双端交接](frontend/AGENT-CONNECT.md)。页面仍是开发版本，本次先同步现状，后续再调整界面。

代码通过 GitHub 更新；学习数据库、课程材料、任务记录、交接包和凭证留在各自设备。更新前停止工作台并备份本地 `frontend/data/`，拉取代码后重新启动；不要用另一台电脑的数据库覆盖本机身份与任务。
