import Shared

enum WebViewEmptyStateStyle: Equatable {
    case disconnected
    case permissionGatewayDisconnected
    case unauthenticated
    case recoveredServerNeedingReauthentication

    enum HeaderAccessory {
        case none
        case settings
        case close
    }

    var title: String {
        switch self {
        case .disconnected:
            L10n.WebView.EmptyState.title
        case .permissionGatewayDisconnected:
            "网关连接失败"
        case .unauthenticated:
            L10n.Unauthenticated.Message.title
        case .recoveredServerNeedingReauthentication:
            L10n.Onboarding.ServerImport.Reauthenticate.title
        }
    }

    var body: String {
        switch self {
        case .disconnected:
            L10n.WebView.EmptyState.body
        case .permissionGatewayDisconnected:
            "无法加载授权设备界面。请检查网络连接，或联系管理员确认网关前端会话和 WebSocket 认证是否正常。"
        case .unauthenticated:
            L10n.Unauthenticated.Message.body
        case .recoveredServerNeedingReauthentication:
            ""
        }
    }

    var primaryButtonTitle: String {
        switch self {
        case .disconnected, .permissionGatewayDisconnected:
            L10n.WebView.EmptyState.retryButton
        case .unauthenticated:
            L10n.WebView.EmptyState.reauthenticateButton
        case .recoveredServerNeedingReauthentication:
            L10n.Onboarding.ServerImport.Reauthenticate.continueButton
        }
    }

    var secondaryButtonTitle: String {
        switch self {
        case .disconnected, .permissionGatewayDisconnected, .unauthenticated, .recoveredServerNeedingReauthentication:
            L10n.WebView.EmptyState.openSettingsButton
        }
    }

    var leadingHeaderAccessory: HeaderAccessory {
        switch self {
        case .disconnected, .permissionGatewayDisconnected:
            .none
        case .unauthenticated:
            .settings
        case .recoveredServerNeedingReauthentication:
            .none
        }
    }

    var trailingHeaderAccessory: HeaderAccessory {
        switch self {
        case .disconnected, .unauthenticated:
            .close
        case .permissionGatewayDisconnected:
            .none
        case .recoveredServerNeedingReauthentication:
            .settings
        }
    }

    var showsSecondarySettingsButton: Bool {
        switch self {
        case .disconnected:
            true
        case .permissionGatewayDisconnected, .unauthenticated, .recoveredServerNeedingReauthentication:
            false
        }
    }

    var showsServerPicker: Bool {
        switch self {
        case .disconnected, .unauthenticated, .recoveredServerNeedingReauthentication:
            true
        case .permissionGatewayDisconnected:
            false
        }
    }

    var urlPickerTitle: String {
        switch self {
        case .disconnected, .permissionGatewayDisconnected, .unauthenticated:
            L10n.WebView.EmptyState.reauthenticateButton
        case .recoveredServerNeedingReauthentication:
            L10n.Onboarding.ServerImport.Reauthenticate.urlPickerTitle
        }
    }
}
