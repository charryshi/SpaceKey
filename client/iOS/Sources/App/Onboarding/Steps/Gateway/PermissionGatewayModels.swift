import Foundation
import Shared

struct PermissionGatewayActivationRequest: Encodable {
    let qrID: String
    let verificationCode: String
    let devicePublicKey: String
    let appInstanceID: String

    enum CodingKeys: String, CodingKey {
        case qrID = "qr_id"
        case verificationCode = "verification_code"
        case devicePublicKey = "device_public_key"
        case appInstanceID = "app_instance_id"
    }
}

struct PermissionGatewayAuthResponse: Decodable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int
    let grantID: String
    let expiresAt: String?
    let permissionSummary: PermissionGatewayPermissionSummary

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
        case grantID = "grant_id"
        case expiresAt = "expires_at"
        case permissionSummary = "permission_summary"
    }

    func accessTokenExpirationDate(now: Date = Current.date()) -> Date {
        now.addingTimeInterval(TimeInterval(expiresIn))
    }
}

struct PermissionGatewayPermissionSummary: Decodable {
    let role: String
    let canRead: Bool
    let canControl: Bool
    let haAreaIDs: [String]
    let deviceIDs: [String]
    let entityIDs: [String]

    enum CodingKeys: String, CodingKey {
        case role
        case canRead = "can_read"
        case canControl = "can_control"
        case haAreaIDs = "ha_area_ids"
        case deviceIDs = "device_ids"
        case entityIDs = "entity_ids"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.role = try container.decodeIfPresent(String.self, forKey: .role) ?? "guest"
        self.canRead = try container.decodeIfPresent(Bool.self, forKey: .canRead) ?? false
        self.canControl = try container.decodeIfPresent(Bool.self, forKey: .canControl) ?? false
        self.haAreaIDs = try container.decodeIfPresent([String].self, forKey: .haAreaIDs) ?? []
        self.deviceIDs = try container.decodeIfPresent([String].self, forKey: .deviceIDs) ?? []
        self.entityIDs = try container.decodeIfPresent([String].self, forKey: .entityIDs) ?? []
    }
}

struct PermissionGatewayQRPayload {
    let gatewayURL: URL?
    let qrID: String

    enum ParseError: LocalizedError {
        case missingQRID
        case invalidGatewayURL(String)

        var errorDescription: String? {
            switch self {
            case .missingQRID:
                return "The QR code does not contain a gateway QR id."
            case let .invalidGatewayURL(value):
                return "The QR code contains an invalid gateway URL: \(value)"
            }
        }
    }

    static func parse(_ rawValue: String) throws -> PermissionGatewayQRPayload {
        let trimmed = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            throw ParseError.missingQRID
        }

        if let data = trimmed.data(using: .utf8),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            return try parse(object)
        }

        if let components = URLComponents(string: trimmed),
           components.scheme != nil,
           components.queryItems?.isEmpty == false {
            return try parse(components)
        }

        return .init(gatewayURL: nil, qrID: trimmed)
    }

    private static func parse(_ object: [String: Any]) throws -> PermissionGatewayQRPayload {
        guard let qrID = stringValue(object["qr_id"] ?? object["template_id"] ?? object["id"]) else {
            throw ParseError.missingQRID
        }

        let gatewayURL = try stringValue(object["gateway_url"]).map(url)
        return .init(gatewayURL: gatewayURL, qrID: qrID)
    }

    private static func parse(_ components: URLComponents) throws -> PermissionGatewayQRPayload {
        let queryItems = components.queryItems ?? []

        func value(for names: [String]) -> String? {
            queryItems.first { names.contains($0.name) }?.value
        }

        guard let qrID = value(for: ["qr_id", "template_id", "id"]) else {
            throw ParseError.missingQRID
        }

        if let explicitGatewayURL = value(for: ["gateway_url"]) {
            return .init(gatewayURL: try url(explicitGatewayURL), qrID: qrID)
        }

        if ["http", "https"].contains(components.scheme?.lowercased()),
           let host = components.host {
            var gatewayComponents = components
            gatewayComponents.path = ""
            gatewayComponents.query = nil
            gatewayComponents.fragment = nil
            guard let gatewayURL = gatewayComponents.url else {
                throw ParseError.invalidGatewayURL(host)
            }
            return .init(gatewayURL: gatewayURL, qrID: qrID)
        }

        return .init(gatewayURL: nil, qrID: qrID)
    }

    private static func stringValue(_ value: Any?) -> String? {
        guard let string = value as? String else { return nil }
        let trimmed = string.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private static func url(_ value: String) throws -> URL {
        guard let url = URL(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme != nil,
              url.host != nil else {
            throw ParseError.invalidGatewayURL(value)
        }
        return url
    }
}
