# 登录与认证

## 选择访问方式

| 场景 | 认证与保护 | 边界 |
| --- | --- | --- |
| 浏览器看板 | 可选账号 + 共享密码；ChatLogin 会话 cookie | 写操作需同源 Origin 与 CSRF |
| 自动化 API | Bearer 或 `X-ChatBoard-Token` | 不需要浏览器 cookie/CSRF |
| 真实 executor 操作 | 外层认证通过后，仍需 `X-ChatBoard-Executor-Token` | 普通 API key 或登录会话不授予执行权限 |
| 无密码、无 API key | 保持本地无认证模式 | 不应直接暴露到不可信网络 |
| 仅 API key | 页面外壳可访问，受保护 API 需 key | 不会隐式启用密码登录 |

ChatBoard 复用 ChatLogin 的 `CallbackBackend`、`SessionManager`、`SQLiteSessionStore` 和 `require_csrf`。账号仍是可选字段；密码独享一个固定身份。不新增用户数据库、角色体系或业务所有权规则。dry-run/mock 仍是安全执行模式；真实执行和控制操作保留独立授权。

## 从 0.1.x 升级

旧的时间戳签名 cookie 不再接受，升级后需要重新登录一次；原账号、密码、API key 和配置路径不变。

新 cookie 格式为 `v2.<随机 core token>.<HMAC-SHA256>`。外层只是传输适配：仍优先使用 `CHATBOARD_AUTH_SECRET`（环境变量优先于 ChatEnv），否则使用登录密码。每次读取按当前有效密钥校验，因此轮换有效密钥会立即拒绝旧 cookie，不需要另外清会话文件。如果配置了独立签名密钥，仅修改密码不会使现有 cookie 失效；需轮换签名密钥，这与原配置优先级一致。

会话的 TTL、持久化、容量和撤销仅由 ChatLogin 管理。随机 token 的摘要保存在 `$CHATBOARD_HOME/sessions.sqlite3`；不把密码摘要作为数据库 namespace。默认 runtime root 为 `~/.chatarch/chatboard/`，最多 1024 个会话；过期记录在会话操作时清理，容量耗尽时登录返回 503。默认 TTL 为 12 小时，最小 60 秒。正常服务重启不要求重新登录；有效密钥变化、过期或撤销除外。

## 数据安全的上线流程

1. 记录当前版本、Python 环境、服务监督器和 `chatbd paths` 显示的实际路径，确认没有正在执行的任务；不要根据默认目录猜测线上数据位置。
2. 备份当前配置、后端连接配置和已有会话库；业务卡片仍留在原工作区，不运行归档、迁移、重新初始化或自动重写卡片的命令。若会话库处于使用中，使用 SQLite 一致性备份而不是只复制主数据库文件。
3. 在隔离环境验证发布 wheel 与依赖，记录旧 wheel/依赖版本后精确升级；不要顺带升级其他服务、执行器或模型环境。
4. 通过现有监督器重启原服务，保持全部配置和数据根不变。检查版本、健康、真实登录/退出、CSRF 和独立 executor 门禁。
5. 失败时优先恢复旧代码/依赖并复用当前业务数据。不要将上线前数据库覆盖到上线后的新写入；数据恢复必须单独确认。

## Cookie 客户端协议

1. `POST /api/login` 发送 JSON：`{"password":"<password>"}`；配置了账号时加 `username`，原 `account` 别名仍支持。跨站 Origin 被拒绝；非浏览器首次 JSON 登录可不发 Origin。
2. 用收到的 `chatboard_session` cookie 读取 `GET /api/session`。响应带 `Cache-Control: no-store`，返回 `authenticated` 与 `csrf_token`（无会话时为 null）。
3. 同一 cookie 的 POST/PATCH/PUT/DELETE 等写请求必须同时带同源 `Origin` 和 `X-CSRF-Token: <csrf_token>`。缺少或不匹配返回 403；读取无需 CSRF。已有会话再次登录也遵守该规则。
4. `POST /api/logout` 按同样规则提交，撤销服务器会话并清除 cookie。重放已退出或轮换前的 cookie 会返回未认证。

内置看板与登录页自动获取 CSRF。`frontendFetch` 只允许当前站点 origin，远程 backend 请求经同源 `/api/backends/{profile}/api/...` 代理，浏览器不向远程 backend 发送当前站点的 cookie 或 CSRF。

`/api/auth` 继续只返回原有四个布尔字段：`enabled`、`authenticated`、`username_required`、`api_token_enabled`。API key 请求不需要 Origin/CSRF；错误的 API key 不能绕过有效 cookie 的写保护。Cookie 使用 HttpOnly、SameSite=Lax 和 Path=/。

## 配置与界面

| 配置项 | 默认值 / 取值 |
| --- | --- |
| `CHATBOARD_USERNAME` | 可选；未配置时登录页隐藏账号字段 |
| `CHATBOARD_PASSWORD` | 未配置时不启用密码登录 |
| `CHATBOARD_AUTH_SECRET` | 可选；默认复用密码，用于 cookie 外层签名 |
| `CHATBOARD_SESSION_TTL_SECONDS` | 43200，最小 60 |
| `CHATBOARD_COOKIE_SECURE` | `1/true/yes/on` 启用 HTTPS cookie |
| `CHATBOARD_LOGIN_PALETTE` | `indigo`、`forest`、`amber`；默认 indigo |
| `CHATBOARD_LOGIN_LAYOUT` | `card` 或 `split`；默认 card |
| `CHATBOARD_LOGIN_APPEARANCE` | `system`、`light`、`dark`；默认 system |

共享 LoginUI 负责布局、主题和登录交互。ChatBoard 只通过 Jinja 继承定制表单与资源链接；应用集成可设置 `app.state.login_ui = LoginUI(...)` 覆盖渲染配置。`/auth-assets/` 仅允许包内 `login.css` 和 `login.js`，不公开模板或任意文件。

HTTPS 反向代理应启用 Secure cookie、校验入口 Host，并限制登录请求速率。`CHATBOARD_SERVICE_URL` 是受信任的规范服务地址，其 origin 与直接请求 origin 都可用于同源检查，因此支持 public/local 代理重写 Host。该地址只能来自服务器配置，客户端 Forwarded/X-Forwarded-* 不会增加允许的 origin。此门禁面向小型共享工作区，不替代 SSO/MFA。

## 验证

`python -m pytest -q` 包括账号/密码模式、密钥轮换、会话过期与重放、CSRF、API/executor 边界、共享模板/资源、前端 fetch 和真实 TCP 登录 smoke。TCP 用随机 loopback 端口和合成数据，结束时停止 uvicorn，不启动模型或真实 executor。Node.js 22+（或 `NODE_BINARY`）执行前端运行时测试；CI 安装 Node.js 并要求此项通过。
