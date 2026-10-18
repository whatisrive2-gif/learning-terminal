# 工具协议

将 `<tool>` 替换为本 skill 相邻的 `scripts/learn.py` 绝对路径。将 `<state>` 替换为用户当前持久状态目录。命令由 Codex 运行，用户不必手动输入。PowerShell 路径用单引号，用户文本优先通过编辑工具写文件；不要把未转义用户内容插入 shell。

所有输出是 JSON；非零退出码表示失败。错误不能当作操作成功。下列 `<...>` 仅是文档参数记号，不是待完成内容。

```text
python <tool> --workspace <state> doctor
python <tool> --workspace <state> list
python <tool> --workspace <state> init --title <标题> --goal <目的>
python <tool> --workspace <state> status <session>
python <tool> --workspace <state> import <session> <材料路径>
python <tool> --workspace <state> import <session> <音视频> --transcript <字幕路径>
python <tool> --workspace <state> import <session> <音视频> --model <模型目录或模型名>
python <tool> --workspace <state> packet <session>
python <tool> --workspace <state> packet <session> --source <source-id> --offset 0 --limit 12000
python <tool> --workspace <state> commit <session> --file <完整讲解.md> --reason <修改理由> --expected <当前版本号>
python <tool> --workspace <state> commit <session> --file <完整讲解.md> --reason <理由> --expected <版本> --goal <新目标>
python <tool> --workspace <state> export <session> --out <不存在的输出.md>
python <tool> --workspace <state> reader <session> --out <不存在的阅读视图.html> --section 0
python <tool> --workspace <state> restore <session> --revision <旧版本> --expected <当前版本>
```

`packet` 首页只给来源清单，必须随后读取所需来源正文。返回 `next_offset` 时继续读。对整份材料编译，必须读完全文或明确尚未覆盖范围。来源引用格式 `[S:s_...]`；数字版本号是数据库生成值，不假设一定连续或从 1 开始。

reader 需要 Node 22.12+ 及 scripts/package-lock.json 对应的依赖。必要时在 scripts 目录 `npm ci --ignore-scripts --no-audit --no-fund`。可通过 `--node` 指定 Node 绝对路径。`--section` 是从 0 开始的章节索引，越界会夹到有效范围。返回实际路径、章节数、公式数和 formulaErrors。生成失败或视图超过 1 MB 时返回错误，不静默截断。HTML 是可视化宿主片段，不是完整网站；在支持的对话中以 visualize 内容引用显示。

新视图基于当前已保存版本与其父版本比较，标记新增/变化块；旧视图不会自行更新。按钮请求携带显示版本，接收后必须先检查最新状态，不能直接套用旧段落覆盖新文稿。展示公式采用本地 MathML，不加载外部字体或渲染脚本；特别长的单个公式在窄屏上允许局部横向查看。

PDF 文字提取用 pypdf；扫描件不提供 OCR。SRT/VTT 保留原时间标签供解释定位，不要求用户回放。本地语音通过 faster-whisper CPU int8；传模型目录离线运行，传模型名首次下载到 `<state>/models`。默认不选模型；中文建议用户在速度/质量间选择，tiny 仅适合安装与流程烟测，不能作为课堂准确性验收。

## 支线与需要

```text
python <tool> --workspace <state> branch <session> --question <问题> --anchor <当前讲解中的短句>
python <tool> --workspace <state> commit <session> --file <合并后的讲解.md> --reason <合回说明> --expected <基准版本> --branch <branch-id>
python <tool> --workspace <state> branch-close <session> <branch-id> --outcome <暂存理由>
python <tool> --workspace <state> need <session> --file <需要.json>
python <tool> --workspace <state> need <session> --file <更新后的需要.json> --id <need-id>
```

需要记录样例（实际使用替换为真实证据）：

```json
{
  "kind": "relationship",
  "statement": "用户知道定义，但不理解它如何支撑下一步。",
  "evidence": "用户原话：这个定义我知道，但为什么这里就能用？",
  "basis": "user-report",
  "state": "open",
  "blocking": "partial",
  "relevance": "core",
  "anchor": "当前讲解中的对应短句"
}
```

kind: goal-mismatch / prerequisite / step / relationship / application / curiosity。
basis: user-report / observed-response / inference。
state: open / working / self-reported-clear / demonstrated / deferred。
blocking: none / partial / blocked；relevance: core / supporting / exploration。
demonstrated 必须有 observed-response；curiosity 的 blocking 必须为 none。

## 多库与写入

```text
python <tool> --workspace <state> vault-list
python <tool> --workspace <state> vault-add --name <别名> --path <已有目录>
python <tool> --workspace <state> vault-add --name <别名> --path <新目录> --create
python <tool> --workspace <state> vault-use <别名>
python <tool> --workspace <state> vault-search --query <词语>
python <tool> --workspace <state> vault-search --vault <别名或路径> --query <词语>
python <tool> --workspace <state> vault-plan <session> --changes <改动.json>
python <tool> --workspace <state> vault-plan <session> --vault <别名或路径> --changes <改动.json>
python <tool> --workspace <state> vault-preview <plan-id>
python <tool> --workspace <state> vault-apply <plan-id>
python <tool> --workspace <state> vault-undo <plan-id>
```

登记库不修改已有目录内容；创建新库只创建目录和空 `.obsidian` 子目录。新登记库会成为当前库。每次计划固定一个绝对库路径，之后切库不会改变计划目标。

改动 JSON 是数组，每项含库内 Markdown 相对路径、mode、reason，以及 content 或 use_current。`use_current` 直接采用已保存讲解正文；请确保正文有可读来源清单。

```json
[
  {"path": "学习/主题.md", "mode": "create", "reason": "保存本次整理结果", "use_current": true},
  {"path": "概念/已有概念.md", "mode": "append", "reason": "补充适用条件并连接新例子", "content": "## 新增解释\n\n这里写实际内容、来源和有理由的 [[学习/主题|主题]] 关联。"}
]
```

预览不改笔记。计划存储原始字节，应用时检查所有目标是否仍与预览一致；完成后保留可撤销记录。外部编辑器不遵守本工具锁，快照检查不能消除检查和替换之间极短的竞态；避免在同一瞬间编辑目标文件。崩溃时状态可能为 applying/undoing，可检查后通过 vault-undo 恢复。`.learning-terminal.lock` 只能在确认原进程已结束后处理。

## 环境依赖

核心存储、Markdown/字幕、库管理与测试只需 Python 3.10+ 标准库。PDF 和音视频按需安装插件根的 requirements.txt。若只安装了 skill（无插件根），可在用户指定的独立虚拟环境中安装 pypdf、faster-whisper。不把模型或虚拟环境写入 skill 安装目录。
