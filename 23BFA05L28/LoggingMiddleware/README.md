# Logging Middleware

This project implements a reusable logging middleware to send logs to the AffordMed test server via an HTTP POST request.

## 🔧 How to Use

The function `Log(stack, level, package, message)` should be used like this:

```js
Log("backend", "error", "handler", "received string, expected bool");
```

## 🌐 API Details

**POST URL:**
```
http://20.244.56.144/evaluation-service/logs
```

**Request Format:**
```json
{
  "stack": "backend",
  "level": "error",
  "package": "handler",
  "message": "received string, expected bool"
}
```

**Response:**
```json
{
  "logID": "some-uuid",
  "message": "log created successfully"
}
```

## ⚠️ Constraints

- **stack**: "backend" or "frontend"
- **level**: "debug", "info", "warn", "error", "fatal"
- **package**: allowed values like "handler", "controller", "api", "db" depending on backend/frontend use. 