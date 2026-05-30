import type { AuthData } from "home-assistant-js-websocket";
import { Auth, ERR_INVALID_AUTH } from "home-assistant-js-websocket";
import { prepareZXingModule } from "barcode-detector";
import type QrScanner from "qr-scanner";
import {
  getPermissionGatewayDevicePublicKey,
  PERMISSION_GATEWAY_CLIENT_ID,
  PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY,
  PERMISSION_GATEWAY_TOKENS_STORAGE_KEY,
  savePermissionGatewaySummary,
  type PermissionGatewaySummary,
} from "./permission_gateway";
import { parsePermissionGatewayQrId } from "./permission_gateway_qr";

prepareZXingModule({
  overrides: {
    locateFile: (path: string, prefix: string) => {
      if (path.endsWith(".wasm")) {
        return "/static/js/zxing_reader.wasm";
      }
      return prefix + path;
    },
  },
});

const PERMISSION_GATEWAY_APP_INSTANCE_ID_STORAGE_KEY =
  "permission_gateway_app_instance_id";

interface PermissionGatewayAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  grant_id: string;
  expires_at: string | null;
  permission_summary?: PermissionGatewaySummary | null;
}

const normalizeGatewayTokens = (
  tokens: AuthData,
  hassUrl?: string
): AuthData => ({
  ...tokens,
  hassUrl: tokens.hassUrl || hassUrl || "",
  clientId: PERMISSION_GATEWAY_CLIENT_ID,
});

const saveGatewayTokens = (tokens: AuthData | null) => {
  if (tokens) {
    localStorage.setItem(
      PERMISSION_GATEWAY_TOKENS_STORAGE_KEY,
      JSON.stringify(normalizeGatewayTokens(tokens))
    );
  } else {
    localStorage.removeItem(PERMISSION_GATEWAY_TOKENS_STORAGE_KEY);
  }
};

const loadGatewayTokens = (hassUrl: string): AuthData | undefined => {
  const raw = localStorage.getItem(PERMISSION_GATEWAY_TOKENS_STORAGE_KEY);
  if (!raw) {
    return undefined;
  }
  try {
    const tokens = normalizeGatewayTokens(JSON.parse(raw) as AuthData, hassUrl);
    saveGatewayTokens(tokens);
    return tokens;
  } catch (_err: any) {
    saveGatewayTokens(null);
    return undefined;
  }
};

const getOrCreateStoredValue = (key: string, prefix: string) => {
  const existing = localStorage.getItem(key);
  if (existing) {
    return existing;
  }
  const random = new Uint8Array(24);
  crypto.getRandomValues(random);
  const value = `${prefix}_${Array.from(random, (byte) =>
    byte.toString(16).padStart(2, "0")
  ).join("")}`;
  localStorage.setItem(key, value);
  return value;
};

const getOrCreateAppInstanceId = () =>
  getOrCreateStoredValue(PERMISSION_GATEWAY_APP_INSTANCE_ID_STORAGE_KEY, "web");

const getOrCreateDevicePublicKey = () =>
  getOrCreateStoredValue(
    PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY,
    "web_device"
  );

const authDataFromGatewayResponse = (
  hassUrl: string,
  response: PermissionGatewayAuthResponse,
  clearMissingPermissionSummary = false
): AuthData => {
  if ("permission_summary" in response) {
    savePermissionGatewaySummary(response.permission_summary);
  } else if (clearMissingPermissionSummary) {
    savePermissionGatewaySummary(null);
  }
  return {
    hassUrl,
    clientId: PERMISSION_GATEWAY_CLIENT_ID,
    expires: response.expires_in * 1000 + Date.now(),
    refresh_token: response.refresh_token,
    access_token: response.access_token,
    expires_in: response.expires_in,
  };
};

