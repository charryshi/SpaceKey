import Shared
import SwiftUI

struct PermissionGatewayQRScannerView: View {
    private enum Constants {
        static let cameraSquareSize: CGFloat = 320
    }

    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel = PermissionGatewayQRScannerViewModel()
    @StateObject private var cameraDataModel = BarcodeScannerDataModel()

    private let onCode: (String) -> Void
    private let flashlightIcon = MaterialDesignIcons.flashlightIcon.image(
        ofSize: .init(width: 24, height: 24),
        color: .white
    )

    init(onCode: @escaping (String) -> Void) {
        self.onCode = onCode
    }

    var body: some View {
        ZStack(alignment: .top) {
            ZStack {
                cameraBackground
                cameraSquare
            }
            .ignoresSafeArea()
            .frame(maxWidth: .infinity)
            .frame(maxHeight: .infinity)

            topInformation
        }
        .onAppear {
            cameraDataModel.delegate = viewModel
        }
        .onDisappear {
            cameraDataModel.turnOffFlashlight()
            cameraDataModel.stop()
        }
        .onChange(of: viewModel.scannedCode) { code in
            guard let code else { return }
            onCode(code)
            dismiss()
        }
    }

    private var topInformation: some View {
        VStack(spacing: DesignSystem.Spaces.one) {
            HStack {
                Spacer()
                ModalCloseButton(tint: .white) {
                    dismiss()
                }
            }

            Text("扫描房间二维码")
                .padding(.top)
                .font(DesignSystem.Font.title2.bold())
                .foregroundColor(.white)

            Text("请将房间或设备区域的授权二维码放入取景框内。")
                .font(DesignSystem.Font.subheadline)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
        }
        .padding()
    }

    private var cameraBackground: some View {
        GeometryReader { proxy in
            BarcodeScannerCameraView(screenSize: proxy.size, model: cameraDataModel)
                .ignoresSafeArea()
                .frame(maxWidth: .infinity)
                .frame(maxHeight: .infinity)
                .overlay {
                    Color.black.opacity(0.8)
                }
        }
    }

    private var cameraSquare: some View {
        BarcodeScannerCameraView(screenSize: .zero, model: cameraDataModel, shouldStartCamera: false)
            .ignoresSafeArea()
            .frame(maxWidth: .infinity)
            .frame(maxHeight: .infinity)
            .mask {
                RoundedRectangle(cornerSize: CGSize(width: 20, height: 20))
                    .frame(width: Constants.cameraSquareSize, height: Constants.cameraSquareSize)
            }
            .shadow(color: .haPrimary.opacity(0.8), radius: 10, x: 0, y: 0)
            .overlay {
                VStack {
                    Spacer()
                    Button(action: {
                        cameraDataModel.toggleFlashlight()
                    }, label: {
                        Image(uiImage: flashlightIcon)
                            .padding()
                            .background(Color(uiColor: .init(hex: "#384956")))
                            .mask(Circle())
                            .padding([.trailing, .bottom], DesignSystem.Spaces.two)
                    })
                    .frame(maxWidth: .infinity, alignment: .trailing)
                }
                .frame(width: Constants.cameraSquareSize, height: Constants.cameraSquareSize)
            }
    }
}

final class PermissionGatewayQRScannerViewModel: ObservableObject, BarcodeScannerDataModelDelegate {
    @Published var scannedCode: String?

    private var hasScanned = false

    func didDetectBarcode(_ code: String, format: String) {
        guard !hasScanned else { return }
        hasScanned = true
        DispatchQueue.main.async {
            self.scannedCode = code
        }
    }
}

#Preview {
    PermissionGatewayQRScannerView { _ in }
}
