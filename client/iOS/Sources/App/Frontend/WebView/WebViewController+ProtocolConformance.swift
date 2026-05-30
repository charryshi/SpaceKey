import Foundation
import PromiseKit
import Shared
import UIKit
import WebKit

extension WebViewController: WebViewControllerProtocol {
    var canGoBack: Bool {
        webView.canGoBack
    }

    var canGoForward: Bool {
        webView.canGoForward
    }

    @objc func goBack() {
        webView.goBack()
    }

    @objc func goForward() {
        webView.goForward()
    }

    var overlayedController: UIViewController? {
        presentedViewController
    }

    func presentOverlayController(controller: UIViewController, animated: Bool) {
        DispatchQueue.main.async { [weak self] in
            self?.dismissOverlayController(animated: false, completion: { [weak self] in
                self?.present(controller, animated: animated, completion: nil)
            })
        }
    }

    func presentAlertController(controller: UIViewController, animated: Bool) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            if let overlayedController {
                overlayedController.present(controller, animated: animated, completion: nil)
            } else {
                present(controller, animated: animated, completion: nil)
            }
        }
    }

    func evaluateJavaScript(_ script: String, completion: ((Any?, (any Error)?) -> Void)?) {
        webView.evaluateJavaScript(script, completionHandler: completion)
    }

    func dismissOverlayController(animated: Bool, completion: (() -> Void)?) {
        dismissAllViewControllersAbove(completion: completion)
    }

    func dismissControllerAboveOverlayController() {
        overlayedController?.dismissAllViewControllersAbove()
    }

    func updateFrontendConnectionState(state: String) {
        emptyStateTimer?.invalidate()
        emptyStateTimer = nil
        latestLoadError = nil

        let requestedState = FrontEndConnectionState(rawValue: state) ?? .unknown
        let resolvedState: FrontEndConnectionState = if connectionState == .authInvalid, requestedState != .connected {
            .authInvalid
        } else {
            requestedState
        }
        isConnected = resolvedState == .connected
        connectionState = resolvedState

        // Possible values: connected, disconnected, auth-invalid
        switch resolvedState {
        case .connected:
            hideEmptyState()
        case .authInvalid:
            showEmptyState()
        case .disconnected, .unknown:
            // Start a 10-second timer. If not interrupted by a 'connected' state, set alpha to 1.
            emptyStateTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: false) { [weak self] _ in
                self?.showEmptyState()
            }
        }
    }

    func navigateToPath(path: String) {
        if let activeURL = server.info.connection.activeURL(), let url = URL(string: activeURL.absoluteString + path) {
            load(request: URLRequest(url: url))
        }
    }

    func showBanner(request: BannerRequest) {
        bannerPresenter.show(on: self, request: request)
    }

    func hideBanner(id: String) {
        bannerPresenter.hide(id: id)
    }

    func load(request: URLRequest) {
        Current.Log.verbose("Requesting webView navigation to \(String(describing: request.url?.absoluteString))")
        guard needsPermissionGatewayFrontendSession(for: request.url) else {
            webView.load(request)
            return
        }

        preparePermissionGatewayFrontendSession().done(on: .main) { [weak self] session in
            guard let self else { return }
            if let frontendURL = self.permissionGatewayFrontendLoadURL(from: session, fallback: request.url),
               request.url?.absoluteString != frontendURL.absoluteString {
                self.webView.load(URLRequest(url: frontendURL))
            } else {
                self.webView.load(request)
            }
        }.catch(on: .main) { [weak self] error in
            self?.handlePermissionGatewayFrontendSessionFailure(error)
        }
    }

    @objc func refresh() {
        let refreshBlock: () -> Void = { [weak self] in
            guard let self else { return }
            // called via menu/keyboard shortcut too
            if let webviewURL = server.info.connection.webviewURL() {
                if webView.url?.baseIsEqual(to: webviewURL) == true, !lastNavigationWasServerError {
                    reload()
                } else {
                    load(request: URLRequest(url: webviewURL))
                }
                hideNoActiveURLError()
            } else {
                showNoActiveURLError()
            }
        }

        if Current.isCatalyst {
            refreshBlock()
        } else {
            Current.connectivity.syncNetworkInformation {
                refreshBlock()
            }
        }
        updateDatabaseAndPanels()
    }

    @objc func refreshIfDisconnected() {
        guard connectionState != .connected else { return }
        refresh()
    }
}

private extension WebViewController {
    struct PermissionGatewayFrontendSessionResponse: Decodable {
        let ok: Bool
        let grantID: String?
        let frontendURL: String?
        let expiresIn: Int?

        enum CodingKeys: String, CodingKey {
            case ok
            case grantID = "grant_id"
            case frontendURL = "frontend_url"
            case expiresIn = "expires_in"
        }
    }

    struct PermissionGatewayFrontendCredentials {
        let accessToken: String
        let devicePublicKey: String?
    }

    struct PermissionGatewayFrontendSessionResult {
        let frontendURL: URL?
        let sessionURL: URL
    }

