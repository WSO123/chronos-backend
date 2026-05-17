# Chronos Auth MVP Frontend Handling

> 版本：v1  
> 日期：2026-05-17  
> 适用范围：P1 前端登录 / 会话恢复 / 请求拦截

---

## 1. 设计边界

P1 Auth 只服务一件事：让用户进入自己的 Chronos 执行闭环。

```text
email + password -> access token + refresh token -> Bearer API
```

P1 不做：

- 短信验证码
- 邮件验证码
- OTP / MFA
- OAuth / Apple / Google
- 密码重置
- 设备管理页

这些能力后续可以加，但不能在 P1 阻塞主线。前端也不要先做“发送验证码”“绑定手机号”“验证邮箱后才能继续”这类流程。

---

## 2. 页面状态

### Register

字段：

- `email`
- `password`
- `name`
- `timezone`，默认 `Asia/Shanghai` 或客户端当前时区

成功后：

- 保存 `access_token`
- 保存 `refresh_token`
- 进入 Today

重复邮箱：

- HTTP `409`
- code `CONFLICT`
- 建议文案：`这个邮箱已经注册，可以直接登录。`

### Login

字段：

- `email`
- `password`

成功后：

- 保存新的 `access_token`
- 保存新的 `refresh_token`
- 进入 Today

邮箱或密码错误：

- HTTP `401`
- code `AUTHENTICATION_FAILED`
- 建议文案：`邮箱或密码不正确。`
- 不区分邮箱不存在和密码错误，避免泄露账号存在性。

### Logout

前端行为：

1. 如果有 `refresh_token`，调用 `POST /auth/logout`。
2. 不管接口返回 `revoked=true` 还是 `revoked=false`，都清理本地 token。
3. 回到 Login。

`revoked=false` 表示后端没有找到这个 refresh token，前端仍应当视为退出成功。

---

## 3. Token 策略

### Access Token

- 放在 `Authorization: Bearer <access_token>`。
- 用于所有业务 API。
- 过期时会返回 `ACCESS_TOKEN_EXPIRED`。

### Refresh Token

- 只用于 `POST /auth/refresh` 和 `POST /auth/logout`。
- refresh 成功后，后端会返回新的 access / refresh token pair。
- 旧 refresh token 会立即失效，不能复用。

### Refresh Single Flight

前端请求拦截器应避免并发 refresh：

```text
API returns ACCESS_TOKEN_EXPIRED
-> if no refresh in progress, start refresh
-> other requests wait for same refresh promise
-> refresh ok: replace both tokens, retry original requests once
-> refresh failed: clear tokens, go to Login
```

不要让多个请求同时拿同一个 refresh token 去刷新，否则只有第一个会成功，后续会因为 token rotation 被拒绝。

---

## 4. 错误码处理表

| code | HTTP | 场景 | 前端处理 |
| --- | --- | --- | --- |
| `CONFLICT` | 409 | 注册邮箱已存在 | 提示直接登录 |
| `REQUEST_VALIDATION_ERROR` | 422 | email / password / name 格式不合法 | 表单内联提示 |
| `AUTHENTICATION_FAILED` | 401 | 登录失败、refresh 无效、refresh 已轮换、refresh 已撤销 | 登录页提示或清理会话 |
| `AUTH_REQUIRED` | 401 | 缺少 Bearer token | 清理会话并进入 Login |
| `INVALID_AUTH_HEADER` | 401 | Authorization 格式错误 | 清理会话并进入 Login |
| `INVALID_ACCESS_TOKEN` | 401 | access token 无效 | 清理会话并进入 Login |
| `ACCESS_TOKEN_EXPIRED` | 401 | access token 过期 | 尝试 refresh，一次失败后进入 Login |
| `USER_NOT_FOUND` | 404 | token 对应用户不存在 | 清理会话并进入 Login |
| `USER_INACTIVE` | 403 | 用户被停用 | 清理会话，提示账号不可用 |
| `INSECURE_AUTH_CONFIGURATION` | 500 | 后端 auth 配置不安全 | 本地提示环境配置问题，不展示给普通用户 |

---

## 5. 推荐请求拦截逻辑

```text
request:
  if access_token exists:
    add Authorization Bearer

response:
  if status != 401:
    return response

  if code == ACCESS_TOKEN_EXPIRED and refresh_token exists:
    run refresh single flight
    if refresh ok:
      retry original request once
    else:
      clear session and go Login

  if code in AUTH_REQUIRED / INVALID_AUTH_HEADER / INVALID_ACCESS_TOKEN / AUTHENTICATION_FAILED:
    clear session and go Login

  if code == USER_INACTIVE:
    clear session and show disabled account message
```

重试只能做一次，避免接口错误时进入循环。

---

## 6. 存储建议

P1 可以先用前端本地安全存储或平台推荐存储方案。后续如果做 Web 生产化，可以再评估 HttpOnly cookie / CSRF 策略。

当前后端返回 token JSON，是为了让移动端、桌面端和本地前端联调都能直接使用。

---

## 7. 验证入口

Auth token 生命周期：

```bash
uv run python scripts/smoke_auth_token_loop.py
uv run python scripts/verify_local.py --smoke auth
```

前端错误契约：

```bash
uv run python scripts/smoke_auth_frontend_error_contract.py
uv run python scripts/verify_local.py --smoke auth-errors
```

真实 Capture 主路径：

```bash
uv run python scripts/smoke_p1_bearer_capture_loop.py
uv run python scripts/verify_local.py --smoke p1-bearer-capture
```
