# V2 状态矩阵（第一阶段）

| 当前状态 | 动作 | 下一状态 | 必须保持 |
|---|---|---|---|
| cold_start | 正常启动正式 EXE | idle / 第 1 步 | 未选文件；无虚构当前任务；同时加载本地历史 |
| idle | 点击“选择文件” | native_file_dialog | 调用 Windows DOCX 选择器；不得打开虚构样例弹窗 |
| native_file_dialog | 取消 | idle | 仍留在第 1 步，不创建任务 |
| idle | 选择 DOCX | source_ready | 文件只读、来源摘要 |
| source_ready | 开始检查 | checking | 任务身份 |
| checking | 检查完成 | review_required | 检查结果、命中项 |
| review_required | 采用/修改/保留/删除 | review_required | 待处理数、右侧列表 |
| review_required | 添加脱敏内容 | review_required | 新增项进入同一列表 |
| review_required | 待处理为 0 | ready_to_generate | 全部决定 |
| ready_to_generate | 生成 | generating | 生成锁定状态 |
| generating | 复查通过 | completed | 输出目录、历史记录 |
| 任意步骤 2–4 | 返回上一步 | 对应上一步 | 当前任务和已做决定 |
| checking/generating | 失败 | failed | 原因、重试入口、无伪成功结果 |
| completed/failed | 关闭 EXE 后重新打开 | idle + history_loaded | 工作区回到第 1 步；已持久化历史仍可见 |

禁止：正式 EXE 启动后直接进入第 2–4 步；桥接不可用时回退到虚构样例；用虚构历史代替本地历史；待处理数大于 0 时生成；失败任务显示成功结果；返回上一步清空已完成决定；AI 交付目录出现映射表。
