# PT 站点分流规则自动生成设计

## 目标

从 [pre-dessert-sites 站点配置目录](https://github.com/mantou568/pre-dessert-sites/tree/main/site_config/sites) 中读取站点 JSON，提取所有存在的 `domain`，生成 Clash/Mihomo 可通过 `RULE-SET` 使用的规则集，并定期更新到 [Fone-1/pt-rules](https://github.com/Fone-1/pt-rules)。

## 已确认的需求

- 收录源目录中所有含有 `domain` 字段的 JSON，不根据 `public` 字段筛选。
- 规范化域名：移除协议、路径和端口，转成小写，去重并按字典序排序。
- 每个域名输出一行 `DOMAIN,域名`。
- 规则文件保存于仓库根目录 `PrivateTracker.list`。
- 每周日 02:00 UTC 自动运行，并提供 GitHub Actions 手动触发入口。
- 规则内容没有变化时跳过提交；变化时由 GitHub Actions 提交并推送。
- 使用 Python 标准库实现生成脚本，不引入第三方依赖。

## 方案结构

仓库包含规则文件、Python 生成脚本和 GitHub Actions 工作流。工作流启动后，脚本先获取上游站点 JSON 文件清单，再下载并解析文件，提取、规范化域名并生成排序去重后的规则。工作流比较生成文件与仓库中的版本：仅在内容变化时提交和推送。

规则集订阅地址：

```text
https://raw.githubusercontent.com/Fone-1/pt-rules/main/PrivateTracker.list
```

在客户端的远程规则集配置中填入上述订阅地址；具体配置语法由客户端决定。

## 校验与失败处理

- 每个网络请求设置超时；上游请求失败时任务失败。
- JSON 格式错误、存在但无效的 `domain`、规则文件为空时任务失败。
- 缺少 `domain` 字段的 JSON 跳过。
- 任何失败都不应以部分结果覆盖仓库中已有的有效规则文件。
- 输出检查非空、格式符合 `DOMAIN,域名`，并验证提取出的域名。
- Actions 日志记录读取的 JSON 数量和生成的规则数量。
- 工作流授予 `GITHUB_TOKEN` 仓库内容写入权限；不保存额外凭据。
- GitHub Actions 的 UTC 定时启动可能有少量延迟。

## 假设

- 上游目录仍使用 JSON 文件，站点地址仍存放于顶层 `domain` 字段。
- 动态生成时间不写入规则文件，以保证数据未变化时文件内容也保持不变。
- GitHub 仓库允许 Actions 使用 `GITHUB_TOKEN` 写入内容。
- 规则的预期使用方接受逐行 `DOMAIN,域名` 格式。

## 决策记录

| 决策 | 选择 | 考虑过的选项与理由 |
| --- | --- | --- |
| 输入筛选 | 收录所有含 `domain` 的 JSON | 不按 `public` 筛选，符合“目录中所有 JSON 的 domain”要求。 |
| 规则规范化 | 小写、移除协议/路径/端口、去重、排序 | 输出稳定，便于审查差异，并避免重复规则。 |
| 实现方式 | Python 标准库脚本加 GitHub Actions | 逻辑可本地复用，依赖少；内联全部逻辑会让工作流难维护。 |
| 更新计划 | 每周日 02:00 UTC，另提供手动触发 | 已确认的每周自动更新计划及运行时间。 |
| 提交策略 | 仅规则内容变化时提交 | 避免无效提交；因此不写动态时间戳。 |
| 失败策略 | 抓取或校验失败即停止 | 防止不完整数据覆盖最后一份有效规则。 |
| 凭据 | 使用仓库 `GITHUB_TOKEN` | 无需保存个人访问令牌；Actions 需有内容写权限。 |

## 实施范围

## 实施状态

- `generate_rules.py` 实现上游 JSON 抓取、字段解析、域名校验、规范化、去重排序和原子写入。
- `.github/workflows/update-rules.yml` 配置每周日 02:00 UTC 定时任务、手动触发及内容变化时提交推送。
- 首次生成读取 193 个 JSON，生成 193 条唯一规则；格式、排序和重复项检查均通过。
- 已推送至 `main`，首个实现提交为 `acd461a`。
- 已通过 GitHub Raw URL 验证远端规则文件返回 HTTP 200 且包含 193 行，并确认 GitHub Actions 将工作流识别为 active。
- 定时任务尚未等到首次计划运行；实际定时运行及后续自动提交仍需由 GitHub Actions 执行记录确认。
