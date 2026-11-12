/* Local API explorer remains usable when the Swagger CDN is unavailable. */
(() => {
  "use strict";
  const config = document.body.dataset;

  async function prepareRequest(request) {
    const target = new URL(request.url, window.location.origin);
    if (target.origin !== window.location.origin) throw new Error("Разрешены только запросы к этому серверу");
    request.headers = request.headers || {};
    if (config.sessionBackend === "true" &&
        !["GET", "HEAD", "OPTIONS"].includes((request.method || "GET").toUpperCase())) {
      const response = await fetch(config.csrfUrl, {credentials: "same-origin"});
      if (!response.ok) throw new Error(`CSRF: HTTP ${response.status}`);
      const data = await response.json();
      if (!data.csrfToken) throw new Error("Сервер не вернул CSRF token");
      request.headers["X-CSRFToken"] = data.csrfToken;
    }
    return request;
  }

  async function execute(url, method, body, token) {
    const request = {url, method, headers: {}};
    if (body !== undefined) {
      JSON.parse(body);
      request.headers["Content-Type"] = "application/json";
      request.body = body;
    }
    if (config.sessionBackend !== "true" && token) request.headers.Authorization = `Bearer ${token}`;
    await prepareRequest(request);
    return fetch(request.url, {...request, credentials: "same-origin"});
  }

  function node(tag, text) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function sample(schema) {
    if (schema.type === "object") return Object.fromEntries(
      Object.entries(schema.properties || {}).map(([key, value]) => [key, sample(value)]));
    if (schema.type === "integer" || schema.type === "number") return schema.minimum || 1;
    if (schema.type === "boolean") return false;
    return schema.example || "";
  }

  function addOperation(path, method, operation, pathParameters) {
    const details = node("details");
    const summary = node("summary");
    summary.append(node("strong", method.toUpperCase()), node("span", `${path} — ${operation.summary}`));
    details.append(summary);
    const parameters = [...pathParameters, ...(operation.parameters || [])].map(parameter => {
      const label = node("label", `${parameter.name} (${parameter.in})`);
      const input = node("input");
      input.value = parameter.schema.type === "integer" ? "1" : "";
      label.append(input);
      details.append(label);
      return {...parameter, input};
    });
    let bodyInput;
    if (operation.requestBody) {
      bodyInput = node("textarea");
      bodyInput.value = JSON.stringify(sample(operation.requestBody.content["application/json"].schema), null, 2);
      const label = node("label", "Тело запроса (JSON)");
      label.append(bodyInput);
      details.append(label);
    }
    const button = node("button", "Выполнить");
    button.type = "button";
    const output = node("pre", "Ответ появится здесь.");
    output.setAttribute("aria-live", "polite");
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        let url = path;
        const query = new URLSearchParams();
        for (const parameter of parameters) {
          if (parameter.in === "path") {
            if (!parameter.input.value) throw new Error(`Заполните ${parameter.name}`);
            url = url.replace(`{${parameter.name}}`, encodeURIComponent(parameter.input.value));
          } else if (parameter.input.value) query.set(parameter.name, parameter.input.value);
        }
        if (query.size) url += `?${query}`;
        const response = await execute(url, method.toUpperCase(), bodyInput?.value,
                                       document.getElementById("jwt-token").value.trim());
        const text = await response.text();
        let content = text;
        try { content = JSON.stringify(JSON.parse(text), null, 2); } catch (_) { /* Non-JSON/204 response. */ }
        output.textContent = `HTTP ${response.status}\n${content}`;
      } catch (error) {
        output.textContent = `Ошибка: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
    details.append(button, output);
    document.getElementById("operations").append(details);
  }

  function loadSwagger() {
    const status = document.getElementById("docs-status");
    const script = node("script");
    script.src = config.swaggerJsUrl;
    if (config.swaggerJsIntegrity) {
      script.integrity = config.swaggerJsIntegrity;
      script.crossOrigin = "anonymous";
    }
    script.async = true;
    script.onerror = () => { status.textContent = "Swagger CDN недоступен. Локальный интерфейс API ниже работает без интернета."; };
    script.onload = () => {
      if (typeof window.SwaggerUIBundle !== "function") return script.onerror();
      const css = node("link");
      css.rel = "stylesheet";
      css.href = config.swaggerCssUrl;
      if (config.swaggerCssIntegrity) {
        css.integrity = config.swaggerCssIntegrity;
        css.crossOrigin = "anonymous";
      }
      // Keep the working local interface if the Swagger stylesheet fails to load.
      css.onerror = script.onerror;
      css.onload = () => {
        try {
          window.SwaggerUIBundle({url: config.schemaUrl, dom_id: "#swagger-ui", deepLinking: true,
            validatorUrl: null, withCredentials: true, requestInterceptor: prepareRequest,
            onComplete: () => {
              document.getElementById("swagger-ui").hidden = false;
              document.getElementById("local-docs").hidden = true;
              status.textContent = "Swagger UI загружен.";
            }});
        } catch (_) { script.onerror(); }
      };
      document.head.append(css);
    };
    document.head.append(script);
  }

  async function init() {
    const status = document.getElementById("docs-status");
    try {
      const response = await fetch(config.schemaUrl, {credentials: "same-origin"});
      if (!response.ok) throw new Error(`Схема API: HTTP ${response.status}`);
      const schema = await response.json();
      document.getElementById("auth-help").textContent = schema.info.description;
      document.getElementById("jwt-control").hidden = config.sessionBackend === "true";
      for (const [path, item] of Object.entries(schema.paths)) {
        for (const method of ["get", "post", "patch", "delete"]) {
          if (item[method]) addOperation(path, method, item[method], item.parameters || []);
        }
      }
      status.textContent = "Локальный интерфейс API готов. Запросы можно выполнять ниже; Swagger UI загружается дополнительно.";
      loadSwagger();
    } catch (error) { status.textContent = `Ошибка загрузки документации: ${error.message}`; }
  }
  window.LastLightDocs = {prepareRequest, execute};
  document.addEventListener("DOMContentLoaded", init);
})();