    enum PermissionGatewayFrontendSessionError: LocalizedError {
        case noAPI
        case missingAccessToken
        case noActiveURL
        case invalidResponse
        case server(statusCode: Int, message: String)
        case missingCookie

        var errorDescription: String? {
            switch self {
            case .noAPI:
                return "Permission gateway API is not available."
            case .missingAccessToken:
                return "Permission gateway token is not available."
            case .noActiveURL:
                return "Permission gateway URL is not available."
            case .invalidResponse:
                return "Permission gateway frontend session returned an invalid response."
            case let .server(statusCode, message):
                return "Permission gateway frontend session failed (\(statusCode)): \(message)"
            case .missingCookie:
                return "Permission gateway frontend session did not return a WebView cookie."
            }
        }
    }

    func needsPermissionGatewayFrontendSession(for url: URL?) -> Bool {
        guard server.info.setting(for: .permissionGatewayGrantID) != nil,
              let url,
              ["http", "https"].contains(url.scheme?.lowercased() ?? "") else {
            return false
        }

        let allowedURLs = [
            server.info.connection.activeURL(),
            permissionGatewayFrontendSessionBaseURL(),
            resolvedPermissionGatewayFrontendURL(from: nil),
        ].compactMap(\.self)

        guard allowedURLs.contains(where: { url.baseIsEqual(to: $0) }) else {
            return false
        }

        return !url.path.hasPrefix("/api")
    }

    func preparePermissionGatewayFrontendSession() -> Promise<PermissionGatewayPreparedFrontendSession> {
        if let permissionGatewayFrontendSessionPromise {
            return permissionGatewayFrontendSessionPromise
        }

        let promise = firstly { () -> Promise<PermissionGatewayFrontendCredentials> in
            guard let api = Current.api(for: server) else {
                throw PermissionGatewayFrontendSessionError.noAPI
            }
            return api.tokenManager.authDictionaryForWebView(forceRefresh: false).map { dictionary in
                guard let accessToken = dictionary["access_token"] as? String else {
                    throw PermissionGatewayFrontendSessionError.missingAccessToken
                }
                return PermissionGatewayFrontendCredentials(
                    accessToken: accessToken,
                    devicePublicKey: dictionary["device_public_key"] as? String
                )
            }
        }.then { [weak self] credentials -> Promise<PermissionGatewayPreparedFrontendSession> in
            guard let self else { return .value(.init(frontendURL: nil)) }
            return self.preparePermissionGatewayFrontendSession(credentials: credentials)
        }.ensure(on: .main) { [weak self] in
            self?.permissionGatewayFrontendSessionPromise = nil
        }

        permissionGatewayFrontendSessionPromise = promise
        return promise
    }

    func preparePermissionGatewayFrontendSession(
        credentials: PermissionGatewayFrontendCredentials
    ) -> Promise<PermissionGatewayPreparedFrontendSession> {
        guard let baseURL = permissionGatewayFrontendSessionBaseURL() else {
            return .init(error: PermissionGatewayFrontendSessionError.noActiveURL)
        }

        return createPermissionGatewayFrontendSession(
            baseURL: baseURL,
            credentials: credentials
        ).then { [weak self] session -> Promise<PermissionGatewayPreparedFrontendSession> in
            guard let self else { return .value(.init(frontendURL: session.frontendURL)) }

            let frontendURL = self.resolvedPermissionGatewayFrontendURL(from: session.frontendURL)
            if let frontendURL {
                self.persistPermissionGatewayFrontendURL(frontendURL)
            }

            guard let frontendBaseURL = frontendURL?.serverBaseURL(),
                  !session.sessionURL.baseIsEqual(to: frontendBaseURL) else {
                return .value(.init(frontendURL: frontendURL))
            }

            Current.Log.info("Preparing permission gateway frontend session for WebView origin \(frontendBaseURL)")
            return self.createPermissionGatewayFrontendSession(
                baseURL: frontendBaseURL,
                credentials: credentials
            ).map { secondSession in
                let resolvedFrontendURL = self.resolvedPermissionGatewayFrontendURL(
                    from: secondSession.frontendURL ?? frontendURL
                )
                if let resolvedFrontendURL {
                    self.persistPermissionGatewayFrontendURL(resolvedFrontendURL)
                }
                return .init(frontendURL: resolvedFrontendURL ?? frontendURL)
            }
        }
    }

