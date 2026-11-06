# M3 模型训练与基线评估复现

本目录包含 M3 的[详细报告](M3_模型训练与基线评估报告.md)、简明汇报稿 `M3部分.docx`、扩展实验汇总和项目原实验的重跑记录。实验基于 v0.1.0 冻结数据，主分析使用 M1 指定的 Trace 排除策略。

## 从仓库根目录运行

使用 Python 3.11，并在虚拟环境中安装 M3 固定版本依赖。下载程序会验证数据包 SHA-256；如果已有完整数据包，可按项目说明从已下载的 ZIP 安装。

```bash
python -m pip install -r requirements-m3.txt
python scripts/download_dataset.py
python scripts/m3_extended_evaluation.py
python scripts/verify_m3_results.py
```

扩展实验读取 `datasets/RainGuard_HK_Dataset/training/trace_exclude/`，分别训练三个站点的逻辑回归和随机森林，评估七种方法。脚本对训练、验证、测试与 2026 年保留集的输入、标签和时间顺序做检查，最终写入以下本地文件：

```text
runtime/m3-evaluation/
├── m3_extended_results.json    参数、数据哈希、各期指标和区间
├── m3_predictions.csv          2023—2026 年逐日预测
├── models_HKO.joblib           HKO 两个已训练模型
├── models_LFS.joblib           LFS 两个已训练模型
└── models_SHA.joblib           SHA 两个已训练模型
```

上述输出和完整数据包不会被 Git 跟踪。本目录的 `m3_extended_results.json` 是本次评估的固定记录；`project_experiments_original.json` 保存原项目在参考提交中的 30 组实验结果，`project_experiments_rerun.json` 保存本次重跑记录。核验脚本会对照两份记录，并从逐日预测及保存模型重新计算和检查结果，不会改写原项目的实验结果。

若冻结数据已放在其他位置，可同时指定两个脚本的数据路径，例如：

```powershell
python scripts/m3_extended_evaluation.py --dataset-dir "D:\你的路径\RainGuard_HK_Dataset"
python scripts/verify_m3_results.py --dataset-dir "D:\你的路径\RainGuard_HK_Dataset"
```

扩展评估可通过 `--output-dir` 指定其他输出目录，核验时通过 `--results-dir` 指向相同目录。模型文件使用记录的 Python 和 scikit-learn 版本；不同环境可能产生极小浮点尾差。

## 使用边界

2026 年保留集在本次扩展评估中已经使用，且只包含 1—8 月的合格样本；如果后续需要未查看过的最终评估，应另外预留数据。25 mm 是项目自定义的次日站点日雨量标签，不是官方暴雨警告或物业水浸概率。Trace 敏感性分析、数据来源审计和实时天气展示应遵循 M1、M2 的交接口径。
