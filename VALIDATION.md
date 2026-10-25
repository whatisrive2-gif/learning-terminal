# v0.0.1 发布验证

2026-10-18，在独立发布副本重新执行：

| 检查 | 结果 |
| --- | --- |
| `python -X utf8 -m unittest discover -s tests -v`（在 `frontend/`） | 18 / 18 通过 |
| `npm ci --ignore-scripts` 后 `npm test`（在技能的 `scripts/`） | 14 / 14 通过 |
| `learn.py --workspace .learning-terminal doctor` | 成功返回能力检查 |
| `learn.py --workspace .learning-terminal init ...` | 成功创建隔离演示会话，数据库未纳入 Git |

后端测试覆盖任务依赖、验收、版本冲突、取消、重启恢复、HTTP 访问校验及工具服务提交/轮询边界。阅读视图测试覆盖公式、来源标记、代码块、HTML 注入防护和版本变化。

第一次在受限终端中运行时，两项 HTTP 测试因本地套接字被限制而失败；在允许本地网络的环境重新执行后全部通过。

未在本次发布中运行浏览器 UI 自动化、真实外部工具服务、模型调用或宿主插件安装流程。测试通过不代表这些集成已完成。

## 2026-10-26 工作台同步验证

在独立的仓库副本运行，保留 `LEARNING_TERMINAL_WORKSPACE` 和 `TABER_BRIDGE_SCRIPT` 配置接口：

- `python -m unittest discover -s frontend/tests -p 'test_*.py'`：31 项通过。
- `frontend/tests/collaboration-ui.cjs`：无头 Chrome + 独立临时数据库通过，覆盖主机/Agent 登记、共同协作创建、主导权调整、交接包下载、普通待办和窄屏显示，无页面脚本异常。
- 双端协议测试使用两个独立临时数据库，覆盖幂等接收、错误目标、旧结果冲突和离线状态；不等同于真实 Windows/Mac 网络联调。
- 待发布文件检查未包含个人绝对路径、私钥或常见凭证格式；未纳入数据库、课程资料、模型会话和测试截图。

本次没有部署到 Windows，没有调用模型或启用自动同步。GitHub 保存程序代码；个人数据继续通过独立私密通道传递。
