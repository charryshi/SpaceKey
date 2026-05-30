import type { Auth } from "home-assistant-js-websocket";

const PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY =
  "permission_gateway_device_public_key";

const getPermissionGatewayDevicePublicKey = () => {
  try {
    return localStorage.getItem(
      PERMISSION_GATEWAY_DEVICE_PUBLIC_KEY_STORAGE_KEY
    );
  } catch (_err: any) {
    return undefined;
  }
};

export const fetchWithAuth = async (
  auth: Auth,
  input: RequestInfo,
  init: RequestInit = {}
) => {
  if (auth.expired) {
    await auth.refreshAccessToken();
  }
  init.credentials = "same-origin";
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${auth.accessToken}`);
  const devicePublicKey = getPermissionGatewayDevicePublicKey();
  if (devicePublicKey) {
    headers.set("X-Device-Public-Key", devicePublicKey);
  }
  init.headers = headers;
  return fetch(input, init);
};
