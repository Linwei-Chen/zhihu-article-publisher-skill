# Zhihu Article Publisher

一个把本地 Markdown 文章一次性发布到知乎专栏或独立文章的工具，自动上传本地图片、转换 LaTeX 公式，并处理知乎编辑器常见的格式问题。

## 解决什么问题

如果你经常在本地写长文，应该很熟悉这套流程：

1. 在本地 Markdown 里写好了图文交错的内容；
2. 知乎编辑器不能直接读取本地图片路径；
3. 你需要一张一张把图片拖进知乎，再手动调整回原位置；
4. LaTeX 公式还要单独处理，经常被转成乱码或普通文本；
5. 表格、列表、引用、代码块等格式也要反复修正。

这个 Skill 的目标就是把这些重复劳动压缩成一条命令：

```bash
python zhihu_publish.py article.md --column c_xxxxxxxx -t 19590195 --json
```

它会：

- 读取本地 Markdown；
- 找到文章里的本地图片，并按原始位置上传到知乎；
- 把 `$...$` 和 `$$...$$` 公式转成知乎原生公式；
- 把 Markdown 转换成知乎可以接受的 HTML；
- 自动处理表格、粗体、斜体等知乎编辑器的格式差异；
- 发布到指定专栏，或省略 `--column` 发布为独立文章；
- 发布后返回文章 URL。

也就是说，你只需要正常写 Markdown，剩下的发布环节交给它。

## 能达到什么效果

以下内容都可以直接发布：

- 标题、段落、列表；
- 本地图片；
- 行内公式 `$E=mc^2$`；
- 独立公式：

```tex
$$
\nabla \cdot \mathbf{E} = \frac{\rho}{\epsilon_0}
$$
```

- Markdown 表格；
- 引用；
- 代码块；
- 粗体、斜体；
- 知乎专栏文章；
- 知乎独立文章。

发布后你得到的是一个真实的知乎文章链接，而不是一个还需要二次整理的草稿。

## 前置条件

你需要准备：

1. `pandoc`

   ```bash
   brew install pandoc
   ```

2. Python 环境里可用：

   - `Pillow`
   - `zhihu_cli` / `pyzhihu-cli`

3. 已登录知乎 CLI：

   ```bash
   zhihu login --qrcode
   ```

4. 如果要发布到专栏，需要知道专栏 ID，形如：

   ```text
   c_1027873866512740352
   ```

## 最简用法

假设你有一篇 `article.md`：

```bash
python /path/to/zhihu_publish.py article.md --column c_xxxxxxxx --json
```

发布后会输出类似：

```json
{
  "id": "123456789",
  "url": "https://zhuanlan.zhihu.com/p/123456789",
  "title": "我的文章标题",
  "column": "c_xxxxxxxx",
  "topics": []
}
```

## Markdown 写法示例

```markdown
# 我的知乎文章

这是一段正文。

![示意图](./images/example.jpg)

这是一个行内公式：$a^2 + b^2 = c^2$。

下面是独立公式：

$$
\int_a^b f(x)\,dx = F(b) - F(a)
$$

| 名称 | 说明 |
| --- | --- |
| Markdown | 本地写作格式 |
| Zhihu | 发布目标 |
```

图片路径可以写成相对路径，例如：

```markdown
![示意图](./images/example.jpg)
![示意图](images/example.png)
```

工具会根据 Markdown 文件所在目录解析这些路径。

## 发布到专栏

```bash
python /path/to/zhihu_publish.py article.md \
  --column c_xxxxxxxx \
  --json
```

如果你使用的是 Codex Skill，并且指的是“人工智能与计算机视觉笔记”，专栏 ID 是：

```text
c_1027873866512740352
```

## 发布为独立文章

不传 `--column`：

```bash
python /path/to/zhihu_publish.py article.md --json
```

## 添加话题

使用 `-t` 或 `--topic`，可以传多个：

```bash
python /path/to/zhihu_publish.py article.md \
  --column c_xxxxxxxx \
  -t 19590195 \
  -t 19588757 \
  --json
```

## 只预览，不发布

发布前建议先跑一次 dry run：

```bash
python /path/to/zhihu_publish.py article.md --dry-run
```

它不会上传图片，也不会发布文章，只会在 Markdown 同目录生成：

