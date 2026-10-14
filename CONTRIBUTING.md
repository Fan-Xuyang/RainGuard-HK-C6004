# 小组协作指南

## 获取与启动

克隆本仓库，执行 `npm ci` 和 `npm start`，打开本地页面。完整训练数据在 Release，也可运行 `python scripts/download_dataset.py` 下载并校验。Python 实验依赖由根目录 `requirements.txt` 安装。

## 推荐分工

| 方向 | 主要位置 | 建议产出 |
|---|---|---|
| 数据与来源审计 | datasets/、docs/data/ | 数据质量报告、字段和来源核验 |
| 特征与模型 | train_hk.py、完整包 training/ | 逻辑回归/随机森林/基线对比 |
| 官方知识与助手 | prepare-plus.py、assistant-api.mjs、retrieval.mjs | 检索改进、引用核验、真实评价 |
| 界面与可访问性 | hk-web/ | 简体中文页面、响应式布局、状态提示 |
| 设施与运营流程 | hk-web/hk-app.js | 实际场景、现场复核、交班记录 |
| 验证与报告 | test-plus.mjs、docs/proposal/ | 测试、30题双人评价、展示和报告 |

六人身份在提案中留空，认领方向后填写真实信息。Issue 里写清负责人与验收结果，避免多人同时改同一段大型界面文件。

## 每次修改的流程

有写入权限的成员：

```bash
git switch main
git pull --ff-only
git switch -c feature/your-change
# 修改后运行 npm test 和 npm run build
git add <明确要提交的文件>
git commit -m "Describe the change"
git push -u origin feature/your-change
```

然后创建 PR，请另一名组员检查。没有写入权限的成员先 Fork，克隆自己的 Fork，再向本仓库提 PR。仓库所有者可在 Settings → Collaborators 添加实际组员账号；仅公开仓库不会自动授予直接推送权限。

不要强制推送主分支，不要把未经验证的模型结果直接写成已完成实验。验证/测试集划分已固定，禁止用测试集挑参数或阈值。

## 提交范围

- 代码、文档和必要的小型页面数据可提交。
- `.env.local`、模型密钥、个人巡检照片、未经授权的设施联系人不提交。
- `datasets/RainGuard_HK_Dataset/`、node_modules、生成的 worker/dist 已忽略。完整数据用 Release 分发，若官方源更新，应保留新采集批次、更新哈希及说明。
- 更新数据包后，清单和发布资产应一起版本化，不要把 README 中旧快照的统计误写成新统计。
- GitHub 共享代码与运行中的业务数据独立。组员需要连接同一台配置了 WORKSPACE_TOKEN 的 Node 服务，使用页面的载入/上传操作共享设施、工单及现场记录；尚未提供自动合并。

## 本地检查

```bash
npm test
npm run build
```

测试使用模拟模型响应，不需要真实 Key，也不会消耗模型额度。`test-hk.mjs` 保留早期界面回归脚本，`npm run test:legacy` 仅用于对照，不作为当前版本 CI 门槛。

有完整数据包时还可执行 `python datasets/collect_dataset.py --offline`，核验原文、日期划分和特征。首次训练/模型评估建议各自保存实验参数、数据哈希和运行日期，再通过 PR 汇总结果。
