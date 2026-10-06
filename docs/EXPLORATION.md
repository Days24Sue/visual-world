# 探索目录与补充资料

当前公开作品库仍使用 NGA、Cleveland、Art Institute of Chicago 的完整馆藏，不设置作品总量上限。所有浏览分类只统计有公开图片的作品。

## 艺术家身份

优先使用馆方结构化作者姓名，兼容旧馆藏中的“姓名（国籍，生卒年）”和换行格式。精确标准姓名与已整理别名关联；不做模糊的人名合并。工作室、归属、学校等署名不直接合并到画家本人。目录数量是创作者及署名数，并非经过人工确认的独立画家人数。

常见中文姓名及别名来自本站的 `curation.json`。其他姓名保留馆方原文，仍可搜索并进入作品页。

## PainterPalette

项目：https://github.com/me9hanics/PainterPalette

作者：Mihaly Hanics（Central European University, Vienna），项目此前亦有 Nurbek Bektursyn、Aset Kabdula 参与。项目采用 MIT 许可。

补充文件：https://raw.githubusercontent.com/me9hanics/PainterPalette/main/PainterPalette.csv

只使用唯一精确姓名匹配的生卒年、国籍字段。资料来源保留在画家页中。因外部资料的流派归类可能不一致，当前不导入其流派为作品标签。人物之间的影响关系也不作为已核实事实展示。

## 风格与主题

使用 Art Institute of Chicago 的 `artist_titles`、`style_titles`、`subject_titles`、`term_titles` 和文字说明。字段说明：https://api.artic.edu/docs/

风格中的世纪标签不作为流派。相同中文映射的馆方近义标签合并为筛选项；原始标签仍保留在作品记录中。每件作品可有多个风格、主题和作者。未标注内容保持未知，不使用年份或模型猜测标签。

## 时期与检索

世纪入口按作品创作年区间重叠筛选；宽时间范围的作品可同时属于多个世纪，未知年代作品只在未限制年代时显示。“时期中的创作者”来自符合该年代条件的作品，并不等价于人物在世或当地活动时间。

静态导出保持 version 2 分片格式，并增加 `search_index_version: 2`、`explore_url`。gzip 索引每行包含分片、含中文别名的检索文本、作品 ID、艺术家 ID、年份、风格 ID、主题 ID、类型 ID、来源、标题。检索先得到全部匹配 ID、总数和排序，再加载本页分片。首次检索需要现代浏览器的 `DecompressionStream` 支持。

原有 GitHub 资源索引依然保留；ArtGraph、ArtBench 尚未作为正式生产数据接入。ArtGraph 的跨库作品匹配与标签可靠性仍需验证，ArtBench 属于研究基准，不用来替代馆藏分类。