    func createPermissionGatewayFrontendSession(
        baseURL: URL,
        credentials: PermissionGatewayFrontendCredentials
    ) -> Promise<PermissionGatewayFrontendSessionResult> {
        Promise { seal in
            guard let sessionURL = permissionGatewayFrontendSessionURL(baseURL: baseURL) else {
                seal.reject(PermissionGatewayFrontendSessionError.noActiveURL)
                return
            }

            var request = URLRequest(url: sessionURL)
            request.httpMethod = "POST"
            request.setValue("Bearer \(credentials.accessToken)", forHTTPHeaderField: "Authorization")
            if let devicePublicKey = credentials.devicePublicKey {
                request.setValue(devicePublicKey, forHTTPHeaderField: "X-Device-Public-Key")
            }
            request.setValue("application/json", forHTTPHeaderField: "Accept")
            request.setValue("0", forHTTPHeaderField: "Content-Length")

            URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
                if let error {
                    seal.reject(error)
                    return
                }

                guard let self, let httpResponse = response as? HTTPURLResponse, let data else {
                    seal.reject(PermissionGatewayFrontendSessionError.invalidResponse)
                    return
                }

                guard (200 ..< 300).contains(httpResponse.statusCode) else {
                    seal.reject(PermissionGatewayFrontendSessionError.server(
                        statusCode: httpResponse.statusCode,
                        message: Self.gatewayErrorMessage(from: data)
                    ))
                    return
                }

                if let response = try? JSONDecoder().decode(PermissionGatewayFrontendSessionResponse.self, from: data),
                   let frontendURL = response.frontendURL {
                    Current.Log.verbose("Prepared permission gateway frontend session for \(frontendURL)")
                }

                let cookies = HTTPCookie.cookies(
                    withResponseHeaderFields: Self.stringHeaderFields(from: httpResponse),
                    for: sessionURL
                )

                guard !cookies.isEmpty else {
                    seal.reject(PermissionGatewayFrontendSessionError.missingCookie)
                    return
                }

                DispatchQueue.main.async {
                    let cookieStore = self.webView.configuration.websiteDataStore.httpCookieStore
                    when(fulfilled: cookies.map { cookie in
                        Promise<Void> { cookieSeal in
                            cookieStore.setCookie(cookie) {
                                cookieSeal.fulfill(())
                            }
                        }
                    }).done {
                        seal.fulfill(.init(
                            frontendURL: self.permissionGatewayFrontendURL(from: data),
                            sessionURL: sessionURL
                        ))
                    }.catch { error in
                        seal.reject(error)
                    }
                }
            }.resume()
        }
    }

    func handlePermissionGatewayFrontendSessionFailure(_ error: Error) {
        let displayError = PermissionGatewayFrontendSessionDisplayError(underlying: error)
        Current.Log.error("Failed to prepare permission gateway frontend session: \(displayError.localizedDescription)")

        latestLoadError = displayError
        connectionState = .disconnected
        isConnected = false
        emptyStateTimer?.invalidate()
        emptyStateTimer = nil

        showEmptyState()
        showBanner(request: .init(
            id: "permission-gateway-frontend-session-failed",
            title: "网关会话建立失败",
            message: displayError.localizedDescription,
            duration: .forever,
            dimming: .none,
            style: .warning
        ))
    }

    func permissionGatewayFrontendSessionBaseURL() -> URL? {
        if let rawURL = server.info.setting(for: .permissionGatewayURL),
           let url = URL(string: rawURL) {
            return url
        }

        return server.info.connection.activeURL()
    }

    func permissionGatewayFrontendSessionURL(baseURL: URL) -> URL? {
        baseURL
            .appendingPathComponent("v1", isDirectory: false)
            .appendingPathComponent("frontend", isDirectory: false)
            .appendingPathComponent("session", isDirectory: false)
    }

    func resolvedPermissionGatewayFrontendURL(from responseURL: URL?) -> URL? {
        if let responseURL {
            return responseURL
        }

        guard let rawURL = server.info.setting(for: .permissionGatewayFrontendURL) else {
            return nil
        }

        return URL(string: rawURL)
    }

    func permissionGatewayFrontendURL(from data: Data) -> URL? {
        guard let response = try? JSONDecoder().decode(PermissionGatewayFrontendSessionResponse.self, from: data),
              let rawURL = response.frontendURL else {
            return nil
        }

        return URL(string: rawURL)
    }

    func permissionGatewayFrontendLoadURL(
        from session: PermissionGatewayPreparedFrontendSession,
        fallback: URL?
    ) -> URL? {
        guard let url = session.frontendURL ?? fallback else {
            return nil
        }

        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
            return url
        }

        var queryItems = components.queryItems ?? []
        if !queryItems.contains(where: { $0.name == "external_auth" }) {
            queryItems.append(.init(name: "external_auth", value: "1"))
        }
        components.queryItems = queryItems

        return components.url ?? url
    }

    func persistPermissionGatewayFrontendURL(_ url: URL) {
        let value = url.absoluteString
        guard server.info.setting(for: .permissionGatewayFrontendURL) != value else {
            return
        }

        server.update { info in
            info.setSetting(value: value, for: .permissionGatewayFrontendURL)
        }
    }

    static func stringHeaderFields(from response: HTTPURLResponse) -> [String: String] {
        response.allHeaderFields.reduce(into: [String: String]()) { result, element in
            guard let key = element.key as? String else { return }
            result[key] = String(describing: element.value)
        }
    }

    static func gatewayErrorMessage(from data: Data) -> String {
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

private struct PermissionGatewayFrontendSessionDisplayError: LocalizedError {
    let underlying: Error

    var errorDescription: String? {
        "无法建立网关 WebView 会话。请检查 /v1/frontend/session 是否返回 200，并确认 Set-Cookie 可用于 WebView。底层错误：\(underlying.localizedDescription)"
    }
}
