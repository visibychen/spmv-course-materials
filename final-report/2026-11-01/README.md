# csrspmv课程实验报告与最终交付

2026年11月1日完成。最终代码为optimization/v2上的a566fd1，提交名 **Final optimized version**；算法仍为已验收9b652e8。本次只增加构建/运行/检查脚本并完善README，没有新增优化版本。原始master保持9352c86。

- [上游PR #1](https://github.com/jamtrott/csrspmv/pull/1)：目标jamtrott/csrspmv的master，当前Open，尚未合并。
- [Word可编辑报告](csrspmv实验报告.docx)
- [PDF提交报告](csrspmv实验报告.pdf)

报告共15页、7章、12张图片。包括原始内核和团队调用源码、v1至v3的开发选择、v2的验证/串行/work/short8/merge方法、34份输入及实验方法、优势场景柱状图、分析和两个仓库提交记录。正文首行2字符、1.5倍行距、小四宋体；三级标题按小三/四号/小四加粗宋体，英文与数字统一Times New Roman。图号按图x-y连续编号。

## 数据与截图

主要性能数据只取experiments/2026-10-26-v2验收批次，不混合后续标准CSR加载器结果。report-data.json保存数据快照，chart-data.json保存图表所用16条版本记录。结果章节按要求展示优势，明确输入条件和成本口径，不报告为全输入平均收益或端到端承诺。开发章节分别解释后续版本未通过其共同门槛。

assets中的源码/提交历史图片是浏览器对真实git show/git log输出的截图；只加语法高亮、行号和显示折行，没有改写源码或捏造界面。PNG对应的逐字文本、HTML、提交和行号在figure-sources.json及assets中保留。fig7-3为真实公开上游PR页面截图，非重建界面。fig5-1至fig5-3由Matplotlib生成。材料仓库提交截图采于本报告归档提交之前，故不自引用当前材料提交。

## 复现报告

Windows上需要Python及python-docx、Matplotlib、Pillow、PyMuPDF、pywin32，并安装宋体、Times New Roman和Microsoft Word。核心程序的Linux/WSL运行依赖见核心README，不需要这些文档包。

~~~
python build_report.py --output-dir <输出目录>
python export_report.py <输出目录>/csrspmv实验报告.docx --qa <内部QA目录>
~~~

audit_document.py中OUT指向本次Windows交付目录；换机器时先改为自己的输出目录再运行。报告重建从保存的report-content.json、report-data.json与assets开始；不要在本归档重新运行extract_evidence.py覆盖历史截图或已有Git输出。新截图或新实验应放在新目录。

本机会话缺少文档依赖加载工具/捆绑运行时，规范renderer也因pdf2image缺失无法启动，失败原日志保留于raw/canonical-render.log。因此采用已安装Microsoft Word原生导出PDF，并由PyMuPDF生成逐页PNG进行视觉检查，避免字体替换。只交付Word/PDF；QA PNG为内部中间产物。document-audit.json记录字体、字号、缩进、行距、图号、图表值、PDF字体和输出SHA；visual-review.json记录15页逐页检查与PNG哈希，render-audit.json保留分页/字体/页面文本信息。

## 代码与脚本验收

portable和native两轮构建与make check均通过，每轮5368项；scripts/check.sh额外核对test.mtx在R=3时original/v2都输出(9,3,9,6)。另8组参数/不同调用目录/后端覆盖检查见release-script-checks.json，构建与测试原始输出见raw。

pull-request.json保留PR实际创建记录。GitHub连接器创建时返回403，随后使用本机既有GitHub认证完成用户授权的上游PR；没有保存认证凭据。delivery-provenance.json证明最终代码的src/Makefile/tests/docs与原v2相同。当前报告承载提交号请查看所属Git提交，避免内部自引用。
