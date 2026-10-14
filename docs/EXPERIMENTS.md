# RainGuard HK 固定时间划分实验结果

数据来源：2026-10-12 官方数据包，三站日雨量；目标为次日总雨量≥25 mm。模型使用七维历史/日历特征，训练2000–2019、验证2020–2022、测试2023–2025。2026年不参与模型选择。

随机森林参数和逻辑回归配置在查看测试结果前固定，未做测试集参数搜索。阈值依据验证集F1选择；完整参数、版本、输入CSV哈希、计数和混淆矩阵见 hk-web/data/experiments.json。AP 使用 sklearn average_precision_score。

| 微量雨策略 | 站点 | 方法 | 测试 AP | ROC-AUC | Brier | F1 | 召回 |
|---|---|---|---:|---:|---:|---:|---:|
| exclude | HKO | train_prevalence | 0.149 | 0.500 | 0.127 | 0.259 | 1.000 |
| exclude | HKO | seasonal_prevalence | 0.220 | 0.668 | 0.123 | 0.323 | 0.681 |
| exclude | HKO | persistence | 0.263 | 0.661 | 0.174 | 0.421 | 0.426 |
| exclude | HKO | logistic_regression | 0.362 | 0.758 | 0.113 | 0.381 | 0.596 |
| exclude | HKO | random_forest | 0.349 | 0.755 | 0.114 | 0.408 | 0.638 |
| exclude | LFS | train_prevalence | 0.049 | 0.500 | 0.047 | 0.000 | 0.000 |
| exclude | LFS | seasonal_prevalence | 0.104 | 0.762 | 0.045 | 0.170 | 0.520 |
| exclude | LFS | persistence | 0.105 | 0.611 | 0.071 | 0.263 | 0.260 |
| exclude | LFS | logistic_regression | 0.194 | 0.841 | 0.043 | 0.274 | 0.320 |
| exclude | LFS | random_forest | 0.158 | 0.834 | 0.043 | 0.216 | 0.420 |
| exclude | SHA | train_prevalence | 0.082 | 0.500 | 0.075 | 0.000 | 0.000 |
| exclude | SHA | seasonal_prevalence | 0.178 | 0.773 | 0.070 | 0.268 | 0.544 |
| exclude | SHA | persistence | 0.172 | 0.643 | 0.108 | 0.344 | 0.344 |
| exclude | SHA | logistic_regression | 0.326 | 0.860 | 0.064 | 0.359 | 0.433 |
| exclude | SHA | random_forest | 0.322 | 0.867 | 0.064 | 0.378 | 0.544 |
| zero | HKO | train_prevalence | 0.078 | 0.500 | 0.072 | 0.000 | 0.000 |
| zero | HKO | seasonal_prevalence | 0.156 | 0.754 | 0.068 | 0.216 | 0.337 |
| zero | HKO | persistence | 0.166 | 0.640 | 0.104 | 0.337 | 0.337 |
| zero | HKO | logistic_regression | 0.284 | 0.845 | 0.063 | 0.358 | 0.581 |
| zero | HKO | random_forest | 0.283 | 0.843 | 0.063 | 0.380 | 0.628 |
| zero | LFS | train_prevalence | 0.049 | 0.500 | 0.047 | 0.000 | 0.000 |
| zero | LFS | seasonal_prevalence | 0.104 | 0.762 | 0.045 | 0.170 | 0.520 |
| zero | LFS | persistence | 0.105 | 0.611 | 0.071 | 0.263 | 0.260 |
| zero | LFS | logistic_regression | 0.194 | 0.841 | 0.043 | 0.274 | 0.320 |
| zero | LFS | random_forest | 0.158 | 0.834 | 0.043 | 0.216 | 0.420 |
| zero | SHA | train_prevalence | 0.082 | 0.500 | 0.075 | 0.000 | 0.000 |
| zero | SHA | seasonal_prevalence | 0.178 | 0.773 | 0.070 | 0.268 | 0.544 |
| zero | SHA | persistence | 0.172 | 0.643 | 0.108 | 0.344 | 0.344 |
| zero | SHA | logistic_regression | 0.326 | 0.860 | 0.064 | 0.359 | 0.433 |
| zero | SHA | random_forest | 0.322 | 0.867 | 0.064 | 0.378 | 0.544 |

该结果是一次预先固定协议的离线实验，未报告统计显著性。两个微量雨策略的可用目标日期集合不同，不能把指标变化直接解释为微量雨处理的因果效果。随机森林不一定优于简单模型，请比较实际结果。

本实验没有真实水浸/损失标签，不能给出物业水浸概率或现场安全结论；也没有完成助手人工问答准确率评价。历史数据有月度发布滞后，不能将离线模型输出冒充今天实时预测。
