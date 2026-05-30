import PromiseKit
import Shared
import SwiftUI

struct PermissionGatewayActivationView: View {
    private enum FocusedField {
        case verificationCode
    }

    @Environment(\.dismiss) private var dismiss

    @State private var gatewayURLString = "https://ha.aivo.19.md"
    @State private var qrID = ""
    @State private var verificationCode = ""
    @State private var isActivating = false
    @State private var showScanner = false
    @State private var showError = false
    @State private var errorMessage = ""
    @FocusState private var focusedField: FocusedField?

    private let service = PermissionGatewayOnboardingService()
    private let embeddedInNavigationView: Bool
    private let showsCloseButton: Bool
    private let onSuccess: (Server) -> Void

    init(
        embeddedInNavigationView: Bool = true,
        showsCloseButton: Bool = true,
        onSuccess: @escaping (Server) -> Void
    ) {
        self.embeddedInNavigationView = embeddedInNavigationView
        self.showsCloseButton = showsCloseButton
        self.onSuccess = onSuccess
    }

    @ViewBuilder
    var body: some View {
        if embeddedInNavigationView {
            NavigationView {
                content
            }
        } else {
            content
        }
    }

    private var content: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DesignSystem.Spaces.two) {
                header
                scanRoomQRCodeCard
                verificationCodeCard
                advancedSettings
            }
            .padding()
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .navigationTitle("房间授权登录")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                if showsCloseButton {
                    CloseButton {
                        dismiss()
                    }
                }
            }
        }
        .sheet(isPresented: $showScanner) {
            PermissionGatewayQRScannerView { code in
                handleScannedCode(code)
            }
        }
        .alert(isPresented: $showError) {
            Alert(
                title: Text(verbatim: "登录失败"),
                message: Text(verbatim: errorMessage),
                dismissButton: .default(Text(verbatim: "知道了"))
            )
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: DesignSystem.Spaces.one) {
            Image(systemName: "qrcode.viewfinder")
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(Color.haPrimary)

            Text("扫描房间二维码")
                .font(DesignSystem.Font.title.bold())

            Text("请扫描管理员贴在房间或设备区域的授权二维码。扫码成功后，再输入认证码完成登录。")
                .font(DesignSystem.Font.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, DesignSystem.Spaces.two)
    }

    private var scanRoomQRCodeCard: some View {
        card {
            VStack(alignment: .leading, spacing: DesignSystem.Spaces.two) {
                stepHeader(number: "1", title: "扫描房间二维码")

                Text(qrID.isEmpty ? "尚未读取二维码" : "已读取房间二维码")
                    .font(DesignSystem.Font.body.bold())

                if !qrID.isEmpty {
                    Text("二维码编号：\(trimmedQRID)")
                        .font(DesignSystem.Font.footnote)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }

                Button {
                    showScanner = true
                } label: {
                    Label(qrID.isEmpty ? "开始扫码" : "重新扫码", systemImage: "qrcode.viewfinder")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.primaryButton)
            }
        }
    }

    private var verificationCodeCard: some View {
        card {
            VStack(alignment: .leading, spacing: DesignSystem.Spaces.two) {
                stepHeader(number: "2", title: "输入认证码")

                Text("请输入管理员提供的认证码。认证码不会保存在二维码里，每次授权都会生成独立登录密钥。")
                    .font(DesignSystem.Font.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                SecureField("认证码", text: $verificationCode)
                    .textContentType(.oneTimeCode)
                    .keyboardType(.numberPad)
                    .focused($focusedField, equals: .verificationCode)
                    .disabled(qrID.isEmpty || isActivating)
                    .textFieldStyle(.roundedBorder)

                Button {
                    activate()
                } label: {
                    HStack {
                        Text("登录")
                        Spacer()
                        if isActivating {
                            ProgressView()
                        } else {
                            Image(systemName: "arrow.right")
                        }
                    }
                }
                .buttonStyle(.primaryButton)
                .disabled(!canActivate)
            }
        }
        .opacity(qrID.isEmpty ? 0.55 : 1)
    }

    private var advancedSettings: some View {
        DisclosureGroup("高级设置") {
            VStack(alignment: .leading, spacing: DesignSystem.Spaces.one) {
                Text("仅在管理员要求时修改网关地址。普通用户请直接扫码。")
                    .font(DesignSystem.Font.footnote)
                    .foregroundStyle(.secondary)

                TextField("网关地址", text: $gatewayURLString)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .autocapitalization(.none)
                    .textFieldStyle(.roundedBorder)

                TextField("二维码编号", text: $qrID)
                    .autocorrectionDisabled()
                    .autocapitalization(.none)
                    .textFieldStyle(.roundedBorder)
            }
            .padding(.top, DesignSystem.Spaces.one)
        }
        .padding()
        .background(Color(uiColor: .secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func stepHeader(number: String, title: String) -> some View {
        HStack(spacing: DesignSystem.Spaces.one) {
            Text(number)
                .font(DesignSystem.Font.footnote.bold())
                .foregroundStyle(.white)
                .frame(width: 24, height: 24)
                .background(Color.haPrimary)
                .clipShape(Circle())

            Text(title)
                .font(DesignSystem.Font.body.bold())
        }
    }

    private func card<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(uiColor: .secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var canActivate: Bool {
        !isActivating &&
            gatewayURL != nil &&
            !qrID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            !verificationCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var trimmedQRID: String {
        qrID.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var gatewayURL: URL? {
        URL(string: gatewayURLString.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    private var permissionSummary: String? {
        guard !trimmedQRID.isEmpty else { return nil }
        return "二维码编号：\(trimmedQRID)"
    }

    private func activate() {
        guard let gatewayURL else {
            show(error: "请输入有效的网关地址。")
            return
        }

        isActivating = true
        service.activate(
            gatewayURL: gatewayURL,
            qrID: qrID.trimmingCharacters(in: .whitespacesAndNewlines),
            verificationCode: verificationCode.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        .ensure(on: .main) {
            isActivating = false
        }
        .done(on: .main) { server in
            onSuccess(server)
            dismiss()
        }
        .catch(on: .main) { error in
            show(error: error.localizedDescription)
        }
    }

    private func handleScannedCode(_ code: String) {
        do {
            let payload = try PermissionGatewayQRPayload.parse(code)
            qrID = payload.qrID
            if let gatewayURL = payload.gatewayURL {
                gatewayURLString = gatewayURL.absoluteString
            }
            focusedField = .verificationCode
        } catch {
            show(error: error.localizedDescription)
        }
    }

    private func show(error: String) {
        errorMessage = error
        showError = true
    }
}

#Preview {
    PermissionGatewayActivationView { _ in }
}
