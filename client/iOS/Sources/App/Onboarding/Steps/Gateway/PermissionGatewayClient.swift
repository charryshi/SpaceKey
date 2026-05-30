import Foundation
import PromiseKit

final class PermissionGatewayClient {
    enum ClientError: LocalizedError {
        case invalidResponse
        case server(statusCode: Int, message: String)

        var errorDescription: String? {
            switch self {
            case .invalidResponse:
                return "权限网关返回了无效响应。"
            case let .server(statusCode, message):
                return "权限网关错误 \(statusCode)：\(message)"
            }
        }
    }

    private let gatewayURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    init(gatewayURL: URL, session: URLSession = .shared) {
        self.gatewayURL = gatewayURL
        self.session = session
    }

    func activate(
        qrID: String,
        verificationCode: String,
        identity: PermissionGatewayDeviceIdentity
    ) -> Promise<PermissionGatewayAuthResponse> {
        let payload = PermissionGatewayActivationRequest(
            qrID: qrID,
            verificationCode: verificationCode,
            devicePublicKey: identity.devicePublicKey,
            appInstanceID: identity.appInstanceID
        )

        return Promise { seal in
            var request = URLRequest(url: endpoint(["v1", "activation", "verify"]))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            do {
                request.httpBody = try encoder.encode(payload)
            } catch {
                seal.reject(error)
                return
            }

            let task = session.dataTask(with: request) { [decoder] data, response, error in
                if let error {
                    seal.reject(error)
                    return
                }

                guard let httpResponse = response as? HTTPURLResponse, let data else {
                    seal.reject(ClientError.invalidResponse)
                    return
                }

                guard (200 ..< 300).contains(httpResponse.statusCode) else {
                    seal.reject(ClientError.server(
                        statusCode: httpResponse.statusCode,
                        message: Self.errorMessage(from: data)
                    ))
                    return
                }

                do {
                    seal.fulfill(try decoder.decode(PermissionGatewayAuthResponse.self, from: data))
                } catch {
                    seal.reject(error)
                }
            }
            task.resume()
        }
    }

    private func endpoint(_ pathComponents: [String]) -> URL {
        pathComponents.reduce(gatewayURL) { url, component in
            url.appendingPathComponent(component, isDirectory: false)
        }
    }

    private static func errorMessage(from data: Data) -> String {
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let detail = object["detail"] {
            return String(describing: detail)
        }

        if let body = String(data: data, encoding: .utf8), !body.isEmpty {
            return body
        }

        return "Unknown error"
    }
}
