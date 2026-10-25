# 装载学习终端

此接口供有本地执行能力的 Agent 装载。默认不启动任何模型进程，不更改模型订阅或消耗前端 API 额度。服务启动后，客户端从本机 runtime.json 读取认证信息，不要把该文件或 token 发给其他设备/网站。

运行 `python agent-client.py <command> --file <JSON绝对路径>`。inbox 可用 `--agent-id <id>` 代替文件。所有请求/结果均为 JSON，终端支持 UTF-8。

1. register：`{"name":"研究-01","provider":"你的平台","role":"核对来源","parent":"父Agent的id或空字符串","quota":"可选的额度说明","background":"职责与上下文"}`。返回 id。保存该 id，后续修改注册须同时传 id 与 revision，不能重复注册同名 Agent。
2. inbox：传 agent_id，返回分配给自己的 waiting_external 任务及消息。领取并不等于已完成；按任务 id + run_id 本地去重，单个注册身份只由一个执行进程负责。每次处理前读取 config、project_snapshot、lead_snapshot 和 agent_snapshot。
3. result：传 agent_id、task_id、run_id、revision、result，后端校验接收方和运行版本；结果进入待验收。过期结果拒绝写入。
4. assign：项目主 Agent 可传 agent_id、project_id、target_agent_id、title、notes、config、dependencies，创建并派发给分工成员。职责、不同提示词与背景写在 notes/config，前置任务填 dependencies。
5. message：传 agent_id、recipient、name（主题）、body、project，写入站内收件箱；平台侧实际读取由接入 Agent 的轮询负责。
6. create-task：当前 GPT 对话可传 title、notes、due、executor、config 等新增前端任务。普通待办 executor=manual；发给 Agent 使用 agent_id。创建不会自动执行。

本版信任装载客户端的本机 Agent，共享工作台本机认证域，不提供不受信任插件的身份隔离。注册代表接口已建立，不代表模型已在线持续工作。last_seen 记录最近轮询；额度字段是手工说明，非实时余额。自动运行 Agent 需要宿主确实具备执行与轮询能力。

## 双端协作（2026-10-25）

固定装载入口仍为本目录 `agent-client.py`。在仓库根目录使用 `python frontend/agent-client.py ...`。若已部署到其他目录，使用对应的绝对路径。本机服务需先启动。

- `workspace`：读取本机 `local_host_id`、主机目录与 agent 状态。把本机主机 ID 告知另一端，双方分别登记，不复制工作台数据库或 runtime.json。
- `register-host --file peer.json`：内容为 `{"id":"对方真实主机ID","name":"Windows","platform":"Windows","endpoint":"远程传输文件夹"}`。主机资料不证明在线。
- `register` 增加 `registration_key`（例如 `codex-main`）：同一主机、同一键重复注册返回原身份并更新心跳。资料修改仍走带 id/revision 的记录保存；重复注册不会静默覆盖资料。自动注册只能代表本机。不要让多个活动执行进程共用注册键。
- `heartbeat --agent-id ID`：报告存活，可用文件传 `work_status=idle|busy|paused`。建议宿主在活动期间每 30 秒报告；90 秒未联系显示离线。此客户端不自行常驻运行，不会自动创建定时任务。
- `offline --agent-id ID`：主动离线。注册/心跳只说明客户端有联系，不证明模型正执行。手工登记的远端 agent 显示未知，不伪造在线。

创建任务时可附加以下字段，也可使用 `set-collaboration --file change.json` 更新现有任务。更新必须带 `task_id` 和当前 `revision`：

```json
{
  "task_id": "任务ID",
  "revision": 3,
  "collaboration_mode": "joint",
  "lead_host_id": "",
  "execution_host_id": "执行主机ID",
  "integrator_agent_id": "",
  "responsibilities": "Mac 负责推导，Windows 负责核查；汇总后由用户验收。"
}
```

`led` 表示指定主机主导，必须填已登记的 lead_host_id；`joint` 表示同等职责，必须填分工与汇总约定，lead_host_id 自动置空。主机没有永久主从关系。更改分工留存历史，不修改 run_id、不重新派发。旧任务不会批量改写。项目原有主 Agent 是项目分派接口的协调人，不等于某台主机永久拥有任务主导权。

### 通过远程传输交接

1. 两端安装同一版本代码，各自运行独立服务，交换真实主机 ID 并登记。每端保留独立私密数据库。
2. 在发起端创建 Agent 任务，指定对方为执行主机，填写分工，明确派发至“等待交接”。
3. 任务详情点击“导出任务交接包”；或 `export-packet` 请求 `{"task_id":"...","target_host_id":"...","packet_kind":"handoff"}`。客户端输出 JSON，可重定向到文件。
4. 用现有 RustDesk/Tailscale 文件通道传递 JSON。在另一端协作区“导入交接包”核对内容再导入；或 `import-packet --file request.json`，请求形如 `{"packet":交接包对象}`。
5. 收到的任务为草稿，不自动执行。分配给本机 agent 或明确处理后登记结果。
6. 接收端在待验收/已完成任务上“导出结果回传包”；CLI 使用 `packet_kind=result`。发起端导入后进入待验收，仍需人工核验。

交接包包含任务说明、本轮配置、分工和结果文本，不包含 token、数据库、课程附件或原文件内容。任务说明本身可能含私密信息，应走自己的传输通道。包不是数字签名，仅适用于本人受信任的设备与文件。重复导入同一包不会重复创建/回填；目标主机、执行主机、run_id 或 revision 不符会拒绝。分工在交接后发生变化时需人工核对旧结果，不会强行覆盖新版。

当前实现为显式文件交接，不自动连接远端、不自动同步目录、不启用 GitHub 同步。远端网络在线探测与持续双向消息同步尚未接入。不要把文件到达时间当作远端在线依据。