```text
article.zhihu.html
```

这个文件可以用来检查标题、图片引用、公式、表格等格式是否正常。

## 命令参数

| 参数 | 说明 |
| --- | --- |
| `markdown` | 必填，本地 Markdown 文件路径 |
| `--column c_xxx` | 可选，指定知乎专栏 ID；不传则发布为独立文章 |
| `-t TOPIC_ID` | 可选，添加知乎话题，可重复使用 |
| `--title TITLE` | 可选，覆盖文章标题 |
| `--dry-run` | 可选，只生成本地知乎 HTML 预览，不发布 |
| `--json` | 可选，输出 JSON 结果 |

## 标题规则

默认规则是：

1. 如果指定了 `--title`，使用指定标题；
2. 否则使用 Markdown 中的第一个一级标题；
3. 如果没有一级标题，会报错。

推荐直接在 Markdown 开头写：

```markdown
# 你的文章标题
```

## 图片处理逻辑

工具会：

1. 扫描 Markdown 里的图片引用；
2. 跳过 `http://`、`https://`、`data:` 开头的图片；
3. 解析本地图片的绝对路径或相对路径；
4. 上传前转换成 JPEG，避免知乎图片处理队列卡住；
5. 把上传后的知乎图片地址替换回原来的位置；
6. 保留图片的 alt 文本作为知乎图片说明。

所以你不需要提前把图片上传到图床。

## 公式处理逻辑

工具会先把 Markdown 转成 HTML，然后把：

```markdown
$E=mc^2$
```

转换成知乎原生的行内公式：

```html
<img eeimg="1" src="https://www.zhihu.com/equation?tex=E%3Dmc%5E2" />
```

把：

```markdown
$$
E=mc^2
$$
```

转换成知乎原生的独立公式：

```html
<img eeimg="2" src="https://www.zhihu.com/equation?tex=E%3Dmc%5E2" />
```

这样知乎会把它作为公式渲染，而不是当成普通文本。

## 知乎登录与隐私

工具依赖本地知乎 CLI 的登录状态。

它不会：

- 读取或保存你的知乎 Cookie 到仓库；
- 打印 Cookie；
- 把 Cookie 上传到第三方服务；
- 在发布流程外传输数据。

它只是通过本地的 `pyzhihu-cli` 与知乎接口交互。

## 如果登录失效

运行：

```bash
zhihu login --qrcode
```

重新扫码即可。

## 如果图片路径报错

检查 Markdown 中的图片路径是否正确：

```markdown
![示意图](./images/example.jpg)
```

如果 Markdown 文件在：

```text
/Users/you/Documents/papers/article.md
```

图片应该在：

```text
/Users/you/Documents/papers/images/example.jpg
```

相对路径是相对于 Markdown 文件本身解析的，不是相对于终端当前目录。

## 如果公式没有正确显示

确认公式写法是：

```markdown
这是行内公式：$E=mc^2$。
```

或：

```markdown
$$
E=mc^2
$$
```

不要把公式写进普通代码块里：

````
```tex
E=mc^2
```
````

代码块里的内容会被当成代码，不会转换成公式。

## 发布前检查清单

发布前建议确认：

1. Markdown 里有一个一级标题；
2. 图片路径真实存在；
3. 公式使用 `$...$` 或 `$$...$$`；
4. 如果要发专栏，已准备好专栏 ID；
5. 如果要加话题，已准备好话题 ID；
6. 先跑 `--dry-run` 检查预览；
7. 正式发布后打开返回的 URL 确认。

## 适合谁用

适合这些场景：

- 经常写图文交错的技术文章；
- 文章里有大量公式；
- 不想在知乎编辑器里反复手动上传图片；
- 希望用 Markdown 管理自己的内容；
- 希望一条命令发布到指定专栏或独立文章。

## 不适合谁用

以下情况不适合：

- 需要非常复杂的知乎富文本排版；
- 文章需要频繁使用知乎特有的卡片、视频、投票等组件；
- 需要精确控制每个元素在知乎编辑器里的内部结构；
- 想要批量同步到多个平台。

## 许可

目前没有附加开源许可证。如果你希望基于这个仓库二次开发或分发，请先联系仓库作者确认。
