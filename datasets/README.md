# RainGuard HK 官方数据采集工具

`collect_dataset.py` 使用 Python 3.10+，PDF 知识文档抽取需要 `PyMuPDF`，不需要 API Key。

```powershell
python -m pip install -r requirements.txt
python collect_dataset.py
python collect_dataset.py --live-only
python collect_dataset.py --offline
```

默认输出至同目录 `RainGuard_HK_Dataset`。也可使用 `--output "目标目录"`。

- 默认采集：从 DATA.GOV.HK 官方目录发现全部雨量站历史资源，下载其全部可用年份；另外采集 HKO、LFS、SHA 三站的日最高/最低/平均气温、平均湿度及平均气压，七份官方知识网页及劳工处两份完整 PDF 附件，九项当前天气接口和官方说明。
- `--live-only`：需要已有完整数据集，仅重新采集九项实时接口，保留历史原文与每次采集记录，并重新整理数据表。
- `--offline`：需要已有 `manifest.json` 及全部原文，完全离线重建清洗表、特征、数据库并核验。
- 每次原文保存在 `raw/<UTC批次时间>/`，不会覆盖旧批次。`manifest.json` 指向当前选用版本，`manifests/` 保存采集日志。失败不会用旧值或随机数填补；失败源列在 `quality/summary.json`。
- 输出包含 SQLite、CSV、JSON/JSONL。原文及完整字段说明见数据集内的 `README_数据集说明.md` 和 `DATA_DICTIONARY.md`。

采集器不会自动启动后台服务，也不会自动修改原网站。历史气候资料按月更新；实时接口可单独按需刷新。七份知识文档按需更新，不应每分钟抓取网页。

离线重建会更新“当前日预测是否具备输入”的检查日期，但不会篡改原文采集时间。天气日期使用香港时间，采集时间使用 UTC。
