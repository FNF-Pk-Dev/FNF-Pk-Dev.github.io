# FNF-Pk-Dev.github.io

Parker Engine 中文维基站点（`https://fnf-pk-dev.github.io/`）。

基于 **MDUI 1**（Material Design 1.0，本地自托管于 `assets/mdui/`）的零依赖静态站：
文档内容以 Markdown 源维护在 `_content/`，由 `build.py` 构建为静态 HTML。

## 本地预览 / 构建

```bash
pip install markdown   # 仅首次
python build.py        # 全量构建 docs/ 与 404.html、旧链接重定向页
python -m http.server 8901   # 本地预览 http://localhost:8901
```

- 页面结构与导航：`_nav.json`（分组、slug、源文件映射）
- 旧维基路径（`函数/Psych/…`、`LuaCodingDocs/` 等）由 `build.py` 的 `REDIRECTS` 表生成跳转页
- 被新版函数文档取代的旧分类页存档于 `_content/legacy/`（不参与构建）

## 目录

| 路径 | 说明 |
|---|---|
| `index.html` | 首页（手工维护） |
| `docs/` | 构建产出的文档页 |
| `_content/` | 文档 Markdown 源 |
| `assets/` | mdui 本地化 + 站点补充样式/脚本 |
| `build.py` / `_nav.json` | 构建脚本与导航配置 |
