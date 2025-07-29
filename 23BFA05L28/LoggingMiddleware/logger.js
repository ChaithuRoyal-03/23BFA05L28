// logger.js

async function Log(stack, level, packageName, message) {
  const logData = {
    stack: stack,
    level: level,
    package: packageName,
    message: message
  };

  try {
    const response = await fetch("http://20.244.56.144/evaluation-service/logs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(logData)
    });

    if (response.ok) {
      const result = await response.json();
      console.log("✅ Log created successfully:", result);
    } else {
      console.error("❌ Failed to log:", response.status);
    }
  } catch (err) {
    console.error("❌ Error in logging:", err.message);
  }
}

// Example usage
Log("backend", "error", "handler", "received string, expected bool");
Log("backend", "fatal", "db", "Critical database connection failure."); 