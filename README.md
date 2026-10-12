# RainGuard HK

香港本地天气决策支持与降雨分类实验平台，SDSC6004 小组课程项目。界面使用简体中文，观测和知识资料来自香港天文台、渠务署及劳工处。

当前版本提供 11 个工作页面，涵盖观测、官方预报与警告、知识检索、DeepSeek 助手、地区比较、作业窗口、设施复核、现场记录、历史高雨量检索和交班报告。它是可运行的课程应用原型；现场业务记录目前保存在各自浏览器中，尚未实现多人共享业务数据库。

## 五分钟启动

需要 Node.js 22 或更新版本。**不配置模型密钥也可以运行天气页面和知识检索**。

```bash
git clone https://github.com/Fan-Xuyang/RainGuard-HK-C6004.git
cd RainGuard-HK-C6004
npm ci
npm start
```

打开 <http://localhost:8095>。从页面刷新官方数据；接口不可用时页面会显示错误或带日期的历史快照，不能将旧快照当作当前观测。

如需 AI 回答，将 `.env.example` 复制为 `.env.local`，在本机填入自己的 `DEEPSEEK_API_KEY`，然后重启服务。密钥只由服务端读取。仓库不包含密钥；不要在 Issues、PR、截图或前端文件中粘贴密钥。模型名称使用 `DEEPSEEK_MODEL` 配置，示例保留项目此前验证使用的值；如账户支持的模型变化，应按 DeepSeek 当前接口配置调整。

## 完整真实数据集

**[下载 v0.1.0 完整数据包](https://github.com/Fan-Xuyang/RainGuard-HK-C6004/releases/tag/v0.1.0)**，或运行：

```bash
python scripts/download_dataset.py
```

下载工具验证 SHA-256，再解压到 `datasets/RainGuard_HK_Dataset/`。完整 SQLite、全量历史 CSV、原文和训练特征放在 Release，避免大型数据文件进入每次代码提交。仓库保留可运行网站需要的三站数据与页面快照。

| 数据内容 | 本次快照规模 |
|---|---:|
| 全部可下载历史日雨量站 | 25 站 |
| 日雨量记录 | 293,267 条 |
| 全部气象日记录（雨量、三站温湿压等） | 671,724 条 |
| 三站核心特征，排除微量雨 | 20,762 个样本 |
| 官方知识库 | 9 份资料，58 个片段 |
| 实时接口 | 9 项 |

完整数据包中的历史日系列截至 **2026-08-31**，实时快照采集于 **2026-10-12**，具体观测时间逐接口保存。历史日系列按月发布，不足以直接提供今天模型所需的最近七个日输入；次日分类实验当前用于有日期标记的历史评价。页面实时展示与历史模型实验应分别解释。

完整包的九份知识资料包括劳工处两份 PDF；网站内置知识库仍为七份网页快照。两者分开保存，尚未把新增 PDF 自动接入线上助手。网站的既有模型结果也没有用新数据包静默覆盖。

详见 [数据集说明](docs/data/README_数据集说明.md)、[字段字典](docs/data/DATA_DICTIONARY.md)、[官方来源](docs/data/SOURCES.md) 和 [质量报告](docs/data/quality/summary.json)。文档中的数据包相对路径以解压后的 `RainGuard_HK_Dataset` 为根目录。

## 实验与更新

```bash
python -m pip install -r requirements.txt
python train_hk.py
npm test
npm run build
```

`train_hk.py` 复现网站现有的三站逻辑回归实验；新数据包另提供扩展站特征与两种微量雨策略。分类目标为“下一日站点总雨量 ≥25 mm”，是课程自定义标签，不等同于官方暴雨信号或实际水浸。随机森林对照、助手 30 题人工评价等仍为待开展实验，见提案。

完整数据采集与离线重建：

```bash
python datasets/collect_dataset.py --live-only
python datasets/collect_dataset.py --offline
```

上述命令需要先下载完整包。首次从官方源完整采集用 `python datasets/collect_dataset.py`。更新网站原有小数据包用 `python download_hk.py`，更新网站七份网页知识用 `python prepare-plus.py`，随后训练、测试和构建。完整包与网站小包不会自动互相覆盖。

## 组员共同开发

阅读 [协作指南](CONTRIBUTING.md)。仓库公开，任何组员均可 Fork 后提交 Pull Request；直接向本仓库推送分支需要仓库所有者添加 Collaborator。公开不代表任何人可以直接改写主分支。

建议按数据、模型、知识助手、界面、业务流程、验证与报告六个方向认领任务，使用 Issues 记录，再以功能分支和 PR 协作。自动检查会运行页面/接口测试和构建。

## 目录

```text
hk-web/                  简体中文界面、浏览器逻辑、网站数据和知识快照
serve-hk.mjs              本地服务入口
server-api.mjs            官方数据代理和接口处理
assistant-api.mjs         服务端 DeepSeek 与知识检索问答
download_hk.py            网站小数据包的官方采集脚本
train_hk.py               网站三站逻辑回归实验
datasets/                 完整数据采集、下载与重建工具
docs/data/                完整数据的来源、字段和质量报告
docs/proposal/            一页 ACM 双栏提案与可编辑源文件
.github/                  自动检查、Issue/PR 模板
```

详细功能与演示步骤见 [智能运营版使用说明](香港智能运营版使用说明.md)。原 Sites 演示链接的访问范围由其原服务设置决定，与本 GitHub 仓库的公开性独立；克隆后本地运行不依赖访问该演示站。

## 数据与第三方材料

官方数据与网页/PDF 原文保留来源和原有适用条款；没有把政府材料重新授予开源许可。Leaflet 的原许可证位于 `hk-web/vendor/LEAFLET-LICENSE.txt`，ACM 模板原许可证在提案源文件包中。详情见 [第三方说明](NOTICE.md)。
