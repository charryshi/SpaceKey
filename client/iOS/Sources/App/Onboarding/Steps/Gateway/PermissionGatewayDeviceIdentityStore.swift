import Foundation
import KeychainAccess
import Security
import Shared

struct PermissionGatewayDeviceIdentity {
    let appInstanceID: String
    let devicePublicKey: String
}

final class PermissionGatewayDeviceIdentityStore {
    enum IdentityError: LocalizedError {
        case keyGenerationFailed
        case publicKeyExportFailed
        case appInstanceIDUnavailable

        var errorDescription: String? {
            switch self {
            case .keyGenerationFailed:
                return "Unable to create a local device key."
            case .publicKeyExportFailed:
                return "Unable to export the local device public key."
            case .appInstanceIDUnavailable:
                return "Unable to create an app instance id."
            }
        }
    }

    private enum Constants {
        static let service = "io.home-assistant.permission-gateway"
        static let appInstanceIDKey = "app_instance_id"
        static let privateKeyTag = ".permission-gateway.private-key"
    }

    private let keychain = Keychain(service: Constants.service)

    func identity() throws -> PermissionGatewayDeviceIdentity {
        .init(
            appInstanceID: try appInstanceID(),
            devicePublicKey: try publicKey()
        )
    }

    private func appInstanceID() throws -> String {
        if let existing = try keychain.get(Constants.appInstanceIDKey), !existing.isEmpty {
            return existing
        }

        let appInstanceID = UUID().uuidString
        try keychain.set(appInstanceID, key: Constants.appInstanceIDKey)
        return appInstanceID
    }

    private func publicKey() throws -> String {
        let privateKey = try loadOrCreatePrivateKey()
        guard let publicKey = SecKeyCopyPublicKey(privateKey) else {
            throw IdentityError.publicKeyExportFailed
        }

        var error: Unmanaged<CFError>?
        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, &error) as Data? else {
            if let error {
                throw error.takeRetainedValue() as Error
            }
            throw IdentityError.publicKeyExportFailed
        }
        return publicKeyData.base64EncodedString()
    }

    private func loadOrCreatePrivateKey() throws -> SecKey {
        if let existing = loadPrivateKey() {
            return existing
        }

        var error: Unmanaged<CFError>?
        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String: true,
                kSecAttrApplicationTag as String: privateKeyTagData,
            ],
        ]

        if let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &error) {
            return privateKey
        }

        if let existing = loadPrivateKey() {
            return existing
        }

        if let error {
            throw error.takeRetainedValue() as Error
        }
        throw IdentityError.keyGenerationFailed
    }

    private func loadPrivateKey() -> SecKey? {
        var item: CFTypeRef?
        let status = SecItemCopyMatching(privateKeyQuery as CFDictionary, &item)
        guard status == errSecSuccess, let item, CFGetTypeID(item) == SecKeyGetTypeID() else { return nil }
        return unsafeBitCast(item, to: SecKey.self)
    }

    private var privateKeyQuery: [String: Any] {
        [
            kSecClass as String: kSecClassKey,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrApplicationTag as String: privateKeyTagData,
            kSecReturnRef as String: true,
        ]
    }

    private var privateKeyTagData: Data {
        (AppConstants.BundleID + Constants.privateKeyTag).data(using: .utf8)!
    }
}
