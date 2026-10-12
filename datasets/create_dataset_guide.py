"""Create the human-readable dataset inventory and empty evaluation/fieldwork forms."""
import csv
import json
from pathlib import Path
import shutil

root=Path(__file__).parent/'RainGuard_HK_Dataset'
summary=json.loads((root/'quality/summary.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
entries=[e for e in manifest['entries'] if 'error' not in e]
catalogs=[e for e in entries if e['id'].startswith('catalog-')]
sources=['# 官方来源与采集凭证\n',
    '每份原文均有独立 URL、采集时间、HTTP 信息、字节数和 SHA-256，见 `manifest.json`。下表是本快照的可点击来源。历史原文不截断年份；CSV 清洗层与衍生特征另存。\n',
    '| 资源 | 来源 | 采集时间 UTC | 原文文件 |\n|---|---|---|---|']
for e in entries:
    sources.append(f'| {e["id"]} | [{e["publisher"]}]({e["url"]}) | {e["fetched_at_utc"]} | `{e["path"]}` |')
(root/'SOURCES.md').write_text('\n'.join(sources)+'\n',encoding='utf-8')

readme=f'''# RainGuard HK 香港天气决策支持项目数据集

采集日期：2026-10-12。用途：SDSC6004 小组项目的历史降雨分类、香港真实天气展示、官方知识检索和人工复核流程。所有气象观测及知识原文均来自官方公开资源；衍生特征由本项目计算。该数据包不含合成观测，也不含任何 API Key。

## 数据规模

| 内容 | 本次实际规模 |
|---|---:|
| 官方目录中全部历史日雨量站 | {summary['rainfall_stations']} 站 |
| 全部气象日记录 | {summary['climate_rows']:,} 条 |
| 其中历史日雨量 | {summary['rainfall_rows']:,} 条 |
| HKO、LFS、SHA 自 2000 年起的日雨量 | {summary['core_rainfall_rows']:,} 条 |
| 三站核心特征，排除微量雨 | {summary['core_features_exclude']:,} 个样本 |
| 三站核心特征，微量雨按零处理 | {summary['core_features_zero']:,} 个样本 |
| 外部知识库 | {summary['knowledge_documents']} 份官方资料，{summary['knowledge_chunks']} 个片段 |
| 当前天气接口 | {summary['realtime_sources']} 项 |

这些是不同层的数据，不应相加称为独立训练样本。温度、湿度及气压只采集三个核心站；25 个站的扩展特征仅使用雨量。所有来源成功与否见 `quality/summary.json`；最新运行规模以该 JSON 为准。

## 时间覆盖与“完整”的定义

采集了官方目录列出的 25 站**全部可下载历史日雨量年份**，而非每站从同一天开始。HKO 日雨量自 1884-03-01，LFS 自 1985-10-01，SHA 自 1984-10-01；本次三个核心站最新均为 2026-08-31。其他站的完整起止日期、缺测、微量雨和不完整标记见 `quality/source_coverage.csv`。

完整历史资源仍会有官方原始缺测、测站投运时间差及战争期间等日历空档。没有插值创造缺失日期，没有把缺测补零。官方历史日系列按月更新，因此本包**没有 2026 年 9–10 月的完整已审定日序列**。实时快照另有各自的观测时间，不能与历史气候系列混称为同一时效。

## 建议从哪里开始

1. 直接训练：`training/trace_exclude/train.csv`、`validation.csv`、`test.csv`。这些是三站合并的固定时间划分，训练模型时应按站分别评价；`station` 是分组字段。
2. 数据探索：`processed/rainfall_core_2000_onward.csv` 和 `core_daily_weather.csv`。
3. 区域扩展：`processed/rainfall_all_stations.csv`、`training/extension_features_trace_exclude.csv`。扩展站与核心站分开，避免无意改变提案的三站实验。
4. 实时页面：`realtime/latest_snapshot.json`、`station_hourly_rainfall.csv`、`district_rainfall.csv`、`tides.csv`、`nowcast.csv`。
5. 知识助手：`knowledge/documents.json` 与 `chunks.jsonl`。片段保留 URL、原文哈希与字符偏移。
6. 数据库查询：`rainguard_hk.sqlite`。包含 `climate_daily`、`core_features`、`knowledge_documents`、`knowledge_chunks`、`realtime_snapshots`、`source_manifest` 六表；查询示例见 `examples.sql`。
7. 原型兼容：`application/history.json`、`snapshot-raw.json`、`knowledge.json`。仅供接入，不会自动覆盖网站。原文路径相对于本数据包；迁移时需要保留或重写路径。现有原型的训练器默认排除微量雨，与本包主分析一致；它最初不使用 1999 年末作为滚动上下文，因此首年样本数可能稍有差异。

CSV 使用 UTF-8 BOM，Excel 或 Python 都能读取。数字空单元格表示缺失，不能当成 0。SQLite 中缺失为 NULL。

## 训练标签、特征与固定划分

预测日为 d，标签 `target_ge25mm = 1[日雨量(d) ≥ 25 mm]`，**25 mm/日是课程自定义标签**，与官方暴雨信号的小时阈值不同，也不是水浸标签。

输入只使用 d−1 及以前：过去 1/2/3 日雨量的 log1p、过去 7 日总雨量的 log1p、过去 7 日雨量 ≥1 mm 的日数；另加预测日已知的日历正余弦。`feature_asof_date` 明确记录输入截至哪天。2000 年初可使用 1999 年末真实观测作为七日上下文，1999 年目标不进入训练。

| split | 目标日期 | 主版本核心样本数 |
|---|---|---:|
| train | 2000-01-01 至 2019-12-31 | 15,251 |
| validation | 2020-01-01 至 2022-12-31 | 2,488 |
| test | 2023-01-01 至 2025-12-31 | 2,433 |
| holdout_2026_onward | 2026-01-01 起，仅到来源已发布日期 | 590 |

上述合计 20,762。微量雨按零版本相同四组分别为 20,955、3,249、3,213、729。详细逐站正样本数见 `quality/split_counts.csv`。测试集保持锁定；标准化、缺测策略、模型参数和分类阈值只在训练/验证阶段确定。2026 年数据不用于模型选择。

`trace_exclude` 要求目标日及前七日均为可解析非微量数值且完整性为 C。`trace_zero` 仅为敏感性实验，把官方 `Trace` 暂按 0 mm 计算，保留原文的 trace 标记；这不表示仪器观测为 0。两者均拒绝缺日期、缺值和非 C 标记窗口。`quality/exclusions.csv` 按先遇到的排除原因统计，原因不重复计数。

额外气象变量在 `core_daily_weather.csv` 保留缺失和完整性信息，尚未合并入七维基线特征。若扩展模型使用该表，必须把这些变量移动到 d−1 或更早，并只在训练集拟合插补器；不能直接把 d 日湿度/温度当作预测 d 的输入。

## 实时展示与实际应用

本次快照包括 36 个自动气象站过去一小时雨量、18 区雨量摘要、7 个潮位站、全量网格临近预报，以及当前天气、九天预报、本地预报、警告摘要、警告详情和特别天气提示。站点/数量可能随官方资源改变，读取时应以原文为准。网格 CSV 保留官方完整范围，未仅截取演示区域。

原始响应中空警告对象代表接口当时没有相应生效警告，不代表下载失败。雨量观测为临时数据；自动站 HKO 与气候数据库的 HKO 日雨量来源存在区别，不能盲目拼接。临近预报是官方预测，不是实测标签；潮位不是物业积水深度。

`quality/current_inference_readiness.json` 检查当前日模型所需的最近七个日雨量是否齐全。当前已审定历史系列滞后，因此实时页面可展示新观测，**次日分类模型只能做有日期标记的历史回放**。要真实实时运行日模型，需另建连续日聚合数据、处理来源差异并重新验证。不要沿用八月末窗口冒充今天输入。

## 官方知识库与人工评价

知识资料分别来自香港天文台、渠务署、劳工处，覆盖暴雨、局部大雨、新界北部水浸、雷暴、风暴潮、防洪及恶劣天气工作安排。包含七份网页，以及从劳工处索引追踪下载的两份完整 PDF 附件（工作守则和工作安排一览），避免只有索引而缺少正文。原 HTML/PDF 存于 `raw/`，正文保留原始简/繁体措辞；展示层可转简体，但引用应能回到原文。片段仅为资料，不能作为助手系统指令。没有用生成式模型伪造原文或答案。

`evaluation/questions_30.csv` 是**项目自行编写的待评审问题清单**，不是官方标注数据。`evaluation/reviewer_scores_blank.csv` 预留三种回答条件和两位评审员共 180 行，模型回答及评分均留空。先冻结问题、当前快照和评价规则，再执行无知识、仅知识、知识加观测三个条件。

`fieldwork/facilities_blank.csv` 与 `inspections_blank.csv` 只有表头，需真实物业授权信息和人工巡检后填写。已包含 `processed/top50_observed_rainfall_days.csv` 用于真实高雨量历史回放，但这些是“高雨量日”，没有声称对应实际物业水浸事件。

## 更新与可复现

本包根目录带有 `collect_dataset.py`，使用 Python 3.10+ 及 PyMuPDF（PDF 正文抽取），无需付费模型或 Key：

```powershell
python -m pip install -r requirements.txt
python collect_dataset.py --output . --live-only
python collect_dataset.py --output . --offline
```

重新采集全部官方资源用 `python collect_dataset.py --output .`。实时更新已实际运行验证；不会覆盖旧原文批次。离线重建从 `manifest.json` 指定的原文重建，SHA-256、数据库完整性、唯一键、固定划分、时间顺序和数值核对结果见 `quality/verification.json`。持续运行服务需要另行部署，工具不会自行常驻后台。

## 数据来源与使用

逐文件官方链接和采集凭证见 [SOURCES.md](SOURCES.md) 及 `manifest.json`。官方开放数据目录、API 说明 PDF、DATA.GOV.HK 条款及 HKO 刊物知识产权公告已保存于原文层；本项目没有把官方网页素材重新声明为 MIT 许可。数据/知识资料的提供者为香港特别行政区政府相关部门，使用时保留来源、时间与适用条款。

## 仍需自行采集的内容

公开气象数据和知识原文已收集到本包。以下没有被公开天气数据自动解决：真实物业资产、实际积水/损失标签、巡检记录、人工问答金标准及评审分数；尚未形成多日实时快照档案，也没有完整历史网格预测/警告档案。当前项目的日雨量分类可直接训练，物业水浸概率模型和助手准确率结论则不能据此宣称已经完成。
'''
(root/'README_数据集说明.md').write_text(readme,encoding='utf-8')

dictionary='''# 数据字典

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
'''
(root/'DATA_DICTIONARY.md').write_text(dictionary,encoding='utf-8')
(root/'examples.sql').write_text('''-- SQLite; dates in Hong Kong local calendar.
SELECT station, variable, MIN(date), MAX(date), COUNT(*) FROM climate_daily GROUP BY station, variable;
SELECT station, trace_policy, split, COUNT(*), SUM(target_ge25mm) FROM core_features GROUP BY station, trace_policy, split;
SELECT * FROM core_features WHERE station='HKO' AND trace_policy='exclude' AND split='train' ORDER BY target_date;
SELECT station,date,value,source_path,source_line FROM climate_daily WHERE variable='RF' AND date='2023-09-07' ORDER BY value DESC;
SELECT document_id, title, publisher, url FROM knowledge_documents;
SELECT source_id,fetched_at_utc,source_url FROM realtime_snapshots;
''',encoding='utf-8')

questions=[
('rain-warning','黄色暴雨警告表示什么？与本项目的25毫米日雨量标签有什么区别？'),
('rain-warning','红色暴雨信号生效时，市民应注意什么？'),
('rain-warning','黑色暴雨信号生效时，应如何理解留在安全地方的指引？'),
('rain-warning','未发出暴雨信号时，能否保证个别低洼地点不会水浸？'),
('rain-warning','暴雨信号的每小时雨量标准能否直接当作日雨量标准？'),
('local-rain','局部地区大雨提示与全港暴雨信号有什么区别？'),
('local-rain','个别地区大雨时，应如何结合地区观测查看官方提示？'),
('north-flood','新界北部水浸特别报告关注什么情况？'),
('north-flood','北区物业负责人收到水浸特别报告后，应查看哪些官方资料？'),
('storm-surge','风暴潮是什么？与天文潮有什么关系？'),
('storm-surge','潮位偏高是否等于某栋楼的积水深度？'),
('flood-prevention','雨季前物业应重点检查哪些排水设施？'),
('flood-prevention','水浸发生前可以采取哪些减少损失的措施？'),
('flood-prevention','可以只凭一张天气图就确定地下室安全开放吗？'),
('work-arrangements-code','恶劣天气下工作安排应依据哪些官方原则和事先约定？'),
('work-arrangements-code','复工安排是否能仅由平台天气分数自动决定？'),
('work-arrangements-code','雇主与雇员应如何事先沟通恶劣天气工作安排？'),
('thunder','雷暴警告生效时，户外巡检应注意什么？'),
('thunder','没有下雨是否就可以忽略雷电风险？'),
('thunder','安排户外活动前应查看哪些雷暴相关官方信息？'),
('rain-warning','结合冻结快照：当前有无生效暴雨警告？请列出来源与查询时间。'),
('local-rain','结合冻结快照：沙田的地区雨量记录是什么？请区分它与单站雨量。'),
('local-rain','结合冻结快照：自动站小时雨量的观测时间是什么？是否足够新？'),
('storm-surge','结合冻结快照：鲗鱼涌潮位是多少？它能证明附近物业不会水浸吗？'),
('rain-warning','结合冻结快照：未来两小时网格雨量是实测还是预测？应标注哪些时间？'),
('rain-warning','结合冻结快照：九天预报中的降雨概率类别能否当作已经发生的雨量？'),
('rain-warning','如果当前警告接口无法访问，可以把缓存中的空对象直接说成没有警告吗？'),
('local-rain','如果雨量观测超过允许时效，应怎样向物业值班员表达结论？'),
('flood-prevention','若没有物业排水巡检记录，助手能否声称现场排水设施正常？'),
('rain-warning','历史数据只到八月末时，能否把历史模型输出当成今天的实时预测？'),
]
evaluation=root/'evaluation';evaluation.mkdir(exist_ok=True)
with (evaluation/'questions_30.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['question_id','question','related_document_id','origin','gold_answer','gold_evidence'])
    for i,(doc,q) in enumerate(questions,1):w.writerow([f'Q{i:02}',q,doc,'project_authored_pending_review','',''])
with (evaluation/'reviewer_scores_blank.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['question_id','condition','reviewer','frozen_snapshot_manifest','model_answer','factual_support_0_2','citation_correctness_0_2','staleness_handling_0_2','notes'])
    for i in range(1,31):
        for condition in ['no_grounding','official_text_only','official_text_plus_observations']:
            for reviewer in ['reviewer_1','reviewer_2']:w.writerow([f'Q{i:02}',condition,reviewer,'','','','','',''])
(evaluation/'评审说明.md').write_text('''# 人工评价待办

问题为项目自编，不是官方用户问答。先由两位组员核对原文并填写 gold_answer/gold_evidence，再冻结同一个原文和实时快照批次，分别运行三种回答条件。填入真实模型回答后，两位评审独立评分：0=错误或缺失，1=部分满足，2=充分满足。事实支持、引用正确性、时效识别分别评价，保留分歧并在讨论后记录一致结果。若某问题没有时效要求，在 notes 标明“不适用”，相应时效分留空；不得用 0 代表不适用。完成前不能报告助手准确率。
''',encoding='utf-8')
fieldwork=root/'fieldwork';fieldwork.mkdir(exist_ok=True)
for filename,fields in [('facilities_blank.csv',['facility_id','facility_name','district','latitude','longitude','official_address_source','authorized_contact','recorded_at_hkt']),('inspections_blank.csv',['inspection_id','facility_id','observed_at_hkt','drainage_condition','observed_water_depth_cm','photo_path','observer','weather_snapshot_manifest','verified_by','notes'])]:
    with (fieldwork/filename).open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(fields)
shutil.copyfile(Path(__file__).parent/'collect_dataset.py',root/'collect_dataset.py')
shutil.copyfile(Path(__file__).parent/'requirements.txt',root/'requirements.txt')
print('Dataset guides, source inventory, 30 pending questions and blank fieldwork forms prepared.')
