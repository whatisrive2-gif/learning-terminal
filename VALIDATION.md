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