class PermissionGatewayAuth extends Auth {
  public async refreshAccessToken() {
    const response = await fetch(`${this.data.hassUrl}/v1/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: this.data.refresh_token,
        device_public_key: getOrCreateDevicePublicKey(),
      }),
    });

    if (!response.ok) {
      saveGatewayTokens(null);
      savePermissionGatewaySummary(null);
      throw ERR_INVALID_AUTH;
    }

    this.data = authDataFromGatewayResponse(
      this.data.hassUrl,
      await response.json()
    );
    saveGatewayTokens(this.data);
  }

  public async revoke() {
    await fetch(`${this.data.hassUrl}/v1/auth/revoke`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Authorization: `Bearer ${this.data.access_token}`,
        "Content-Type": "application/json",
        "X-Device-Public-Key": getOrCreateDevicePublicKey(),
      },
      body: JSON.stringify({}),
    }).catch(() => undefined);
    saveGatewayTokens(null);
    savePermissionGatewaySummary(null);
  }
}

export const createPermissionGatewayAuth = async (hassUrl: string) => {
  let tokens = loadGatewayTokens(hassUrl);
  if (!tokens || tokens.hassUrl !== hassUrl) {
    savePermissionGatewaySummary(null);
    tokens = await showActivationForm(hassUrl);
  } else {
    tokens = normalizeGatewayTokens(tokens, hassUrl);
    saveGatewayTokens(tokens);
  }
  const auth = new PermissionGatewayAuth(tokens, saveGatewayTokens);
  if (auth.expired) {
    await auth.refreshAccessToken();
  }
  return auth;
};

const showActivationForm = (hassUrl: string): Promise<AuthData> =>
  new Promise((resolve) => {
    let qrScanner: QrScanner | undefined;

    const root = document.createElement("div");
    root.innerHTML = `
      <style>
        :root {
          color-scheme: light;
        }
        body {
          margin: 0;
          font-family: Roboto, Noto, sans-serif;
          background: #eef3f8;
          color: #17212b;
        }
        .pg-auth {
          min-height: 100vh;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          padding: max(18px, env(safe-area-inset-top)) 16px max(18px, env(safe-area-inset-bottom));
        }
        .pg-auth form {
          width: min(440px, 100%);
          margin: auto;
          background: #fff;
          border: 1px solid #d6dee8;
          border-radius: 8px;
          padding: 18px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, 0.10);
          box-sizing: border-box;
        }
        .pg-auth h1 {
          font-size: 24px;
          margin: 0 0 6px;
          letter-spacing: 0;
        }
        .pg-auth p {
          margin: 0;
          color: #52616f;
          line-height: 1.45;
        }
        .scanner {
          position: relative;
          overflow: hidden;
          margin: 18px 0;
          border-radius: 8px;
          background: #111827;
          aspect-ratio: 1;
        }
        .scanner video,
        .scanner canvas {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .scanner-frame {
          position: absolute;
          inset: 13%;
          border: 2px solid rgba(255, 255, 255, 0.92);
          border-radius: 8px;
          box-shadow: 0 0 0 999px rgba(0, 0, 0, 0.38);
          pointer-events: none;
        }
        .scanner-status {
          position: absolute;
          left: 12px;
          right: 12px;
          bottom: 12px;
          color: #fff;
          font-size: 13px;
          text-align: center;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
        }
        .scanned {
          display: none;
          margin: 0 0 12px;
          padding: 10px 12px;
          border-radius: 6px;
          background: #ecfdf3;
          color: #067647;
          font-size: 14px;
        }
        .actions {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          margin-bottom: 14px;
        }
        .secondary-button,
        .primary-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 6px;
          padding: 10px 12px;
          font: inherit;
          font-weight: 700;
          cursor: pointer;
          text-align: center;
        }
        .secondary-button {
          border: 1px solid #c6d0dc;
          color: #202a35;
          background: #fff;
          margin: 0;
        }
        .manual {
          display: none;
        }
        .manual.visible {
          display: block;
        }
        .pg-auth label {
          display: grid;
          gap: 6px;
          margin: 12px 0;
          font-size: 13px;
          color: #52616f;
        }
        .pg-auth input {
          font: inherit;
          color: #202a35;
          border: 1px solid #c6d0dc;
          border-radius: 6px;
          padding: 10px 12px;
          outline: none;
        }
        .pg-auth input:focus {
          border-color: #0b7fab;
          box-shadow: 0 0 0 3px rgba(3, 169, 244, 0.14);
        }
        .primary-button {
          width: 100%;
          margin-top: 16px;
          border: 0;
          padding: 11px 14px;
          background: #0b7fab;
          color: #fff;
        }
        .primary-button:disabled {
          opacity: 0.64;
          cursor: wait;
        }
        .pg-auth .error {
          min-height: 20px;
          color: #b42318;
          font-size: 13px;
          margin-top: 12px;
        }
        .hint {
          font-size: 12px;
          color: #667789;
          margin-top: 10px;
          line-height: 1.4;
        }
        @media (max-width: 480px) {
          .pg-auth {
            padding-left: 12px;
            padding-right: 12px;
          }
          .pg-auth form {
            padding: 16px;
          }
          .pg-auth h1 {
            font-size: 22px;
          }
        }
      </style>
      <div class="pg-auth">
        <form>
          <h1>扫码授权</h1>
          <p>扫描管理员提供的二维码，然后输入验证码。</p>
          <div class="scanner">
            <video playsinline muted></video>
            <div class="scanner-frame"></div>
            <div class="scanner-status">正在启动摄像头...</div>
          </div>
          <div class="scanned"></div>
          <div class="actions">
            <label class="secondary-button">
              拍照识别
              <input name="qr_image" type="file" accept="image/*" capture="environment" hidden>
            </label>
            <button class="secondary-button" name="manual_toggle" type="button">手动输入</button>
          </div>
          <div class="manual">
            <label>
              授权码
              <input name="qr_id" autocomplete="off">
            </label>
          </div>
          <label>
            验证码
            <input name="verification_code" autocomplete="one-time-code" required>
          </label>
          <button class="primary-button" type="submit">确认授权</button>
          <div class="error" role="alert"></div>
          <div class="hint">如果浏览器无法打开摄像头，请使用“拍照识别”或“手动输入”。</div>
        </form>
      </div>
    `;
    document.body.replaceChildren(root);

    const form = root.querySelector("form")!;
    const qrInput = form.elements.namedItem("qr_id") as HTMLInputElement;
    const imageInput = form.elements.namedItem("qr_image") as HTMLInputElement;
    const codeInput = form.elements.namedItem(
      "verification_code"
    ) as HTMLInputElement;
    const manual = root.querySelector(".manual") as HTMLElement;
    const manualToggle = form.elements.namedItem(
      "manual_toggle"
    ) as HTMLButtonElement;
    const error = root.querySelector(".error") as HTMLElement;
    const scannerStatus = root.querySelector(".scanner-status") as HTMLElement;
    const scanned = root.querySelector(".scanned") as HTMLElement;
    const video = root.querySelector("video") as HTMLVideoElement;
    const qrId =
      new URLSearchParams(location.search).get("qr_id") ||
      new URLSearchParams(location.search).get("template_id");

    const setQrId = (value: string) => {
      const parsedQrId = parsePermissionGatewayQrId(value);
      if (!parsedQrId) {
        error.textContent = "无法识别二维码内容。";
        return;
      }
      qrInput.value = parsedQrId;
      scanned.style.display = "block";
      scanned.textContent = `已识别授权码：${parsedQrId}`;
      scannerStatus.textContent = "二维码已识别，请输入验证码。";
      manual.classList.remove("visible");
      codeInput.focus();
      qrScanner?.stop();
    };

    if (qrId) {
      setQrId(qrId);
      codeInput.focus();
    } else if (!navigator.mediaDevices) {
      manual.classList.add("visible");
      qrInput.focus();
    }

    const startScanner = async () => {
      if (!navigator.mediaDevices) {
        scannerStatus.textContent = "当前浏览器不支持直接扫码。";
        return;
      }
      try {
        const qrScannerClass = (await import("qr-scanner")).default;
        qrScannerClass.WORKER_PATH = "/static/js/qr-scanner-worker.min.js";
        if (!(await qrScannerClass.hasCamera())) {
          scannerStatus.textContent = "未检测到摄像头。";
          manual.classList.add("visible");
          return;
        }
        qrScanner = new qrScannerClass(
          video,
          (result) => setQrId(result),
          (scanError) => {
            if (String(scanError).endsWith("No QR code found")) {
              return;
            }
            scannerStatus.textContent = "扫码失败，可尝试拍照识别。";
          }
        );
        await qrScanner.start();
        scannerStatus.textContent = "请将二维码放入框内。";
      } catch (_err: any) {
        scannerStatus.textContent = window.isSecureContext
          ? "无法打开摄像头。"
          : "浏览器需要 HTTPS 才能直接打开摄像头。";
        manual.classList.add("visible");
      }
    };

    startScanner();

    manualToggle.addEventListener("click", () => {
      manual.classList.toggle("visible");
      if (manual.classList.contains("visible")) {
        qrInput.focus();
      }
    });

    imageInput.addEventListener("change", async () => {
      const file = imageInput.files?.[0];
      if (!file) {
        return;
      }
      try {
        const qrScannerClass = (await import("qr-scanner")).default;
        const result = await qrScannerClass.scanImage(file);
        setQrId(result);
      } catch (_err: any) {
        error.textContent = "未能从图片中识别二维码。";
      } finally {
        imageInput.value = "";
      }
    });

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      error.textContent = "";
      if (!qrInput.value.trim()) {
        manual.classList.add("visible");
        qrInput.focus();
        error.textContent = "请先扫描二维码或输入授权码。";
        return;
      }
      const submitButton = form.querySelector(
        "button[type='submit']"
      ) as HTMLButtonElement;
      submitButton.setAttribute("disabled", "true");
      try {
        const response = await fetch(`${hassUrl}/v1/activation/verify`, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            qr_id: qrInput.value.trim(),
            verification_code: codeInput.value.trim(),
            device_public_key: getOrCreateDevicePublicKey(),
            app_instance_id: getOrCreateAppInstanceId(),
          }),
        });
        if (!response.ok) {
          throw new Error("activation failed");
        }
        const data = authDataFromGatewayResponse(
          hassUrl,
          await response.json(),
          true
        );
        saveGatewayTokens(data);
        document.body.replaceChildren(document.createElement("home-assistant"));
        resolve(data);
      } catch (_err: any) {
        error.textContent = "授权失败，请检查二维码和验证码。";
      } finally {
        submitButton.removeAttribute("disabled");
      }
    });
  });

export { getPermissionGatewayDevicePublicKey };
