import Foundation
import PromiseKit
import Shared
import Version

final class PermissionGatewayOnboardingService {
    private let identityStore: PermissionGatewayDeviceIdentityStore

    init(identityStore: PermissionGatewayDeviceIdentityStore = .init()) {
        self.identityStore = identityStore
    }

    func activate(gatewayURL: URL, qrID: String, verificationCode: String) -> Promise<Server> {
        firstly {
            identity()
        }.then { identity in
            PermissionGatewayClient(gatewayURL: gatewayURL)
                .activate(qrID: qrID, verificationCode: verificationCode, identity: identity)
                .map(on: .main) { response in
                    self.persistServer(gatewayURL: gatewayURL, identity: identity, response: response)
                }
        }
    }

    private func identity() -> Promise<PermissionGatewayDeviceIdentity> {
        Promise { seal in
            do {
                seal.fulfill(try identityStore.identity())
            } catch {
                seal.reject(error)
            }
        }
    }

    private func persistServer(
        gatewayURL: URL,
        identity: PermissionGatewayDeviceIdentity,
        response: PermissionGatewayAuthResponse
    ) -> Server {
        var connectionInfo = ConnectionInfo(
            externalURL: gatewayURL,
            internalURL: nil,
            cloudhookURL: nil,
            remoteUIURL: nil,
            webhookID: "",
            webhookSecret: nil,
            internalSSIDs: nil,
            internalHardwareAddresses: nil,
            isLocalPushEnabled: false,
            securityExceptions: .init(),
            connectionAccessSecurityLevel: gatewayURL.scheme?.lowercased() == "https" ? .mostSecure : .lessSecure,
            clientCertificate: nil
        )
        connectionInfo.useCloud = false

        let tokenInfo = TokenInfo(
            accessToken: response.accessToken,
            refreshToken: response.refreshToken,
            expiration: response.accessTokenExpirationDate(),
            gatewayDevicePublicKey: identity.devicePublicKey
        )

        var serverInfo = ServerInfo(
            name: "Permission Gateway",
            connection: connectionInfo,
            token: tokenInfo,
            version: Version()
        )
        serverInfo.setSetting(value: ServerLocationPrivacy.never, for: .locationPrivacy)
        serverInfo.setSetting(value: ServerSensorPrivacy.none, for: .sensorPrivacy)
        serverInfo.setSetting(value: response.grantID, for: .permissionGatewayGrantID)
        serverInfo.setSetting(value: gatewayURL.absoluteString, for: .permissionGatewayURL)

        let identifier = Identifier<Server>(rawValue: "permission-gateway-\(response.grantID)")
        let server = Current.servers.add(identifier: identifier, serverInfo: serverInfo)
        Current.setCachedApi(HomeAssistantAPI(server: server), for: identifier)
        return server
    }
}
