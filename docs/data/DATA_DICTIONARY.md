# 数据字典

所有日期为公历；气象观测的日/时为香港时间（UTC+8）。`fetched_at_utc` 为 HTTP 抓取时间，不等同于观测时间。

## processed/climate_daily_all.csv 与雨量子表

一行 = 一个站点、变量、日期。唯一键 `(station, variable, date)`。

| 字段 | 类型/单位 | 含义 |
|---|---|---|
| station | text | 官方历史站点代码；HKO、LFS、SHA 为提案核心站 |
| station_name | text | 原 CSV 英文标题，保留来源原称 |
| variable | text | RF 日总雨量；MAXT/MINT/TEMP 日最高/最低/平均气温；RH 日平均相对湿度；MSLP 日平均海平面气压 |
| date | YYYY-MM-DD | 观测日期 |
| value | nullable number | 可解析数值，Trace/缺测保留空白，不替换为 0 |
| unit | text | RF=mm；温度=degC；RH=percent；MSLP=hPa |
| raw_value | text | 官方原始值，包含 `Trace`、`***` 等标记 |
| completeness | text | 官方 C 表示完整；其他或空白不能当完整 |
| is_trace | 0/1 | 官方值是否为微量雨 |
| quality_status | enum | numeric / trace / missing / invalid_negative |
| source_id | text | 对应 manifest 资源 ID |
| source_line | integer | 原 CSV 的记录行序号，自 1 开始；对当前官方格式也对应物理行 |
| source_path | text | 相对数据包的不可变原文路径 |

`core_daily_weather.csv` 添加每项气象变量的 `_value`、`_raw`、`_completeness`。`_value` 仅在对应来源为 C 时保留；原始数值仍可在全量气象长表查找。空值不等于零。

## training/*.csv

一行 = 一个站的次日分类样本。唯一键 `(station, target_date, trace_policy)`。

| 字段 | 类型 | 含义 |
|---|---|---|
| station | text | 站点分组 |
| target_date | date | 要预测的日期 d |
| feature_asof_date | date | 仅使用此前及当日已发生观测，即 d−1 |
| split | enum | train / validation / test / holdout_2026_onward |
| trace_policy | enum | exclude 主分析；zero 微量雨按零的敏感性分析 |
| log1p_lag1/lag2/lag3 | number | ln(1+日雨量(d−1/d−2/d−3)) |
| log1p_past7_total | number | ln(1+日雨量(d−7…d−1)之和) |
| past7_wetdays | integer | d−7…d−1 中雨量 ≥1 mm 的日数，0…7 |
| sin_dayofyear/cos_dayofyear | number | 预测日期 d 的年内日序/365.25 ×2π 的正余弦 |
| lag1_rainfall_mm | mm | d−1 日雨量，用于持续性基线 |
| target_rainfall_mm | mm | d 日雨量，只用于标签与事后评价 |
| target_ge25mm | 0/1 | d 日总雨量是否 ≥25 mm，项目自定义分类 |
| target_source_path/source_line | text/int | 可追踪到官方目标日原文 |

特征列是 `log1p_lag1, log1p_lag2, log1p_lag3, log1p_past7_total, past7_wetdays, sin_dayofyear, cos_dayofyear`。`target_*`、原文行号和 split 不能用作训练特征。按站训练或明确使用站点编码，不能让字符串日期被默认读作预测变量。

## realtime

`latest_snapshot.json` 一项 = 一个接口响应，含 source_id、source_url、raw_path、fetched_at_utc、format、payload。警告空对象是有效响应。

| 表 | 原始关键字段 | 含义 |
|---|---|---|
| station_hourly_rainfall.csv | observation_time, automaticWeatherStation, automaticWeatherStationID, value, unit | 结束时刻之前一小时自动站雨量，mm；ID 不等同于历史气候站代码 |
| district_rainfall.csv | start_time, end_time, place, min/max, unit, main | 官方地区雨量摘要，按接口提供的字段保留；不可当成整个地区平均值 |
| tides.csv | Tide Station, Date, Time, Height(m) | 实测潮位，保留官方垂直基准，不是相对地面的积水深度；基准说明以 API 文档为准 |
| nowcast.csv | Updated Date and Time, Ending Date and Time, Latitude, Longitude, Half-hourly Nowcast Accumulated Rainfall | 发布时刻、半小时预测结束时刻、网格坐标、预测累积雨量 mm，字段完整名称以 CSV 表头为准 |
| forecast payload | updateTime, weatherForecast, forecastDate, PSR 等 | 官方九天预报和降雨概率类别，不是已实现的真实结果 |

网格预测唯一记录可使用 `(发布时刻, 结束时刻, 纬度, 经度)`。没有将当前预测网格当成多年的模型训练数据。源 CSV 原字节保存在 raw 中，清洗副本可能调整换行/BOM，不承担原文哈希证明。

## knowledge

`documents.json` 保留 document_id、title、publisher、url、raw_path、text_path、fetched_at_utc、sha256。`chunks.jsonl` 保留 chunk_id、document_id、text、start_char、end_char、source_url、source_sha256；字符偏移针对抽取后的正文，不是 HTML 字节位置。900 字符片段，步长 650，有重叠。最后片段可较短。PDF 正文按页面顺序抽取，表格可能失去二维排版，精确工作安排应回查原 PDF；它不作为自动生成的金标准。`pdf_pages.jsonl` 另保留每个物理 PDF 页的文本、页号、URL、原文哈希，以便页级引用；封面和部分插图页可能没有可抽取文字，原 PDF 仍完整保存。

## manifest 与质量表

`manifest.json`：当前选用资源，含 id/url/final_url/publisher/category/format/path/sha256/bytes/http_status/http_date/last_modified/content_type/fetched_at_utc。某些服务器没有 Last-Modified，该值为空。失败记录保留 error，不能视为成功采集。

`source_coverage.csv`：逐来源日期、行数、重复日期、完整性、数值/缺测/微量/负雨量情况。`split_counts.csv`：逐站和处理策略的样本、正样本及日期范围。`exclusions.csv`：按优先原因计数。`verification.json`：原文与衍生数据核验；`current_inference_readiness.json`：当天七日输入是否可用。

## 空白人工采集表

`questions_30.csv`：项目自编问题及相关官方文档 ID，不是标注好的真实用户问答。`reviewer_scores_blank.csv`：人工评审分数、回答及备注待填写。`facilities_blank.csv`、`inspections_blank.csv` 无虚构物业或虚构巡检记录；坐标、照片和现场数据需要实际采集。
