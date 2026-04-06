# Vida 本地语料说明

## 本 skill 使用的主语料

- `web/src/data/articles.json`
  - 结构化文章数据
  - 包含标题、时间、赞同数、原始 URL、全文内容、图片数量
- `archive/vida_articles_extract/extracted.md`
  - 从 `00后富一代vida文章.pdf` 提取的全文归档
- `archive/vida_articles_extract/manifest.json`
  - 提取过程的清单文件

## 语料统计

- 总内容数：564
- 时间范围：`2020-11-23` 到 `2025-02-27`
- 内容类型：
  - 回答：88
  - 专栏：28
  - 想法：448

## 使用原则

- 本轮蒸馏只使用仓库内已有内容，不额外引入网络搜索
- 因此：
  - 一手语料很强
  - 第三方评价和正式访谈维度偏弱

## URL 字段说明

- `web/src/data/articles.json` 里的 `url` 字段不是我蒸馏时去联网抓取的来源
- 它是从 `archive/vida_articles_extract/extracted.md` 里的文章头部原样解析出来的历史字段
- 对应脚本见 `scripts/prepare_vida_dataset.py`
  - `ARTICLE_HEADER_RE = re.compile(r"^第\\s*(\\d+)\\s*篇\\s*:\\s*(https?://\\S+)$")`
- 所以这些 URL 的作用是“文章身份指纹 / 原始出处记录”
- 如果其中一部分现在已经失效，不影响本 skill 的语料真实性，因为真正用于蒸馏的是本地提取后的正文内容

## 高信号参考条目

- `关于创业有什么建议？`
- `给00后们的话`
- `如何看待2022年金融危机？`
- `我爸的A股投资思维`
- `币圈到底是谁一直在赚钱？`
- `高质量英文CT信息源列表`
- `为什么我要开这个知乎账户？`
- `2025我的1000万刀美股战略布局`
- `如何看待bybit被黑客攻击盗取15亿美元资产`

## 备注

- 如果后续要把这个 skill 提升到更高版本，建议补：
  - 视频/播客 transcript
  - 外部媒体采访
  - 第三方评价与质疑材料
