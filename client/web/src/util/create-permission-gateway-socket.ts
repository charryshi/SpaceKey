import type {
  ConnectionOptions,
  HaWebSocket,
} from "home-assistant-js-websocket";
import {
  ERR_CANNOT_CONNECT,
  ERR_HASS_HOST_REQUIRED,
  ERR_INVALID_AUTH,
} from "home-assistant-js-websocket";
import { getPermissionGatewayDevicePublicKey } from "../data/permission_gateway";

const MSG_TYPE_AUTH_INVALID = "auth_invalid";
const MSG_TYPE_AUTH_OK = "auth_ok";

const supportsCoalescedMessages = (haVersion: string | undefined) => {
  if (!haVersion) {
    return false;
  }
  const [year, month] = haVersion.split(".").map((part) => Number(part));
  return year > 2022 || (year === 2022 && month >= 9);
};

const buildAuthMessage = (accessToken: string) => {
  const message: {
    type: "auth";
    access_token: string;
    device_public_key?: string;
  } = {
    type: "auth",
    access_token: accessToken,
  };
  const devicePublicKey = getPermissionGatewayDevicePublicKey();
  if (devicePublicKey) {
    message.device_public_key = devicePublicKey;
  }
  return message;
};

export const createPermissionGatewaySocket = (
  options: ConnectionOptions
): Promise<HaWebSocket> => {
  if (!options.auth) {
    throw ERR_HASS_HOST_REQUIRED;
  }
  const auth = options.auth;
  let authRefreshTask = auth.expired
    ? auth.refreshAccessToken().then(
        () => {
          authRefreshTask = undefined;
        },
        () => {
          authRefreshTask = undefined;
        }
      )
    : undefined;
  const url = auth.wsUrl;

  const connect = (
    triesLeft: number,
    resolve: (socket: HaWebSocket) => void,
    reject: (err: any) => void
  ) => {
    const socket = new WebSocket(url) as HaWebSocket;
    let invalidAuth = false;

    const closeMessage = () => {
      socket.removeEventListener("close", closeMessage);
      if (invalidAuth) {
        reject(ERR_INVALID_AUTH);
        return;
      }
      if (triesLeft === 0) {
        reject(ERR_CANNOT_CONNECT);
        return;
      }
      const newTries = triesLeft === -1 ? -1 : triesLeft - 1;
      setTimeout(() => connect(newTries, resolve, reject), 1000);
    };

    const handleOpen = async () => {
      try {
        if (auth.expired) {
          await (authRefreshTask || auth.refreshAccessToken());
        }
        socket.send(JSON.stringify(buildAuthMessage(auth.accessToken)));
      } catch (err) {
        invalidAuth = err === ERR_INVALID_AUTH;
        socket.close();
      }
    };

    const handleMessage = (event: MessageEvent) => {
      const message = JSON.parse(event.data);
      switch (message.type) {
        case MSG_TYPE_AUTH_INVALID:
          invalidAuth = true;
          socket.close();
          break;
        case MSG_TYPE_AUTH_OK:
          socket.removeEventListener("open", handleOpen);
          socket.removeEventListener("message", handleMessage);
          socket.removeEventListener("close", closeMessage);
          socket.removeEventListener("error", closeMessage);
          socket.haVersion = message.ha_version;
          if (supportsCoalescedMessages(socket.haVersion)) {
            socket.send(
              JSON.stringify({
                type: "supported_features",
                id: 1,
                features: { coalesce_messages: 1 },
              })
            );
          }
          resolve(socket);
          break;
      }
    };

    socket.addEventListener("open", handleOpen);
    socket.addEventListener("message", handleMessage);
    socket.addEventListener("close", closeMessage);
    socket.addEventListener("error", closeMessage);
  };

  return new Promise((resolve, reject) => {
    connect(options.setupRetry, resolve, reject);
  });
};
