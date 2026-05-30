import Foundation

struct GatewayActivationRequest: Encodable {
    let qrId: String
    let verificationCode: String
    let devicePublicKey: String
    let appInstanceId: String

    enum CodingKeys: String, CodingKey {
        case qrId = "qr_id"
        case verificationCode = "verification_code"
        case devicePublicKey = "device_public_key"
        case appInstanceId = "app_instance_id"
    }
}

struct GatewayRefreshRequest: Encodable {
    let refreshToken: String
    let devicePublicKey: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
        case devicePublicKey = "device_public_key"
    }
}

struct GatewayFrontendSessionResponse: Decodable {
    let ok: Bool
    let grantId: String
    let frontendURL: String
    let frontendSameOrigin: Bool?
    let requiresExternalAuthBridge: Bool?
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case ok
        case grantId = "grant_id"
        case frontendURL = "frontend_url"
        case frontendSameOrigin = "frontend_same_origin"
        case requiresExternalAuthBridge = "requires_external_auth_bridge"
        case expiresIn = "expires_in"
    }
}

struct GatewayAuthResponse: Decodable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int
    let grantId: String
    let expiresAt: String?
    let permissionSummary: [String: PermissionValue]

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
        case grantId = "grant_id"
        case expiresAt = "expires_at"
        case permissionSummary = "permission_summary"
    }
}

struct GatewayPersistedServerSettings: Codable, Equatable {
    let baseURL: URL
    let grantId: String
    let uploadLocation: Bool
    let uploadSensors: Bool

    init(
        baseURL: URL,
        grantId: String,
        uploadLocation: Bool = false,
        uploadSensors: Bool = false
    ) {
        self.baseURL = baseURL
        self.grantId = grantId
        self.uploadLocation = uploadLocation
        self.uploadSensors = uploadSensors
    }
}

enum PermissionValue: Decodable {
    case string(String)
    case bool(Bool)
    case array([String])

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode([String].self) {
            self = .array(value)
        } else {
            self = .string(try container.decode(String.self))
        }
    }
}

final class PermissionGatewayClient {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func activate(
        qrId: String,
        verificationCode: String,
        devicePublicKey: String,
        appInstanceId: String
    ) async throws -> GatewayAuthResponse {
        let request = GatewayActivationRequest(
            qrId: qrId,
            verificationCode: verificationCode,
            devicePublicKey: devicePublicKey,
            appInstanceId: appInstanceId
        )
        return try await post(path: "/v1/activation/verify", body: request)
    }

    func refresh(refreshToken: String, devicePublicKey: String) async throws -> GatewayAuthResponse {
        let request = GatewayRefreshRequest(refreshToken: refreshToken, devicePublicKey: devicePublicKey)
        return try await post(path: "/v1/auth/refresh", body: request)
    }

    func makeHARequest(path: String, accessToken: String, devicePublicKey: String) -> URLRequest {
        var request = URLRequest(url: baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue(devicePublicKey, forHTTPHeaderField: "X-Device-Public-Key")
        return request
    }

    func establishFrontendSession(
        accessToken: String,
        devicePublicKey: String
    ) async throws -> GatewayFrontendSessionResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent("v1/frontend/session"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue(devicePublicKey, forHTTPHeaderField: "X-Device-Public-Key")
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, (200..<300).contains(httpResponse.statusCode) else {
            throw URLError(.userAuthenticationRequired)
        }
        return try JSONDecoder().decode(GatewayFrontendSessionResponse.self, from: data)
    }

    func resolvedFrontendURL(from response: GatewayFrontendSessionResponse) throws -> URL {
        guard let url = URL(string: response.frontendURL, relativeTo: baseURL)?.absoluteURL else {
            throw URLError(.badURL)
        }
        return url
    }

    func defaultPersistedServerSettings(grantId: String) -> GatewayPersistedServerSettings {
        GatewayPersistedServerSettings(
            baseURL: baseURL,
            grantId: grantId,
            uploadLocation: false,
            uploadSensors: false
        )
    }

    private func post<RequestBody: Encodable, ResponseBody: Decodable>(
        path: String,
        body: RequestBody
    ) async throws -> ResponseBody {
        var request = URLRequest(url: baseURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, (200..<300).contains(httpResponse.statusCode) else {
            throw URLError(.userAuthenticationRequired)
        }
        return try JSONDecoder().decode(ResponseBody.self, from: data)
    }
}
